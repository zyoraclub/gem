from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from app.scraper.gem_api_scraper import GEMScraper
from app.services.sheets_service import SheetsService
from app.database import get_db
from app.auth import get_current_user
from app.models import User

router = APIRouter()
scraper = GEMScraper()


class ScrapeToSheetRequest(BaseModel):
    query: str
    sheet_id: str
    tab_name: Optional[str] = "Sheet1"
    max_products: Optional[int] = 100
    category_index: Optional[int] = 0


@router.get("/search")
async def search_products(
    q: str = Query(..., description="Search query like 'laptop', 'chair', 'safety shoes'"),
    page: int = Query(1, ge=1, description="Page number"),
    sort: str = Query("price_in_asc", description="Sort: price_in_asc, price_in_desc, relevance"),
    category_index: int = Query(0, ge=0, description="Which category to use (0 = most relevant)")
):
    """Search products by keyword - automatically finds relevant category"""
    result = scraper.search_products(q, page, sort, category_index)
    return result


@router.get("/search/all")
async def search_all_categories(
    q: str = Query(..., description="Search query"),
    max_per_category: int = Query(10, ge=1, le=50, description="Max products per category")
):
    """Search across ALL matching categories and combine results"""
    result = scraper.search_all_categories(q, max_per_category)
    return result


@router.get("/categories")
async def get_categories(q: str = Query(..., description="Search query")):
    """Get matching categories for a search term"""
    categories = scraper.search_categories(q)
    return {"query": q, "categories": categories, "count": len(categories)}


@router.get("/products/{category_slug}")
async def get_products(
    category_slug: str,
    page: int = Query(1, ge=1, description="Page number"),
    sort: str = Query("price_in_asc", description="Sort: price_in_asc, price_in_desc, relevance"),
    realtime: bool = Query(False, description="Fetch real-time prices from product pages (slower but accurate)")
):
    """Get products by exact category slug. Use realtime=true for accurate live prices."""
    if realtime:
        result = scraper.get_products_with_realtime_prices(category_slug, page, sort)
    else:
        result = scraper.get_products_by_category(category_slug, page, sort)
    return result


@router.get("/products/{category_slug}/all")
async def get_all_products(
    category_slug: str,
    max_products: int = Query(None, description="Max products to fetch"),
    realtime: bool = Query(False, description="Fetch real-time prices from product pages (slower but accurate)")
):
    """Get all products from a category (handles pagination). Use realtime=true for accurate live prices."""
    products = scraper.get_all_products(category_slug, max_products)
    
    # If realtime prices requested, fetch actual prices from product pages
    if realtime and products:
        updated = 0
        for product in products:
            url = product.get("url")
            if url:
                realtime_price = scraper.get_realtime_price(url)
                if realtime_price is not None:
                    product["cached_price"] = product.get("final_price")
                    product["final_price"] = realtime_price
                    product["realtime_price"] = realtime_price
                    updated += 1
        return {"products": products, "count": len(products), "category_slug": category_slug, "realtime_prices_fetched": updated}
    
    return {"products": products, "count": len(products), "category_slug": category_slug}


@router.post("/scrape-to-sheet")
async def scrape_to_sheet(
    request: ScrapeToSheetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Scrape products and save directly to Google Sheet
    
    1. Searches for products by query
    2. Writes results to specified Google Sheet
    """
    sheets_service = SheetsService(db, current_user.id)
    
    # Check if sheets is connected
    status = sheets_service.get_connection_status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="Google Sheets not connected. Please connect first.")
    
    try:
        # Scrape products
        result = scraper.search_products(request.query, page=1, category_index=request.category_index)
        products = result.get("products", [])
        
        # Get more pages if needed
        total_fetched = len(products)
        page = 2
        while total_fetched < request.max_products and result.get("has_more", False):
            result = scraper.search_products(request.query, page=page, category_index=request.category_index)
            products.extend(result.get("products", []))
            total_fetched = len(products)
            page += 1
        
        # Limit to max_products
        products = products[:request.max_products]
        
        if not products:
            return {"success": False, "message": "No products found", "count": 0}
        
        # Prepare data for sheet - headers + rows
        headers = ["Product Name", "Price", "Unit", "Seller", "Product ID", "Category", "Image URL"]
        rows = [headers]
        
        for p in products:
            rows.append([
                p.get("name", ""),
                str(p.get("price", "")),
                p.get("unit", ""),
                p.get("seller", ""),
                p.get("product_id", ""),
                p.get("category", request.query),
                p.get("image_url", "")
            ])
        
        # Write to sheet
        range_name = f"{request.tab_name}!A1"
        write_result = sheets_service.write_sheet(request.sheet_id, range_name, rows)
        
        return {
            "success": True,
            "message": f"Scraped {len(products)} products and saved to sheet",
            "count": len(products),
            "sheet_id": request.sheet_id,
            "range": range_name,
            "rows_written": write_result.get("updatedRows", len(rows))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/append-to-sheet")
async def append_to_sheet(
    request: ScrapeToSheetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Scrape products and APPEND to existing Google Sheet (doesn't overwrite)
    """
    sheets_service = SheetsService(db, current_user.id)
    
    # Check if sheets is connected
    status = sheets_service.get_connection_status()
    if not status.get("connected"):
        raise HTTPException(status_code=400, detail="Google Sheets not connected. Please connect first.")
    
    try:
        # Scrape products
        result = scraper.search_products(request.query, page=1, category_index=request.category_index)
        products = result.get("products", [])
        
        # Get more pages if needed
        total_fetched = len(products)
        page = 2
        while total_fetched < request.max_products and result.get("has_more", False):
            result = scraper.search_products(request.query, page=page, category_index=request.category_index)
            products.extend(result.get("products", []))
            total_fetched = len(products)
            page += 1
        
        # Limit to max_products
        products = products[:request.max_products]
        
        if not products:
            return {"success": False, "message": "No products found", "count": 0}
        
        # Prepare data rows (no headers for append)
        rows = []
        for p in products:
            rows.append([
                p.get("name", ""),
                str(p.get("price", "")),
                p.get("unit", ""),
                p.get("seller", ""),
                p.get("product_id", ""),
                p.get("category", request.query),
                p.get("image_url", "")
            ])
        
        # Append to sheet
        range_name = f"{request.tab_name}!A:G"
        append_result = sheets_service.append_sheet(request.sheet_id, range_name, rows)
        
        return {
            "success": True,
            "message": f"Scraped {len(products)} products and appended to sheet",
            "count": len(products),
            "sheet_id": request.sheet_id,
            "rows_appended": append_result.get("updates", {}).get("updatedRows", len(rows))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
