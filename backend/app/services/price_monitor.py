"""
Price Monitor Service - Automatically monitors and updates prices for scraped products
Reads products from Google Sheet, fetches current prices from GEM, updates if changed
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.scraper.gem_api_scraper import GEMScraper
from app.services.sheets_service import SheetsService
from app.database import SessionLocal
from app.models import PriceHistory
import threading
import time

# Global scheduler state
_monitor_thread: Optional[threading.Thread] = None
_monitor_running = False
_monitor_interval = 3600  # Default: 1 hour (in seconds)
_last_check: Optional[datetime] = None
_last_result: Dict = {}


class PriceMonitor:
    """Monitor prices of products in Google Sheet"""
    
    def __init__(self, db: Session, user_id: int = None):
        self.db = db
        self.user_id = user_id
        self.sheets_service = SheetsService(db, user_id)
        self.scraper = GEMScraper()
    
    def get_products_from_sheet(self, sheet_id: str) -> List[Dict]:
        """
        Read products from Google Sheet
        Actual column structure:
        - A: URL
        - B: Product ID  
        - C: empty
        - D: empty
        - E: Price (selling_price)
        - F: Status
        - K: Last Updated
        - L: Prev Price
        - M: Price Changed flag
        """
        try:
            # Use just A:M to read from first/default sheet tab
            # read_sheet returns List[List[Any]] directly, not a dict
            rows = self.sheets_service.read_sheet(sheet_id, "A:M")
            
            print(f"[Price Monitor] Read {len(rows)} rows from sheet")
            
            if not rows or len(rows) < 2:
                return []
            
            # Skip header rows (first 2 rows are headers/junk based on actual data)
            products = []
            for idx, row in enumerate(rows[2:], start=3):  # Start from row 3
                if len(row) < 1:
                    continue
                
                url = row[0].strip() if len(row) > 0 else ""
                product_id = row[1].strip() if len(row) > 1 else ""
                current_price = row[4].strip() if len(row) > 4 else ""  # Column E (index 4)
                status = row[5].strip().upper() if len(row) > 5 else ""  # Column F (index 5)
                
                # Only include rows with URLs (must be valid GEM URL)
                if url and "mkp.gem.gov.in" in url:
                    products.append({
                        "row_index": idx,
                        "url": url,
                        "product_id": product_id,
                        "name": product_id,
                        "status": status,
                        "stored_price": current_price
                    })
            
            return products
            
        except Exception as e:
            print(f"Error reading sheet: {e}")
            return []
    
    def check_and_update_prices(self, sheet_id: str) -> Dict:
        """
        Check current prices for all products in sheet and update if changed
        
        Returns:
            Summary of price changes
        """
        global _last_check, _last_result
        
        results = {
            "checked_at": datetime.now().isoformat(),
            "total_products": 0,
            "prices_checked": 0,
            "prices_changed": 0,
            "prices_dropped": 0,
            "prices_increased": 0,
            "errors": 0,
            "changes": []
        }
        
        # Get products from sheet
        products = self.get_products_from_sheet(sheet_id)
        results["total_products"] = len(products)
        
        if not products:
            _last_check = datetime.now()
            _last_result = results
            return results
        
        # Check each product
        for product in products:
            url = product["url"]
            row_idx = product["row_index"]
            stored_price_str = product["stored_price"]
            
            try:
                # Parse stored price
                stored_price = None
                if stored_price_str:
                    # Remove currency symbols, commas
                    clean = stored_price_str.replace("₹", "").replace(",", "").strip()
                    try:
                        stored_price = float(clean)
                    except:
                        pass
                
                # Fetch current price from GEM
                current_price = self.scraper.get_realtime_price(url)
                
                if current_price is None:
                    results["errors"] += 1
                    continue
                
                results["prices_checked"] += 1
                
                # Compare prices
                if stored_price is not None and abs(current_price - stored_price) > 0.01:
                    results["prices_changed"] += 1
                    
                    change_percent = ((current_price - stored_price) / stored_price) * 100
                    
                    if current_price < stored_price:
                        results["prices_dropped"] += 1
                    else:
                        results["prices_increased"] += 1
                    
                    change_info = {
                        "row": row_idx,
                        "name": product["name"],
                        "old_price": stored_price,
                        "new_price": current_price,
                        "change_percent": round(change_percent, 2),
                        "direction": "dropped" if current_price < stored_price else "increased"
                    }
                    results["changes"].append(change_info)
                    
                    # Update sheet - Column E for price, Column L for prev price, Column M for flag
                    try:
                        # Update price in column E
                        self.sheets_service.update_cell(sheet_id, f"E{row_idx}", str(current_price))
                        
                        # Store previous price in column L
                        self.sheets_service.update_cell(sheet_id, f"L{row_idx}", str(stored_price))
                        
                        # Mark price changed in column M
                        self.sheets_service.update_cell(sheet_id, f"M{row_idx}", "YES")
                        
                        # Update timestamp in column K
                        now = datetime.now().strftime("%Y-%m-%d %H:%M")
                        self.sheets_service.update_cell(sheet_id, f"K{row_idx}", now)
                        
                    except Exception as e:
                        print(f"Error updating sheet row {row_idx}: {e}")
                    
                    # Log to database
                    try:
                        history = PriceHistory(
                            product_id=str(row_idx),
                            product_url=url,
                            old_price=stored_price,
                            new_price=current_price,
                            change_percent=change_percent
                        )
                        self.db.add(history)
                        self.db.commit()
                    except Exception as e:
                        print(f"Error logging price history: {e}")
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error checking product {url}: {e}")
                results["errors"] += 1
        
        _last_check = datetime.now()
        _last_result = results
        
        return results


def _monitor_loop():
    """Background monitoring loop"""
    global _monitor_running, _monitor_interval
    
    while _monitor_running:
        try:
            # Get first sheet from database
            db = SessionLocal()
            monitor = PriceMonitor(db)
            
            # Get connected sheets
            status = monitor.sheets_service.get_connection_status()
            if status.get("connected"):
                sheets = monitor.sheets_service.list_spreadsheets()
                if sheets:
                    sheet_id = sheets[0]["id"]
                    print(f"\n[Price Monitor] Checking prices for sheet: {sheets[0]['name']}")
                    result = monitor.check_and_update_prices(sheet_id)
                    print(f"[Price Monitor] Checked {result['prices_checked']} products, {result['prices_changed']} changed")
            
            db.close()
            
        except Exception as e:
            print(f"[Price Monitor] Error: {e}")
        
        # Sleep for interval
        for _ in range(int(_monitor_interval)):
            if not _monitor_running:
                break
            time.sleep(1)


def start_monitor(interval_seconds: int = 3600) -> Dict:
    """Start background price monitoring"""
    global _monitor_thread, _monitor_running, _monitor_interval
    
    if _monitor_running:
        return {"status": "already_running", "interval": _monitor_interval}
    
    _monitor_interval = interval_seconds
    _monitor_running = True
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()
    
    return {"status": "started", "interval": interval_seconds}


def stop_monitor() -> Dict:
    """Stop background price monitoring"""
    global _monitor_running
    
    if not _monitor_running:
        return {"status": "not_running"}
    
    _monitor_running = False
    return {"status": "stopped"}


def get_monitor_status() -> Dict:
    """Get current monitoring status"""
    return {
        "running": _monitor_running,
        "interval_seconds": _monitor_interval,
        "interval_human": f"{_monitor_interval // 60} minutes" if _monitor_interval < 3600 else f"{_monitor_interval // 3600} hours",
        "last_check": _last_check.isoformat() if _last_check else None,
        "last_result": _last_result
    }


def run_check_now(sheet_id: str, user_id: int = None) -> Dict:
    """Run price check immediately"""
    db = SessionLocal()
    try:
        monitor = PriceMonitor(db, user_id)
        return monitor.check_and_update_prices(sheet_id)
    finally:
        db.close()
