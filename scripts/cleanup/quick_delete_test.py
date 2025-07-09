#!/usr/bin/env python3
"""
Quick test script to verify deletion works with a small subset of products
"""

import csv
import sys
from pathlib import Path

def create_test_file(input_file: str, output_file: str, limit: int = 5):
    """Create a test file with just a few products"""
    with open(input_file, 'r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        rows = list(reader)[:limit]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f_out:
        if rows:
            writer = csv.DictWriter(f_out, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    
    print(f"Created test file with {len(rows)} products: {output_file}")
    for i, row in enumerate(rows, 1):
        print(f"  {i}. SKU: {row.get('sku', '')}, Title: {row.get('title', '')}")

if __name__ == "__main__":
    data_dir = Path(__file__).parent.parent.parent / "data"
    input_file = data_dir / "products_to_delete_20250627_160334.csv"
    output_file = data_dir / "test_delete_5_products.csv"
    
    create_test_file(str(input_file), str(output_file), limit=5)
    print(f"\nTo test deletion with these 5 products:")
    print(f"python scripts/shopify/delete_products_by_sku.py {output_file}")