#!/usr/bin/env python3
"""
Script to extract specific columns from CowansOfficeSupplies CSV file with SKU matching.
This script extracts title, URL handle, SKU, and specific metafields (CWS_A, CWS_Catalog, SPRC).
It filters out additional image rows for each product handle.
Additionally, it compares against Xorosoft reference data and extracts matching ItemNumbers into a newSKU column.
"""

import pandas as pd
import os
from datetime import datetime

def extract_columns_with_sku_matching(input_file, xorosoft_file, output_file=None):
    """
    Extract specific columns from the input CSV file, match against Xorosoft data, and save to a new CSV file.
    
    Args:
        input_file (str): Path to the input CSV file
        xorosoft_file (str): Path to the Xorosoft reference CSV file
        output_file (str, optional): Path to the output CSV file. If None, a default name will be generated.
    
    Returns:
        str: Path to the output file
    """
    print(f"Reading CSV file: {input_file}")
    
    # Read the CSV file with different encoding options
    try:
        # Try UTF-8 first
        df = pd.read_csv(input_file, low_memory=False)
    except UnicodeDecodeError:
        try:
            # Try Latin-1 encoding
            df = pd.read_csv(input_file, low_memory=False, encoding='latin1')
        except Exception:
            # Try with ISO-8859-1 encoding
            df = pd.read_csv(input_file, low_memory=False, encoding='ISO-8859-1')
    
    print(f"Reading Xorosoft reference file: {xorosoft_file}")
    
    # Read the Xorosoft reference file
    try:
        # Try UTF-8 first
        xoro_df = pd.read_csv(xorosoft_file, low_memory=False)
    except UnicodeDecodeError:
        try:
            # Try Latin-1 encoding
            xoro_df = pd.read_csv(xorosoft_file, low_memory=False, encoding='latin1')
        except Exception:
            # Try with ISO-8859-1 encoding
            xoro_df = pd.read_csv(xorosoft_file, low_memory=False, encoding='ISO-8859-1')
    
    # Columns to extract
    columns_to_extract = [
        'Title',
        'URL handle',
        'SKU',
        'Metafield: custom.CWS_A[list.single_line_text]',
        'Metafield: custom.CWS_Catalog[list.single_line_text]',
        'Metafield: custom.SPRC[list.single_line_text]'
    ]
    
    # Check if all columns exist
    missing_columns = [col for col in columns_to_extract if col not in df.columns]
    if missing_columns:
        print(f"Warning: The following columns are missing from the CSV: {missing_columns}")
        # Filter to only include columns that exist
        columns_to_extract = [col for col in columns_to_extract if col in df.columns]
    
    # Extract the specified columns
    extracted_df = df[columns_to_extract]
    
    # Filter out additional image rows (rows with empty Title but same URL handle)
    print(f"Total rows before filtering: {len(extracted_df)}")
    
    # Keep only the first occurrence of each URL handle
    extracted_df = extracted_df.drop_duplicates(subset=['URL handle'], keep='first')
    
    print(f"Total rows after filtering: {len(extracted_df)}")
    
    # Create a set of Xorosoft ItemNumbers for matching
    print("Creating SKU matching lookup from Xorosoft data...")
    
    # Check if ItemNumber column exists in Xorosoft data
    if 'ItemNumber' not in xoro_df.columns:
        print("Warning: 'ItemNumber' column not found in Xorosoft file. Available columns:")
        print(xoro_df.columns.tolist())
        # Initialize newSKU column with empty values
        extracted_df['newSKU'] = ''
    else:
        # Create set of ItemNumbers for efficient lookup
        xoro_items = set(xoro_df['ItemNumber'].astype(str).str.strip())
        
        print(f"Created lookup with {len(xoro_items)} Xorosoft ItemNumbers")
        
        # Function to find matching SKU across multiple fields
        def find_matching_sku(row):
            # Fields to check for matches
            fields_to_check = [
                'SKU',
                'Metafield: custom.CWS_A[list.single_line_text]',
                'Metafield: custom.CWS_Catalog[list.single_line_text]',
                'Metafield: custom.SPRC[list.single_line_text]'
            ]
            
            for field in fields_to_check:
                if field in row and not pd.isna(row[field]) and row[field] != '':
                    field_value = str(row[field]).strip()
                    # Direct match only
                    if field_value in xoro_items:
                        return field_value
            
            return ''
        
        # Apply the matching function to create newSKU column
        print("Matching values across SKU, CWS_A, CWS_Catalog, and SPRC fields against Xorosoft ItemNumbers...")
        extracted_df['newSKU'] = extracted_df.apply(find_matching_sku, axis=1)
        
        # Filter to keep only rows with matches
        total_rows_before_filter = len(extracted_df)
        extracted_df = extracted_df[extracted_df['newSKU'] != '']
        matched_rows = len(extracted_df)
        
        print(f"SKU matching results: {matched_rows}/{total_rows_before_filter} rows matched ({matched_rows/total_rows_before_filter*100:.1f}%)")
        print(f"Filtered to keep only matched rows: {matched_rows} rows retained")
    
    # Generate output file name if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d")
        base_name = os.path.basename(input_file)
        name_parts = os.path.splitext(base_name)
        output_file = f"{os.path.dirname(input_file)}/extracted_with_sku_{name_parts[0]}_{timestamp}{name_parts[1]}"
    
    # Save to new CSV file
    extracted_df.to_csv(output_file, index=False)
    print(f"Extracted data with SKU matching saved to: {output_file}")
    
    # Print summary
    print(f"Summary:")
    print(f"  - Total rows: {len(extracted_df)}")
    print(f"  - Columns extracted: {', '.join(columns_to_extract + ['newSKU'])}")
    if 'ItemNumber' in xoro_df.columns:
        print(f"  - SKU matches found: {len(extracted_df[extracted_df['newSKU'] != ''])}")
    
    return output_file

def main():
    """Main function to run the script."""
    # Define input file paths
    input_file = "data/CowansOfficeSupplies_20250604.csv"
    xorosoft_file = "data/Xorosoft -CurrentProducts202505221345341.csv"
    
    # Check if files exist
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        return
    
    if not os.path.exists(xorosoft_file):
        print(f"Error: Xorosoft reference file '{xorosoft_file}' not found.")
        return
    
    # Extract columns with SKU matching and save to new file
    output_file = extract_columns_with_sku_matching(input_file, xorosoft_file)
    print(f"Process completed successfully.")

if __name__ == "__main__":
    main()