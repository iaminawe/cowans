"""
Enhanced Etilize Import Service with Xorosoft API Integration

This service extends the original import service to use Xorosoft API
for product validation instead of CSV file comparison.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from sqlalchemy.orm import Session

from services.import_service import EtilizeImportService, ImportConfiguration, ImportResult
from services.xorosoft_api_service import XorosoftAPIService, ProductMatch, MatchType
from models import EtilizeStagingProduct, ProcessingStatus


class EtilizeImportServiceWithAPI(EtilizeImportService):
    """Enhanced import service that uses Xorosoft API for validation."""
    
    def __init__(self, session: Session, user_id: int, xorosoft_api_key: Optional[str] = None, 
                 xorosoft_api_pass: Optional[str] = None):
        """Initialize the enhanced import service with API support.
        
        Args:
            session: Database session
            user_id: ID of user triggering the import
            xorosoft_api_key: Optional Xorosoft API key
            xorosoft_api_pass: Optional Xorosoft API password
        """
        super().__init__(session, user_id)
        
        # Initialize Xorosoft API service
        try:
            self.xorosoft_api = XorosoftAPIService(xorosoft_api_key, xorosoft_api_pass)
            self.api_available = True
            self.logger.info("Xorosoft API service initialized successfully")
        except ValueError as e:
            self.xorosoft_api = None
            self.api_available = False
            self.logger.warning(f"Xorosoft API not available: {e}")
    
    def validate_with_api(self, staging_product: EtilizeStagingProduct) -> Tuple[bool, Optional[ProductMatch]]:
        """Validate a staging product against Xorosoft API.
        
        Args:
            staging_product: The staging product to validate
            
        Returns:
            Tuple of (is_valid, match_result)
        """
        if not self.api_available:
            # Fallback to basic validation if API not available
            return self._basic_validation(staging_product), None
        
        try:
            # Extract metafields from raw data
            metafields = {}
            raw_data = staging_product.raw_data or {}
            
            # Map metafield columns to API field names
            metafield_mappings = {
                'Metafield: custom.CWS_A[list.single_line_text]': 'CWS_A',
                'Metafield: custom.CWS_Catalog[list.single_line_text]': 'CWS_Catalog',
                'Metafield: custom.SPRC[list.single_line_text]': 'SPRC'
            }
            
            for csv_field, api_field in metafield_mappings.items():
                if csv_field in raw_data and raw_data[csv_field]:
                    metafields[api_field] = raw_data[csv_field]
            
            # Validate product
            match_result = self.xorosoft_api.validate_product(
                staging_product.sku or '',
                metafields
            )
            
            # Update staging product with validation results
            if match_result.matched:
                xorosoft_product = match_result.xorosoft_product
                
                # Update validation status
                staging_product.validation_status = 'valid'
                staging_product.validation_errors = None
                
                # Store match information
                staging_product.mapping_details = {
                    'match_type': match_result.match_type.value,
                    'matched_value': match_result.matched_value,
                    'confidence_score': match_result.confidence_score,
                    'xorosoft_item_number': xorosoft_product.item_number,
                    'xorosoft_base_part': xorosoft_product.base_part_number,
                    'xorosoft_description': xorosoft_product.description
                }
                
                # Check inventory if available
                if hasattr(self.xorosoft_api, 'get_inventory_status'):
                    inventory = self.xorosoft_api.get_inventory_status(xorosoft_product.item_number)
                    if inventory:
                        staging_product.mapping_details['inventory_status'] = {
                            'in_stock': inventory['in_stock'],
                            'total_inventory': inventory['total_inventory']
                        }
                
                return True, match_result
            else:
                # Product not found in Xorosoft
                staging_product.validation_status = 'invalid'
                staging_product.validation_errors = ['Product not found in Xorosoft inventory']
                return False, match_result
                
        except Exception as e:
            self.logger.error(f"API validation error for SKU {staging_product.sku}: {str(e)}")
            staging_product.validation_status = 'error'
            staging_product.validation_errors = [f'API error: {str(e)}']
            return False, None
    
    def _basic_validation(self, staging_product: EtilizeStagingProduct) -> bool:
        """Basic validation when API is not available."""
        errors = []
        
        # Required fields
        if not staging_product.sku:
            errors.append("SKU is required")
        if not staging_product.title:
            errors.append("Title is required")
        
        # Store validation results
        if errors:
            staging_product.validation_status = 'invalid'
            staging_product.validation_errors = errors
            return False
        else:
            staging_product.validation_status = 'valid'
            staging_product.validation_errors = None
            return True
    
    def process_staging_batch(self, batch_id: int, config: Optional[ImportConfiguration] = None) -> Dict[str, Any]:
        """Process a batch of staging products with API validation.
        
        Args:
            batch_id: ID of the import batch
            config: Optional import configuration
            
        Returns:
            Processing results dictionary
        """
        if not config:
            config = ImportConfiguration()
        
        # Get staging products
        staging_products = self.session.query(EtilizeStagingProduct).filter(
            EtilizeStagingProduct.batch_id == batch_id,
            EtilizeStagingProduct.processing_status == ProcessingStatus.PENDING.value
        ).all()
        
        results = {
            'total': len(staging_products),
            'validated': 0,
            'invalid': 0,
            'errors': 0,
            'api_matches': {
                'by_sku': 0,
                'by_cws_a': 0,
                'by_cws_catalog': 0,
                'by_sprc': 0
            }
        }
        
        # Process in batches for API efficiency
        batch_size = 50
        for i in range(0, len(staging_products), batch_size):
            batch = staging_products[i:i + batch_size]
            
            for product in batch:
                try:
                    # Update processing status
                    product.processing_status = ProcessingStatus.PROCESSING.value
                    
                    # Validate with API
                    is_valid, match_result = self.validate_with_api(product)
                    
                    if is_valid:
                        results['validated'] += 1
                        
                        # Track match types
                        if match_result and match_result.matched:
                            if match_result.match_type == MatchType.SKU:
                                results['api_matches']['by_sku'] += 1
                            elif match_result.match_type == MatchType.CWS_A:
                                results['api_matches']['by_cws_a'] += 1
                            elif match_result.match_type == MatchType.CWS_CATALOG:
                                results['api_matches']['by_cws_catalog'] += 1
                            elif match_result.match_type == MatchType.SPRC:
                                results['api_matches']['by_sprc'] += 1
                        
                        # Mark as validated
                        product.processing_status = ProcessingStatus.VALIDATED.value
                    else:
                        results['invalid'] += 1
                        product.processing_status = ProcessingStatus.FAILED.value
                    
                    product.processed_at = datetime.utcnow()
                    
                except Exception as e:
                    results['errors'] += 1
                    product.processing_status = ProcessingStatus.FAILED.value
                    product.error_message = str(e)
                    self.logger.error(f"Error processing product {product.sku}: {str(e)}")
            
            # Commit batch
            self.session.commit()
            
            # Report progress
            progress = ((i + len(batch)) / len(staging_products)) * 100
            self._update_progress(
                stage='validating',
                progress=progress,
                message=f'Validated {i + len(batch)} of {len(staging_products)} products'
            )
        
        # Log API cache statistics
        if self.api_available:
            cache_info = self.xorosoft_api.get_cache_info()
            self.logger.info(f"API Cache Stats: {cache_info}")
        
        return results
    
    def import_from_csv_with_api(
        self, 
        csv_file_path: str, 
        config: Optional[ImportConfiguration] = None
    ) -> ImportResult:
        """Import products from CSV with Xorosoft API validation.
        
        This method overrides the parent method to add API validation
        during the import process.
        
        Args:
            csv_file_path: Path to CSV file
            config: Optional import configuration
            
        Returns:
            ImportResult with details of the operation
        """
        # First, run the standard import to staging
        result = self.import_from_csv(csv_file_path, None, config)
        
        if result.success and self.api_available:
            # Now run API validation on the staged products
            self.logger.info(f"Running API validation for batch {result.batch_id}")
            
            validation_results = self.process_staging_batch(result.batch_id, config)
            
            # Update result with API validation info
            result.warnings.append(
                f"API validation complete: {validation_results['validated']} validated, "
                f"{validation_results['invalid']} invalid"
            )
            
            # Add match statistics
            api_matches = validation_results['api_matches']
            result.warnings.append(
                f"API matches: SKU={api_matches['by_sku']}, "
                f"CWS_A={api_matches['by_cws_a']}, "
                f"CWS_Catalog={api_matches['by_cws_catalog']}, "
                f"SPRC={api_matches['by_sprc']}"
            )
        
        return result