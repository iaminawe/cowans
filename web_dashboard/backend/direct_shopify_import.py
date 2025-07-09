"""
Direct Shopify Import Script
Directly import 1000 products from Shopify using the backend services
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
from database import db_session_scope, db_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DirectShopifyImporter:
    """Direct Shopify product importer"""
    
    def __init__(self):
        # We'll create the repository with session when needed
        self.product_repo = None
        
        # Check if Shopify credentials are available
        self.shopify_url = os.getenv('SHOPIFY_SHOP_URL')
        self.shopify_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not self.shopify_url or not self.shopify_token:
            logger.error("Shopify credentials not found in environment variables")
            raise ValueError("Missing Shopify credentials")
        
        logger.info(f"Initialized with Shopify store: {self.shopify_url}")
    
    async def fetch_products_graphql(self, limit: int = 1000):
        """Fetch products using GraphQL (more efficient)"""
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
                'sku': f"IMPORT-{shopify_id}",  # Generate SKU from Shopify ID
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
                if variant_sku:
                    product_data['sku'] = variant_sku  # Use actual SKU if available
                
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
    
    async def import_products_to_db(self, products, batch_size=50):
        """Import products to database using batch processing"""
        logger.info(f"Importing {len(products)} products to database in batches of {batch_size}")
        
        imported_count = 0
        skipped_count = 0
        error_count = 0
        
        # Ensure we have a default category first (outside batch processing)
        default_category_id = None
        try:
            with db_session_scope() as session:
                from models import Category
                # Try to find existing category by slug first (most reliable)
                default_category = session.query(Category).filter_by(slug='imported-products').first()
                
                if not default_category:
                    # Also check by name as backup
                    default_category = session.query(Category).filter_by(name='Imported Products').first()
                
                if not default_category:
                    # Create new category only if none exists
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
                        # If creation fails, try to find it again (race condition)
                        session.rollback()
                        default_category = session.query(Category).filter_by(slug='imported-products').first()
                        if default_category:
                            default_category_id = default_category.id
                        else:
                            # Fall back to any category
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
                'imported': 0,
                'skipped': 0, 
                'errors': len(products),
                'total': len(products)
            }
        
        # Process in batches
        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(products) + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} products)")
            
            batch_imported = 0
            batch_skipped = 0
            batch_errors = 0
            
            # Process each product individually to avoid batch rollbacks
            for product_data in batch:
                try:
                    with db_session_scope() as session:
                        # Check if product already exists
                        from models import Product
                        existing_product = session.query(Product).filter_by(
                            shopify_id=product_data['shopify_id']
                        ).first()
                        
                        if existing_product:
                            logger.debug(f"Product {product_data['shopify_id']} already exists, skipping")
                            batch_skipped += 1
                            continue
                        
                        # Set category_id
                        product_data['category_id'] = default_category_id
                        
                        # Create new product directly
                        product = Product(**product_data)
                        session.add(product)
                        session.commit()
                        
                        batch_imported += 1
                        logger.debug(f"Imported product: {product.name}")
                        
                except Exception as e:
                    logger.error(f"Error importing individual product {product_data.get('name', 'unknown')}: {str(e)}")
                    batch_errors += 1
            
            # Update counters
            imported_count += batch_imported
            skipped_count += batch_skipped 
            error_count += batch_errors
            
            logger.info(f"Batch {batch_num} completed: {batch_imported} imported, {batch_skipped} skipped, {batch_errors} errors")
        
        logger.info(f"Import completed:")
        logger.info(f"  • Imported: {imported_count}")
        logger.info(f"  • Skipped: {skipped_count}")
        logger.info(f"  • Errors: {error_count}")
        
        return {
            'imported': imported_count,
            'skipped': skipped_count,
            'errors': error_count,
            'total': len(products)
        }
    
    async def run_import(self, limit=1000):
        """Run the complete import process"""
        logger.info(f"Starting Shopify import of {limit} products")
        start_time = time.time()
        
        # Initialize database
        try:
            from database import init_database
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
            
            # Step 2: Import to database
            logger.info("Step 2: Importing products to database...")
            import_stats = await self.import_products_to_db(products)
            
            # Calculate final statistics
            end_time = time.time()
            duration = end_time - start_time
            
            final_stats = {
                **import_stats,
                'duration_seconds': duration,
                'products_per_second': len(products) / duration if duration > 0 else 0,
                'shopify_fetch_count': len(products),
                'success_rate': import_stats['imported'] / len(products) if products else 0
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
    print("🚀 Direct Shopify Import")
    print("Importing 1000 products using direct API calls")
    print("=" * 60)
    
    try:
        # Initialize importer
        importer = DirectShopifyImporter()
        
        # Run import
        print("📡 Starting import from Shopify...")
        results = await importer.run_import(limit=1000)
        
        if 'error' in results:
            print(f"❌ Import failed: {results['error']}")
        else:
            print(f"\n✅ Import completed successfully!")
            print(f"📊 Results:")
            print(f"   • Products fetched from Shopify: {results['shopify_fetch_count']}")
            print(f"   • Products imported to database: {results['imported']}")
            print(f"   • Products skipped (already exist): {results['skipped']}")
            print(f"   • Import errors: {results['errors']}")
            print(f"   • Total duration: {results['duration_seconds']:.2f}s")
            print(f"   • Import rate: {results['products_per_second']:.1f} products/second")
            print(f"   • Success rate: {results['success_rate']:.1%}")
            
            if results['imported'] > 0:
                print(f"\n🎉 Successfully imported {results['imported']} new products!")
            else:
                print(f"\n💡 No new products imported (may already exist in database)")
        
    except Exception as e:
        print(f"❌ Failed to initialize importer: {str(e)}")
        print(f"💡 Make sure Shopify credentials are set in .env file")

if __name__ == "__main__":
    asyncio.run(main())