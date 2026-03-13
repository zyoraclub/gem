import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime
import json
from typing import Optional, Dict, List, Any
from sqlalchemy.orm import Session
from app.models import OAuthToken, ConnectedSheet

# Google Sheets scopes
SHEETS_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly',
]

CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS", "client_secrets.json")
REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/api/oauth/callback")

# Store the flow object to preserve code_verifier for PKCE
_oauth_flows = {}


class SheetsService:
    """Google Sheets OAuth and read/write service"""
    
    def __init__(self, db: Session, user_id: int = None):
        self.db = db
        self.user_id = user_id
    
    def get_auth_url(self) -> str:
        """Generate OAuth authorization URL"""
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SHEETS_SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        # Include user_id in state for callback
        custom_state = f"sheets_user_{self.user_id}"
        
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='false',
            prompt='consent',
            state=custom_state
        )
        
        # Store the flow object with user_id
        _oauth_flows[f'sheets_{self.user_id}'] = flow
        print(f"[Sheets] Auth URL generated for user {self.user_id}, state: {custom_state}")
        
        return auth_url
    
    def handle_callback(self, code: str) -> Dict:
        """Handle OAuth callback and store tokens"""
        # Try to get the stored flow (which has the code_verifier)
        flow = _oauth_flows.get(f'sheets_{self.user_id}')
        
        if flow:
            print(f"[Sheets] Using stored flow for user {self.user_id}")
        else:
            print("[Sheets] No stored flow, creating new one (may fail with PKCE)")
            flow = Flow.from_client_secrets_file(
                CLIENT_SECRETS_FILE,
                scopes=SHEETS_SCOPES,
                redirect_uri=REDIRECT_URI
            )
        
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Clear stored flow
        _oauth_flows.pop(f'sheets_{self.user_id}', None)
        
        # Store or update token for this user
        token = self.db.query(OAuthToken).filter(
            OAuthToken.service == 'sheets',
            OAuthToken.user_id == self.user_id
        ).first()
        if not token:
            token = OAuthToken(service='sheets', user_id=self.user_id)
            self.db.add(token)
        
        token.email = "Google Sheets Connected"
        token.access_token = credentials.token
        token.refresh_token = credentials.refresh_token
        token.token_expiry = credentials.expiry
        token.scopes = json.dumps(list(credentials.scopes))
        token.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        return {
            "email": "Google Sheets Connected",
            "connected": True
        }
    
    def get_credentials(self) -> Optional[Credentials]:
        """Get stored Sheets credentials for this user"""
        token = self.db.query(OAuthToken).filter(
            OAuthToken.service == 'sheets',
            OAuthToken.user_id == self.user_id
        ).first()
        if not token:
            return None
        
        with open(CLIENT_SECRETS_FILE) as f:
            client_config = json.load(f)
            client_info = client_config.get('web', client_config.get('installed', {}))
        
        credentials = Credentials(
            token=token.access_token,
            refresh_token=token.refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_info['client_id'],
            client_secret=client_info['client_secret'],
            scopes=json.loads(token.scopes) if token.scopes else SHEETS_SCOPES
        )
        
        return credentials
    
    def get_connection_status(self) -> Dict:
        """Check Sheets connection status for this user"""
        token = self.db.query(OAuthToken).filter(
            OAuthToken.service == 'sheets',
            OAuthToken.user_id == self.user_id
        ).first()
        if not token:
            return {"connected": False, "email": None}
        
        return {
            "connected": True,
            "email": token.email,
            "updated_at": token.updated_at.isoformat() if token.updated_at else None
        }
    
    def disconnect(self) -> bool:
        """Remove Sheets OAuth token for this user"""
        token = self.db.query(OAuthToken).filter(
            OAuthToken.service == 'sheets',
            OAuthToken.user_id == self.user_id
        ).first()
        if token:
            self.db.delete(token)
            self.db.commit()
            return True
        return False
    
    def list_spreadsheets(self, max_results: int = 20) -> List[Dict]:
        """List user's spreadsheets from Google Drive"""
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("Google Sheets not connected")
        
        drive_service = build('drive', 'v3', credentials=credentials)
        
        results = drive_service.files().list(
            q="mimeType='application/vnd.google-apps.spreadsheet'",
            pageSize=max_results,
            fields="files(id, name, webViewLink, modifiedTime)"
        ).execute()
        
        files = results.get('files', [])
        return [
            {
                "id": f['id'],
                "name": f['name'],
                "url": f.get('webViewLink'),
                "modified_at": f.get('modifiedTime')
            }
            for f in files
        ]
    
    def connect_sheet(self, sheet_id: str) -> Dict:
        """Add a sheet to connected sheets for this user"""
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("Google Sheets not connected")
        
        sheets_service = build('sheets', 'v4', credentials=credentials)
        
        # Get sheet metadata
        sheet = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        
        # Check if already connected for this user
        existing = self.db.query(ConnectedSheet).filter(
            ConnectedSheet.sheet_id == sheet_id,
            ConnectedSheet.user_id == self.user_id
        ).first()
        if not existing:
            existing = ConnectedSheet(sheet_id=sheet_id, user_id=self.user_id)
            self.db.add(existing)
        
        existing.sheet_name = sheet.get('properties', {}).get('title')
        existing.sheet_url = sheet.get('spreadsheetUrl')
        existing.is_active = True
        existing.last_synced_at = datetime.utcnow()
        
        self.db.commit()
        
        return {
            "id": existing.id,
            "sheet_id": existing.sheet_id,
            "name": existing.sheet_name,
            "url": existing.sheet_url
        }
    
    def get_connected_sheets(self) -> List[Dict]:
        """Get all connected sheets for this user"""
        sheets = self.db.query(ConnectedSheet).filter(
            ConnectedSheet.is_active == True,
            ConnectedSheet.user_id == self.user_id
        ).all()
        return [
            {
                "id": s.id,
                "sheet_id": s.sheet_id,
                "name": s.sheet_name,
                "url": s.sheet_url,
                "last_synced_at": s.last_synced_at.isoformat() if s.last_synced_at else None
            }
            for s in sheets
        ]
    
    def disconnect_sheet(self, sheet_id: str) -> bool:
        """Remove sheet from connected sheets for this user"""
        sheet = self.db.query(ConnectedSheet).filter(
            ConnectedSheet.sheet_id == sheet_id,
            ConnectedSheet.user_id == self.user_id
        ).first()
        if sheet:
            sheet.is_active = False
            self.db.commit()
            return True
        return False
    
    def get_sheet_tabs(self, sheet_id: str) -> List[Dict]:
        """Get all tabs/worksheets in a spreadsheet"""
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("Google Sheets not connected")
        
        sheets_service = build('sheets', 'v4', credentials=credentials)
        sheet = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        
        return [
            {
                "id": s['properties']['sheetId'],
                "title": s['properties']['title'],
                "index": s['properties']['index']
            }
            for s in sheet.get('sheets', [])
        ]
    
    def read_sheet(self, sheet_id: str, range_name: str) -> List[List[Any]]:
        """
        Read data from a sheet
        
        Args:
            sheet_id: Spreadsheet ID
            range_name: Range like 'Sheet1!A1:Z100' or just 'Sheet1'
        """
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("Google Sheets not connected")
        
        sheets_service = build('sheets', 'v4', credentials=credentials)
        
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        return result.get('values', [])
    
    def write_sheet(self, sheet_id: str, range_name: str, values: List[List[Any]]) -> Dict:
        """
        Write data to a sheet
        
        Args:
            sheet_id: Spreadsheet ID
            range_name: Range like 'Sheet1!A1'
            values: 2D array of values
        """
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("Google Sheets not connected")
        
        sheets_service = build('sheets', 'v4', credentials=credentials)
        
        body = {'values': values}
        
        result = sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        return {
            "updated_cells": result.get('updatedCells'),
            "updated_rows": result.get('updatedRows'),
            "updated_columns": result.get('updatedColumns')
        }
    
    def append_sheet(self, sheet_id: str, range_name: str, values: List[List[Any]]) -> Dict:
        """Append rows to a sheet"""
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("Google Sheets not connected")
        
        sheets_service = build('sheets', 'v4', credentials=credentials)
        
        body = {'values': values}
        
        result = sheets_service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        return {
            "updated_cells": result.get('updates', {}).get('updatedCells'),
            "updated_rows": result.get('updates', {}).get('updatedRows')
        }

    def update_cell(self, sheet_id: str, cell_ref: str, value: str) -> Dict:
        """
        Update a single cell value
        
        Args:
            sheet_id: Spreadsheet ID
            cell_ref: Cell reference like 'D5' or 'Sheet1!D5'
            value: Value to write
        """
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("Google Sheets not connected")
        
        sheets_service = build('sheets', 'v4', credentials=credentials)
        
        # Add Sheet1! prefix if not present
        if '!' not in cell_ref:
            cell_ref = f"Sheet1!{cell_ref}"
        
        body = {'values': [[value]]}
        
        result = sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=cell_ref,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        return {
            "updated_cells": result.get('updatedCells', 1),
            "cell": cell_ref,
            "value": value
        }

    def upsert_products(self, sheet_id: str, products: List[Dict], id_column: int = 1) -> Dict:
        """
        Update existing products or insert new ones. Track price changes.
        Matches existing sheet format: ID in column B, Price in column E.
        
        Existing format:
        - A: URL
        - B: Product ID (used for matching)
        - C: empty
        - D: empty  
        - E: Price (selling_price)
        - F: Status
        - G: Code
        - H: (reserved)
        - I: (reserved)
        - J: (reserved)
        - K: LAST_UPDATED
        - L: PREV_PRICE
        - M: PRICE_CHANGED
        
        Args:
            sheet_id: Spreadsheet ID
            products: List of product dicts with keys: id, title, brand, list_price, selling_price/final_price, url, seller
            id_column: Column index where product ID is stored (1 = column B)
        
        Returns:
            Stats about updates, inserts, and price changes
        """
        from datetime import datetime
        
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("Google Sheets not connected")
        
        sheets_service = build('sheets', 'v4', credentials=credentials)
        
        # Read existing data from the sheet (columns A through M)
        try:
            result = sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range="A:M"
            ).execute()
            existing_data = result.get('values', [])
        except:
            existing_data = []
        
        # Build index of existing product IDs -> row number (1-indexed for sheets)
        # Product ID is in column B (index 1)
        existing_ids = {}
        for row_idx, row in enumerate(existing_data):
            if row and len(row) > id_column:
                product_id = str(row[id_column]).strip()
                if product_id:
                    existing_ids[product_id] = row_idx + 1  # Sheet rows are 1-indexed
        
        # Prepare batch updates and new rows
        updates = []
        new_rows = []
        price_changes = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        for product in products:
            # Get product ID - handle both API formats
            product_id = str(product.get("id", "")).strip()
            if not product_id:
                continue
            
            # Get price - handle both "selling_price" and "final_price" keys
            new_price = product.get("selling_price") or product.get("final_price") or product.get("list_price") or ""
            new_price = str(new_price).strip() if new_price else ""
            
            # Debug: Log first 3 products' price data
            if len(updates) + len(new_rows) < 3:
                print(f"[DEBUG] Product {product_id}: selling_price={product.get('selling_price')}, final_price={product.get('final_price')}, list_price={product.get('list_price')} -> using: {new_price}")
            
            # Get URL
            product_url = product.get("url", "")
            
            if product_id in existing_ids:
                # Product exists - update price and tracking columns only
                row_num = existing_ids[product_id]
                existing_row = existing_data[row_num - 1] if row_num <= len(existing_data) else []
                
                # Price is in column E (index 4)
                old_price = str(existing_row[4]).strip() if len(existing_row) > 4 else ""
                
                # Check for price change
                price_changed = False
                prev_price = ""
                if old_price and new_price and old_price != new_price:
                    price_changed = True
                    prev_price = old_price
                    price_changes.append({
                        "id": product_id,
                        "old_price": old_price,
                        "new_price": new_price
                    })
                
                # Update only price (column E) and tracking columns (K, L, M)
                # First, update the price in column E
                updates.append({
                    "range": f"E{row_num}",
                    "values": [[new_price]]
                })
                
                # Update tracking columns K, L, M
                updates.append({
                    "range": f"K{row_num}:M{row_num}",
                    "values": [[now, prev_price if price_changed else "", "YES" if price_changed else ""]]
                })
            else:
                # New product - add in existing format
                # A: URL, B: ID, C: empty, D: empty, E: Price, F: empty, G: empty, H-J: empty, K: Updated, L: empty, M: empty
                new_row = [
                    product_url,      # A: URL
                    product_id,       # B: Product ID
                    "",               # C: empty
                    "",               # D: empty
                    new_price,        # E: Price
                    "",               # F: Status (blank - to be filled manually)
                    "",               # G: Code
                    "",               # H: reserved
                    "",               # I: reserved
                    "",               # J: reserved
                    now,              # K: LAST_UPDATED
                    "",               # L: PREV_PRICE
                    "NEW"             # M: Marker for new products
                ]
                new_rows.append(new_row)
        
        # Execute batch update for existing rows
        updated_count = 0
        if updates:
            batch_body = {
                "valueInputOption": "USER_ENTERED",
                "data": updates
            }
            sheets_service.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body=batch_body
            ).execute()
            updated_count = len([u for u in updates if u["range"].startswith("E")])  # Count price updates
        
        # Append new rows
        inserted_count = 0
        if new_rows:
            body = {'values': new_rows}
            sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range="A1",
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            inserted_count = len(new_rows)
        
        return {
            "updated": updated_count,
            "inserted": inserted_count,
            "price_changes": len(price_changes),
            "price_change_details": price_changes
        }
