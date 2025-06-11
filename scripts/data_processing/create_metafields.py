"""
Metafield Creator Module

This module handles transforming product data into Shopify metafield format.
Implements chunked processing, performance tracking, and data validation.
"""

import pandas as pd
import json
import os
import time
import logging
import chardet
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class MetafieldCreator:
    """Transforms product data into Shopify metafields format."""

    # Column mapping for Shopify format
    COLUMN_MAPPING = {
        'Title': 'title',
        'Description': 'body_html',
        'Vendor': 'vendor',
        'Type': 'product_type',
        'SKU': 'sku',
        'Price': 'price',
        'Inventory': 'inventory_quantity'
    }

    def __init__(
        self,
        chunk_size: int = 1000,
        logger: Optional[logging.Logger] = None,
        json_validator = None,
        csv_reader = None
    ):
        """
        Initialize MetafieldCreator with optional injected dependencies.
        
        Args:
            chunk_size: Number of rows to process at a time
            logger: Optional logger instance
            json_validator: Optional JSON validator for metafield format
            csv_reader: Optional CSV reader for testing
        """
        self.chunk_size = chunk_size
        self.logger = logger or logging.getLogger(__name__)
        self.json_validator = json_validator
        self.csv_reader = csv_reader
        self.transform_metrics = {
            'start_time': 0.0,
            'total_products': 0,
            'processing_time': 0.0
        }

    def detect_encoding(self, file_path: str) -> str:
        """
        Detect the encoding of a file.
        
        Args:
            file_path: Path to file to analyze
            
        Returns:
            Detected encoding string
        """
        with open(file_path, 'rb') as f:
            raw_data = f.read(min(os.path.getsize(file_path), 1000000))  # Read up to 1MB
        result = chardet.detect(raw_data)
        return result['encoding']

    def normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names to match Shopify format.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with normalized column names
        """
        # First, map known columns
        renamed = df.rename(columns=self.COLUMN_MAPPING)
        
        # Then handle any remaining columns by lowercasing
        remaining_cols = {
            col: col.lower() 
            for col in renamed.columns 
            if col not in self.COLUMN_MAPPING.values()
        }
        return renamed.rename(columns=remaining_cols)

    def transform(self, input_csv: str, output_csv: str = None) -> List[Dict]:
        """
        Transform CSV file data into Shopify metafields format.
        
        Args:
            input_csv: Path to input CSV file
            output_csv: Optional path to save transformed CSV
            
        Returns:
            List of transformed product dictionaries
            
        Raises:
            FileNotFoundError: If input file doesn't exist
        """
        if not os.path.exists(input_csv):
            raise FileNotFoundError(f"Input file not found: {input_csv}")

        self.logger.info(f"Processing CSV file: {input_csv}")
        self.transform_metrics['start_time'] = time.time()

        file_encoding = self.detect_encoding(input_csv)
        self.logger.info(f"Detected file encoding: {file_encoding}")
        
        # Get the header and normalize column names
        df_header = (
            self.csv_reader.read_header(input_csv)
            if self.csv_reader
            else pd.read_csv(
                input_csv,
                nrows=0,
                encoding=file_encoding,
                encoding_errors='replace',
                low_memory=False
            )
        )
        df_header = self.normalize_columns(df_header)
        all_columns = df_header.columns.tolist()
        
        # Identify metadata columns after normalization
        metadata_columns = [
            col for col in all_columns 
            if col.startswith("metafield: custom.")
            or col.startswith("Metafield: custom.")
        ]
        product_columns = [
            col for col in all_columns 
            if not col.startswith("metafield: custom.")
            and not col.startswith("Metafield: custom.")
        ]
        
        self.logger.info(f"Found {len(metadata_columns)} metadata columns to consolidate")
        
        transformed_data = []
        reader = (
            self.csv_reader.read_chunks(input_csv, self.chunk_size)
            if self.csv_reader
            else pd.read_csv(
                input_csv,
                chunksize=self.chunk_size,
                encoding=file_encoding,
                encoding_errors='replace',
                low_memory=False
            )
        )
        
        # Get total rows for progress tracking
        total_rows = sum(1 for _ in pd.read_csv(input_csv, encoding=file_encoding))
        self.logger.info(f"Total products to process: {total_rows}")

        processed_rows = 0
        start_time = time.time()
        
        for chunk_num, chunk in enumerate(reader, 1):
            # Normalize column names
            chunk = self.normalize_columns(chunk)
            
            chunk_data = []
            for _, row in chunk.iterrows():
                # Create product data with normalized field names
                product_data = {
                    col: row[col] 
                    for col in product_columns 
                    if pd.notna(row[col])
                }
                
                # Add metafields
                product_data['metafields'] = self.create_metafield_json(row, metadata_columns)
                chunk_data.append(product_data)
                
            # Update progress
            processed_rows += len(chunk_data)
            progress = (processed_rows / total_rows) * 100
            
            # Calculate time estimates
            elapsed_time = time.time() - start_time
            avg_time_per_row = elapsed_time / processed_rows
            remaining_rows = total_rows - processed_rows
            estimated_time_remaining = remaining_rows * avg_time_per_row
            
            self.logger.info(
                f"Progress: {progress:.1f}% ({processed_rows}/{total_rows} products) | "
                f"Est. time remaining: {estimated_time_remaining:.1f}s"
            )
            
            transformed_data.extend(chunk_data)
                
        if output_csv:
            pd.DataFrame(transformed_data).to_csv(output_csv, index=False)
            self.logger.info(f"Done! CSV with consolidated metafields saved to: {output_csv}")
            
        # Calculate and verify performance metrics
        self.transform_metrics['total_products'] = len(transformed_data)
        self.transform_metrics['processing_time'] = time.time() - self.transform_metrics['start_time']
        avg_time_per_product = (
            self.transform_metrics['processing_time'] * 1000 / 
            self.transform_metrics['total_products']
        )
        
        self.logger.info(
            f"Transformation complete. Average processing time: "
            f"{avg_time_per_product:.2f}ms per product"
        )
        
        if avg_time_per_product > 100:  # Performance requirement from test plan
            self.logger.warning(
                f"Performance threshold exceeded: "
                f"{avg_time_per_product:.2f}ms > 100ms target"
            )
            
        return transformed_data

    def create_metafield_json(self, row: pd.Series, metadata_columns: List[str]) -> Dict:
        """
        Create a JSON metafield from row metadata columns.
        
        Args:
            row: Pandas Series containing product data
            metadata_columns: List of column names containing metadata
            
        Returns:
            Dictionary of metafield data
            
        Raises:
            ValueError: If created metafields fail validation
        """
        metafields = {}
        
        # Print all metadata columns for debugging
        self.logger.info(f"All metadata columns: {metadata_columns}")
        
        for col in metadata_columns:
                
            # Extract the key name from the column name
            key = (col.replace("Metafield: custom.", "")
                     .replace("metafield: custom.", "")
                     .replace("[list.single_line_text]", ""))
            
            # Only add non-empty values
            if pd.notna(row[col]) and row[col] != "":
                # Handle nested keys
                if "." in key:
                    parts = key.split(".")
                    current = metafields
                    for i, part in enumerate(parts):
                        if i == len(parts) - 1:
                            current[part] = row[col]
                        else:
                            if part not in current:
                                current[part] = {}
                            current = current[part]
                else:
                    metafields[key] = row[col]

        # Validate metafield format if validator is provided
        if self.json_validator:
            if not self.json_validator.validate(metafields):
                self.logger.error("Invalid metafield format detected")
                raise ValueError("Created metafields failed validation")
            
        return metafields

def main():
    """Main function for testing."""
    import sys
    
    if len(sys.argv) < 2:
        logging.error("Input file path required as first argument")
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_file = os.path.join(
        os.path.dirname(input_file),
        f"shopify_{os.path.basename(input_file)}"
    )
    
    if not os.path.exists(input_file):
        logging.error(f"Input file not found: {input_file}")
        sys.exit(1)

    try:
        creator = MetafieldCreator()
        creator.transform(input_file, output_file)
    except Exception as e:
        logging.error(f"Transformation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
