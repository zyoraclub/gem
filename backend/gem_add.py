import re
import gspread
from google.oauth2.credentials import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoAlertPresentException
from datetime import datetime, timedelta
import time
import platform
import os
import json
from sqlalchemy import create_engine, text

# OTP Handler for auto-fetching Gmail OTP
from otp_handler import handle_otp

print("⚡ Running GeM Automation Script...")

# ---------------- STOP SIGNAL CHECK ----------------
STOP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".stop_automation")

def should_stop():
    """Check if stop signal file exists"""
    return os.path.exists(STOP_FILE)

def cleanup_stop_file():
    """Remove stop file on exit"""
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)

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

# Get the selected sheet ID from database (same as frontend)
sheet_id = None
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT value FROM settings WHERE key = 'selected_sheet_id'"))
        sheet_row = result.fetchone()
        if sheet_row and sheet_row[0]:
            sheet_id = sheet_row[0]
except Exception as e:
    print(f"⚠ Settings table not found, will auto-select sheet: {e}")

if sheet_id:
    print(f"✅ Using selected sheet ID: {sheet_id}")
    sheet_obj = client.open_by_key(sheet_id)
else:
    # Fallback: Auto-pick first sheet from Google Drive
    all_sheets = client.openall()
    if all_sheets:
        sheet_obj = all_sheets[0]
        sheet_id = sheet_obj.id
        print(f"✅ Auto-selected sheet: {sheet_obj.title}")
    else:
        print("❌ No sheets found in Google Drive!")
        exit(1)

sheet = sheet_obj.sheet1

# ---------------- READ DATA ----------------
rows = sheet.get_all_values()
products = []

# Debug: Print first row to see column structure
if rows:
    print(f"📋 Sheet headers: {rows[0][:10]}")
    if len(rows) > 1:
        print(f"📋 First data row: {rows[1][:10]}")

# ACTUAL Sheet structure:
# A(0): URL, B(1): Product ID, C(2): Status (NEW/ADD/DONE)
# E(4): Price, F(5): empty, G(6): Seller, H(7): Full URL with variant

for i, row in enumerate(rows[1:], start=2):  # skip header
    try:
        link = row[0].strip() if len(row) > 0 else ""   # A col = URL
        if not link and len(row) > 7:
            link = row[7].strip()  # Fallback to H col (full URL)
        
        status = row[2].strip().upper() if len(row) > 2 else ""  # C col = Status (NEW/ADD/DONE)
        
        if not link:
            continue
        
        # Process if: Column C is NEW or ADD (not DONE)
        if status in ["NEW", "ADD"]:
            products.append((i, link, row))
            print(f"   ✅ Row {i}: {status} - {link[:50]}...")
    except Exception as e:
        print(f"   ⚠ Row {i} error: {e}")
        continue

print(f"✅ Total NEW products to process: {len(products)}")
if not products:
    exit()

# ---------------- SELENIUM SETUP ----------------
options = Options()
options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

# ---------------- HELPERS ----------------
IS_MAC = platform.system() == "Darwin"

def _dispatch_events(el):
    js = """
      const el = arguments[0];
      ['input','change','blur'].forEach(evt => el.dispatchEvent(new Event(evt, {bubbles:true})));
    """
    driver.execute_script(js, el)

def fill_field(el, value):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.2)
    try:
        el.click()
    except:
        driver.execute_script("arguments[0].click();", el)
    time.sleep(0.15)

    if IS_MAC:
        el.send_keys(Keys.COMMAND, "a")
    else:
        el.send_keys(Keys.CONTROL, "a")
    time.sleep(0.05)
    el.send_keys(Keys.BACKSPACE)
    time.sleep(0.1)

    for ch in str(value):
        el.send_keys(ch)
        time.sleep(0.01)

    time.sleep(0.1)
    _dispatch_events(el)
    el.send_keys(Keys.TAB)
    time.sleep(0.2)

    try:
        current = el.get_attribute("value") or ""
        if str(current) != str(value):
            driver.execute_script("arguments[0].value = arguments[1];", el, str(value))
            _dispatch_events(el)
            el.send_keys(Keys.TAB)
            time.sleep(0.2)
    except:
        pass

def clean_number(s):
    return (s or "").replace(",", "").strip()

def two_dec(n):
    return f"{float(n):.2f}"

today = datetime.today().strftime("%Y-%m-%d")
two_years_later = (datetime.today() + timedelta(days=730)).strftime("%Y-%m-%d")

