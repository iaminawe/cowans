#!/usr/bin/env python3
import csv
import sys
import os
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
    current_product = None
    buffer_size = 1000  # Write to file in batches
    
    with open(primary_file, 'r', encoding=primary_encoding) as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.DictReader(infile)
        validate_required_columns(reader.fieldnames, ['SKU'], "primary")
        
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        writer.writeheader()
        
        print(f"Processing primary file products...")
        buffer = []
        
        for row in reader:
            stats['total_primary_rows'] += 1
            
            if not is_product_row(row):
                stats['image_variant_rows'] += 1
                continue
            
            stats['total_primary_products'] += 1
            
            if stats['total_primary_products'] % 100 == 0:
                print(f"Processed {stats['total_primary_products']} products...")
            
            orig_id = row.get('SKU', '')
            
            if not orig_id:
                stats['empty_skus_primary'] += 1
                continue
                
            normalized_id = normalize_id(orig_id)
            
            if normalized_id:
                matched = False
                match_method = None
                reference_item = None
                
                # First try exact match by SKU
                if normalized_id in valid_skus:
                    matched = True
                    match_method = 'sku'
                    reference_item = valid_skus[normalized_id]
                    stats['matched_by_sku'] += 1
                
                # If no SKU match and metafields enabled, try metafield matching
                if not matched and use_metafields:
                    metafield_matches = []
                    
                    # Debug metafield values
                    if debug:
                        cws_a = row.get('Metafield: custom.CWS_A[list.single_line_text]', '')
                        cws_catalog = row.get('Metafield: custom.CWS_Catalog[list.single_line_text]', '')
                        sprc = row.get('Metafield: custom.SPRC[list.single_line_text]', '')
                        
                        if cws_a or cws_catalog or sprc:
                            print(f"\nDebug for SKU {orig_id}:")
                            if cws_a:
                                norm_cws_a = normalize_id(cws_a)
                                print(f"  CWS_A: {cws_a} (normalized: {norm_cws_a})")
                                print(f"  In base_part_to_item: {norm_cws_a in base_part_to_item}")
                            if cws_catalog:
                                norm_cws_catalog = normalize_id(cws_catalog)
                                print(f"  CWS_Catalog: {cws_catalog} (normalized: {norm_cws_catalog})")
                                print(f"  In base_part_to_item: {norm_cws_catalog in base_part_to_item}")
                            if sprc:
                                norm_sprc = normalize_id(sprc)
                                print(f"  SPRC: {sprc} (normalized: {norm_sprc})")
                                print(f"  In base_part_to_item: {norm_sprc in base_part_to_item}")
                    
                    # Check CWS_A metafield
                    cws_a = row.get('Metafield: custom.CWS_A[list.single_line_text]', '')
                    if cws_a and not matched:
                        normalized_cws_a = normalize_id(cws_a)
                        if normalized_cws_a and normalized_cws_a in base_part_to_item:
                            metafield_matches.append({
                                'field': 'CWS_A',
                                'value': cws_a,
                                'normalized': normalized_cws_a,
                                'matches': base_part_to_item[normalized_cws_a]
                            })
                            stats['matched_by_metafield_cws_a'] += 1
                    
                    # Check CWS_Catalog metafield
                    cws_catalog = row.get('Metafield: custom.CWS_Catalog[list.single_line_text]', '')
                    if cws_catalog and not matched:
                        normalized_cws_catalog = normalize_id(cws_catalog)
                        if normalized_cws_catalog and normalized_cws_catalog in base_part_to_item:
                            metafield_matches.append({
                                'field': 'CWS_Catalog',
                                'value': cws_catalog,
                                'normalized': normalized_cws_catalog,
                                'matches': base_part_to_item[normalized_cws_catalog]
                            })
                            stats['matched_by_metafield_cws_catalog'] += 1
                    
                    # Check SPRC metafield
                    sprc = row.get('Metafield: custom.SPRC[list.single_line_text]', '')
                    if sprc and not matched:
                        normalized_sprc = normalize_id(sprc)
                        if normalized_sprc and normalized_sprc in base_part_to_item:
                            metafield_matches.append({
                                'field': 'SPRC',
                                'value': sprc,
                                'normalized': normalized_sprc,
                                'matches': base_part_to_item[normalized_sprc]
                            })
                            stats['matched_by_metafield_sprc'] += 1
                    
                    # If we have metafield matches, use the first one
                    if metafield_matches:
                        matched = True
                        match_info = metafield_matches[0]
                        match_method = f"metafield_{match_info['field'].lower()}"
                        
                        # Use the first match if there are multiple
                        item_match = match_info['matches'][0]
                        reference_item = valid_skus[item_match['normalized_id']]
                
                if matched:
                    # We have a match (either by SKU or metafield)
                    matched_rows.append(row)
                    stats['matched_products'] += 1
                    
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
                            for match_info in metafield_matches:
                                field_name = match_info['field']
                                sample_match[f'metafield_{field_name.lower()}'] = match_info['value']
                                sample_match[f'reference_base_part'] = reference_item['base_part']
                        
                        stats['sample_matches'].append(sample_match)
        
        # Write any remaining buffered rows
        if buffer:
            writer.writerows(buffer)
    
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
