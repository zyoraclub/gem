from app.scraper.gem_api_scraper import GEMScraper
import json

scraper = GEMScraper()

print("Testing GEM API Scraper\n")
print("=" * 50)

# Test 1: Get products from safety shoes category
print("\n1. Getting products from 'safety-shoes-leather-with-pvc-sole'...\n")
result = scraper.get_products_by_category("safety-shoes-leather-with-pvc-sole", page=1)

print(f"Total products: {result['total_results']}")
print(f"Category: {result['category']}")
print(f"Products on page 1: {len(result['products'])}")

print("\nFirst 3 products:")
for i, product in enumerate(result['products'][:3], 1):
    print(f"\n{i}. {product['title']}")
    print(f"   Brand: {product['brand']}")
    print(f"   Price: ₹{product['final_price']} (was ₹{product['list_price']})")
    print(f"   Discount: {product['discount_percent']}%")
    print(f"   MOQ: {product['moq']}")
    print(f"   Seller: {product['seller']['name']} (Rating: {product['seller']['rating']})")

print("\n" + "=" * 50)
print("\n2. Searching for categories matching 'laptop'...\n")
categories = scraper.search_categories("laptop")
print(f"Found {len(categories)} categories:")
for cat in categories[:5]:
    print(f"  - {cat['name']} ({cat['slug']})")
