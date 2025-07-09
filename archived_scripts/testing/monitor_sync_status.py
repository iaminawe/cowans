#!/usr/bin/env python3
"""
Monitor the current sync status and provide real-time updates
"""

import os
import time
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Get database connection."""
    db_url = os.getenv('DATABASE_URL')
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    return psycopg2.connect(db_url)

def get_current_status():
    """Get current database status."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM products")
        total = cursor.fetchone()[0]
        
        # Get products updated in last 5 minutes
        cursor.execute("SELECT COUNT(*) FROM products WHERE updated_at > NOW() - INTERVAL '5 minutes'")
        recent = cursor.fetchone()[0]
        
        # Get products with titles (to see if we have real data)
        cursor.execute("SELECT COUNT(*) FROM products WHERE title IS NOT NULL AND title != ''")
        with_titles = cursor.fetchone()[0]
        
        # Get sample products
        cursor.execute("""
            SELECT title, sku, price, updated_at, shopify_product_id 
            FROM products 
            WHERE updated_at > NOW() - INTERVAL '5 minutes'
            ORDER BY updated_at DESC 
            LIMIT 3
        """)
        samples = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            'total': total,
            'recent_updates': recent,
            'with_titles': with_titles,
            'samples': samples,
            'timestamp': datetime.now()
        }
    except Exception as e:
        return {'error': str(e)}

def monitor_sync():
    """Monitor sync progress in real-time."""
    print("🔍 Monitoring sync progress...")
    print("=" * 60)
    
    last_total = 0
    check_count = 0
    
    while True:
        check_count += 1
        status = get_current_status()
        
        if 'error' in status:
            print(f"❌ Error: {status['error']}")
            time.sleep(10)
            continue
        
        current_total = status['total']
        recent_updates = status['recent_updates']
        with_titles = status['with_titles']
        timestamp = status['timestamp']
        
        # Calculate change
        change = current_total - last_total
        change_str = f"(+{change})" if change > 0 else f"({change})" if change < 0 else "(no change)"
        
        print(f"⏰ [{timestamp.strftime('%H:%M:%S')}] Check #{check_count}")
        print(f"📊 Total products: {current_total:,} {change_str}")
        print(f"📈 Recent updates (5 min): {recent_updates:,}")
        print(f"📝 Products with titles: {with_titles:,} ({with_titles/current_total*100:.1f}%)")
        
        # Show sample products if any recent updates
        if status['samples']:
            print("🔍 Recent products:")
            for title, sku, price, updated_at, shopify_id in status['samples']:
                title_display = title[:30] + "..." if title and len(title) > 30 else title or "No title"
                sku_display = sku or "No SKU"
                price_display = f"${price:.2f}" if price else "No price"
                print(f"   • {title_display} | {sku_display} | {price_display} | ID: {shopify_id}")
        
        print("-" * 60)
        
        last_total = current_total
        
        # Check if sync seems to be finished (no recent updates)
        if recent_updates == 0 and check_count > 3:
            print("✅ No recent updates detected. Sync may be completed.")
            break
        
        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    try:
        monitor_sync()
    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped by user")