from app.scraper.gem_scraper import GEMScraper

scraper = GEMScraper(headless=True)
try:
    print("Searching for 'safety shoes' on GEM portal...")
    products = scraper.search_products("safety shoes", page=1)
    print(f"\nFound {len(products)} products:\n")
    for i, product in enumerate(products, 1):
        print(f"{i}. {product}")
        print("-" * 50)
except Exception as e:
    print(f"Error: {e}")
finally:
    scraper.close()
