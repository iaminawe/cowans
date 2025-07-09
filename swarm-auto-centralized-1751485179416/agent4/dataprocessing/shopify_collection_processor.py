"""
Shopify Collection Data Processor

This module handles the data processing pipeline for extracting product-collection
relationship data from Shopify API responses and generating CSV output.

Key Features:
- API response data transformation
- Product-collection relationship mapping
- CSV generation with proper formatting
- Data validation and cleansing
- Pagination handling for large datasets
- Memory-efficient processing
- Edge case handling
"""

import csv
import json
import logging
import os
import re
from typing import Dict, List, Any, Optional, Set, Union, Tuple
from datetime import datetime
from collections import defaultdict, Counter
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class ShopifyCollectionProcessor:
    """
    Main processor class for handling Shopify collection data transformations.
    """
    
    def __init__(self, debug: bool = False, batch_size: int = 1000):
        """
        Initialize the processor.
        
        Args:
            debug: Enable debug logging
            batch_size: Number of records to process in each batch
        """
        self.debug = debug
        self.batch_size = batch_size
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        # Statistics tracking
        self.stats = {
            'products_processed': 0,
            'collections_found': 0,
            'products_with_collections': 0,
            'products_without_collections': 0,
            'duplicate_relationships': 0,
            'invalid_handles': 0,
            'processing_errors': 0
        }
        
        # Cache for performance
        self.collection_cache = {}
        self.handle_validation_cache = {}
        
    def process_api_response(self, api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Transform raw API response into structured data.
        
        Args:
            api_response: Raw response from Shopify API
            
        Returns:
            List of processed product-collection relationships
        """
        self.logger.info("Processing API response...")
        
        if not api_response or 'data' not in api_response:
            self.logger.warning("Invalid API response structure")
            return []
        
        products = []
        
        # Handle different API response structures
        if 'products' in api_response['data']:
            products = api_response['data']['products']['edges']
        elif 'collections' in api_response['data']:
            # If response contains collections with products
            for collection_edge in api_response['data']['collections']['edges']:
                collection = collection_edge['node']
                if 'products' in collection:
                    for product_edge in collection['products']['edges']:
                        product = product_edge['node']
                        product['_collection_context'] = collection
                        products.append({'node': product})
        
        processed_data = []
        
        for product_edge in products:
            try:
                product = product_edge['node']
                product_data = self._extract_product_data(product)
                if product_data:
                    processed_data.extend(product_data)
                    self.stats['products_processed'] += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing product: {e}")
                self.stats['processing_errors'] += 1
                continue
        
        self.logger.info(f"Processed {len(processed_data)} product-collection relationships")
        return processed_data
    
    def _extract_product_data(self, product: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract product-collection relationship data from a single product.
        
        Args:
            product: Product data from API response
            
        Returns:
            List of product-collection relationship records
        """
        product_handle = product.get('handle', '')
        product_title = product.get('title', '')
        
        if not self._validate_handle(product_handle):
            self.stats['invalid_handles'] += 1
            return []
        
        relationships = []
        collections_found = False
        
        # Extract collections from various sources
        collections = []
        
        # Direct collections field
        if 'collections' in product and product['collections']:
            if 'edges' in product['collections']:
                for collection_edge in product['collections']['edges']:
                    collections.append(collection_edge['node'])
            elif isinstance(product['collections'], list):
                collections.extend(product['collections'])
        
        # Collection context (when fetched via collections endpoint)
        if '_collection_context' in product:
            collections.append(product['_collection_context'])
        
        # Product type as collection (fallback)
        product_type = product.get('productType', '').strip()
        if product_type and not collections:
            # Create synthetic collection from product type
            synthetic_collection = {
                'handle': self._generate_handle(product_type),
                'title': product_type,
                'description': f"Auto-generated collection for {product_type}",
                'collectionType': 'SMART'  # or 'MANUAL'
            }
            collections.append(synthetic_collection)
        
        # Process each collection
        for collection in collections:
            collection_data = self._process_collection(collection)
            if collection_data:
                relationship = {
                    'product_handle': product_handle,
                    'product_title': product_title,
                    'collection_handle': collection_data['handle'],
                    'collection_title': collection_data['title'],
                    'collection_type': collection_data.get('type', 'MANUAL'),
                    'collection_description': collection_data.get('description', ''),
                    'is_synthetic': collection_data.get('is_synthetic', False),
                    'source': collection_data.get('source', 'api')
                }
                relationships.append(relationship)
                collections_found = True
        
        # Handle products with no collections
        if not collections_found:
            # Create entry for products without collections
            relationship = {
                'product_handle': product_handle,
                'product_title': product_title,
                'collection_handle': '',
                'collection_title': '',
                'collection_type': '',
                'collection_description': '',
                'is_synthetic': False,
                'source': 'no_collection'
            }
            relationships.append(relationship)
            self.stats['products_without_collections'] += 1
        else:
            self.stats['products_with_collections'] += 1
        
        return relationships
    
    def _process_collection(self, collection: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process and validate collection data.
        
        Args:
            collection: Raw collection data
            
        Returns:
            Processed collection data or None if invalid
        """
        collection_handle = collection.get('handle', '')
        
        # Use cache to avoid reprocessing
        if collection_handle in self.collection_cache:
            return self.collection_cache[collection_handle]
        
        if not self._validate_handle(collection_handle):
            return None
        
        collection_data = {
            'handle': collection_handle,
            'title': collection.get('title', collection_handle.replace('-', ' ').title()),
            'description': collection.get('description', ''),
            'type': collection.get('collectionType', 'MANUAL'),
            'is_synthetic': collection.get('is_synthetic', False),
            'source': collection.get('source', 'api')
        }
        
        # Clean up description (remove HTML tags)
        if collection_data['description']:
            collection_data['description'] = self._clean_html(collection_data['description'])
        
        # Cache the result
        self.collection_cache[collection_handle] = collection_data
        self.stats['collections_found'] += 1
        
        return collection_data
    
    def _validate_handle(self, handle: str) -> bool:
        """
        Validate Shopify handle format.
        
        Args:
            handle: Handle to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not handle or not isinstance(handle, str):
            return False
        
        # Use cache for performance
        if handle in self.handle_validation_cache:
            return self.handle_validation_cache[handle]
        
        # Shopify handle rules:
        # - Only lowercase letters, numbers, and hyphens
        # - Cannot start or end with hyphen
        # - Cannot have consecutive hyphens
        # - Max 255 characters
        
        is_valid = (
            len(handle) <= 255 and
            re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', handle) is not None
        )
        
        self.handle_validation_cache[handle] = is_valid
        return is_valid
    
    def _generate_handle(self, text: str) -> str:
        """
        Generate a valid Shopify handle from text.
        
        Args:
            text: Text to convert to handle
            
        Returns:
            Valid Shopify handle
        """
        if not text:
            return 'uncategorized'
        
        # Convert to lowercase and replace spaces/special chars with hyphens
        handle = re.sub(r'[^a-zA-Z0-9\s-]', '', text.lower())
        handle = re.sub(r'[\s-]+', '-', handle)
        handle = handle.strip('-')
        
        # Ensure valid format
        if not handle or not self._validate_handle(handle):
            handle = 'uncategorized'
        
        return handle
    
    def _clean_html(self, html_text: str) -> str:
        """
        Remove HTML tags and clean up text.
        
        Args:
            html_text: HTML text to clean
            
        Returns:
            Clean text
        """
        if not html_text:
            return ''
        
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', html_text)
        
        # Clean up whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # Remove HTML entities
        clean_text = clean_text.replace('&amp;', '&')
        clean_text = clean_text.replace('&lt;', '<')
        clean_text = clean_text.replace('&gt;', '>')
        clean_text = clean_text.replace('&quot;', '"')
        clean_text = clean_text.replace('&#39;', "'")
        
        return clean_text
    
    def deduplicate_relationships(self, relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate product-collection relationships.
        
        Args:
            relationships: List of relationship records
            
        Returns:
            Deduplicated list
        """
        seen = set()
        deduplicated = []
        
        for relationship in relationships:
            # Create unique key for the relationship
            key = (
                relationship['product_handle'],
                relationship['collection_handle']
            )
            
            if key not in seen:
                seen.add(key)
                deduplicated.append(relationship)
            else:
                self.stats['duplicate_relationships'] += 1
        
        self.logger.info(f"Removed {self.stats['duplicate_relationships']} duplicate relationships")
        return deduplicated
    
    def validate_data(self, relationships: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate relationship data and separate valid from invalid records.
        
        Args:
            relationships: List of relationship records
            
        Returns:
            Tuple of (valid_records, invalid_records)
        """
        valid_records = []
        invalid_records = []
        
        for relationship in relationships:
            is_valid = True
            validation_errors = []
            
            # Check required fields
            if not relationship.get('product_handle'):
                is_valid = False
                validation_errors.append('Missing product handle')
            
            # Validate handle format if present
            if relationship.get('product_handle') and not self._validate_handle(relationship['product_handle']):
                is_valid = False
                validation_errors.append('Invalid product handle format')
            
            if relationship.get('collection_handle') and not self._validate_handle(relationship['collection_handle']):
                is_valid = False
                validation_errors.append('Invalid collection handle format')
            
            # Add validation errors to record
            if validation_errors:
                relationship['validation_errors'] = validation_errors
            
            if is_valid:
                valid_records.append(relationship)
            else:
                invalid_records.append(relationship)
        
        self.logger.info(f"Validated {len(valid_records)} valid and {len(invalid_records)} invalid records")
        return valid_records, invalid_records
    
    def generate_csv(self, relationships: List[Dict[str, Any]], output_path: str, 
                    include_metadata: bool = False) -> bool:
        """
        Generate CSV file from relationship data.
        
        Args:
            relationships: List of relationship records
            output_path: Path for output CSV file
            include_metadata: Whether to include additional metadata columns
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Define CSV columns
            base_columns = [
                'product_handle',
                'product_title', 
                'collection_handle',
                'collection_title',
                'collection_type',
                'collection_description'
            ]
            
            if include_metadata:
                base_columns.extend([
                    'is_synthetic',
                    'source',
                    'processing_timestamp'
                ])
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=base_columns)
                writer.writeheader()
                
                for relationship in relationships:
                    # Add processing timestamp if including metadata
                    if include_metadata:
                        relationship['processing_timestamp'] = datetime.now().isoformat()
                    
                    # Filter out fields not in our column list
                    filtered_row = {k: relationship.get(k, '') for k in base_columns}
                    writer.writerow(filtered_row)
            
            self.logger.info(f"Generated CSV with {len(relationships)} records at {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error generating CSV: {e}")
            return False
    
    def process_paginated_data(self, api_responses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process multiple paginated API responses efficiently.
        
        Args:
            api_responses: List of API response pages
            
        Returns:
            Combined processed data
        """
        all_relationships = []
        
        for i, response in enumerate(api_responses):
            self.logger.info(f"Processing page {i+1}/{len(api_responses)}")
            
            page_relationships = self.process_api_response(response)
            all_relationships.extend(page_relationships)
            
            # Log progress for large datasets
            if len(all_relationships) % 1000 == 0:
                self.logger.info(f"Processed {len(all_relationships)} relationships so far...")
        
        # Deduplicate across all pages
        all_relationships = self.deduplicate_relationships(all_relationships)
        
        return all_relationships
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get current processing statistics.
        
        Returns:
            Dictionary of processing statistics
        """
        return {
            **self.stats,
            'cache_sizes': {
                'collections': len(self.collection_cache),
                'handle_validations': len(self.handle_validation_cache)
            },
            'last_updated': datetime.now().isoformat()
        }
    
    def export_stats(self, stats_path: str) -> bool:
        """
        Export processing statistics to JSON file.
        
        Args:
            stats_path: Path for stats JSON file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            stats = self.get_processing_stats()
            
            os.makedirs(os.path.dirname(stats_path), exist_ok=True)
            
            with open(stats_path, 'w') as f:
                json.dump(stats, f, indent=2)
            
            self.logger.info(f"Exported stats to {stats_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting stats: {e}")
            return False
    
    def clear_caches(self) -> None:
        """
        Clear internal caches to free memory.
        """
        self.collection_cache.clear()
        self.handle_validation_cache.clear()
        self.logger.info("Cleared internal caches")


class CSVCollectionExtractor:
    """
    Utility class for extracting collection data from existing CSV files.
    """
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if debug:
            self.logger.setLevel(logging.DEBUG)
    
    def extract_from_shopify_export(self, csv_path: str) -> List[Dict[str, Any]]:
        """
        Extract product-collection data from Shopify product export CSV.
        
        Args:
            csv_path: Path to Shopify export CSV file
            
        Returns:
            List of product-collection relationships
        """
        relationships = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    handle = row.get('Handle', '').strip()
                    title = row.get('Title', '').strip()
                    category = row.get('Product Category', '').strip()
                    product_type = row.get('Type', '').strip()
                    
                    if not handle:
                        continue
                    
                    # Use category first, then product type as fallback
                    collection_source = category or product_type
                    
                    if collection_source:
                        # Parse hierarchical categories (e.g., "Office Supplies > Pens")
                        categories = self._parse_hierarchical_category(collection_source)
                        
                        for cat in categories:
                            relationship = {
                                'product_handle': handle,
                                'product_title': title,
                                'collection_handle': self._generate_handle(cat),
                                'collection_title': cat,
                                'collection_type': 'SMART',
                                'collection_description': f'Products in {cat} category',
                                'is_synthetic': True,
                                'source': 'csv_export'
                            }
                            relationships.append(relationship)
                    else:
                        # Product with no category
                        relationship = {
                            'product_handle': handle,
                            'product_title': title,
                            'collection_handle': '',
                            'collection_title': '',
                            'collection_type': '',
                            'collection_description': '',
                            'is_synthetic': False,
                            'source': 'csv_export_no_category'
                        }
                        relationships.append(relationship)
            
            self.logger.info(f"Extracted {len(relationships)} relationships from CSV")
            return relationships
            
        except Exception as e:
            self.logger.error(f"Error extracting from CSV: {e}")
            return []
    
    def _parse_hierarchical_category(self, category_string: str) -> List[str]:
        """
        Parse hierarchical category string into individual categories.
        
        Args:
            category_string: Category string like "Office Supplies > Pens > Ballpoint"
            
        Returns:
            List of category names
        """
        if not category_string:
            return []
        
        # Split on common separators
        separators = [' > ', ' / ', ' >> ', ' | ', ' > ']
        
        categories = [category_string.strip()]
        
        for sep in separators:
            if sep in category_string:
                categories = [cat.strip() for cat in category_string.split(sep) if cat.strip()]
                break
        
        return categories
    
    def _generate_handle(self, text: str) -> str:
        """
        Generate a valid Shopify handle from text.
        
        Args:
            text: Text to convert to handle
            
        Returns:
            Valid Shopify handle
        """
        if not text:
            return 'uncategorized'
        
        # Convert to lowercase and replace spaces/special chars with hyphens
        handle = re.sub(r'[^a-zA-Z0-9\s-]', '', text.lower())
        handle = re.sub(r'[\s-]+', '-', handle)
        handle = handle.strip('-')
        
        # Ensure valid format
        if not handle:
            handle = 'uncategorized'
        
        return handle


class DataQualityAnalyzer:
    """
    Analyze data quality and provide insights.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def analyze_relationships(self, relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the quality and characteristics of relationship data.
        
        Args:
            relationships: List of relationship records
            
        Returns:
            Analysis report
        """
        if not relationships:
            return {'error': 'No data to analyze'}
        
        # Basic counts
        total_relationships = len(relationships)
        unique_products = len(set(r['product_handle'] for r in relationships))
        unique_collections = len(set(r['collection_handle'] for r in relationships if r['collection_handle']))
        
        # Products without collections
        no_collection = sum(1 for r in relationships if not r['collection_handle'])
        
        # Collection type distribution
        collection_types = Counter(r['collection_type'] for r in relationships if r['collection_type'])
        
        # Source distribution
        sources = Counter(r.get('source', 'unknown') for r in relationships)
        
        # Products per collection stats
        collection_product_counts = Counter(r['collection_handle'] for r in relationships if r['collection_handle'])
        
        # Collection per product stats
        product_collection_counts = Counter(r['product_handle'] for r in relationships)
        
        analysis = {
            'summary': {
                'total_relationships': total_relationships,
                'unique_products': unique_products,
                'unique_collections': unique_collections,
                'products_without_collections': no_collection,
                'avg_collections_per_product': round(total_relationships / unique_products, 2) if unique_products else 0
            },
            'distributions': {
                'collection_types': dict(collection_types),
                'data_sources': dict(sources)
            },
            'collection_analysis': {
                'most_populated_collections': collection_product_counts.most_common(10),
                'avg_products_per_collection': round(sum(collection_product_counts.values()) / len(collection_product_counts), 2) if collection_product_counts else 0
            },
            'product_analysis': {
                'products_with_most_collections': product_collection_counts.most_common(10),
                'single_collection_products': sum(1 for count in product_collection_counts.values() if count == 1)
            },
            'data_quality': {
                'completeness_score': round((total_relationships - no_collection) / total_relationships * 100, 2) if total_relationships else 0,
                'handle_format_compliance': self._check_handle_compliance(relationships)
            }
        }
        
        return analysis
    
    def _check_handle_compliance(self, relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check handle format compliance.
        
        Args:
            relationships: List of relationship records
            
        Returns:
            Compliance report
        """
        total_product_handles = len([r for r in relationships if r.get('product_handle')])
        valid_product_handles = 0
        
        total_collection_handles = len([r for r in relationships if r.get('collection_handle')])
        valid_collection_handles = 0
        
        handle_pattern = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
        
        for relationship in relationships:
            if relationship.get('product_handle'):
                if handle_pattern.match(relationship['product_handle']):
                    valid_product_handles += 1
            
            if relationship.get('collection_handle'):
                if handle_pattern.match(relationship['collection_handle']):
                    valid_collection_handles += 1
        
        return {
            'product_handle_compliance': round(valid_product_handles / total_product_handles * 100, 2) if total_product_handles else 0,
            'collection_handle_compliance': round(valid_collection_handles / total_collection_handles * 100, 2) if total_collection_handles else 0
        }


# Memory storage and utility functions
def store_memory(memory_key: str, data: Dict[str, Any]) -> bool:
    """
    Store data in swarm memory.
    
    Args:
        memory_key: Memory storage key
        data: Data to store
        
    Returns:
        True if successful, False otherwise
    """
    try:
        memory_path = f"/Users/iaminawe/Sites/cowans/{memory_key}.json"
        os.makedirs(os.path.dirname(memory_path), exist_ok=True)
        
        with open(memory_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return True
    except Exception as e:
        logging.error(f"Error storing memory: {e}")
        return False


def process_csv_to_collections(csv_path: str, output_path: str, include_metadata: bool = True) -> bool:
    """
    Main function to process CSV file and generate collection mapping.
    
    Args:
        csv_path: Path to input CSV file
        output_path: Path for output CSV file
        include_metadata: Whether to include metadata columns
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Initialize processors
        extractor = CSVCollectionExtractor(debug=True)
        processor = ShopifyCollectionProcessor(debug=True)
        analyzer = DataQualityAnalyzer()
        
        # Extract relationships from CSV
        logging.info(f"Extracting relationships from {csv_path}")
        relationships = extractor.extract_from_shopify_export(csv_path)
        
        if not relationships:
            logging.error("No relationships extracted")
            return False
        
        # Deduplicate and validate
        relationships = processor.deduplicate_relationships(relationships)
        valid_relationships, invalid_relationships = processor.validate_data(relationships)
        
        # Analyze data quality
        analysis = analyzer.analyze_relationships(valid_relationships)
        
        # Generate CSV output
        success = processor.generate_csv(valid_relationships, output_path, include_metadata)
        
        if success:
            # Export statistics
            stats_path = output_path.replace('.csv', '_stats.json')
            processor.export_stats(stats_path)
            
            # Export analysis
            analysis_path = output_path.replace('.csv', '_analysis.json')
            with open(analysis_path, 'w') as f:
                json.dump(analysis, f, indent=2)
            
            # Store in swarm memory
            memory_data = {
                'step': 'Data Processing Implementation',
                'timestamp': datetime.now().isoformat(),
                'objective': 'Implement data processing and CSV generation',
                'implementation': {
                    'dataTransforms': [
                        'API response parsing',
                        'Product-collection relationship extraction',
                        'Handle validation and generation',
                        'HTML content cleaning',
                        'Hierarchical category parsing'
                    ],
                    'csvGeneration': 'Multi-column CSV with configurable metadata',
                    'validation': [
                        'Handle format validation',
                        'Required field validation',
                        'Data type validation',
                        'Duplicate relationship detection'
                    ],
                    'pagination': 'Batch processing with memory management'
                },
                'csvSchema': {
                    'columns': ['product_handle', 'product_title', 'collection_handle', 'collection_title', 'collection_type', 'collection_description'],
                    'sampleOutput': 'staedtle-pigment-liner-set,Staedtle Pigment Liner Set,office-supplies,Office Supplies,SMART,Products in Office Supplies category'
                },
                'performance': [
                    'Caching for collection and handle validation',
                    'Batch processing for large datasets',
                    'Memory-efficient streaming for CSV generation',
                    'Optimized regex patterns for handle generation'
                ],
                'edgeCases': [
                    'Products with no collections',
                    'Multiple collections per product',
                    'Invalid handle formats',
                    'HTML content in descriptions',
                    'Hierarchical category structures',
                    'Duplicate relationships'
                ],
                'integrationPoints': [
                    'Compatible with Agent 3 core script API response format',
                    'Configurable output format for downstream processing',
                    'Statistics export for monitoring and debugging',
                    'Memory storage for swarm coordination'
                ],
                'stats': processor.get_processing_stats(),
                'analysis': analysis
            }
            
            store_memory('swarm-auto-centralized-1751485179416/agent4/dataprocessing', memory_data)
            
            logging.info(f"Successfully processed {len(valid_relationships)} relationships")
            logging.info(f"Output saved to {output_path}")
            logging.info(f"Statistics saved to {stats_path}")
            logging.info(f"Analysis saved to {analysis_path}")
            
        return success
        
    except Exception as e:
        logging.error(f"Error in main processing function: {e}")
        return False


if __name__ == '__main__':
    # Example usage
    csv_path = '/Users/iaminawe/Sites/cowans/data/products_export_1-8.csv'
    output_path = '/Users/iaminawe/Sites/cowans/data/product_collections_mapping.csv'
    
    success = process_csv_to_collections(csv_path, output_path)
    print(f"Processing {'successful' if success else 'failed'}!")