"""
Data Transformation Service

Handles transformations from Etilize CSV to Product model with metafield extraction,
normalization, category mapping, and image processing.
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
import urllib.parse

from models import Product, Category, ProductStatus, ProductMetafield
from .mapping_service import MatchResult


@dataclass
class TransformationRule:
    """Rule for transforming a field from source to target format."""
    source_field: str
    target_field: str
    transformation_type: str  # direct, lookup, computed, metafield
    transformation_config: Dict[str, Any] = field(default_factory=dict)
    is_required: bool = False
    default_value: Any = None


@dataclass
class MetafieldDefinition:
    """Definition for extracting metafields."""
    namespace: str
    key: str
    source_field: str
    value_type: str = 'string'  # string, integer, float, boolean, json, date
    is_list: bool = False
    list_separator: str = ','


@dataclass
class TransformationResult:
    """Result of a data transformation operation."""
    success: bool
    product_data: Dict[str, Any] = field(default_factory=dict)
    metafields: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataTransformationService:
    """
    Service for transforming Etilize CSV data to Product model format.
    
    Features:
    - Field mapping and transformation
    - Metafield extraction and normalization
    - Category mapping and classification
    - Image URL processing and validation
    - Data type conversion and validation
    - Custom transformation rules
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the transformation service."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Load transformation rules
        self.transformation_rules = self._load_transformation_rules()
        self.metafield_definitions = self._load_metafield_definitions()
        self.category_mappings = self._load_category_mappings()
        
        # Transformation cache
        self._transformation_cache: Dict[str, Any] = {}
    
    def transform_to_product(
        self,
        source_data: Dict[str, Any],
        mapping_result: Optional[MatchResult] = None
    ) -> TransformationResult:
        """
        Transform source data to Product model format.
        
        Args:
            source_data: Raw data from CSV
            mapping_result: Result from product mapping service
            
        Returns:
            TransformationResult with product data and metafields
        """
        try:
            result = TransformationResult(success=True)
            
            # Apply field transformations
            product_data = self._apply_field_transformations(source_data)
            
            # Extract metafields
            metafields = self._extract_metafields(source_data)
            
            # Process images
            image_data = self._process_images(source_data)
            product_data.update(image_data)
            
            # Map category
            category_data = self._map_category(source_data)
            product_data.update(category_data)
            
            # Apply mapping result data
            if mapping_result and mapping_result.reference_record:
                reference_data = self._apply_reference_data(product_data, mapping_result.reference_record)
                product_data.update(reference_data)
            
            # Validate and clean data
            cleaned_data = self._validate_and_clean_data(product_data)
            
            result.product_data = cleaned_data
            result.metafields = metafields
            result.metadata = {
                'transformation_timestamp': datetime.now().isoformat(),
                'source_fields': list(source_data.keys()),
                'mapping_used': mapping_result.match_type.value if mapping_result else None
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Transformation failed: {str(e)}")
            return TransformationResult(
                success=False,
                errors=[f"Transformation error: {str(e)}"]
            )
    
    def transform_batch(
        self,
        source_data_list: List[Dict[str, Any]],
        mapping_results: Optional[List[MatchResult]] = None
    ) -> List[TransformationResult]:
        """
        Transform a batch of source data records.
        
        Args:
            source_data_list: List of raw data from CSV
            mapping_results: List of mapping results (optional)
            
        Returns:
            List of TransformationResult objects
        """
        results = []
        
        for i, source_data in enumerate(source_data_list):
            mapping_result = mapping_results[i] if mapping_results and i < len(mapping_results) else None
            
            result = self.transform_to_product(source_data, mapping_result)
            results.append(result)
        
        return results
    
    def _apply_field_transformations(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply field transformation rules."""
        product_data = {}
        
        for rule in self.transformation_rules:
            try:
                value = self._apply_transformation_rule(source_data, rule)
                if value is not None:
                    product_data[rule.target_field] = value
                elif rule.is_required:
                    product_data[rule.target_field] = rule.default_value
                    
            except Exception as e:
                self.logger.warning(f"Failed to apply transformation rule for {rule.target_field}: {str(e)}")
                if rule.is_required and rule.default_value is not None:
                    product_data[rule.target_field] = rule.default_value
        
        return product_data
    
    def _apply_transformation_rule(
        self,
        source_data: Dict[str, Any],
        rule: TransformationRule
    ) -> Any:
        """Apply a single transformation rule."""
        source_value = source_data.get(rule.source_field)
        
        if source_value is None or (isinstance(source_value, str) and source_value.strip() == ''):
            return rule.default_value
        
        if rule.transformation_type == 'direct':
            return self._transform_direct(source_value, rule.transformation_config)
        
        elif rule.transformation_type == 'lookup':
            return self._transform_lookup(source_value, rule.transformation_config)
        
        elif rule.transformation_type == 'computed':
            return self._transform_computed(source_data, rule.transformation_config)
        
        elif rule.transformation_type == 'format':
            return self._transform_format(source_value, rule.transformation_config)
        
        elif rule.transformation_type == 'normalize':
            return self._transform_normalize(source_value, rule.transformation_config)
        
        else:
            return source_value
    
    def _transform_direct(self, value: Any, config: Dict[str, Any]) -> Any:
        """Direct value transformation with type conversion."""
        target_type = config.get('type', 'string')
        
        if target_type == 'string':
            return str(value).strip()
        
        elif target_type == 'float':
            try:
                # Handle currency formats
                if isinstance(value, str):
                    # Remove currency symbols and spaces
                    cleaned = re.sub(r'[^\d.-]', '', value)
                    return float(cleaned) if cleaned else 0.0
                return float(value)
            except (ValueError, TypeError):
                return config.get('default', 0.0)
        
        elif target_type == 'integer':
            try:
                if isinstance(value, str):
                    cleaned = re.sub(r'[^\d-]', '', value)
                    return int(cleaned) if cleaned else 0
                return int(float(value))
            except (ValueError, TypeError):
                return config.get('default', 0)
        
        elif target_type == 'boolean':
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on', 'active')
            return bool(value)
        
        elif target_type == 'decimal':
            try:
                if isinstance(value, str):
                    cleaned = re.sub(r'[^\d.-]', '', value)
                    return Decimal(cleaned) if cleaned else Decimal('0.00')
                return Decimal(str(value))
            except (InvalidOperation, ValueError):
                return Decimal(config.get('default', '0.00'))
        
        return value
    
    def _transform_lookup(self, value: Any, config: Dict[str, Any]) -> Any:
        """Transform using lookup table."""
        lookup_table = config.get('lookup_table', {})
        default_value = config.get('default')
        
        # Normalize key for lookup
        key = str(value).strip().lower()
        
        # Try exact match first
        if key in lookup_table:
            return lookup_table[key]
        
        # Try case-insensitive match
        for lookup_key, lookup_value in lookup_table.items():
            if lookup_key.lower() == key:
                return lookup_value
        
        return default_value
    
    def _transform_computed(self, source_data: Dict[str, Any], config: Dict[str, Any]) -> Any:
        """Compute value from multiple source fields."""
        computation_type = config.get('type')
        source_fields = config.get('fields', [])
        
        if computation_type == 'concatenate':
            separator = config.get('separator', ' ')
            values = []
            for field in source_fields:
                value = source_data.get(field)
                if value and str(value).strip():
                    values.append(str(value).strip())
            return separator.join(values)
        
        elif computation_type == 'first_non_empty':
            for field in source_fields:
                value = source_data.get(field)
                if value and str(value).strip():
                    return str(value).strip()
            return config.get('default')
        
        elif computation_type == 'arithmetic':
            operation = config.get('operation')
            values = []
            for field in source_fields:
                try:
                    value = float(source_data.get(field, 0))
                    values.append(value)
                except (ValueError, TypeError):
                    values.append(0.0)
            
            if operation == 'sum':
                return sum(values)
            elif operation == 'average':
                return sum(values) / len(values) if values else 0.0
            elif operation == 'multiply':
                result = 1.0
                for value in values:
                    result *= value
                return result
        
        return config.get('default')
    
    def _transform_format(self, value: Any, config: Dict[str, Any]) -> Any:
        """Format value using pattern."""
        format_type = config.get('type')
        
        if format_type == 'regex_replace':
            pattern = config.get('pattern')
            replacement = config.get('replacement', '')
            return re.sub(pattern, replacement, str(value))
        
        elif format_type == 'uppercase':
            return str(value).upper()
        
        elif format_type == 'lowercase':
            return str(value).lower()
        
        elif format_type == 'title_case':
            return str(value).title()
        
        elif format_type == 'slug':
            # Create URL-friendly slug
            value = str(value).lower()
            value = re.sub(r'[^\w\s-]', '', value)
            value = re.sub(r'[-\s]+', '-', value)
            return value.strip('-')
        
        return value
    
    def _transform_normalize(self, value: Any, config: Dict[str, Any]) -> Any:
        """Normalize value for consistency."""
        normalization_type = config.get('type')
        
        if normalization_type == 'whitespace':
            # Normalize whitespace
            return ' '.join(str(value).split())
        
        elif normalization_type == 'phone':
            # Normalize phone number
            digits = re.sub(r'[^\d]', '', str(value))
            if len(digits) == 10:
                return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            elif len(digits) == 11 and digits[0] == '1':
                return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
            return value
        
        elif normalization_type == 'url':
            # Normalize URL
            url = str(value).strip()
            if url and not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            return url
        
        return value
    
    def _extract_metafields(self, source_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract metafields from source data."""
        metafields = []
        
        for definition in self.metafield_definitions:
            try:
                source_value = source_data.get(definition.source_field)
                
                if source_value is None or (isinstance(source_value, str) and source_value.strip() == ''):
                    continue
                
                # Process value based on type and list format
                if definition.is_list:
                    values = self._parse_list_value(source_value, definition.list_separator)
                    processed_values = []
                    for value in values:
                        processed_value = self._convert_metafield_value(value, definition.value_type)
                        if processed_value is not None:
                            processed_values.append(processed_value)
                    
                    if processed_values:
                        metafield_value = json.dumps(processed_values)
                    else:
                        continue
                else:
                    processed_value = self._convert_metafield_value(source_value, definition.value_type)
                    if processed_value is None:
                        continue
                    metafield_value = processed_value
                
                metafield = {
                    'namespace': definition.namespace,
                    'key': definition.key,
                    'value': metafield_value,
                    'value_type': definition.value_type
                }
                
                metafields.append(metafield)
                
            except Exception as e:
                self.logger.warning(f"Failed to extract metafield {definition.namespace}.{definition.key}: {str(e)}")
        
        return metafields
    
    def _parse_list_value(self, value: Any, separator: str) -> List[str]:
        """Parse list value from string."""
        if not value:
            return []
        
        value_str = str(value).strip()
        
        # Handle different list formats
        if value_str.startswith('[') and value_str.endswith(']'):
            # JSON-style list
            try:
                return json.loads(value_str)
            except json.JSONDecodeError:
                # Fall back to manual parsing
                value_str = value_str[1:-1]
        
        # Split by separator and clean values
        values = []
        for item in value_str.split(separator):
            cleaned = item.strip().strip('"\'')
            if cleaned:
                values.append(cleaned)
        
        return values
    
    def _convert_metafield_value(self, value: Any, value_type: str) -> Any:
        """Convert value to specified metafield type."""
        if value is None:
            return None
        
        try:
            if value_type == 'string':
                return str(value).strip()
            
            elif value_type == 'integer':
                if isinstance(value, str):
                    cleaned = re.sub(r'[^\d-]', '', value)
                    return int(cleaned) if cleaned else None
                return int(float(value))
            
            elif value_type == 'float':
                if isinstance(value, str):
                    cleaned = re.sub(r'[^\d.-]', '', value)
                    return float(cleaned) if cleaned else None
                return float(value)
            
            elif value_type == 'boolean':
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on', 'active')
                return bool(value)
            
            elif value_type == 'json':
                if isinstance(value, str):
                    return json.loads(value)
                return value
            
            elif value_type == 'date':
                # Handle various date formats
                date_str = str(value).strip()
                # Add date parsing logic here
                return date_str
            
            else:
                return str(value)
                
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            self.logger.warning(f"Failed to convert metafield value '{value}' to type '{value_type}': {str(e)}")
            return None
    
    def _process_images(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process image URLs and additional images."""
        image_data = {}
        
        # Process featured image
        featured_image = source_data.get('Image Src')
        if featured_image and self._is_valid_image_url(featured_image):
            image_data['featured_image_url'] = featured_image
        
        # Process additional images
        additional_images = []
        image_fields = [
            'Image Alt Text',  # Sometimes contains additional image URLs
            'Metafield: custom.additional_images[list.single_line_text]'
        ]
        
        for field in image_fields:
            value = source_data.get(field)
            if value:
                # Extract URLs from various formats
                urls = self._extract_image_urls(value)
                for url in urls:
                    if self._is_valid_image_url(url) and url not in additional_images:
                        additional_images.append(url)
        
        if additional_images:
            image_data['additional_images'] = additional_images
        
        return image_data
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Validate image URL."""
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        
        # Check if it's a valid URL format
        try:
            parsed = urllib.parse.urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                return False
        except Exception:
            return False
        
        # Check file extension
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        url_lower = url.lower()
        
        return any(url_lower.endswith(ext) for ext in image_extensions)
    
    def _extract_image_urls(self, text: str) -> List[str]:
        """Extract image URLs from text."""
        urls = []
        
        # URL pattern
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+\.(jpg|jpeg|png|gif|webp|bmp)'
        
        matches = re.findall(url_pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                url = match[0]
            else:
                url = match
            urls.append(url)
        
        return urls
    
    def _map_category(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map product to category."""
        category_data = {}
        
        # Try direct category mapping
        product_type = source_data.get('Type')
        vendor = source_data.get('Vendor')
        
        category_id = self._find_category_mapping(product_type, vendor)
        
        if category_id:
            category_data['category_id'] = category_id
        else:
            # Use default category or create mapping
            default_category = self._get_default_category(product_type, vendor)
            if default_category:
                category_data['category_id'] = default_category
        
        return category_data
    
    def _find_category_mapping(self, product_type: str, vendor: str) -> Optional[int]:
        """Find category mapping for product type and vendor."""
        if not product_type:
            return None
        
        # Normalize for lookup
        product_type_key = product_type.lower().strip()
        vendor_key = vendor.lower().strip() if vendor else ''
        
        # Check exact mapping first
        mapping_key = f"{vendor_key}:{product_type_key}"
        if mapping_key in self.category_mappings:
            return self.category_mappings[mapping_key]
        
        # Check product type only
        if product_type_key in self.category_mappings:
            return self.category_mappings[product_type_key]
        
        # Check partial matches
        for key, category_id in self.category_mappings.items():
            if product_type_key in key or key in product_type_key:
                return category_id
        
        return None
    
    def _get_default_category(self, product_type: str, vendor: str) -> Optional[int]:
        """Get default category for unmapped products."""
        # Return a default category ID or None
        # This would typically be configured
        return 1  # Assuming category ID 1 is "Uncategorized" or default
    
    def _apply_reference_data(
        self,
        product_data: Dict[str, Any],
        reference_record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply data from reference record."""
        reference_data = {}
        
        # Map reference fields to product fields
        reference_mappings = {
            'BasePartNumber': 'manufacturer_part_number',
            'ManufacturerName': 'manufacturer',
            'BrandName': 'brand',
            'ProductDescription': 'description',
            'ListPrice': 'compare_at_price',
            'Weight': 'weight',
            'UPC': 'upc'
        }
        
        for ref_field, product_field in reference_mappings.items():
            ref_value = reference_record.get(ref_field)
            if ref_value and (product_field not in product_data or not product_data[product_field]):
                # Apply transformation based on field type
                if product_field in ['compare_at_price', 'weight']:
                    try:
                        reference_data[product_field] = float(ref_value)
                    except (ValueError, TypeError):
                        pass
                else:
                    reference_data[product_field] = str(ref_value).strip()
        
        return reference_data
    
    def _validate_and_clean_data(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean product data."""
        cleaned_data = {}
        
        for field, value in product_data.items():
            try:
                # Clean based on field type
                if field in ['price', 'compare_at_price', 'cost_price', 'weight']:
                    # Numeric fields
                    if value is not None:
                        cleaned_value = float(value)
                        if cleaned_value >= 0:
                            cleaned_data[field] = cleaned_value
                
                elif field in ['inventory_quantity']:
                    # Integer fields
                    if value is not None:
                        cleaned_value = int(float(value))
                        if cleaned_value >= 0:
                            cleaned_data[field] = cleaned_value
                
                elif field in ['track_inventory', 'continue_selling_when_out_of_stock', 'is_active']:
                    # Boolean fields
                    if value is not None:
                        cleaned_data[field] = bool(value)
                
                elif field in ['sku', 'name', 'description', 'brand', 'manufacturer']:
                    # String fields
                    if value is not None:
                        cleaned_value = str(value).strip()
                        if cleaned_value:
                            cleaned_data[field] = cleaned_value
                
                else:
                    # Other fields
                    if value is not None:
                        cleaned_data[field] = value
                        
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Failed to clean field '{field}' with value '{value}': {str(e)}")
        
        # Ensure required fields have defaults
        defaults = {
            'status': ProductStatus.DRAFT.value,
            'is_active': True,
            'track_inventory': True,
            'continue_selling_when_out_of_stock': False,
            'inventory_quantity': 0,
            'weight_unit': 'kg',
            'dimension_unit': 'cm'
        }
        
        for field, default_value in defaults.items():
            if field not in cleaned_data:
                cleaned_data[field] = default_value
        
        return cleaned_data
    
    def _load_transformation_rules(self) -> List[TransformationRule]:
        """Load transformation rules for field mapping."""
        return [
            # Basic product information
            TransformationRule(
                source_field='SKU',
                target_field='sku',
                transformation_type='format',
                transformation_config={'type': 'uppercase'},
                is_required=True
            ),
            TransformationRule(
                source_field='Title',
                target_field='name',
                transformation_type='normalize',
                transformation_config={'type': 'whitespace'},
                is_required=True
            ),
            TransformationRule(
                source_field='Body (HTML)',
                target_field='description',
                transformation_type='direct',
                transformation_config={'type': 'string'}
            ),
            
            # Pricing
            TransformationRule(
                source_field='Variant Price',
                target_field='price',
                transformation_type='direct',
                transformation_config={'type': 'float', 'default': 0.0},
                is_required=True
            ),
            TransformationRule(
                source_field='Variant Compare At Price',
                target_field='compare_at_price',
                transformation_type='direct',
                transformation_config={'type': 'float'}
            ),
            
            # Product attributes
            TransformationRule(
                source_field='Vendor',
                target_field='brand',
                transformation_type='direct',
                transformation_config={'type': 'string'}
            ),
            TransformationRule(
                source_field='Type',
                target_field='product_type',
                transformation_type='direct',
                transformation_config={'type': 'string'}
            ),
            TransformationRule(
                source_field='Variant Grams',
                target_field='weight',
                transformation_type='direct',
                transformation_config={'type': 'float'}
            ),
            
            # Inventory
            TransformationRule(
                source_field='Variant Inventory Qty',
                target_field='inventory_quantity',
                transformation_type='direct',
                transformation_config={'type': 'integer', 'default': 0}
            ),
            TransformationRule(
                source_field='Variant Inventory Tracker',
                target_field='track_inventory',
                transformation_type='direct',
                transformation_config={'type': 'boolean'}
            ),
            
            # SEO
            TransformationRule(
                source_field='SEO Title',
                target_field='seo_title',
                transformation_type='direct',
                transformation_config={'type': 'string'}
            ),
            TransformationRule(
                source_field='SEO Description',
                target_field='seo_description',
                transformation_type='direct',
                transformation_config={'type': 'string'}
            ),
            
            # Handle/URL
            TransformationRule(
                source_field='Handle',
                target_field='shopify_handle',
                transformation_type='format',
                transformation_config={'type': 'slug'}
            ),
            
            # Status
            TransformationRule(
                source_field='Status',
                target_field='status',
                transformation_type='lookup',
                transformation_config={
                    'lookup_table': {
                        'active': ProductStatus.ACTIVE.value,
                        'draft': ProductStatus.DRAFT.value,
                        'archived': ProductStatus.ARCHIVED.value
                    },
                    'default': ProductStatus.DRAFT.value
                }
            )
        ]
    
    def _load_metafield_definitions(self) -> List[MetafieldDefinition]:
        """Load metafield extraction definitions."""
        return [
            MetafieldDefinition(
                namespace='custom',
                key='cws_a',
                source_field='Metafield: custom.CWS_A[list.single_line_text]',
                value_type='string',
                is_list=True
            ),
            MetafieldDefinition(
                namespace='custom',
                key='cws_catalog',
                source_field='Metafield: custom.CWS_Catalog[list.single_line_text]',
                value_type='string',
                is_list=True
            ),
            MetafieldDefinition(
                namespace='custom',
                key='sprc',
                source_field='Metafield: custom.SPRC[list.single_line_text]',
                value_type='string',
                is_list=True
            ),
            MetafieldDefinition(
                namespace='product',
                key='dimensions',
                source_field='Variant Weight',
                value_type='json'
            ),
            MetafieldDefinition(
                namespace='product',
                key='additional_images',
                source_field='Image Alt Text',
                value_type='string',
                is_list=True
            )
        ]
    
    def _load_category_mappings(self) -> Dict[str, int]:
        """Load category mappings."""
        # This would typically be loaded from database or configuration file
        return {
            'office supplies': 1,
            'art supplies': 2,
            'school supplies': 3,
            'stationery': 1,
            'paper': 1,
            'pens': 1,
            'pencils': 1,
            'markers': 2,
            'paints': 2,
            'brushes': 2,
            'canvas': 2,
            'notebooks': 3,
            'binders': 3
        }