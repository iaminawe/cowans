#!/usr/bin/env python3
"""
Continue Shopify Product Sync from where it left off
This will resume syncing from batch 177 (products 17,700+)
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

# Global variable for graceful shutdown
running = True

def get_shopify_credentials():
    """Get Shopify API credentials from environment."""
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        raise ValueError("Shopify credentials not found in environment variables")
    
    return shop_url, access_token

def get_db_connection():
    """Get database connection with keepalive settings."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment variables")
    
    # Fix the URL format if needed
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    # Add keepalive parameters to prevent connection timeout
    conn = psycopg2.connect(
        db_url,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )
    return conn

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
            if (i + 1) % 25 == 0:
                print(f"  Progress: {i + 1}/{len(products)} products processed")
                
        except Exception as e:
            print(f"  ⚠️  Error processing product {product.get('id', 'unknown')}: {str(e)}")
            skipped_count += 1
    
    print(f"✅ Batch {batch_num} completed: {imported_count} imported, {updated_count} updated, {skipped_count} skipped")
    return imported_count, updated_count, skipped_count

def continue_sync():
    """Continue sync from where it left off."""
    print("🚀 CONTINUING SHOPIFY PRODUCT SYNC")
    print("=" * 50)
    print("📊 Previous progress: 17,700/24,535 (72.1%)")
    print("🎯 Resuming from batch 177...")
    
    start_time = time.time()
    
    # Get credentials
    shop_url, access_token = get_shopify_credentials()
    print(f"🔗 Connected to: {shop_url}")
    
    # Log file for progress
    log_file = "/tmp/shopify_sync_continue.log"
    
    def log_progress(message):
        """Log progress to both console and file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        
        with open(log_file, 'a') as f:
            f.write(log_line + "\n")
    
    # Clear log file
    with open(log_file, 'w') as f:
        f.write("")
    
    try:
        # Get database connection with keepalive
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Test connection
        cursor.execute("SELECT 1")
        log_progress("✅ Database connection established with keepalive settings")
        
        # Total products to sync (remaining)
        total_products = 24535
        already_synced = 17700
        remaining = total_products - already_synced
        
        log_progress(f"📊 Remaining products to sync: {remaining}")
        
        # Start from batch 177, but we need to skip 177 batches worth of products
        # That's 177 * 100 = 17700 products to skip
        products_to_skip = 17700
        products_per_page = 250
        pages_to_skip = products_to_skip // products_per_page  # 70 pages
        
        log_progress(f"⏭️  Skipping {pages_to_skip} pages to reach batch 177...")
        
        # Skip to the right page
        page_info = None
        current_page = 0
        
        while current_page < pages_to_skip:
            products, page_info = fetch_products_page(shop_url, access_token, page_info, products_per_page)
            current_page += 1
            if current_page % 10 == 0:
                log_progress(f"  Skipped {current_page}/{pages_to_skip} pages...")
            
            if not page_info:
                log_progress("⚠️  Reached end of products while skipping!")
                break
        
        log_progress(f"✅ Skipped to page {current_page}, ready to resume sync")
        
        # Now continue syncing from where we left off
        total_imported = 0
        total_updated = 0
        total_skipped = 0
        batch_num = 177
        
        # We'll process in smaller batches of 100 to match the original
        batch_size = 100
        current_batch_products = []
        
        while page_info and running:
            try:
                # Fetch next page (250 products)
                products, page_info = fetch_products_page(shop_url, access_token, page_info, products_per_page)
                
                if not products:
                    break
                
                # Add products to current batch
                current_batch_products.extend(products)
                
                # Process in batches of 100
                while len(current_batch_products) >= batch_size and running:
                    batch_products = current_batch_products[:batch_size]
                    current_batch_products = current_batch_products[batch_size:]
                    
                    # Sync batch
                    imported, updated, skipped = sync_products_batch(batch_products, cursor, batch_num)
                    
                    total_imported += imported
                    total_updated += updated
                    total_skipped += skipped
                    
                    # Commit batch
                    conn.commit()
                    
                    # Progress update
                    total_processed = already_synced + total_imported + total_updated + total_skipped
                    progress = (total_processed / total_products) * 100
                    elapsed = time.time() - start_time
                    rate = (total_imported + total_updated + total_skipped) / elapsed if elapsed > 0 else 0
                    
                    log_progress(f"📈 Progress: {total_processed:,}/{total_products:,} ({progress:.1f}%) | Rate: {rate:.1f} products/sec")
                    
                    batch_num += 1
                    
                    # Ping database to keep connection alive
                    if batch_num % 5 == 0:
                        cursor.execute("SELECT 1")
                        log_progress("  🔌 Database connection verified")
                
            except Exception as e:
                log_progress(f"❌ Error in batch {batch_num}: {str(e)}")
                # Try to reconnect
                try:
                    conn.rollback()
                    conn.close()
                    log_progress("🔄 Reconnecting to database...")
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    log_progress("✅ Reconnected successfully")
                except Exception as reconnect_error:
                    log_progress(f"❌ Failed to reconnect: {str(reconnect_error)}")
                    break
        
        # Process any remaining products
        if current_batch_products and running:
            imported, updated, skipped = sync_products_batch(current_batch_products, cursor, batch_num)
            total_imported += imported
            total_updated += updated
            total_skipped += skipped
            conn.commit()
        
        # Final results
        cursor.close()
        conn.close()
        
        elapsed = time.time() - start_time
        final_total = already_synced + total_imported + total_updated + total_skipped
        
        log_progress(f"\n🎉 SYNC CONTINUATION COMPLETED!")
        log_progress(f"📊 Final Results:")
        log_progress(f"   • Products imported: {total_imported:,}")
        log_progress(f"   • Products updated: {total_updated:,}")
        log_progress(f"   • Products skipped: {total_skipped:,}")
        log_progress(f"   • Total now synced: {final_total:,}/{total_products:,}")
        log_progress(f"   • Duration: {elapsed:.1f} seconds")
        log_progress(f"   • Rate: {(total_imported + total_updated + total_skipped) / elapsed:.1f} products/second")
        
        if final_total >= total_products:
            log_progress(f"\n✅ ALL PRODUCTS SYNCED SUCCESSFULLY!")
        else:
            log_progress(f"\n⚠️  Still {total_products - final_total} products remaining")
        
        return True
        
    except Exception as e:
        log_progress(f"❌ Sync failed: {str(e)}")
        return False

# Set up signal handlers
import signal
signal.signal(signal.SIGINT, lambda signum, frame: globals().update(running=False))
signal.signal(signal.SIGTERM, lambda signum, frame: globals().update(running=False))

if __name__ == "__main__":
    try:
        continue_sync()
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        sys.exit(1)