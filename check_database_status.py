#!/usr/bin/env python3
"""
Check current database status
"""
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def check_database_status():
    """Check current database status."""
    try:
        # Get credentials
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        
        if not all([supabase_url, supabase_key]):
            print("Missing required credentials")
            return
        
        # Create Supabase client
        supabase = create_client(supabase_url, supabase_key)
        
        # Check current product count
        print("📊 Current Database Status:")
        print("=" * 40)
        
        # Total products
        total_result = supabase.table('products').select('id', count='exact').execute()
        total_count = total_result.count if hasattr(total_result, 'count') else 0
        print(f"Total products: {total_count}")
        
        # Products by category
        categories_result = supabase.table('categories').select('id, name').execute()
        if categories_result.data:
            print("\nProducts by category:")
            for category in categories_result.data:
                cat_products = supabase.table('products').select('id', count='exact').eq('category_id', category['id']).execute()
                count = cat_products.count if hasattr(cat_products, 'count') else 0
                print(f"  {category['name']}: {count} products")
        
        # Products with Shopify ID
        shopify_result = supabase.table('products').select('id', count='exact').not_.is_('shopify_product_id', 'null').execute()
        shopify_count = shopify_result.count if hasattr(shopify_result, 'count') else 0
        print(f"\nProducts with Shopify ID: {shopify_count}")
        
        # Recent products (last 10 minutes)
        from datetime import datetime, timedelta
        recent_time = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        recent_result = supabase.table('products').select('id', count='exact').gte('created_at', recent_time).execute()
        recent_count = recent_result.count if hasattr(recent_result, 'count') else 0
        print(f"Recently added products (last 10 min): {recent_count}")
        
        print("\n" + "=" * 40)
        
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    check_database_status()