"""
Data Validation Module

Comprehensive data validation for product-collection relationships
with detailed error reporting and data cleansing capabilities.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
from collections import Counter
import json

class DataValidator:
    """
    Comprehensive data validator for product-collection relationships.
    """
    
    def __init__(self, strict_mode: bool = False, debug: bool = False):
        """
        Initialize validator.
        
        Args:
            strict_mode: Enable strict validation rules
            debug: Enable debug logging
        """
        self.strict_mode = strict_mode
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        # Validation patterns
        self.handle_pattern = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
        self.id_pattern = re.compile(r'^gid://shopify/\w+/\d+$')
        self.url_pattern = re.compile(r'^https?://[\w\.-]+/.*$')
        
        # Validation statistics
        self.validation_stats = {
            'total_records': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'warnings': 0,
            'errors_by_type': Counter(),
            'warnings_by_type': Counter()
        }
    
    def validate_product_collection_relationship(self, relationship: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single product-collection relationship record.
        
        Args:
            relationship: Relationship record to validate
            
        Returns:
            Validation result with errors and warnings
        """
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'cleaned_data': relationship.copy()
        }
        
        self.validation_stats['total_records'] += 1
        
        # Required field validation
        self._validate_required_fields(relationship, result)
        
        # Handle validation
        self._validate_handles(relationship, result)
        
        # Data type validation
        self._validate_data_types(relationship, result)
        
        # Content validation
        self._validate_content(relationship, result)
        
        # Cross-field validation
        self._validate_cross_fields(relationship, result)
        
        # Clean and normalize data
        self._clean_data(result)
        
        # Update statistics
        if result['is_valid']:
            self.validation_stats['valid_records'] += 1
        else:
            self.validation_stats['invalid_records'] += 1
        
        self.validation_stats['warnings'] += len(result['warnings'])
        
        for error in result['errors']:
            self.validation_stats['errors_by_type'][error['type']] += 1
        
        for warning in result['warnings']:
            self.validation_stats['warnings_by_type'][warning['type']] += 1
        
        return result
    
    def _validate_required_fields(self, relationship: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Validate required fields are present.
        
        Args:
            relationship: Relationship record
            result: Validation result to update
        """
        required_fields = ['product_handle']
        
        if self.strict_mode:
            required_fields.extend(['product_title', 'collection_handle', 'collection_title'])
        
        for field in required_fields:
            if not relationship.get(field):
                result['errors'].append({
                    'type': 'missing_required_field',
                    'field': field,
                    'message': f'Required field "{field}" is missing or empty'
                })
                result['is_valid'] = False
    
    def _validate_handles(self, relationship: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Validate handle formats.
        
        Args:
            relationship: Relationship record
            result: Validation result to update
        """
        handle_fields = ['product_handle', 'collection_handle']
        
        for field in handle_fields:
            handle = relationship.get(field, '')
            if handle:  # Only validate non-empty handles
                if not self._is_valid_handle(handle):
                    result['errors'].append({
                        'type': 'invalid_handle_format',
                        'field': field,
                        'value': handle,
                        'message': f'Handle "{handle}" does not match Shopify format requirements'
                    })
                    result['is_valid'] = False
                elif len(handle) > 255:
                    result['errors'].append({
                        'type': 'handle_too_long',
                        'field': field,
                        'value': handle,
                        'message': f'Handle exceeds maximum length of 255 characters'
                    })
                    result['is_valid'] = False
    
    def _validate_data_types(self, relationship: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Validate data types of fields.
        
        Args:
            relationship: Relationship record
            result: Validation result to update
        """
        string_fields = [
            'product_handle', 'product_title', 'collection_handle', 
            'collection_title', 'collection_type', 'collection_description'
        ]
        
        boolean_fields = ['is_synthetic']
        
        # Validate string fields
        for field in string_fields:
            value = relationship.get(field)
            if value is not None and not isinstance(value, str):
                result['warnings'].append({
                    'type': 'incorrect_data_type',
                    'field': field,
                    'expected': 'string',
                    'actual': type(value).__name__,
                    'message': f'Field "{field}" should be a string'
                })
        
        # Validate boolean fields
        for field in boolean_fields:
            value = relationship.get(field)
            if value is not None and not isinstance(value, bool):
                result['warnings'].append({
                    'type': 'incorrect_data_type',
                    'field': field,
                    'expected': 'boolean',
                    'actual': type(value).__name__,
                    'message': f'Field "{field}" should be a boolean'
                })
    
    def _validate_content(self, relationship: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Validate content of fields.
        
        Args:
            relationship: Relationship record
            result: Validation result to update
        """
        # Validate collection type
        collection_type = relationship.get('collection_type', '')
        if collection_type and collection_type not in ['MANUAL', 'SMART', '']:
            result['warnings'].append({
                'type': 'invalid_collection_type',
                'field': 'collection_type',
                'value': collection_type,
                'message': f'Collection type "{collection_type}" is not standard (MANUAL/SMART)'
            })
        
        # Validate titles for suspicious content
        for field in ['product_title', 'collection_title']:
            title = relationship.get(field, '')
            if title:
                # Check for HTML tags
                if re.search(r'<[^>]+>', title):
                    result['warnings'].append({
                        'type': 'html_in_title',
                        'field': field,
                        'message': f'Title contains HTML tags: "{title[:50]}..."'
                    })
                
                # Check for excessive length
                if len(title) > 255:
                    result['warnings'].append({
                        'type': 'title_too_long',
                        'field': field,
                        'message': f'Title exceeds recommended length of 255 characters'
                    })
        
        # Validate description
        description = relationship.get('collection_description', '')
        if description and len(description) > 5000:
            result['warnings'].append({
                'type': 'description_too_long',
                'field': 'collection_description',
                'message': 'Description exceeds recommended length of 5000 characters'
            })
    
    def _validate_cross_fields(self, relationship: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Validate relationships between fields.
        
        Args:
            relationship: Relationship record
            result: Validation result to update
        """
        # If collection handle is present, collection title should be too
        collection_handle = relationship.get('collection_handle', '')
        collection_title = relationship.get('collection_title', '')
        
        if collection_handle and not collection_title:
            result['warnings'].append({
                'type': 'missing_collection_title',
                'message': 'Collection handle present but title is missing'
            })
        
        if collection_title and not collection_handle:
            result['warnings'].append({
                'type': 'missing_collection_handle',
                'message': 'Collection title present but handle is missing'
            })
        
        # Check if synthetic flag matches content
        is_synthetic = relationship.get('is_synthetic', False)
        source = relationship.get('source', '')
        
        if is_synthetic and source == 'api':
            result['warnings'].append({
                'type': 'inconsistent_synthetic_flag',
                'message': 'Record marked as synthetic but source is API'
            })
    
    def _clean_data(self, result: Dict[str, Any]) -> None:
        """
        Clean and normalize data in the result.
        
        Args:
            result: Validation result to update
        """
        cleaned = result['cleaned_data']
        
        # Trim whitespace from string fields
        string_fields = [
            'product_handle', 'product_title', 'collection_handle',
            'collection_title', 'collection_type', 'collection_description', 'source'
        ]
        
        for field in string_fields:
            if field in cleaned and isinstance(cleaned[field], str):
                cleaned[field] = cleaned[field].strip()
        
        # Normalize collection type
        if 'collection_type' in cleaned and cleaned['collection_type']:
            cleaned['collection_type'] = cleaned['collection_type'].upper()
        
        # Convert string booleans to actual booleans
        if 'is_synthetic' in cleaned and isinstance(cleaned['is_synthetic'], str):
            cleaned['is_synthetic'] = cleaned['is_synthetic'].lower() in ['true', '1', 'yes']
        
        # Clean HTML from descriptions
        if 'collection_description' in cleaned and cleaned['collection_description']:
            cleaned['collection_description'] = self._clean_html(cleaned['collection_description'])
    
    def _is_valid_handle(self, handle: str) -> bool:
        """
        Check if a handle is valid according to Shopify rules.
        
        Args:
            handle: Handle to validate
            
        Returns:
            True if valid, False otherwise
        """
        return bool(self.handle_pattern.match(handle))
    
    def _clean_html(self, text: str) -> str:
        """
        Remove HTML tags from text.
        
        Args:
            text: Text to clean
            
        Returns:
            Clean text
        """
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # Decode HTML entities
        html_entities = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&nbsp;': ' '
        }
        
        for entity, replacement in html_entities.items():
            clean_text = clean_text.replace(entity, replacement)
        
        return clean_text
    
    def validate_batch(self, relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate a batch of relationships.
        
        Args:
            relationships: List of relationship records
            
        Returns:
            Batch validation results
        """
        self.logger.info(f"Validating batch of {len(relationships)} relationships")
        
        valid_records = []
        invalid_records = []
        all_warnings = []
        all_errors = []
        
        for i, relationship in enumerate(relationships):
            try:
                result = self.validate_product_collection_relationship(relationship)
                
                if result['is_valid']:
                    valid_records.append(result['cleaned_data'])
                else:
                    invalid_records.append({
                        'original_data': relationship,
                        'errors': result['errors'],
                        'warnings': result['warnings']
                    })
                
                all_warnings.extend(result['warnings'])
                all_errors.extend(result['errors'])
                
            except Exception as e:
                self.logger.error(f"Error validating record {i}: {e}")
                invalid_records.append({
                    'original_data': relationship,
                    'errors': [{
                        'type': 'validation_exception',
                        'message': str(e)
                    }],
                    'warnings': []
                })
        
        batch_result = {
            'summary': {
                'total_records': len(relationships),
                'valid_records': len(valid_records),
                'invalid_records': len(invalid_records),
                'total_warnings': len(all_warnings),
                'total_errors': len(all_errors),
                'validation_rate': len(valid_records) / len(relationships) * 100 if relationships else 0
            },
            'valid_data': valid_records,
            'invalid_data': invalid_records,
            'statistics': self.get_validation_statistics(),
            'error_summary': dict(Counter(error['type'] for error in all_errors)),
            'warning_summary': dict(Counter(warning['type'] for warning in all_warnings))
        }
        
        self.logger.info(f"Validation complete: {batch_result['summary']['validation_rate']:.1f}% success rate")
        
        return batch_result
    
    def generate_validation_report(self, validation_results: Dict[str, Any], 
                                 output_path: str) -> bool:
        """
        Generate a detailed validation report.
        
        Args:
            validation_results: Results from validate_batch
            output_path: Path for output report
            
        Returns:
            True if successful, False otherwise
        """
        try:
            report = {
                'validation_report': {
                    'generated_at': datetime.now().isoformat(),
                    'summary': validation_results['summary'],
                    'error_analysis': {
                        'most_common_errors': validation_results['error_summary'],
                        'error_details': []
                    },
                    'warning_analysis': {
                        'most_common_warnings': validation_results['warning_summary'],
                        'warning_details': []
                    },
                    'recommendations': self._generate_recommendations(validation_results)
                }
            }
            
            # Add detailed error information
            for invalid_record in validation_results['invalid_data'][:10]:  # Limit to first 10
                report['validation_report']['error_analysis']['error_details'].append({
                    'sample_data': invalid_record['original_data'],
                    'errors': invalid_record['errors']
                })
            
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            self.logger.info(f"Validation report saved to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error generating validation report: {e}")
            return False
    
    def _generate_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """
        Generate recommendations based on validation results.
        
        Args:
            validation_results: Validation results
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        error_summary = validation_results['error_summary']
        warning_summary = validation_results['warning_summary']
        summary = validation_results['summary']
        
        if summary['validation_rate'] < 90:
            recommendations.append(
                "Low validation rate detected. Review data quality and consider data cleansing."
            )
        
        if 'missing_required_field' in error_summary:
            recommendations.append(
                "Missing required fields detected. Ensure all product handles are provided."
            )
        
        if 'invalid_handle_format' in error_summary:
            recommendations.append(
                "Invalid handle formats detected. Implement handle normalization in data preparation."
            )
        
        if 'html_in_title' in warning_summary:
            recommendations.append(
                "HTML content found in titles. Consider implementing HTML cleaning in data pipeline."
            )
        
        if 'title_too_long' in warning_summary:
            recommendations.append(
                "Long titles detected. Consider truncating or summarizing lengthy titles."
            )
        
        return recommendations
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """
        Get current validation statistics.
        
        Returns:
            Dictionary of validation statistics
        """
        return {
            **self.validation_stats,
            'validation_rate': (self.validation_stats['valid_records'] / 
                              self.validation_stats['total_records'] * 100) 
                              if self.validation_stats['total_records'] > 0 else 0,
            'last_updated': datetime.now().isoformat()
        }
    
    def reset_statistics(self) -> None:
        """
        Reset validation statistics.
        """
        self.validation_stats = {
            'total_records': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'warnings': 0,
            'errors_by_type': Counter(),
            'warnings_by_type': Counter()
        }
        self.logger.info("Validation statistics reset")


class DataCleaner:
    """
    Data cleaning utilities for product-collection relationships.
    """
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if debug:
            self.logger.setLevel(logging.DEBUG)
    
    def clean_relationships(self, relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean and normalize relationship data.
        
        Args:
            relationships: List of relationship records
            
        Returns:
            Cleaned relationship records
        """
        cleaned = []
        
        for relationship in relationships:
            try:
                cleaned_relationship = self._clean_single_relationship(relationship)
                if cleaned_relationship:
                    cleaned.append(cleaned_relationship)
            except Exception as e:
                self.logger.error(f"Error cleaning relationship: {e}")
                continue
        
        self.logger.info(f"Cleaned {len(cleaned)} out of {len(relationships)} relationships")
        return cleaned
    
    def _clean_single_relationship(self, relationship: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Clean a single relationship record.
        
        Args:
            relationship: Relationship record to clean
            
        Returns:
            Cleaned relationship record or None if invalid
        """
        cleaned = {}
        
        # Clean handles
        for handle_field in ['product_handle', 'collection_handle']:
            handle = relationship.get(handle_field, '')
            if handle:
                cleaned_handle = self._clean_handle(handle)
                if cleaned_handle:
                    cleaned[handle_field] = cleaned_handle
                else:
                    # If product handle is invalid, skip the record
                    if handle_field == 'product_handle':
                        return None
            else:
                cleaned[handle_field] = ''
        
        # Clean text fields
        text_fields = ['product_title', 'collection_title', 'collection_description']
        for field in text_fields:
            text = relationship.get(field, '')
            cleaned[field] = self._clean_text(text)
        
        # Normalize collection type
        collection_type = relationship.get('collection_type', '')
        cleaned['collection_type'] = self._normalize_collection_type(collection_type)
        
        # Handle boolean fields
        is_synthetic = relationship.get('is_synthetic', False)
        if isinstance(is_synthetic, str):
            cleaned['is_synthetic'] = is_synthetic.lower() in ['true', '1', 'yes']
        else:
            cleaned['is_synthetic'] = bool(is_synthetic)
        
        # Clean source field
        source = relationship.get('source', '')
        cleaned['source'] = source.strip() if source else 'unknown'
        
        return cleaned
    
    def _clean_handle(self, handle: str) -> Optional[str]:
        """
        Clean and normalize a handle.
        
        Args:
            handle: Handle to clean
            
        Returns:
            Cleaned handle or None if invalid
        """
        if not handle or not isinstance(handle, str):
            return None
        
        # Convert to lowercase and replace invalid characters
        cleaned = re.sub(r'[^a-zA-Z0-9\s-]', '', handle.lower())
        cleaned = re.sub(r'[\s-]+', '-', cleaned)
        cleaned = cleaned.strip('-')
        
        # Validate final result
        if cleaned and re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', cleaned) and len(cleaned) <= 255:
            return cleaned
        
        return None
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text content.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        if not text or not isinstance(text, str):
            return ''
        
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', text)
        
        # Decode HTML entities
        html_entities = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&nbsp;': ' '
        }
        
        for entity, replacement in html_entities.items():
            clean_text = clean_text.replace(entity, replacement)
        
        # Normalize whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text
    
    def _normalize_collection_type(self, collection_type: str) -> str:
        """
        Normalize collection type.
        
        Args:
            collection_type: Collection type to normalize
            
        Returns:
            Normalized collection type
        """
        if not collection_type or not isinstance(collection_type, str):
            return 'MANUAL'
        
        normalized = collection_type.upper().strip()
        
        if normalized in ['MANUAL', 'SMART']:
            return normalized
        
        # Default to MANUAL for unknown types
        return 'MANUAL'