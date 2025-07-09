#!/usr/bin/env python3
"""
Simple product count check
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_product_count():
    """Get basic product count and info."""
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("Error: DATABASE_URL not found")
        return
    
    # Fix the URL format if needed
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Basic product count
        cursor.execute("SELECT COUNT(*) FROM products")
        total = cursor.fetchone()[0]
        
        print(f"📊 Total products in database: {total:,}")
        
        # Check if products have basic info
        cursor.execute("SELECT COUNT(*) FROM products WHERE title IS NOT NULL AND title != ''")
        with_title = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products WHERE sku IS NOT NULL AND sku != ''")
        with_sku = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products WHERE price IS NOT NULL")
        with_price = cursor.fetchone()[0]
        
        print(f"📝 Products with title: {with_title:,} ({with_title/total*100:.1f}%)")
        print(f"🏷️  Products with SKU: {with_sku:,} ({with_sku/total*100:.1f}%)")
        print(f"💰 Products with price: {with_price:,} ({with_price/total*100:.1f}%)")
        
        # Check for Shopify integration
        cursor.execute("SELECT COUNT(*) FROM products WHERE shopify_product_id IS NOT NULL")
        with_shopify = cursor.fetchone()[0]
        
        print(f"🛍️  Products synced to Shopify: {with_shopify:,} ({with_shopify/total*100:.1f}%)")
        
        # Check recent activity
        cursor.execute("SELECT COUNT(*) FROM products WHERE updated_at > NOW() - INTERVAL '24 hours'")
        recent = cursor.fetchone()[0]
        
        print(f"⏰ Products updated in last 24 hours: {recent:,}")
        
        # Sample recent products
        cursor.execute("""
            SELECT title, sku, price, updated_at 
            FROM products 
            WHERE title IS NOT NULL 
            ORDER BY updated_at DESC 
            LIMIT 5
        """)
        
        print("\n🔍 Recent products:")
        for title, sku, price, updated in cursor.fetchall():
            title_short = title[:50] + "..." if len(title) > 50 else title
            sku_display = sku if sku else "No SKU"
            price_display = f"${price:.2f}" if price else "No price"
            print(f"  • {title_short} | {sku_display} | {price_display}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    get_product_count()