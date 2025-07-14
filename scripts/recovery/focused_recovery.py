#!/usr/bin/env python3
"""
Focused product recovery - smaller batches with progress tracking
"""
import os
from dotenv import load_dotenv
from supabase import create_client
import requests
import json
import time
from datetime import datetime

# Load environment variables
load_dotenv()

def focused_recovery():
    """Focused recovery with smaller batches and better progress tracking."""
    try:
        # Get credentials
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        shopify_shop_url = os.getenv('SHOPIFY_SHOP_URL')
        shopify_access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not all([supabase_url, supabase_key, shopify_shop_url, shopify_access_token]):
            print("❌ Missing required credentials")
            return
        
        print("🎯 FOCUSED PRODUCT RECOVERY")
        print("=" * 40)
        
        # Create Supabase client
        supabase = create_client(supabase_url, supabase_key)
        
        # Get current count
        current_result = supabase.table('products').select('id', count='exact').execute()
        current_count = current_result.count if hasattr(current_result, 'count') else 0
        print(f"Starting with: {current_count} products")
        
        # Get existing IDs efficiently
        print("🔍 Getting existing product IDs...")
        existing_result = supabase.table('products')\
            .select('shopify_product_id')\
            .not_.is_('shopify_product_id', 'null')\
            .execute()
        
        existing_ids = set()
        if existing_result.data:
            existing_ids = {item['shopify_product_id'] for item in existing_result.data}
        
        print(f"Found {len(existing_ids)} existing products")
        
        # Get category
        cat_result = supabase.table('categories')\
            .select('id')\
            .eq('name', 'Imported Products')\
            .execute()
        
        if not cat_result.data:
            print("❌ Imported Products category not found")
            return
        
        category_id = cat_result.data[0]['id']
        print(f"Using category: {category_id}")
        
        # Fetch products in chunks
        print("\n📥 Fetching products in focused batches...")
        
        headers = {
            'X-Shopify-Access-Token': shopify_access_token,
            'Content-Type': 'application/json'
        }
        
        shopify_base_url = f"https://{shopify_shop_url}"
        
        # Process in smaller chunks
        max_pages = 10  # Process 10 pages at a time (2,500 products)
        page = 1
        page_info = None
        total_imported = 0
        
        while page <= max_pages:
            print(f"\n🔄 Processing batch starting at page {page}...")
            
            # Fetch this batch of pages
            batch_products = []
            batch_pages = 0
            
            while batch_pages < 5 and page <= max_pages:  # 5 pages per batch
                url = f"{shopify_base_url}/admin/api/2023-10/products.json?limit=250"
                if page_info:
                    url += f"&page_info={page_info}"
                
                print(f"  📄 Fetching page {page}...")
                response = requests.get(url, headers=headers)
                
                if response.status_code != 200:
                    print(f"  ❌ Error: {response.status_code}")
                    break
                
                data = response.json()
                products = data.get('products', [])
                
                if not products:
                    print(f"  ✅ No more products")
                    break
                
                batch_products.extend(products)
                print(f"  ✅ Got {len(products)} products")
                
                # Check pagination
                link_header = response.headers.get('Link', '')
                if 'rel="next"' in link_header:
                    import re
                    match = re.search(r'page_info=([^&>]+)', link_header)
                    if match:
                        page_info = match.group(1)
                    else:
                        break
                else:
                    break
                
                batch_pages += 1
                page += 1
                time.sleep(0.3)
            
            if not batch_products:
                print("No more products to process")
                break
            
            print(f"📦 Processing {len(batch_products)} products...")
            
            # Filter new products
            new_products = []
            for product in batch_products:
                if str(product['id']) not in existing_ids:
                    new_products.append(product)
            
            print(f"🆕 Found {len(new_products)} new products to import")
            
            # Import new products
            imported_count = 0
            for i, product in enumerate(new_products):
                try:
                    # Get variant data
                    variants = product.get('variants', [])
                    price = 0
                    sku = ''
                    inventory = 0
                    
                    if variants:
                        first_variant = variants[0]
                        price = float(first_variant.get('price', 0))
                        sku = first_variant.get('sku', '')
                        inventory = int(first_variant.get('inventory_quantity', 0))
                    
                    # Prepare product data
                    product_data = {
                        'name': product.get('title', ''),
                        'description': product.get('body_html', ''),
                        'shopify_product_id': str(product['id']),
                        'handle': product.get('handle', ''),
                        'product_type': product.get('product_type', ''),
                        'brand': product.get('vendor', ''),
                        'tags': product.get('tags', '').split(',') if product.get('tags') else [],
                        'status': product.get('status', 'draft'),
                        'category_id': category_id,
                        'sku': sku,
                        'price': price,
                        'inventory_quantity': inventory,
                        'shopify_sync_status': 'synced',
                        'shopify_synced_at': product.get('updated_at', ''),
                        'created_at': product.get('created_at', ''),
                        'updated_at': product.get('updated_at', '')
                    }
                    
                    # Insert product
                    result = supabase.table('products').insert(product_data).execute()
                    if result.data:
                        imported_count += 1
                        existing_ids.add(str(product['id']))  # Add to existing set
                        
                        if imported_count % 10 == 0:
                            print(f"  ✅ Imported {imported_count}/{len(new_products)} products")
                    
                except Exception as e:
                    print(f"  ❌ Error with product {product.get('title', 'Unknown')}: {str(e)}")
                    continue
            
            total_imported += imported_count
            print(f"✅ Batch complete: {imported_count} products imported")
            print(f"📊 Total imported so far: {total_imported}")
            
            # Check current database count
            check_result = supabase.table('products').select('id', count='exact').execute()
            current_db_count = check_result.count if hasattr(check_result, 'count') else 0
            print(f"📈 Database now has: {current_db_count} products")
            
            # Rate limiting between batches
            time.sleep(2)
        
        # Final summary
        print(f"\n🎉 FOCUSED RECOVERY COMPLETE!")
        print(f"  Total products imported: {total_imported}")
        
        # Final count
        final_result = supabase.table('products').select('id', count='exact').execute()
        final_count = final_result.count if hasattr(final_result, 'count') else 0
        
        print(f"  Starting count: {current_count}")
        print(f"  Final count: {final_count}")
        print(f"  Net increase: {final_count - current_count}")
        
        recovery_percentage = (final_count / 24535) * 100
        print(f"  Recovery percentage: {recovery_percentage:.1f}%")
        
        if final_count > current_count:
            print(f"✅ SUCCESS: Added {final_count - current_count} products!")
        else:
            print("⚠️  No products were added in this batch")
        
        remaining = 24535 - final_count
        if remaining > 0:
            print(f"🔄 Still need to recover: {remaining} products")
            print("Run this script again to continue recovery")
        else:
            print("🎉 FULL RECOVERY COMPLETE!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    focused_recovery()