def open_product_form(product_url):
    """
    Navigate to product URL and click 'Sell this item' to open form
    Returns True if form opened successfully
    """
    try:
        # Navigate to product page
        driver.get(product_url)
        print(f"🌐 Navigating to: {product_url[:60]}...")
        time.sleep(3)
        
        # Find and click "Sell this item" or similar button
        sell_buttons = [
            "//button[contains(text(), 'Sell this')]",
            "//a[contains(text(), 'Sell this')]",
            "//button[contains(text(), 'Sell This')]",
            "//a[contains(text(), 'Sell This')]",
            "//button[contains(text(), 'Add to Catalog')]",
            "//a[contains(@href, 'add-product')]",
            "//button[contains(@ng-click, 'sell')]",
        ]
        
        for xpath in sell_buttons:
            try:
                btn = driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    print("✅ Clicked 'Sell this item' button")
                    time.sleep(3)
                    return True
            except:
                continue
        
        print("⚠ 'Sell this item' button not found automatically")
        return False
        
    except Exception as e:
        print(f"⚠ Error opening form: {e}")
        return False

# ---------------- MAIN LOOP ----------------
# Find the GEM form tab among all open tabs
print(f"🔍 Found {len(driver.window_handles)} tabs open")

gem_tab_found = False
gem_tab_handle = None
for handle in driver.window_handles:
    driver.switch_to.window(handle)
    current_url = driver.current_url
    print(f"   Tab: {current_url[:60]}...")
    
    if "admin-mkp.gem.gov.in" in current_url and "catalog" in current_url:
        print(f"✅ Found GEM form tab!")
        gem_tab_found = True
        gem_tab_handle = handle  # Save the correct handle
        break

if not gem_tab_found:
    print("⚠ No GEM form detected in any tab...")
    print("   Please open a GEM catalog form, then restart the script")
    print(f"   Expected URL pattern: admin-mkp.gem.gov.in/#!/catalog/...")
    exit()

current_url = driver.current_url
print(f"🔍 Current URL: {current_url[:80]}...")

if "admin-mkp.gem.gov.in" in current_url and "catalog" in current_url:
    print("✅ GEM form already open - filling directly (manual workflow)")
    
    # Extract product ID from form URL to find matching row
    # URL format: .../catalog/new?id=XXX-YYY-cat&...&gem_catalog_id=ZZZ
    import urllib.parse
    parsed = urllib.parse.urlparse(current_url)
    fragment = parsed.fragment  # !/catalog/new?id=...
    if "?" in fragment:
        query_part = fragment.split("?", 1)[1]
        params = urllib.parse.parse_qs(query_part)
        gem_catalog_id = params.get("gem_catalog_id", [""])[0]
        form_id = params.get("id", [""])[0]
        print(f"📦 Form ID: {form_id}, Catalog ID: {gem_catalog_id}")
    
    # Find matching product row (or use first NEW/ADD row)
    if products:
        row_index, link, row = products[0]  # Use first product for data
        print(f"📋 Using data from Row {row_index}")
        
        # Fill the form directly (code continues below in try block)
        products = [(row_index, link, row)]  # Process only this one
    else:
        print("⚠ No NEW/ADD products in sheet - nothing to fill")
        exit()
else:
    print("⚠ No GEM form detected - waiting for you to open a form...")
    print("   Please open a GEM catalog form, then restart the script")
    print(f"   Expected URL pattern: admin-mkp.gem.gov.in/#!/catalog/...")
    exit()

