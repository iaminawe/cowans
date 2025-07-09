#!/usr/bin/env python3
"""
Optimized Full Shopify Product Sync - With better progress tracking
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

def get_product_count(shop_url, access_token):
    """Get total product count from Shopify."""
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }
    
    url = f"https://{shop_url}/admin/api/2023-10/products/count.json"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"Failed to get product count: {response.status_code}")
    
    return response.json().get('count', 0)

def fetch_products_page(shop_url, access_token, page_info=None, limit=250):
    """Fetch a single page of products."""
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }
    
    if page_info:
        url = f"https://{shop_url}/admin/api/2023-10/products.json?limit={limit}&page_info={page_info}"
    else:
        url = f"https://{shop_url}/admin/api/2023-10/products.json?limit={limit}"
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch products: {response.status_code}")
    
    # Extract page info for next page
    next_page_info = None
    if 'Link' in response.headers:
        links = response.headers['Link'].split(',')
        for link in links:
            if 'rel="next"' in link:
                next_page_info = link.split('page_info=')[1].split('>')[0]
                break
    
    products = response.json().get('products', [])
    return products, next_page_info

def sync_products_batch(products, cursor, batch_num):
    """Sync a batch of products to database."""
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    
    print(f"🔄 Processing batch {batch_num} ({len(products)} products)...")
    
    for i, product in enumerate(products):
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
                
            # Progress indicator
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i + 1}/{len(products)} products processed")
                
        except Exception as e:
            print(f"  ⚠️  Error processing product {product.get('id', 'unknown')}: {str(e)}")
            skipped_count += 1
    
    print(f"✅ Batch {batch_num} completed: {imported_count} imported, {updated_count} updated, {skipped_count} skipped")
    return imported_count, updated_count, skipped_count

def main():
    """Main sync function."""
    print("🚀 OPTIMIZED SHOPIFY PRODUCT SYNC")
    print("=" * 50)
    
    start_time = time.time()
    
    # Get credentials
    shop_url, access_token = get_shopify_credentials()
    print(f"🔗 Connected to: {shop_url}")
    
    # Get total product count
    print("🔍 Fetching total product count...")
    total_products = get_product_count(shop_url, access_token)
    print(f"📊 Total products in Shopify: {total_products:,}")
    
    # Get database connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Sync products in batches
    total_imported = 0
    total_updated = 0
    total_skipped = 0
    
    page_info = None
    batch_num = 1
    
    while True:
        try:
            # Fetch next batch
            products, page_info = fetch_products_page(shop_url, access_token, page_info)
            
            if not products:
                break
            
            # Sync batch
            imported, updated, skipped = sync_products_batch(products, cursor, batch_num)
            
            total_imported += imported
            total_updated += updated
            total_skipped += skipped
            
            # Commit batch
            conn.commit()
            
            # Progress update
            total_processed = total_imported + total_updated + total_skipped
            progress = (total_processed / total_products) * 100
            elapsed = time.time() - start_time
            rate = total_processed / elapsed if elapsed > 0 else 0
            
            print(f"📈 Progress: {total_processed:,}/{total_products:,} ({progress:.1f}%) | Rate: {rate:.1f} products/sec")
            
            batch_num += 1
            
            # Check if we're done
            if not page_info:
                break
                
        except Exception as e:
            print(f"❌ Error in batch {batch_num}: {str(e)}")
            conn.rollback()
            break
    
    # Final results
    cursor.close()
    conn.close()
    
    elapsed = time.time() - start_time
    
    print(f"\n🎉 SYNC COMPLETED!")
    print(f"📊 Final Results:")
    print(f"   • Products imported: {total_imported:,}")
    print(f"   • Products updated: {total_updated:,}")
    print(f"   • Products skipped: {total_skipped:,}")
    print(f"   • Total processed: {total_imported + total_updated + total_skipped:,}")
    print(f"   • Duration: {elapsed:.1f} seconds")
    print(f"   • Rate: {(total_imported + total_updated + total_skipped) / elapsed:.1f} products/second")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Sync failed: {str(e)}")
        sys.exit(1)