from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from typing import List, Dict, Optional
import time
import re


class GEMScraper:
    BASE_URL = "https://gem.gov.in"
    SEARCH_URL = "https://gem.gov.in/search"
    
    def __init__(self, headless: bool = True):
        self.options = Options()
        if headless:
            self.options.add_argument("--headless")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--window-size=1920,1080")
        self.options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.driver = webdriver.Chrome(options=self.options)
        self.wait = WebDriverWait(self.driver, 15)
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
    
    def get_categories(self) -> List[Dict]:
        """Scrape all product categories from GEM portal"""
        categories = []
        try:
            self.driver.get(self.BASE_URL)
            time.sleep(3)
            
            # Try to find category links - GEM portal structure may vary
            # Looking for main category sections
            category_elements = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "a[href*='category'], .category-item, .product-category"
            )
            
            for elem in category_elements:
                try:
                    name = elem.text.strip()
                    href = elem.get_attribute("href")
                    if name and href:
                        categories.append({
                            "name": name,
                            "url": href
                        })
                except:
                    continue
            
            # Alternative: Try finding from navigation menu
            if not categories:
                nav_items = self.driver.find_elements(By.CSS_SELECTOR, "nav a, .navbar a, .menu a")
                for item in nav_items:
                    try:
                        text = item.text.strip()
                        href = item.get_attribute("href")
                        if text and href and "product" in href.lower():
                            categories.append({"name": text, "url": href})
                    except:
                        continue
                        
        except Exception as e:
            print(f"Error getting categories: {e}")
        
        return categories
    
    def get_products_by_category(self, category: str, page: int = 1, limit: int = 20) -> List[Dict]:
        """Scrape products from a specific category"""
        products = []
        try:
            # If category is a URL, use it directly; otherwise search
            if category.startswith("http"):
                url = category
            else:
                url = f"{self.SEARCH_URL}?q={category}"
            
            self.driver.get(url)
            time.sleep(3)
            
            # Wait for product listings to load
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Find product cards - common patterns on e-commerce sites
            product_selectors = [
                ".product-card",
                ".product-item",
                ".product-listing",
                "[class*='product']",
                ".search-result-item",
                ".item-card"
            ]
            
            product_elements = []
            for selector in product_selectors:
                product_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if product_elements:
                    break
            
            for elem in product_elements[:limit]:
                product = self._extract_product_info(elem)
                if product:
                    products.append(product)
                    
        except Exception as e:
            print(f"Error getting products: {e}")
        
        return products
    
    def _extract_product_info(self, element) -> Optional[Dict]:
        """Extract product information from a product card element"""
        try:
            product = {}
            
            # Try to get product name
            name_selectors = ["h3", "h4", ".product-name", ".title", "a"]
            for selector in name_selectors:
                try:
                    name_elem = element.find_element(By.CSS_SELECTOR, selector)
                    if name_elem.text.strip():
                        product["name"] = name_elem.text.strip()
                        break
                except:
                    continue
            
            # Try to get price
            price_selectors = [".price", ".product-price", "[class*='price']", "span"]
            for selector in price_selectors:
                try:
                    price_elem = element.find_element(By.CSS_SELECTOR, selector)
                    price_text = price_elem.text.strip()
                    if "₹" in price_text or "Rs" in price_text or price_text.replace(",", "").replace(".", "").isdigit():
                        product["price"] = price_text
                        break
                except:
                    continue
            
            # Try to get product link
            try:
                link_elem = element.find_element(By.TAG_NAME, "a")
                product["url"] = link_elem.get_attribute("href")
                
                # Extract product ID from URL if possible
                if product.get("url"):
                    id_match = re.search(r'/product/(\d+)', product["url"])
                    if id_match:
                        product["id"] = id_match.group(1)
            except:
                pass
            
            # Try to get image
            try:
                img_elem = element.find_element(By.TAG_NAME, "img")
                product["image"] = img_elem.get_attribute("src")
            except:
                pass
            
            # Try to get seller/brand
            seller_selectors = [".seller", ".brand", ".vendor", "[class*='seller']"]
            for selector in seller_selectors:
                try:
                    seller_elem = element.find_element(By.CSS_SELECTOR, selector)
                    if seller_elem.text.strip():
                        product["seller"] = seller_elem.text.strip()
                        break
                except:
                    continue
            
            return product if product.get("name") else None
            
        except Exception as e:
            print(f"Error extracting product info: {e}")
            return None
    
    def get_product_details(self, product_id: str) -> Dict:
        """Get detailed information about a specific product"""
        details = {}
        try:
            url = f"{self.BASE_URL}/product/{product_id}"
            self.driver.get(url)
            time.sleep(3)
            
            # Product name
            try:
                name = self.driver.find_element(By.CSS_SELECTOR, "h1, .product-title, .product-name").text
                details["name"] = name.strip()
            except:
                pass
            
            # Price
            try:
                price = self.driver.find_element(By.CSS_SELECTOR, ".price, .product-price, [class*='price']").text
                details["price"] = price.strip()
            except:
                pass
            
            # Description
            try:
                desc = self.driver.find_element(By.CSS_SELECTOR, ".description, .product-description, [class*='description']").text
                details["description"] = desc.strip()
            except:
                pass
            
            # Specifications
            details["specifications"] = []
            try:
                spec_rows = self.driver.find_elements(By.CSS_SELECTOR, ".spec-row, .specification, tr")
                for row in spec_rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 2:
                            details["specifications"].append({
                                "key": cells[0].text.strip(),
                                "value": cells[1].text.strip()
                            })
                    except:
                        continue
            except:
                pass
            
            # Seller info
            try:
                seller = self.driver.find_element(By.CSS_SELECTOR, ".seller-info, .vendor-info, [class*='seller']").text
                details["seller"] = seller.strip()
            except:
                pass
            
            # Images
            details["images"] = []
            try:
                images = self.driver.find_elements(By.CSS_SELECTOR, ".product-image img, .gallery img")
                for img in images:
                    src = img.get_attribute("src")
                    if src:
                        details["images"].append(src)
            except:
                pass
            
            details["id"] = product_id
            details["url"] = url
            
        except Exception as e:
            print(f"Error getting product details: {e}")
        
        return details
    
    def search_products(self, query: str, page: int = 1) -> List[Dict]:
        """Search for products on GEM portal"""
        products = []
        try:
            search_url = f"{self.SEARCH_URL}?q={query}&page={page}"
            self.driver.get(search_url)
            time.sleep(3)
            
            # Use same extraction logic as category products
            products = self.get_products_by_category(search_url, page)
            
        except Exception as e:
            print(f"Error searching products: {e}")
        
        return products
