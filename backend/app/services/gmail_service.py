import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime
import json
import base64
import re
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from app.models import OAuthToken

# Gmail scopes - read only for OTP fetching
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

# Path to OAuth client credentials (download from Google Cloud Console)
CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS", "client_secrets.json")
REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/api/oauth/callback")


class GmailService:
    """Gmail OAuth and OTP fetching service"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_auth_url(self) -> str:
        """Generate OAuth authorization URL"""
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=GMAIL_SCOPES,
            redirect_uri=REDIRECT_URI
        )
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state='gmail'
        )
        return auth_url
    
    def handle_callback(self, code: str) -> Dict:
        """Handle OAuth callback and store tokens"""
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=GMAIL_SCOPES,
            redirect_uri=REDIRECT_URI
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Get user email
        service = build('gmail', 'v1', credentials=credentials)
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress')
        
        # Store or update token
        token = self.db.query(OAuthToken).filter(OAuthToken.service == 'gmail').first()
        if not token:
            token = OAuthToken(service='gmail')
            self.db.add(token)
        
        token.email = email
        token.access_token = credentials.token
        token.refresh_token = credentials.refresh_token
        token.token_expiry = credentials.expiry
        token.scopes = json.dumps(list(credentials.scopes))
        token.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        return {
            "email": email,
            "connected": True
        }
    
    def get_credentials(self) -> Optional[Credentials]:
        """Get stored Gmail credentials"""
        token = self.db.query(OAuthToken).filter(OAuthToken.service == 'gmail').first()
        if not token:
            return None
        
        # Load client secrets for client_id and client_secret
        with open(CLIENT_SECRETS_FILE) as f:
            client_config = json.load(f)
            client_info = client_config.get('web', client_config.get('installed', {}))
        
        credentials = Credentials(
            token=token.access_token,
            refresh_token=token.refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_info['client_id'],
            client_secret=client_info['client_secret'],
            scopes=json.loads(token.scopes) if token.scopes else GMAIL_SCOPES
        )
        
        return credentials
    
    def get_connection_status(self) -> Dict:
        """Check Gmail connection status"""
        token = self.db.query(OAuthToken).filter(OAuthToken.service == 'gmail').first()
        if not token:
            return {"connected": False, "email": None}
        
        return {
            "connected": True,
            "email": token.email,
            "updated_at": token.updated_at.isoformat() if token.updated_at else None
        }
    
    def disconnect(self) -> bool:
        """Remove Gmail OAuth token"""
        token = self.db.query(OAuthToken).filter(OAuthToken.service == 'gmail').first()
        if token:
            self.db.delete(token)
            self.db.commit()
            return True
        return False
    
    def fetch_otp(self, sender_email: str = "noreply@gem.gov.in", max_results: int = 5, timeout_seconds: int = 120) -> Optional[str]:
        """
        Fetch OTP from Gmail inbox
        
        Args:
            sender_email: Email sender to filter (GEM portal)
            max_results: Number of recent emails to check
            timeout_seconds: Not used here, for polling use in caller
        
        Returns:
            OTP string if found, None otherwise
        """
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("Gmail not connected")
        
        service = build('gmail', 'v1', credentials=credentials)
        
        # Search for recent emails from GEM
        query = f"from:{sender_email} newer_than:5m"
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        
        for msg in messages:
            # Get full message
            message = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'
            ).execute()
            
            # Extract body
            body = self._get_email_body(message)
            
            # Find OTP pattern (usually 6 digits)
            otp_patterns = [
                r'\b(\d{6})\b',  # 6 digit OTP
                r'OTP[:\s]+(\d{4,6})',  # OTP: 123456
                r'verification code[:\s]+(\d{4,6})',
                r'one[- ]time[- ]password[:\s]+(\d{4,6})',
            ]
            
            for pattern in otp_patterns:
                match = re.search(pattern, body, re.IGNORECASE)
                if match:
                    return match.group(1)
        
        return None
    
    def _get_email_body(self, message: Dict) -> str:
        """Extract email body text"""
        payload = message.get('payload', {})
        
        # Try to get body from payload directly
        body_data = payload.get('body', {}).get('data')
        if body_data:
            return base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
        
        # Check parts
        parts = payload.get('parts', [])
        for part in parts:
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            elif part.get('mimeType') == 'text/html':
                data = part.get('body', {}).get('data')
                if data:
                    html = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    # Simple HTML to text
                    return re.sub('<[^<]+?>', '', html)
        
        return ""
