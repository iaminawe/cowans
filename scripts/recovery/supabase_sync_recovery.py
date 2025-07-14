#!/usr/bin/env python3
"""
Supabase sync recovery using the working pattern from execute_full_sync.py
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client
import requests
from datetime import datetime
import time

# Load environment variables
load_dotenv()

# Add the backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'web_dashboard', 'backend'))

def supabase_sync_recovery():
    """Recovery using the working sync pattern with Supabase."""
    try:
        from scripts.shopify.shopify_base import ShopifyAPIBase
        
        start_time = time.time()
        print(f'[{datetime.now()}] Starting Supabase product recovery...')
        
        # Get credentials
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        
        if not all([shop_url, access_token, supabase_url, supabase_key]):
            print('ERROR: Missing credentials')
            return
        
        # Create clients
        client = ShopifyAPIBase(shop_url, access_token, debug=False)
        supabase = create_client(supabase_url, supabase_key)
        
        # Test auth
        print('Testing authentication...')
        try:
            client.test_auth()
            print('✓ Authentication successful')
        except Exception as e:
            print(f'✗ Authentication failed: {e}')
            return
        
        # Get current count
        current_result = supabase.table('products').select('id', count='exact').execute()
        current_count = current_result.count if hasattr(current_result, 'count') else 0
        print(f'Current products in database: {current_count}')
        
        # Fetch all products with pagination using GraphQL
        print('\nFetching all products from Shopify...')
        query = """
        query GetProducts($first: Int!, $cursor: String) {
            products(first: $first, after: $cursor) {
                edges {
                    node {
                        id
                        title
                        description
                        handle
                        status
                        vendor
                        productType
                        tags
                        createdAt
                        updatedAt
                        variants(first: 10) {
                            edges {
                                node {
                                    id
                                    sku
                                    price
                                    compareAtPrice
                                    inventoryQuantity
                                    barcode
                                }
                            }
                        }
                        images(first: 5) {
                            edges {
                                node {
                                    url
                                    altText
                                }
                            }
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """
        
        all_products = []
        cursor = None
        page = 1
        
        while True:
            print(f'Fetching page {page}...')
            variables = {'first': 50}  # Conservative page size
            if cursor:
                variables['cursor'] = cursor
            
            try:
                result = client.execute_graphql(query, variables)
                
                if 'errors' in result:
                    print(f'GraphQL errors: {result["errors"]}')
                    break
                
                products_data = result.get('data', {}).get('products', {})
                products = products_data.get('edges', [])
                all_products.extend(products)
                
                print(f'  Retrieved {len(products)} products (Total: {len(all_products)})')
                
                # Check pagination
                page_info = products_data.get('pageInfo', {})
                if not page_info.get('hasNextPage'):
                    break
                    
                cursor = page_info.get('endCursor')
                page += 1
                
                # Small delay to avoid rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f'Error fetching page {page}: {e}')
                break
        
        print(f'\n✓ Total products fetched: {len(all_products)}')
        
        # Get existing products to avoid duplicates
        print('Getting existing products...')
        existing_result = supabase.table('products')\
            .select('shopify_product_id')\
            .not_.is_('shopify_product_id', 'null')\
            .execute()
        
        existing_ids = set()
        if existing_result.data:
            existing_ids = {item['shopify_product_id'] for item in existing_result.data}
        
        print(f'Found {len(existing_ids)} existing products')
        
        # Get or create category
        print('Setting up category...')
        category_result = supabase.table('categories')\
            .select('id')\
            .eq('name', 'Imported Products')\
            .execute()
        
        if category_result.data:
            category_id = category_result.data[0]['id']
        else:
            print('❌ Imported Products category not found')
            return
        
        # Save to database
        print('\nSaving products to database...')
        saved_count = 0
        updated_count = 0
        error_count = 0
        
        for i, edge in enumerate(all_products):
            if i % 100 == 0 and i > 0:
                print(f'  Processing product {i}/{len(all_products)}...')
            
            try:
                product = edge['node']
                shopify_id = product['id'].split('/')[-1]
                
                # Skip if already exists
                if shopify_id in existing_ids:
                    continue
                
                # Get first variant
                variant_data = {}
                if product.get('variants', {}).get('edges'):
                    variant = product['variants']['edges'][0]['node']
                    variant_data = {
                        'sku': variant.get('sku', ''),
                        'price': float(variant.get('price', 0)),
                        'compare_at_price': float(variant.get('compareAtPrice')) if variant.get('compareAtPrice') else None,
                        'inventory_quantity': variant.get('inventoryQuantity', 0),
                        'barcode': variant.get('barcode', '')
                    }
                
                # Get first image
                image_url = None
                if product.get('images', {}).get('edges'):
                    image_url = product['images']['edges'][0]['node'].get('url')
                
                # Prepare product data for Supabase
                product_data = {
                    'name': product['title'],
                    'description': product.get('description', ''),
                    'sku': variant_data.get('sku', f'SHOPIFY-{shopify_id}'),
                    'price': variant_data.get('price'),
                    'compare_at_price': variant_data.get('compare_at_price'),
                    'inventory_quantity': variant_data.get('inventory_quantity', 0),
                    'category_id': category_id,
                    'shopify_product_id': shopify_id,
                    'handle': product.get('handle'),
                    'product_type': product.get('productType'),
                    'brand': product.get('vendor'),
                    'tags': product.get('tags', []),
                    'status': product.get('status', '').lower(),
                    'shopify_sync_status': 'synced',
                    'shopify_synced_at': product.get('updatedAt', ''),
                    'featured_image_url': image_url,
                    'is_active': True,  # Required field
                    'created_at': product.get('createdAt', ''),
                    'updated_at': product.get('updatedAt', '')
                }
                
                # Insert product
                result = supabase.table('products').insert(product_data).execute()
                if result.data:
                    saved_count += 1
                    existing_ids.add(shopify_id)  # Add to existing set
                else:
                    error_count += 1
                
                # Progress update
                if saved_count % 100 == 0 and saved_count > 0:
                    print(f'  ✓ Saved {saved_count} products so far...')
                    
            except Exception as e:
                error_count += 1
                if error_count <= 5:  # Only show first 5 errors
                    print(f'  Error processing product: {e}')
                continue
        
        # Calculate duration
        duration = time.time() - start_time
        
        print(f'\n✓ RECOVERY COMPLETE!')
        print(f'  Duration: {duration:.1f} seconds')
        print(f'  Total products processed: {len(all_products)}')
        print(f'  New products saved: {saved_count}')
        print(f'  Updated products: {updated_count}')
        print(f'  Errors: {error_count}')
        print(f'  Success rate: {(saved_count / len(all_products) * 100):.1f}%')
        
        # Final count check
        final_result = supabase.table('products').select('id', count='exact').execute()
        final_count = final_result.count if hasattr(final_result, 'count') else 0
        
        print(f'\n📊 FINAL RESULTS:')
        print(f'  Database before: {current_count}')
        print(f'  Database after: {final_count}')
        print(f'  Net increase: {final_count - current_count}')
        
        recovery_percentage = (final_count / 24535) * 100
        print(f'  Recovery percentage: {recovery_percentage:.1f}%')
        
        if final_count > current_count:
            print(f'✅ SUCCESS: Recovered {final_count - current_count} products!')
        else:
            print('⚠️  No new products were added')
        
    except Exception as e:
        print(f'❌ Error in recovery: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    supabase_sync_recovery()