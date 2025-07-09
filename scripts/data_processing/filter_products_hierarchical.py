#!/usr/bin/env python3
import csv
import sys
import os
import json
from datetime import datetime
from collections import defaultdict

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
    return (row.get('Title') and row.get('SKU') and 
            row.get('Vendor') and row.get('Type'))

def filter_products_hierarchical(primary_file, reference_file, output_file=None, debug=False, use_metafields=True):
    """
    Filter products with hierarchical SKU matching and deduplication.
    
    Priority hierarchy: SKU > CWS_A > SPRC
    - If SKU matches: remove duplicates from CWS_A and SPRC
    - If CWS_A matches: keep CWS_A, remove duplicates from SPRC  
    - If only SPRC matches: use SPRC
    
    Parameters:
    - primary_file: Path to the primary CSV file (Cowans)
    - reference_file: Path to the reference CSV file (Xorosoft)
    - output_file: Optional path for the output file
    - debug: Enable debug output
    - use_metafields: Enable matching using metafields
    """
    # Generate output filenames
    datestamp = datetime.now().strftime("%Y%m%d")
    base_name = os.path.splitext(os.path.basename(primary_file))[0]
    
    if not output_file:
        output_dir = os.path.dirname(primary_file)
        output_file = os.path.join(output_dir, f"{base_name}_filtered_hierarchical_{datestamp}.csv")
    
    stats_file = os.path.join(os.path.dirname(output_file), f"{base_name}_hierarchical_stats_{datestamp}.json")
    duplicates_removed_file = os.path.join(os.path.dirname(output_file), f"{base_name}_duplicates_removed_{datestamp}.csv")
    
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
        'matched_by_cws_a': 0,
        'matched_by_sprc': 0,
        'duplicates_removed_by_sku_priority': 0,
        'duplicates_removed_by_cws_a_priority': 0,
        'empty_skus_primary': 0,
        'empty_skus_reference': 0,
        'image_variant_rows': 0,
        'cross_reference_matches': []
    }
    
    # Read and index reference file
    valid_skus = {}
    print(f"Reading and indexing reference file...")
    with open(reference_file, 'r', encoding=ref_encoding) as f:
        reader = csv.DictReader(f)
        validate_required_columns(reader.fieldnames, ['ItemNumber'], "reference")
        
        for row in reader:
            stats['total_reference_skus'] += 1
            if not row['ItemNumber']:
                stats['empty_skus_reference'] += 1
                continue
                
            normalized_id = normalize_id(row['ItemNumber'])
            if normalized_id:
                valid_skus[normalized_id] = {
                    'original_id': row['ItemNumber'],
                    'description': row.get('Description', '')
                }
                stats['valid_reference_skus'] += 1
    
    print(f"Found {len(valid_skus)} valid SKUs in reference file")

    # First pass: collect all products and their matches
    all_products = []
    cross_reference_map = defaultdict(list)  # Maps Xorosoft ItemNumber to list of products
    
    print(f"First pass: collecting all products and matches...")
    with open(primary_file, 'r', encoding=primary_encoding) as f:
        reader = csv.DictReader(f)
        validate_required_columns(reader.fieldnames, ['SKU', 'Title'], "primary")
        
        # Check if metafield columns exist
        metafield_cols = {
            'cws_a': 'Metafield: custom.CWS_A[list.single_line_text]',
            'sprc': 'Metafield: custom.SPRC[list.single_line_text]'
        }
        
        for row in reader:
            stats['total_primary_rows'] += 1
            
            # Handle image variants
            if not is_product_row(row):
                stats['image_variant_rows'] += 1
                continue
            
            stats['total_primary_products'] += 1
            
            if stats['total_primary_products'] % 1000 == 0:
                print(f"Processed {stats['total_primary_products']} products...")
            
            # Check for matches in priority order
            matches = []
            
            # Priority 1: SKU field
            sku_value = row.get('SKU', '')
            if sku_value:
                normalized_sku = normalize_id(sku_value)
                if normalized_sku in valid_skus:
                    matches.append({
                        'field': 'SKU',
                        'value': sku_value,
                        'normalized': normalized_sku,
                        'priority': 1,
                        'reference_item': valid_skus[normalized_sku]
                    })
            
            # Priority 2: CWS_A field
            cws_a_value = row.get(metafield_cols['cws_a'], '')
            if cws_a_value:
                normalized_cws_a = normalize_id(cws_a_value)
                if normalized_cws_a in valid_skus:
                    matches.append({
                        'field': 'CWS_A',
                        'value': cws_a_value,
                        'normalized': normalized_cws_a,
                        'priority': 2,
                        'reference_item': valid_skus[normalized_cws_a]
                    })
            
            # Priority 3: SPRC field
            sprc_value = row.get(metafield_cols['sprc'], '')
            if sprc_value:
                normalized_sprc = normalize_id(sprc_value)
                if normalized_sprc in valid_skus:
                    matches.append({
                        'field': 'SPRC',
                        'value': sprc_value,
                        'normalized': normalized_sprc,
                        'priority': 3,
                        'reference_item': valid_skus[normalized_sprc]
                    })
            
            if matches:
                # Sort by priority (lower number = higher priority)
                matches.sort(key=lambda x: x['priority'])
                
                # Store product with its matches
                product_info = {
                    'row': row,
                    'matches': matches,
                    'best_match': matches[0]  # Highest priority match
                }
                all_products.append(product_info)
                
                # Index by Xorosoft ItemNumber for cross-reference detection
                for match in matches:
                    cross_reference_map[match['normalized']].append(product_info)

    print(f"Collected {len(all_products)} products with matches")
    
    # Second pass: Apply hierarchical deduplication
    print(f"Second pass: applying hierarchical deduplication...")
    products_to_keep = []
    products_removed = []
    
    for xoro_item, product_list in cross_reference_map.items():
        if len(product_list) == 1:
            # No duplicates, keep the product
            products_to_keep.append(product_list[0])
        else:
            # Multiple products reference the same Xorosoft ItemNumber
            print(f"Found {len(product_list)} products referencing Xorosoft item {xoro_item}")
            
            # Group by priority of best match
            by_priority = defaultdict(list)
            for product in product_list:
                by_priority[product['best_match']['priority']].append(product)
            
            # Keep products with highest priority (lowest number)
            highest_priority = min(by_priority.keys())
            products_to_keep.extend(by_priority[highest_priority])
            
            # Remove products with lower priority
            for priority in sorted(by_priority.keys()):
                if priority > highest_priority:
                    for product in by_priority[priority]:
                        products_removed.append({
                            'row': product['row'],
                            'removed_reason': f"Lower priority match ({product['best_match']['field']}) than {by_priority[highest_priority][0]['best_match']['field']}",
                            'xoro_reference': xoro_item
                        })
                        
                        # Update stats
                        if highest_priority == 1:  # SKU had priority
                            if priority == 2:
                                stats['duplicates_removed_by_sku_priority'] += 1
                            elif priority == 3:
                                stats['duplicates_removed_by_sku_priority'] += 1
                        elif highest_priority == 2:  # CWS_A had priority
                            if priority == 3:
                                stats['duplicates_removed_by_cws_a_priority'] += 1
            
            # Log cross-reference info
            kept_products = by_priority[highest_priority]
            stats['cross_reference_matches'].append({
                'xoro_item': xoro_item,
                'total_products': len(product_list),
                'kept_products': len(kept_products),
                'removed_products': len(product_list) - len(kept_products),
                'winning_field': kept_products[0]['best_match']['field'],
                'kept_titles': [p['row']['Title'][:50] for p in kept_products[:3]]
            })

    # Third pass: Write filtered results
    print(f"Third pass: writing {len(products_to_keep)} filtered products...")
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f_out:
        if products_to_keep:
            # Get fieldnames from first product and add our columns
            sample_row = products_to_keep[0]['row']
            fieldnames = list(sample_row.keys()) + ['matchedsku', 'newsku', 'matchmethod', 'referenceid', 'referencedescription']
            
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            
            for product_info in products_to_keep:
                row = product_info['row'].copy()
                best_match = product_info['best_match']
                
                # Add match information
                row['matchedsku'] = best_match['value']
                row['newsku'] = best_match['value']  # Set newsku to the matched value
                row['matchmethod'] = best_match['field']
                row['referenceid'] = best_match['reference_item']['original_id']
                row['referencedescription'] = best_match['reference_item']['description']
                
                writer.writerow(row)
                
                # Update stats
                stats['matched_products'] += 1
                if best_match['field'] == 'SKU':
                    stats['matched_by_sku'] += 1
                elif best_match['field'] == 'CWS_A':
                    stats['matched_by_cws_a'] += 1
                elif best_match['field'] == 'SPRC':
                    stats['matched_by_sprc'] += 1

    # Write removed duplicates to separate file
    if products_removed:
        with open(duplicates_removed_file, 'w', encoding='utf-8', newline='') as f_removed:
            if products_removed:
                fieldnames = list(products_removed[0]['row'].keys()) + ['removed_reason', 'xoro_reference']
                writer = csv.DictWriter(f_removed, fieldnames=fieldnames)
                writer.writeheader()
                
                for removed_info in products_removed:
                    row = removed_info['row'].copy()
                    row['removed_reason'] = removed_info['removed_reason']
                    row['xoro_reference'] = removed_info['xoro_reference']
                    writer.writerow(row)

    # Write statistics to file
    # Convert non-serializable objects for JSON
    stats_copy = stats.copy()
    if len(stats_copy['cross_reference_matches']) > 50:
        stats_copy['cross_reference_matches'] = stats_copy['cross_reference_matches'][:50] + [{"note": "truncated for brevity"}]
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats_copy, f, indent=2)
    
    # Print statistics
    print("\nHierarchical filtering complete:")
    print(f"Total rows in primary file: {stats['total_primary_rows']}")
    print(f"Main product rows: {stats['total_primary_products']}")
    print(f"Image variant rows: {stats['image_variant_rows']}")
    print(f"Valid reference SKUs: {stats['valid_reference_skus']}")
    print(f"Products kept after filtering: {stats['matched_products']}")
    print(f"  - Matched by SKU (priority 1): {stats['matched_by_sku']}")
    print(f"  - Matched by CWS_A (priority 2): {stats['matched_by_cws_a']}")
    print(f"  - Matched by SPRC (priority 3): {stats['matched_by_sprc']}")
    print(f"Duplicates removed by SKU priority: {stats['duplicates_removed_by_sku_priority']}")
    print(f"Duplicates removed by CWS_A priority: {stats['duplicates_removed_by_cws_a_priority']}")
    print(f"Total products removed: {len(products_removed)}")
    
    match_rate = stats['matched_products'] / stats['total_primary_products'] * 100 if stats['total_primary_products'] > 0 else 0
    print(f"Match rate: {match_rate:.2f}%")
    
    print("\nOutput files:")
    print(f"Filtered products: {output_file}")
    print(f"Removed duplicates: {duplicates_removed_file}")
    print(f"Statistics: {stats_file}")
    
    return output_file

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Filter products with hierarchical SKU matching and deduplication.')
    parser.add_argument('primary_file', help='Path to the primary CSV file')
    parser.add_argument('reference_file', help='Path to the reference CSV file')
    parser.add_argument('--output', help='Path to the output CSV file')
    parser.add_argument('--debug', action='store_true', help='Print debug information')
    parser.add_argument('--no-metafields', action='store_true', help='Disable metafield matching')
    
    args = parser.parse_args()
    
    output_file = filter_products_hierarchical(
        args.primary_file,
        args.reference_file,
        args.output,
        args.debug,
        not args.no_metafields
    )
    
    print(f"Output written to {output_file}")