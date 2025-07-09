#!/usr/bin/env python3
"""
Remove duplicate entries from CSV file based on SKU and URL handle.
Keeps the first occurrence of each duplicate.
"""

import pandas as pd
import argparse
import sys

def remove_duplicates(input_file: str, output_file: str) -> None:
    """Remove duplicates from CSV file."""
    print(f"Reading CSV file: {input_file}")
    df = pd.read_csv(input_file)
    
    original_count = len(df)
    print(f"Original product count: {original_count:,}")
    
    # Check for duplicate SKUs
    sku_duplicates = df['sku'].duplicated().sum()
    if sku_duplicates > 0:
        print(f"Found {sku_duplicates:,} duplicate SKUs")
    
    # Check for duplicate URL handles  
    handle_duplicates = df['url handle'].duplicated().sum()
    if handle_duplicates > 0:
        print(f"Found {handle_duplicates:,} duplicate URL handles")
    
    # Remove duplicates based on SKU (keep first occurrence)
    print("Removing SKU duplicates (keeping first occurrence)...")
    df_no_sku_dups = df.drop_duplicates(subset=['sku'], keep='first')
    sku_removed = len(df) - len(df_no_sku_dups)
    
    # Remove duplicates based on URL handle (keep first occurrence)
    print("Removing URL handle duplicates (keeping first occurrence)...")
    df_clean = df_no_sku_dups.drop_duplicates(subset=['url handle'], keep='first')
    handle_removed = len(df_no_sku_dups) - len(df_clean)
    
    final_count = len(df_clean)
    total_removed = original_count - final_count
    
    print(f"\nCleaning Summary:")
    print(f"  SKU duplicates removed: {sku_removed:,}")
    print(f"  URL handle duplicates removed: {handle_removed:,}")
    print(f"  Total duplicates removed: {total_removed:,}")
    print(f"  Final product count: {final_count:,}")
    print(f"  Reduction: {(total_removed/original_count)*100:.1f}%")
    
    # Save cleaned CSV
    print(f"\nSaving cleaned CSV to: {output_file}")
    df_clean.to_csv(output_file, index=False)
    
    # Verify no duplicates remain
    verify_sku_dups = df_clean['sku'].duplicated().sum()
    verify_handle_dups = df_clean['url handle'].duplicated().sum()
    
    if verify_sku_dups == 0 and verify_handle_dups == 0:
        print("✅ Verification passed: No duplicates remaining")
    else:
        print(f"⚠️  Warning: Still found {verify_sku_dups} SKU duplicates and {verify_handle_dups} handle duplicates")

def main():
    parser = argparse.ArgumentParser(description='Remove duplicate entries from CSV file')
    parser.add_argument('input_csv', help='Input CSV file path')
    parser.add_argument('--output', help='Output CSV file path (default: input_file_cleaned.csv)')
    
    args = parser.parse_args()
    
    if not args.output:
        base_name = args.input_csv.replace('.csv', '')
        args.output = f"{base_name}_cleaned.csv"
    
    try:
        remove_duplicates(args.input_csv, args.output)
        print(f"\n🎉 Duplicate removal completed successfully!")
        print(f"Clean file ready for upload: {args.output}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()