#!/usr/bin/env python3
import csv
import sys
import os
import json
from datetime import datetime

def normalize_id(id_str):
    """Normalize an ID by removing hyphens and converting to uppercase."""
    if not id_str:
        return ""
    return id_str.replace("-", "").upper()

def validate_required_columns(fieldnames, required_columns, file_type):
    """Validate that the required columns are present in the fieldnames."""
    for column in required_columns:
        if column not in fieldnames:
            print(f"Error: Required column '{column}' not found in {file_type} file.")
            print(f"Available columns: {', '.join(fieldnames)}")
            sys.exit(1)

def is_product_row(row):
    """Check if a row represents a main product (not an image variant)."""
    # For Cowans data
    return (row.get('Title') and row.get('SKU') and 
            row.get('Vendor') and row.get('Type'))

def filter_products(primary_file, reference_file, output_file=None, debug=False, use_metafields=True):
    """
    Filter products from primary file based on matching identifiers in reference file.
    Primary file must have 'SKU' column.
    Reference file must have 'ItemNumber' column.
    
    Parameters:
    - primary_file: Path to the primary CSV file (Cowans)
    - reference_file: Path to the reference CSV file (Xorosoft)
    - output_file: Optional path for the output file
    - debug: Enable debug output
    - use_metafields: Enable matching using metafields (CWS_A, CWS_Catalog, SPRC) against BasePartNumber
    
    The script checks for matches in the following order of priority:
    1. SKU
    2. Metafield: custom.CWS_A[list.single_line_text]
    3. Metafield: custom.CWS_Catalog[list.single_line_text]
    4. Metafield: custom.SPRC[list.single_line_text]
    
    The first matching field is stored in a new column called 'matchedSKU'.
    """
    # Generate output filenames
    datestamp = datetime.now().strftime("%Y%m%d")
    base_name = os.path.splitext(os.path.basename(primary_file))[0]
    
    if not output_file:
        output_dir = os.path.dirname(primary_file)
        output_file = os.path.join(output_dir, f"{base_name}_filtered_{datestamp}.csv")
    
    sample_matches_file = os.path.join(os.path.dirname(output_file), f"{base_name}_sample_matches_{datestamp}.csv")
    near_matches_file = os.path.join(os.path.dirname(output_file), f"{base_name}_near_matches_{datestamp}.csv")
    stats_file = os.path.join(os.path.dirname(output_file), f"{base_name}_matching_stats_{datestamp}.json")
    
    # Detect file encodings
    primary_encoding = 'latin1'  # Common for Cowans data
    ref_encoding = 'utf-8-sig'   # Common for Xorosoft data
    
    # Statistics tracking
    stats = {
        'total_primary_rows': 0,
        'total_primary_products': 0,
        'total_reference_skus': 0,
        'valid_reference_skus': 0,
        'matched_products': 0,
        'matched_by_sku': 0,
        'matched_by_metafield_cws_a': 0,
        'matched_by_metafield_cws_catalog': 0,
        'matched_by_metafield_sprc': 0,
        'empty_skus_primary': 0,
        'empty_skus_reference': 0,
        'near_matches': 0,
        'image_variant_rows': 0,
        'sample_matches': [],
        'sample_near_matches': []
    }
    
    # Define the fields to check in order of priority
    fields_to_check = [
        {'field': 'SKU', 'stat': 'matched_by_sku'},
        {'field': 'Metafield: custom.CWS_A[list.single_line_text]', 'stat': 'matched_by_metafield_cws_a'},
        {'field': 'Metafield: custom.CWS_Catalog[list.single_line_text]', 'stat': 'matched_by_metafield_cws_catalog'},
        {'field': 'Metafield: custom.SPRC[list.single_line_text]', 'stat': 'matched_by_metafield_sprc'}
    ]

    # Read and index reference file
    valid_skus = {}
    base_part_to_item = {}  # Map from BasePartNumber to ItemNumber
    print(f"Reading and indexing reference file...")
    with open(reference_file, 'r', encoding=ref_encoding) as f:
        reader = csv.DictReader(f)
        validate_required_columns(reader.fieldnames, ['ItemNumber'], "reference")
        
        # Check if BasePartNumber column exists
        has_base_part = 'BasePartNumber' in reader.fieldnames
        if has_base_part and use_metafields:
            print("Found BasePartNumber column in reference file, will use for metafield matching")
        
        for row in reader:
            stats['total_reference_skus'] += 1
            if not row['ItemNumber']:
                stats['empty_skus_reference'] += 1
                continue
                
            normalized_id = normalize_id(row['ItemNumber'])
            if normalized_id:
                valid_skus[normalized_id] = {
                    'original_id': row['ItemNumber'],
                    'description': row.get('Description', ''),
                    'base_part': row.get('BasePartNumber', '')
                }
                stats['valid_reference_skus'] += 1
                
                # Index by BasePartNumber if available
                if has_base_part and use_metafields and row.get('BasePartNumber'):
                    base_part = normalize_id(row['BasePartNumber'])
                    if base_part:
                        if base_part not in base_part_to_item:
                            base_part_to_item[base_part] = []
                        base_part_to_item[base_part].append({
                            'item_number': row['ItemNumber'],
                            'normalized_id': normalized_id
                        })
    
    print(f"Found {len(valid_skus)} valid SKUs in reference file")
    print(f"Found {len(base_part_to_item)} unique BasePartNumber values in reference file")

    # Process primary file
    matched_rows = []
    near_matches = []
    buffer_size = 1000  # Write to file in batches
    
    with open(primary_file, 'r', encoding=primary_encoding) as f_in, \
         open(output_file, 'w', encoding='utf-8', newline='') as f_out:
        reader = csv.DictReader(f_in)
        validate_required_columns(reader.fieldnames, ['SKU', 'Title'], "primary")
        
        # Check if metafield columns exist
        metafield_cols = {
            'cws_a': 'Metafield: custom.CWS_A[list.single_line_text]',
            'cws_catalog': 'Metafield: custom.CWS_Catalog[list.single_line_text]',
            'sprc': 'Metafield: custom.SPRC[list.single_line_text]'
        }
        
        missing_metafields = []
        for key, col in metafield_cols.items():
            if col not in reader.fieldnames:
                missing_metafields.append(col)
                
        if missing_metafields and use_metafields:
            print(f"Warning: The following metafield columns are missing: {', '.join(missing_metafields)}")
            print("Metafield matching will be limited to available columns.")
            
        # Create output writer with additional columns for match information
        fieldnames = reader.fieldnames + ['matchedSKU', 'newsku', 'MatchMethod', 'ReferenceID', 'ReferenceDescription']
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        
        print(f"Processing primary file...")
        buffer = []
        
        for row in reader:
            stats['total_primary_rows'] += 1
            
            # Handle image variants
            if not is_product_row(row):
                stats['image_variant_rows'] += 1
                continue
            
            stats['total_primary_products'] += 1
            
            if stats['total_primary_products'] % 1000 == 0:
                print(f"Processed {stats['total_primary_products']} products...")
            
            orig_id = row.get('SKU', '')
            
            if not orig_id:
                stats['empty_skus_primary'] += 1
                continue
                
            normalized_id = normalize_id(orig_id)
            
            if normalized_id:
                # Try to match fields in order of priority
                match_found = False
                match_method = ''
                reference_item = None
                matched_sku = ''
                
                # Check each field in order
                for field_info in fields_to_check:
                    field = field_info['field']
                    stat_key = field_info['stat']
                    
                    # Skip if field doesn't exist in the row
                    if field not in row or not row[field]:
                        continue
                    
                    normalized_value = normalize_id(row[field])
                    
                    # Direct match with ItemNumber
                    if normalized_value in valid_skus:
                        match_found = True
                        match_method = field.replace('Metafield: custom.', '').replace('[list.single_line_text]', '')
                        reference_item = valid_skus[normalized_value]
                        matched_sku = row[field]
                        stats[stat_key] += 1
                        break
                    
                    # Match with BasePartNumber if available
                    if use_metafields and has_base_part and normalized_value in base_part_to_item:
                        match_found = True
                        match_method = field.replace('Metafield: custom.', '').replace('[list.single_line_text]', '')
                        item_number = base_part_to_item[normalized_value][0]['normalized_id']
                        reference_item = valid_skus[item_number]
                        matched_sku = row[field]
                        stats[stat_key] += 1
                        break
                
                if match_found:
                    # We have a match (either by SKU or metafield)
                    matched_rows.append(row)
                    stats['matched_products'] += 1
                    
                    # Add match information
                    row['matchedSKU'] = matched_sku
                    row['newsku'] = matched_sku  # Copy the matched value to newsku column (lowercase)
                    row['MatchMethod'] = match_method
                    row['ReferenceID'] = reference_item['original_id']
                    row['ReferenceDescription'] = reference_item['description']
                    
                    # Write to output file
                    buffer.append(row)
                    if len(buffer) >= buffer_size:
                        writer.writerows(buffer)
                        buffer = []
                    
                    if len(stats['sample_matches']) < 10:
                        sample_match = {
                            'primary_sku': orig_id,
                            'normalized_sku': normalized_id,
                            'reference_sku': reference_item['original_id'],
                            'primary_title': row.get('Title', ''),
                            'reference_description': reference_item['description'],
                            'match_method': match_method
                        }
                        
                        # Add metafield info if matched by metafield
                        if match_method.startswith('metafield_'):
                            field_name = match_method.split('_')[1]
                            metafield_col = f"Metafield: custom.{field_name.upper()}[list.single_line_text]"
                            sample_match[f'metafield_{field_name}'] = row.get(metafield_col, '')
                            sample_match[f'reference_base_part'] = reference_item['base_part']
                        
                        stats['sample_matches'].append(sample_match)
        
        # Write any remaining buffered rows
        if buffer:
            writer.writerows(buffer)
    
    # Write sample matches to file
    if stats['sample_matches']:
        # Ensure all dictionaries have the same keys
        all_keys = set()
        for match in stats['sample_matches']:
            all_keys.update(match.keys())
        
        with open(sample_matches_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
            writer.writeheader()
            writer.writerows(stats['sample_matches'])
    
    # Write near matches to file
    if stats['sample_near_matches']:
        with open(near_matches_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=stats['sample_near_matches'][0].keys())
            writer.writeheader()
            writer.writerows(stats['sample_near_matches'])
    
    # Write statistics to file
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    # Print statistics
    print("\nProcessing complete:")
    print(f"Total rows in primary file: {stats['total_primary_rows']}")
    print(f"Main product rows: {stats['total_primary_products']}")
    print(f"Image variant rows: {stats['image_variant_rows']}")
    print(f"Empty SKUs in product rows: {stats['empty_skus_primary']}")
    print(f"Total SKUs in reference file: {stats['total_reference_skus']}")
    print(f"Empty SKUs in reference file: {stats['empty_skus_reference']}")
    print(f"Valid reference SKUs: {stats['valid_reference_skus']}")
    print(f"Products matching reference file: {stats['matched_products']}")
    print(f"  - Matched by SKU: {stats['matched_by_sku']}")
    print(f"  - Matched by CWS_A metafield: {stats['matched_by_metafield_cws_a']}")
    print(f"  - Matched by CWS_Catalog metafield: {stats['matched_by_metafield_cws_catalog']}")
    print(f"  - Matched by SPRC metafield: {stats['matched_by_metafield_sprc']}")
    print(f"Near matches found: {stats['near_matches']}")
    
    match_rate = stats['matched_products'] / stats['total_primary_products'] * 100 if stats['total_primary_products'] > 0 else 0
    print(f"Match rate: {match_rate:.2f}%")
    
    print("\nOutput files:")
    print(f"Filtered products: {output_file}")
    print(f"Sample matches: {sample_matches_file}")
    print(f"Near matches: {near_matches_file}")
    print(f"Matching statistics: {stats_file}")
    
    print("\nWould you like to proceed to the metafield merging stage?")
    print(f"To continue, run the next stage with the filtered file: {output_file}")
    
    return output_file

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Filter products from a primary CSV file against a reference CSV file.')
    parser.add_argument('primary_file', help='Path to the primary CSV file')
    parser.add_argument('reference_file', help='Path to the reference CSV file')
    parser.add_argument('--output', help='Path to the output CSV file')
    parser.add_argument('--debug', action='store_true', help='Print debug information')
    parser.add_argument('--no-metafields', action='store_true', help='Disable metafield matching')
    
    args = parser.parse_args()
    
    output_file = filter_products(
        args.primary_file,
        args.reference_file,
        args.output,
        args.debug,
        not args.no_metafields
    )
    
    print(f"Output written to {output_file}")
