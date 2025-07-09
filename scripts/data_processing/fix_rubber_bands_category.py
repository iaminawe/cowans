#!/usr/bin/env python3
"""
Fix categorization for rubber band products that are only categorized as generic "Office Supplies"
"""

import csv
import sys

def fix_rubber_bands_category(input_file, output_file):
    """Fix rubber band products categorization."""
    
    rubber_bands_fixed = 0
    total_processed = 0
    
    # Read all data
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = []
        
        for row in reader:
            total_processed += 1
            
            # Check if this is a rubber band product with generic categorization
            product_type = row.get('product_type', '').lower()
            tags = row.get('tags', '').lower()
            category_name = row.get('category_name', '')
            category_gid = row.get('category_gid', '')
            
            # Identify rubber bands that need better categorization
            is_rubber_band = (
                'rubber band' in product_type or
                'rubber bands' in tags or
                (row.get('title', '').lower().find('rubber band') >= 0 and 
                 'pen' not in row.get('title', '').lower() and
                 'pencil' not in row.get('title', '').lower())
            )
            
            # Check if it's only categorized as generic "Office Supplies"
            if is_rubber_band and category_name == 'Office Supplies' and category_gid == 'gid://shopify/TaxonomyCategory/os':
                # Update to more specific category
                row['category_name'] = 'Office Supplies > Fasteners & Rubber Bands'
                row['category_gid'] = 'gid://shopify/TaxonomyCategory/os-3'  # Fasteners & Rubber Bands
                row['category_confidence'] = '95'  # High confidence since product_type confirms it
                rubber_bands_fixed += 1
                
                print(f"Fixed: {row['newsku']} - {row['title']}")
            
            rows.append(row)
    
    # Write updated data
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n✅ Categorization Fix Complete!")
    print(f"📊 Summary:")
    print(f"   - Total products processed: {total_processed}")
    print(f"   - Rubber bands re-categorized: {rubber_bands_fixed}")
    print(f"   - Output file: {output_file}")
    
    return rubber_bands_fixed

def verify_rubber_bands(csv_file):
    """Verify all rubber band products and their categories."""
    
    print("\n=== RUBBER BAND PRODUCTS VERIFICATION ===\n")
    
    rubber_band_categories = {}
    rubber_band_products = []
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            product_type = row.get('product_type', '').lower()
            tags = row.get('tags', '').lower()
            title = row.get('title', '').lower()
            
            # Find all rubber band products
            if ('rubber band' in product_type or 
                'rubber bands' in tags or
                ('rubber band' in title and 'pen' not in title and 'pencil' not in title)):
                
                category = row.get('category_name', 'Unknown')
                rubber_band_categories[category] = rubber_band_categories.get(category, 0) + 1
                
                if category == 'Office Supplies':  # Generic category
                    rubber_band_products.append({
                        'sku': row.get('newsku', ''),
                        'title': row.get('title', ''),
                        'product_type': row.get('product_type', ''),
                        'category': category,
                        'category_gid': row.get('category_gid', '')
                    })
    
    print("Category distribution for rubber band products:")
    for category, count in sorted(rubber_band_categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count}")
    
    if rubber_band_products:
        print(f"\n⚠️  Found {len(rubber_band_products)} rubber band products with generic categorization:")
        for i, product in enumerate(rubber_band_products[:10], 1):  # Show first 10
            print(f"\n{i}. {product['sku']} - {product['title']}")
            print(f"   Product Type: {product['product_type']}")
            print(f"   Current Category: {product['category']}")
            print(f"   Current GID: {product['category_gid']}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_rubber_bands_category.py <input_csv> [output_csv]")
        print("\nTo verify current state:")
        print("  python fix_rubber_bands_category.py data/cowans_products_merged_final.csv --verify")
        print("\nTo fix categorization:")
        print("  python fix_rubber_bands_category.py data/cowans_products_merged_final.csv data/cowans_products_fixed_categories.csv")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if len(sys.argv) > 2 and sys.argv[2] == '--verify':
        # Just verify current state
        verify_rubber_bands(input_file)
    else:
        # Fix categorization
        output_file = sys.argv[2] if len(sys.argv) > 2 else 'data/cowans_products_fixed_categories.csv'
        fix_rubber_bands_category(input_file, output_file)