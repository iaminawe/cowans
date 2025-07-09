#!/usr/bin/env python3
"""
Summarize the products that will be deleted
"""

import csv
from pathlib import Path
from collections import Counter

def summarize_deletions(csv_file: str):
    """Analyze and summarize products to be deleted"""
    products = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        products = list(reader)
    
    # Analyze by vendor
    vendor_counts = Counter(p.get('vendor', 'Unknown') for p in products)
    
    # Analyze by status
    status_counts = Counter(p.get('status', 'Unknown') for p in products)
    
    # Analyze by inventory
    with_inventory = sum(1 for p in products if int(p.get('inventory_qty', '0')) > 0)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"DELETION SUMMARY FOR: {Path(csv_file).name}")
    print(f"{'='*60}")
    print(f"\nTotal products to delete: {len(products)}")
    
    print(f"\nBy Status:")
    for status, count in status_counts.most_common():
        print(f"  - {status}: {count}")
    
    print(f"\nBy Vendor (top 10):")
    for vendor, count in vendor_counts.most_common(10):
        print(f"  - {vendor}: {count}")
    
    print(f"\nInventory:")
    print(f"  - With inventory > 0: {with_inventory}")
    print(f"  - With no inventory: {len(products) - with_inventory}")
    
    # Show some sample products
    print(f"\nSample products to be deleted:")
    for i, p in enumerate(products[:10], 1):
        print(f"  {i}. SKU: {p.get('sku', '')}")
        print(f"     Title: {p.get('title', 'No title')}")
        print(f"     Vendor: {p.get('vendor', 'Unknown')}")
        print(f"     Price: ${p.get('price', '0')}")
        print(f"     Inventory: {p.get('inventory_qty', '0')}")
        print()
    
    if len(products) > 10:
        print(f"  ... and {len(products) - 10} more products")
    
    print(f"\n{'='*60}")
    print("IMPORTANT: Make sure you have a backup before proceeding!")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    data_dir = Path(__file__).parent.parent.parent / "data"
    csv_file = data_dir / "products_to_delete_20250627_160334.csv"
    
    if csv_file.exists():
        summarize_deletions(str(csv_file))
    else:
        print(f"Error: File not found: {csv_file}")