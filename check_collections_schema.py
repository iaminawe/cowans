#!/usr/bin/env python3
"""
Check collections table schema in Supabase
"""
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def check_collections_schema():
    """Check collections table schema and add missing columns if needed."""
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
        
        # Get a sample collection to check schema
        result = client.table('collections').select('*').limit(1).execute()
        
        if result.data:
            print("Collections table schema (sample record):")
            sample = result.data[0]
            for key, value in sample.items():
                print(f"  {key}: {type(value).__name__}")
            
            # Check for new columns we need for Shopify sync
            required_columns = [
                'image_url', 'image_alt', 'products_count', 'seo_title', 
                'seo_description', 'sort_order', 'template_suffix', 
                'shopify_updated_at', 'synced_at'
            ]
            
            missing_columns = []
            for col in required_columns:
                if col not in sample:
                    missing_columns.append(col)
            
            if missing_columns:
                print(f"\nMissing columns for Shopify sync: {missing_columns}")
                print("Note: These columns may need to be added to the collections table")
            else:
                print("\nAll required columns present for Shopify sync")
        else:
            print("No collections found in table")
            
    except Exception as e:
        print(f"Error checking schema: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_collections_schema()