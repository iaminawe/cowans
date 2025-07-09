#!/usr/bin/env python3
"""
Analyze products categorized as Rubber Bands to find misclassifications
"""

import csv
import re
from collections import defaultdict

def analyze_rubber_bands_category(csv_file):
    """Analyze products in the rubber bands category."""
    
    rubber_band_products = []
    misclassified_pens = []
    other_misclassified = []
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            category_name = row.get('category_name', '').lower()
            
            # Check if categorized as rubber bands or office supplies (which might include rubber bands)
            if 'rubber band' in category_name or (category_name == 'office supplies' and 'rubber band' in row.get('product_type', '').lower()):
                product_info = {
                    'sku': row.get('newsku', ''),
                    'title': row.get('title', ''),
                    'handle': row.get('url handle', ''),
                    'product_type': row.get('product_type', ''),
                    'description': row.get('body_html', ''),
                    'category': category_name,
                    'confidence': row.get('category_confidence', '')
                }
                
                # Check if it's actually a pen with rubber grip
                title_lower = product_info['title'].lower()
                desc_lower = product_info['description'].lower()
                
                if any(word in title_lower for word in ['pen', 'marker', 'pencil', 'highlighter']):
                    if 'rubber' in title_lower or 'rubber' in desc_lower:
                        if 'grip' in title_lower or 'grip' in desc_lower or 'comfort' in title_lower:
                            misclassified_pens.append(product_info)
                            continue
                
                # Check for other misclassifications
                if any(word in title_lower for word in ['mop', 'band saw', 'bandage', 'wristband', 'headband']):
                    other_misclassified.append(product_info)
                else:
                    rubber_band_products.append(product_info)
    
    return rubber_band_products, misclassified_pens, other_misclassified

def print_analysis(rubber_bands, pens, others):
    """Print analysis results."""
    
    print("=== RUBBER BANDS CATEGORY ANALYSIS ===\n")
    
    print(f"Total products analyzed: {len(rubber_bands) + len(pens) + len(others)}")
    print(f"Correctly categorized rubber bands: {len(rubber_bands)}")
    print(f"Misclassified pens with rubber grips: {len(pens)}")
    print(f"Other misclassifications: {len(others)}")
    
    if pens:
        print(f"\n=== MISCLASSIFIED PENS ({len(pens)}) ===")
        for i, pen in enumerate(pens[:10], 1):  # Show first 10
            print(f"\n{i}. {pen['sku']} - {pen['title']}")
            print(f"   Category: {pen['category']} (confidence: {pen['confidence']})")
            print(f"   Product Type: {pen['product_type']}")
            # Extract rubber grip mentions
            desc_text = re.sub('<[^<]+?>', '', pen['description'])  # Remove HTML
            rubber_mentions = [line.strip() for line in desc_text.split('\n') if 'rubber' in line.lower()]
            if rubber_mentions:
                print(f"   Rubber mentions: {rubber_mentions[0][:100]}...")
    
    if others:
        print(f"\n=== OTHER MISCLASSIFICATIONS ({len(others)}) ===")
        for i, other in enumerate(others[:10], 1):  # Show first 10
            print(f"\n{i}. {other['sku']} - {other['title']}")
            print(f"   Category: {other['category']} (confidence: {other['confidence']})")
            print(f"   Product Type: {other['product_type']}")
    
    if len(rubber_bands) > 0:
        print(f"\n=== SAMPLE CORRECT RUBBER BANDS ({min(5, len(rubber_bands))}) ===")
        for i, rb in enumerate(rubber_bands[:5], 1):
            print(f"\n{i}. {rb['sku']} - {rb['title']}")
            print(f"   Product Type: {rb['product_type']}")

def generate_recategorization_csv(pens, others, output_file):
    """Generate CSV with suggested recategorizations."""
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['sku', 'title', 'current_category', 'suggested_category', 'suggested_category_gid', 'reason']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Pens should be categorized as Writing Instruments
        for pen in pens:
            writer.writerow({
                'sku': pen['sku'],
                'title': pen['title'],
                'current_category': pen['category'],
                'suggested_category': 'Writing Instruments',
                'suggested_category_gid': 'gid://shopify/TaxonomyCategory/os-2',  # Office Supplies > Writing Instruments
                'reason': 'Pen/marker with rubber grip, not a rubber band'
            })
        
        # Other misclassifications
        for other in others:
            title_lower = other['title'].lower()
            if 'mop' in title_lower:
                suggested_cat = 'Cleaning Supplies'
                suggested_gid = 'gid://shopify/TaxonomyCategory/hg-4-1'
            elif 'band saw' in title_lower:
                suggested_cat = 'Tools'
                suggested_gid = 'gid://shopify/TaxonomyCategory/t'
            else:
                suggested_cat = 'Office Supplies'
                suggested_gid = 'gid://shopify/TaxonomyCategory/os'
            
            writer.writerow({
                'sku': other['sku'],
                'title': other['title'],
                'current_category': other['category'],
                'suggested_category': suggested_cat,
                'suggested_category_gid': suggested_gid,
                'reason': f'Not a rubber band - appears to be {other["product_type"]}'
            })
    
    print(f"\n✅ Recategorization suggestions saved to: {output_file}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python analyze_rubber_bands_category.py <csv_file>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    # Analyze categories
    rubber_bands, pens, others = analyze_rubber_bands_category(csv_file)
    
    # Print analysis
    print_analysis(rubber_bands, pens, others)
    
    # Generate recategorization file if there are misclassifications
    if pens or others:
        output_file = 'data/rubber_bands_recategorization.csv'
        generate_recategorization_csv(pens, others, output_file)