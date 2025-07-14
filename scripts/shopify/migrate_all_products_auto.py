#!/usr/bin/env python3
"""
Auto-migrate ALL products (including drafts) to hierarchy without confirmation
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.shopify.migrate_products_to_hierarchy import ProductHierarchyMigrator

def main():
    shop_url = os.environ.get('SHOPIFY_SHOP_URL')
    access_token = os.environ.get('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        print("Error: SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN must be set")
        sys.exit(1)
    
    print("🚀 Starting migration of ALL products (including drafts) to hierarchy...")
    
    # Initialize migrator
    migrator = ProductHierarchyMigrator(
        shop_url=shop_url,
        access_token=access_token
    )
    
    # Test authentication
    try:
        migrator.test_auth()
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        sys.exit(1)
    
    # Load mappings
    migrator.load_hierarchy_mapping('collection_hierarchy_3_levels.csv')
    
    # Skip confirmation and migrate ALL products directly
    print("\n✅ Auto-migrating ALL products (including drafts)...")
    migrator.migrate_all_products()
    
    print("\n✅ Product migration complete!")

if __name__ == '__main__':
    main()