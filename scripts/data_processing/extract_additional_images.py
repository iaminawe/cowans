#!/usr/bin/env python3
"""
Script to extract additional image rows for products with multiple images.
This script finds products that have more than one image row in the source data
and are also present in the filtered Shopify CSV (matched by handle).
The output can be used for a follow-up import to add extra images to existing products.
"""

import pandas as pd
import os
import sys
from datetime import datetime
from collections import defaultdict

def extract_additional_images(source_file, filtered_file, output_file=None):
    """
    Extract additional image rows for products with multiple images.
    
    Args:
        source_file (str): Path to the original source CSV file (with all image rows)
        filtered_file (str): Path to the filtered Shopify CSV file (matched products)
        output_file (str, optional): Path to the output CSV file
    
    Returns:
        str: Path to the output file
    """
    print(f"Reading source file: {source_file}")
    
    # Read source file with multiple encoding attempts
    try:
        source_df = pd.read_csv(source_file, low_memory=False)
    except UnicodeDecodeError:
        try:
            source_df = pd.read_csv(source_file, low_memory=False, encoding='latin1')
        except Exception:
            source_df = pd.read_csv(source_file, low_memory=False, encoding='ISO-8859-1')
    
    print(f"Reading filtered file: {filtered_file}")
    
    # Read filtered file
    try:
        filtered_df = pd.read_csv(filtered_file, low_memory=False)
    except UnicodeDecodeError:
        try:
            filtered_df = pd.read_csv(filtered_file, low_memory=False, encoding='latin1')
        except Exception:
            filtered_df = pd.read_csv(filtered_file, low_memory=False, encoding='ISO-8859-1')
    
    # Get the set of handles from filtered file (these are the matched products)
    matched_handles = set(filtered_df['url handle'].dropna().str.strip())
    print(f"Found {len(matched_handles)} matched product handles in filtered file")
    
    # Debug: Check column names in source file
    print(f"Source file columns: {list(source_df.columns)[:10]}...")  # Show first 10 columns
    
    # Find the correct column names in source file (handle quotes and spacing differences)
    handle_col = None
    image_url_col = None
    
    for col in source_df.columns:
        col_clean = col.strip('"').strip()
        if col_clean.lower() == 'url handle':
            handle_col = col
        elif col_clean.lower() == 'product image url':
            image_url_col = col
    
    if not handle_col:
        print("Error: Could not find 'URL handle' column in source file")
        print("Available columns:", list(source_df.columns))
        return None
        
    if not image_url_col:
        print("Error: Could not find image URL column in source file")
        print("Available columns:", list(source_df.columns))
        return None
    
    print(f"Using handle column: '{handle_col}'")
    print(f"Using image URL column: '{image_url_col}'")
    
    # Group source data by handle to find products with multiple images
    print("Analyzing source file for products with multiple images...")
    
    # Filter source data to only include rows that have a handle and image URL
    # Convert image URL column to string to handle mixed types
    source_df[image_url_col] = source_df[image_url_col].astype(str)
    
    source_with_images = source_df[
        (source_df[handle_col].notna()) & 
        (source_df[handle_col].str.strip() != '') &
        (source_df[image_url_col].notna()) &
        (source_df[image_url_col] != 'nan') &
        (source_df[image_url_col].str.strip() != '') &
        (source_df[image_url_col].str.startswith('http'))  # Only valid URLs
    ].copy()
    
    # Group by handle to find products with multiple image rows
    handle_groups = defaultdict(list)
    for idx, row in source_with_images.iterrows():
        handle = row[handle_col].strip()
        if handle in matched_handles:  # Only consider matched products
            handle_groups[handle].append(idx)
    
    # Find products with multiple images
    multi_image_handles = {}
    for handle, indices in handle_groups.items():
        if len(indices) > 1:
            multi_image_handles[handle] = indices
    
    print(f"Found {len(multi_image_handles)} matched products with multiple images")
    
    # Extract additional image rows (all except the first one for each product)
    additional_image_indices = []
    products_processed = 0
    
    for handle, indices in multi_image_handles.items():
        # Skip the first image row (index 0), collect the rest as "additional"
        additional_indices = indices[1:]  # All images except the first one
        additional_image_indices.extend(additional_indices)
        products_processed += 1
        
        if products_processed <= 10:  # Show first 10 as examples
            print(f"  Product '{handle}': {len(indices)} total images, {len(additional_indices)} additional")
    
    if products_processed > 10:
        print(f"  ... and {products_processed - 10} more products")
    
    print(f"Total additional image rows to extract: {len(additional_image_indices)}")
    
    if not additional_image_indices:
        print("No additional image rows found to extract.")
        return None
    
    # Extract the additional image rows
    additional_images_df = source_df.iloc[additional_image_indices].copy()
    
    # Generate output file name if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(os.path.basename(source_file))[0]
        output_file = f"data/additional_images_{base_name}_{timestamp}.csv"
    
    # Save to CSV file
    additional_images_df.to_csv(output_file, index=False)
    print(f"\nAdditional images data saved to: {output_file}")
    
    # Print summary statistics
    print(f"\nSummary:")
    print(f"  Source file rows: {len(source_df)}")
    print(f"  Matched products (from filtered file): {len(matched_handles)}")
    print(f"  Products with multiple images: {len(multi_image_handles)}")
    print(f"  Additional image rows extracted: {len(additional_image_indices)}")
    print(f"  Average additional images per product: {len(additional_image_indices) / len(multi_image_handles):.1f}")
    
    # Show some examples of the extracted data
    print(f"\nSample of extracted additional images:")
    # Find image position column
    position_col = None
    for col in additional_images_df.columns:
        if 'position' in col.lower():
            position_col = col
            break
    
    sample_columns = [handle_col, image_url_col]
    if position_col:
        sample_columns.append(position_col)
    
    sample_df = additional_images_df[sample_columns].head(5)
    for idx, row in sample_df.iterrows():
        handle = row[handle_col]
        position = row.get(position_col, 'N/A') if position_col else 'N/A'
        image_url = row[image_url_col]
        print(f"  {handle} (pos: {position}): {image_url}")
    
    return output_file

