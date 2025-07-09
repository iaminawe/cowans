"""
Direct Database Check
Check products count directly in PostgreSQL database
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db_session_scope, init_database
from models import Product, Category

def check_products():
    """Check products in database directly"""
    try:
        with db_session_scope() as session:
            # Count total products
            total_products = session.query(Product).count()
            
            # Count by source
            shopify_products = session.query(Product).filter(
                Product.shopify_id.isnot(None)
            ).count()
            
            # Get some sample products
            sample_products = session.query(Product).order_by(Product.id.desc()).limit(5).all()
            
            # Check categories
            total_categories = session.query(Category).count()
            
            print(f"📦 Database Status:")
            print(f"   • Total products: {total_products}")
            print(f"   • Products with Shopify ID: {shopify_products}")
            print(f"   • Total categories: {total_categories}")
            
            if sample_products:
                print(f"\n📋 Latest products:")
                for i, product in enumerate(sample_products, 1):
                    print(f"   {i}. {product.name} (SKU: {product.sku}, Shopify ID: {product.shopify_id})")
            else:
                print(f"\n📋 No products found in database")
                
            return {
                'total_products': total_products,
                'shopify_products': shopify_products,
                'total_categories': total_categories,
                'sample_products': len(sample_products)
            }
            
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        return None

def fix_sequences():
    """Fix PostgreSQL sequences for auto-increment IDs"""
    try:
        from sqlalchemy import text
        with db_session_scope() as session:
            # Fix products sequence
            result = session.execute(text("SELECT setval('products_id_seq', (SELECT COALESCE(MAX(id), 1) FROM products), true)"))
            print(f"✅ Fixed products sequence")
            
            # Fix categories sequence  
            result = session.execute(text("SELECT setval('categories_id_seq', (SELECT COALESCE(MAX(id), 1) FROM categories), true)"))
            print(f"✅ Fixed categories sequence")
            
            session.commit()
            return True
            
    except Exception as e:
        print(f"❌ Error fixing sequences: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔍 Direct Database Check")
    print("=" * 50)
    
    # Initialize database first
    try:
        init_database()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization failed: {str(e)}")
        exit(1)
    
    # Check current status
    status = check_products()
    
    if status and status['total_products'] > 0:
        print(f"\n🎉 Found {status['total_products']} products in database!")
    else:
        print(f"\n💡 Database appears to be empty or has issues")
        
    # Fix sequences
    print(f"\n🔧 Fixing database sequences...")
    if fix_sequences():
        print(f"✅ Sequences fixed successfully")
    else:
        print(f"❌ Failed to fix sequences")