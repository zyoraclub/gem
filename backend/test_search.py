from app.scraper.gem_api_scraper import GEMScraper
scraper = GEMScraper()

# Test simple keyword search
print('=== Search: "laptop" ===')
result = scraper.search_products('laptop')
print(f'Category: {result.get("selected_category", {}).get("name")}')
print(f'Total: {result["total_results"]} products')
print(f'Available categories: {len(result.get("available_categories", []))}')
if result['products']:
    p = result['products'][0]
    print(f'First: {p["title"]} - Rs.{p["final_price"]}')

print()
print('=== Search: "chair" ===')
result = scraper.search_products('chair')
print(f'Category: {result.get("selected_category", {}).get("name")}')
print(f'Total: {result["total_results"]} products')

print()
print('=== Search ALL categories: "safety" ===')
result = scraper.search_all_categories('safety', max_products_per_category=3)
print(f'Total fetched: {result["total_fetched"]}')
print(f'Categories searched: {len(result["categories_searched"])}')
for cat in result['categories_searched'][:3]:
    print(f'  - {cat["name"]}: {cat["total_in_category"]} products')
