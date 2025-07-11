#!/usr/bin/env python3
"""
Clean up test category since no products use it anymore
"""
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def clean_test_category():
    """Remove test category since it's no longer used."""
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
        
        # Check if test category is still used
        print("\n1. Checking Test Category usage...")
        products_in_test = client.table('products').select('id', count='exact').eq('category_id', 1).execute()
        test_usage = products_in_test.count if hasattr(products_in_test, 'count') else 0
        
        print(f"Products still in Test Category (ID: 1): {test_usage}")
        
        if test_usage == 0:
            print("\n2. Removing unused Test Category...")
            
            # Delete the test category
            result = client.table('categories').delete().eq('id', 1).execute()
            
            if result.data:
                print("✅ Test Category removed successfully!")
            else:
                print("⚠️  Test Category may have already been removed or deletion failed")
        else:
            print(f"⚠️  Cannot remove Test Category - still has {test_usage} products")
        
        # Show current categories
        print("\n3. Current categories:")
        categories_result = client.table('categories').select('*').order('id').execute()
        
        if categories_result.data:
            for cat in categories_result.data:
                # Count products in this category
                prod_count_result = client.table('products').select('id', count='exact').eq('category_id', cat['id']).execute()
                prod_count = prod_count_result.count if hasattr(prod_count_result, 'count') else 0
                
                print(f"  ID: {cat['id']}, Name: {cat['name']}, Products: {prod_count}")
        else:
            print("  No categories found")
            
    except Exception as e:
        print(f"Error cleaning test category: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    clean_test_category()