"""
Shopify Import with Update Strategy
Import/update products from Shopify, handling SKU conflicts by updating existing products
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

# Import backend services
from services.shopify_product_sync_service import ShopifyProductSyncService
from repositories.product_repository import ProductRepository
from database import db_session_scope, db_manager, init_database

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ShopifyImportUpdater:
    """Shopify product importer with update capability"""
    
    def __init__(self):
        # Check if Shopify credentials are available
        self.shopify_url = os.getenv('SHOPIFY_SHOP_URL')
        self.shopify_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not self.shopify_url or not self.shopify_token:
            logger.error("Shopify credentials not found in environment variables")
            raise ValueError("Missing Shopify credentials")
        
        logger.info(f"Initialized with Shopify store: {self.shopify_url}")
    
    async def fetch_products_graphql(self, limit: int = 1000):
        """Fetch products using GraphQL (same as before)"""
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
                variants(first: 10) {{
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
                images(first: 5) {{
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
            
            # Map status to correct enum value
            status_map = {
                'ACTIVE': 'active',
                'DRAFT': 'draft', 
                'ARCHIVED': 'archived'
            }
            status = status_map.get(shopify_product.get('status', 'ACTIVE'), 'draft')
            
            product_data = {
                'shopify_id': shopify_id,
                'shopify_product_id': shopify_id,  # Add this field too
                'name': shopify_product.get('title', ''),
                'description': shopify_product.get('descriptionHtml', ''),
                'brand': shopify_product.get('vendor', ''),
                'status': status,
                'shopify_handle': shopify_product.get('handle', ''),
                'custom_attributes': {
                    'product_type': shopify_product.get('productType', ''),
                    'tags': ', '.join(shopify_product.get('tags', [])),
                    'shopify_created_at': shopify_product.get('createdAt'),
                    'shopify_updated_at': shopify_product.get('updatedAt'),
                    'handle': shopify_product.get('handle', '')
                }
            }
            
            # Extract first variant info (basic implementation)
            variants = shopify_product.get('variants', {}).get('edges', [])
            if variants:
                first_variant = variants[0]['node']
                variant_sku = first_variant.get('sku', '')
                
                # Use SKU if available, otherwise generate one
                if variant_sku:
                    product_data['sku'] = variant_sku
                else:
                    product_data['sku'] = f"SHOPIFY-{shopify_id}"
                
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
                # Set default values if no variants - price is required
                product_data.update({
                    'sku': f"SHOPIFY-{shopify_id}",
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
    
    async def import_or_update_products(self, products, batch_size=50):
        """Import new products or update existing ones"""
        logger.info(f"Processing {len(products)} products from Shopify in batches of {batch_size}")
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        # Ensure we have a default category first
        default_category_id = None
        try:
            with db_session_scope() as session:
                from models import Category
                default_category = session.query(Category).filter_by(slug='imported-products').first()
                
                if not default_category:
                    default_category = session.query(Category).filter_by(name='Imported Products').first()
                
                if not default_category:
                    try:
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
                    except Exception as create_error:
                        session.rollback()
                        default_category = session.query(Category).filter_by(slug='imported-products').first()
                        if default_category:
                            default_category_id = default_category.id
                        else:
                            any_category = session.query(Category).filter_by(is_active=True).first()
                            if any_category:
                                default_category_id = any_category.id
                                logger.warning(f"Using existing category '{any_category.name}' as fallback")
                            else:
                                raise create_error
                else:
                    default_category_id = default_category.id
                    
            if default_category_id:
                logger.info(f"Using default category ID: {default_category_id}")
            else:
                raise ValueError("Could not establish default category")
                    
        except Exception as e:
            logger.error(f"Failed to create default category: {str(e)}")
            return {
                'created': 0,
                'updated': 0,
                'skipped': 0, 
                'errors': len(products),
                'total': len(products)
            }
        
        # Process each product individually
        for i, product_data in enumerate(products, 1):
            if i % 50 == 0:
                logger.info(f"Processing product {i}/{len(products)}")
                
            try:
                with db_session_scope() as session:
                    from models import Product
                    
                    # Check if product exists by Shopify ID first
                    existing_product = session.query(Product).filter_by(
                        shopify_id=product_data['shopify_id']
                    ).first()
                    
                    if existing_product:
                        # Update existing product with Shopify data
                        for key, value in product_data.items():
                            if hasattr(existing_product, key) and key != 'id':
                                setattr(existing_product, key, value)
                        
                        # Mark as Shopify synced
                        existing_product.shopify_sync_status = 'synced'
                        existing_product.shopify_synced_at = datetime.utcnow()
                        
                        session.commit()
                        updated_count += 1
                        logger.debug(f"Updated existing product: {existing_product.name}")
                        continue
                    
                    # Check if product exists by SKU
                    existing_by_sku = session.query(Product).filter_by(
                        sku=product_data['sku']
                    ).first()
                    
                    if existing_by_sku:
                        # Update existing product and add Shopify data
                        for key, value in product_data.items():
                            if hasattr(existing_by_sku, key) and key != 'id':
                                # Don't overwrite existing name, description if they exist
                                if key in ['name', 'description'] and getattr(existing_by_sku, key):
                                    continue
                                setattr(existing_by_sku, key, value)
                        
                        # Mark as Shopify synced
                        existing_by_sku.shopify_sync_status = 'synced'
                        existing_by_sku.shopify_synced_at = datetime.utcnow()
                        
                        session.commit()
                        updated_count += 1
                        logger.debug(f"Updated product by SKU: {existing_by_sku.name}")
                        continue
                    
                    # Create new product
                    product_data['category_id'] = default_category_id
                    product_data['shopify_sync_status'] = 'synced'
                    product_data['shopify_synced_at'] = datetime.utcnow()
                    
                    product = Product(**product_data)
                    session.add(product)
                    session.commit()
                    
                    created_count += 1
                    logger.debug(f"Created new product: {product.name}")
                    
            except Exception as e:
                logger.error(f"Error processing product {product_data.get('name', 'unknown')}: {str(e)}")
                error_count += 1
        
        logger.info(f"Import/update completed:")
        logger.info(f"  • Created: {created_count}")
        logger.info(f"  • Updated: {updated_count}")
        logger.info(f"  • Skipped: {skipped_count}")
        logger.info(f"  • Errors: {error_count}")
        
        return {
            'created': created_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'errors': error_count,
            'total': len(products)
        }
    
    async def run_import(self, limit=1000):
        """Run the complete import process"""
        logger.info(f"Starting Shopify import/update of {limit} products")
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
            
            # Step 2: Import/update to database
            logger.info("Step 2: Importing/updating products in database...")
            import_stats = await self.import_or_update_products(products)
            
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
    print("🚀 Shopify Import/Update Tool")
    print("Importing 1000 products with update strategy")
    print("=" * 60)
    
    try:
        # Initialize importer
        importer = ShopifyImportUpdater()
        
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
            print(f"   • Products skipped: {results['skipped']}")
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