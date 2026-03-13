"""
Gmail OTP Fetcher for GEM Portal
Uses IMAP with App Password (no OAuth needed for demo)

Setup:
1. Enable IMAP in Gmail: Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP
2. Create App Password: myaccount.google.com → Security → 2-Step Verification → App passwords
3. Set environment variables or update credentials below
"""

import imaplib
import email
from email.header import decode_header
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple
import os

# Configuration - Update these or use environment variables
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")  # your-email@gmail.com
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")  # 16-char app password

# GEM Portal email patterns
GEM_SENDER_PATTERNS = [
    "noreply@gem.gov.in",
    "gem.gov.in",
    "support@gem.gov.in",
]

# OTP extraction patterns
OTP_PATTERNS = [
    r'\b(\d{6})\b',  # Generic 6-digit code
    r'OTP[:\s]+(\d{4,6})',
    r'verification code[:\s]*(\d{4,6})',
    r'one[- ]time[- ]password[:\s]*(\d{4,6})',
    r'code[:\s]+(\d{6})',
    r'<b>(\d{6})</b>',  # OTP in bold tags
    r'<strong>(\d{6})</strong>',
]


class GmailOTPFetcher:
    """Fetch OTP from Gmail using IMAP"""
    
    def __init__(self, email_address: str = None, app_password: str = None):
        self.email = email_address or GMAIL_EMAIL
        self.password = app_password or GMAIL_APP_PASSWORD
        self.imap = None
        
    def connect(self) -> bool:
        """Connect to Gmail IMAP server"""
        try:
            self.imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            self.imap.login(self.email, self.password)
            print(f"✅ Connected to Gmail: {self.email}")
            return True
        except imaplib.IMAP4.error as e:
            print(f"❌ IMAP Login failed: {e}")
            print("📝 Make sure you're using an App Password, not your regular password")
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
    
    def _decode_email_subject(self, subject) -> str:
        """Decode email subject"""
        if subject is None:
            return ""
        decoded_parts = decode_header(subject)
        result = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                result += part
        return result
    
    def _get_email_body(self, msg) -> str:
        """Extract text body from email message"""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
                elif content_type == "text/html" and not body:
                    try:
                        html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        # Simple HTML to text
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
        """Extract OTP from text using patterns"""
        for pattern in OTP_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _is_gem_email(self, sender: str) -> bool:
        """Check if email is from GEM portal"""
        sender_lower = sender.lower()
        return any(pattern in sender_lower for pattern in GEM_SENDER_PATTERNS)
    
    def fetch_latest_otp(self, max_age_minutes: int = 5, max_emails: int = 10) -> Optional[Tuple[str, str]]:
        """
        Fetch the latest OTP from GEM emails
        
        Args:
            max_age_minutes: Only check emails from last N minutes
            max_emails: Maximum number of recent emails to check
            
        Returns:
            Tuple of (otp, subject) if found, None otherwise
        """
        if not self.imap:
            if not self.connect():
                return None
        
        try:
            # Select inbox
            self.imap.select("INBOX")
            
            # Search for recent emails
            # Calculate date for search (IMAP date format)
            since_date = (datetime.now() - timedelta(minutes=max_age_minutes)).strftime("%d-%b-%Y")
            
            # Search for emails since date
            status, messages = self.imap.search(None, f'(SINCE "{since_date}")')
            
            if status != "OK":
                print("❌ Failed to search emails")
                return None
            
            email_ids = messages[0].split()
            
            if not email_ids:
                print(f"📭 No emails in last {max_age_minutes} minutes")
                return None
            
            # Check most recent emails first
            email_ids = email_ids[-max_emails:][::-1]  # Reverse to get newest first
            
            for email_id in email_ids:
                status, msg_data = self.imap.fetch(email_id, "(RFC822)")
                
                if status != "OK":
                    continue
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # Get sender
                        sender = msg.get("From", "")
                        
                        # Check if from GEM
                        if not self._is_gem_email(sender):
                            continue
                        
                        subject = self._decode_email_subject(msg.get("Subject"))
                        body = self._get_email_body(msg)
                        
                        # Try to extract OTP from subject first, then body
                        otp = self._extract_otp(subject) or self._extract_otp(body)
                        
                        if otp:
                            print(f"✅ Found OTP: {otp}")
                            print(f"   From: {sender}")
                            print(f"   Subject: {subject[:50]}...")
                            return (otp, subject)
            
            print("📭 No OTP found in recent GEM emails")
            return None
            
        except Exception as e:
            print(f"❌ Error fetching emails: {e}")
            return None
    
    def wait_for_otp(self, timeout_seconds: int = 120, poll_interval: int = 5) -> Optional[str]:
        """
        Wait and poll for OTP arrival
        
        Args:
            timeout_seconds: Maximum time to wait
            poll_interval: Seconds between checks
            
        Returns:
            OTP string if found, None if timeout
        """
        print(f"⏳ Waiting for OTP (timeout: {timeout_seconds}s)...")
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            result = self.fetch_latest_otp(max_age_minutes=2)
            
            if result:
                otp, _ = result
                return otp
            
            elapsed = int(time.time() - start_time)
            print(f"   Checking... ({elapsed}s elapsed)")
            time.sleep(poll_interval)
        
        print("⏰ Timeout waiting for OTP")
        return None


def fetch_gem_otp(
    email_address: str = None,
    app_password: str = None,
    wait: bool = True,
    timeout: int = 120
) -> Optional[str]:
    """
    Convenience function to fetch GEM OTP
    
    Args:
        email_address: Gmail address (or set GMAIL_EMAIL env var)
        app_password: Gmail app password (or set GMAIL_APP_PASSWORD env var)
        wait: If True, poll until OTP arrives or timeout
        timeout: Seconds to wait if wait=True
        
    Returns:
        OTP string if found, None otherwise
    """
    fetcher = GmailOTPFetcher(email_address, app_password)
    
    try:
        if wait:
            return fetcher.wait_for_otp(timeout_seconds=timeout)
        else:
            result = fetcher.fetch_latest_otp()
            return result[0] if result else None
    finally:
        fetcher.disconnect()


# Demo / Test
if __name__ == "__main__":
    print("=" * 50)
    print("Gmail OTP Fetcher - Demo")
    print("=" * 50)
    
    # Check credentials
    if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
        print("\n⚠️  Credentials not set!")
        print("Set these environment variables:")
        print("  export GMAIL_EMAIL='your-email@gmail.com'")
        print("  export GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx'")
        print("\nOr update the variables in this file.")
        
        # Interactive mode for demo
        email_input = input("\nEnter Gmail address (or press Enter to skip): ").strip()
        if email_input:
            password_input = input("Enter App Password: ").strip()
            
            fetcher = GmailOTPFetcher(email_input, password_input)
            if fetcher.connect():
                print("\n🔍 Checking for recent GEM OTP emails...")
                result = fetcher.fetch_latest_otp(max_age_minutes=30)
                if result:
                    otp, subject = result
                    print(f"\n🎉 OTP Found: {otp}")
                else:
                    print("\n📭 No GEM OTP emails found in last 30 minutes")
            fetcher.disconnect()
    else:
        # Auto mode with env vars
        fetcher = GmailOTPFetcher()
        if fetcher.connect():
            result = fetcher.fetch_latest_otp()
            if result:
                print(f"\n🎉 Latest OTP: {result[0]}")
            else:
                print("\n📭 No recent OTP found")
        fetcher.disconnect()
