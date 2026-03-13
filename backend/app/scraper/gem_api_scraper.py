import requests
from typing import List, Dict, Optional
import re


class GEMScraper:
    """GEM Portal Scraper using direct API calls"""
    
    BASE_URL = "https://mkp.gem.gov.in"
    
    HEADERS = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    def search_categories(self, query: str) -> List[Dict]:
        """Search for categories matching query"""
        url = f"{self.BASE_URL}/search"
        params = {"q": query}
        
        # Use HTML headers for category search (not JSON)
        html_headers = {
            "Accept": "text/html",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        try:
            response = requests.get(url, params=params, headers=html_headers, timeout=30)
            html = response.text
            
            categories = []
            seen_slugs = set()
            
            # Pattern to match category links
            pattern = r'href="(/[^"]+)/search#/\?q=[^"]*"'
            matches = re.findall(pattern, html)
            
            for slug_path in matches:
                slug = slug_path.strip('/')
                if slug in seen_slugs or not slug:
                    continue
                seen_slugs.add(slug)
                
                # Get display name from slug
                name = slug.replace('-', ' ').title()
                if len(name) > 60:
                    name = name[:60] + "..."
                
                categories.append({
                    "name": name,
                    "slug": slug,
                    "product_count": 0  # Will be populated when fetching
                })
            
            # Get product counts for each category (first 5 only for speed)
            for cat in categories[:10]:
                try:
                    result = self.get_products_by_category(cat["slug"], page=1)
                    cat["product_count"] = result.get("total_results", 0)
                except:
                    pass
            
            return categories
        except Exception as e:
            print(f"Error searching categories: {e}")
            return []
    
    def get_products_by_category(
        self, 
        category_slug: str, 
        page: int = 1, 
        sort: str = "price_in_asc"
    ) -> Dict:
        """Get products from a category with pagination info"""
        url = f"{self.BASE_URL}/{category_slug}/search"
        params = {"page": page, "sort": sort}
        
        try:
            response = requests.get(url, params=params, headers=self.HEADERS, timeout=30)
            data = response.json()
            
            products = []
            for catalog in data.get("catalogs", []):
                product = {
                    "id": catalog.get("id"),
                    "title": catalog.get("title"),
                    "brand": catalog.get("brand"),
                    "image_url": catalog.get("img_url"),
                    "list_price": catalog.get("list_price", {}).get("value"),
                    "final_price": catalog.get("final_price", {}).get("value"),
                    "currency": catalog.get("final_price", {}).get("currency", "INR"),
                    "discount_percent": round(catalog.get("discount_percent", 0), 2),
                    "moq": catalog.get("moq"),
                    "is_buyable": catalog.get("is_buyable"),
                    "url": self._build_product_url(catalog.get("url", [])),
                    "seller": self._extract_seller_info(catalog.get("seller", {}))
                }
                products.append(product)
            
            total_results = data.get("number_of_results", 0)
            products_per_page = len(products)
            
            return {
                "products": products,
                "total_results": total_results,
                "current_page": data.get("curr_page", page),
                "products_per_page": products_per_page,
                "has_more": (page * products_per_page) < total_results if products_per_page > 0 else False,
                "category": data.get("browse_node", {}).get("title"),
                "sort": data.get("current_sort_option")
            }
            
        except Exception as e:
            print(f"Error fetching products: {e}")
            return {"products": [], "total_results": 0, "current_page": page, "has_more": False}
    
    def _build_product_url(self, url_parts: List[str]) -> str:
        if url_parts and len(url_parts) >= 3:
            return f"{self.BASE_URL}/{url_parts[0]}/{url_parts[1]}/{url_parts[2]}"
        return ""
    
    def _extract_seller_info(self, seller: Dict) -> Dict:
        return {
            "name": seller.get("name"),
            "rating": seller.get("rating"),
            "is_authorized": seller.get("is_authorized"),
            "is_reseller": seller.get("is_reseller"),
            "sold_as": seller.get("display_sold_as")
        }
    
    def get_all_products(self, category_slug: str, max_products: int = None, progress_callback=None) -> List[Dict]:
        """
        Get ALL products from a category with proper pagination.
        
        Args:
            category_slug: Category URL slug
            max_products: Optional limit (None = get all)
            progress_callback: Optional function(fetched, total) for progress updates
        """
        all_products = []
        page = 1
        total_results = 0
        retries = 0
        max_retries = 3
        
        while True:
            try:
                result = self.get_products_by_category(category_slug, page)
                products = result.get("products", [])
                total_results = result.get("total_results", 0)
                
                if not products:
                    # Retry empty response
                    retries += 1
                    if retries >= max_retries:
                        print(f"[Scraper] No more products after {page-1} pages, {len(all_products)} products")
                        break
                    import time
                    time.sleep(1)
                    continue
                
                retries = 0  # Reset retry counter on success
                all_products.extend(products)
                
                # Progress callback
                if progress_callback:
                    progress_callback(len(all_products), total_results)
                
                has_more = result.get("has_more", False)
                print(f"[Scraper] Page {page}: {len(products)} products, Total: {len(all_products)}/{total_results}, has_more={has_more}")
                
                # Check max limit
                if max_products and len(all_products) >= max_products:
                    all_products = all_products[:max_products]
                    print(f"[Scraper] Reached max_products limit: {max_products}")
                    break
                
                # Check if we got all products (use has_more flag or total count)
                if not has_more or len(all_products) >= total_results:
                    print(f"[Scraper] Got all {len(all_products)} products (total_results={total_results})")
                    break
                
                page += 1
                
                # Rate limiting - be nice to GEM servers
                import time
                time.sleep(0.5)
                
            except Exception as e:
                print(f"[Scraper] Error on page {page}: {e}")
                retries += 1
                if retries >= max_retries:
                    break
                import time
                time.sleep(2)
        
        return all_products
    
    def search_products(
        self, 
        query: str, 
        page: int = 1, 
        sort: str = "price_in_asc",
        category_index: int = 0
    ) -> Dict:
        """
        Search products by keyword - automatically finds category and fetches products
        
        Args:
            query: Search term like "laptop", "chair", "safety shoes"
            page: Page number
            sort: Sort option
            category_index: Which category to use if multiple found (0 = first/most relevant)
        """
        # First, find matching categories
        categories = self.search_categories(query)
        
        if not categories:
            return {
                "products": [],
                "total_results": 0,
                "query": query,
                "error": "No categories found for this search"
            }
        
        # Use specified category (default first/most relevant)
        if category_index >= len(categories):
            category_index = 0
        
        selected_category = categories[category_index]
        
        # Fetch products from that category
        result = self.get_products_by_category(selected_category["slug"], page, sort)
        
        # Add search metadata
        result["query"] = query
        result["selected_category"] = selected_category
        result["available_categories"] = categories
        
        return result
    
    def search_all_categories(
        self, 
        query: str, 
        max_products_per_category: int = 10
    ) -> Dict:
        """
        Search across ALL matching categories and combine results
        
        Args:
            query: Search term
            max_products_per_category: Limit products from each category
        """
        categories = self.search_categories(query)
        
        all_products = []
        category_results = []
        
        for cat in categories:
            result = self.get_products_by_category(cat["slug"], page=1)
            products = result.get("products", [])[:max_products_per_category]
            
            for p in products:
                p["category"] = cat["name"]
                p["category_slug"] = cat["slug"]
            
            all_products.extend(products)
            category_results.append({
                "name": cat["name"],
                "slug": cat["slug"],
                "total_in_category": result.get("total_results", 0),
                "fetched": len(products)
            })
        
        return {
            "query": query,
            "products": all_products,
            "total_fetched": len(all_products),
            "categories_searched": category_results
        }
    
    def get_realtime_price(self, product_url: str) -> Optional[float]:
        """
        Fetch real-time price from actual product page.
        The search API returns cached prices; this gets the live price.
        
        Args:
            product_url: Full URL or path like /category/brand/p-ID-cat.html
            
        Returns:
            Current price as float, or None if failed
        """
        try:
            if not product_url.startswith("http"):
                product_url = f"{self.BASE_URL}{product_url}"
            
            html_headers = {
                "Accept": "text/html",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(product_url, headers=html_headers, timeout=15)
            html = response.text
            
            # Method 1: Look for final_price in the product JSON data block
            # This is the most reliable - appears near base_price and discount
            match = re.search(r'"final_price"\s*:\s*([\d.]+)\s*,\s*"base_price"', html)
            if match:
                return float(match.group(1))
            
            # Method 2: Look for "Our Price" label pattern with price after it
            # Pattern: Our Price:</label><span> <span class='m-w'><span class='m-c c-inr'>₹</span>650.00
            match = re.search(r'Our Price.*?₹\s*</span>([\d,]+\.?\d*)', html, re.DOTALL)
            if match:
                price_str = match.group(1).replace(',', '')
                return float(price_str)
            
            # Method 3: Look for final-price div class
            # Pattern: class="final-price">...<span class='m-c c-inr'>₹</span>650.00
            match = re.search(r'final-price.*?₹\s*</span>([\d,]+\.?\d*)', html, re.DOTALL)
            if match:
                price_str = match.group(1).replace(',', '')
                return float(price_str)
            
            # Method 4: Generic final_price in JSON (less reliable - may catch wrong one)
            match = re.search(r'"final_price"\s*:\s*([\d.]+)', html)
            if match:
                return float(match.group(1))
            
            # Method 5: Fallback - first rupee price found
            match = re.search(r'₹\s*([\d,]+\.?\d*)', html)
            if match:
                price_str = match.group(1).replace(',', '')
                return float(price_str)
            
            return None
        except Exception as e:
            print(f"[GEM] Error fetching real-time price: {e}")
            return None
    
    def get_products_with_realtime_prices(
        self, 
        category_slug: str, 
        page: int = 1,
        sort: str = "price_in_asc"
    ) -> Dict:
        """
        Get products and fetch real-time prices from actual product pages.
        Slower but accurate - use for final price verification.
        
        Args:
            category_slug: Category to fetch from
            page: Page number
            sort: Sort option
            
        Returns:
            Same as get_products_by_category but with accurate realtime_price field
        """
        result = self.get_products_by_category(category_slug, page, sort)
        products = result.get("products", [])
        
        updated_count = 0
        for product in products:
            url = product.get("url")
            if url:
                realtime_price = self.get_realtime_price(url)
                if realtime_price is not None:
                    product["realtime_price"] = realtime_price
                    # Update final_price to use realtime value
                    product["cached_price"] = product.get("final_price")
                    product["final_price"] = realtime_price
                    updated_count += 1
        
        result["realtime_prices_fetched"] = updated_count
        return result
