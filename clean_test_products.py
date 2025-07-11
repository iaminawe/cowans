#!/usr/bin/env python3
"""
Clean up test products automatically
"""
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def clean_test_products():
    """Remove test products from the database."""
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
        
        # Check current state
        print("\n1. Current state:")
        total_result = client.table('products').select('id', count='exact').execute()
        total_products = total_result.count if hasattr(total_result, 'count') else 0
        
        test_result = client.table('products').select('id', count='exact').eq('category_id', 1).execute()
        test_products = test_result.count if hasattr(test_result, 'count') else 0
        
        print(f"  Total products: {total_products}")
        print(f"  Test products (category_id=1): {test_products}")
        print(f"  Real products: {total_products - test_products}")
        
        if test_products > 0:
            print(f"\n2. Removing {test_products} test products...")
            
            # Delete in batches to avoid timeout
            batch_size = 1000
            deleted_total = 0
            
            while True:
                # Get a batch of test products
                batch_result = client.table('products')\
                    .select('id')\
                    .eq('category_id', 1)\
                    .limit(batch_size)\
                    .execute()
                
                if not batch_result.data:
                    break
                
                # Delete this batch
                product_ids = [p['id'] for p in batch_result.data]
                
                # Delete from product_collections first (foreign key constraint)
                client.table('product_collections')\
                    .delete()\
                    .in_('product_id', product_ids)\
                    .execute()
                
                # Delete the products
                delete_result = client.table('products')\
                    .delete()\
                    .in_('id', product_ids)\
                    .execute()
                
                batch_deleted = len(delete_result.data) if delete_result.data else 0
                deleted_total += batch_deleted
                
                print(f"  Deleted batch: {batch_deleted} products (total: {deleted_total})")
                
                if batch_deleted < batch_size:
                    break
            
            print(f"✅ Deleted {deleted_total} test products")
        
        # Final state
        print("\n3. Final state:")
        final_result = client.table('products').select('id', count='exact').execute()
        final_products = final_result.count if hasattr(final_result, 'count') else 0
        print(f"  Remaining products: {final_products}")
        
        # Show categories of remaining products
        if final_products > 0:
            categories_result = client.table('products')\
                .select('category_id, categories(name)')\
                .execute()
            
            if categories_result.data:
                category_counts = {}
                for product in categories_result.data:
                    cat_id = product.get('category_id')
                    cat_name = product.get('categories', {}).get('name', 'Unknown') if product.get('categories') else 'Uncategorized'
                    category_counts[f"{cat_name} (ID: {cat_id})"] = category_counts.get(f"{cat_name} (ID: {cat_id})", 0) + 1
                
                print("\n  Products by category:")
                for cat_name, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                    print(f"    {cat_name}: {count} products")
        
        print("\n✅ Test product cleanup completed!")
            
    except Exception as e:
        print(f"Error cleaning test products: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    clean_test_products()