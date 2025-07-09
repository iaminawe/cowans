"""
Shopify Import Using Handle as Primary Key
Fast bulk import using Shopify handle as the unique identifier
"""

import os
import sys
import asyncio
import time
import json
import logging
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db_session_scope, init_database
from models import Product, Category

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ShopifyHandleImporter:
    """Fast Shopify product importer using handle as primary key"""
    
    def __init__(self):
        # Check if Shopify credentials are available
        self.shopify_url = os.getenv('SHOPIFY_SHOP_URL')
        self.shopify_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not self.shopify_url or not self.shopify_token:
            logger.error("Shopify credentials not found in environment variables")
            raise ValueError("Missing Shopify credentials")
        
        logger.info(f"Initialized with Shopify store: {self.shopify_url}")
    
    async def fetch_products_graphql(self, limit: int = 1000):
        """Fetch products using GraphQL"""
        import requests
        
        graphql_url = f"https://{self.shopify_url}/admin/api/2023-10/graphql.json"
        
        # GraphQL query to fetch products with all needed fields
        query = f"""
        query {{
          products(first: {min(limit, 250)}) {{
            edges {{
              node {{
                id
                title
                descriptionHtml
                vendor
                productType
                handle
                status
                tags
                createdAt
                updatedAt
                variants(first: 1) {{
                  edges {{
                    node {{
                      id
                      title
                      price
                      sku
                      inventoryQuantity
                      weight
                      weightUnit
                    }}
                  }}
                }}
                images(first: 1) {{
                  edges {{
                    node {{
                      id
                      url
                      altText
                    }}
                  }}
                }}
              }}
            }}
            pageInfo {{
              hasNextPage
              endCursor
            }}
          }}
        }}
        """
        
        headers = {
            'X-Shopify-Access-Token': self.shopify_token,
            'Content-Type': 'application/json'
        }
        
        all_products = []
        cursor = None
        
        while len(all_products) < limit:
            # Modify query for pagination if we have a cursor
            if cursor:
                paginated_query = query.replace(
                    f"products(first: {min(limit, 250)})",
                    f"products(first: {min(limit - len(all_products), 250)}, after: \"{cursor}\")"
                )
            else:
                paginated_query = query
            
            try:
                response = requests.post(
                    graphql_url,
                    json={'query': paginated_query},
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'errors' in data:
                        logger.error(f"GraphQL errors: {data['errors']}")
                        break
                    
                    if 'data' in data and 'products' in data['data']:
                        products = data['data']['products']
                        
                        # Process products
                        for edge in products['edges']:
                            product = self._transform_shopify_product(edge['node'])
                            if product:
                                all_products.append(product)
                        
                        # Check for more pages
                        page_info = products.get('pageInfo', {})
                        if page_info.get('hasNextPage') and len(all_products) < limit:
                            cursor = page_info.get('endCursor')
                        else:
                            break
                    else:
                        logger.error(f"Unexpected response structure: {data}")
                        break
                        
                else:
                    logger.error(f"HTTP error {response.status_code}: {response.text}")
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching products: {str(e)}")
                break
        
        logger.info(f"Fetched {len(all_products)} products from Shopify")
        return all_products
    
    def _transform_shopify_product(self, shopify_product):
        """Transform Shopify GraphQL product to our database format"""
        try:
            # Extract numeric ID from GraphQL ID
            shopify_id = shopify_product['id'].split('/')[-1]
            handle = shopify_product.get('handle', '')
            
            if not handle:
                logger.warning(f"Product {shopify_id} has no handle, skipping")
                return None
            
            # Map status to correct enum value
            status_map = {
                'ACTIVE': 'active',
                'DRAFT': 'draft', 
                'ARCHIVED': 'archived'
            }
            status = status_map.get(shopify_product.get('status', 'ACTIVE'), 'draft')
            
            product_data = {
                'shopify_id': shopify_id,
                'shopify_product_id': shopify_id,
                'shopify_handle': handle,
                'name': shopify_product.get('title', ''),
                'description': shopify_product.get('descriptionHtml', ''),
                'brand': shopify_product.get('vendor', ''),
                'status': status,
                'custom_attributes': {
                    'product_type': shopify_product.get('productType', ''),
                    'tags': ', '.join(shopify_product.get('tags', [])),
                    'shopify_created_at': shopify_product.get('createdAt'),
                    'shopify_updated_at': shopify_product.get('updatedAt'),
                    'handle': handle
                },
                'shopify_sync_status': 'synced',
                'shopify_synced_at': datetime.now()
            }
            
            # Extract first variant info
            variants = shopify_product.get('variants', {}).get('edges', [])
            if variants:
                first_variant = variants[0]['node']
                variant_sku = first_variant.get('sku', '')
                
                # Use SKU if available, otherwise generate one from handle
                if variant_sku:
                    product_data['sku'] = variant_sku
                else:
                    product_data['sku'] = f"SHOPIFY-{handle.upper()}"
                
                # Handle price safely
                try:
                    price_val = float(first_variant.get('price', 0))
                except (ValueError, TypeError):
                    price_val = 0.0
                
                # Handle weight safely  
                try:
                    weight_val = float(first_variant.get('weight', 0))
                except (ValueError, TypeError):
                    weight_val = 0.0
                
                product_data.update({
                    'price': price_val,
                    'inventory_quantity': first_variant.get('inventoryQuantity', 0) or 0,
                    'weight': weight_val,
                    'weight_unit': first_variant.get('weightUnit', 'kg'),
                    'shopify_variant_id': first_variant['id'].split('/')[-1]
                })
            else:
                # Set default values if no variants
                product_data.update({
                    'sku': f"SHOPIFY-{handle.upper()}",
                    'price': 0.0,
                    'inventory_quantity': 0,
                    'weight': 0.0,
                    'weight_unit': 'kg'
                })
            
            # Extract first image
            images = shopify_product.get('images', {}).get('edges', [])
            if images:
                first_image = images[0]['node']
                product_data['featured_image_url'] = first_image.get('url', '')
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error transforming product {shopify_product.get('id', 'unknown')}: {str(e)}")
            return None
    
    async def bulk_import_by_handle(self, products):
        """Bulk import using handle as primary key for deduplication"""
        logger.info(f"Bulk importing {len(products)} products using handle as key")
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        # Get default category
        default_category_id = None
        try:
            with db_session_scope() as session:
                default_category = session.query(Category).filter_by(slug='imported-products').first()
                
                if not default_category:
                    default_category = Category(
                        name='Imported Products',
                        slug='imported-products',
                        description='Products imported from Shopify',
                        level=0,
                        is_active=True
                    )
                    session.add(default_category)
                    session.commit()
                    
                default_category_id = default_category.id
                logger.info(f"Using category ID: {default_category_id}")
                    
        except Exception as e:
            logger.error(f"Failed to setup default category: {str(e)}")
            return {'created': 0, 'updated': 0, 'errors': len(products)}
        
        # Create a mapping of existing products by handle
        logger.info("Building existing products index...")
        existing_by_handle = {}
        try:
            with db_session_scope() as session:
                existing_products = session.query(Product).filter(
                    Product.shopify_handle.isnot(None)
                ).all()
                
                for product in existing_products:
                    if product.shopify_handle:
                        existing_by_handle[product.shopify_handle] = product.id
                        
                logger.info(f"Found {len(existing_by_handle)} existing products with handles")
                
        except Exception as e:
            logger.error(f"Failed to build existing products index: {str(e)}")
            return {'created': 0, 'updated': 0, 'errors': len(products)}
        
        # Process products in batches
        batch_size = 100
        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(products) + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} products)")
            
            try:
                with db_session_scope() as session:
                    batch_created = 0
                    batch_updated = 0
                    batch_errors = 0
                    
                    for product_data in batch:
                        try:
                            handle = product_data.get('shopify_handle')
                            if not handle:
                                batch_errors += 1
                                continue
                                
                            product_data['category_id'] = default_category_id
                            
                            # Check if product exists by handle
                            if handle in existing_by_handle:
                                # Update existing product
                                existing_id = existing_by_handle[handle]
                                existing_product = session.query(Product).get(existing_id)
                                
                                if existing_product:
                                    # Update with Shopify data
                                    for key, value in product_data.items():
                                        if hasattr(existing_product, key) and key != 'id':
                                            # Don't overwrite existing name/description if they exist
                                            if key in ['name', 'description'] and getattr(existing_product, key):
                                                continue
                                            setattr(existing_product, key, value)
                                    
                                    batch_updated += 1
                                else:
                                    batch_errors += 1
                            else:
                                # Create new product
                                product = Product(**product_data)
                                session.add(product)
                                batch_created += 1
                                
                                # Add to our index for next batches
                                existing_by_handle[handle] = "new"
                                
                        except Exception as e:
                            logger.error(f"Error processing product {product_data.get('name', 'unknown')}: {str(e)}")
                            batch_errors += 1
                    
                    # Commit the batch
                    session.commit()
                    
                    created_count += batch_created
                    updated_count += batch_updated
                    error_count += batch_errors
                    
                    logger.info(f"Batch {batch_num} completed: {batch_created} created, {batch_updated} updated, {batch_errors} errors")
                    
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {str(e)}")
                error_count += len(batch)
        
        logger.info(f"Bulk import completed:")
        logger.info(f"  • Created: {created_count}")
        logger.info(f"  • Updated: {updated_count}") 
        logger.info(f"  • Errors: {error_count}")
        
        return {
            'created': created_count,
            'updated': updated_count,
            'errors': error_count,
            'total': len(products)
        }
    
    async def run_import(self, limit=1000):
        """Run the complete import process"""
        logger.info(f"Starting Shopify handle-based import of {limit} products")
        start_time = time.time()
        
        # Initialize database
        try:
            init_database()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            return {"error": f"Database initialization failed: {str(e)}"}
        
        try:
            # Step 1: Fetch products from Shopify
            logger.info("Step 1: Fetching products from Shopify...")
            products = await self.fetch_products_graphql(limit)
            
            if not products:
                logger.error("No products fetched from Shopify")
                return {"error": "No products fetched"}
            
            # Step 2: Bulk import using handles
            logger.info("Step 2: Bulk importing products by handle...")
            import_stats = await self.bulk_import_by_handle(products)
            
            # Calculate final statistics
            end_time = time.time()
            duration = end_time - start_time
            
            final_stats = {
                **import_stats,
                'duration_seconds': duration,
                'products_per_second': len(products) / duration if duration > 0 else 0,
                'shopify_fetch_count': len(products),
                'success_rate': (import_stats['created'] + import_stats['updated']) / len(products) if products else 0
            }
            
            logger.info(f"Import completed in {duration:.2f}s")
            logger.info(f"Rate: {final_stats['products_per_second']:.1f} products/second")
            logger.info(f"Success rate: {final_stats['success_rate']:.1%}")
            
            return final_stats
            
        except Exception as e:
            logger.error(f"Import failed: {str(e)}")
            return {"error": str(e)}

