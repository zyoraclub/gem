from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

driver = webdriver.Chrome(options=options)

try:
    # GEM marketplace search URL - correct format
    url = "https://mkp.gem.gov.in/safety-shoes-leather-with-pvc-sole/search#/?q=safety%20shoes"
    print(f"Loading: {url}")
    driver.get(url)
    time.sleep(8)  # More time for JS to load
    
    print(f"\nPage title: {driver.title}")
    print(f"Current URL: {driver.current_url}")
    
    # Get page source snippet
    body = driver.find_element(By.TAG_NAME, "body")
    print(f"\nBody text (first 2000 chars):\n{body.text[:2000]}")
    
    # Find all links
    links = driver.find_elements(By.TAG_NAME, "a")
    print(f"\n\nFound {len(links)} links. First 20:")
    for link in links[:20]:
        href = link.get_attribute("href")
        text = link.text.strip()[:50] if link.text else ""
        print(f"  {text} -> {href}")
    
    # Save full HTML for inspection
    with open("page_source.html", "w") as f:
        f.write(driver.page_source)
    print("\n\nFull HTML saved to page_source.html")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    driver.quit()
