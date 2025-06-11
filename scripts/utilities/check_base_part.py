#!/usr/bin/env python3
import csv
import sys

def check_base_part(file_path):
    """Check for non-empty BasePartNumber values in the CSV file."""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        # Count of rows with non-empty BasePartNumber
        count = 0
        examples = []
        
        # Process rows
        for i, row in enumerate(reader):
            if 'BasePartNumber' in row and row['BasePartNumber']:
                count += 1
                if len(examples) < 5:
                    examples.append({
                        'ItemNumber': row.get('ItemNumber', ''),
                        'BasePartNumber': row['BasePartNumber']
                    })
            
            # Print progress every 10,000 rows
            if i % 10000 == 0:
                print(f"Processed {i} rows...")
        
        # Print results
        print("\nResults:")
        print(f"BasePartNumber: {count} non-empty values")
        if examples:
            print("Examples:")
            for ex in examples:
                print(f"  ItemNumber: {ex['ItemNumber']}, BasePartNumber: {ex['BasePartNumber']}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        check_base_part(sys.argv[1])
    else:
        print("Usage: python check_base_part.py <csv_file>")