def main():
    """Main function to run the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract additional image rows for matched products')
    parser.add_argument('source_file', help='Path to the original source CSV file (with all image rows)')
    parser.add_argument('filtered_file', help='Path to the filtered Shopify CSV file (matched products)')
    parser.add_argument('--output', help='Path to the output CSV file')
    
    # If no arguments provided, use default files
    if len(sys.argv) == 1:
        print("No arguments provided, using default files...")
        
        # Default file paths
        source_file = "data/CowansOfficeSupplies_20250604.csv"
        filtered_file = "data/shopify_CowansOfficeSupplies_20250609_filtered_20250609.csv"
        
        # Check if default files exist
        if not os.path.exists(source_file):
            print(f"Error: Default source file '{source_file}' not found.")
            print("Usage: python extract_additional_images.py <source_file> <filtered_file> [--output <output_file>]")
            sys.exit(1)
            
        if not os.path.exists(filtered_file):
            print(f"Error: Default filtered file '{filtered_file}' not found.")
            print("Available files in data/:")
            data_files = [f for f in os.listdir("data/") if f.endswith('.csv')]
            for f in sorted(data_files):
                print(f"  {f}")
            sys.exit(1)
            
        output_file = extract_additional_images(source_file, filtered_file)
        
    else:
        args = parser.parse_args()
        
        # Check if files exist
        if not os.path.exists(args.source_file):
            print(f"Error: Source file '{args.source_file}' not found.")
            sys.exit(1)
            
        if not os.path.exists(args.filtered_file):
            print(f"Error: Filtered file '{args.filtered_file}' not found.")
            sys.exit(1)
        
        output_file = extract_additional_images(args.source_file, args.filtered_file, args.output)
    
    if output_file:
        print(f"\n✅ Process completed successfully!")
        print(f"📁 Output file: {output_file}")
        print(f"🔄 This file can be used for a follow-up Shopify import to add additional images to existing products.")
    else:
        print(f"\n⚠️  No additional images found to extract.")

if __name__ == "__main__":
    main()