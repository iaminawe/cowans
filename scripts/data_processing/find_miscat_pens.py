#!/usr/bin/env python3
"""
Find pens with rubber grips and check their categorization
"""

import csv
import re

def find_rubber_grip_pens(csv_file):
    """Find all pens with rubber grips and their categories."""
    
    rubber_grip_pens = []
    category_counts = {}
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            title = row.get('title', '').lower()
            description = row.get('body_html', '').lower()
            product_type = row.get('product_type', '').lower()
            
            # Check if it's a pen/marker/pencil
            is_writing_instrument = any(word in title or word in product_type for word in ['pen', 'marker', 'pencil', 'highlighter'])
            
            if is_writing_instrument:
                # Check if it mentions rubber grip
                has_rubber_grip = (
                    ('rubber' in title and 'grip' in title) or
                    ('rubber' in description and 'grip' in description) or
                    'rubber grip' in title or
                    'rubber grip' in description or
                    'rubberized grip' in title or
                    'rubberized grip' in description
                )
                
                if has_rubber_grip:
                    category = row.get('category_name', 'Unknown')
                    rubber_grip_pens.append({
                        'sku': row.get('newsku', ''),
                        'title': row.get('title', ''),
                        'product_type': row.get('product_type', ''),
                        'category': category,
                        'category_gid': row.get('category_gid', ''),
                        'confidence': row.get('category_confidence', '')
                    })
                    
                    # Count categories
                    category_counts[category] = category_counts.get(category, 0) + 1
    
    return rubber_grip_pens, category_counts

def print_findings(pens, category_counts):
    """Print findings about pens with rubber grips."""
    
    print(f"=== PENS WITH RUBBER GRIPS ANALYSIS ===\n")
    print(f"Total pens with rubber grips found: {len(pens)}")
    
    if category_counts:
        print(f"\nCategory distribution:")
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {category}: {count}")
    
    # Show samples from each category
    categories_shown = set()
    print(f"\n=== SAMPLE PENS BY CATEGORY ===")
    
    for pen in pens:
        if pen['category'] not in categories_shown:
            print(f"\nCategory: {pen['category']}")
            print(f"  SKU: {pen['sku']}")
            print(f"  Title: {pen['title']}")
            print(f"  Product Type: {pen['product_type']}")
            print(f"  Category GID: {pen['category_gid']}")
            print(f"  Confidence: {pen['confidence']}")
            categories_shown.add(pen['category'])
            
            # Show a few more from this category
            same_cat_pens = [p for p in pens if p['category'] == pen['category'] and p['sku'] != pen['sku']]
            for i, other_pen in enumerate(same_cat_pens[:2]):
                print(f"  Also in this category: {other_pen['sku']} - {other_pen['title']}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python find_miscat_pens.py <csv_file>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    # Find pens with rubber grips
    pens, category_counts = find_rubber_grip_pens(csv_file)
    
    # Print findings
    print_findings(pens, category_counts)