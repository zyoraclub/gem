"""
GEM OTP Handler - Auto fetch from Gmail (IMAP), fill, and submit
Uses IMAP with App Password - no OAuth server needed

Setup:
1. Enable 2-Step Verification in Google Account
2. Create App Password: myaccount.google.com → Security → App passwords
3. Set GMAIL_EMAIL and GMAIL_APP_PASSWORD in .env file
"""

import imaplib
import email
from email.header import decode_header
import time
import re
import os
from typing import Optional
from datetime import datetime, timedelta

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use environment variables directly

# ============== CONFIGURATION ==============
# Set these values in .env file OR as environment variables
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")  # e.g., "user@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")  # 16-char app password

# GEM email patterns
GEM_SENDER_PATTERNS = ["noreply@gem.gov.in", "gem.gov.in"]

# OTP extraction patterns (ordered by specificity)
OTP_PATTERNS = [
    r'Your OTP for transaction on GEM is (\d{6})',  # Exact GEM format
    r'OTP for transaction.*?is (\d{6})',
    r'OTP[:\s]+(\d{6})',
    r'\b(\d{6})\b',  # Fallback: any 6-digit
]
# ===========================================


class GmailIMAPFetcher:
    """Fetch OTP from Gmail using IMAP"""
    
    def __init__(self, email_address: str = None, app_password: str = None):
        self.email = email_address or GMAIL_EMAIL
        self.password = app_password or GMAIL_APP_PASSWORD
        self.imap = None
    
    def connect(self) -> bool:
        """Connect to Gmail IMAP"""
        if not self.email or not self.password:
            print("❌ Gmail credentials not set!")
            print("   Set GMAIL_EMAIL and GMAIL_APP_PASSWORD")
            return False
        
        try:
            self.imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            self.imap.login(self.email, self.password)
            print(f"✅ Connected to Gmail: {self.email}")
            return True
        except imaplib.IMAP4.error as e:
            print(f"❌ IMAP Login failed: {e}")
            print("   Make sure you're using an App Password, not regular password")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def disconnect(self):
        """Close IMAP connection"""
        if self.imap:
            try:
                self.imap.logout()
            except:
                pass
            self.imap = None
    
    def _decode_subject(self, subject) -> str:
        """Decode email subject"""
        if not subject:
            return ""
        decoded = decode_header(subject)
        result = ""
        for part, enc in decoded:
            if isinstance(part, bytes):
                result += part.decode(enc or 'utf-8', errors='ignore')
            else:
                result += part
        return result
    
    def _get_body(self, msg) -> str:
        """Extract text from email"""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
                elif ctype == "text/html" and not body:
                    try:
                        html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        body = re.sub('<[^<]+?>', ' ', html)
                    except:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                pass
        return body
    
    def _extract_otp(self, text: str) -> Optional[str]:
        """Extract OTP from text"""
        for pattern in OTP_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _is_gem_email(self, sender: str) -> bool:
        """Check if from GEM"""
        sender_lower = sender.lower()
        return any(p in sender_lower for p in GEM_SENDER_PATTERNS)
    
    def fetch_latest_otp(self, max_age_minutes: int = 5, max_emails: int = 10) -> Optional[str]:
        """Fetch latest OTP from GEM emails"""
        if not self.imap:
            if not self.connect():
                return None
        
        try:
            self.imap.select("INBOX")
            
            # Search recent emails
            since_date = (datetime.now() - timedelta(minutes=max_age_minutes)).strftime("%d-%b-%Y")
            status, messages = self.imap.search(None, f'(SINCE "{since_date}")')
            
            if status != "OK":
                return None
            
            email_ids = messages[0].split()
            if not email_ids:
                return None
            
            # Check newest first
            email_ids = email_ids[-max_emails:][::-1]
            
            for email_id in email_ids:
                status, msg_data = self.imap.fetch(email_id, "(RFC822)")
                if status != "OK":
                    continue
                
                for response in msg_data:
                    if isinstance(response, tuple):
                        msg = email.message_from_bytes(response[1])
                        sender = msg.get("From", "")
                        
                        if not self._is_gem_email(sender):
                            continue
                        
                        subject = self._decode_subject(msg.get("Subject"))
                        body = self._get_body(msg)
                        
                        otp = self._extract_otp(subject) or self._extract_otp(body)
                        if otp:
                            print(f"✅ Found OTP: {otp} (from: {sender[:30]}...)")
                            return otp
            
            return None
            
        except Exception as e:
            print(f"❌ Error fetching: {e}")
            return None


