#!/usr/bin/env python3
"""
Comprehensive product recovery - recover all 23,535 missing products
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

def comprehensive_recovery():
    """Comprehensive recovery of all missing products."""
    try:
        # Get credentials
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        shopify_shop_url = os.getenv('SHOPIFY_SHOP_URL')
        shopify_access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not all([supabase_url, supabase_key, shopify_shop_url, shopify_access_token]):
            print("❌ Missing required credentials")
            return
        
        print("🚨 COMPREHENSIVE PRODUCT RECOVERY")
        print("=" * 50)
        print(f"Target: Recover 23,535 missing products from Shopify")
        print(f"Started: {datetime.now()}")
        
        # Create Supabase client
        supabase = create_client(supabase_url, supabase_key)
        
        # Get current state
        current_result = supabase.table('products').select('id', count='exact').execute()
        current_count = current_result.count if hasattr(current_result, 'count') else 0
        print(f"Current database products: {current_count}")
        
        # Get existing Shopify IDs to avoid duplicates
        print("\n🔍 Getting existing Shopify IDs...")
        existing_result = supabase.table('products')\
            .select('shopify_product_id')\
            .not_.is_('shopify_product_id', 'null')\
            .execute()
        
        existing_ids = set()
        if existing_result.data:
            existing_ids = {item['shopify_product_id'] for item in existing_result.data}
        
        print(f"Found {len(existing_ids)} existing Shopify IDs")
        
        # Find "Imported Products" category
        imported_cat_result = supabase.table('categories')\
            .select('id')\
            .eq('name', 'Imported Products')\
            .execute()
        
        if imported_cat_result.data:
            imported_category_id = imported_cat_result.data[0]['id']
        else:
            print("❌ Imported Products category not found")
            return
        
        # Fetch ALL products from Shopify
        print("\n📥 Fetching ALL products from Shopify...")
        
        shopify_base_url = f"https://{shopify_shop_url}"
        headers = {
            'X-Shopify-Access-Token': shopify_access_token,
            'Content-Type': 'application/json'
        }
        
        all_products = []
        page_info = None
        page = 1
        
        while True:
            url = f"{shopify_base_url}/admin/api/2023-10/products.json?limit=250"
            if page_info:
                url += f"&page_info={page_info}"
            
            print(f"  📄 Fetching page {page}...")
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                print(f"  ❌ Error fetching page {page}: {response.status_code}")
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
            time.sleep(0.3)
        
        print(f"\n📊 Total products found in Shopify: {len(all_products)}")
        
        # Filter out existing products
        print("\n🔍 Filtering out existing products...")
        new_products = []
        for product in all_products:
            shopify_id = str(product['id'])
            if shopify_id not in existing_ids:
                new_products.append(product)
        
        print(f"Products to import: {len(new_products)}")
        print(f"Products already exist: {len(all_products) - len(new_products)}")
        
        if len(new_products) == 0:
            print("✅ All products already exist in database!")
            return
        
        # Import products in optimized batches
        print(f"\n💾 Importing {len(new_products)} products...")
        batch_size = 10  # Small batches for reliability
        imported_count = 0
        error_count = 0
        start_time = time.time()
        
        for i in range(0, len(new_products), batch_size):
            batch = new_products[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(new_products) + batch_size - 1) // batch_size
            
            print(f"  📦 Batch {batch_num}/{total_batches} ({len(batch)} products)...")
            
            batch_data = []
            for shopify_product in batch:
                try:
                    # Get first variant
                    variants = shopify_product.get('variants', [])
                    price = 0
                    sku = ''
                    inventory = 0
                    compare_at_price = None
                    
                    if variants:
                        first_variant = variants[0]
                        price = float(first_variant.get('price', 0))
                        sku = first_variant.get('sku', '')
                        inventory = int(first_variant.get('inventory_quantity', 0))
                        if first_variant.get('compare_at_price'):
                            compare_at_price = float(first_variant.get('compare_at_price', 0))
                    
                    # Prepare product data
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
                        'compare_at_price': compare_at_price,
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
            
            # Insert batch
            if batch_data:
                try:
                    result = supabase.table('products').insert(batch_data).execute()
                    if result.data:
                        imported_count += len(result.data)
                        print(f"    ✅ Imported {len(result.data)} products")
                    else:
                        print(f"    ⚠️  No data returned for batch")
                        
                except Exception as e:
                    error_count += len(batch_data)
                    print(f"    ❌ Batch failed: {str(e)}")
            
            # Progress update
            if batch_num % 10 == 0:
                elapsed = time.time() - start_time
                rate = imported_count / elapsed if elapsed > 0 else 0
                remaining = len(new_products) - (i + batch_size)
                eta = remaining / rate / 60 if rate > 0 else 0
                print(f"    📊 Progress: {imported_count}/{len(new_products)} ({imported_count/len(new_products)*100:.1f}%) - ETA: {eta:.1f}min")
            
            # Rate limiting
            time.sleep(0.2)
        
        # Final results
        elapsed = time.time() - start_time
        print(f"\n🎉 COMPREHENSIVE RECOVERY COMPLETE!")
        print(f"  Duration: {elapsed/60:.1f} minutes")
        print(f"  Products processed: {len(new_products)}")
        print(f"  Successfully imported: {imported_count}")
        print(f"  Errors: {error_count}")
        print(f"  Success rate: {(imported_count / len(new_products) * 100):.1f}%")
        
        # Final count check
        final_result = supabase.table('products').select('id', count='exact').execute()
        final_count = final_result.count if hasattr(final_result, 'count') else 0
        print(f"  Database before: {current_count}")
        print(f"  Database after: {final_count}")
        print(f"  Net increase: {final_count - current_count}")
        
        if final_count > current_count:
            recovery_percentage = (final_count / 24535) * 100
            print(f"\n✅ SUCCESS: Recovered {final_count - current_count} products!")
            print(f"📊 Total recovery: {recovery_percentage:.1f}% of original products")
            
            if recovery_percentage > 95:
                print("🎉 EXCELLENT: Nearly complete recovery!")
            elif recovery_percentage > 80:
                print("✅ GOOD: Strong recovery achieved!")
            else:
                print("⚠️  PARTIAL: Some products still missing")
        else:
            print(f"\n❌ FAILED: No products were recovered")
        
    except Exception as e:
        print(f"❌ Error in comprehensive recovery: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    comprehensive_recovery()