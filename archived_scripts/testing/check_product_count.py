#!/usr/bin/env python3
"""
Check how many products are in the database
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'web_dashboard', 'backend'))

# Load environment variables
load_dotenv()

def check_product_count():
    """Check the product count in the database."""
    # Get database connection details from environment
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("Error: DATABASE_URL not found in environment variables")
        return
    
    # Fix the URL format if needed (remove psycopg+ prefix)
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print(f"Connecting to database...")
    
    try:
        # Connect to the database
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Count total products
        cursor.execute("SELECT COUNT(*) FROM products")
        total_count = cursor.fetchone()[0]
        
        print(f"Total products in database: {total_count:,}")
        
        # Count by sync status
        cursor.execute("""
            SELECT sync_status, COUNT(*) 
            FROM products 
            GROUP BY sync_status 
            ORDER BY COUNT(*) DESC
        """)
        
        print("\nProducts by sync status:")
        for status, count in cursor.fetchall():
            status_display = status if status else "Not set"
            print(f"  {status_display}: {count:,}")
        
        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) 
            FROM products 
            GROUP BY status 
            ORDER BY COUNT(*) DESC
        """)
        
        print("\nProducts by status:")
        for status, count in cursor.fetchall():
            status_display = status if status else "Not set"
            print(f"  {status_display}: {count:,}")
        
        # Count published vs draft
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN published_at IS NOT NULL THEN 1 ELSE 0 END) as published,
                SUM(CASE WHEN published_at IS NULL THEN 1 ELSE 0 END) as draft
            FROM products
        """)
        published, draft = cursor.fetchone()
        
        print(f"\nPublished products: {published:,}")
        print(f"Draft products: {draft:,}")
        
        # Check recently updated products
        cursor.execute("""
            SELECT COUNT(*) 
            FROM products 
            WHERE updated_at > NOW() - INTERVAL '7 days'
        """)
        recent_updates = cursor.fetchone()[0]
        
        print(f"\nProducts updated in last 7 days: {recent_updates:,}")
        
        # Check products with shopify_product_id
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN shopify_product_id IS NOT NULL THEN 1 ELSE 0 END) as with_shopify_id,
                SUM(CASE WHEN shopify_product_id IS NULL THEN 1 ELSE 0 END) as without_shopify_id
            FROM products
        """)
        with_shopify, without_shopify = cursor.fetchone()
        
        print(f"\nProducts with Shopify ID: {with_shopify:,}")
        print(f"Products without Shopify ID: {without_shopify:,}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")
        print("\nAlternative: Checking via API...")
        
        # Try via API as fallback
        try:
            import requests
            response = requests.get("http://localhost:3560/api/products?per_page=1")
            if response.status_code == 200:
                data = response.json()
                if 'total' in data:
                    print(f"Total products (via API): {data['total']:,}")
            else:
                print(f"API returned status code: {response.status_code}")
        except Exception as api_error:
            print(f"API check failed: {str(api_error)}")

if __name__ == "__main__":
    check_product_count()