#!/usr/bin/env python3
"""
Script to extract specific columns from CowansOfficeSupplies CSV file.
This script extracts title, URL handle, SKU, and specific metafields (CWS_A, CWS_Catalog, SPRC).
It filters out additional image rows for each product handle.
"""

import pandas as pd
import os
from datetime import datetime

def extract_columns(input_file, output_file=None):
    """
    Extract specific columns from the input CSV file and save to a new CSV file.
    
    Args:
        input_file (str): Path to the input CSV file
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
    
    # Alternative approach: Filter out rows with empty Title
    # extracted_df = extracted_df[extracted_df['Title'].notna() & (extracted_df['Title'] != '')]
    
    print(f"Total rows after filtering: {len(extracted_df)}")
    
    # Generate output file name if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d")
        base_name = os.path.basename(input_file)
        name_parts = os.path.splitext(base_name)
        output_file = f"{os.path.dirname(input_file)}/extracted_{name_parts[0]}_{timestamp}{name_parts[1]}"
    
    # Save to new CSV file
    extracted_df.to_csv(output_file, index=False)
    print(f"Extracted data saved to: {output_file}")
    
    # Print summary
    print(f"Summary:")
    print(f"  - Total rows: {len(extracted_df)}")
    print(f"  - Columns extracted: {', '.join(columns_to_extract)}")
    
    return output_file

def main():
    """Main function to run the script."""
    # Define input file path
    input_file = "data/CowansOfficeSupplies_20250604.csv"
    
    # Check if file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        return
    
    # Extract columns and save to new file
    output_file = extract_columns(input_file)
    print(f"Process completed successfully.")

if __name__ == "__main__":
    main()
