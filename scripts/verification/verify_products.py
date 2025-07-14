#!/usr/bin/env python3
"""
Verify products exist in Supabase database
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'web_dashboard', 'backend'))

from services.supabase_database import get_supabase_db

def verify_products():
    """Check if products exist in Supabase database."""
    try:
        supabase = get_supabase_db()
        
        # Get total product count
        result = supabase.client.table('products').select('*', count='exact').execute()
        
        print(f"Total products in database: {result.count if hasattr(result, 'count') else 'Unknown'}")
        
        # Get first 5 products to verify data
        sample_result = supabase.client.table('products').select('*').limit(5).execute()
        
        if sample_result.data:
            print(f"Sample products found: {len(sample_result.data)}")
            for i, product in enumerate(sample_result.data[:3]):
                print(f"  {i+1}. {product.get('name', 'No name')} (ID: {product.get('id')}) - SKU: {product.get('sku', 'No SKU')}")
        else:
            print("No products found in database")
            
        # Check if categories exist
        categories_result = supabase.client.table('categories').select('*', count='exact').execute()
        print(f"Total categories: {categories_result.count if hasattr(categories_result, 'count') else 'Unknown'}")
        
        # Check if collections exist
        collections_result = supabase.client.table('collections').select('*', count='exact').execute()
        print(f"Total collections: {collections_result.count if hasattr(collections_result, 'count') else 'Unknown'}")
        
    except Exception as e:
        print(f"Error verifying products: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_products()