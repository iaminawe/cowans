#!/usr/bin/env python3
"""
Complete Shopify Product Sync - Pull ALL products from Shopify
This will sync all 24,535+ products from Shopify to the local database
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

def fetch_all_shopify_products(shop_url, access_token):
    """Fetch ALL products from Shopify using pagination."""
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }
    
    print("🔍 Fetching total product count from Shopify...")
    
    # Get total count first
    count_response = requests.get(f"https://{shop_url}/admin/api/2023-10/products/count.json", headers=headers)
    if count_response.status_code != 200:
        raise Exception(f"Failed to get product count: {count_response.status_code}")
    
    total_count = count_response.json()['count']
    print(f"📊 Total products in Shopify: {total_count:,}")
    
    # Fetch all products using pagination
    all_products = []
    limit = 250  # Maximum allowed by Shopify
    page_info = None
    page_num = 1
    
    print("📥 Starting to fetch all products...")
    
    while True:
        print(f"📄 Fetching page {page_num} (up to {limit} products per page)...")
        
        # Build URL with pagination
        url = f"https://{shop_url}/admin/api/2023-10/products.json?limit={limit}"
        if page_info:
            url += f"&page_info={page_info}"
        
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Error fetching page {page_num}: {response.status_code}")
            print(f"Response: {response.text}")
            break
        
        data = response.json()
        products = data.get('products', [])
        
        if not products:
            print("✅ No more products to fetch")
            break
        
        all_products.extend(products)
        print(f"📦 Fetched {len(products)} products (total so far: {len(all_products):,})")
        
        # Check for next page
        link_header = response.headers.get('Link', '')
        if 'rel="next"' in link_header:
            # Parse the page_info from the Link header
            next_link = [link.strip() for link in link_header.split(',') if 'rel="next"' in link][0]
            page_info = next_link.split('page_info=')[1].split('&')[0].replace('>', '')
            page_num += 1
            
            # Rate limiting - Shopify allows 2 calls per second
            time.sleep(0.5)
        else:
            print("✅ Reached the last page")
            break
        
        # Safety check to avoid infinite loops
        if len(all_products) >= total_count:
            print("✅ Fetched all available products")
            break
    
    print(f"🎉 Successfully fetched {len(all_products):,} products from Shopify")
    return all_products

def save_products_to_database(products):
    """Save products to the database with upsert logic."""
    print(f"💾 Saving {len(products):,} products to database...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Count existing products
    cursor.execute("SELECT COUNT(*) FROM products")
    existing_count = cursor.fetchone()[0]
    print(f"📊 Existing products in database: {existing_count:,}")
    
    # Process products in batches
    batch_size = 100
    total_batches = (len(products) + batch_size - 1) // batch_size
    
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    
    for i in range(0, len(products), batch_size):
        batch_num = (i // batch_size) + 1
        batch = products[i:i + batch_size]
        
        print(f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} products)...")
        
        for product in batch:
            try:
                shopify_id = str(product['id'])
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
                print(f"⚠️  Error processing product {product.get('id', 'unknown')}: {str(e)}")
                skipped_count += 1
        
        # Commit batch
        conn.commit()
        
        if batch_num % 10 == 0:  # Progress update every 10 batches
            print(f"📊 Progress: {batch_num}/{total_batches} batches | {imported_count} new, {updated_count} updated, {skipped_count} errors")
    
    # Final count
    cursor.execute("SELECT COUNT(*) FROM products")
    final_count = cursor.fetchone()[0]
    
    print(f"\n🎉 Sync completed!")
    print(f"📊 Final database count: {final_count:,} products")
    print(f"📈 New products imported: {imported_count:,}")
    print(f"🔄 Existing products updated: {updated_count:,}")
    print(f"⚠️  Products with errors: {skipped_count:,}")
    
    cursor.close()
    conn.close()
    
    return {
        'total_processed': len(products),
        'imported': imported_count,
        'updated': updated_count,
        'skipped': skipped_count,
        'final_count': final_count
    }

def main():
    """Main sync function."""
    print("🚀 COMPLETE SHOPIFY PRODUCT SYNC")
    print("=" * 50)
    print("This will sync ALL products from Shopify to your local database")
    print("Expected: ~24,535 products")
    print()
    
    try:
        # Get credentials
        shop_url, access_token = get_shopify_credentials()
        print(f"🔗 Connected to: {shop_url}")
        
        # Fetch all products
        start_time = time.time()
        products = fetch_all_shopify_products(shop_url, access_token)
        fetch_time = time.time() - start_time
        
        print(f"⏱️  Fetch completed in {fetch_time:.1f} seconds")
        
        # Save to database
        save_time = time.time()
        results = save_products_to_database(products)
        save_time = time.time() - save_time
        
        print(f"⏱️  Database save completed in {save_time:.1f} seconds")
        print(f"⏱️  Total sync time: {(fetch_time + save_time):.1f} seconds")
        
        print("\n✅ Full sync completed successfully!")
        print("🎯 Your database now contains real Shopify data (no mock data)")
        
        return True
        
    except Exception as e:
        print(f"❌ Sync failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)