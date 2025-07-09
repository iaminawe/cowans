#!/usr/bin/env python3
"""
Script to deduplicate products by newsku using hierarchical priority:
1. SKU (highest priority)
2. CWS_A metafield
3. SPRC metafield (lowest priority)

When multiple products share the same newsku, keep the one with the highest priority match method.
"""

import pandas as pd
import sys
import os
from datetime import datetime

def deduplicate_by_newsku(input_file, output_file=None):
    """
    Deduplicate products by newsku using hierarchical priority.
    
    Priority order:
    1. SKU field match (highest priority)
    2. CWS_A metafield match
    3. SPRC metafield match (lowest priority)
    
    Args:
        input_file (str): Path to the input CSV file
        output_file (str, optional): Path to the output CSV file
    
    Returns:
        str: Path to the output file
    """
    print(f"Reading CSV file: {input_file}")
    
    # Read the CSV file
    df = pd.read_csv(input_file, encoding='utf-8')
    
    print(f"Total rows before deduplication: {len(df):,}")
    
    # Check required columns
    required_columns = ['newsku', 'matchmethod']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"Error: Missing required columns: {missing_columns}")
        print(f"Available columns: {list(df.columns)}")
        return None
    
    # Define priority mapping (lower number = higher priority)
    priority_map = {
        'SKU': 1,
        'CWS_A': 2, 
        'SPRC': 3
    }
    
    # Add priority column based on matchmethod
    df['priority'] = df['matchmethod'].map(priority_map)
    
    # Handle any unmapped match methods with lowest priority
    df['priority'] = df['priority'].fillna(99)
    
    print(f"Match method distribution:")
    method_counts = df['matchmethod'].value_counts()
    for method, count in method_counts.items():
        priority = priority_map.get(method, 99)
        print(f"  {method}: {count:,} products (priority {priority})")
    
    # Find duplicates
    newsku_counts = df['newsku'].value_counts()
    duplicated_newskus = newsku_counts[newsku_counts > 1]
    
    print(f"\nDuplicate analysis:")
    print(f"  Unique newsku values with duplicates: {len(duplicated_newskus):,}")
    print(f"  Total duplicate entries to remove: {duplicated_newskus.sum() - len(duplicated_newskus):,}")
    
    if len(duplicated_newskus) == 0:
        print("✅ No duplicates found, nothing to deduplicate")
        if output_file:
            df.drop('priority', axis=1).to_csv(output_file, index=False, encoding='utf-8')
            return output_file
        return input_file
    
    # Group by newsku and select the product with highest priority (lowest number)
    print(f"\nApplying hierarchical deduplication...")
    
    # Sort by newsku and priority to ensure consistent selection
    df_sorted = df.sort_values(['newsku', 'priority', 'title'])
    
    # Keep the first row (highest priority) for each newsku
    df_deduplicated = df_sorted.groupby('newsku').first().reset_index()
    
    # Remove the temporary priority column
    df_deduplicated = df_deduplicated.drop('priority', axis=1)
    
    print(f"Rows after deduplication: {len(df_deduplicated):,}")
    print(f"Rows removed: {len(df) - len(df_deduplicated):,}")
    
    # Generate output filename if not provided
    if not output_file:
        datestamp = datetime.now().strftime("%Y%m%d")
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_dir = os.path.dirname(input_file)
        output_file = os.path.join(output_dir, f"{base_name}_deduplicated_{datestamp}.csv")
    
    # Create removed products file for reference
    removed_file = output_file.replace('.csv', '_removed.csv')
    
    # Find removed products (products that were not kept in deduplication)
    kept_indices = df_sorted.groupby('newsku').first().index
    df_removed = df_sorted[~df_sorted.index.isin(kept_indices)]
    
    print(f"\nDeduplication summary by priority:")
    
    # Analyze what was kept vs removed
    for newsku in duplicated_newskus.head(10).index:
        products = df[df['newsku'] == newsku].sort_values('priority')
        kept_product = products.iloc[0]
        removed_products = products.iloc[1:]
        
        print(f"\nnewsku '{newsku}' ({len(products)} products):")
        print(f"  ✅ KEPT: {kept_product['title'][:50]}... (method: {kept_product['matchmethod']})")
        for _, removed in removed_products.iterrows():
            print(f"  ❌ REMOVED: {removed['title'][:50]}... (method: {removed['matchmethod']})")
    
    if len(duplicated_newskus) > 10:
        print(f"\n... and {len(duplicated_newskus) - 10} more duplicate groups")
    
    # Save deduplicated file
    df_deduplicated.to_csv(output_file, index=False, encoding='utf-8')
    print(f"\n✅ Deduplicated file saved to: {output_file}")
    
    # Save removed products for reference
    if len(df_removed) > 0:
        # Add removal reason
        df_removed['removal_reason'] = 'Duplicate newsku - lower priority match method'
        df_removed.to_csv(removed_file, index=False, encoding='utf-8')
        print(f"📄 Removed products saved to: {removed_file}")
    
    # Final verification
    final_newsku_counts = df_deduplicated['newsku'].value_counts()
    final_duplicates = final_newsku_counts[final_newsku_counts > 1]
    
    if len(final_duplicates) == 0:
        print(f"✅ Verification passed: No duplicate newsku values remain")
    else:
        print(f"❌ Warning: {len(final_duplicates)} duplicate newsku values still exist")
    
    return output_file

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Deduplicate products by newsku using hierarchical priority.')
    parser.add_argument('input_file', help='Path to the input CSV file')
    parser.add_argument('--output', help='Path to the output CSV file')
    
    args = parser.parse_args()
    
    output_file = deduplicate_by_newsku(args.input_file, args.output)
    
    if output_file:
        print(f"\nDeduplication completed successfully!")
        print(f"Output file: {output_file}")
    else:
        print(f"\nDeduplication failed!")
        sys.exit(1)