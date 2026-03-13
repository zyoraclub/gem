#!/usr/bin/env python3
"""Test script to debug GEM scraper prices"""

import requests

# Test the GEM API directly
url = 'https://mkp.gem.gov.in/safety-shoes/search'
headers = {
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

try:
    response = requests.get(url, headers=headers, timeout=30)
    print(f'Status: {response.status_code}')
    print(f'Content-Type: {response.headers.get("Content-Type", "unknown")}')
    print(f'Length: {len(response.text)} chars')
    print()
    
    if response.status_code == 200:
        try:
            data = response.json()
            catalogs = data.get('catalogs', [])
            print(f'Found {len(catalogs)} catalogs')
            
            for i, c in enumerate(catalogs[:5]):
                print(f'\n--- Product {i+1} ---')
                print(f'ID: {c.get("id")}')
                print(f'Title: {c.get("title", "")[:50]}')
                print(f'list_price: {c.get("list_price")}')
                print(f'final_price: {c.get("final_price")}')
                print(f'discount_percent: {c.get("discount_percent")}')
        except Exception as e:
            print(f'JSON parse error: {e}')
            print(f'Response: {response.text[:500]}')
    else:
        print(f'Response: {response.text[:500]}')
except Exception as e:
    print(f'Error: {e}')
