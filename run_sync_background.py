#!/usr/bin/env python3
"""
Background Shopify Sync - Runs in background with progress logging
"""

import os
import sys
import time
import requests
import json
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
import threading
import signal

# Load environment variables
load_dotenv()

# Global variables for tracking
progress_file = "/tmp/shopify_sync_progress.log"
total_products = 0
total_processed = 0
start_time = None
running = True

def signal_handler(signum, frame):
    global running
    print(f"\n🛑 Received signal {signum}, stopping sync...")
    running = False

def log_progress(message):
    """Log progress to both console and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    
    with open(progress_file, 'a') as f:
        f.write(log_line + "\n")

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

def fetch_products_page(shop_url, access_token, page_info=None, limit=100):
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
    global total_processed
    
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    
    log_progress(f"🔄 Processing batch {batch_num} ({len(products)} products)...")
    
    for i, product in enumerate(products):
        if not running:
            break
            
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
                
        except Exception as e:
            log_progress(f"  ⚠️  Error processing product {product.get('id', 'unknown')}: {str(e)}")
            skipped_count += 1
    
    total_processed += imported_count + updated_count + skipped_count
    
    # Progress update
    if total_products > 0:
        progress = (total_processed / total_products) * 100
        elapsed = time.time() - start_time if start_time else 0
        rate = total_processed / elapsed if elapsed > 0 else 0
        
        log_progress(f"✅ Batch {batch_num} completed: {imported_count} imported, {updated_count} updated, {skipped_count} skipped")
        log_progress(f"📈 Progress: {total_processed:,}/{total_products:,} ({progress:.1f}%) | Rate: {rate:.1f} products/sec")
    
    return imported_count, updated_count, skipped_count

def main():
    """Main sync function."""
    global total_products, start_time, running
    
    # Clear progress file
    with open(progress_file, 'w') as f:
        f.write("")
    
    log_progress("🚀 BACKGROUND SHOPIFY PRODUCT SYNC STARTED")
    log_progress("=" * 50)
    
    start_time = time.time()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Get credentials
        shop_url, access_token = get_shopify_credentials()
        log_progress(f"🔗 Connected to: {shop_url}")
        
        # Get total product count
        log_progress("🔍 Fetching total product count...")
        total_products = get_product_count(shop_url, access_token)
        log_progress(f"📊 Total products in Shopify: {total_products:,}")
        
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Sync products in batches
        total_imported = 0
        total_updated = 0
        total_skipped = 0
        
        page_info = None
        batch_num = 1
        
        while running:
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
                
                batch_num += 1
                
                # Check if we're done
                if not page_info:
                    break
                    
                # Small delay to prevent overwhelming the API
                time.sleep(0.1)
                
            except Exception as e:
                log_progress(f"❌ Error in batch {batch_num}: {str(e)}")
                conn.rollback()
                break
        
        # Final results
        cursor.close()
        conn.close()
        
        elapsed = time.time() - start_time
        
        log_progress(f"\n🎉 SYNC COMPLETED!")
        log_progress(f"📊 Final Results:")
        log_progress(f"   • Products imported: {total_imported:,}")
        log_progress(f"   • Products updated: {total_updated:,}")
        log_progress(f"   • Products skipped: {total_skipped:,}")
        log_progress(f"   • Total processed: {total_imported + total_updated + total_skipped:,}")
        log_progress(f"   • Duration: {elapsed:.1f} seconds")
        log_progress(f"   • Rate: {(total_imported + total_updated + total_skipped) / elapsed:.1f} products/second")
        
        return True
    
    except Exception as e:
        log_progress(f"❌ Sync failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)