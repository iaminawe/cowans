#!/usr/bin/env python3
"""
Sync Verification Script - Comprehensive check of Shopify sync status
"""

from database import db_manager, init_database
from models import Product, Collection, Category, ProductCollection
from sqlalchemy import func, text
import os
from datetime import datetime

def verify_sync_status():
    """Verify the completion and integrity of Shopify sync"""
    
    # Initialize database
    init_database()
    
    print(f"=== Sync Verification Report ===")
    print(f"Generated at: {datetime.now().isoformat()}")
    print("-" * 50)
    
    # Get table statistics
    stats = db_manager.get_table_stats()
    print('\n=== Database Table Statistics ===')
    for table, count in sorted(stats.items()):
        if count != 'error':
            print(f'{table}: {count} rows')
    
    # Check sync operations
    with db_manager.session_scope() as session:
        # Check products with Shopify IDs
        try:
            synced_products = session.query(func.count(Product.id)).filter(Product.shopify_product_id.isnot(None)).scalar()
            total_products = session.query(func.count(Product.id)).scalar()
            print(f'\n=== Product Sync Status ===')
            print(f'Total products: {total_products}')
            print(f'Products with Shopify ID: {synced_products}')
            print(f'Products without Shopify ID: {total_products - synced_products}')
            print(f'Sync percentage: {(synced_products/total_products*100) if total_products > 0 else 0:.2f}%')
            
            # Get sample products
            sample_products = session.query(Product).limit(5).all()
            if sample_products:
                print('\nSample products:')
                for p in sample_products:
                    desc = p.description[:50] if p.description else "No description"
                    print(f'  - {p.sku}: {desc}... (Shopify ID: {p.shopify_product_id})')
        except Exception as e:
            print(f'\nError checking product sync status: {e}')
        
        # Check collections
        try:
            total_collections = session.query(func.count(Collection.id)).scalar()
            synced_collections = session.query(func.count(Collection.id)).filter(Collection.shopify_collection_id.isnot(None)).scalar()
            print(f'\n=== Collection Sync Status ===')
            print(f'Total collections: {total_collections}')
            print(f'Collections with Shopify ID: {synced_collections}')
            print(f'Collections without Shopify ID: {total_collections - synced_collections}')
            print(f'Sync percentage: {(synced_collections/total_collections*100) if total_collections > 0 else 0:.2f}%')
            
            # Get sample collections
            sample_collections = session.query(Collection).limit(5).all()
            if sample_collections:
                print('\nSample collections:')
                for c in sample_collections:
                    print(f'  - {c.name} (Shopify ID: {c.shopify_collection_id})')
        except Exception as e:
            print(f'\nError checking collection sync status: {e}')
        
        # Check product-collection associations
        try:
            total_associations = session.query(func.count(ProductCollection.product_id)).scalar()
            print(f'\n=== Product-Collection Associations ===')
            print(f'Total associations: {total_associations}')
            
            # Check orphaned products
            orphaned_products = session.query(func.count(Product.id)).filter(
                ~Product.id.in_(session.query(ProductCollection.product_id).distinct())
            ).scalar()
            print(f'Orphaned products (not in any collection): {orphaned_products}')
            
            # Check products per collection
            collection_counts = session.execute(text('''
                SELECT c.name, COUNT(pc.product_id) as product_count
                FROM collections c
                LEFT JOIN product_collections pc ON c.id = pc.collection_id
                GROUP BY c.id, c.name
                ORDER BY product_count DESC
                LIMIT 10
            ''')).fetchall()
            
            if collection_counts:
                print('\nTop collections by product count:')
                for title, count in collection_counts:
                    print(f'  - {title}: {count} products')
        except Exception as e:
            print(f'\nError checking associations: {e}')
        
        # Check categories
        try:
            total_categories = session.query(func.count(Category.id)).scalar()
            print(f'\n=== Categories ===')
            print(f'Total categories: {total_categories}')
            
            # Sample categories
            sample_categories = session.query(Category).limit(5).all()
            if sample_categories:
                print('\nSample categories:')
                for cat in sample_categories:
                    print(f'  - {cat.name} (Path: {cat.path})')
        except Exception as e:
            print(f'\nError checking categories: {e}')
        
        # Data integrity checks
        print(f'\n=== Data Integrity Checks ===')
        try:
            # Check for duplicate SKUs
            duplicate_skus = session.execute(text('''
                SELECT sku, COUNT(*) as count
                FROM products
                GROUP BY sku
                HAVING COUNT(*) > 1
                LIMIT 10
            ''')).fetchall()
            
            if duplicate_skus:
                print(f'Found {len(duplicate_skus)} duplicate SKUs:')
                for sku, count in duplicate_skus:
                    print(f'  - {sku}: {count} occurrences')
            else:
                print('No duplicate SKUs found ✓')
                
            # Check for null required fields
            null_descriptions = session.query(func.count(Product.id)).filter(Product.description.is_(None)).scalar()
            null_prices = session.query(func.count(Product.id)).filter(Product.price.is_(None)).scalar()
            
            print(f'\nData quality issues:')
            print(f'  - Products without description: {null_descriptions}')
            print(f'  - Products without price: {null_prices}')
            
        except Exception as e:
            print(f'Error in data integrity checks: {e}')
        
        # Sync operation history
        try:
            # Check sync_history table
            recent_syncs = session.execute(text('''
                SELECT sync_type, status, started_at, completed_at, 
                       items_processed, items_failed, error_message
                FROM sync_history
                ORDER BY started_at DESC
                LIMIT 5
            ''')).fetchall()
            
            if recent_syncs:
                print(f'\n=== Recent Sync Operations ===')
                for sync in recent_syncs:
                    sync_type, status, started, completed, processed, failed, error = sync
                    duration = (completed - started).total_seconds() if completed and started else 'N/A'
                    print(f'  - {sync_type}: {status} ({processed} processed, {failed} failed)')
                    if error:
                        print(f'    Error: {error[:100]}...')
        except Exception as e:
            print(f'\nNo sync history available')
        
        # Final summary
        print(f'\n=== SYNC VERIFICATION SUMMARY ===')
        try:
            sync_complete = (synced_products == total_products and 
                           synced_collections == total_collections and
                           total_associations > 0)
            
            if sync_complete:
                print('✓ Full sync appears to be COMPLETE')
            else:
                print('⚠️  Sync is INCOMPLETE')
                if synced_products < total_products:
                    print(f'   - {total_products - synced_products} products need syncing')
                if synced_collections < total_collections:
                    print(f'   - {total_collections - synced_collections} collections need syncing')
                if total_associations == 0:
                    print(f'   - No product-collection associations found')
        except:
            print('Unable to determine sync status')

if __name__ == "__main__":
    verify_sync_status()