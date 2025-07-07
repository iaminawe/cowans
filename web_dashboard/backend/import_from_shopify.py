#!/usr/bin/env python3
import os
import sys
sys.path.append('/Users/iaminawe/Sites/cowans/web_dashboard/backend')

from database import get_db_session
from models import Product
from services.shopify_product_sync_service import ShopifyProductSyncService
from sqlalchemy import text

def main():
    # Initialize database
    from database import db_manager
    db_manager.initialize()
    
    # Get database session
    db = get_db_session()
    
    # Clear existing products
    print("Clearing existing products...")
    db.execute(text('DELETE FROM products'))
    db.commit()
    
    # Initialize Shopify sync service with database session
    sync_service = ShopifyProductSyncService(db_session=db)
    
    print('Fetching products from Shopify...')
    try:
        # Start a fresh sync from Shopify
        result = sync_service.sync_all_products(
            include_draft=True,
            resume_cursor=None  # Start fresh
        )
        
        print(f'Sync result: {result}')
        
        # Check how many products we now have
        count = db.query(Product).count()
        print(f'Total products in database: {count}')
        
        # Show some sample products
        products = db.query(Product).limit(5).all()
        for p in products:
            print(f'- {p.sku}: {p.name} (${p.price})')
            
    except Exception as e:
        print(f'Error during sync: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()