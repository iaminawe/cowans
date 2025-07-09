#!/usr/bin/env python3
"""
Filter products using Xorosoft API instead of CSV reference file.

This script validates products against Xorosoft's live inventory API,
providing real-time validation and inventory status.
"""

import csv
import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import argparse
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web_dashboard.backend.services.xorosoft_api_service import (
    XorosoftAPIService, ProductMatch, MatchType
)


def setup_logging(debug: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def is_product_row(row: Dict[str, str]) -> bool:
    """Check if a row represents a main product (not an image variant)."""
    return (row.get('Title') and row.get('SKU') and 
            row.get('Vendor') and row.get('Type'))


def extract_metafields(row: Dict[str, str]) -> Dict[str, str]:
    """Extract metafield values from a product row."""
    metafields = {}
    
    # Define metafield mappings
    metafield_columns = {
        'CWS_A': 'Metafield: custom.CWS_A[list.single_line_text]',
        'CWS_Catalog': 'Metafield: custom.CWS_Catalog[list.single_line_text]',
        'SPRC': 'Metafield: custom.SPRC[list.single_line_text]'
    }
    
    for field_name, column_name in metafield_columns.items():
        if column_name in row and row[column_name]:
            metafields[field_name] = row[column_name]
    
    return metafields


def filter_products_api(
    primary_file: str,
    output_file: Optional[str] = None,
    debug: bool = False,
    use_metafields: bool = True,
    check_inventory: bool = False,
    batch_size: int = 100
) -> str:
    """
    Filter products from primary file using Xorosoft API validation.
    
    Parameters:
    - primary_file: Path to the primary CSV file (Cowans)
    - output_file: Optional path for the output file
    - debug: Enable debug output
    - use_metafields: Enable matching using metafields
    - check_inventory: Also check inventory status
    - batch_size: Number of products to process in each batch
    
    Returns:
    - Path to the output file
    """
    logger = setup_logging(debug)
    
    # Initialize API service
    try:
        api_service = XorosoftAPIService()
        logger.info("Successfully connected to Xorosoft API")
    except ValueError as e:
        logger.error(f"Failed to initialize Xorosoft API: {e}")
        logger.error("Please ensure XOROSOFT_API and XOROSOFT_PASS environment variables are set")
        sys.exit(1)
    
    # Generate output filenames
    datestamp = datetime.now().strftime("%Y%m%d")
    base_name = os.path.splitext(os.path.basename(primary_file))[0]
    
    if not output_file:
        output_dir = os.path.dirname(primary_file)
        output_file = os.path.join(output_dir, f"{base_name}_filtered_api_{datestamp}.csv")
    
    # Additional output files
    stats_file = os.path.join(os.path.dirname(output_file), f"{base_name}_api_matching_stats_{datestamp}.json")
    inventory_file = os.path.join(os.path.dirname(output_file), f"{base_name}_inventory_status_{datestamp}.csv")
    
    # Statistics tracking
    stats = {
        'total_primary_rows': 0,
        'total_primary_products': 0,
        'matched_products': 0,
        'matched_by_sku': 0,
        'matched_by_cws_a': 0,
        'matched_by_cws_catalog': 0,
        'matched_by_sprc': 0,
        'empty_skus_primary': 0,
        'image_variant_rows': 0,
        'api_requests': 0,
        'api_cache_hits': 0,
        'products_in_stock': 0,
        'products_out_of_stock': 0,
        'processing_time_seconds': 0
    }
    
    start_time = datetime.now()
    
    # Process primary file
    matched_rows = []
    inventory_status = []
    
    try:
        with open(primary_file, 'r', encoding='utf-8-sig') as f_in:
            reader = csv.DictReader(f_in)
            
            # Validate required columns
            required_columns = ['SKU', 'Title']
            missing_columns = [col for col in required_columns if col not in reader.fieldnames]
            if missing_columns:
                logger.error(f"Missing required columns: {', '.join(missing_columns)}")
                sys.exit(1)
            
            # Check for metafield columns
            metafield_cols = {
                'CWS_A': 'Metafield: custom.CWS_A[list.single_line_text]',
                'CWS_Catalog': 'Metafield: custom.CWS_Catalog[list.single_line_text]',
                'SPRC': 'Metafield: custom.SPRC[list.single_line_text]'
            }
            
            available_metafields = []
            for field_name, col_name in metafield_cols.items():
                if col_name in reader.fieldnames:
                    available_metafields.append(field_name)
            
            if use_metafields and not available_metafields:
                logger.warning("No metafield columns found. Matching will be limited to SKU only.")
            elif use_metafields:
                logger.info(f"Found metafield columns: {', '.join(available_metafields)}")
            
            # Prepare output file
            output_fieldnames = reader.fieldnames + [
                'matchedSKU', 'newsku', 'MatchMethod', 
                'XorosoftItemNumber', 'XorosoftDescription',
                'XorosoftBasePartNumber', 'XorosoftPrice'
            ]
            
            if check_inventory:
                output_fieldnames.extend(['InventoryStatus', 'QuantityAvailable'])
            
            rows_to_process = []
            
            # Read all product rows first
            logger.info("Reading primary file...")
            for row in reader:
                stats['total_primary_rows'] += 1
                
                if not is_product_row(row):
                    stats['image_variant_rows'] += 1
                    continue
                
                stats['total_primary_products'] += 1
                
                if not row.get('SKU'):
                    stats['empty_skus_primary'] += 1
                    continue
                
                rows_to_process.append(row)
            
            logger.info(f"Found {len(rows_to_process)} products to validate")
            
            # Process in batches
            with open(output_file, 'w', encoding='utf-8', newline='') as f_out:
                writer = csv.DictWriter(f_out, fieldnames=output_fieldnames)
                writer.writeheader()
                
                for i in range(0, len(rows_to_process), batch_size):
                    batch = rows_to_process[i:i + batch_size]
                    batch_num = (i // batch_size) + 1
                    total_batches = (len(rows_to_process) + batch_size - 1) // batch_size
                    
                    logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} products)...")
                    
                    for row in batch:
                        sku = row['SKU']
                        
                        # Extract metafields if enabled
                        metafields = extract_metafields(row) if use_metafields else {}
                        
                        # Validate product via API
                        stats['api_requests'] += 1
                        match_result = api_service.validate_product(sku, metafields)
                        
                        if match_result.matched:
                            stats['matched_products'] += 1
                            
                            # Track match type
                            if match_result.match_type == MatchType.SKU:
                                stats['matched_by_sku'] += 1
                            elif match_result.match_type == MatchType.CWS_A:
                                stats['matched_by_cws_a'] += 1
                            elif match_result.match_type == MatchType.CWS_CATALOG:
                                stats['matched_by_cws_catalog'] += 1
                            elif match_result.match_type == MatchType.SPRC:
                                stats['matched_by_sprc'] += 1
                            
                            # Add match information to row
                            xorosoft_product = match_result.xorosoft_product
                            row['matchedSKU'] = match_result.matched_value
                            row['newsku'] = match_result.matched_value
                            row['MatchMethod'] = match_result.match_type.value
                            row['XorosoftItemNumber'] = xorosoft_product.item_number
                            row['XorosoftDescription'] = xorosoft_product.description or ''
                            row['XorosoftBasePartNumber'] = xorosoft_product.base_part_number or ''
                            row['XorosoftPrice'] = str(xorosoft_product.unit_price) if xorosoft_product.unit_price else ''
                            
                            # Check inventory if requested
                            if check_inventory:
                                inventory = api_service.get_inventory_status(xorosoft_product.item_number)
                                if inventory:
                                    in_stock = inventory['in_stock']
                                    quantity = inventory['total_inventory']
                                    
                                    row['InventoryStatus'] = 'In Stock' if in_stock else 'Out of Stock'
                                    row['QuantityAvailable'] = str(quantity)
                                    
                                    if in_stock:
                                        stats['products_in_stock'] += 1
                                    else:
                                        stats['products_out_of_stock'] += 1
                                    
                                    # Track inventory status
                                    inventory_status.append({
                                        'SKU': sku,
                                        'ItemNumber': xorosoft_product.item_number,
                                        'InStock': in_stock,
                                        'Quantity': quantity,
                                        'Variants': len(inventory.get('variants', []))
                                    })
                            
                            # Write matched product
                            writer.writerow(row)
                            matched_rows.append(row)
                    
                    # Log progress
                    progress = ((i + len(batch)) / len(rows_to_process)) * 100
                    logger.info(f"Progress: {progress:.1f}% - Matched: {stats['matched_products']}")
    
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        raise
    
    # Calculate final statistics
    stats['processing_time_seconds'] = (datetime.now() - start_time).total_seconds()
    
    # Get cache statistics
    cache_info = api_service.get_cache_info()
    stats['api_cache_hits'] = (
        cache_info['item_number_cache']['hits'] + 
        cache_info['base_part_cache']['hits']
    )
    
    # Write statistics
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    # Write inventory status if collected
    if inventory_status and check_inventory:
        with open(inventory_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=inventory_status[0].keys())
            writer.writeheader()
            writer.writerows(inventory_status)
    
    # Print summary
    match_rate = (stats['matched_products'] / stats['total_primary_products'] * 100 
                  if stats['total_primary_products'] > 0 else 0)
    
    logger.info("\n" + "="*60)
    logger.info("Processing Complete:")
    logger.info(f"Total products processed: {stats['total_primary_products']}")
    logger.info(f"Products matched: {stats['matched_products']} ({match_rate:.2f}%)")
    logger.info(f"  - Matched by SKU: {stats['matched_by_sku']}")
    logger.info(f"  - Matched by CWS_A: {stats['matched_by_cws_a']}")
    logger.info(f"  - Matched by CWS_Catalog: {stats['matched_by_cws_catalog']}")
    logger.info(f"  - Matched by SPRC: {stats['matched_by_sprc']}")
    
    if check_inventory:
        logger.info(f"Inventory Status:")
        logger.info(f"  - In Stock: {stats['products_in_stock']}")
        logger.info(f"  - Out of Stock: {stats['products_out_of_stock']}")
    
    logger.info(f"\nAPI Performance:")
    logger.info(f"  - Total API requests: {stats['api_requests']}")
    logger.info(f"  - Cache hits: {stats['api_cache_hits']}")
    logger.info(f"  - Processing time: {stats['processing_time_seconds']:.2f} seconds")
    
    logger.info(f"\nOutput files:")
    logger.info(f"  - Filtered products: {output_file}")
    logger.info(f"  - Statistics: {stats_file}")
    if check_inventory:
        logger.info(f"  - Inventory status: {inventory_file}")
    
    return output_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Filter products using Xorosoft API validation.'
    )
    parser.add_argument('primary_file', help='Path to the primary CSV file')
    parser.add_argument('--output', help='Path to the output CSV file')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-metafields', action='store_true', 
                       help='Disable metafield matching')
    parser.add_argument('--check-inventory', action='store_true',
                       help='Also check inventory status for matched products')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Number of products to process per batch (default: 100)')
    
    args = parser.parse_args()
    
    try:
        output_file = filter_products_api(
            args.primary_file,
            args.output,
            args.debug,
            not args.no_metafields,
            args.check_inventory,
            args.batch_size
        )
        
        print(f"\nFiltering complete. Output written to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)