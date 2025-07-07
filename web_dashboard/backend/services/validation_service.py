"""
Data Validation Service

Provides comprehensive data validation for import operations including
business rules, data integrity checks, and quality scoring.
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import urllib.parse


class ValidationSeverity(Enum):
    """Validation message severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationMessage:
    """A validation message."""
    severity: ValidationSeverity
    field: str
    message: str
    code: str
    value: Any = None
    expected: Any = None
    row_number: Optional[int] = None


@dataclass
class ValidationResult:
    """Result of validation operation."""
    is_valid: bool
    messages: List[ValidationMessage] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    info: List[Dict[str, Any]] = field(default_factory=list)
    quality_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_critical_errors(self) -> bool:
        """Check if there are critical errors."""
        return any(msg.severity == ValidationSeverity.CRITICAL for msg in self.messages)
    
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return any(msg.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] for msg in self.messages)
    
    def get_error_count(self) -> int:
        """Get count of error messages."""
        return len([msg for msg in self.messages if msg.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]])
    
    def get_warning_count(self) -> int:
        """Get count of warning messages."""
        return len([msg for msg in self.messages if msg.severity == ValidationSeverity.WARNING])


class DataValidationService:
    """
    Service for validating import data quality and business rules.
    
    Features:
    - Comprehensive field validation
    - Business rule validation
    - Data integrity checks
    - Reference data validation
    - Quality scoring and recommendations
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the validation service."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Validation patterns
        self.validation_patterns = self._load_validation_patterns()
        self.business_rules = self._load_business_rules()
    
    def validate_import_data(
        self,
        data: List[Dict[str, Any]],
        reference_data: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate import data comprehensively.
        
        Args:
            data: List of data records to validate
            reference_data: Reference data for validation (optional)
            
        Returns:
            ValidationResult with detailed validation information
        """
        try:
            result = ValidationResult(is_valid=True)
            total_quality_score = 0.0
            
            for i, record in enumerate(data):
                # Validate individual record
                record_result = self.validate_record(record, reference_data, i + 1)
                
                # Merge messages
                result.messages.extend(record_result.messages)
                total_quality_score += record_result.quality_score
                
                # Check if record has critical errors
                if record_result.has_critical_errors():
                    result.is_valid = False
            
            # Calculate overall quality score
            result.quality_score = total_quality_score / len(data) if data else 0.0
            
            # Categorize messages
            self._categorize_messages(result)
            
            # Validate batch-level rules
            batch_validation = self._validate_batch_rules(data)
            result.messages.extend(batch_validation.messages)
            
            # Final validation status
            result.is_valid = not result.has_critical_errors()
            
            # Add metadata
            result.metadata = {
                'total_records': len(data),
                'error_records': len([r for r in data if self._record_has_errors(r, result.messages)]),
                'validation_timestamp': datetime.now().isoformat(),
                'reference_data_used': reference_data is not None
            }
            
            self.logger.info(f"Validation completed: {len(data)} records, "
                           f"Quality score: {result.quality_score:.2f}, "
                           f"Errors: {result.get_error_count()}, "
                           f"Warnings: {result.get_warning_count()}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            return ValidationResult(
                is_valid=False,
                messages=[ValidationMessage(
                    severity=ValidationSeverity.CRITICAL,
                    field="validation",
                    message=f"Validation process failed: {str(e)}",
                    code="VALIDATION_ERROR"
                )]
            )
    
    def validate_record(
        self,
        record: Dict[str, Any],
        reference_data: Optional[Dict[str, Any]] = None,
        row_number: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate a single record.
        
        Args:
            record: Data record to validate
            reference_data: Reference data for validation (optional)
            row_number: Row number for error reporting (optional)
            
        Returns:
            ValidationResult for the record
        """
        result = ValidationResult(is_valid=True)
        
        # Required field validation
        self._validate_required_fields(record, result, row_number)
        
        # Data type validation
        self._validate_data_types(record, result, row_number)
        
        # Format validation
        self._validate_formats(record, result, row_number)
        
        # Business rule validation
        self._validate_business_rules(record, result, row_number)
        
        # Reference data validation
        if reference_data:
            self._validate_against_reference(record, reference_data, result, row_number)
        
        # Calculate quality score
        result.quality_score = self._calculate_record_quality_score(record, result)
        
        return result
    
    def _validate_required_fields(
        self,
        record: Dict[str, Any],
        result: ValidationResult,
        row_number: Optional[int]
    ) -> None:
        """Validate required fields are present and not empty."""
        required_fields = ['SKU', 'Title', 'Variant Price']
        
        for field in required_fields:
            value = record.get(field)
            
            if value is None:
                result.messages.append(ValidationMessage(
                    severity=ValidationSeverity.CRITICAL,
                    field=field,
                    message=f"Required field '{field}' is missing",
                    code="MISSING_REQUIRED_FIELD",
                    row_number=row_number
                ))
            elif isinstance(value, str) and not value.strip():
                result.messages.append(ValidationMessage(
                    severity=ValidationSeverity.CRITICAL,
                    field=field,
                    message=f"Required field '{field}' is empty",
                    code="EMPTY_REQUIRED_FIELD",
                    value=value,
                    row_number=row_number
                ))
    
    def _validate_data_types(
        self,
        record: Dict[str, Any],
        result: ValidationResult,
        row_number: Optional[int]
    ) -> None:
        """Validate data types for specific fields."""
        type_validations = {
            'Variant Price': {'type': 'float', 'min': 0.0},
            'Variant Compare At Price': {'type': 'float', 'min': 0.0, 'optional': True},
            'Variant Grams': {'type': 'float', 'min': 0.0, 'optional': True},
            'Variant Inventory Qty': {'type': 'int', 'min': 0, 'optional': True},
            'Variant Weight': {'type': 'float', 'min': 0.0, 'optional': True}
        }
        
        for field, validation in type_validations.items():
            value = record.get(field)
            
            # Skip if optional and not present
            if validation.get('optional') and (value is None or value == ''):
                continue
            
            if value is not None and value != '':
                try:
                    if validation['type'] == 'float':
                        # Handle currency formats
                        if isinstance(value, str):
                            cleaned_value = re.sub(r'[^\d.-]', '', value)
                            numeric_value = float(cleaned_value) if cleaned_value else 0.0
                        else:
                            numeric_value = float(value)
                        
                        if 'min' in validation and numeric_value < validation['min']:
                            result.messages.append(ValidationMessage(
                                severity=ValidationSeverity.ERROR,
                                field=field,
                                message=f"Value {numeric_value} is below minimum {validation['min']}",
                                code="VALUE_BELOW_MINIMUM",
                                value=value,
                                expected=f">= {validation['min']}",
                                row_number=row_number
                            ))
                        
                        if 'max' in validation and numeric_value > validation['max']:
                            result.messages.append(ValidationMessage(
                                severity=ValidationSeverity.ERROR,
                                field=field,
                                message=f"Value {numeric_value} is above maximum {validation['max']}",
                                code="VALUE_ABOVE_MAXIMUM",
                                value=value,
                                expected=f"<= {validation['max']}",
                                row_number=row_number
                            ))
                    
                    elif validation['type'] == 'int':
                        if isinstance(value, str):
                            cleaned_value = re.sub(r'[^\d-]', '', value)
                            int_value = int(cleaned_value) if cleaned_value else 0
                        else:
                            int_value = int(float(value))
                        
                        if 'min' in validation and int_value < validation['min']:
                            result.messages.append(ValidationMessage(
                                severity=ValidationSeverity.ERROR,
                                field=field,
                                message=f"Value {int_value} is below minimum {validation['min']}",
                                code="VALUE_BELOW_MINIMUM",
                                value=value,
                                expected=f">= {validation['min']}",
                                row_number=row_number
                            ))
                
                except (ValueError, TypeError):
                    result.messages.append(ValidationMessage(
                        severity=ValidationSeverity.ERROR,
                        field=field,
                        message=f"Invalid {validation['type']} value: {value}",
                        code="INVALID_DATA_TYPE",
                        value=value,
                        expected=validation['type'],
                        row_number=row_number
                    ))
    
    def _validate_formats(
        self,
        record: Dict[str, Any],
        result: ValidationResult,
        row_number: Optional[int]
    ) -> None:
        """Validate field formats using regex patterns."""
        for field, pattern_info in self.validation_patterns.items():
            value = record.get(field)
            
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            
            pattern = pattern_info['pattern']
            message = pattern_info['message']
            severity = ValidationSeverity(pattern_info.get('severity', 'warning'))
            
            if not re.match(pattern, str(value)):
                result.messages.append(ValidationMessage(
                    severity=severity,
                    field=field,
                    message=f"{message}: {value}",
                    code="INVALID_FORMAT",
                    value=value,
                    expected=pattern_info.get('expected', 'Valid format'),
                    row_number=row_number
                ))
    
    def _validate_business_rules(
        self,
        record: Dict[str, Any],
        result: ValidationResult,
        row_number: Optional[int]
    ) -> None:
        """Validate business rules."""
        for rule in self.business_rules:
            try:
                if not self._evaluate_business_rule(record, rule):
                    result.messages.append(ValidationMessage(
                        severity=ValidationSeverity(rule.get('severity', 'warning')),
                        field=rule.get('field', 'business_rule'),
                        message=rule['message'],
                        code=rule.get('code', 'BUSINESS_RULE_VIOLATION'),
                        row_number=row_number
                    ))
            except Exception as e:
                self.logger.warning(f"Failed to evaluate business rule {rule.get('name')}: {str(e)}")
    
    def _evaluate_business_rule(self, record: Dict[str, Any], rule: Dict[str, Any]) -> bool:
        """Evaluate a single business rule."""
        rule_type = rule['type']
        
        if rule_type == 'price_consistency':
            # Variant price should not be higher than compare at price
            price = record.get('Variant Price')
            compare_price = record.get('Variant Compare At Price')
            
            if price and compare_price:
                try:
                    price_val = float(re.sub(r'[^\d.-]', '', str(price)))
                    compare_val = float(re.sub(r'[^\d.-]', '', str(compare_price)))
                    return price_val <= compare_val
                except (ValueError, TypeError):
                    return True  # Skip validation if can't parse
            return True
        
        elif rule_type == 'sku_uniqueness':
            # This would require database lookup
            return True  # Placeholder
        
        elif rule_type == 'inventory_tracking':
            # If tracking inventory, quantity should be specified
            tracker = record.get('Variant Inventory Tracker')
            quantity = record.get('Variant Inventory Qty')
            
            if tracker and str(tracker).lower() in ['shopify', 'true', '1']:
                return quantity is not None and quantity != ''
            return True
        
        elif rule_type == 'image_url_valid':
            # Validate image URLs
            image_url = record.get('Image Src')
            if image_url:
                return self._is_valid_url(image_url)
            return True
        
        elif rule_type == 'category_consistency':
            # Vendor and type should be consistent
            vendor = record.get('Vendor', '').lower()
            product_type = record.get('Type', '').lower()
            
            # Add specific vendor-type consistency rules here
            return True  # Placeholder
        
        return True
    
    def _validate_against_reference(
        self,
        record: Dict[str, Any],
        reference_data: Dict[str, Any],
        result: ValidationResult,
        row_number: Optional[int]
    ) -> None:
        """Validate record against reference data."""
        sku = record.get('SKU')
        if not sku:
            return
        
        reference_records = reference_data.get('records', [])
        
        # Look for matching reference record
        matching_record = None
        for ref_record in reference_records:
            if ref_record.get('ItemNumber') == sku:
                matching_record = ref_record
                break
        
        if matching_record:
            # Validate consistency with reference data
            self._validate_reference_consistency(record, matching_record, result, row_number)
        else:
            # SKU not found in reference data
            result.messages.append(ValidationMessage(
                severity=ValidationSeverity.WARNING,
                field='SKU',
                message=f"SKU {sku} not found in reference data",
                code="SKU_NOT_IN_REFERENCE",
                value=sku,
                row_number=row_number
            ))
    
    def _validate_reference_consistency(
        self,
        record: Dict[str, Any],
        reference_record: Dict[str, Any],
        result: ValidationResult,
        row_number: Optional[int]
    ) -> None:
        """Validate consistency between record and reference data."""
        consistency_checks = {
            'Vendor': 'ManufacturerName',
            'Variant Price': 'ListPrice',
            'Variant Grams': 'Weight'
        }
        
        for record_field, ref_field in consistency_checks.items():
            record_value = record.get(record_field)
            ref_value = reference_record.get(ref_field)
            
            if record_value and ref_value:
                # Normalize values for comparison
                if record_field in ['Variant Price', 'Variant Grams']:
                    try:
                        record_num = float(re.sub(r'[^\d.-]', '', str(record_value)))
                        ref_num = float(str(ref_value))
                        
                        # Allow for small variations
                        if abs(record_num - ref_num) / max(record_num, ref_num) > 0.1:  # 10% tolerance
                            result.messages.append(ValidationMessage(
                                severity=ValidationSeverity.WARNING,
                                field=record_field,
                                message=f"Value differs significantly from reference: {record_value} vs {ref_value}",
                                code="REFERENCE_INCONSISTENCY",
                                value=record_value,
                                expected=ref_value,
                                row_number=row_number
                            ))
                    except (ValueError, TypeError):
                        pass
                else:
                    # String comparison
                    if str(record_value).strip().lower() != str(ref_value).strip().lower():
                        result.messages.append(ValidationMessage(
                            severity=ValidationSeverity.INFO,
                            field=record_field,
                            message=f"Value differs from reference: '{record_value}' vs '{ref_value}'",
                            code="REFERENCE_DIFFERENCE",
                            value=record_value,
                            expected=ref_value,
                            row_number=row_number
                        ))
    
    def _validate_batch_rules(self, data: List[Dict[str, Any]]) -> ValidationResult:
        """Validate batch-level rules."""
        result = ValidationResult(is_valid=True)
        
        # Check for duplicate SKUs
        sku_counts = {}
        for i, record in enumerate(data):
            sku = record.get('SKU')
            if sku:
                if sku in sku_counts:
                    sku_counts[sku].append(i + 1)
                else:
                    sku_counts[sku] = [i + 1]
        
        # Report duplicates
        for sku, rows in sku_counts.items():
            if len(rows) > 1:
                result.messages.append(ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    field='SKU',
                    message=f"Duplicate SKU '{sku}' found in rows: {', '.join(map(str, rows))}",
                    code="DUPLICATE_SKU",
                    value=sku
                ))
        
        return result
    
    def _calculate_record_quality_score(
        self,
        record: Dict[str, Any],
        validation_result: ValidationResult
    ) -> float:
        """Calculate quality score for a record (0-100)."""
        # Start with perfect score
        score = 100.0
        
        # Deduct points for validation issues
        for message in validation_result.messages:
            if message.severity == ValidationSeverity.CRITICAL:
                score -= 25.0
            elif message.severity == ValidationSeverity.ERROR:
                score -= 15.0
            elif message.severity == ValidationSeverity.WARNING:
                score -= 5.0
            elif message.severity == ValidationSeverity.INFO:
                score -= 1.0
        
        # Bonus points for completeness
        completeness_score = self._calculate_completeness_score(record)
        score += (completeness_score - 70.0) * 0.3  # Bonus for above-average completeness
        
        return max(0.0, min(100.0, score))
    
    def _calculate_completeness_score(self, record: Dict[str, Any]) -> float:
        """Calculate completeness score for a record."""
        required_fields = ['SKU', 'Title', 'Variant Price']
        optional_fields = ['Body (HTML)', 'Vendor', 'Type', 'Image Src', 'Variant Grams']
        
        required_score = 0
        for field in required_fields:
            if record.get(field) and str(record[field]).strip():
                required_score += 1
        
        optional_score = 0
        for field in optional_fields:
            if record.get(field) and str(record[field]).strip():
                optional_score += 1
        
        # Required fields are 70% of score, optional are 30%
        total_score = (required_score / len(required_fields)) * 70 + (optional_score / len(optional_fields)) * 30
        return total_score
    
    def _categorize_messages(self, result: ValidationResult) -> None:
        """Categorize validation messages by severity."""
        for message in result.messages:
            message_dict = {
                'field': message.field,
                'message': message.message,
                'code': message.code,
                'value': message.value,
                'expected': message.expected,
                'row_number': message.row_number
            }
            
            if message.severity == ValidationSeverity.CRITICAL:
                result.errors.append(message_dict)
            elif message.severity == ValidationSeverity.ERROR:
                result.errors.append(message_dict)
            elif message.severity == ValidationSeverity.WARNING:
                result.warnings.append(message_dict)
            elif message.severity == ValidationSeverity.INFO:
                result.info.append(message_dict)
    
    def _record_has_errors(self, record: Dict[str, Any], messages: List[ValidationMessage]) -> bool:
        """Check if a record has validation errors."""
        record_row = record.get('_import_row_number')
        for message in messages:
            if (message.row_number == record_row and 
                message.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]):
                return True
        return False
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            parsed = urllib.parse.urlparse(url)
            return all([parsed.scheme, parsed.netloc])
        except Exception:
            return False
    
    def _load_validation_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load validation patterns for field formats."""
        return {
            'SKU': {
                'pattern': r'^[A-Z0-9\-_]{3,50}$',
                'message': 'SKU must be 3-50 characters, alphanumeric, hyphens and underscores only',
                'severity': 'warning',
                'expected': 'Alphanumeric with hyphens/underscores, 3-50 chars'
            },
            'Handle': {
                'pattern': r'^[a-z0-9\-]+$',
                'message': 'Handle must be lowercase alphanumeric with hyphens only',
                'severity': 'warning',
                'expected': 'Lowercase alphanumeric with hyphens'
            },
            'Image Src': {
                'pattern': r'^https?://.*\.(jpg|jpeg|png|gif|webp)(\?.*)?$',
                'message': 'Image URL must be a valid HTTP/HTTPS URL ending with image extension',
                'severity': 'warning',
                'expected': 'Valid image URL'
            }
        }
    
    def _load_business_rules(self) -> List[Dict[str, Any]]:
        """Load business validation rules."""
        return [
            {
                'name': 'price_consistency',
                'type': 'price_consistency',
                'message': 'Variant price should not exceed compare at price',
                'severity': 'warning',
                'field': 'Variant Price',
                'code': 'PRICE_INCONSISTENCY'
            },
            {
                'name': 'inventory_tracking',
                'type': 'inventory_tracking',
                'message': 'Inventory quantity should be specified when tracking inventory',
                'severity': 'warning',
                'field': 'Variant Inventory Qty',
                'code': 'INVENTORY_TRACKING_INCOMPLETE'
            },
            {
                'name': 'image_url_valid',
                'type': 'image_url_valid',
                'message': 'Image URL is not accessible or invalid',
                'severity': 'warning',
                'field': 'Image Src',
                'code': 'INVALID_IMAGE_URL'
            }
        ]