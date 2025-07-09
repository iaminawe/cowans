#!/usr/bin/env python3
"""
Download Collection Images Script

This script downloads all collection images from the export data,
organizing them for easy upload to the new Shopify store.

Usage:
    python download_collection_images.py --input-file old_shopify_complete_collections/collections_images.csv --output-dir collection_images
"""

import os
import csv
import argparse
import requests
import time
from urllib.parse import urlparse
from pathlib import Path

def download_collection_images(input_file: str, output_dir: str) -> None:
    """Download all collection images from CSV."""
    print(f"📸 Starting collection image downloads...")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Load image data
    images = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        images = list(reader)
    
    print(f"📊 Found {len(images)} collection images to download")
    
    downloaded = 0
    skipped = 0
    errors = 0
    
    for idx, image_data in enumerate(images, 1):
        handle = image_data['collection_handle']
        title = image_data['collection_title']
        image_url = image_data['image_url']
        alt_text = image_data.get('image_alt_text', '')
        
        if not image_url:
            skipped += 1
            continue
        
        print(f"\n[{idx}/{len(images)}] {handle}")
        print(f"   Title: {title}")
        
        try:
            # Parse URL to get extension
            parsed_url = urlparse(image_url)
            path_parts = parsed_url.path.split('/')
            filename = path_parts[-1] if path_parts else f"{handle}.jpg"
            
            # Remove query parameters from filename
            if '?' in filename:
                filename = filename.split('?')[0]
            
            # Ensure filename has an extension
            if '.' not in filename:
                filename = f"{handle}.jpg"
            else:
                # Use handle as base name but keep extension
                ext = filename.split('.')[-1]
                filename = f"{handle}.{ext}"
            
            filepath = os.path.join(output_dir, filename)
            
            # Skip if already downloaded
            if os.path.exists(filepath):
                print(f"   ⏭️  Already downloaded")
                skipped += 1
                continue
            
            # Download image
            print(f"   ⬇️  Downloading...")
            response = requests.get(image_url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; ShopifyMigration/1.0)'
            })
            response.raise_for_status()
            
            # Save image
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            # Save metadata
            metadata_file = os.path.join(output_dir, f"{handle}_metadata.txt")
            with open(metadata_file, 'w', encoding='utf-8') as f:
                f.write(f"Collection: {title}\n")
                f.write(f"Handle: {handle}\n")
                f.write(f"Alt Text: {alt_text}\n")
                f.write(f"Original URL: {image_url}\n")
                f.write(f"Filename: {filename}\n")
            
            downloaded += 1
            print(f"   ✅ Saved as: {filename}")
            
            # Rate limiting to be nice to CDN
            time.sleep(0.5)
            
        except requests.exceptions.RequestException as e:
            errors += 1
            print(f"   ❌ Download failed: {str(e)}")
        except Exception as e:
            errors += 1
            print(f"   ❌ Error: {str(e)}")
    
    print(f"\n✅ Download Summary:")
    print(f"   📸 Downloaded: {downloaded}")
    print(f"   ⏭️  Skipped: {skipped}")
    print(f"   ❌ Errors: {errors}")
    print(f"   📁 Images saved to: {output_dir}/")
    
    # Create upload instructions
    instructions_file = os.path.join(output_dir, "UPLOAD_INSTRUCTIONS.md")
    with open(instructions_file, 'w') as f:
        f.write("# Collection Image Upload Instructions\n\n")
        f.write("## Automated Upload (via Shopify Admin API)\n\n")
        f.write("The migration script will attempt to upload these images automatically.\n\n")
        f.write("## Manual Upload (via Shopify Admin)\n\n")
        f.write("If automatic upload fails, you can manually upload images:\n\n")
        f.write("1. Go to Shopify Admin > Collections\n")
        f.write("2. Find each collection by handle (filename without extension)\n")
        f.write("3. Click 'Edit collection'\n")
        f.write("4. Upload the corresponding image file\n")
        f.write("5. Set the alt text from the _metadata.txt file\n\n")
        f.write("## File Naming Convention\n\n")
        f.write("- Image files: `{collection-handle}.{extension}`\n")
        f.write("- Metadata files: `{collection-handle}_metadata.txt`\n")
    
    print(f"\n📝 Upload instructions saved to: {instructions_file}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Download collection images for migration'
    )
    parser.add_argument('--input-file', required=True, 
                       help='CSV file with collection image data')
    parser.add_argument('--output-dir', default='collection_images',
                       help='Directory to save images (default: collection_images)')
    
    args = parser.parse_args()
    
    try:
        download_collection_images(args.input_file, args.output_dir)
    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()