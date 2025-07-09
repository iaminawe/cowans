#!/usr/bin/env python
"""Direct Shopify Product Sync Script"""

import os
import sys
sys.path.append('.')
sys.path.append('../..')

from database import db_session_scope
from models import Product, Category
from repositories import ProductRepository
from datetime import datetime
import json

# Import Shopify base
from scripts.shopify.shopify_base import ShopifyAPIBase

def main():
    print('Starting direct Shopify product sync...')
    
    # Get Shopify credentials
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        print('ERROR: Shopify credentials not found in environment')
        sys.exit(1)
    
    print(f'Shop URL: {shop_url}')
    print('Access token: ***' + access_token[-4:])
    
    # Create client
    client = ShopifyAPIBase(shop_url, access_token, debug=True)
    
    # Test connection
    print('\nTesting Shopify connection...')
    try:
        client.test_auth()
        print('✓ Connection successful!')
    except Exception as e:
        print(f'✗ Connection failed: {e}')
        sys.exit(1)
    
    # Fetch products
    print('\nFetching products from Shopify...')
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
                    updatedAt
                    createdAt
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
                    images(first: 10) {
                        edges {
                            node {
                                id
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
        variables = {'first': 50}
        if cursor:
            variables['cursor'] = cursor
            
        result = client.execute_graphql(query, variables)
        
        if 'errors' in result:
            print(f'GraphQL errors: {result["errors"]}')
            sys.exit(1)
        
        products_data = result.get('data', {}).get('products', {})
        products = products_data.get('edges', [])
        all_products.extend(products)
        
        print(f'Page {page}: Retrieved {len(products)} products')
        
        # Check if there are more pages
        page_info = products_data.get('pageInfo', {})
        if not page_info.get('hasNextPage'):
            break
            
        cursor = page_info.get('endCursor')
        page += 1
    
    print(f'\nTotal products found: {len(all_products)}')
    
    # Display first 5 products
    print('\nFirst 5 products:')
    for i, edge in enumerate(all_products[:5]):
        product = edge['node']
        print(f'{i+1}. {product["title"]} (ID: {product["id"]})')
        if product.get('variants', {}).get('edges'):
            variant = product['variants']['edges'][0]['node']
            print(f'   SKU: {variant.get("sku", "N/A")}')
            print(f'   Price: ${variant.get("price", "0")}')
            print(f'   Inventory: {variant.get("inventoryQuantity", 0)}')
    
    if len(all_products) > 5:
        print(f'\n... and {len(all_products) - 5} more products')
    
    # Store in database
    print('\nSaving products to local database...')
    with db_session_scope() as session:
        repo = ProductRepository(session)
        
        # Get or create default category
        category = session.query(Category).filter_by(name='Imported from Shopify').first()
        if not category:
            category = Category(
                name='Imported from Shopify',
                description='Products imported from Shopify'
            )
            session.add(category)
            session.flush()
        
        saved_count = 0
        updated_count = 0
        error_count = 0
        
        for edge in all_products:
            try:
                product = edge['node']
                shopify_id = product['id'].split('/')[-1]
                
                # Get variant data
                variant_data = {}
                if product.get('variants', {}).get('edges'):
                    variant = product['variants']['edges'][0]['node']
                    variant_data = {
                        'sku': variant.get('sku', ''),
                        'price': float(variant.get('price', 0)),
                        'inventory_quantity': variant.get('inventoryQuantity', 0),
                        'barcode': variant.get('barcode', ''),
                    }
                
                # Get image data
                image_url = None
                if product.get('images', {}).get('edges'):
                    image = product['images']['edges'][0]['node']
                    image_url = image.get('url')
                
                # Check if product exists
                existing = None
                if variant_data.get('sku'):
                    existing = repo.get_by_sku(variant_data['sku'])
                if not existing:
                    existing = repo.get_by_shopify_id(shopify_id)
                
                if existing:
                    # Update existing product
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
                    existing.inventory_quantity = variant_data.get('inventory_quantity', 0)
                    existing.featured_image_url = image_url
                    existing.custom_attributes = {
                        'product_type': product.get('productType'),
                        'tags': product.get('tags', []),
                        'barcode': variant_data.get('barcode')
                    }
                    updated_count += 1
                else:
                    # Create new product
                    new_product = Product(
                        name=product['title'],
                        title=product['title'],
                        description=product.get('description', ''),
                        sku=variant_data.get('sku', f'SHOPIFY-{shopify_id}'),
                        price=variant_data.get('price'),
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
                        custom_attributes={
                            'product_type': product.get('productType'),
                            'tags': product.get('tags', []),
                            'barcode': variant_data.get('barcode')
                        }
                    )
                    session.add(new_product)
                    saved_count += 1
                    
            except Exception as e:
                print(f'Error processing product {product.get("title", "Unknown")}: {e}')
                error_count += 1
                continue
        
        session.commit()
        print(f'\n✓ Sync complete!')
        print(f'  - New products: {saved_count}')
        print(f'  - Updated products: {updated_count}')
        print(f'  - Errors: {error_count}')
        print(f'  - Total synced: {saved_count + updated_count}')
        
        # Store sync result in memory
        print('\nStoring sync results in coordination memory...')
        sync_result = {
            'sync_id': f'direct_sync_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}',
            'timestamp': datetime.utcnow().isoformat(),
            'total_products': len(all_products),
            'new_products': saved_count,
            'updated_products': updated_count,
            'errors': error_count,
            'status': 'completed'
        }
        
        # Save to file for coordination
        import json
        with open('/tmp/shopify_sync_result.json', 'w') as f:
            json.dump(sync_result, f, indent=2)
        
        print('✓ Sync results saved to coordination memory')

if __name__ == '__main__':
    main()