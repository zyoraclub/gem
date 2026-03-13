#!/usr/bin/env python3
"""Find a specific product and show its price details"""
import requests

API = "http://localhost:8000"
CATEGORY = "safety-shoes-leather-with-pvc-sole"
SEARCH_ID = "1998731755"

print(f"Searching for product containing: {SEARCH_ID}")
print(f"Category: {CATEGORY}\n")

for page in range(1, 10):
    try:
        resp = requests.get(f"{API}/api/products/{CATEGORY}?page={page}", timeout=30)
        data = resp.json()
        products = data.get("products", [])
        
        if not products:
            print(f"Page {page}: No more products")
            break
            
        for p in products:
            pid = str(p.get("id", ""))
            if SEARCH_ID in pid:
                print(f"FOUND on page {page}!")
                print(f"  ID: {p.get('id')}")
                print(f"  Title: {p.get('title')}")
                print(f"  Brand: {p.get('brand')}")
                print(f"  list_price: {p.get('list_price')}")
                print(f"  final_price: {p.get('final_price')}")
                print(f"  discount_percent: {p.get('discount_percent')}")
                print(f"  URL: {p.get('url')}")
                exit(0)
        
        print(f"Page {page}: {len(products)} products (not found)")
    except Exception as e:
        print(f"Page {page} error: {e}")

print("\nProduct not found in first 10 pages")
