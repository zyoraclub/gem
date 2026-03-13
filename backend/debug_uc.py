import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Use undetected chromedriver to bypass bot detection
options = uc.ChromeOptions()
options.add_argument("--window-size=1920,1080")
# options.add_argument("--headless")  # Try without headless first

driver = uc.Chrome(options=options)
wait = WebDriverWait(driver, 15)

try:
    # Load the search URL directly
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
        "div[data-product]", "article", ".variant-card"
    ]
    
    for selector in selectors_to_try:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            print(f"\n{selector}: Found {len(elements)} elements")
            for i, el in enumerate(elements[:3]):
                class_attr = el.get_attribute('class')
                print(f"  {i+1}. Class: {class_attr}")
                text = el.text[:150].replace('\n', ' ') if el.text else 'No text'
                print(f"     Text: {text}...")
    
    # Save HTML
    with open("page_source_uc.html", "w") as f:
        f.write(driver.page_source)
    print("\n\nFull HTML saved to page_source_uc.html")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    driver.quit()
