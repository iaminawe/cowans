#!/usr/bin/env python3
"""
Merge stocked products CSV with products final CSV
Sets published field based on whether product is in stocked list
"""

import csv
import sys
import os
from typing import Dict, Set

def read_stocked_handles(stocked_file: str) -> Set[str]:
    """Read stocked products and return set of handles."""
    stocked_handles = set()
    
    with open(stocked_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            handle = row.get('url handle', '').strip()
            if handle:
                stocked_handles.add(handle)
    
    return stocked_handles

def merge_with_stock_status(products_file: str, stocked_handles: Set[str], output_file: str) -> None:
    """Merge products with stock status."""
    
    # Read all rows from products file
    with open(products_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    # Update published status based on stocked handles
    updated_count = 0
    stocked_count = 0
    
    for row in rows:
        handle = row.get('url handle', '').strip()
        
        # Set published status based on whether handle is in stocked list
        if handle in stocked_handles:
            row['published'] = 'True'
            stocked_count += 1
        else:
            row['published'] = 'False'
        
        # Set inventory policy for all products
        # In Shopify CSV format:
        # - 'continue' = YES, continue selling when out of stock (allows backorders)
        # - 'deny' = NO, stop selling when out of stock
        # You requested "Continue Selling when out of stock" = TRUE
        row['continue selling when out of stock'] = 'continue'
        
        updated_count += 1
    
    # Write updated data
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    # Print summary
    print(f"✅ Merge completed successfully!")
    print(f"📊 Summary:")
    print(f"   - Total products processed: {updated_count}")
    print(f"   - Products marked as published (stocked): {stocked_count}")
    print(f"   - Products marked as unpublished (not stocked): {updated_count - stocked_count}")
    print(f"   - Output file: {output_file}")

def main():
    """Main function to handle command line arguments and run merge."""
    if len(sys.argv) != 4:
        print("Usage: python merge_stocked_products.py <products_final.csv> <stocked.csv> <output.csv>")
        print("\nExample:")
        print("  python merge_stocked_products.py data/cowans_products_final.csv data/cowans_stocked.csv data/cowans_products_merged.csv")
        sys.exit(1)
    
    products_file = sys.argv[1]
    stocked_file = sys.argv[2]
    output_file = sys.argv[3]
    
    # Validate input files exist
    if not os.path.exists(products_file):
        print(f"❌ Error: Products file '{products_file}' not found")
        sys.exit(1)
    
    if not os.path.exists(stocked_file):
        print(f"❌ Error: Stocked file '{stocked_file}' not found")
        sys.exit(1)
    
    print(f"📁 Reading stocked products from: {stocked_file}")
    stocked_handles = read_stocked_handles(stocked_file)
    print(f"   Found {len(stocked_handles)} stocked products")
    
    print(f"\n📁 Processing products file: {products_file}")
    merge_with_stock_status(products_file, stocked_handles, output_file)

if __name__ == "__main__":
    main()