"""
Price Monitor Router - API endpoints for automatic price monitoring
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.services.price_monitor import (
    start_monitor,
    stop_monitor,
    get_monitor_status,
    run_check_now,
    PriceMonitor
)
from app.services.sheets_service import SheetsService
from app.auth import get_current_user
from app.models import User

router = APIRouter(prefix="/api/monitor", tags=["price-monitor"])


@router.get("/status")
async def monitor_status():
    """Get current price monitoring status"""
    return get_monitor_status()


@router.post("/start")
async def start_monitoring(
    interval_minutes: int = Query(60, ge=5, le=1440, description="Check interval in minutes (5-1440)")
):
    """
    Start automatic price monitoring
    
    - Runs in background
    - Checks prices of all products in connected sheet
    - Updates sheet when prices change
    """
    interval_seconds = interval_minutes * 60
    result = start_monitor(interval_seconds)
    return {
        **result,
        "message": f"Price monitoring started. Will check every {interval_minutes} minutes."
    }


@router.post("/stop")
async def stop_monitoring():
    """Stop automatic price monitoring"""
    result = stop_monitor()
    return {
        **result,
        "message": "Price monitoring stopped." if result["status"] == "stopped" else "Monitor was not running."
    }


@router.post("/check-now")
async def check_prices_now(
    sheet_id: Optional[str] = Query(None, description="Sheet ID to check (uses first sheet if not provided)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run price check immediately
    
    - Fetches current prices from GEM for all products in sheet
    - Updates sheet with new prices
    - Returns summary of changes
    """
    # If no sheet_id, get first connected sheet
    if not sheet_id:
        sheets_service = SheetsService(db, current_user.id)
        status = sheets_service.get_connection_status()
        
        if not status.get("connected"):
            raise HTTPException(status_code=400, detail="Google Sheets not connected")
        
        sheets = sheets_service.list_spreadsheets()
        if not sheets:
            raise HTTPException(status_code=400, detail="No spreadsheets found")
        
        sheet_id = sheets[0]["id"]
    
    result = run_check_now(sheet_id, current_user.id)
    
    return {
        **result,
        "message": f"Checked {result['prices_checked']} products. {result['prices_changed']} price changes detected."
    }


@router.get("/history")
async def get_price_history(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get recent price change history"""
    from app.models import PriceHistory
    
    history = db.query(PriceHistory).order_by(PriceHistory.recorded_at.desc()).limit(limit).all()
    
    return {
        "count": len(history),
        "changes": [
            {
                "product_url": h.product_url,
                "old_price": h.old_price,
                "new_price": h.new_price,
                "change_percent": round(h.change_percent, 2) if h.change_percent else 0,
                "recorded_at": h.recorded_at.isoformat() if h.recorded_at else None
            }
            for h in history
        ]
    }
