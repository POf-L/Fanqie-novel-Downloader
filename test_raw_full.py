# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'D:\项目\Fanqie-novel-Downloader')

import requests
from config import CONFIG, get_headers

book_id = '7555508561518808088'
base_url = 'http://qkfqapi.vv9v.cn'

print("Testing different endpoints and parameters...")

# Test 1: raw_full with item_id
print("\n--- Test 1: /api/raw_full with item_id ---")
url = f'{base_url}/api/raw_full'
params = {'item_id': book_id}
try:
    resp = requests.get(url, params=params, headers=get_headers(), timeout=30)
    print(f'Status: {resp.status_code}')
    print(f'Response: {resp.text[:500]}')
except Exception as e:
    print(f'Error: {e}')

# Test 2: Check if there's a download endpoint
print("\n--- Test 2: /api/download ---")
url = f'{base_url}/api/download'
params = {'book_id': book_id}
try:
    resp = requests.get(url, params=params, headers=get_headers(), timeout=30)
    print(f'Status: {resp.status_code}')
    print(f'Response: {resp.text[:500]}')
except Exception as e:
    print(f'Error: {e}')

# Test 3: Get book chapters first to understand item_id
print("\n--- Test 3: /api/book to get chapters ---")
url = f'{base_url}/api/book'
params = {'book_id': book_id}
try:
    resp = requests.get(url, params=params, headers=get_headers(), timeout=30)
    print(f'Status: {resp.status_code}')
    data = resp.json()
    print(f'Code: {data.get("code")}')
    if data.get("data"):
        inner = data["data"]
        if isinstance(inner, dict):
            if "data" in inner:
                inner = inner["data"]
            if "allItemIds" in inner:
                print(f'First 3 item IDs: {inner["allItemIds"][:3]}')
            print(f'Keys: {list(inner.keys()) if isinstance(inner, dict) else "list"}')
except Exception as e:
    print(f'Error: {e}')

# Test 4: raw_full with first chapter item_id
print("\n--- Test 4: /api/raw_full with first chapter item_id ---")
url = f'{base_url}/api/book'
params = {'book_id': book_id}
try:
    resp = requests.get(url, params=params, headers=get_headers(), timeout=30)
    data = resp.json()
    inner = data.get("data", {})
    if isinstance(inner, dict) and "data" in inner:
        inner = inner["data"]
    item_ids = inner.get("allItemIds", [])
    if item_ids:
        first_item_id = item_ids[0]
        print(f'First item_id: {first_item_id}')
        
        url2 = f'{base_url}/api/raw_full'
        params2 = {'item_id': str(first_item_id)}
        resp2 = requests.get(url2, params=params2, headers=get_headers(), timeout=30)
        print(f'Status: {resp2.status_code}')
        print(f'Response: {resp2.text[:500]}')
except Exception as e:
    print(f'Error: {e}')
