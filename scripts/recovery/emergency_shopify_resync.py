#!/usr/bin/env python3
"""
Emergency re-sync all products from Shopify to recover accidentally deleted products
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

# Add the backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'web_dashboard', 'backend'))

def emergency_resync_from_shopify():
    """Re-sync all products from Shopify to recover deleted products."""
    try:
        # Get credentials
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        shopify_shop_url = os.getenv('SHOPIFY_SHOP_URL')
        shopify_access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not all([supabase_url, supabase_key, shopify_shop_url, shopify_access_token]):
            print("Missing required credentials")
            return
            
        print(f"🚨 EMERGENCY SHOPIFY PRODUCT RECOVERY")
        print("=" * 50)
        print(f"Shopify Store: {shopify_shop_url}")
        print(f"Supabase: {supabase_url}")
        
        # Create Supabase client
        supabase = create_client(supabase_url, supabase_key)
        
        # Check current state
        current_result = supabase.table('products').select('id', count='exact').execute()
        current_count = current_result.count if hasattr(current_result, 'count') else 0
        print(f"Current products in database: {current_count}")
        
        # Get products from Shopify using REST API (more reliable for bulk operations)
        print(f"\n📥 Fetching products from Shopify...")
        
        shopify_base_url = f"https://{shopify_shop_url}"
        headers = {
            'X-Shopify-Access-Token': shopify_access_token,
            'Content-Type': 'application/json'
        }
        
        all_products = []
        page_info = None
        page_count = 0
        
        while True:
            page_count += 1
            url = f"{shopify_base_url}/admin/api/2023-10/products.json?limit=250"
            if page_info:
                url += f"&page_info={page_info}"
            
            print(f"  Fetching page {page_count}...")
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                print(f"  ❌ Error fetching page {page_count}: {response.status_code}")
                print(f"  Response: {response.text}")
                break
            
            data = response.json()
            products = data.get('products', [])
            
            if not products:
                break
                
            all_products.extend(products)
            print(f"  ✅ Fetched {len(products)} products (total: {len(all_products)})")
            
            # Check for pagination
            link_header = response.headers.get('Link', '')
            if 'rel="next"' in link_header:
                # Extract page_info from link header
                import re
                match = re.search(r'page_info=([^&>]+)', link_header)
                if match:
                    page_info = match.group(1)
                else:
                    break
            else:
                break
            
            # Rate limiting
            time.sleep(0.5)
        
        print(f"\n📊 Found {len(all_products)} products in Shopify")
        
        if len(all_products) == 0:
            print("❌ No products found in Shopify!")
            return
        
        # Find or create "Imported Products" category
        print(f"\n📁 Setting up categories...")
        
        # Check if "Imported Products" category exists
        imported_cat_result = supabase.table('categories')\
            .select('id')\
            .eq('name', 'Imported Products')\
            .single()\
            .execute()
        
        if imported_cat_result.data:
            imported_category_id = imported_cat_result.data['id']
            print(f"  Using existing 'Imported Products' category (ID: {imported_category_id})")
        else:
            # Create it
            cat_data = {
                'name': 'Imported Products',
                'slug': 'imported-products',
                'description': 'Products imported from Shopify',
                'level': 0,
                'path': 'imported-products',
                'is_active': True,
                'created_at': '2023-01-01T00:00:00Z',
                'updated_at': '2023-01-01T00:00:00Z'
            }
            cat_result = supabase.table('categories').insert(cat_data).execute()
            imported_category_id = cat_result.data[0]['id']
            print(f"  Created 'Imported Products' category (ID: {imported_category_id})")
        
        # Import products in batches using bulk operations
        print(f"\n💾 Importing products to Supabase...")
        batch_size = 50  # Smaller batches for better performance
        imported_count = 0
        updated_count = 0
        error_count = 0
        
        # Process in smaller batches with bulk operations
        for i in range(0, len(all_products), batch_size):
            batch = all_products[i:i + batch_size]
            print(f"  Processing batch {i//batch_size + 1} ({len(batch)} products)...")
            
            # Prepare batch data
            batch_data = []
            for shopify_product in batch:
                try:
                    # Prepare product data
                    product_data = {
                        'name': shopify_product.get('title', ''),
                        'description': shopify_product.get('body_html', ''),
                        'shopify_product_id': str(shopify_product['id']),
                        'handle': shopify_product.get('handle', ''),
                        'product_type': shopify_product.get('product_type', ''),
                        'tags': shopify_product.get('tags', '').split(',') if shopify_product.get('tags') else [],
                        'status': shopify_product.get('status', 'draft'),
                        'category_id': imported_category_id,
                        'shopify_sync_status': 'synced',
                        'shopify_synced_at': shopify_product.get('updated_at', ''),
                        'created_at': shopify_product.get('created_at', ''),
                        'updated_at': shopify_product.get('updated_at', '')
                    }
                    
                    # Add variant data if available
                    variants = shopify_product.get('variants', [])
                    if variants:
                        first_variant = variants[0]
                        product_data.update({
                            'sku': first_variant.get('sku', ''),
                            'price': float(first_variant.get('price', 0)),
                            'compare_at_price': float(first_variant.get('compare_at_price', 0)) if first_variant.get('compare_at_price') else None,
                            'inventory_quantity': int(first_variant.get('inventory_quantity', 0)),
                            'weight': float(first_variant.get('weight', 0)) if first_variant.get('weight') else None,
                            'weight_unit': first_variant.get('weight_unit', 'kg'),
                            'requires_shipping': first_variant.get('requires_shipping', True),
                            'taxable': first_variant.get('taxable', True)
                        })
                    
                    batch_data.append(product_data)
                    
                except Exception as e:
                    error_count += 1
                    print(f"    ❌ Error preparing product {shopify_product.get('id', 'unknown')}: {str(e)}")
            
            # Bulk insert with upsert (handles duplicates)
            try:
                result = supabase.table('products').upsert(batch_data, on_conflict='shopify_product_id').execute()
                if result.data:
                    imported_count += len(result.data)
                    print(f"    ✅ Batch {i//batch_size + 1}: {len(result.data)} products processed")
            except Exception as e:
                print(f"    ❌ Batch {i//batch_size + 1} failed: {str(e)}")
                error_count += len(batch_data)
            
            # Minimal rate limiting
            time.sleep(0.5)
            
            if (i // batch_size + 1) % 20 == 0:  # Progress update every 20 batches
                print(f"    Progress: {imported_count} imported, {error_count} errors")
        
        # Final results
        print(f"\n✅ RECOVERY COMPLETE!")
        print(f"  New products imported: {imported_count}")
        print(f"  Existing products updated: {updated_count}")
        print(f"  Errors: {error_count}")
        print(f"  Total processed: {len(all_products)}")
        
        # Check final count
        final_result = supabase.table('products').select('id', count='exact').execute()
        final_count = final_result.count if hasattr(final_result, 'count') else 0
        print(f"  Final products in database: {final_count}")
        
        if final_count > current_count:
            print(f"\n🎉 SUCCESS: Recovered {final_count - current_count} products!")
        else:
            print(f"\n⚠️  WARNING: Product count didn't increase as expected")
            
    except Exception as e:
        print(f"❌ Error in emergency resync: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    emergency_resync_from_shopify()