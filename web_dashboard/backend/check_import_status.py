"""
Check Import Status and Results
Monitor the progress of the Shopify import and display results
"""

import requests
import time
import json
from datetime import datetime

BASE_URL = "http://localhost:3560"

def check_database_products():
    """Check how many products are in the database"""
    try:
        response = requests.get(f"{BASE_URL}/api/products", timeout=10)
        if response.status_code == 200:
            data = response.json()
            total_products = data.get('total', 0)
            products = data.get('products', [])
            return total_products, products[:5]  # Return first 5 for preview
        else:
            print(f"❌ Failed to get products: {response.status_code}")
            return 0, []
    except Exception as e:
        print(f"❌ Error checking products: {str(e)}")
        return 0, []

def check_sync_status():
    """Check the status of sync operations"""
    try:
        response = requests.get(f"{BASE_URL}/api/sync/parallel/status", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "unknown", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def main():
    """Main monitoring function"""
    print("📊 Shopify Import Status Monitor")
    print("=" * 50)
    
    # Check current products in database
    print("🔍 Checking current database status...")
    total_products, sample_products = check_database_products()
    
    print(f"📦 Total products in database: {total_products}")
    
    if sample_products:
        print(f"\n📋 Sample products:")
        for i, product in enumerate(sample_products, 1):
            print(f"   {i}. {product.get('title', 'Unknown')} (ID: {product.get('id', 'N/A')})")
    
    # Check sync status
    print(f"\n🔄 Checking sync status...")
    sync_status = check_sync_status()
    
    print(f"   Status: {sync_status.get('status', 'unknown')}")
    if 'metrics' in sync_status:
        metrics = sync_status['metrics']
        print(f"   Progress: {metrics.get('operations_completed', 0)} operations")
        print(f"   Rate: {metrics.get('operations_per_second', 0):.1f}/sec")
    
    # Monitor for a short while
    print(f"\n⏱️  Monitoring import progress for 30 seconds...")
    
    start_time = time.time()
    last_count = total_products
    
    for i in range(6):  # Check every 5 seconds for 30 seconds
        time.sleep(5)
        
        current_count, _ = check_database_products()
        elapsed = time.time() - start_time
        
        if current_count > last_count:
            new_products = current_count - last_count
            rate = new_products / 5  # per second over last 5 seconds
            print(f"   📈 +{new_products} products added (total: {current_count}, rate: {rate:.1f}/sec)")
            last_count = current_count
        else:
            print(f"   📊 No change (total: {current_count})")
    
    # Final status
    final_count, _ = check_database_products()
    total_added = final_count - total_products
    
    print(f"\n🎯 Final Results:")
    print(f"   • Starting products: {total_products}")
    print(f"   • Final products: {final_count}")
    print(f"   • Products added: {total_added}")
    print(f"   • Monitoring time: 30 seconds")
    
    if total_added > 0:
        print(f"   ✅ Import appears to be working!")
    else:
        print(f"   ⚠️  No new products detected during monitoring")
        print(f"   💡 Import may still be in progress or completed already")

if __name__ == "__main__":
    main()