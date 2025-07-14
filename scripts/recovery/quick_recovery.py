#!/usr/bin/env python3
"""
Quick recovery - import products from Shopify to recover deleted ones
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client
import requests
import json
import time

# Load environment variables
load_dotenv()

def quick_recovery():
    """Quick product recovery with progress tracking."""
    try:
        # Get credentials
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        shopify_shop_url = os.getenv('SHOPIFY_SHOP_URL')
        shopify_access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not all([supabase_url, supabase_key, shopify_shop_url, shopify_access_token]):
            print("❌ Missing required credentials")
            return
        
        print("🚨 QUICK SHOPIFY RECOVERY")
        print("=" * 40)
        
        # Create Supabase client
        supabase = create_client(supabase_url, supabase_key)
        
        # Check current state
        current_result = supabase.table('products').select('id', count='exact').execute()
        current_count = current_result.count if hasattr(current_result, 'count') else 0
        print(f"Current products: {current_count}")
        
        # Get products from Shopify - limit to recent ones for faster recovery
        print("\n📥 Fetching products from Shopify...")
        
        shopify_base_url = f"https://{shopify_shop_url}"
        headers = {
            'X-Shopify-Access-Token': shopify_access_token,
            'Content-Type': 'application/json'
        }
        
        # Fetch products using cursor pagination (Link header)
        all_products = []
        page_info = None
        page = 1
        max_pages = 20  # Limit to first 20 pages for quick recovery
        
        while page <= max_pages:
            url = f"{shopify_base_url}/admin/api/2023-10/products.json?limit=250"
            if page_info:
                url += f"&page_info={page_info}"
            
            print(f"  Fetching page {page}...")
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                print(f"  ❌ Error fetching page {page}: {response.status_code}")
                print(f"  Response: {response.text}")
                break
            
            data = response.json()
            products = data.get('products', [])
            
            if not products:
                print(f"  ✅ No more products found at page {page}")
                break
                
            all_products.extend(products)
            print(f"  ✅ Page {page}: {len(products)} products (total: {len(all_products)})")
            
            # Check for pagination
            link_header = response.headers.get('Link', '')
            if 'rel="next"' in link_header:
                # Extract page_info from link header
                import re
                match = re.search(r'page_info=([^&>]+)', link_header)
                if match:
                    page_info = match.group(1)
                    page += 1
                else:
                    break
            else:
                break
            
            # Rate limiting
            time.sleep(0.5)
        
        print(f"\n📊 Found {len(all_products)} products to process")
        
        # Find "Imported Products" category
        imported_cat_result = supabase.table('categories')\
            .select('id')\
            .eq('name', 'Imported Products')\
            .execute()
        
        if imported_cat_result.data:
            imported_category_id = imported_cat_result.data[0]['id']
            print(f"Using category ID: {imported_category_id}")
        else:
            print("❌ Imported Products category not found")
            return
        
        # Import products in batches
        print(f"\n💾 Importing products...")
        batch_size = 25  # Very small batches for reliability
        imported_count = 0
        error_count = 0
        
        for i in range(0, len(all_products), batch_size):
            batch = all_products[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            print(f"  Processing batch {batch_num}/{(len(all_products) + batch_size - 1) // batch_size}...")
            
            # Prepare batch data
            batch_data = []
            for shopify_product in batch:
                try:
                    # Get first variant
                    variants = shopify_product.get('variants', [])
                    price = 0
                    sku = ''
                    inventory = 0
                    
                    if variants:
                        first_variant = variants[0]
                        price = float(first_variant.get('price', 0))
                        sku = first_variant.get('sku', '')
                        inventory = int(first_variant.get('inventory_quantity', 0))
                    
                    product_data = {
                        'name': shopify_product.get('title', ''),
                        'description': shopify_product.get('body_html', ''),
                        'shopify_product_id': str(shopify_product['id']),
                        'handle': shopify_product.get('handle', ''),
                        'product_type': shopify_product.get('product_type', ''),
                        'brand': shopify_product.get('vendor', ''),
                        'tags': shopify_product.get('tags', '').split(',') if shopify_product.get('tags') else [],
                        'status': shopify_product.get('status', 'draft'),
                        'category_id': imported_category_id,
                        'sku': sku,
                        'price': price,
                        'inventory_quantity': inventory,
                        'shopify_sync_status': 'synced',
                        'shopify_synced_at': shopify_product.get('updated_at', ''),
                        'created_at': shopify_product.get('created_at', ''),
                        'updated_at': shopify_product.get('updated_at', '')
                    }
                    
                    batch_data.append(product_data)
                    
                except Exception as e:
                    error_count += 1
                    print(f"    ❌ Error preparing product: {str(e)}")
            
            # Insert batch - checking for duplicates first
            if batch_data:
                try:
                    # Check for existing products in this batch
                    shopify_ids = [item['shopify_product_id'] for item in batch_data]
                    existing_result = supabase.table('products')\
                        .select('shopify_product_id')\
                        .in_('shopify_product_id', shopify_ids)\
                        .execute()
                    
                    existing_ids = set()
                    if existing_result.data:
                        existing_ids = {item['shopify_product_id'] for item in existing_result.data}
                    
                    # Filter out existing products
                    new_products = [item for item in batch_data if item['shopify_product_id'] not in existing_ids]
                    
                    if new_products:
                        result = supabase.table('products').insert(new_products).execute()
                        if result.data:
                            imported_count += len(result.data)
                            print(f"    ✅ Batch {batch_num}: {len(result.data)} new products imported")
                        else:
                            print(f"    ⚠️  Batch {batch_num}: No data returned")
                    else:
                        print(f"    ⚠️  Batch {batch_num}: All products already exist")
                        
                except Exception as e:
                    print(f"    ❌ Batch {batch_num} failed: {str(e)}")
                    error_count += len(batch_data)
            
            # Progress update
            if batch_num % 10 == 0:
                print(f"    📊 Progress: {imported_count} imported, {error_count} errors")
            
            # Rate limiting
            time.sleep(0.2)
        
        # Final results
        print(f"\n🎉 QUICK RECOVERY COMPLETE!")
        print(f"  Products processed: {len(all_products)}")
        print(f"  Successfully imported: {imported_count}")
        print(f"  Errors: {error_count}")
        
        # Check final count
        final_result = supabase.table('products').select('id', count='exact').execute()
        final_count = final_result.count if hasattr(final_result, 'count') else 0
        print(f"  Database before: {current_count}")
        print(f"  Database after: {final_count}")
        print(f"  Net increase: {final_count - current_count}")
        
        if final_count > current_count:
            print(f"\n✅ SUCCESS: Added {final_count - current_count} products!")
        else:
            print(f"\n⚠️  No new products added")
        
    except Exception as e:
        print(f"❌ Error in quick recovery: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    quick_recovery()