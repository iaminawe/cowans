#!/usr/bin/env python3
"""
Test script to demonstrate product categorization functionality.
This version simulates the OpenAI API calls for testing without requiring an API key.
"""

import pandas as pd
import os
import sys
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ProductCategorizerTest:
    def __init__(self, categories_file: str, debug: bool = False):
        """Initialize the test categorizer."""
        self.categories_file = categories_file
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        # Load categories
        self.categories = self.load_categories()
        self.office_supplies_categories = self.extract_office_supplies_categories()
        
    def load_categories(self):
        """Load categories from the categories file."""
        categories = {}
        try:
            with open(self.categories_file, 'r', encoding='utf-8') as f:
                line_count = 0
                categories_found = 0
                for line in f:
                    line = line.strip()
                    line_count += 1
                    if line and not line.startswith('#') and ' : ' in line:
                        parts = line.split(' : ', 1)
                        if len(parts) == 2:
                            gid = parts[0].strip()
                            category_path = parts[1].strip()
                            categories[gid] = category_path
                            categories_found += 1
                            if self.debug and categories_found <= 3:
                                self.logger.debug(f"Loaded category: {gid} -> {category_path}")
                
                self.logger.info(f"Found {categories_found} valid category lines out of {line_count} total lines")
            
            self.logger.info(f"Loaded {len(categories)} categories from {self.categories_file} ({line_count} lines processed)")
            if self.debug and categories:
                self.logger.debug("Sample categories loaded:")
                for gid, category in list(categories.items())[:5]:
                    self.logger.debug(f"  {gid}: '{category}'")
            return categories
            
        except Exception as e:
            self.logger.error(f"Failed to load categories: {str(e)}")
            raise
    
    def extract_office_supplies_categories(self):
        """Extract only Office Supplies categories."""
        office_categories = {}
        for gid, category_path in self.categories.items():
            if category_path.startswith("Office Supplies"):
                office_categories[gid] = category_path
        
        self.logger.info(f"Found {len(office_categories)} Office Supplies categories")
        if self.debug and office_categories:
            self.logger.debug("Sample Office Supplies categories:")
            for gid, category in list(office_categories.items())[:5]:
                self.logger.debug(f"  {gid}: {category}")
        return office_categories
    
    def simulate_categorization(self, title: str, description: str, tags: str):
        """Simulate product categorization using simple keyword matching."""
        title_lower = title.lower()
        desc_lower = description.lower()
        tags_lower = tags.lower()
        combined_text = f"{title_lower} {desc_lower} {tags_lower}"
        
        # Simple keyword-based categorization for demo
        category_keywords = {
            "gid://shopify/TaxonomyCategory/os-10": ["scanner", "scanning", "scan", "photocopier", "printer", "printing"],
            "gid://shopify/TaxonomyCategory/os-10-1": ["scanner", "scanning", "scan"],
            "gid://shopify/TaxonomyCategory/os-10-2": ["printer", "printing", "toner", "cartridge", "ink"],
            "gid://shopify/TaxonomyCategory/os-10-5": ["docking", "dock", "hub", "port", "usb"],
            "gid://shopify/TaxonomyCategory/os-4": ["pen", "pencil", "marker", "writing", "stationery"],
            "gid://shopify/TaxonomyCategory/os-3": ["filing", "folder", "binder", "organization"],
            "gid://shopify/TaxonomyCategory/os-12": ["paper", "shredder", "laminator"],
            "gid://shopify/TaxonomyCategory/os-14": ["shipping", "packaging", "envelope", "label"],
        }
        
        # Find best match
        best_match_gid = "gid://shopify/TaxonomyCategory/os"  # Default
        best_score = 0
        
        for gid, keywords in category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in combined_text)
            if score > best_score:
                best_score = score
                best_match_gid = gid
        
        category_name = self.categories.get(best_match_gid, "Office Supplies")
        
        return {
            'category_gid': best_match_gid,
            'category_name': category_name,
            'confidence_score': best_score
        }
    
    def process_csv(self, input_file: str, output_file: str = None, limit: int = None):
        """Process a CSV file and add simulated categories."""
        try:
            # Read CSV file
            self.logger.info(f"Reading CSV file: {input_file}")
            try:
                df = pd.read_csv(input_file, low_memory=False)
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(input_file, low_memory=False, encoding='latin1')
                except Exception:
                    df = pd.read_csv(input_file, low_memory=False, encoding='ISO-8859-1')
            
            # Check for required columns with flexible naming
            column_mappings = {
                'title': None,
                'body_html': None,
                'tags': None
            }
            
            # Find columns
            for col in df.columns:
                col_lower = col.lower().strip()
                if col_lower in ['title', 'product title']:
                    column_mappings['title'] = col
                elif col_lower in ['description', 'body_html', 'product description']:
                    column_mappings['body_html'] = col
                elif col_lower in ['tags', 'product tags']:
                    column_mappings['tags'] = col
            
            # Check if we found all required columns
            missing = [k for k, v in column_mappings.items() if v is None]
            if missing:
                self.logger.error(f"Missing required columns: {missing}")
                self.logger.info(f"Available columns: {list(df.columns)}")
                return None
            
            # Apply limit if specified
            if limit:
                df = df.head(limit)
                self.logger.info(f"Processing first {limit} products")
            
            total_products = len(df)
            self.logger.info(f"Processing {total_products} products")
            
            # Add category columns
            df['category_gid'] = ''
            df['category_name'] = ''
            df['confidence_score'] = 0
            
            # Process each product
            for idx, row in df.iterrows():
                try:
                    title = str(row.get(column_mappings['title'], '')).strip()
                    description = str(row.get(column_mappings['body_html'], '')).strip()
                    tags = str(row.get(column_mappings['tags'], '')).strip()
                    
                    if not title:
                        self.logger.warning(f"Row {idx}: Empty title, skipping")
                        continue
                    
                    # Simulate categorization
                    result = self.simulate_categorization(title, description, tags)
                    
                    # Update dataframe
                    df.at[idx, 'category_gid'] = result['category_gid']
                    df.at[idx, 'category_name'] = result['category_name']
                    df.at[idx, 'confidence_score'] = result['confidence_score']
                    
                    # Progress reporting
                    if (idx + 1) % 100 == 0:
                        progress = (idx + 1) / total_products * 100
                        self.logger.info(f"Progress: {idx + 1}/{total_products} ({progress:.1f}%)")
                    
                    if self.debug and idx < 5:
                        self.logger.debug(f"Product: {title[:50]}...")
                        self.logger.debug(f"Category: {result['category_name']}")
                        self.logger.debug(f"Confidence: {result['confidence_score']}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing row {idx}: {str(e)}")
                    continue
            
            # Generate output filename if not provided
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                output_file = f"data/categorized_test_{base_name}_{timestamp}.csv"
            
            # Save results
            df.to_csv(output_file, index=False)
            self.logger.info(f"Categorized data saved to: {output_file}")
            
            # Print summary
            category_counts = df['category_name'].value_counts()
            self.logger.info(f"\nCategory distribution:")
            for category, count in category_counts.head(10).items():
                self.logger.info(f"  {category}: {count} products")
            
            # Show confidence scores
            avg_confidence = df['confidence_score'].mean()
            self.logger.info(f"\nAverage confidence score: {avg_confidence:.2f}")
            
            return output_file
            
        except Exception as e:
            self.logger.error(f"Failed to process CSV: {str(e)}")
            raise

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test product categorization (simulated)')
    parser.add_argument('input_file', nargs='?', 
                      default='data/shopify_CowansOfficeSupplies_20250609_filtered_20250609.csv',
                      help='Path to input CSV file')
    parser.add_argument('--output', help='Path to output CSV file')
    parser.add_argument('--categories-file', default='data/shopify-categories.txt', 
                      help='Path to categories file')
    parser.add_argument('--limit', type=int, default=50, help='Limit number of products to process')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Check if files exist
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.")
        print("Available files in data/:")
        try:
            data_files = [f for f in os.listdir("data/") if f.endswith('.csv')]
            for f in sorted(data_files)[:10]:
                print(f"  {f}")
        except:
            pass
        sys.exit(1)
    
    if not os.path.exists(args.categories_file):
        print(f"Error: Categories file '{args.categories_file}' not found.")
        sys.exit(1)
    
    try:
        # Initialize categorizer
        categorizer = ProductCategorizerTest(
            categories_file=args.categories_file,
            debug=args.debug
        )
        
        # Process CSV
        output_file = categorizer.process_csv(
            input_file=args.input_file,
            output_file=args.output,
            limit=args.limit
        )
        
        if output_file:
            print(f"\n✅ Test categorization complete!")
            print(f"📁 Output file: {output_file}")
            print(f"🏷️  Products have been categorized using simulated keyword matching")
            print(f"🔄 This demonstrates how the real OpenAI version would work")
            print(f"\n💡 To use the real OpenAI version:")
            print(f"   1. Get an OpenAI API key")
            print(f"   2. Run: python scripts/categorize_products.py {args.input_file} --openai-api-key YOUR_KEY")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()