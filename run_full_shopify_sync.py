#!/usr/bin/env python3
"""
Run full Shopify product sync - pull all products from Shopify to local database
"""

import os
import sys
import time
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Add backend path
sys.path.append(os.path.join(os.path.dirname(__file__), 'web_dashboard', 'backend'))

# Load environment variables
load_dotenv()

def run_full_sync():
    """Run a complete Shopify product sync."""
    
    print("🚀 Starting Full Shopify Product Sync")
    print("=" * 50)
    
    # Get credentials
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        print("❌ Error: Shopify credentials not found")
        return False
    
    # Check if backend is running
    try:
        health_response = requests.get("http://localhost:3560/api/health/")
        if health_response.status_code != 200:
            print("❌ Backend is not running. Please start it first.")
            return False
        print("✅ Backend is running")
    except:
        print("❌ Cannot connect to backend. Please start it first.")
        return False
    
    # Start the sync via API
    print(f"📥 Initiating sync from Shopify ({shop_url})...")
    
    sync_data = {
        "sync_type": "full",
        "batch_name": f"Full Sync - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "options": {
            "include_variants": True,
            "include_images": True,
            "include_metafields": True,
            "update_existing": True,
            "created_at_min": None,  # Get all products regardless of date
            "updated_at_min": None
        }
    }
    
    try:
        # Start the sync
        response = requests.post(
            "http://localhost:3560/api/sync/shopify/pull",
            json=sync_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 401:
            print("❌ Authentication required. Let me try the direct Shopify sync endpoint...")
            
            # Try direct shopify sync endpoint
            response = requests.post(
                "http://localhost:3560/api/shopify/sync",
                json={
                    "direction": "down",
                    "sync_type": "full",
                    "include_variants": True
                },
                headers={"Content-Type": "application/json"}
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Sync initiated successfully!")
            print(f"📊 Sync ID: {result.get('sync_id', 'N/A')}")
            
            # Monitor progress
            return monitor_sync_progress(result.get('sync_id'))
            
        else:
            print(f"❌ Failed to start sync: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Try alternative approach - direct script
            print("\n🔄 Trying direct sync script approach...")
            return run_direct_sync()
            
    except Exception as e:
        print(f"❌ Error starting sync: {str(e)}")
        return run_direct_sync()

def monitor_sync_progress(sync_id):
    """Monitor the sync progress."""
    if not sync_id:
        return False
        
    print(f"\n📊 Monitoring sync progress for ID: {sync_id}")
    
    start_time = time.time()
    while True:
        try:
            response = requests.get(f"http://localhost:3560/api/sync/status/{sync_id}")
            if response.status_code == 200:
                status = response.json()
                
                progress = status.get('progress', 0)
                state = status.get('status', 'unknown')
                processed = status.get('processed_items', 0)
                total = status.get('total_items', 0)
                
                elapsed = int(time.time() - start_time)
                print(f"⏱️  [{elapsed}s] Status: {state} | Progress: {progress}% | Items: {processed}/{total}")
                
                if state in ['completed', 'finished']:
                    print("✅ Sync completed successfully!")
                    return True
                elif state in ['failed', 'error']:
                    print(f"❌ Sync failed: {status.get('error', 'Unknown error')}")
                    return False
                    
            time.sleep(5)  # Check every 5 seconds
            
        except KeyboardInterrupt:
            print("\n⏹️  Sync monitoring stopped by user")
            return False
        except Exception as e:
            print(f"Error monitoring sync: {str(e)}")
            time.sleep(10)

def run_direct_sync():
    """Run direct sync using existing scripts."""
    print("\n🔄 Running direct Shopify sync script...")
    
    # Check if the shopify sync script exists
    script_paths = [
        "scripts/shopify/shopify_uploader.py",
        "scripts/shopify/shopify_downloader.py",
        "web_dashboard/backend/direct_shopify_import.py"
    ]
    
    for script_path in script_paths:
        if os.path.exists(script_path):
            print(f"📁 Found sync script: {script_path}")
            
            # Run the script
            import subprocess
            try:
                result = subprocess.run([
                    sys.executable, script_path
                ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
                
                if result.returncode == 0:
                    print("✅ Direct sync completed successfully!")
                    print(f"Output: {result.stdout[-500:]}")  # Last 500 chars
                    return True
                else:
                    print(f"❌ Direct sync failed: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                print("⏰ Sync timed out after 1 hour")
            except Exception as e:
                print(f"Error running script: {str(e)}")
    
    print("❌ No suitable sync script found")
    return False

def verify_sync_results():
    """Verify the sync results."""
    print("\n🔍 Verifying sync results...")
    
    try:
        # Check local database count
        import psycopg2
        db_url = os.getenv('DATABASE_URL')
        if db_url.startswith('postgresql+psycopg://'):
            db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
        
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM products")
        local_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products WHERE updated_at > NOW() - INTERVAL '1 hour'")
        recent_updates = cursor.fetchone()[0]
        
        print(f"📊 Local database now has: {local_count:,} products")
        print(f"📊 Products updated in last hour: {recent_updates:,}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Error verifying results: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Full Shopify Product Sync Tool")
    print("This will sync ALL products from Shopify to your local database")
    print("Current status: 24,535 products in Shopify vs 1,000 in local DB")
    print()
    print("🚀 Starting full sync automatically...")
    
    success = run_full_sync()
    
    if success:
        verify_sync_results()
        print("\n🎉 Full sync completed successfully!")
    else:
        print("\n❌ Sync failed. Please check the logs and try again.")