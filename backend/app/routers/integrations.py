from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel
from app.database import get_db
from app.services.gmail_service import GmailService
from app.services.sheets_service import SheetsService
from app.models import ScrapeStats, OverallStats, Settings, User
from app.auth import get_current_user
import imaplib
import os

router = APIRouter()


class GmailImapSettings(BaseModel):
    email: str
    app_password: str
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993


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


def increment_overall_stat(db: Session, key: str, amount: int):
    """Increment an overall stat"""
    stat = db.query(OverallStats).filter(OverallStats.key == key).first()
    if not stat:
        stat = OverallStats(key=key, value=amount)
        db.add(stat)
    else:
        stat.value += amount
    db.commit()


# ==================== Gmail OAuth ====================

@router.get("/gmail/connect")
async def gmail_connect(db: Session = Depends(get_db)):
    """Start Gmail OAuth flow - redirects to Google"""
    service = GmailService(db)
    try:
        auth_url = service.get_auth_url()
        return {"auth_url": auth_url}
    except FileNotFoundError:
        raise HTTPException(
            status_code=500, 
            detail="client_secrets.json not found. Please add Google OAuth credentials."
        )


@router.get("/gmail/status")
async def gmail_status(db: Session = Depends(get_db)):
    """Check Gmail connection status"""
    service = GmailService(db)
    return service.get_connection_status()


@router.delete("/gmail/disconnect")
async def gmail_disconnect(db: Session = Depends(get_db)):
    """Disconnect Gmail"""
    service = GmailService(db)
    success = service.disconnect()
    return {"disconnected": success}


