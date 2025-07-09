#!/usr/bin/env python
"""Execute full Shopify product sync"""

import os
import sys
sys.path.append('.')
sys.path.append('../..')

from database import db_session_scope
from models import Product, Category
from repositories import ProductRepository
from datetime import datetime
import json
import time

from scripts.shopify.shopify_base import ShopifyAPIBase

def main():
    start_time = time.time()
    print(f'[{datetime.now()}] Starting FULL Shopify product sync...')
    
    # Get credentials
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        print('ERROR: Missing Shopify credentials')
        return
    
    # Create client
    client = ShopifyAPIBase(shop_url, access_token, debug=False)
    
    # Test auth
    print('Testing authentication...')
    try:
        client.test_auth()
        print('✓ Authentication successful')
    except Exception as e:
        print(f'✗ Authentication failed: {e}')
        return
    
    # Fetch all products with pagination
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
        variables = {'first': 50}  # Max 250 per request
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
    
    # Save to database
    print('\nSaving products to database...')
    with db_session_scope() as session:
        repo = ProductRepository(session)
        
        # Get or create category
        category = session.query(Category).filter_by(name='Shopify Import').first()
        if not category:
            category = Category(
                name='Shopify Import',
                description='Products imported from Shopify'
            )
            session.add(category)
            session.flush()
        
        saved_count = 0
        updated_count = 0
        error_count = 0
        
        for i, edge in enumerate(all_products):
            if i % 100 == 0 and i > 0:
                print(f'  Processing product {i}/{len(all_products)}...')
            
            try:
                product = edge['node']
                shopify_id = product['id'].split('/')[-1]
                
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
                
                # Check if exists
                existing = None
                if variant_data.get('sku'):
                    existing = repo.get_by_sku(variant_data['sku'])
                if not existing:
                    existing = repo.get_by_shopify_id(shopify_id)
                
                if existing:
                    # Update
                    existing.name = product['title']
                    existing.title = product['title']
                    existing.description = product.get('description', '')
                    existing.shopify_product_id = shopify_id
                    existing.shopify_handle = product.get('handle')
                    existing.shopify_status = product.get('status', '').lower()
                    existing.shopify_sync_status = 'synced'
                    existing.shopify_synced_at = datetime.utcnow()
                    existing.brand = product.get('vendor')
                    existing.price = variant_data.get('price')
                    existing.compare_at_price = variant_data.get('compare_at_price')
                    existing.inventory_quantity = variant_data.get('inventory_quantity', 0)
                    existing.featured_image_url = image_url
                    existing.product_type = product.get('productType')
                    existing.custom_attributes = {
                        'tags': product.get('tags', []),
                        'barcode': variant_data.get('barcode')
                    }
                    updated_count += 1
                else:
                    # Create new
                    new_product = Product(
                        name=product['title'],
                        title=product['title'],
                        description=product.get('description', ''),
                        sku=variant_data.get('sku', f'SHOPIFY-{shopify_id}'),
                        price=variant_data.get('price'),
                        compare_at_price=variant_data.get('compare_at_price'),
                        inventory_quantity=variant_data.get('inventory_quantity', 0),
                        category_id=category.id,
                        shopify_product_id=shopify_id,
                        shopify_handle=product.get('handle'),
                        shopify_status=product.get('status', '').lower(),
                        shopify_sync_status='synced',
                        shopify_synced_at=datetime.utcnow(),
                        brand=product.get('vendor'),
                        status='active',
                        featured_image_url=image_url,
                        product_type=product.get('productType'),
                        custom_attributes={
                            'tags': product.get('tags', []),
                            'barcode': variant_data.get('barcode')
                        }
                    )
                    session.add(new_product)
                    saved_count += 1
                
                # Commit every 100 products
                if (saved_count + updated_count) % 100 == 0:
                    session.commit()
                    
            except Exception as e:
                print(f'  Error processing product: {e}')
                error_count += 1
                continue
        
        # Final commit
        session.commit()
        
        # Calculate duration
        duration = time.time() - start_time
        
        print(f'\n✓ SYNC COMPLETE!')
        print(f'  Duration: {duration:.1f} seconds')
        print(f'  Total products: {len(all_products)}')
        print(f'  New products: {saved_count}')
        print(f'  Updated products: {updated_count}')
        print(f'  Errors: {error_count}')
        print(f'  Success rate: {((saved_count + updated_count) / len(all_products) * 100):.1f}%')
        
        # Save sync result
        sync_result = {
            'sync_id': f'full_sync_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}',
            'timestamp': datetime.utcnow().isoformat(),
            'duration_seconds': duration,
            'total_products': len(all_products),
            'new_products': saved_count,
            'updated_products': updated_count,
            'errors': error_count,
            'status': 'completed',
            'shop_url': shop_url
        }
        
        with open('/tmp/shopify_full_sync_result.json', 'w') as f:
            json.dump(sync_result, f, indent=2)
        
        print(f'\n✓ Sync results saved to /tmp/shopify_full_sync_result.json')
        
        # Also save to database sync history (if table exists)
        try:
            from sync_models import SyncBatch
            sync_batch = SyncBatch(
                batch_id=sync_result['sync_id'],
                batch_name='Full Shopify Product Sync',
                sync_type='full',
                sync_direction='pull_from_shopify',
                status='completed',
                total_items=len(all_products),
                processed_items=saved_count + updated_count,
                failed_items=error_count,
                started_at=datetime.utcnow() - timedelta(seconds=duration),
                completed_at=datetime.utcnow(),
                created_by='system',
                statistics=sync_result
            )
            session.add(sync_batch)
            session.commit()
            print('✓ Sync history saved to database')
        except:
            pass

if __name__ == '__main__':
    main()