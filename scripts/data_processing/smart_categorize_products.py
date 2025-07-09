#!/usr/bin/env python3
"""
Smart Product Categorization Script

This script analyzes product titles and tags to automatically assign the most appropriate
Shopify taxonomy categories based on keyword matching and intelligent scoring.
"""

import pandas as pd
import re
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import argparse


class SmartCategorizer:
    """Intelligent product categorization based on title and tag analysis."""
    
    def __init__(self, categories_file: str):
        """Initialize with Shopify categories file."""
        self.categories = self._load_categories(categories_file)
        self.keyword_mappings = self._build_keyword_mappings()
    
    def _load_categories(self, categories_file: str) -> Dict[str, str]:
        """Load categories from the shopify-categories.txt file."""
        categories = {}
        
        with open(categories_file, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                
                # Look for the pattern: gid://shopify/TaxonomyCategory/... : Category Name
                if 'gid://shopify/TaxonomyCategory/' in line and ' : ' in line:
                    try:
                        # Split on ' : ' to separate GID from category name
                        parts = line.split(' : ', 1)
                        if len(parts) == 2:
                            gid = parts[0].strip()
                            category_path = parts[1].strip()
                            categories[gid] = category_path
                    except Exception as e:
                        print(f"Error parsing line: {line} - {e}")
                        continue
        
        print(f"Loaded {len(categories)} categories")
        return categories
    
    def _build_keyword_mappings(self) -> Dict[str, List[Tuple[str, str, int]]]:
        """Build keyword mappings for intelligent categorization."""
        keyword_mappings = defaultdict(list)
        
        # Define keyword patterns with scores (higher = better match)
        patterns = {
            # Scanners - Use correct el-13-6 category
            r'\bscann?ers?\b': [
                ('el-13-6', 'Electronics > Print, Copy, Scan & Fax > Scanners', 100),
                ('el-7-9-12-1', 'Electronics > Electronics Accessories > Computer Components > Input Devices > Barcode Scanners', 80),
                ('os-10', 'Office Supplies > Office Equipment', 70)  # Fallback for office scanners
            ],
            r'\bscansnap\b': [
                ('el-13-6', 'Electronics > Print, Copy, Scan & Fax > Scanners', 100)
            ],
            r'\badf scanner\b': [
                ('el-13-6-6', 'Electronics > Print, Copy, Scan & Fax > Scanners > Sheetfed Scanners', 100)
            ],
            r'\bdocument scanner\b': [
                ('el-13-6', 'Electronics > Print, Copy, Scan & Fax > Scanners', 100)
            ],
            r'\bflatbed scanner\b': [
                ('el-13-6-3', 'Electronics > Print, Copy, Scan & Fax > Scanners > Flatbed Scanners', 100)
            ],
            r'\bportable scanner\b': [
                ('el-13-6-5', 'Electronics > Print, Copy, Scan & Fax > Scanners > Portable Scanners', 100)
            ],
            
            # Computer Monitors
            r'\bmonitors?\b': [
                ('el-17-1', 'Electronics > Video > Computer Monitors', 100)
            ],
            r'\blcd monitor\b': [
                ('el-17-1', 'Electronics > Video > Computer Monitors', 100)
            ],
            r'\b4k.*monitor\b': [
                ('el-17-1', 'Electronics > Video > Computer Monitors', 100)
            ],
            
            # Docking Stations
            r'\bdocking stations?\b': [
                ('el-7-8-7', 'Electronics > Electronics Accessories > Computer Accessories > Laptop Docking Stations', 100)
            ],
            r'\bdocking\b': [
                ('el-7-8-7', 'Electronics > Electronics Accessories > Computer Accessories > Laptop Docking Stations', 90)
            ],
            
            # Computer Accessories
            r'\busb.*hub\b': [
                ('el-7-9-16', 'Electronics > Electronics Accessories > Computer Components > USB & FireWire Hubs', 100)
            ],
            r'\bkeyboards?\b': [
                ('el-7-9-12-8', 'Electronics > Electronics Accessories > Computer Components > Input Devices > Keyboards', 100)
            ],
            r'\bmice\b|\bmouse\b': [
                ('el-7-9-12-11', 'Electronics > Electronics Accessories > Computer Components > Input Devices > Mice & Trackballs', 100)
            ],
            
            # Phones and Communication
            r'\bip phones?\b': [
                ('el-8-3-7', 'Electronics > Communications > Telephony > VoIP Phones', 100)
            ],
            r'\bphones?\b': [
                ('el-8-3', 'Electronics > Communications > Telephony', 90)
            ],
            r'\bcorded\b.*\bphone\b': [
                ('el-8-3-3', 'Electronics > Communications > Telephony > Corded Telephones', 95)
            ],
            
            # Printers and Printing
            r'\bprinters?\b': [
                ('el-13-4', 'Electronics > Print, Copy, Scan & Fax > Printers, Copiers & Fax Machines', 100)
            ],
            r'\blaser.*printer\b': [
                ('el-13-4', 'Electronics > Print, Copy, Scan & Fax > Printers, Copiers & Fax Machines', 100)
            ],
            r'\bmultifunction.*printer\b': [
                ('el-13-4', 'Electronics > Print, Copy, Scan & Fax > Printers, Copiers & Fax Machines', 100)
            ],
            r'\btoner\b.*\bcartridge\b': [
                ('el-13-3-1-7', 'Electronics > Print, Copy, Scan & Fax > Printer, Copier & Fax Machine Accessories > Printer Consumables > Toner & Inkjet Cartridges', 100)
            ],
            r'\bink.*cartridge\b': [
                ('el-13-3-1-7', 'Electronics > Print, Copy, Scan & Fax > Printer, Copier & Fax Machine Accessories > Printer Consumables > Toner & Inkjet Cartridges', 100)
            ],
            
            # Networking Equipment
            r'\brouters?\b': [
                ('el-8-2-8', 'Electronics > Communications > Networking Equipment > Network Routers', 100)
            ],
            r'\bwireless.*router\b': [
                ('el-8-2-8-8', 'Electronics > Communications > Networking Equipment > Network Routers > Wireless Routers', 100)
            ],
            r'\baccess points?\b': [
                ('el-8-2-1', 'Electronics > Communications > Networking Equipment > Network Access Points', 100)
            ],
            r'\brange extenders?\b': [
                ('el-8-2-9', 'Electronics > Communications > Networking Equipment > Network Repeaters & Extenders', 100)
            ],
            
            # Computers
            r'\bdesktop.*computers?\b': [
                ('el-6-3', 'Electronics > Computers > Desktop Computers', 100)
            ],
            r'\blaptops?\b': [
                ('el-6-6', 'Electronics > Computers > Laptops', 100)
            ],
            r'\btablets?\b': [
                ('el-6-8', 'Electronics > Computers > Tablet Computers', 100)
            ],
            
            # Office Equipment
            r'\bcalculators?\b': [
                ('os-10-2', 'Office Supplies > Office Equipment > Calculators', 100)
            ],
            r'\blabel makers?\b': [
                ('os-10-4', 'Office Supplies > Office Equipment > Label Makers', 100)
            ],
            r'\blaminators?\b': [
                ('os-10-5', 'Office Supplies > Office Equipment > Laminators', 100)
            ],
            r'\bshredders?\b': [
                ('os-10-6', 'Office Supplies > Office Equipment > Office Shredders', 100)
            ],
            
            # Office Supplies - Filing & Organization
            r'\bbinders?\b': [
                ('os-3-2-2', 'Office Supplies > Filing & Organization > Binding Supplies > Binders', 100)
            ],
            r'\bfile folders?\b': [
                ('os-3-12', 'Office Supplies > Filing & Organization > File Folders', 100)
            ],
            r'\bfile.*organizers?\b': [
                ('os-3-10-3', 'Office Supplies > Filing & Organization > Desk Organizers > File Sorters', 100)
            ],
            r'\bdesk.*organizers?\b': [
                ('os-3-10-1', 'Office Supplies > Filing & Organization > Desk Organizers > Desktop Organizers', 100)
            ],
            
            # General Office Supplies
            r'\bstapler\b': [
                ('os-4-14', 'Office Supplies > General Office Supplies > Staplers', 100)
            ],
            r'\bstaples\b': [
                ('os-4-13', 'Office Supplies > General Office Supplies > Staples', 100)
            ],
            r'\bpens?\b': [
                ('os-4-10', 'Office Supplies > General Office Supplies > Pens', 100)
            ],
            r'\bpencils?\b': [
                ('os-4-9', 'Office Supplies > General Office Supplies > Pencils', 100)
            ],
            r'\bpaper\b': [
                ('os-4-9-11', 'Office Supplies > General Office Supplies > Paper Products > Printer & Copier Paper', 90)
            ],
            
            # Cleaning and Maintenance
            r'\bcleaner\b|\bcleaning\b': [
                ('hg-4-1', 'Home & Garden > Household Supplies > Household Cleaning Supplies', 100)
            ],
            r'\bsanitiz\w+\b': [
                ('hg-4-1-2', 'Home & Garden > Household Supplies > Household Cleaning Supplies > Disinfectants & Sanitizers', 100)
            ],
            
            # Food and Beverages
            r'\btea\b.*\bk-?cups?\b': [
                ('fb-2-4-13', 'Food, Beverages & Tobacco > Beverages > Tea > Tea Bags & Sachets', 100)
            ],
            r'\bcoffee\b.*\bk-?cups?\b': [
                ('fb-2-2-1-3', 'Food, Beverages & Tobacco > Beverages > Coffee > Coffee Pods & Capsules', 100)
            ],
            
            # Bags and Cases  
            r'\bbackpacks?\b': [
                ('aa-4-1', 'Apparel & Accessories > Handbags, Wallets & Cases > Backpacks', 100)
            ],
            r'\bcarrying.*case\b': [
                ('aa-4-3', 'Apparel & Accessories > Handbags, Wallets & Cases > Cases', 100)
            ],
            
            # General Technology/Electronics fallback
            r'\btechnology\b|\belectronics?\b|\bIT\b': [
                ('el', 'Electronics', 50)  # Low score fallback
            ],
            
            # Office Supplies fallback
            r'\boffice\b': [
                ('os', 'Office Supplies', 50)  # Low score fallback
            ]
        }
        
        # Build the keyword mappings
        for pattern, category_list in patterns.items():
            for gid, name, score in category_list:
                # Find the full GID if it's a partial match
                full_gid = self._find_category_gid(gid)
                if full_gid:
                    keyword_mappings[pattern].append((full_gid, name, score))
        
        return keyword_mappings
    
    def _find_category_gid(self, partial_gid: str) -> Optional[str]:
        """Find the full GID for a partial category ID."""
        target_id = partial_gid.replace('gid://shopify/TaxonomyCategory/', '')
        
        for gid in self.categories.keys():
            gid_id = gid.replace('gid://shopify/TaxonomyCategory/', '')
            if gid_id == target_id:
                return gid
        
        return None
    
    def _score_category_match(self, text: str, tags: str) -> List[Tuple[str, str, int]]:
        """Score categories based on text analysis."""
        combined_text = f"{text} {tags}".lower()
        category_scores = defaultdict(int)
        category_names = {}
        
        # Score based on keyword patterns
        for pattern, category_list in self.keyword_mappings.items():
            if re.search(pattern, combined_text, re.IGNORECASE):
                for gid, name, score in category_list:
                    category_scores[gid] += score
                    category_names[gid] = name
        
        # Convert to sorted list
        scored_categories = [
            (gid, category_names[gid], score)
            for gid, score in category_scores.items()
        ]
        
        return sorted(scored_categories, key=lambda x: x[2], reverse=True)
    
    def categorize_product(self, title: str, tags: str, product_type: str = "") -> Tuple[str, str, int]:
        """Categorize a single product and return (gid, category_name, confidence_score)."""
        # Combine all text for analysis
        full_text = f"{title} {tags} {product_type}"
        
        # Get scored categories
        scored_categories = self._score_category_match(full_text, tags)
        
        if scored_categories:
            gid, name, score = scored_categories[0]
            return gid, name, score
        else:
            # Default fallback to general Office Supplies
            default_gid = 'gid://shopify/TaxonomyCategory/os'
            return default_gid, self.categories.get(default_gid, 'Office Supplies'), 25
    
    def categorize_csv(self, input_file: str, output_file: str) -> None:
        """Process entire CSV file and add category information."""
        print(f"Reading CSV file: {input_file}")
        df = pd.read_csv(input_file)
        
        # Ensure required columns exist
        if 'title' not in df.columns:
            raise ValueError("CSV must contain 'title' column")
        
        # Fill NaN values
        df['tags'] = df['tags'].fillna('')
        df['product_type'] = df['product_type'].fillna('')
        
        # Categorize each product
        category_gids = []
        category_names = []
        confidence_scores = []
        
        print("Categorizing products...")
        for idx, row in df.iterrows():
            if idx % 100 == 0:
                print(f"Processed {idx}/{len(df)} products...")
            
            title = str(row['title']) if pd.notna(row['title']) else ''
            tags = str(row['tags']) if pd.notna(row['tags']) else ''
            product_type = str(row['product_type']) if pd.notna(row['product_type']) else ''
            
            gid, name, score = self.categorize_product(title, tags, product_type)
            
            category_gids.append(gid)
            category_names.append(name)
            confidence_scores.append(score)
        
        # Add new columns
        df['category_gid'] = category_gids
        df['category_name'] = category_names
        df['category_confidence'] = confidence_scores
        
        # Save updated CSV
        print(f"Saving updated CSV to: {output_file}")
        df.to_csv(output_file, index=False)
        
        # Print categorization summary
        self._print_summary(df)
    
    def _print_summary(self, df: pd.DataFrame) -> None:
        """Print categorization summary statistics."""
        print("\n" + "="*60)
        print("CATEGORIZATION SUMMARY")
        print("="*60)
        
        # Overall stats
        total_products = len(df)
        print(f"Total products categorized: {total_products}")
        
        # Confidence distribution
        high_confidence = len(df[df['category_confidence'] >= 90])
        medium_confidence = len(df[(df['category_confidence'] >= 70) & (df['category_confidence'] < 90)])
        low_confidence = len(df[df['category_confidence'] < 70])
        
        print(f"\nConfidence Distribution:")
        print(f"  High (90+): {high_confidence} ({high_confidence/total_products*100:.1f}%)")
        print(f"  Medium (70-89): {medium_confidence} ({medium_confidence/total_products*100:.1f}%)")
        print(f"  Low (<70): {low_confidence} ({low_confidence/total_products*100:.1f}%)")
        
        # Top categories
        print(f"\nTop Categories:")
        top_categories = df['category_name'].value_counts().head(10)
        for category, count in top_categories.items():
            print(f"  {category}: {count} products")
        
        # Low confidence products (for manual review)
        if low_confidence > 0:
            print(f"\nProducts with low confidence (manual review recommended):")
            low_conf_products = df[df['category_confidence'] < 70][['title', 'category_name', 'category_confidence']].head(10)
            for _, row in low_conf_products.iterrows():
                print(f"  '{row['title'][:50]}...' -> {row['category_name']} (confidence: {row['category_confidence']})")


def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(
        description='Smart Product Categorization for Shopify Taxonomy',
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument('input_csv', help='Path to input CSV file')
    parser.add_argument('--categories', default='data/shopify-categories.txt',
                       help='Path to Shopify categories file (default: data/shopify-categories.txt)')
    parser.add_argument('--output', help='Output CSV file (default: input_file with _categorized suffix)')
    
    args = parser.parse_args()
    
    # Determine output file
    if not args.output:
        base_name = args.input_csv.replace('.csv', '')
        args.output = f"{base_name}_recategorized.csv"
    
    try:
        # Initialize categorizer
        categorizer = SmartCategorizer(args.categories)
        
        # Process CSV
        categorizer.categorize_csv(args.input_csv, args.output)
        
        print(f"\n✅ Categorization complete! Results saved to: {args.output}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())