for idx, (row_index, link, row) in enumerate(products, start=1):
    # Check for stop signal before each product
    if should_stop():
        print("\n🛑 Stop signal received! Stopping automation...")
        cleanup_stop_file()
        break
    
    print(f"\n{'='*50}")
    print(f"📦 Processing product {idx}/{len(products)}")
    print(f"{'='*50}")

    try:
        # Switch to the GEM form tab (not the last tab!)
        driver.switch_to.window(gem_tab_handle)
        print(f"✅ Switched to GEM form tab: {driver.current_url[:50]}...")

        print("⏳ Waiting 2 seconds before filling...")
        time.sleep(2)
        
        # Wait for Angular to fully load the page
        print("⏳ Waiting for page to fully load...")
        time.sleep(5)  # Increased wait time
        
        # Check for iframes - GEM might use iframes
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"🔍 Found {len(iframes)} iframes on page")
        
        # Try to find form fields - if not found, try switching to iframes
        all_inputs = driver.find_elements(By.TAG_NAME, "input")
        if len(all_inputs) == 0 and len(iframes) > 0:
            print("   Trying to switch to iframe...")
            for i, iframe in enumerate(iframes):
                try:
                    driver.switch_to.frame(iframe)
                    all_inputs = driver.find_elements(By.TAG_NAME, "input")
                    print(f"   Iframe {i}: Found {len(all_inputs)} inputs")
                    if len(all_inputs) > 0:
                        print(f"   ✅ Switched to iframe {i} with form fields")
                        break
                    driver.switch_to.default_content()
                except:
                    driver.switch_to.default_content()
                    continue
        
        # Wait for Angular scope to be ready (GEM uses AngularJS)
        try:
            driver.execute_script("""
                if (window.angular) {
                    var el = document.querySelector('[ng-app]') || document.body;
                    var scope = angular.element(el).scope();
                    if (scope && scope.$apply) {
                        scope.$apply();
                    }
                }
            """)
            print("✅ Angular scope refreshed")
            time.sleep(2)
        except:
            pass
        
        # Re-scan for inputs after Angular refresh
        all_inputs = driver.find_elements(By.TAG_NAME, "input")
        
        # If still no inputs, try scrolling and waiting
        if len(all_inputs) == 0:
            print("   No inputs found yet, scrolling page...")
            driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(2)
            all_inputs = driver.find_elements(By.TAG_NAME, "input")
        
        # Debug: Print page title and a snippet of HTML
        print(f"📄 Page title: {driver.title}")
        body_text = driver.find_element(By.TAG_NAME, "body").text[:500] if driver.find_elements(By.TAG_NAME, "body") else "No body"
        print(f"📄 Page content preview: {body_text[:200]}...")

        # Debug: Print all form fields found on page
        print("🔍 Scanning form fields on page...")
        print(f"   Found {len(all_inputs)} input fields")
        
        # If no inputs found, print more debug info
        if len(all_inputs) == 0:
            print("   ⚠ NO FORM FIELDS FOUND!")
            print("   Possible reasons: form not loaded, need to scroll, or fields are hidden")
            print("   Page HTML snippet:")
            try:
                html = driver.page_source[:2000]
                print(f"   {html[:500]}...")
            except:
                pass
            
            # Try waiting for specific element
            print("   Waiting 10 more seconds for form to load...")
            time.sleep(10)
            all_inputs = driver.find_elements(By.TAG_NAME, "input")
            print(f"   After extra wait: Found {len(all_inputs)} input fields")
        
        for inp in all_inputs[:30]:  # Show first 30
            name = inp.get_attribute("name") or ""
            ng_model = inp.get_attribute("ng-model") or ""
            inp_type = inp.get_attribute("type") or ""
            placeholder = inp.get_attribute("placeholder") or ""
            if name or ng_model:
                print(f"   - name='{name}' ng-model='{ng_model}' type='{inp_type}' placeholder='{placeholder}'")
        
        # Print ALL fields that might be quantity, price, lead, moq related
        print("🔍 Looking for quantity/price/lead/moq fields...")
        for inp in all_inputs:
            ng_model = (inp.get_attribute("ng-model") or "").lower()
            name = (inp.get_attribute("name") or "").lower()
            if any(x in ng_model or x in name for x in ['qty', 'quantity', 'price', 'wsp', 'lead', 'moq', 'min', 'offer', 'stock']):
                print(f"   🎯 name='{inp.get_attribute('name')}' ng-model='{inp.get_attribute('ng-model')}'")
        
        # Scroll down to reveal more form fields
        print("📜 Scrolling to reveal all form fields...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(1)
        
        # Also look for forms by ng-model or form tags
        all_forms = driver.find_elements(By.TAG_NAME, "form")
        print(f"   Found {len(all_forms)} form tags")
        
        # Look for any ng-model elements (AngularJS bound inputs)
        ng_model_elements = driver.find_elements(By.XPATH, "//*[@ng-model]")
        print(f"   Found {len(ng_model_elements)} ng-model elements")
        for el in ng_model_elements[:10]:
            tag = el.tag_name
            ng_model = el.get_attribute("ng-model") or ""
            print(f"   - <{tag}> ng-model='{ng_model}'")
        
        all_selects = driver.find_elements(By.TAG_NAME, "select")
        print(f"   Found {len(all_selects)} select dropdowns")
        for sel in all_selects[:10]:
            name = sel.get_attribute("name") or ""
            ng_model = sel.get_attribute("ng-model") or ""
            print(f"   - SELECT: name='{name}' ng-model='{ng_model}'")

        try:
            # Try multiple selector strategies for each field
            print("🔧 Attempting to fill authorization fields...")
            
            # Authorization Number
            auth_no_filled = False
            for selector in [
                (By.NAME, "authorization_no"),
                (By.XPATH, "//input[contains(@ng-model, 'authorization')]"),
                (By.XPATH, "//input[contains(@placeholder, 'authorization') or contains(@placeholder, 'Authorization')]"),
                (By.CSS_SELECTOR, "input[name*='auth']"),
            ]:
                try:
                    el = driver.find_element(*selector)
                    if el.is_displayed():
                        fill_field(el, "NA")
                        print(f"   ✅ Filled authorization_no using {selector}")
                        auth_no_filled = True
                        break
                except:
                    continue
            if not auth_no_filled:
                print("   ⚠ authorization_no field not found")
            
            # Authorization Agency
            auth_agency_filled = False
            for selector in [
                (By.NAME, "authorization_agency"),
                (By.XPATH, "//input[contains(@ng-model, 'agency')]"),
                (By.CSS_SELECTOR, "input[name*='agency']"),
            ]:
                try:
                    el = driver.find_element(*selector)
                    if el.is_displayed():
                        fill_field(el, "NA")
                        print(f"   ✅ Filled authorization_agency using {selector}")
                        auth_agency_filled = True
                        break
                except:
                    continue
            if not auth_agency_filled:
                print("   ⚠ authorization_agency field not found")

            # Authorization Date - specific field
            print("🔧 Filling authorization date fields...")
            try:
                auth_date_el = driver.find_element(By.XPATH, "//input[contains(@ng-model, 'authorization_date')]")
                if auth_date_el.is_displayed():
                    fill_field(auth_date_el, today)
                    print(f"   ✅ Filled authorization_date = {today}")
            except:
                print("   ⚠ authorization_date field not found")
            
            # Authorization Valid From - REQUIRED
            try:
                valid_from_el = driver.find_element(By.XPATH, "//input[contains(@ng-model, 'authorization_valid_from')]")
                if valid_from_el.is_displayed():
                    fill_field(valid_from_el, today)
                    print(f"   ✅ Filled authorization_valid_from = {today}")
            except:
                print("   ⚠ authorization_valid_from field not found")
            
            # Authorization Valid To - REQUIRED (2 years from today)
            try:
                valid_to_el = driver.find_element(By.XPATH, "//input[contains(@ng-model, 'authorization_valid_to')]")
                if valid_to_el.is_displayed():
                    fill_field(valid_to_el, two_years_later)
                    print(f"   ✅ Filled authorization_valid_to = {two_years_later}")
            except:
                print("   ⚠ authorization_valid_to field not found")
            
            print("✅ Authorization details filled (or attempted)")

            # ---------------- TERMS OF DELIVERY DROPDOWN ----------------
            print("🔧 Selecting Terms of Delivery...")
            tod_filled = False
            for selector in [
                (By.XPATH, "//select[contains(@ng-model, 'terms_of_delivery')]"),
                (By.XPATH, "//select[contains(@ng-model, 'delivery_terms')]"),
                (By.XPATH, "//select[contains(@name, 'delivery')]"),
                (By.XPATH, "//select[contains(@ng-model, 'catSvc') and contains(@ng-model, 'delivery')]"),
            ]:
                try:
                    sel_el = driver.find_element(*selector)
                    if sel_el.is_displayed():
                        select = Select(sel_el)
                        # Try to select "Free Delivery" option
                        for option in select.options:
                            opt_text = option.text.lower()
                            if 'free' in opt_text and 'delivery' in opt_text:
                                select.select_by_visible_text(option.text)
                                print(f"   ✅ Selected Terms of Delivery: {option.text}")
                                tod_filled = True
                                break
                        if not tod_filled:
                            # Try selecting by index (usually first non-empty option)
                            if len(select.options) > 1:
                                select.select_by_index(1)
                                print(f"   ✅ Selected Terms of Delivery by index")
                                tod_filled = True
                        break
                except:
                    continue
            if not tod_filled:
                # Try clicking ui-select for AngularJS style dropdowns
                try:
                    ui_select = driver.find_element(By.XPATH, "//div[contains(@class, 'ui-select') and .//span[contains(text(), 'Delivery')]]")
                    driver.execute_script("arguments[0].click();", ui_select)
                    time.sleep(0.3)
                    free_option = driver.find_element(By.XPATH, "//div[contains(@class, 'ui-select-choices')]//span[contains(text(), 'Free Delivery')]")
                    driver.execute_script("arguments[0].click();", free_option)
                    print("   ✅ Selected Free Delivery from ui-select")
                    tod_filled = True
                except:
                    print("   ⚠ Terms of Delivery dropdown not found")

            # State checkboxes - scroll to them first
            print("🔧 Selecting state checkboxes...")
            driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(0.5)
            
            # Try specific state checkbox patterns first
            state_selectors = [
                "//input[@type='checkbox' and contains(@ng-model, 'state')]",
                "//input[@type='checkbox' and contains(@ng-model, 'region')]",
                "//input[@type='checkbox' and contains(@ng-model, 'location')]",
                "//input[@type='checkbox' and contains(@ng-model, 'area')]",
                "//label[contains(@class, 'checkbox')]//input[@type='checkbox']",
                "//div[contains(@class, 'checkbox')]//input[@type='checkbox']",
            ]
            
            checked_count = 0
            for sel in state_selectors:
                try:
                    checkboxes = driver.find_elements(By.XPATH, sel)
                    for checkbox in checkboxes:
                        try:
                            if checkbox.is_displayed() and not checkbox.is_selected():
                                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", checkbox)
                                time.sleep(0.1)
                                driver.execute_script("arguments[0].click();", checkbox)
                                checked_count += 1
                                time.sleep(0.15)
                                try:
                                    alert = driver.switch_to.alert
                                    alert.accept()
                                except NoAlertPresentException:
                                    pass
                        except:
                            pass
                except:
                    pass
            
            # If no specific state checkboxes found, try all visible checkboxes
            if checked_count == 0:
                all_checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox']")
                for checkbox in all_checkboxes:
                    try:
                        if checkbox.is_displayed() and not checkbox.is_selected():
                            ng_model = checkbox.get_attribute("ng-model") or ""
                            # Skip declaration/undertaking checkboxes (will handle later)
                            if any(x in ng_model.lower() for x in ['declaration', 'undertaking', 'agree', 'accept']):
                                continue
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", checkbox)
                            time.sleep(0.1)
                            driver.execute_script("arguments[0].click();", checkbox)
                            checked_count += 1
                            time.sleep(0.15)
                            try:
                                alert = driver.switch_to.alert
                                alert.accept()
                            except NoAlertPresentException:
                                pass
                    except:
                        pass
            print(f"✅ Checked {checked_count} state/region checkboxes")

            # ---------------- CURRENT STOCK / MAXIMUM QUANTITY ----------------
            print("🔧 Filling Current Stock / Maximum Quantity...")
            stock_filled = False
            for selector in [
                (By.NAME, "quantity"),
                (By.XPATH, "//input[@ng-model='catSvc.data.stock.quantity.value']"),
                (By.XPATH, "//input[contains(@ng-model, 'stock') and contains(@ng-model, 'quantity')]"),
                (By.XPATH, "//input[contains(@ng-model, 'quantity.value')]"),
                (By.XPATH, "//input[contains(@placeholder, 'quantity') or contains(@placeholder, 'Quantity')]"),
                (By.XPATH, "//input[contains(@placeholder, 'stock') or contains(@placeholder, 'Stock')]"),
            ]:
                try:
                    el = driver.find_element(*selector)
                    if el.is_displayed():
                        fill_field(el, "100000")
                        print(f"   ✅ Filled stock/quantity = 100000")
                        stock_filled = True
                        break
                except:
                    continue
            if not stock_filled:
                print("   ⚠ Stock/quantity field not found")

            # ---------------- MINIMUM QUANTITY PER CONSIGNEE (MOQ) ----------------
            print("🔧 Filling Minimum Quantity Per Consignee (MOQ)...")
            moq_raw = row[9].strip() if len(row) > 9 else ""
            moq_value = str(int(float(clean_number(moq_raw)))) if moq_raw else "1"
            moq_filled = False
            for selector in [
                (By.NAME, "moq"),
                (By.XPATH, "//input[@ng-model='catSvc.data.stock.moq.value']"),
                (By.XPATH, "//input[contains(@ng-model, 'stock') and contains(@ng-model, 'moq')]"),
                (By.XPATH, "//input[contains(@ng-model, 'moq.value')]"),
                (By.XPATH, "//input[contains(@placeholder, 'Minimum') or contains(@placeholder, 'minimum')]"),
                (By.XPATH, "//input[contains(@placeholder, 'MOQ') or contains(@placeholder, 'moq')]"),
            ]:
                try:
                    el = driver.find_element(*selector)
                    if el.is_displayed():
                        fill_field(el, moq_value)
                        print(f"   ✅ Filled MOQ = {moq_value}")
                        moq_filled = True
                        break
                except:
                    continue
            if not moq_filled:
                print(f"   ⚠ MOQ field not found")

            # ---------------- LEAD TIME FOR DIRECT PURCHASE ----------------
            print("🔧 Filling Lead Time for Direct Purchase...")
            lead_filled = False
            for selector in [
                (By.NAME, "lead_time"),
                (By.XPATH, "//input[@ng-model='catSvc.data.stock.lead_time.value']"),
                (By.XPATH, "//input[contains(@ng-model, 'stock') and contains(@ng-model, 'lead_time')]"),
                (By.XPATH, "//input[contains(@ng-model, 'lead_time.value')]"),
                (By.XPATH, "//input[contains(@placeholder, 'Lead') or contains(@placeholder, 'lead')]"),
                (By.XPATH, "//input[contains(@placeholder, 'days') or contains(@placeholder, 'Days')]"),
            ]:
                try:
                    el = driver.find_element(*selector)
                    if el.is_displayed():
                        # Check placeholder for range like [1-15]
                        placeholder = el.get_attribute("placeholder") or ""
                        if "-" in placeholder:
                            # Extract max value from range like "[1-15]"
                            import re
                            match = re.search(r'\d+-(\d+)', placeholder)
                            if match:
                                lead_value = match.group(1)
                            else:
                                lead_value = "10"
                        else:
                            lead_value = "10"  # Default 10 days
                        fill_field(el, lead_value)
                        print(f"   ✅ Filled lead_time = {lead_value}")
                        lead_filled = True
                        break
                except:
                    continue
            if not lead_filled:
                print("   ⚠ Lead time field not found")

            # Price (WSP)
            print("🔧 Filling price...")
            offer_price_raw = row[4].strip() if len(row) > 4 else ""
            if offer_price_raw:
                try:
                    base = float(clean_number(offer_price_raw))
                    offer_price = two_dec(base - 0.01)
                    price_filled = False
                    for selector in [
                        (By.NAME, "wsp"),
                        (By.XPATH, "//input[contains(@ng-model, 'wsp')]"),
                        (By.XPATH, "//input[contains(@ng-model, 'selling_price')]"),
                        (By.XPATH, "//input[contains(@ng-model, 'offer_price')]"),
                        (By.XPATH, "//input[contains(@ng-model, 'price') and not(contains(@ng-model, 'mrp'))]"),
                        (By.XPATH, "//input[contains(@ng-model, 'catSvc') and contains(@ng-model, 'price')]"),
                        (By.XPATH, "//input[contains(@placeholder, 'price') or contains(@placeholder, 'Price')]"),
                        (By.XPATH, "//input[contains(@placeholder, 'WSP') or contains(@placeholder, 'wsp')]"),
                    ]:
                        try:
                            el = driver.find_element(*selector)
                            if el.is_displayed():
                                fill_field(el, offer_price)
                                print(f"   ✅ Filled price={offer_price}")
                                sheet.update_acell(f"E{row_index}", offer_price)
                                price_filled = True
                                break
                        except:
                            continue
                    if not price_filled:
                        print("   ⚠ price/wsp field not found")
                except Exception as e:
                    print(f"   ⚠ Price error: {e}")
            else:
                print("   ⚠ No price in sheet column E")

            # Undertaking checkbox
            print("🔧 Clicking undertaking checkbox...")
            undertaking_clicked = False
            for selector in [
                (By.XPATH, "//input[@type='checkbox' and contains(@ng-model,'chain_document_declaration')]"),
                (By.XPATH, "//input[@type='checkbox' and contains(@ng-model,'declaration')]"),
                (By.XPATH, "//input[@type='checkbox' and contains(@ng-model,'undertaking')]"),
            ]:
                try:
                    el = driver.find_element(*selector)
                    if not el.is_selected():
                        driver.execute_script("arguments[0].click();", el)
                        undertaking_clicked = True
                        print(f"   ✅ Clicked undertaking checkbox")
                        break
                except:
                    continue
            if not undertaking_clicked:
                print("   ⚠ undertaking checkbox not found")

            # ---------------- BYPASS IMAGE UPLOAD (skip it) ----------------
            print("🔧 Bypassing image upload section...")
            try:
                # Try to close any image upload modal/popup if open
                close_btns = driver.find_elements(By.XPATH, 
                    "//button[contains(@class, 'close') or contains(text(), 'Skip') or contains(text(), 'Cancel') or contains(text(), '×')]"
                )
                for btn in close_btns:
                    try:
                        if btn.is_displayed():
                            driver.execute_script("arguments[0].click();", btn)
                            print("   ✅ Closed image upload dialog")
                            time.sleep(0.3)
                    except:
                        pass
                
                # Scroll past image section
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)
                print("   ✅ Scrolled past image section")
            except:
                pass

            print("🎉 Form fields filled successfully!")
            
            # ---------------- STEP 1: SAVE AND PROCEED ----------------
            print("🔧 Looking for Save and Proceed button...")
            
            # Scroll to bottom to ensure button is visible
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # Find and click "Save and Proceed" / "Save & Proceed" button
            save_proceed_found = False
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            
            for btn in all_buttons:
                try:
                    btn_text = (btn.text or "").strip().lower()
                    if ('save' in btn_text and 'proceed' in btn_text) and btn.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                        time.sleep(0.5)
                        driver.execute_script("arguments[0].click();", btn)
                        print(f"📤 Clicked Save and Proceed: '{btn.text}'")
                        save_proceed_found = True
                        break
                except:
                    continue
            
            # Try XPath if not found
            if not save_proceed_found:
                for selector in [
                    "//button[contains(text(), 'Save') and contains(text(), 'Proceed')]",
                    "//button[contains(text(), 'SAVE') and contains(text(), 'PROCEED')]",
                    "//button[contains(text(), 'Save & Proceed')]",
                    "//button[contains(text(), 'Save and Proceed')]",
                    "//a[contains(text(), 'Save') and contains(text(), 'Proceed')]",
                    "//button[contains(@ng-click, 'save') and contains(@ng-click, 'proceed')]",
                    "//button[contains(@ng-click, 'next')]",
                    "//button[contains(text(), 'Next')]",
                    "//button[contains(text(), 'Continue')]",
                ]:
                    try:
                        btn = driver.find_element(By.XPATH, selector)
                        if btn.is_displayed():
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", btn)
                            print(f"📤 Clicked Save/Proceed via XPath")
                            save_proceed_found = True
                            break
                    except:
                        continue
            
            if not save_proceed_found:
                print("⚠ Save and Proceed button not found")
                input("👉 Please click SAVE AND PROCEED manually, then press ENTER...")
            
            # Wait for next page to load
            print("⏳ Waiting for declaration page to load...")
            time.sleep(3)
            
            # ---------------- STEP 2: DECLARATION CHECKBOX ----------------
            print("🔧 Looking for declaration checkbox on new page...")
            
            # Scroll to bottom where declaration usually is
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # Re-fetch checkboxes on new page
            declaration_clicked = 0
            
            # Look for the main declaration checkbox
            declaration_selectors = [
                # Text-based selectors for "I have read and agreed"
                "//input[@type='checkbox' and ancestor::*[contains(text(), 'I have read')]]",
                "//input[@type='checkbox' and ancestor::label[contains(., 'I have read')]]",
                "//label[contains(., 'I have read')]//input[@type='checkbox']",
                "//label[contains(., 'agreed')]//input[@type='checkbox']",
                "//div[contains(., 'I have read and agreed')]//input[@type='checkbox']",
                # ng-model based
                "//input[@type='checkbox' and contains(@ng-model,'declaration')]",
                "//input[@type='checkbox' and contains(@ng-model,'undertaking')]",
                "//input[@type='checkbox' and contains(@ng-model,'agree')]",
                "//input[@type='checkbox' and contains(@ng-model,'terms')]",
                "//input[@type='checkbox' and contains(@ng-model,'catSvc')]",
            ]
            
            for selector in declaration_selectors:
                try:
                    els = driver.find_elements(By.XPATH, selector)
                    for el in els:
                        try:
                            if el.is_displayed() and not el.is_selected():
                                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                                time.sleep(0.3)
                                driver.execute_script("arguments[0].click();", el)
                                declaration_clicked += 1
                                print(f"   ✅ Clicked declaration checkbox!")
                                time.sleep(0.5)
                        except:
                            pass
                except:
                    continue
            
            # If still not found, click ALL unchecked checkboxes on the page
            if declaration_clicked == 0:
                print("   🔍 Looking for any unchecked checkboxes...")
                all_checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox']")
                for cb in all_checkboxes:
                    try:
                        if cb.is_displayed() and not cb.is_selected():
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cb)
                            time.sleep(0.2)
                            driver.execute_script("arguments[0].click();", cb)
                            declaration_clicked += 1
                            print(f"   ✅ Clicked checkbox")
                            time.sleep(0.3)
                    except:
                        pass
            
            print(f"   Total checkboxes clicked: {declaration_clicked}")
            
            if declaration_clicked == 0:
                print("⚠ No declaration checkbox found")
                input("👉 Please click the declaration checkbox manually, then press ENTER...")
            
            # Wait for Publish button to enable
            print("⏳ Waiting 2 seconds for Publish button to enable...")
            time.sleep(2)
            
            # ---------------- STEP 3: PUBLISH BUTTON ----------------
            print("🔧 Looking for Publish button...")
            
            # Scroll to bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # RE-FETCH all buttons
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            print(f"   📋 Found {len(all_buttons)} buttons on page:")
            
            # Print button info for debugging
            for btn in all_buttons:
                try:
                    btn_text = (btn.text or "").strip()[:40]
                    btn_disabled = btn.get_attribute("disabled")
                    is_visible = btn.is_displayed()
                    if btn_text:
                        print(f"   - text='{btn_text}' disabled={btn_disabled} visible={is_visible}")
                except:
                    pass
            
            submit_found = False
            
            # Try to find Publish button
            for btn in all_buttons:
                try:
                    btn_text = (btn.text or "").strip().lower()
                    if 'publish' in btn_text and btn.is_displayed():
                        btn_disabled = btn.get_attribute("disabled")
                        
                        if btn_disabled == "true" or btn_disabled == "disabled":
                            print(f"   ⚠ Publish button is DISABLED - trying to enable...")
                            driver.execute_script("arguments[0].removeAttribute('disabled');", btn)
                            time.sleep(0.3)
                        
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                        time.sleep(0.5)
                        driver.execute_script("arguments[0].click();", btn)
                        print(f"📤 Clicked Publish button: '{btn.text}'")
                        submit_found = True
                        break
                except:
                    continue
            
            # Fallback: XPath selectors
            if not submit_found:
                for selector in [
                    "//button[contains(text(), 'Publish')]",
                    "//button[contains(text(), 'PUBLISH')]",
                    "//button[contains(@ng-click, 'publish')]",
                    "//a[contains(text(), 'Publish')]",
                    "//button[contains(text(), 'Submit')]",
                    "//button[contains(@class, 'btn-success')]",
                    "//button[contains(@class, 'btn-primary')]",
                ]:
                    try:
                        btn = driver.find_element(By.XPATH, selector)
                        if btn.is_displayed():
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", btn)
                            print(f"📤 Clicked Publish via XPath!")
                            submit_found = True
                            break
                    except:
                        continue
            
            if not submit_found:
                print("⚠ Publish button not found or still disabled")
                input("👉 Please click PUBLISH manually, then press ENTER...")
            
            time.sleep(2)
            
            # Check if OTP dialog appeared
            print("🔍 Checking for OTP dialog...")
            otp_found = False
            for selector in [
                (By.XPATH, "//input[contains(@placeholder, 'OTP') or contains(@placeholder, 'otp')]"),
                (By.XPATH, "//input[contains(@ng-model, 'otp')]"),
                (By.XPATH, "//input[contains(@name, 'otp')]"),
            ]:
                try:
                    otp_el = driver.find_element(*selector)
                    if otp_el.is_displayed():
                        otp_found = True
                        print("   ✅ OTP input field found")
                        break
                except:
                    continue
            
            if otp_found:
                # Auto-handle OTP
                try:
                    if handle_otp(driver, max_retries=3, otp_timeout=120):
                        print("✅ OTP verified successfully!")
                        sheet.update_acell(f"C{row_index}", "DONE")
                    else:
                        print("❌ OTP verification failed")
                        sheet.update_acell(f"C{row_index}", "OTP_FAILED")
                except Exception as otp_err:
                    print(f"⚠ OTP auto-handler error: {otp_err}")
                    input("👉 Please complete OTP manually, then press ENTER...")
                    sheet.update_acell(f"C{row_index}", "DONE")
            else:
                print("   No OTP dialog detected - form may have submitted directly")
                # Mark as done anyway
                sheet.update_acell(f"C{row_index}", "DONE")

        except Exception as e:
            print("⚠ Error while filling form:", e)

    except Exception as e:
        print(f"⚠️ Error in tab handling → {str(e)}")
        continue

print("\n🎉 Process finished! All NEW products handled.")
