from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

options = Options()
# Run with browser visible to debug
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

try:
    url = "https://mkp.gem.gov.in/safety-shoes-leather-with-pvc-sole/search#/?q=safety%20shoes"
    print(f"Loading: {url}")
    driver.get(url)
    
    print("Waiting for page to load...")
    time.sleep(10)
    
    print(f"\nPage title: {driver.title}")
    print(f"Current URL: {driver.current_url}")
    
    # Get body text
    body = driver.find_element(By.TAG_NAME, "body")
    body_text = body.text[:3000]
    print(f"\nBody text:\n{body_text}")
    
    # Look for product elements
    print("\n\nSearching for product elements...")
    selectors_to_try = [
        ".product", ".product-card", ".product-item",
        "[class*='product']", "[class*='card']",
        ".search-result", ".item", ".listing",
        "div[data-product]", "article"
    ]
    
    for selector in selectors_to_try:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            print(f"\n{selector}: Found {len(elements)} elements")
            for i, el in enumerate(elements[:3]):
                print(f"  {i+1}. Class: {el.get_attribute('class')}")
                print(f"     Text: {el.text[:100] if el.text else 'No text'}...")
    
    # Save HTML
    with open("page_source.html", "w") as f:
        f.write(driver.page_source)
    print("\n\nFull HTML saved to page_source.html")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    driver.quit()
