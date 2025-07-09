#!/usr/bin/env python3
"""
Extract remaining products from deletion list starting from a specific position
Based on the knowledge that approximately 295 products were processed
"""

import csv
from pathlib import Path
from datetime import datetime

def extract_remaining(input_file: str, start_position: int = 295):
    """Extract products from position onwards"""
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_products = list(reader)
    
    # Get remaining products
    remaining_products = all_products[start_position:]
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path(input_file).parent / f"remaining_to_delete_{timestamp}.csv"
    
    # Save remaining products
    if remaining_products:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=remaining_products[0].keys())
            writer.writeheader()
            writer.writerows(remaining_products)
    
    print(f"Original list had {len(all_products)} products")
    print(f"Approximately {start_position} were processed")
    print(f"Remaining products: {len(remaining_products)}")
    print(f"\nSaved to: {output_file}")
    
    # Show sample of remaining products
    print("\nFirst 5 remaining products:")
    for i, product in enumerate(remaining_products[:5], 1):
        print(f"  {i}. SKU: {product.get('sku', '')}, Title: {product.get('title', 'No title')}")
    
    return str(output_file)

if __name__ == "__main__":
    data_dir = Path(__file__).parent.parent.parent / "data"
    input_file = data_dir / "products_to_delete_20250627_160334.csv"
    
    if input_file.exists():
        output_file = extract_remaining(str(input_file), start_position=295)
        print(f"\nTo delete the remaining products, run:")
        print(f"python scripts/shopify/delete_products_by_sku.py {output_file}")
    else:
        print(f"Error: Input file not found: {input_file}")