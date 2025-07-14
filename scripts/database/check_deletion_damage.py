#!/usr/bin/env python3
"""
Check what we accidentally deleted and see if we can recover
"""
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def check_deletion_damage():
    """Check what we accidentally deleted."""
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
        
        # Check current state
        print("\n❌ DELETION DAMAGE ASSESSMENT")
        print("=" * 50)
        
        # Check remaining products
        total_result = client.table('products').select('*', count='exact').execute()
        remaining_products = total_result.count if hasattr(total_result, 'count') else 0
        print(f"Remaining products: {remaining_products}")
        
        if total_result.data:
            # Check if any have shopify_product_id (were synced from Shopify)
            shopify_synced = [p for p in total_result.data if p.get('shopify_product_id')]
            print(f"Shopify-synced products remaining: {len(shopify_synced)}")
            
            # Sample of remaining products
            print(f"\nSample of remaining products:")
            for i, product in enumerate(total_result.data[:5]):
                print(f"  {i+1}. {product.get('name', 'No name')}")
                print(f"     SKU: {product.get('sku', 'No SKU')}")
                print(f"     Shopify ID: {product.get('shopify_product_id', 'None')}")
                print(f"     Category ID: {product.get('category_id', 'None')}")
                print()
        
        # Check what categories existed before
        print("\nRemaining categories:")
        categories_result = client.table('categories').select('*').execute()
        if categories_result.data:
            for cat in categories_result.data:
                prod_count_result = client.table('products').select('id', count='exact').eq('category_id', cat['id']).execute()
                prod_count = prod_count_result.count if hasattr(prod_count_result, 'count') else 0
                print(f"  ID: {cat['id']}, Name: {cat['name']}, Products: {prod_count}")
        
        # Check if we can find any backup or recent sync data
        print(f"\n🔍 LOOKING FOR RECOVERY OPTIONS...")
        
        # Check if there are any recent sync records or backups
        # This would depend on your specific backup strategy
        print("Checking for potential recovery sources...")
        
        # If you have a sync log or history table, check it here
        # For now, we'll suggest re-syncing from Shopify
        
        print(f"\n💡 RECOVERY RECOMMENDATIONS:")
        print("1. If you have database backups, restore from before the deletion")
        print("2. Re-sync products from Shopify using the sync functionality")
        print("3. Check if Shopify has all your products and re-import them")
        
        if remaining_products < 2000:  # Much lower than expected 24k
            print(f"\n⚠️  CRITICAL: We accidentally deleted {24000 - remaining_products}+ Shopify products!")
            print("   The 'Test Category' contained your real Shopify-synced products")
            print("   Need immediate recovery action")
        
    except Exception as e:
        print(f"Error checking deletion damage: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_deletion_damage()