@router.get("/gmail/fetch-otp")
async def fetch_gmail_otp(
    sender: str = Query("noreply@gem.gov.in", description="Sender email to filter"),
    db: Session = Depends(get_db)
):
    """Fetch latest OTP from Gmail inbox"""
    service = GmailService(db)
    try:
        otp = service.fetch_otp(sender_email=sender)
        if otp:
            return {"otp": otp, "found": True}
        return {"otp": None, "found": False, "message": "No OTP found in recent emails"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Gmail IMAP Settings ====================

def get_user_setting(db: Session, user_id: int, key: str) -> Optional[str]:
    """Get a user-specific setting value from database"""
    user_key = f"user_{user_id}_{key}"
    setting = db.query(Settings).filter(Settings.key == user_key).first()
    return setting.value if setting else None


def set_user_setting(db: Session, user_id: int, key: str, value: str, description: str = ""):
    """Set a user-specific setting value in database"""
    user_key = f"user_{user_id}_{key}"
    setting = db.query(Settings).filter(Settings.key == user_key).first()
    if setting:
        setting.value = value
        setting.updated_at = datetime.utcnow()
    else:
        setting = Settings(key=user_key, value=value, description=description)
        db.add(setting)
    db.commit()


@router.get("/gmail/imap-settings")
async def get_gmail_imap_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get Gmail IMAP configuration for current user"""
    email = get_user_setting(db, current_user.id, "gmail_email") or ""
    db_password = get_user_setting(db, current_user.id, "gmail_app_password")
    has_password = bool(db_password)
    imap_server = get_user_setting(db, current_user.id, "gmail_imap_server") or "imap.gmail.com"
    imap_port = int(get_user_setting(db, current_user.id, "gmail_imap_port") or "993")
    
    return {
        "email": email,
        "has_password": has_password,
        "imap_server": imap_server,
        "imap_port": imap_port,
        "configured": bool(email and has_password)
    }


@router.post("/gmail/imap-settings")
async def save_gmail_imap_settings(
    settings: GmailImapSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save Gmail IMAP configuration for current user"""
    set_user_setting(db, current_user.id, "gmail_email", settings.email, "Gmail email for IMAP")
    set_user_setting(db, current_user.id, "gmail_app_password", settings.app_password, "Gmail app password")
    set_user_setting(db, current_user.id, "gmail_imap_server", settings.imap_server, "IMAP server address")
    set_user_setting(db, current_user.id, "gmail_imap_port", str(settings.imap_port), "IMAP server port")
    
    return {"success": True, "message": "Gmail IMAP settings saved"}


@router.post("/gmail/test-imap")
async def test_gmail_imap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test Gmail IMAP connection for current user"""
    email = get_user_setting(db, current_user.id, "gmail_email")
    password = get_user_setting(db, current_user.id, "gmail_app_password")
    server = get_user_setting(db, current_user.id, "gmail_imap_server") or "imap.gmail.com"
    port = int(get_user_setting(db, current_user.id, "gmail_imap_port") or "993")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Gmail IMAP not configured")
    
    try:
        print(f"[IMAP] Testing connection to {server}:{port} for {email}")
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(email, password)
        mail.select("INBOX")
        mail.logout()
        print(f"[IMAP] SUCCESS: Connected to {email}")
        return {"success": True, "message": f"Successfully connected to {email}"}
    except imaplib.IMAP4.error as e:
        print(f"[IMAP] FAILED: {str(e)}")
        return {"success": False, "message": f"IMAP authentication failed: {str(e)}"}
    except Exception as e:
        print(f"[IMAP] ERROR: {str(e)}")
        return {"success": False, "message": f"Connection failed: {str(e)}"}


# ==================== Google Sheets OAuth ====================

@router.get("/sheets/connect")
async def sheets_connect(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start Google Sheets OAuth flow"""
    service = SheetsService(db, current_user.id)
    try:
        auth_url = service.get_auth_url()
        return {"auth_url": auth_url}
    except FileNotFoundError:
        raise HTTPException(
            status_code=500, 
            detail="client_secrets.json not found. Please add Google OAuth credentials."
        )


@router.get("/sheets/status")
async def sheets_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check Sheets connection status"""
    service = SheetsService(db, current_user.id)
    return service.get_connection_status()


@router.delete("/sheets/disconnect")
async def sheets_disconnect(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Disconnect Google Sheets"""
    service = SheetsService(db, current_user.id)
    success = service.disconnect()
    return {"disconnected": success}


@router.get("/sheets/list")
async def list_spreadsheets(
    max_results: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List available spreadsheets from Google Drive"""
    service = SheetsService(db, current_user.id)
    try:
        sheets = service.list_spreadsheets(max_results)
        return {"spreadsheets": sheets, "count": len(sheets)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sheets/connect/{sheet_id}")
async def connect_sheet(
    sheet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a spreadsheet to connected sheets"""
    service = SheetsService(db, current_user.id)
    try:
        result = service.connect_sheet(sheet_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sheets/connected")
async def get_connected_sheets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all connected sheets"""
    service = SheetsService(db, current_user.id)
    sheets = service.get_connected_sheets()
    return {"sheets": sheets, "count": len(sheets)}


@router.delete("/sheets/connected/{sheet_id}")
async def disconnect_sheet(
    sheet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a sheet from connected sheets"""
    service = SheetsService(db, current_user.id)
    success = service.disconnect_sheet(sheet_id)
    return {"disconnected": success}


@router.get("/sheets/{sheet_id}/tabs")
async def get_sheet_tabs(
    sheet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all tabs in a spreadsheet"""
    service = SheetsService(db, current_user.id)
    try:
        tabs = service.get_sheet_tabs(sheet_id)
        return {"tabs": tabs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sheets/{sheet_id}/read")
async def read_sheet_data(
    sheet_id: str,
    range: str = Query(..., description="Range like 'Sheet1!A1:Z100'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Read data from a sheet range"""
    service = SheetsService(db, current_user.id)
    try:
        data = service.read_sheet(sheet_id, range)
        return {"data": data, "rows": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sheets/{sheet_id}/write")
async def write_sheet_data(
    sheet_id: str,
    range: str = Query(..., description="Range like 'Sheet1!A1'"),
    values: list = Body(..., description="2D array of values"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Write data to a sheet range"""
    service = SheetsService(db, current_user.id)
    try:
        result = service.write_sheet(sheet_id, range, values)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sheets/{sheet_id}/append")
async def append_sheet_data(
    sheet_id: str,
    range: str = Query(default="A1", description="Range to append after"),
    values: list = Body(..., description="2D array of values"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Append data to a sheet (adds rows at the end)"""
    service = SheetsService(db, current_user.id)
    try:
        result = service.append_sheet(sheet_id, range, values)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sheets/{sheet_id}/upsert")
async def upsert_products(
    sheet_id: str,
    products: list = Body(..., description="List of product objects"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Smart update: Updates existing products (by ID) or inserts new ones.
    Also tracks price changes and updates stats in DB.
    """
    service = SheetsService(db, current_user.id)
    try:
        result = service.upsert_products(sheet_id, products)
        
        # Update stats in database
        today_stats = get_or_create_today_stats(db)
        today_stats.total_products_scraped += len(products)
        today_stats.products_updated += result.get("updated", 0)
        today_stats.new_products_found += result.get("inserted", 0)
        today_stats.price_changes_detected += result.get("price_changes", 0)
        today_stats.updated_at = datetime.utcnow()
        
        # Update overall stats
        increment_overall_stat(db, "total_products_scraped", len(products))
        increment_overall_stat(db, "total_new_products", result.get("inserted", 0))
        increment_overall_stat(db, "total_price_changes", result.get("price_changes", 0))
        
        db.commit()
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== OAuth Callback (handles both) ====================

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    db: Session = Depends(get_db)
):
    """OAuth callback handler for both Gmail and Sheets"""
    # Check for OAuth errors from Google
    if error:
        print(f"[OAuth] Google returned error: {error}")
        frontend_url = f"{FRONTEND_URL}/integrations?error={error}"
        return RedirectResponse(url=frontend_url)
    
    if not code:
        print("[OAuth] No authorization code received")
        frontend_url = f"{FRONTEND_URL}/integrations?error=No_authorization_code"
        return RedirectResponse(url=frontend_url)
    
    try:
        # Extract user_id and service from state (format: sheets_user_123 or gmail_user_123)
        user_id = None
        service_name = 'sheets'
        
        if state:
            if 'gmail' in state.lower():
                service_name = 'gmail'
            if '_user_' in state:
                try:
                    user_id = int(state.split('_user_')[1])
                except:
                    pass
        
        print(f"[OAuth] Processing callback for {service_name}, user_id: {user_id}")
        
        if service_name == 'gmail':
            service = GmailService(db)
            result = service.handle_callback(code)
        else:
            service = SheetsService(db, user_id)
            result = service.handle_callback(code)
        
        print(f"[OAuth] Success! Connected: {result}")
        
        # Redirect to frontend integrations page
        frontend_url = f"{FRONTEND_URL}/integrations?{service_name}_connected=true"
        return RedirectResponse(url=frontend_url)
        
    except Exception as e:
        import traceback
        print(f"[OAuth] ERROR: {str(e)}")
        traceback.print_exc()
        # Redirect with error
        error_msg = str(e).replace(" ", "_")[:100]
        frontend_url = f"{FRONTEND_URL}/integrations?error={error_msg}"
        return RedirectResponse(url=frontend_url)
