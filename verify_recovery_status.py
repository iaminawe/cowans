#!/usr/bin/env python3
"""
Verify the current recovery status
"""
import os
from dotenv import load_dotenv
from supabase import create_client
import requests

# Load environment variables
load_dotenv()

def verify_recovery_status():
    """Verify current recovery status."""
    try:
        # Get credentials
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        shopify_shop_url = os.getenv('SHOPIFY_SHOP_URL')
        shopify_access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not all([supabase_url, supabase_key, shopify_shop_url, shopify_access_token]):
            print("❌ Missing required credentials")
            return
        
        print("🔍 RECOVERY STATUS VERIFICATION")
        print("=" * 50)
        
        # Create Supabase client
        supabase = create_client(supabase_url, supabase_key)
        
        # Check database state
        print("\n📊 DATABASE STATUS:")
        total_result = supabase.table('products').select('id', count='exact').execute()
        total_count = total_result.count if hasattr(total_result, 'count') else 0
        print(f"  Total products: {total_count}")
        
        # Check products with Shopify ID
        shopify_result = supabase.table('products').select('id', count='exact').not_.is_('shopify_product_id', 'null').execute()
        shopify_count = shopify_result.count if hasattr(shopify_result, 'count') else 0
        print(f"  Products with Shopify ID: {shopify_count}")
        
        # Check Shopify store
        print("\n🛍️  SHOPIFY STORE STATUS:")
        shopify_base_url = f"https://{shopify_shop_url}"
        headers = {
            'X-Shopify-Access-Token': shopify_access_token,
            'Content-Type': 'application/json'
        }
        
        # Get total product count from Shopify
        url = f"{shopify_base_url}/admin/api/2023-10/products/count.json"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            count_data = response.json()
            shopify_total = count_data.get('count', 0)
            print(f"  Total products in Shopify: {shopify_total}")
        else:
            print(f"  ❌ Could not get Shopify count: {response.status_code}")
            shopify_total = 0
        
        # Analysis
        print("\n📈 ANALYSIS:")
        print(f"  Originally had: ~24,535 products")
        print(f"  Accidentally deleted: ~23,535 products")
        print(f"  Currently have: {total_count} products")
        print(f"  Products in Shopify: {shopify_total}")
        
        if shopify_total > 0:
            recovery_percentage = (total_count / shopify_total) * 100
            print(f"  Recovery percentage: {recovery_percentage:.1f}%")
            
            if recovery_percentage > 80:
                print("  ✅ Recovery appears successful!")
            elif recovery_percentage > 50:
                print("  ⚠️  Partial recovery - need more products")
            else:
                print("  ❌ Recovery incomplete - major data loss")
        
        # Check if we need to recover more
        missing_count = shopify_total - total_count
        if missing_count > 0:
            print(f"\n🚨 MISSING: {missing_count} products still need to be recovered")
            print("  Recommend running full recovery script")
        else:
            print(f"\n✅ COMPLETE: All products appear to be recovered!")
            print("  No further recovery needed")
        
        # Show sample of existing products
        print("\n📋 SAMPLE PRODUCTS:")
        sample_result = supabase.table('products')\
            .select('name, shopify_product_id, created_at')\
            .limit(5)\
            .execute()
        
        if sample_result.data:
            for product in sample_result.data:
                print(f"  - {product.get('name', 'Unknown')} (ID: {product.get('shopify_product_id', 'None')})")
        
    except Exception as e:
        print(f"❌ Error in verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_recovery_status()