class OTPHandler:
    """Handle OTP fetch, fill, and submit for GEM portal"""
    
    def __init__(self, driver, gmail_email: str = None, gmail_password: str = None):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)
        self.gmail = GmailIMAPFetcher(gmail_email, gmail_password)
        
        # GEM OTP field selectors
        self.otp_field_selectors = [
            "input[ng-model*='otp']",
            "input[name*='otp']",
            "input[id*='otp']",
            "input[placeholder*='OTP']",
            "input[placeholder*='otp']",
            "input[type='text'][maxlength='6']",
        ]
        
        # Submit button selectors  
        self.submit_selectors = [
            "button[ng-click*='verifyOtp']",
            "button[ng-click*='submitOtp']",
            "button[ng-click*='verify']",
        ]
        
        # Resend OTP selectors
        self.resend_selectors = [
            "a[ng-click*='resend']",
            "button[ng-click*='resend']",
        ]
    
    def close(self):
        """Cleanup"""
        self.gmail.disconnect()
    
    def wait_for_otp(self, timeout_seconds: int = 120, poll_interval: int = 5) -> Optional[str]:
        """Wait and poll for OTP"""
        print(f"⏳ Waiting for OTP email (timeout: {timeout_seconds}s)...")
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            otp = self.gmail.fetch_latest_otp(max_age_minutes=2)
            
            if otp:
                return otp
            
            elapsed = int(time.time() - start_time)
            print(f"   Polling... ({elapsed}s)")
            time.sleep(poll_interval)
        
        print("⏰ Timeout - no OTP received")
        return None
    
    def find_otp_field(self):
        """Find OTP input field"""
        for selector in self.otp_field_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        return el
            except:
                pass
        
        # XPath fallback
        xpaths = [
            "//input[contains(@placeholder, 'OTP')]",
            "//input[contains(@ng-model, 'otp')]",
            "//input[@maxlength='6']",
        ]
        for xpath in xpaths:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        return el
            except:
                pass
        
        return None
    
    def find_submit_button(self):
        """Find submit/verify button"""
        for selector in self.submit_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        return el
            except:
                pass
        
        # Text-based search
        for text in ['Verify', 'Submit', 'Confirm']:
            try:
                xpath = f"//button[contains(text(), '{text}')] | //input[@type='submit' and contains(@value, '{text}')]"
                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        return el
            except:
                pass
        
        return None
    
    def find_resend_button(self):
        """Find resend OTP button"""
        for selector in self.resend_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        return el
            except:
                pass
        
        # Text search
        try:
            xpath = "//*[contains(text(), 'Resend') or contains(text(), 'resend')]"
            elements = self.driver.find_elements(By.XPATH, xpath)
            for el in elements:
                if el.is_displayed():
                    return el
        except:
            pass
        
        return None
    
    def fill_otp(self, otp: str) -> bool:
        """Fill OTP field"""
        otp_field = self.find_otp_field()
        if not otp_field:
            print("❌ OTP field not found")
            return False
        
        try:
            otp_field.clear()
            time.sleep(0.1)
            for char in otp:
                otp_field.send_keys(char)
                time.sleep(0.05)
            print(f"✅ OTP filled: {otp}")
            return True
        except Exception as e:
            print(f"❌ Error filling OTP: {e}")
            return False
    
    def submit_otp(self) -> bool:
        """Submit OTP"""
        submit_btn = self.find_submit_button()
        
        if not submit_btn:
            print("⚠️ Submit button not found, trying Enter...")
            otp_field = self.find_otp_field()
            if otp_field:
                otp_field.send_keys(Keys.ENTER)
                return True
            return False
        
        try:
            self.driver.execute_script("arguments[0].click();", submit_btn)
            print("✅ OTP submitted")
            return True
        except Exception as e:
            print(f"❌ Submit error: {e}")
            return False
    
    def click_resend(self) -> bool:
        """Click resend button"""
        btn = self.find_resend_button()
        if not btn:
            print("❌ Resend button not found")
            return False
        
        try:
            self.driver.execute_script("arguments[0].click();", btn)
            print("✅ Resend clicked")
            return True
        except Exception as e:
            print(f"❌ Resend error: {e}")
            return False
    
    def check_otp_error(self) -> bool:
        """Check for OTP error message"""
        error_xpaths = [
            "//*[contains(text(), 'Invalid OTP')]",
            "//*[contains(text(), 'invalid')]",
            "//*[contains(text(), 'Wrong')]",
            "//*[contains(text(), 'expired')]",
        ]
        for xpath in error_xpaths:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    if el.is_displayed():
                        return True
            except:
                pass
        return False
    
    def handle_otp_flow(self, max_retries: int = 3, otp_timeout: int = 120) -> bool:
        """
        Complete OTP flow:
        1. Wait for OTP email
        2. Fill OTP
        3. Submit
        4. Retry if failed
        """
        # Check Gmail connection
        if not self.gmail.connect():
            print("❌ Cannot connect to Gmail")
            return False
        
        print("\n" + "=" * 50)
        print("🔐 Starting OTP Flow")
        print("=" * 50)
        
        for attempt in range(1, max_retries + 1):
            print(f"\n📍 Attempt {attempt}/{max_retries}")
            
            # Wait for OTP
            otp = self.wait_for_otp(timeout_seconds=otp_timeout)
            
            if not otp:
                if attempt < max_retries:
                    print("🔄 Clicking resend...")
                    self.click_resend()
                    time.sleep(3)
                continue
            
            # Fill OTP
            if not self.fill_otp(otp):
                continue
            
            time.sleep(0.5)
            
            # Submit
            if not self.submit_otp():
                continue
            
            time.sleep(2)
            
            # Check result
            if self.check_otp_error():
                print("❌ OTP invalid/expired")
                if attempt < max_retries:
                    print("🔄 Retrying...")
                    self.click_resend()
                    time.sleep(3)
                continue
            
            print("\n🎉 OTP Verified Successfully!")
            return True
        
        print("\n❌ OTP verification failed after all retries")
        return False