async def main():
    """Main import function"""
    print("🚀 Shopify Handle-Based Import")
    print("Fast bulk import using Shopify handle as primary key")
    print("=" * 60)
    
    try:
        # Initialize importer
        importer = ShopifyHandleImporter()
        
        # Run import
        print("📡 Starting import from Shopify...")
        results = await importer.run_import(limit=1000)
        
        if 'error' in results:
            print(f"❌ Import failed: {results['error']}")
        else:
            print(f"\n✅ Import completed successfully!")
            print(f"📊 Results:")
            print(f"   • Products fetched from Shopify: {results['shopify_fetch_count']}")
            print(f"   • Products created: {results['created']}")
            print(f"   • Products updated: {results['updated']}")
            print(f"   • Import errors: {results['errors']}")
            print(f"   • Total duration: {results['duration_seconds']:.2f}s")
            print(f"   • Processing rate: {results['products_per_second']:.1f} products/second")
            print(f"   • Success rate: {results['success_rate']:.1%}")
            
            if results['created'] > 0 or results['updated'] > 0:
                print(f"\n🎉 Successfully processed {results['created'] + results['updated']} products!")
            else:
                print(f"\n💡 No products were created or updated")
        
    except Exception as e:
        print(f"❌ Failed to initialize importer: {str(e)}")
        print(f"💡 Make sure Shopify credentials are set in .env file")

if __name__ == "__main__":
    asyncio.run(main())