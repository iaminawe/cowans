#!/usr/bin/env python3
"""Test script to verify Shopify connection and environment variables."""

import os
import sys
from dotenv import load_dotenv
import requests

# Load environment variables from the correct path
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
print(f"Loading .env from: {env_path}")
load_dotenv(env_path)

# Check if environment variables are loaded
shop_url = os.getenv('SHOPIFY_SHOP_URL')
access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')

print(f"\nEnvironment Variables:")
print(f"SHOPIFY_SHOP_URL: {shop_url}")
print(f"SHOPIFY_ACCESS_TOKEN: {'*' * 10 if access_token else 'NOT SET'}")

if not shop_url or not access_token:
    print("\nERROR: Shopify credentials not found in environment variables!")
    print("Please ensure .env file contains SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN")
    sys.exit(1)

# Test the connection
print(f"\nTesting connection to Shopify...")

# Ensure shop URL format is correct
if not shop_url.startswith('https://'):
    shop_url = f"https://{shop_url}"

if '.myshopify.com' not in shop_url:
    shop_url += '.myshopify.com'

url = f"{shop_url}/admin/api/2024-10/shop.json"
print(f"API URL: {url}")

headers = {
    'X-Shopify-Access-Token': access_token,
    'Content-Type': 'application/json'
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"\nResponse Status: {response.status_code}")
    
    if response.status_code == 200:
        shop_data = response.json().get('shop', {})
        print("\n✅ Successfully connected to Shopify!")
        print(f"Shop Name: {shop_data.get('name')}")
        print(f"Shop Domain: {shop_data.get('domain')}")
        print(f"Shop Email: {shop_data.get('email')}")
        print(f"Currency: {shop_data.get('currency')}")
    else:
        print(f"\n❌ Failed to connect to Shopify")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"\n❌ Error connecting to Shopify: {e}")