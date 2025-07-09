import json
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from services.supabase_auth import supabase_jwt_required, get_current_user_id
from database import db_session_scope as db_session
from models import Product, Category
from repositories import ProductRepository
from sqlalchemy import func
from datetime import datetime
import logging
import os
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.shopify.shopify_base import ShopifyAPIBase, CREATE_PRODUCT_MUTATION
import traceback

# Create blueprint
shopify_sync_bp = Blueprint('shopify_sync', __name__, url_prefix='/api/shopify')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_shopify_client():
    """Get configured Shopify API client."""
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        raise ValueError("Shopify credentials not configured")
    
    return ShopifyAPIBase(shop_url, access_token, debug=True)

@shopify_sync_bp.route('/products', methods=['POST'])
@supabase_jwt_required
def create_product():
    """Create a new product in Shopify and local database."""
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['title', 'description', 'vendor', 'productType']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Get Shopify client
        try:
            shopify_client = get_shopify_client()
        except ValueError as e:
            return jsonify({'error': str(e)}), 500
        
        # Prepare product data for Shopify GraphQL API
        product_input = {
            'title': data['title'],
            'description': data['description'],
            'vendor': data['vendor'],
            'productType': data['productType'],
            'status': data.get('status', 'DRAFT'),
            'tags': data.get('tags', []),
            'handle': data.get('handle', ''),
            'seo': {
                'title': data.get('seoTitle', ''),
                'description': data.get('seoDescription', '')
            }
        }
        
        # Add variants if provided
        variants = []
        if data.get('price') or data.get('sku'):
            variant = {}
            if data.get('price'):
                variant['price'] = str(data['price'])
            if data.get('compareAtPrice'):
                variant['compareAtPrice'] = str(data['compareAtPrice'])
            if data.get('sku'):
                variant['sku'] = data['sku']
            if data.get('barcode'):
                variant['barcode'] = data['barcode']
            if data.get('inventoryQuantity'):
                variant['inventoryQuantities'] = [{
                    'availableQuantity': int(data['inventoryQuantity']),
                    'locationId': 'gid://shopify/Location/1'  # Default location
                }]
            if data.get('weight'):
                variant['weight'] = float(data['weight'])
                variant['weightUnit'] = data.get('weightUnit', 'POUNDS')
            if data.get('inventoryPolicy'):
                variant['inventoryPolicy'] = data['inventoryPolicy']
            if data.get('inventoryTracked') is not None:
                variant['inventoryManagement'] = 'SHOPIFY' if data['inventoryTracked'] else 'NOT_MANAGED'
            if data.get('requiresShipping') is not None:
                variant['requiresShipping'] = data['requiresShipping']
            if data.get('taxable') is not None:
                variant['taxable'] = data['taxable']
            
            variants.append(variant)
        
        if variants:
            product_input['variants'] = variants
        
        # Create product in Shopify
        variables = {'input': product_input}
        
        logger.info(f"Creating product in Shopify with data: {json.dumps(variables, indent=2)}")
        
        result = shopify_client.execute_graphql(CREATE_PRODUCT_MUTATION, variables)
        
        if 'errors' in result:
            logger.error(f"Shopify GraphQL errors: {result['errors']}")
            return jsonify({'error': 'Shopify API error', 'details': result['errors']}), 500
        
        # Check for user errors
        product_create = result.get('data', {}).get('productCreate', {})
        if product_create.get('userErrors'):
            logger.error(f"Shopify user errors: {product_create['userErrors']}")
            return jsonify({'error': 'Product creation failed', 'details': product_create['userErrors']}), 400
        
        # Get created product data
        created_product = product_create.get('product')
        if not created_product:
            return jsonify({'error': 'Product creation failed - no product returned'}), 500
        
        shopify_product_id = created_product['id']
        shopify_handle = created_product['handle']
        
        logger.info(f"Product created in Shopify: {shopify_product_id}")
        
        # Store product in local database
        with db_session() as session:
            # Find or create category
            category = session.query(Category).filter_by(name='Uncategorized').first()
            if not category:
                category = Category(
                    name='Uncategorized',
                    description='Default category for new products'
                )
                session.add(category)
                session.flush()
            
            # Create local product record
            local_product = Product(
                name=data['title'],
                description=data['description'],
                brand=data['vendor'],
                sku=data.get('sku', ''),
                price=float(data['price']) if data.get('price') else None,
                compare_at_price=float(data['compareAtPrice']) if data.get('compareAtPrice') else None,
                inventory_quantity=int(data.get('inventoryQuantity', 0)),
                weight=float(data['weight']) if data.get('weight') else None,
                category_id=category.id,
                shopify_product_id=shopify_product_id,
                shopify_sync_status='synced',
                shopify_synced_at=datetime.utcnow(),
                custom_attributes={
                    'product_type': data['productType'],
                    'tags': data.get('tags', []),
                    'handle': shopify_handle,
                    'status': data.get('status', 'DRAFT'),
                    'seo_title': data.get('seoTitle', ''),
                    'seo_description': data.get('seoDescription', ''),
                    'weight_unit': data.get('weightUnit', 'POUNDS'),
                    'requires_shipping': data.get('requiresShipping', True),
                    'taxable': data.get('taxable', True),
                    'inventory_policy': data.get('inventoryPolicy', 'DENY'),
                    'inventory_tracked': data.get('inventoryTracked', True)
                }
            )
            
            session.add(local_product)
            session.commit()
            
            local_product_id = local_product.id
        
        logger.info(f"Product stored locally with ID: {local_product_id}")
        
        return jsonify({
            'success': True,
            'shopify_product_id': shopify_product_id,
            'local_product_id': local_product_id,
            'handle': shopify_handle,
            'message': 'Product created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@shopify_sync_bp.route('/products/types', methods=['GET'])
@supabase_jwt_required
def get_product_types():
    """Get available product types for dropdown selection."""
    try:
        with db_session() as session:
            # Get product types from existing products' custom_attributes
            products = session.query(Product).filter(
                Product.custom_attributes.isnot(None)
            ).all()
            
            product_types = set()
            
            # Extract product types from custom_attributes
            for product in products:
                if product.custom_attributes and 'product_type' in product.custom_attributes:
                    product_type = product.custom_attributes['product_type']
                    if product_type:
                        product_types.add(product_type)
            
            # Also get categories as potential product types
            categories = session.query(Category).all()
            for category in categories:
                if category.name and category.name != 'Uncategorized':
                    product_types.add(category.name)
            
            # Add some common product types if database is empty
            if not product_types:
                product_types = {
                    'Office Supplies', 'Electronics', 'Furniture', 'Stationery',
                    'Computers', 'Accessories', 'Books', 'Art Supplies'
                }
            
            return jsonify({
                'success': True,
                'product_types': sorted(list(product_types))
            })
            
    except Exception as e:
        logger.error(f"Error getting product types: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@shopify_sync_bp.route('/products/vendors', methods=['GET'])
@supabase_jwt_required
def get_vendors():
    """Get available vendors for dropdown selection."""
    try:
        with db_session() as session:
            # Get unique vendors from existing products
            vendors = session.query(Product.brand).distinct().filter(
                Product.brand.isnot(None),
                Product.brand != ''
            ).all()
            
            vendor_list = [vendor[0] for vendor in vendors if vendor[0]]
            
            # Add some common vendors if database is empty
            if not vendor_list:
                vendor_list = [
                    'Generic', 'House Brand', 'Private Label', 'Manufacturer Direct'
                ]
            
            return jsonify({
                'success': True,
                'vendors': sorted(vendor_list)
            })
            
    except Exception as e:
        logger.error(f"Error getting vendors: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# Add other existing endpoints...
@shopify_sync_bp.route('/test-connection', methods=['GET'])
@supabase_jwt_required
def test_shopify_connection():
    """Test Shopify API connection."""
    try:
        shopify_client = get_shopify_client()
        shopify_client.test_auth()
        
        # Get shop info
        shop_query = """
        query {
          shop {
            name
            email
            domain
            currencyCode
            plan {
              displayName
            }
          }
        }
        """
        
        result = shopify_client.execute_graphql(shop_query, {})
        shop_data = result.get('data', {}).get('shop', {})
        
        return jsonify({
            'connected': True,
            'shop': {
                'name': shop_data.get('name'),
                'email': shop_data.get('email'),
                'domain': shop_data.get('domain'),
                'currency': shop_data.get('currencyCode'),
                'plan': shop_data.get('plan', {}).get('displayName')
            }
        })
        
    except Exception as e:
        logger.error(f"Shopify connection test failed: {str(e)}")
        return jsonify({
            'connected': False,
            'error': str(e)
        }), 500


# Missing Shopify Endpoints
@shopify_sync_bp.route('/approved-products', methods=['GET'])
@supabase_jwt_required
def get_approved_products():
    """Get products that have been approved for sync."""
    try:
        with db_session() as session:
            # Get query parameters
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 50))
            status = request.args.get('status', 'approved')
            
            # Build query for approved products
            # In a real system, this would filter by approval status
            query = session.query(Product).filter(
                Product.status == 'active'
            )
            
            # Add status filter if provided
            if status == 'approved':
                query = query.filter(Product.shopify_product_id.isnot(None))
            elif status == 'pending':
                query = query.filter(Product.shopify_product_id.is_(None))
            
            # Order by updated date
            query = query.order_by(Product.updated_at.desc())
            
            # Paginate
            total = query.count()
            products = query.offset((page - 1) * per_page).limit(per_page).all()
            
            # Format response
            items = []
            for product in products:
                items.append({
                    'id': product.id,
                    'sku': product.sku,
                    'name': product.name,
                    'description': product.description,
                    'price': product.price,
                    'brand': product.brand,
                    'category': product.category.name if product.category else None,
                    'inventory_quantity': product.inventory_quantity,
                    'shopify_product_id': product.shopify_product_id,
                    'status': product.status,
                    'sync_status': 'synced' if product.shopify_product_id else 'pending',
                    'updated_at': product.updated_at.isoformat() if product.updated_at else None
                })
            
            return jsonify({
                'success': True,
                'products': items,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'total_pages': (total + per_page - 1) // per_page
                }
            })
            
    except Exception as e:
        logger.error(f"Error getting approved products: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@shopify_sync_bp.route('/collections', methods=['GET'])
@supabase_jwt_required
def get_collections():
    """Get Shopify collections."""
    try:
        # Try to get Shopify client
        try:
            shopify_client = get_shopify_client()
        except ValueError as e:
            logger.warning(f"Shopify not configured: {e}")
            # Return empty collections with 200 OK status if Shopify is not configured
            return jsonify({
                'success': True,
                'collections': [],
                'total': 0,
                'message': 'Shopify integration not configured'
            }), 200  # Changed from implicit 200 to explicit
        
        # GraphQL query to get collections
        collections_query = """
        query GetCollections($first: Int!) {
          collections(first: $first) {
            edges {
              node {
                id
                handle
                title
                description
                image {
                  url
                  altText
                }
                productsCount
                updatedAt
                sortOrder
                templateSuffix
                seo {
                  title
                  description
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
        
        # Get collections from Shopify
        variables = {'first': 50}
        result = shopify_client.execute_graphql(collections_query, variables)
        
        if result.get('errors'):
            logger.error(f"Shopify GraphQL errors: {result['errors']}")
            # Return empty array instead of 500 error
            return jsonify({
                'success': True,
                'error': 'Failed to fetch collections from Shopify',
                'collections': [],
                'total': 0,
                'message': 'Unable to fetch collections from Shopify'
            }), 200
        
        collections_data = result.get('data', {}).get('collections', {}).get('edges', [])
        
        # Format collections
        collections = []
        for edge in collections_data:
            collection = edge['node']
            collections.append({
                'id': collection['id'],
                'handle': collection['handle'],
                'title': collection['title'],
                'description': collection.get('description', ''),
                'image': {
                    'url': collection.get('image', {}).get('url'),
                    'alt': collection.get('image', {}).get('altText')
                } if collection.get('image') else None,
                'products_count': collection.get('productsCount', 0),
                'updated_at': collection.get('updatedAt'),
                'sort_order': collection.get('sortOrder'),
                'template_suffix': collection.get('templateSuffix'),
                'seo': {
                    'title': collection.get('seo', {}).get('title', ''),
                    'description': collection.get('seo', {}).get('description', '')
                }
            })
        
        return jsonify({
            'success': True,
            'collections': collections,
            'total': len(collections)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting collections: {str(e)}")
        logger.error(traceback.format_exc())
        # Return empty collections instead of 500 error
        return jsonify({
            'success': True,
            'error': 'Internal server error',
            'collections': [],
            'total': 0,
            'message': 'Unable to fetch collections'
        }), 200


@shopify_sync_bp.route('/product-types', methods=['GET'])
@supabase_jwt_required
def get_shopify_product_types():
    """Get product types from Shopify."""
    try:
        shopify_client = get_shopify_client()
        
        # GraphQL query to get product types
        product_types_query = """
        query GetProductTypes($first: Int!) {
          products(first: $first) {
            edges {
              node {
                productType
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """
        
        # Get product types from Shopify
        variables = {'first': 250}
        result = shopify_client.execute_graphql(product_types_query, variables)
        
        if result.get('errors'):
            return jsonify({'error': 'Failed to fetch product types from Shopify'}), 500
        
        products_data = result.get('data', {}).get('products', {}).get('edges', [])
        
        # Extract unique product types
        product_types = set()
        for edge in products_data:
            product_type = edge['node'].get('productType')
            if product_type and product_type.strip():
                product_types.add(product_type.strip())
        
        # Also get types from local database
        with db_session() as session:
            local_types = session.query(Product.brand).distinct().filter(
                Product.brand.isnot(None),
                Product.brand != ''
            ).all()
            
            for type_row in local_types:
                if type_row[0]:
                    product_types.add(type_row[0])
        
        return jsonify({
            'success': True,
            'product_types': sorted(list(product_types))
        })
        
    except Exception as e:
        logger.error(f"Error getting product types: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500