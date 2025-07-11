#!/usr/bin/env python3
"""
Check product categories and pagination
"""
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def check_product_categories():
    """Check product categories and pagination issues."""
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
        
        # Check categories
        print("\n1. Checking categories...")
        categories_result = client.table('categories').select('*').limit(10).execute()
        
        if categories_result.data:
            print(f"Found {len(categories_result.data)} categories:")
            for cat in categories_result.data[:5]:
                print(f"  - ID: {cat.get('id')}, Name: {cat.get('name')}, Slug: {cat.get('slug')}")
        else:
            print("No categories found!")
        
        # Check products with categories
        print("\n2. Checking products with categories...")
        products_result = client.table('products')\
            .select('id, name, category_id, categories(*)')\
            .limit(10)\
            .execute()
        
        if products_result.data:
            print(f"Sample products:")
            category_counts = {}
            for product in products_result.data:
                cat_id = product.get('category_id')
                category_counts[cat_id] = category_counts.get(cat_id, 0) + 1
                cat_name = product.get('categories', {}).get('name', 'No category') if product.get('categories') else 'No category'
                print(f"  - {product.get('name', 'No name')[:50]}... -> Category: {cat_name} (ID: {cat_id})")
            
            print(f"\nCategory distribution in sample:")
            for cat_id, count in category_counts.items():
                print(f"  Category ID {cat_id}: {count} products")
        
        # Check total products by category
        print("\n3. Checking total product distribution by category...")
        all_products_result = client.table('products')\
            .select('category_id')\
            .execute()
        
        if all_products_result.data:
            category_distribution = {}
            for product in all_products_result.data:
                cat_id = product.get('category_id')
                category_distribution[cat_id] = category_distribution.get(cat_id, 0) + 1
            
            print("Full category distribution:")
            for cat_id, count in sorted(category_distribution.items(), key=lambda x: x[1], reverse=True)[:10]:
                # Get category name
                if cat_id:
                    cat_result = client.table('categories').select('name').eq('id', cat_id).single().execute()
                    cat_name = cat_result.data.get('name', 'Unknown') if cat_result.data else 'Unknown'
                else:
                    cat_name = 'Uncategorized'
                print(f"  {cat_name} (ID: {cat_id}): {count} products")
        
        # Test pagination
        print("\n4. Testing pagination...")
        page1_result = client.table('products')\
            .select('id, name')\
            .range(0, 9)\
            .execute()
        
        page2_result = client.table('products')\
            .select('id, name')\
            .range(10, 19)\
            .execute()
        
        print(f"Page 1: {len(page1_result.data) if page1_result.data else 0} products")
        print(f"Page 2: {len(page2_result.data) if page2_result.data else 0} products")
        
        if page1_result.data and page2_result.data:
            print("Pagination working - different products on each page")
        else:
            print("Pagination issue detected")
            
    except Exception as e:
        print(f"Error checking product categories: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_product_categories()