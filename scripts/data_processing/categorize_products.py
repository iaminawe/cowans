#!/usr/bin/env python3
"""
Script to categorize products using OpenAI API.
This script analyzes product title, description, and tags to determine
the most appropriate Shopify category from the categories.txt file.
"""

import pandas as pd
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    import openai
except ImportError:
    print("Error: OpenAI library not installed. Please install with: pip install openai")
    sys.exit(1)

class ProductCategorizer:
    def __init__(self, openai_api_key: str, categories_file: str, debug: bool = False):
        """Initialize the product categorizer."""
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.categories_file = categories_file
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        # Load categories
        self.categories = self.load_categories()
        self.office_supplies_categories = self.extract_office_supplies_categories()
        
        # Rate limiting
        self.request_count = 0
        self.start_time = time.time()
        
    def load_categories(self) -> Dict[str, str]:
        """Load categories from the categories file."""
        categories = {}
        try:
            with open(self.categories_file, 'r', encoding='utf-8') as f:
                line_count = 0
                for line in f:
                    line = line.strip()
                    line_count += 1
                    if line and not line.startswith('#') and ' : ' in line:
                        parts = line.split(' : ', 1)
                        if len(parts) == 2:
                            gid = parts[0].strip()
                            category_path = parts[1].strip()
                            categories[gid] = category_path
            
            self.logger.info(f"Loaded {len(categories)} categories from {self.categories_file} ({line_count} lines processed)")
            return categories
            
        except Exception as e:
            self.logger.error(f"Failed to load categories: {str(e)}")
            raise
    
    def extract_office_supplies_categories(self) -> Dict[str, str]:
        """Extract only Office Supplies categories for focused matching."""
        office_categories = {}
        for gid, category_path in self.categories.items():
            if category_path.startswith("Office Supplies"):
                office_categories[gid] = category_path
        
        self.logger.info(f"Found {len(office_categories)} Office Supplies categories")
        return office_categories
    
    def rate_limit(self):
        """Simple rate limiting to avoid API limits."""
        self.request_count += 1
        elapsed = time.time() - self.start_time
        
        # Limit to 2 requests per second
        if self.request_count > 1 and elapsed < (self.request_count * 0.5):
            sleep_time = (self.request_count * 0.5) - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def create_categorization_prompt(self, title: str, description: str, tags: str) -> str:
        """Create a prompt for OpenAI to categorize the product."""
        
        # Create a condensed list of categories for the prompt
        category_list = []
        for gid, category_path in self.office_supplies_categories.items():
            category_list.append(f"{gid}: {category_path}")
        
        # Limit to reasonable number for prompt
        if len(category_list) > 50:
            # Focus on main subcategories
            main_categories = [cat for cat in category_list if cat.count('>') <= 2]
            category_list = main_categories[:50]
        
        categories_text = "\n".join(category_list)
        
        prompt = f"""You are a product categorization expert. Analyze the following product and determine the most appropriate Shopify category.

PRODUCT INFORMATION:
Title: {title}
Description: {description[:500]}...  
Tags: {tags}

AVAILABLE CATEGORIES:
{categories_text}

INSTRUCTIONS:
1. Analyze the product title, description, and tags
2. Find the MOST SPECIFIC and RELEVANT category from the list above
3. Respond with ONLY the category GID (e.g., gid://shopify/TaxonomyCategory/os-10-1)
4. If no perfect match exists, choose the closest parent category
5. If the product doesn't seem to fit Office Supplies at all, respond with: gid://shopify/TaxonomyCategory/os

RESPONSE FORMAT: Only return the GID, nothing else."""

        return prompt
    
    def categorize_product(self, title: str, description: str, tags: str) -> Dict[str, str]:
        """Categorize a single product using OpenAI."""
        try:
            self.rate_limit()
            
            prompt = self.create_categorization_prompt(title, description, tags)
            
            if self.debug:
                self.logger.debug(f"Categorizing: {title}")
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1
            )
            
            predicted_gid = response.choices[0].message.content.strip()
            
            # Validate the response
            if predicted_gid not in self.categories:
                self.logger.warning(f"Invalid GID returned: {predicted_gid}, using default")
                predicted_gid = "gid://shopify/TaxonomyCategory/os"
            
            category_name = self.categories[predicted_gid]
            
            result = {
                'category_gid': predicted_gid,
                'category_name': category_name
            }
            
            if self.debug:
                self.logger.debug(f"Result: {category_name}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to categorize product '{title}': {str(e)}")
            # Return default category on error
            return {
                'category_gid': "gid://shopify/TaxonomyCategory/os",
                'category_name': "Office Supplies"
            }
    
    def process_csv(self, input_file: str, output_file: str = None, limit: int = None):
        """Process a CSV file and add categories to each product."""
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
            
            # Check required columns
            required_columns = ['title', 'body_html', 'tags']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                # Check for alternative column names
                alt_mappings = {
                    'title': ['Title', 'Product Title'],
                    'body_html': ['Description', 'body_html', 'Product Description'],
                    'tags': ['Tags', 'Product Tags']
                }
                
                for col in missing_columns:
                    found = False
                    for alt_col in alt_mappings.get(col, []):
                        if alt_col in df.columns:
                            df[col] = df[alt_col]
                            found = True
                            self.logger.info(f"Using '{alt_col}' for '{col}'")
                            break
                    if not found:
                        self.logger.error(f"Required column '{col}' not found")
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
            
            # Process each product
            for idx, row in df.iterrows():
                try:
                    title = str(row.get('title', '')).strip()
                    description = str(row.get('body_html', '')).strip()
                    tags = str(row.get('tags', '')).strip()
                    
                    if not title:
                        self.logger.warning(f"Row {idx}: Empty title, skipping")
                        continue
                    
                    # Categorize product
                    result = self.categorize_product(title, description, tags)
                    
                    # Update dataframe
                    df.at[idx, 'category_gid'] = result['category_gid']
                    df.at[idx, 'category_name'] = result['category_name']
                    
                    # Progress reporting
                    if (idx + 1) % 10 == 0:
                        progress = (idx + 1) / total_products * 100
                        self.logger.info(f"Progress: {idx + 1}/{total_products} ({progress:.1f}%)")
                    
                except Exception as e:
                    self.logger.error(f"Error processing row {idx}: {str(e)}")
                    continue
            
            # Generate output filename if not provided
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                output_file = f"data/categorized_{base_name}_{timestamp}.csv"
            
            # Save results
            df.to_csv(output_file, index=False)
            self.logger.info(f"Categorized data saved to: {output_file}")
            
            # Print summary
            category_counts = df['category_name'].value_counts()
            self.logger.info(f"\nCategory distribution:")
            for category, count in category_counts.head(10).items():
                self.logger.info(f"  {category}: {count} products")
            
            return output_file
            
        except Exception as e:
            self.logger.error(f"Failed to process CSV: {str(e)}")
            raise

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Categorize products using OpenAI API')
    parser.add_argument('input_file', help='Path to input CSV file')
    parser.add_argument('--output', help='Path to output CSV file')
    parser.add_argument('--categories-file', default='data/shopify-categories.txt', 
                      help='Path to categories file (default: data/shopify-categories.txt)')
    parser.add_argument('--openai-api-key', help='OpenAI API key (or set OPENAI_API_KEY env var)')
    parser.add_argument('--limit', type=int, help='Limit number of products to process (for testing)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    # If no arguments provided, use default files for testing
    if len(sys.argv) == 1:
        print("No arguments provided. Usage:")
        print("python categorize_products.py <input_file> --openai-api-key <key>")
        print("\nExample:")
        print("python categorize_products.py data/shopify_products.csv --openai-api-key sk-... --limit 10")
        sys.exit(1)
    
    args = parser.parse_args()
    
    # Get OpenAI API key
    api_key = args.openai_api_key or os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Error: OpenAI API key is required. Provide it via --openai-api-key or OPENAI_API_KEY environment variable.")
        sys.exit(1)
    
    # Check if files exist
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)
    
    if not os.path.exists(args.categories_file):
        print(f"Error: Categories file '{args.categories_file}' not found.")
        sys.exit(1)
    
    try:
        # Initialize categorizer
        categorizer = ProductCategorizer(
            openai_api_key=api_key,
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
            print(f"\n✅ Categorization complete!")
            print(f"📁 Output file: {output_file}")
            print(f"🏷️  Products have been categorized with Shopify taxonomy categories")
            print(f"🔄 This file is ready for Shopify upload with proper categories")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()