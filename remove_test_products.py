#!/usr/bin/env python3
"""
Check and remove test products if they are test data
"""
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def check_and_remove_test_products():
    """Check if products are test data and remove them if needed."""
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
        
        # Check total products
        print("\n1. Checking total products...")
        total_result = client.table('products').select('id', count='exact').execute()
        total_products = total_result.count if hasattr(total_result, 'count') else 0
        print(f"Total products: {total_products}")
        
        # Check products in "Test Category" (ID: 1)
        test_result = client.table('products').select('id', count='exact').eq('category_id', 1).execute()
        test_products = test_result.count if hasattr(test_result, 'count') else 0
        print(f"Products in 'Test Category': {test_products}")
        
        # Check if all products are in test category
        if test_products == total_products and total_products > 0:
            print(f"\n⚠️  ALL {total_products} products are in 'Test Category'")
            print("These appear to be test data products.")
            
            # Get a sample to verify they're test data
            sample_result = client.table('products').select('name, sku, description').limit(5).execute()
            if sample_result.data:
                print("\nSample products:")
                for product in sample_result.data:
                    print(f"  - {product.get('name', 'No name')}")
                    print(f"    SKU: {product.get('sku', 'No SKU')}")
                    print(f"    Description: {product.get('description', 'No description')[:100]}...")
                    print()
            
            # Ask for confirmation to remove
            print("Do you want to remove all these test products? (y/N): ", end="")
            response = input().strip().lower()
            
            if response == 'y' or response == 'yes':
                print("\n🗑️  Removing all test products...")
                
                # Delete all products in test category
                result = client.table('products').delete().eq('category_id', 1).execute()
                print(f"Deleted {len(result.data) if result.data else 0} products")
                
                # Verify deletion
                remaining_result = client.table('products').select('id', count='exact').execute()
                remaining_products = remaining_result.count if hasattr(remaining_result, 'count') else 0
                print(f"Remaining products: {remaining_products}")
                
                if remaining_products == 0:
                    print("✅ All test products removed successfully!")
                else:
                    print(f"⚠️  {remaining_products} products still remain")
            else:
                print("❌ Cancelled - no products removed")
        else:
            print(f"\n✅ Not all products are test data:")
            print(f"  - Test products: {test_products}")
            print(f"  - Other products: {total_products - test_products}")
            print("No action needed.")
            
    except Exception as e:
        print(f"Error checking/removing test products: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_and_remove_test_products()