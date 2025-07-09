"""
Quick Shopify Import Script - Import 1000 products fast
Uses the existing Shopify sync infrastructure with parallel processing
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def import_via_api():
    """Import products via the backend API using parallel processing"""
    
    # Backend API URL (adjust if needed)
    BASE_URL = "http://localhost:3560"
    
    print("🚀 Starting Shopify Import via Backend API")
    print("=" * 60)
    
    try:
        # Step 1: Start parallel sync
        print("📡 Starting parallel sync operation...")
        
        sync_config = {
            "enabled": True,
            "minWorkers": 6,
            "maxWorkers": 10,
            "batchSize": 50,
            "priority": "high",
            "operationType": "import",
            "strategy": "speed",
            "retryAttempts": 3,
            "timeout": 300
        }
        
        response = requests.post(
            f"{BASE_URL}/api/sync/parallel/start",
            json=sync_config,
            timeout=30
        )
        
        if response.status_code == 200:
            sync_data = response.json()
            operation_id = sync_data.get("operation_id")
            print(f"✅ Parallel sync started - Operation ID: {operation_id}")
        else:
            print(f"❌ Failed to start parallel sync: {response.text}")
            return False
        
        # Step 2: Monitor progress
        print("📊 Monitoring sync progress...")
        
        start_time = time.time()
        last_update = 0
        
        while True:
            try:
                status_response = requests.get(
                    f"{BASE_URL}/api/sync/parallel/status",
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    status = status_response.json()
                    
                    # Display progress
                    current_time = time.time()
                    elapsed = current_time - start_time
                    
                    if current_time - last_update >= 5:  # Update every 5 seconds
                        print(f"⏱️  Elapsed: {elapsed:.1f}s | Status: {status.get('status', 'unknown')}")
                        
                        if 'metrics' in status:
                            metrics = status['metrics']
                            print(f"   📈 Products processed: {metrics.get('operations_completed', 0)}")
                            print(f"   🚀 Rate: {metrics.get('operations_per_second', 0):.1f}/sec")
                            print(f"   ✅ Success rate: {metrics.get('success_rate', 0):.1%}")
                        
                        last_update = current_time
                    
                    # Check if completed
                    if status.get('status') == 'completed':
                        print("🎉 Sync completed successfully!")
                        
                        final_metrics = status.get('metrics', {})
                        print(f"\n📊 Final Results:")
                        print(f"   • Total duration: {elapsed:.2f}s")
                        print(f"   • Products imported: {final_metrics.get('operations_completed', 0)}")
                        print(f"   • Average rate: {final_metrics.get('operations_per_second', 0):.1f} products/sec")
                        print(f"   • Success rate: {final_metrics.get('success_rate', 0):.1%}")
                        break
                    
                    elif status.get('status') == 'failed':
                        print("❌ Sync failed!")
                        print(f"Error: {status.get('error', 'Unknown error')}")
                        break
                    
                    # Safety timeout (10 minutes)
                    if elapsed > 600:
                        print("⏰ Timeout reached - stopping monitoring")
                        break
                
                else:
                    print(f"⚠️  Status check failed: {status_response.status_code}")
                
                time.sleep(2)  # Wait 2 seconds before next check
                
            except requests.exceptions.RequestException as e:
                print(f"⚠️  Connection error during monitoring: {str(e)}")
                time.sleep(5)
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {str(e)}")
        return False

def import_via_direct_sync():
    """Import products using direct Shopify sync"""
    
    BASE_URL = "http://localhost:3560"
    
    print("📦 Starting Direct Shopify Sync...")
    
    try:
        # Trigger Shopify import
        response = requests.post(
            f"{BASE_URL}/api/shopify/import",
            json={
                "limit": 1000,
                "use_parallel": True,
                "batch_size": 50,
                "max_workers": 8
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Import started: {result}")
            return True
        else:
            print(f"❌ Import failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Direct sync failed: {str(e)}")
        return False

def test_backend_connection():
    """Test if backend is running"""
    try:
        # Try the root endpoint first
        response = requests.get("http://localhost:3560/", timeout=5)
        if response.status_code in [200, 404]:  # 404 is OK, means server is running
            print("✅ Backend is running")
            return True
        else:
            print(f"⚠️  Backend responded with status {response.status_code}")
            return False
    except requests.exceptions.RequestException:
        print("❌ Backend is not running or not accessible")
        print("   Please start the backend with: python app.py")
        return False

def main():
    """Main function"""
    print("🚀 Fast Shopify Import Tool")
    print("Importing 1000 products using parallel batch processing")
    print("=" * 60)
    
    # Test backend connection
    if not test_backend_connection():
        print("\n💡 To start the backend:")
        print("   cd /Users/iaminawe/Sites/cowans/web_dashboard/backend")
        print("   python app.py")
        return
    
    # Try parallel sync first (fastest method)
    print("\n🚀 Method 1: Parallel Batch Sync (Fastest)")
    success = import_via_api()
    
    if not success:
        print("\n🔄 Method 2: Direct Shopify Sync (Fallback)")
        success = import_via_direct_sync()
    
    if success:
        print(f"\n🎉 Import completed successfully!")
        print(f"📈 Check the dashboard to see your imported products")
    else:
        print(f"\n❌ All import methods failed")
        print(f"💡 Please check the backend logs for more details")

if __name__ == "__main__":
    main()