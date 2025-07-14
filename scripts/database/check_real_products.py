#!/usr/bin/env python3
"""
Check the real products (not in test category)
"""
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def check_real_products():
    """Check products that are not in test category."""
    try:
        # Get Supabase credentials
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            print("Missing Supabase credentials")
            return
            
        print(f"Connecting to Supabase at: {supabase_url}")
        
        # Create client
        client = create_client(supabase_url, supabase_key)
        
        # Get products not in test category
        print("\n1. Checking real products (not in Test Category)...")
        real_products_result = client.table('products')\
            .select('*, categories(*)')\
            .neq('category_id', 1)\
            .limit(10)\
            .execute()
        
        if real_products_result.data:
            print(f"Found {len(real_products_result.data)} real products (sample):")
            for product in real_products_result.data:
                cat_name = product.get('categories', {}).get('name', 'No category') if product.get('categories') else 'No category'
                print(f"  - {product.get('name', 'No name')[:50]}...")
                print(f"    Category: {cat_name} (ID: {product.get('category_id')})")
                print(f"    SKU: {product.get('sku', 'No SKU')}")
                print()
        
        # Check category distribution of real products
        print("\n2. Category distribution of real products...")
        all_real_result = client.table('products')\
            .select('category_id')\
            .neq('category_id', 1)\
            .execute()
        
        if all_real_result.data:
            category_counts = {}
            for product in all_real_result.data:
                cat_id = product.get('category_id')
                category_counts[cat_id] = category_counts.get(cat_id, 0) + 1
            
            print("Real products by category:")
            for cat_id, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                if cat_id:
                    cat_result = client.table('categories').select('name').eq('id', cat_id).single().execute()
                    cat_name = cat_result.data.get('name', 'Unknown') if cat_result.data else 'Unknown'
                else:
                    cat_name = 'Uncategorized'
                print(f"  {cat_name} (ID: {cat_id}): {count} products")
        
        # Check if we should remove test products
        print(f"\n3. Should we remove the 23,535 test products?")
        print("These are taking up space and skewing the data.")
        print("Remove test products? (y/N): ", end="")
        response = input().strip().lower()
        
        if response == 'y' or response == 'yes':
            print("\n🗑️  Removing test products...")
            
            # Delete products in test category
            result = client.table('products').delete().eq('category_id', 1).execute()
            deleted_count = len(result.data) if result.data else 0
            print(f"Deletion completed - attempted to delete products in test category")
            
            # Check remaining products
            remaining_result = client.table('products').select('id', count='exact').execute()
            remaining_total = remaining_result.count if hasattr(remaining_result, 'count') else 0
            print(f"Remaining total products: {remaining_total}")
            
            if remaining_total <= 1000:
                print("✅ Test products removed successfully!")
            else:
                print(f"⚠️  {remaining_total} products still remain - may need manual cleanup")
        else:
            print("❌ Keeping test products")
            
    except Exception as e:
        print(f"Error checking real products: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_real_products()