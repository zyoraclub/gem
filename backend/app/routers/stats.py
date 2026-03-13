from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timedelta
from app.database import get_db
from app.models import ScrapeStats, OverallStats, PriceHistory

router = APIRouter(prefix="/api/stats", tags=["stats"])


def get_or_create_today_stats(db: Session) -> ScrapeStats:
    """Get or create today's stats record"""
    today = date.today()
    stats = db.query(ScrapeStats).filter(ScrapeStats.stat_date == today).first()
    if not stats:
        stats = ScrapeStats(stat_date=today)
        db.add(stats)
        db.commit()
        db.refresh(stats)
    return stats


def get_or_create_overall_stat(db: Session, key: str) -> OverallStats:
    """Get or create an overall stat by key"""
    stat = db.query(OverallStats).filter(OverallStats.key == key).first()
    if not stat:
        stat = OverallStats(key=key, value=0)
        db.add(stat)
        db.commit()
        db.refresh(stat)
    return stat


@router.get("")
async def get_stats(db: Session = Depends(get_db)):
    """Get all statistics"""
    today = date.today()
    
    # Get today's stats
    today_stats = get_or_create_today_stats(db)
    
    # Get overall stats
    total_products = get_or_create_overall_stat(db, "total_products_scraped")
    total_categories = get_or_create_overall_stat(db, "total_categories_scraped")
    total_price_changes = get_or_create_overall_stat(db, "total_price_changes")
    total_new_products = get_or_create_overall_stat(db, "total_new_products")
    
    # Get stats for the last 7 days
    week_ago = today - timedelta(days=7)
    weekly_stats = db.query(ScrapeStats).filter(ScrapeStats.stat_date >= week_ago).all()
    
    weekly_products = sum(s.total_products_scraped for s in weekly_stats)
    weekly_categories = sum(s.total_categories_scraped for s in weekly_stats)
    weekly_price_changes = sum(s.price_changes_detected for s in weekly_stats)
    
    return {
        "today": {
            "products_scraped": today_stats.total_products_scraped,
            "categories_scraped": today_stats.total_categories_scraped,
            "price_changes": today_stats.price_changes_detected,
            "new_products": today_stats.new_products_found,
            "products_updated": today_stats.products_updated
        },
        "weekly": {
            "products_scraped": weekly_products,
            "categories_scraped": weekly_categories,
            "price_changes": weekly_price_changes
        },
        "overall": {
            "total_products": total_products.value,
            "total_categories": total_categories.value,
            "total_price_changes": total_price_changes.value,
            "total_new_products": total_new_products.value
        }
    }


@router.post("/increment")
async def increment_stats(
    products_scraped: int = 0,
    categories_scraped: int = 0,
    price_changes: int = 0,
    new_products: int = 0,
    products_updated: int = 0,
    db: Session = Depends(get_db)
):
    """Increment statistics (called after scraping/upsert operations)"""
    # Update today's stats
    today_stats = get_or_create_today_stats(db)
    today_stats.total_products_scraped += products_scraped
    today_stats.total_categories_scraped += categories_scraped
    today_stats.price_changes_detected += price_changes
    today_stats.new_products_found += new_products
    today_stats.products_updated += products_updated
    today_stats.updated_at = datetime.utcnow()
    
    # Update overall stats
    if products_scraped > 0:
        total_products = get_or_create_overall_stat(db, "total_products_scraped")
        total_products.value += products_scraped
    
    if categories_scraped > 0:
        total_categories = get_or_create_overall_stat(db, "total_categories_scraped")
        total_categories.value += categories_scraped
    
    if price_changes > 0:
        total_pc = get_or_create_overall_stat(db, "total_price_changes")
        total_pc.value += price_changes
    
    if new_products > 0:
        total_np = get_or_create_overall_stat(db, "total_new_products")
        total_np.value += new_products
    
    db.commit()
    
    return {"success": True, "message": "Stats updated"}


@router.get("/history")
async def get_stats_history(days: int = 30, db: Session = Depends(get_db)):
    """Get daily stats history for charting"""
    start_date = date.today() - timedelta(days=days)
    stats = db.query(ScrapeStats).filter(
        ScrapeStats.stat_date >= start_date
    ).order_by(ScrapeStats.stat_date).all()
    
    return [
        {
            "date": s.stat_date.isoformat(),
            "products_scraped": s.total_products_scraped,
            "categories_scraped": s.total_categories_scraped,
            "price_changes": s.price_changes_detected,
            "new_products": s.new_products_found
        }
        for s in stats
    ]
