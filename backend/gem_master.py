import gspread
from google.oauth2.credentials import Credentials
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, re, os, json
from sqlalchemy import create_engine, text

# OTP Handler for auto-fetching Gmail OTP
from otp_handler import handle_otp

print("⚡ Running GeM Automation Script...")

# ---------------- GOOGLE SHEET SETUP (Use Web UI OAuth Token) ----------------
DATABASE_URL = "sqlite:///./gem_automation.db"
CLIENT_SECRETS = "client_secrets.json"

# Read token from database (same as web UI)
engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    result = conn.execute(text("SELECT access_token, refresh_token, scopes FROM oauth_tokens WHERE service = 'sheets'"))
    row = result.fetchone()

if not row:
    print("❌ Google Sheets not connected!")
    print("   Please connect Google Sheets via Web UI first (http://localhost:3000)")
    exit(1)

access_token, refresh_token, scopes = row

# Load client secrets for client_id/client_secret
with open(CLIENT_SECRETS) as f:
    client_config = json.load(f)
    client_info = client_config.get('web', client_config.get('installed', {}))

creds = Credentials(
    token=access_token,
    refresh_token=refresh_token,
    token_uri='https://oauth2.googleapis.com/token',
    client_id=client_info['client_id'],
    client_secret=client_info['client_secret'],
    scopes=json.loads(scopes) if scopes else ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
)

client = gspread.authorize(creds)
print("✅ Google Sheets connected (using Web UI token)")

# Auto-pick first sheet from Google Drive (same as frontend)
all_sheets = client.openall()
if all_sheets:
    sheet_obj = all_sheets[0]
    sheet_id = sheet_obj.id
    print(f"✅ Auto-selected sheet: {sheet_obj.title}")
else:
    print("❌ No sheets found in Google Drive!")
    exit(1)

sheet = sheet_obj.sheet1
all_data = sheet.get_all_values()

# headers + rows
headers = all_data[0]
rows = all_data[1:]

products = []
for i, row in enumerate(rows, start=2):   # start=2 bcz row 1 = header
    try:
        product_id = row[1].strip() if len(row) > 1 else ""    # B col
        status = row[2].strip().upper() if len(row) > 2 else ""  # C col
        rate = row[4].strip().replace(",", "") if len(row) > 4 else ""  # E col (Price)

        if status == "ACTIVE" and product_id and rate:
            try:
                price = float(rate) - 0.01
                price = f"{price:.2f}"
                products.append((i, product_id, price))   # save row index also
            except:
                continue
    except:
        continue

print(f"✅ Total ACTIVE products to update: {len(products)}")

# ---------------- SELENIUM SETUP ----------------
options = webdriver.ChromeOptions()
options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")  # attach to existing Chrome
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

input("👉 Chrome attach हो गया है!\n👉 अब Catalogue page खोलकर ENTER दबाएँ...")

# ---------------- MAIN LOOP ----------------
for idx, (row_index, pid, price) in enumerate(products, start=1):
    try:
        print(f"\n➡️ {idx}/{len(products)} Updating Product: {pid} | New Price: {price}")

        # Search box → type product id
        search_box = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[ng-model='search_term.value']")
        ))
        search_box.clear()
        search_box.send_keys(pid)

        # ✅ Search button click
        search_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button[ng-click='uisearch()']")
        ))
        driver.execute_script("arguments[0].click();", search_btn)

        # ✅ Wait until product ID appears in results
        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "table"), pid))

        # Click pencil (edit) button
        edit_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.fa.fa-pencil-square-o")))
        driver.execute_script("arguments[0].click();", edit_btn)
        time.sleep(2)

        # Offer price box (wsp input)
        price_box = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[ng-model='catSvc.data.stock.wsp.value']"))
        )
        price_box.clear()
        price_box.send_keys(price)

        # ---------------- AUTO SUBMIT & HANDLE OTP ----------------
        try:
            # Find and click Save/Submit button
            save_btn = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//button[contains(@ng-click, 'save') or contains(@ng-click, 'update') or contains(text(), 'Save') or contains(text(), 'Update')]"
            )))
            driver.execute_script("arguments[0].click();", save_btn)
            print("📤 Save clicked, handling OTP...")
            time.sleep(2)
            
            # Auto-handle OTP
            if handle_otp(driver, max_retries=3, otp_timeout=120):
                print("✅ OTP verified! Product updated.")
            else:
                print("❌ OTP verification failed")
                input("👉 Please complete manually, then press ENTER...")
        except Exception as otp_error:
            print(f"⚠ Auto-submit failed: {otp_error}")
            input("👉 अब captcha डालें और Save manually करें, फिर ENTER दबाएँ...")

        # ✅ Update back to sheet
        sheet.update_acell(f"C{row_index}", "DONE")  # Column C
        sheet.update_acell(f"E{row_index}", price)   # Column E

        print(f"✅ Updated Sheet Row {row_index} → DONE, Rate={price}")

    except Exception as e:
        print(f"⚠️ FAILED: {pid} | Error: {str(e)}")
        continue

print("\n🎉 All products processed!")
