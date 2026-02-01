#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

print("=== API Test ===")
print("Python version:", sys.version)

try:
    print("Importing config...")
    from config.config import CONFIG
    print("CONFIG loaded:", CONFIG is not None)
    
    print("Importing api_manager...")
    from core.api_manager import get_api_manager
    api = get_api_manager()
    print("API Base URL:", api.base_url)
    
    print("Testing get_book_detail...")
    detail = api.get_book_detail('7143408920434218505')
    print("Book detail result:", detail)
    
except Exception as e:
    import traceback
    print("ERROR:", e)
    traceback.print_exc()

print("=== Test Complete ===")
