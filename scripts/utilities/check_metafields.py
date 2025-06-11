#!/usr/bin/env python3
import csv
import sys

def check_metafields(file_path):
    """Check for non-empty metafield values in the CSV file."""
    with open(file_path, 'r', encoding='latin1') as f:
        reader = csv.DictReader(f)
        
        # Metafields to check
        metafields = [
            'Metafield: custom.CWS_A[list.single_line_text]',
            'Metafield: custom.CWS_Catalog[list.single_line_text]',
            'Metafield: custom.SPRC[list.single_line_text]'
        ]
        
        # Count of rows with non-empty metafields
        counts = {field: 0 for field in metafields}
        examples = {field: [] for field in metafields}
        
        # Process rows
        for i, row in enumerate(reader):
            for field in metafields:
                if field in row and row[field]:
                    counts[field] += 1
                    if len(examples[field]) < 3:
                        examples[field].append({
                            'SKU': row.get('SKU', ''),
                            'value': row[field]
                        })
            
            # Print progress every 10,000 rows
            if i % 10000 == 0:
                print(f"Processed {i} rows...")
        
        # Print results
        print("\nResults:")
        for field in metafields:
            print(f"{field}: {counts[field]} non-empty values")
            if examples[field]:
                print("Examples:")
                for ex in examples[field]:
                    print(f"  SKU: {ex['SKU']}, Value: {ex['value']}")
            print()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        check_metafields(sys.argv[1])
    else:
        print("Usage: python check_metafields.py <csv_file>")
