#!/usr/bin/env python3
"""
Compare duplicate SKUs from duplicates_for_removal.csv with products_export_1-8.csv
to create a final list of products to delete from Shopify.
"""

import csv
import sys
from pathlib import Path
from datetime import datetime
from typing import Set, List, Dict

def load_duplicate_skus(duplicates_file: str) -> Set[str]:
    """Load SKUs from duplicates_for_removal.csv"""
    duplicate_skus = set()
    
    with open(duplicates_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        # Skip headers
        next(reader, None)
        next(reader, None)
        
        for row in reader:
            if row and row[0]:  # SKU is in first column
                sku = row[0].strip()
                if sku:
                    duplicate_skus.add(sku)
    
    return duplicate_skus

def find_products_to_delete(products_file: str, duplicate_skus: Set[str]) -> List[Dict]:
    """Find products in the export that match duplicate SKUs"""
    products_to_delete = []
    
    with open(products_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            variant_sku = row.get('Variant SKU', '').strip()
            
            if variant_sku in duplicate_skus:
                products_to_delete.append({
                    'sku': variant_sku,
                    'handle': row.get('Handle', ''),
                    'title': row.get('Title', ''),
                    'vendor': row.get('Vendor', ''),
                    'price': row.get('Variant Price', ''),
                    'inventory_qty': row.get('Variant Inventory Qty', ''),
                    'status': row.get('Status', '')
                })
    
    return products_to_delete

def save_deletion_list(products_to_delete: List[Dict], output_file: str):
    """Save the list of products to delete"""
    if not products_to_delete:
        print("No matching products found to delete.")
        return
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['sku', 'handle', 'title', 'vendor', 'price', 'inventory_qty', 'status']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(products_to_delete)
    
    print(f"Saved {len(products_to_delete)} products to delete in: {output_file}")

def main():
    # File paths
    data_dir = Path(__file__).parent.parent.parent / "data"
    duplicates_file = data_dir / "duplicates_for_removal.csv"
    products_file = data_dir / "products_export_1-8.csv"
    
    # Check if files exist
    if not duplicates_file.exists():
        print(f"Error: {duplicates_file} not found")
        sys.exit(1)
    
    if not products_file.exists():
        print(f"Error: {products_file} not found")
        sys.exit(1)
    
    # Load duplicate SKUs
    print(f"Loading duplicate SKUs from {duplicates_file}...")
    duplicate_skus = load_duplicate_skus(str(duplicates_file))
    print(f"Found {len(duplicate_skus)} duplicate SKUs")
    
    # Find products to delete
    print(f"Searching for matching products in {products_file}...")
    products_to_delete = find_products_to_delete(str(products_file), duplicate_skus)
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = data_dir / f"products_to_delete_{timestamp}.csv"
    
    # Save deletion list
    save_deletion_list(products_to_delete, str(output_file))
    
    # Print summary
    print("\nSummary:")
    print(f"- Total duplicate SKUs: {len(duplicate_skus)}")
    print(f"- Products found in export: {len(products_to_delete)}")
    print(f"- SKUs not found: {len(duplicate_skus - {p['sku'] for p in products_to_delete})}")
    
    # Show first few products to delete
    if products_to_delete:
        print("\nFirst 5 products to delete:")
        for i, product in enumerate(products_to_delete[:5]):
            print(f"  {i+1}. SKU: {product['sku']}, Title: {product['title']}")

if __name__ == "__main__":
    main()