def handle_otp(driver, max_retries: int = 3, otp_timeout: int = 120, 
               gmail_email: str = None, gmail_password: str = None) -> bool:
    """
    Convenience function to handle OTP
    
    Args:
        driver: Selenium WebDriver
        max_retries: Max retry attempts
        otp_timeout: Seconds to wait for OTP
        gmail_email: Gmail address (or set GMAIL_EMAIL env var)
        gmail_password: App password (or set GMAIL_APP_PASSWORD env var)
    
    Returns:
        True if successful
    """
    handler = OTPHandler(driver, gmail_email, gmail_password)
    try:
        return handler.handle_otp_flow(max_retries, otp_timeout)
    finally:
        handler.close()


# ============== TEST ==============
if __name__ == "__main__":
    print("=" * 50)
    print("Gmail OTP Fetcher - Test")
    print("=" * 50)
    
    if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
        print("\n⚠️ Credentials not set!")
        print("\nOption 1 - Environment variables:")
        print("  export GMAIL_EMAIL='your-email@gmail.com'")
        print("  export GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx'")
        print("\nOption 2 - Edit this file and set GMAIL_EMAIL and GMAIL_APP_PASSWORD")
        
        # Interactive test
        email_input = input("\nEnter Gmail (or press Enter to skip): ").strip()
        if email_input:
            pwd_input = input("Enter App Password: ").strip()
            fetcher = GmailIMAPFetcher(email_input, pwd_input)
            if fetcher.connect():
                print("\n🔍 Checking for recent GEM OTP...")
                otp = fetcher.fetch_latest_otp(max_age_minutes=30)
                if otp:
                    print(f"\n🎉 Found OTP: {otp}")
                else:
                    print("\n📭 No GEM OTP found in last 30 minutes")
            fetcher.disconnect()
    else:
        fetcher = GmailIMAPFetcher()
        if fetcher.connect():
            print("\n🔍 Checking for recent OTP...")
            otp = fetcher.fetch_latest_otp()
            print(f"\nResult: {otp or 'No OTP found'}")
        fetcher.disconnect()
