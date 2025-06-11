#!/usr/bin/env python3
import csv
import sys

def normalize_id(id_str):
    """Normalize an ID by removing hyphens and converting to uppercase."""
    if not id_str:
        return ""
    return id_str.replace("-", "").upper()

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_base_part_mapping.py <reference_file>")
        sys.exit(1)
    
    reference_file = sys.argv[1]
    
    # Read and index reference file
    base_part_to_item = {}
    base_part_examples = []
    
    print(f"Reading reference file: {reference_file}")
    
    with open(reference_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        if 'BasePartNumber' not in reader.fieldnames:
            print("Error: BasePartNumber column not found in reference file")
            print(f"Available columns: {', '.join(reader.fieldnames)}")
            sys.exit(1)
            
        total_rows = 0
        non_empty_base_part = 0
        
        for row in reader:
            total_rows += 1
            
            if row.get('BasePartNumber'):
                non_empty_base_part += 1
                base_part = normalize_id(row['BasePartNumber'])
                
                if base_part:
                    if base_part not in base_part_to_item:
                        base_part_to_item[base_part] = []
                        
                        # Store some examples for debugging
                        if len(base_part_examples) < 20:
                            base_part_examples.append({
                                'original': row['BasePartNumber'],
                                'normalized': base_part,
                                'item_number': row.get('ItemNumber', '')
                            })
                    
                    base_part_to_item[base_part].append({
                        'item_number': row.get('ItemNumber', ''),
                        'normalized_id': normalize_id(row.get('ItemNumber', ''))
                    })
    
    print(f"Total rows in reference file: {total_rows}")
    print(f"Rows with non-empty BasePartNumber: {non_empty_base_part}")
    print(f"Unique normalized BasePartNumber values: {len(base_part_to_item)}")
    
    print("\nExample BasePartNumber values:")
    for example in base_part_examples:
        print(f"Original: '{example['original']}', Normalized: '{example['normalized']}', ItemNumber: '{example['item_number']}'")
    
    # Now test some specific values
    test_values = [
        'BAO0600900',  # From debug output
        'BAO1300200',
        'BAO1309200',
        'HEWC2P24AN140'
    ]
    
    print("\nTesting specific values:")
    for value in test_values:
        print(f"Value: '{value}', In base_part_to_item: {value in base_part_to_item}")
        if value in base_part_to_item:
            print(f"  Matches: {len(base_part_to_item[value])}")
            for match in base_part_to_item[value][:3]:  # Show up to 3 matches
                print(f"  - ItemNumber: {match['item_number']}")
    
    # Now read the primary file to check some metafields
    if len(sys.argv) >= 3:
        primary_file = sys.argv[2]
        print(f"\nReading primary file: {primary_file}")
        
        with open(primary_file, 'r', encoding='latin1') as f:
            reader = csv.DictReader(f)
            
            metafield_columns = [
                'Metafield: custom.CWS_A[list.single_line_text]',
                'Metafield: custom.CWS_Catalog[list.single_line_text]',
                'Metafield: custom.SPRC[list.single_line_text]'
            ]
            
            for col in metafield_columns:
                if col not in reader.fieldnames:
                    print(f"Warning: {col} not found in primary file")
            
            sample_rows = []
            for row in reader:
                if (row.get('Metafield: custom.CWS_A[list.single_line_text]') or
                    row.get('Metafield: custom.CWS_Catalog[list.single_line_text]') or
                    row.get('Metafield: custom.SPRC[list.single_line_text]')):
                    
                    sample_rows.append(row)
                    if len(sample_rows) >= 10:
                        break
            
            print(f"\nSample rows with metafields:")
            for row in sample_rows:
                print(f"\nSKU: {row.get('SKU', '')}")
                
                for field_name in metafield_columns:
                    short_name = field_name.split('.')[1].split('[')[0]
                    value = row.get(field_name, '')
                    if value:
                        normalized = normalize_id(value)
                        in_dict = normalized in base_part_to_item
                        print(f"  {short_name}: '{value}' (normalized: '{normalized}', in dict: {in_dict})")
                        if in_dict:
                            print(f"    Matches: {len(base_part_to_item[normalized])}")
                            for match in base_part_to_item[normalized][:2]:  # Show up to 2 matches
                                print(f"    - ItemNumber: {match['item_number']}")

if __name__ == "__main__":
    main()
