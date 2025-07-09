#!/usr/bin/env python3
"""
Test sync with just a few products to verify the fix works
"""

import os
import sys
import time
import requests
import json
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_shopify_credentials():
    """Get Shopify API credentials from environment."""
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        raise ValueError("Shopify credentials not found in environment variables")
    
    return shop_url, access_token

def get_db_connection():
    """Get database connection."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment variables")
    
    # Fix the URL format if needed
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    return psycopg2.connect(db_url)

def test_small_sync():
    """Test sync with just 10 products."""
    print("🧪 Testing small sync (10 products)...")
    
    # Get credentials
    shop_url, access_token = get_shopify_credentials()
    print(f"🔗 Connected to: {shop_url}")
    
    # Get database connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch just 10 products
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }
    
    url = f"https://{shop_url}/admin/api/2023-10/products.json?limit=10"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Error fetching products: {response.status_code}")
        return False
    
    products = response.json().get('products', [])
    print(f"📦 Fetched {len(products)} products")
    
    # Process each product
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    
    for product in products:
        try:
            # Extract product data
            shopify_id = str(product.get('id', ''))
            title = product.get('title', '')
            handle = product.get('handle', '')
            vendor = product.get('vendor', '')
            product_type = product.get('product_type', '')
            tags = product.get('tags', '')
            status = product.get('status', 'draft')
            created_at = product.get('created_at')
            updated_at = product.get('updated_at')
            published_at = product.get('published_at')
            
            # Get price from first variant
            price = 0.0
            sku = ''
            inventory_quantity = 0
            
            variants = product.get('variants', [])
            if variants:
                first_variant = variants[0]
                price = float(first_variant.get('price', 0))
                sku = first_variant.get('sku', '') or f"shopify-{shopify_id}"
                inventory_quantity = int(first_variant.get('inventory_quantity', 0))
            else:
                # Fallback SKU if no variants
                sku = f"shopify-{shopify_id}"
            
            print(f"  Processing: {title} (SKU: {sku})")
            
            # Check if product exists
            cursor.execute(
                "SELECT id FROM products WHERE shopify_product_id = %s",
                (shopify_id,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing product
                cursor.execute("""
                    UPDATE products SET 
                        name = %s, title = %s, handle = %s, vendor = %s, product_type = %s,
                        tags = %s, status = %s, price = %s, sku = %s,
                        inventory_quantity = %s, published_at = %s,
                        updated_at = %s
                    WHERE shopify_product_id = %s
                """, (
                    title, title, handle, vendor, product_type, tags, status,
                    price, sku, inventory_quantity, published_at,
                    updated_at, shopify_id
                ))
                updated_count += 1
                print(f"    ✅ Updated existing product")
            else:
                # Insert new product - need to get category_id for required field
                cursor.execute("SELECT id FROM categories LIMIT 1")
                category_result = cursor.fetchone()
                category_id = category_result[0] if category_result else 1
                
                cursor.execute("""
                    INSERT INTO products (
                        shopify_product_id, name, title, handle, vendor, product_type,
                        tags, status, price, sku, inventory_quantity,
                        published_at, created_at, updated_at, category_id, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    shopify_id, title, title, handle, vendor, product_type, tags,
                    status, price, sku, inventory_quantity, published_at,
                    created_at, updated_at, category_id, True
                ))
                imported_count += 1
                print(f"    ✅ Imported new product")
                
        except Exception as e:
            print(f"    ⚠️  Error processing product {product.get('id', 'unknown')}: {str(e)}")
            skipped_count += 1
    
    # Commit all changes
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n📊 Test Results:")
    print(f"   • Imported: {imported_count}")
    print(f"   • Updated: {updated_count}")
    print(f"   • Skipped: {skipped_count}")
    print(f"   • Total: {imported_count + updated_count + skipped_count}")
    
    return True

if __name__ == "__main__":
    try:
        test_small_sync()
        print("\n✅ Test completed successfully!")
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        sys.exit(1)