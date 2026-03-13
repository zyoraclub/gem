#!/usr/bin/env python3
"""Test script to debug GEM scraper prices using full scraper flow"""

from app.scraper.gem_api_scraper import GEMScraper

scraper = GEMScraper()

# First search for categories
print('Searching for safety shoes categories...')
cats = scraper.search_categories('safety shoes')
print(f'Found {len(cats)} categories:')
for c in cats[:5]:
    print(f'  - {c["slug"]}: {c["name"]} ({c["product_count"]} products)')

if cats:
    # Try to get products from first category with products
    for cat in cats[:5]:
        if cat["product_count"] > 0:
            slug = cat["slug"]
            print(f'\nFetching products from: {slug}')
            result = scraper.get_products_by_category(slug)
            print(f'Total results: {result["total_results"]}')
            print(f'Products on page 1: {len(result["products"])}')
            
            for p in result['products'][:5]:
                print(f'\n  Product ID: {p["id"]}')
                title = p.get("title", "N/A") or "N/A"
                print(f'  Title: {title[:60]}...' if len(title) > 60 else f'  Title: {title}')
                print(f'  list_price: {p["list_price"]}')
                print(f'  final_price: {p["final_price"]}')
            break
else:
    print('No categories found.')
