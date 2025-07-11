#!/usr/bin/env python3
"""
Recover products using existing Supabase infrastructure
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'web_dashboard', 'backend'))

def recover_products():
    """Recover products using the existing Shopify sync functionality."""
    try:
        from services.supabase_database import get_supabase_db
        from scripts.shopify.shopify_base import ShopifyAPIBase
        from datetime import datetime
        
        print("🚨 SHOPIFY PRODUCT RECOVERY")
        print("=" * 40)
        
        # Get credentials
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            print("❌ Missing Shopify credentials")
            return
        
        print(f"🛍️  Shop: {shop_url}")
        print(f"🔑 Token: ...{access_token[-4:]}")
        
        # Initialize clients
        shopify_client = ShopifyAPIBase(shop_url, access_token, debug=True)
        supabase = get_supabase_db()
        
        # Test authentication
        print("\n🔐 Testing Shopify authentication...")
        shopify_client.test_auth()
        print("✅ Shopify authenticated successfully")
        
        # Check current state
        print("\n📊 Current database state:")
        current_result = supabase.client.table('products').select('id', count='exact').execute()
        current_count = current_result.count if hasattr(current_result, 'count') else 0
        print(f"   Products in database: {current_count}")
        
        # Fetch products from Shopify using GraphQL (more comprehensive)
        print("\n📥 Fetching products from Shopify...")
        
        query = """
        query GetProducts($first: Int!, $after: String) {
            products(first: $first, after: $after) {
                edges {
                    node {
                        id
                        title
                        handle
                        description: descriptionHtml
                        productType
                        vendor
                        tags
                        status
                        createdAt
                        updatedAt
                        variants(first: 1) {
                            edges {
                                node {
                                    id
                                    sku
                                    price
                                    compareAtPrice
                                    inventoryQuantity
                                    weight
                                    weightUnit
                                    requiresShipping
                                    taxable
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
        has_next_page = True
        cursor = None
        page = 1
        
        while has_next_page:
            variables = {'first': 250}
            if cursor:
                variables['after'] = cursor
            
            print(f"   Fetching page {page}...")
            result = shopify_client.execute_graphql(query, variables)
            
            if result.get('errors'):
                print(f"❌ GraphQL errors: {result['errors']}")
                break
            
            products_data = result.get('data', {}).get('products', {})
            edges = products_data.get('edges', [])
            
            for edge in edges:
                all_products.append(edge['node'])
            
            page_info = products_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
            
            print(f"   ✅ Page {page}: {len(edges)} products (total: {len(all_products)})")
            page += 1
            
            if page > 200:  # Safety limit
                print("⚠️  Reached page limit of 200")
                break
        
        print(f"\n📦 Total products found in Shopify: {len(all_products)}")
        
        if len(all_products) == 0:
            print("❌ No products found in Shopify!")
            return
        
        # Find or create category for imported products
        print("\n📁 Setting up categories...")
        
        # Use existing "Imported Products" category or create it
        imported_cat_result = supabase.client.table('categories')\
            .select('id')\
            .eq('name', 'Imported Products')\
            .execute()
        
        if imported_cat_result.data:
            category_id = imported_cat_result.data[0]['id']
            print(f"   Using existing 'Imported Products' category (ID: {category_id})")
        else:
            # Create the category
            cat_data = {
                'name': 'Imported Products',
                'slug': 'imported-products',
                'description': 'Products synced from Shopify',
                'level': 0,
                'path': 'imported-products',
                'is_active': True,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            cat_result = supabase.client.table('categories').insert(cat_data).execute()
            category_id = cat_result.data[0]['id']
            print(f"   Created 'Imported Products' category (ID: {category_id})")
        
        # Import products
        print(f"\n💾 Importing {len(all_products)} products...")
        
        imported_count = 0
        updated_count = 0
        error_count = 0
        
        for i, shopify_product in enumerate(all_products):
            try:
                if i % 100 == 0:
                    print(f"   Progress: {i}/{len(all_products)} ({i/len(all_products)*100:.1f}%)")
                
                # Extract Shopify product ID (remove gid prefix)
                shopify_id = shopify_product['id'].replace('gid://shopify/Product/', '')
                
                # Check if product already exists
                existing_result = supabase.client.table('products')\
                    .select('id')\
                    .eq('shopify_product_id', shopify_id)\
                    .execute()
                
                # Prepare product data
                product_data = {
                    'name': shopify_product.get('title', ''),
                    'description': shopify_product.get('description', ''),
                    'shopify_product_id': shopify_id,
                    'handle': shopify_product.get('handle', ''),
                    'product_type': shopify_product.get('productType', ''),
                    'brand': shopify_product.get('vendor', ''),
                    'tags': shopify_product.get('tags', []),
                    'status': shopify_product.get('status', 'DRAFT').lower(),
                    'category_id': category_id,
                    'shopify_sync_status': 'synced',
                    'shopify_synced_at': shopify_product.get('updatedAt', ''),
                    'created_at': shopify_product.get('createdAt', ''),
                    'updated_at': shopify_product.get('updatedAt', '')
                }
                
                # Add variant data if available
                variants = shopify_product.get('variants', {}).get('edges', [])
                if variants:
                    variant = variants[0]['node']
                    product_data.update({
                        'sku': variant.get('sku', ''),
                        'price': float(variant.get('price', 0)) if variant.get('price') else None,
                        'compare_at_price': float(variant.get('compareAtPrice', 0)) if variant.get('compareAtPrice') else None,
                        'inventory_quantity': int(variant.get('inventoryQuantity', 0)) if variant.get('inventoryQuantity') else 0,
                        'weight': float(variant.get('weight', 0)) if variant.get('weight') else None,
                        'weight_unit': variant.get('weightUnit', 'kg'),
                        'requires_shipping': variant.get('requiresShipping', True),
                        'taxable': variant.get('taxable', True)
                    })
                
                if existing_result.data:
                    # Update existing product
                    result = supabase.client.table('products')\
                        .update(product_data)\
                        .eq('id', existing_result.data[0]['id'])\
                        .execute()
                    if result.data:
                        updated_count += 1
                else:
                    # Insert new product
                    result = supabase.client.table('products').insert(product_data).execute()
                    if result.data:
                        imported_count += 1
                
            except Exception as e:
                error_count += 1
                if error_count <= 10:  # Only show first 10 errors
                    print(f"   ❌ Error with product {shopify_product.get('title', 'Unknown')}: {str(e)}")
        
        # Final results
        print(f"\n🎉 RECOVERY COMPLETE!")
        print(f"   📦 New products imported: {imported_count}")
        print(f"   🔄 Existing products updated: {updated_count}")
        print(f"   ❌ Errors: {error_count}")
        print(f"   📊 Total processed: {len(all_products)}")
        
        # Check final count
        final_result = supabase.client.table('products').select('id', count='exact').execute()
        final_count = final_result.count if hasattr(final_result, 'count') else 0
        
        print(f"\n📈 RESULTS:")
        print(f"   Before: {current_count} products")
        print(f"   After:  {final_count} products")
        print(f"   Recovered: {final_count - current_count} products")
        
        if final_count > current_count:
            print(f"\n✅ SUCCESS: Recovered {final_count - current_count} products from Shopify!")
        else:
            print(f"\n⚠️  WARNING: Product count didn't increase as expected")
        
    except Exception as e:
        print(f"❌ Error during recovery: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    recover_products()