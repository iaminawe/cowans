#!/usr/bin/env python3
"""
Test script to debug file size-based duplicate detection.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.shopify.shopify_uploader import ShopifyUploader

def test_product_images(shop_url: str, access_token: str, product_handle: str):
    """Test file size detection for a specific product."""
    uploader = ShopifyUploader(shop_url=shop_url, access_token=access_token, debug=True)
    
    # Get product by handle
    result = uploader.execute_graphql("""
    query getProductByHandle($handle: String!) {
      productByHandle(handle: $handle) {
        id
        title
      }
    }
    """, {'handle': product_handle})
    
    if 'errors' in result:
        print(f"Error getting product: {result['errors']}")
        return
    
    product = result.get('data', {}).get('productByHandle')
    if not product:
        print(f"Product not found: {product_handle}")
        return
    
    product_id = product['id']
    print(f"Testing product: {product['title']}")
    print(f"Product ID: {product_id}")
    
    # Get existing images
    existing_images = uploader.get_product_images(product_id)
    print(f"Found {len(existing_images)} images:")
    
    # Test file size detection
    file_sizes = {}
    for i, img in enumerate(existing_images, 1):
        url = img['originalSrc']
        filename = url.split('/')[-1].split('?')[0]
        file_size = uploader.get_image_file_size(url)
        
        print(f"  {i}. {filename}")
        print(f"     URL: {url}")
        print(f"     File size: {file_size} bytes ({file_size/1024:.2f} KB)" if file_size else "     File size: Unable to get")
        print(f"     Image ID: {img['id']}")
        
        if file_size:
            if file_size in file_sizes:
                file_sizes[file_size].append((filename, img['id']))
            else:
                file_sizes[file_size] = [(filename, img['id'])]
        print()
    
    # Check for duplicates
    print("Duplicate analysis:")
    duplicates_found = False
    for file_size, images in file_sizes.items():
        if len(images) > 1:
            duplicates_found = True
            print(f"  🚨 DUPLICATES FOUND - File size: {file_size} bytes ({file_size/1024:.2f} KB)")
            for i, (filename, img_id) in enumerate(images):
                status = "KEEP" if i == 0 else "REMOVE"
                print(f"    {status}: {filename} (ID: {img_id})")
            print()
    
    if not duplicates_found:
        print("  ✅ No duplicates found")
    
    # Test the duplicate finding function
    print("Testing find_duplicate_images_by_size function:")
    duplicate_groups = uploader.find_duplicate_images_by_size(existing_images)
    print(f"Found {len(duplicate_groups)} duplicate groups")
    
    for i, group in enumerate(duplicate_groups, 1):
        print(f"  Group {i}: {len(group)} images")
        for img in group:
            filename = img['originalSrc'].split('/')[-1].split('?')[0]
            print(f"    - {filename} (ID: {img['id']})")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python test_file_size_detection.py <shop_url> <access_token> <product_handle>")
        print("Example: python test_file_size_detection.py e19833-4.myshopify.com TOKEN ricoh-scansnap-ix1600-large-format-adf-scanner-600-dpi-optical-pa03770-b615")
        sys.exit(1)
    
    shop_url = sys.argv[1]
    access_token = sys.argv[2]
    product_handle = sys.argv[3]
    
    test_product_images(shop_url, access_token, product_handle)