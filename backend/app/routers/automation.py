from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import subprocess
import json
import os
import sys

router = APIRouter()

# Add parent directory to path to import otp_handler
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from otp_handler import OTPHandler
except ImportError:
    OTPHandler = None


class FillRequest(BaseModel):
    product_name: str
    price: str
    unit: Optional[str] = ""
    seller: Optional[str] = ""
    product_id: Optional[str] = ""
    category: Optional[str] = ""


class OTPRequest(BaseModel):
    timeout: Optional[int] = 120


@router.get("/check-chrome")
async def check_chrome_connection():
    """Check if Chrome is running with remote debugging on port 9222"""
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:9222/json/version")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return {
                "connected": True,
                "browser": data.get("Browser", "Chrome"),
                "webSocketDebuggerUrl": data.get("webSocketDebuggerUrl", "")
            }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }


@router.post("/fill")
async def fill_form(request: FillRequest):
    """
    Fill a product form in GEM portal via Selenium
    
    This connects to an existing Chrome browser with remote debugging enabled,
    finds the form fields, and fills in the product data.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
    except ImportError:
        raise HTTPException(status_code=500, detail="Selenium not installed. Run: pip install selenium")

    try:
        # Connect to existing Chrome
        options = Options()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=options)
        
        wait = WebDriverWait(driver, 10)
        
        # Try to find and fill common GEM form fields
        # These selectors may need adjustment based on actual GEM portal structure
        filled_fields = []
        
        # Product name / title
        try:
            name_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 
                "input[name*='product_name'], input[name*='title'], input[id*='product'], textarea[name*='description']")))
            name_field.clear()
            name_field.send_keys(request.product_name)
            filled_fields.append("product_name")
        except TimeoutException:
            pass
        
        # Price field
        try:
            price_field = driver.find_element(By.CSS_SELECTOR, 
                "input[name*='price'], input[name*='amount'], input[id*='price'], input[type='number']")
            price_field.clear()
            price_field.send_keys(request.price)
            filled_fields.append("price")
        except:
            pass
        
        # Check if there's a submit button that triggers OTP
        has_submit = False
        try:
            submit_btn = driver.find_element(By.CSS_SELECTOR, 
                "button[type='submit'], input[type='submit'], button.submit-btn, .btn-submit")
            has_submit = True
        except:
            pass
        
        return {
            "success": True,
            "filled_fields": filled_fields,
            "needs_otp": has_submit,
            "message": f"Filled {len(filled_fields)} fields"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fill-and-submit")
async def fill_and_submit(request: FillRequest):
    """
    Fill form and submit, waiting for OTP
    
    This is the full automation flow:
    1. Fill form fields
    2. Click submit
    3. Wait for OTP via Gmail IMAP
    4. Fill OTP and complete submission
    """
    if not OTPHandler:
        raise HTTPException(status_code=500, detail="OTP handler not available. Check otp_handler.py exists.")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        raise HTTPException(status_code=500, detail="Selenium not installed")

    try:
        # Connect to existing Chrome
        options = Options()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=options)
        
        # Initialize OTP handler
        otp_handler = OTPHandler(driver)
        
        # Run the full OTP flow
        success = otp_handler.handle_otp_flow()
        
        return {
            "success": success,
            "message": "Form submitted with OTP" if success else "OTP flow failed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wait-otp")
async def wait_for_otp(request: OTPRequest):
    """
    Wait for OTP to arrive in Gmail and handle it
    
    Uses IMAP to check for new OTP emails, extracts the code,
    fills it in the form, and submits.
    """
    if not OTPHandler:
        raise HTTPException(status_code=500, detail="OTP handler not available")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        raise HTTPException(status_code=500, detail="Selenium not installed")

    try:
        # Connect to existing Chrome
        options = Options()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=options)
        
        # Initialize OTP handler
        otp_handler = OTPHandler(driver)
        
        # Wait for OTP
        otp = otp_handler.otp_fetcher.wait_for_otp(timeout=request.timeout)
        
        if otp:
            # Fill OTP
            filled = otp_handler.fill_otp(otp)
            if filled:
                # Submit
                submitted = otp_handler.submit_otp()
                return {
                    "success": submitted,
                    "otp": otp,
                    "message": "OTP submitted successfully" if submitted else "Failed to submit OTP"
                }
            else:
                return {
                    "success": False,
                    "otp": otp,
                    "message": "Found OTP but failed to fill it in form"
                }
        else:
            return {
                "success": False,
                "message": f"No OTP received within {request.timeout} seconds"
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_automation_status():
    """Get current automation status"""
    chrome_connected = False
    
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:9222/json/version")
        with urllib.request.urlopen(req, timeout=2) as response:
            chrome_connected = True
    except:
        pass
    
    otp_handler_available = OTPHandler is not None
    
    return {
        "chrome_connected": chrome_connected,
        "otp_handler_available": otp_handler_available,
        "ready": chrome_connected and otp_handler_available
    }
