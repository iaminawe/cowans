#!/usr/bin/env python3
"""
Simple verification of Supabase products
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

def verify_products():
    """Check if products exist in Supabase database."""
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
        
        # Get total product count
        result = client.table('products').select('*', count='exact').execute()
        
        print(f"Total products in database: {result.count if hasattr(result, 'count') else len(result.data or [])}")
        
        # Get first 5 products to verify data
        sample_result = client.table('products').select('*').limit(5).execute()
        
        if sample_result.data:
            print(f"Sample products found: {len(sample_result.data)}")
            for i, product in enumerate(sample_result.data[:3]):
                print(f"  {i+1}. {product.get('name', 'No name')} (ID: {product.get('id')}) - SKU: {product.get('sku', 'No SKU')}")
        else:
            print("No products found in database")
            
        # Check if categories exist
        categories_result = client.table('categories').select('*', count='exact').execute()
        print(f"Total categories: {categories_result.count if hasattr(categories_result, 'count') else len(categories_result.data or [])}")
        
        # Check if collections exist
        collections_result = client.table('collections').select('*', count='exact').execute()
        print(f"Total collections: {collections_result.count if hasattr(collections_result, 'count') else len(collections_result.data or [])}")
        
    except Exception as e:
        print(f"Error verifying products: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_products()