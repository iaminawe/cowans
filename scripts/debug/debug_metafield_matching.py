#!/usr/bin/env python3
import csv
import sys
import os

def normalize_id(id_str):
    """Normalize an ID by removing hyphens and converting to uppercase."""
    if not id_str:
        return ""
    return id_str.replace("-", "").upper()

def debug_metafield_matching(cowans_file, xorosoft_file):
    """Debug the metafield matching process."""
    # Read and index Xorosoft file by BasePartNumber
    base_part_to_item = {}
    base_part_counts = 0
    
    print(f"Reading and indexing Xorosoft file...")
    with open(xorosoft_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            if 'BasePartNumber' in row and row.get('BasePartNumber'):
                base_part = normalize_id(row['BasePartNumber'])
                if base_part:
                    base_part_counts += 1
                    if base_part not in base_part_to_item:
                        base_part_to_item[base_part] = []
                    base_part_to_item[base_part].append({
                        'item_number': row['ItemNumber'],
                        'base_part': row['BasePartNumber']
                    })
    
    print(f"Found {base_part_counts} BasePartNumber values, {len(base_part_to_item)} unique normalized values")
    
    # Process Cowans file and check for matches
    metafields = [
        'Metafield: custom.CWS_A[list.single_line_text]',
        'Metafield: custom.CWS_Catalog[list.single_line_text]',
        'Metafield: custom.SPRC[list.single_line_text]'
    ]
    
    field_stats = {field: {'total': 0, 'matched': 0} for field in metafields}
    matches = []
    
    print(f"Processing Cowans file to find matches...")
    with open(cowans_file, 'r', encoding='latin1') as f:
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader):
            if i % 10000 == 0:
                print(f"Processed {i} rows...")
            
            for field in metafields:
                field_value = row.get(field, '')
                if field_value:
                    field_stats[field]['total'] += 1
                    normalized_value = normalize_id(field_value)
                    
                    if normalized_value in base_part_to_item:
                        field_stats[field]['matched'] += 1
                        if len(matches) < 10:
                            matches.append({
                                'sku': row.get('SKU', ''),
                                'field': field,
                                'field_value': field_value,
                                'normalized_value': normalized_value,
                                'matched_to': base_part_to_item[normalized_value][0]['base_part'],
                                'item_number': base_part_to_item[normalized_value][0]['item_number']
                            })
    
    # Print results
    print("\nMatching Results:")
    for field in metafields:
        stats = field_stats[field]
        match_rate = (stats['matched'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"{field}: {stats['matched']} matches out of {stats['total']} values ({match_rate:.2f}%)")
    
    print("\nSample Matches:")
    for match in matches:
        print(f"SKU: {match['sku']}")
        print(f"  {match['field']} = {match['field_value']}")
        print(f"  Normalized: {match['normalized_value']}")
        print(f"  Matched to BasePartNumber: {match['matched_to']} (ItemNumber: {match['item_number']})")
        print()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python debug_metafield_matching.py <cowans_file> <xorosoft_file>")
        sys.exit(1)
    
    cowans_file = sys.argv[1]
    xorosoft_file = sys.argv[2]
    
    if not os.path.exists(cowans_file):
        print(f"Error: Cowans file '{cowans_file}' not found")
        sys.exit(1)
    
    if not os.path.exists(xorosoft_file):
        print(f"Error: Xorosoft file '{xorosoft_file}' not found")
        sys.exit(1)
    
    debug_metafield_matching(cowans_file, xorosoft_file)
