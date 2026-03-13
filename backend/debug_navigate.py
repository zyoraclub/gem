from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time

options = Options()
# options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
wait = WebDriverWait(driver, 15)

try:
    # Start from homepage
    print("Loading GEM homepage...")
    driver.get("https://gem.gov.in/")
    time.sleep(5)
    
    print(f"Title: {driver.title}")
    print(f"URL: {driver.current_url}")
    
    # Look for search box or categories link
    print("\nLooking for search box...")
    search_selectors = [
        "input[type='search']", "input[type='text']",
        "#search", ".search-input", "[placeholder*='search']",
        "[placeholder*='Search']", "input[name='q']"
    ]
    
    for selector in search_selectors:
        try:
            search_box = driver.find_element(By.CSS_SELECTOR, selector)
            print(f"Found search: {selector} -> {search_box.get_attribute('outerHTML')[:200]}")
        except:
            pass
    
    # Look for Categories link
    print("\nLooking for Products/Categories links...")
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        text = link.text.strip().lower()
        href = link.get_attribute("href") or ""
        if any(word in text for word in ["product", "categor", "shop", "browse"]) or "product" in href.lower():
            print(f"  '{link.text.strip()}' -> {href}")
    
    # Click on PRODUCTS menu if exists
    print("\nTrying to click PRODUCTS menu...")
    try:
        products_link = driver.find_element(By.XPATH, "//a[contains(text(),'PRODUCTS') or contains(text(),'Products')]")
        print(f"Found PRODUCTS link: {products_link.get_attribute('href')}")
        products_link.click()
        time.sleep(5)
        print(f"After click - URL: {driver.current_url}")
        print(f"Body text:\n{driver.find_element(By.TAG_NAME, 'body').text[:2000]}")
    except Exception as e:
        print(f"Could not click PRODUCTS: {e}")
    
    # Save HTML
    with open("gem_homepage.html", "w") as f:
        f.write(driver.page_source)
    print("\nSaved to gem_homepage.html")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    driver.quit()
