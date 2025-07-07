"""
Product Mapping Service

Provides SKU/MPN matching, validation rules engine, conflict detection and resolution,
and data quality scoring algorithms for product import operations.
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from difflib import SequenceMatcher
import hashlib

from models import Product, Category
from repositories import ProductRepository, CategoryRepository


class MatchType(Enum):
    """Types of product matches."""
    EXACT_SKU = "exact_sku"
    EXACT_MPN = "exact_mpn"
    METAFIELD_CWS_A = "metafield_cws_a"
    METAFIELD_CWS_CATALOG = "metafield_cws_catalog"
    METAFIELD_SPRC = "metafield_sprc"
    FUZZY_SKU = "fuzzy_sku"
    FUZZY_MPN = "fuzzy_mpn"
    NO_MATCH = "no_match"


class MatchQuality(Enum):
    """Quality levels for matches."""
    PERFECT = "perfect"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class MatchResult:
    """Result of a product matching operation."""
    match_type: MatchType
    quality: MatchQuality
    confidence: float  # 0.0 to 1.0
    matched_sku: Optional[str] = None
    matched_product_id: Optional[int] = None
    reference_record: Optional[Dict[str, Any]] = None
    similarity_score: float = 0.0
    conflicts: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationRule:
    """A validation rule for product data."""
    name: str
    field: str
    rule_type: str  # required, format, range, custom
    rule_value: Any
    error_message: str
    severity: str = "error"  # error, warning, info


@dataclass
class ConflictResolution:
    """Configuration for resolving data conflicts."""
    strategy: str  # overwrite, merge, skip, manual
    priority_fields: List[str] = field(default_factory=list)
    merge_strategy: Dict[str, str] = field(default_factory=dict)  # field -> strategy


class ProductMappingService:
    """
    Service for mapping and validating product identifiers and data.
    
    Features:
    - SKU/MPN matching with fuzzy logic
    - Metafield-based matching
    - Validation rules engine
    - Conflict detection and resolution
    - Data quality scoring
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the mapping service."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Validation rules
        self.validation_rules = self._load_default_validation_rules()
        
        # Normalization patterns
        self.sku_normalization_patterns = [
            (r'[^A-Z0-9]', ''),  # Remove non-alphanumeric
            (r'^0+', ''),        # Remove leading zeros
        ]
        
        self.mpn_normalization_patterns = [
            (r'[^A-Z0-9-]', ''),  # Keep alphanumeric and hyphens
            (r'-+', '-'),         # Collapse multiple hyphens
            (r'^-|-$', ''),       # Remove leading/trailing hyphens
        ]
    
    def map_product_identifiers(
        self,
        product_data: Dict[str, Any],
        reference_data: Optional[Dict[str, Any]] = None
    ) -> MatchResult:
        """
        Map product identifiers using various matching strategies.
        
        Args:
            product_data: Raw product data from import
            reference_data: Reference data for validation
            
        Returns:
            MatchResult with mapping information
        """
        try:
            # Extract identifiers from product data
            identifiers = self._extract_identifiers(product_data)
            
            # Try exact matching first
            match_result = self._try_exact_matching(identifiers, reference_data)
            
            if match_result.match_type != MatchType.NO_MATCH:
                return match_result
            
            # Try metafield matching
            match_result = self._try_metafield_matching(identifiers, reference_data)
            
            if match_result.match_type != MatchType.NO_MATCH:
                return match_result
            
            # Try fuzzy matching
            match_result = self._try_fuzzy_matching(identifiers, reference_data)
            
            # Calculate final quality and confidence
            match_result = self._calculate_match_quality(match_result)
            
            return match_result
            
        except Exception as e:
            self.logger.error(f"Error in product mapping: {str(e)}")
            return MatchResult(
                match_type=MatchType.NO_MATCH,
                quality=MatchQuality.NONE,
                confidence=0.0,
                validation_errors=[f"Mapping error: {str(e)}"]
            )
    
    def validate_product_data(
        self,
        product_data: Dict[str, Any],
        rules: Optional[List[ValidationRule]] = None
    ) -> List[str]:
        """
        Validate product data against validation rules.
        
        Args:
            product_data: Product data to validate
            rules: Custom validation rules (optional)
            
        Returns:
            List of validation error messages
        """
        validation_rules = rules or self.validation_rules
        errors = []
        
        for rule in validation_rules:
            try:
                error = self._apply_validation_rule(product_data, rule)
                if error:
                    errors.append(error)
            except Exception as e:
                errors.append(f"Validation rule '{rule.name}' failed: {str(e)}")
        
        return errors
    
    def detect_conflicts(
        self,
        new_data: Dict[str, Any],
        existing_data: Dict[str, Any],
        conflict_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect conflicts between new and existing product data.
        
        Args:
            new_data: New product data
            existing_data: Existing product data
            conflict_fields: Fields to check for conflicts
            
        Returns:
            List of conflict descriptions
        """
        if not conflict_fields:
            conflict_fields = ['name', 'price', 'description', 'brand', 'manufacturer']
        
        conflicts = []
        
        for field in conflict_fields:
            new_value = new_data.get(field)
            existing_value = existing_data.get(field)
            
            if new_value is not None and existing_value is not None:
                if new_value != existing_value:
                    # Calculate similarity for text fields
                    similarity = 0.0
                    if isinstance(new_value, str) and isinstance(existing_value, str):
                        similarity = SequenceMatcher(None, new_value, existing_value).ratio()
                    
                    conflicts.append({
                        'field': field,
                        'new_value': new_value,
                        'existing_value': existing_value,
                        'similarity': similarity,
                        'severity': 'high' if similarity < 0.5 else 'medium'
                    })
        
        return conflicts
    
    def resolve_conflicts(
        self,
        conflicts: List[Dict[str, Any]],
        resolution: ConflictResolution
    ) -> Dict[str, Any]:
        """
        Resolve conflicts using the specified strategy.
        
        Args:
            conflicts: List of conflicts to resolve
            resolution: Resolution configuration
            
        Returns:
            Resolved data
        """
        resolved_data = {}
        
        for conflict in conflicts:
            field = conflict['field']
            new_value = conflict['new_value']
            existing_value = conflict['existing_value']
            
            if resolution.strategy == 'overwrite':
                resolved_data[field] = new_value
            elif resolution.strategy == 'keep_existing':
                resolved_data[field] = existing_value
            elif resolution.strategy == 'merge':
                # Use field-specific merge strategy
                merge_strategy = resolution.merge_strategy.get(field, 'overwrite')
                if merge_strategy == 'concatenate' and isinstance(new_value, str):
                    resolved_data[field] = f"{existing_value} | {new_value}"
                elif merge_strategy == 'prefer_longer':
                    resolved_data[field] = new_value if len(str(new_value)) > len(str(existing_value)) else existing_value
                else:
                    resolved_data[field] = new_value
            elif resolution.strategy == 'skip':
                # Don't include conflicting field
                continue
            else:
                # Default to new value
                resolved_data[field] = new_value
        
        return resolved_data
    
    def calculate_data_quality_score(
        self,
        product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate a data quality score for product data.
        
        Args:
            product_data: Product data to score
            
        Returns:
            Quality score and breakdown
        """
        score_components = {}
        total_weight = 0
        total_score = 0
        
        # Completeness score (40% weight)
        completeness_score = self._calculate_completeness_score(product_data)
        score_components['completeness'] = completeness_score
        total_score += completeness_score * 0.4
        total_weight += 0.4
        
        # Accuracy score (30% weight)
        accuracy_score = self._calculate_accuracy_score(product_data)
        score_components['accuracy'] = accuracy_score
        total_score += accuracy_score * 0.3
        total_weight += 0.3
        
        # Consistency score (20% weight)
        consistency_score = self._calculate_consistency_score(product_data)
        score_components['consistency'] = consistency_score
        total_score += consistency_score * 0.2
        total_weight += 0.2
        
        # Validity score (10% weight)
        validity_score = self._calculate_validity_score(product_data)
        score_components['validity'] = validity_score
        total_score += validity_score * 0.1
        total_weight += 0.1
        
        overall_score = total_score / total_weight if total_weight > 0 else 0
        
        return {
            'overall_score': round(overall_score, 2),
            'grade': self._score_to_grade(overall_score),
            'components': score_components,
            'recommendations': self._generate_quality_recommendations(score_components)
        }
    
    def _extract_identifiers(self, product_data: Dict[str, Any]) -> Dict[str, str]:
        """Extract and normalize identifiers from product data."""
        identifiers = {}
        
        # Extract SKU
        sku = product_data.get('SKU') or product_data.get('sku')
        if sku:
            identifiers['sku'] = self._normalize_sku(str(sku))
        
        # Extract MPN
        mpn = (product_data.get('Variant Grams') or 
               product_data.get('manufacturer_part_number') or
               product_data.get('mpn'))
        if mpn:
            identifiers['mpn'] = self._normalize_mpn(str(mpn))
        
        # Extract metafields
        metafields = [
            'Metafield: custom.CWS_A[list.single_line_text]',
            'Metafield: custom.CWS_Catalog[list.single_line_text]',
            'Metafield: custom.SPRC[list.single_line_text]'
        ]
        
        for metafield in metafields:
            value = product_data.get(metafield)
            if value and str(value).strip():
                # Extract values from list format
                values = self._parse_metafield_list(str(value))
                identifiers[metafield] = values
        
        return identifiers
    
    def _normalize_sku(self, sku: str) -> str:
        """Normalize SKU for matching."""
        normalized = sku.upper().strip()
        for pattern, replacement in self.sku_normalization_patterns:
            normalized = re.sub(pattern, replacement, normalized)
        return normalized
    
    def _normalize_mpn(self, mpn: str) -> str:
        """Normalize MPN for matching."""
        normalized = mpn.upper().strip()
        for pattern, replacement in self.mpn_normalization_patterns:
            normalized = re.sub(pattern, replacement, normalized)
        return normalized
    
    def _parse_metafield_list(self, metafield_value: str) -> List[str]:
        """Parse metafield list values."""
        # Handle different list formats
        if metafield_value.startswith('[') and metafield_value.endswith(']'):
            # JSON-style list
            values = metafield_value[1:-1].split(',')
        else:
            # Simple comma-separated
            values = metafield_value.split(',')
        
        # Clean and normalize values
        cleaned_values = []
        for value in values:
            cleaned = value.strip().strip('"\'')
            if cleaned:
                cleaned_values.append(self._normalize_sku(cleaned))
        
        return cleaned_values
    
    def _try_exact_matching(
        self,
        identifiers: Dict[str, Any],
        reference_data: Optional[Dict[str, Any]]
    ) -> MatchResult:
        """Try exact matching on SKU and MPN."""
        if not reference_data:
            return MatchResult(
                match_type=MatchType.NO_MATCH,
                quality=MatchQuality.NONE,
                confidence=0.0
            )
        
        # Create lookup index from reference data
        reference_index = self._create_reference_index(reference_data)
        
        # Try exact SKU match
        sku = identifiers.get('sku')
        if sku and sku in reference_index['sku']:
            record = reference_index['sku'][sku]
            return MatchResult(
                match_type=MatchType.EXACT_SKU,
                quality=MatchQuality.PERFECT,
                confidence=1.0,
                matched_sku=sku,
                reference_record=record,
                similarity_score=1.0
            )
        
        # Try exact MPN match
        mpn = identifiers.get('mpn')
        if mpn and mpn in reference_index['base_part_number']:
            record = reference_index['base_part_number'][mpn]
            return MatchResult(
                match_type=MatchType.EXACT_MPN,
                quality=MatchQuality.PERFECT,
                confidence=1.0,
                matched_sku=record.get('ItemNumber'),
                reference_record=record,
                similarity_score=1.0
            )
        
        return MatchResult(
            match_type=MatchType.NO_MATCH,
            quality=MatchQuality.NONE,
            confidence=0.0
        )
    
    def _try_metafield_matching(
        self,
        identifiers: Dict[str, Any],
        reference_data: Optional[Dict[str, Any]]
    ) -> MatchResult:
        """Try matching using metafield values."""
        if not reference_data:
            return MatchResult(
                match_type=MatchType.NO_MATCH,
                quality=MatchQuality.NONE,
                confidence=0.0
            )
        
        reference_index = self._create_reference_index(reference_data)
        
        # Check metafields in priority order
        metafield_types = [
            ('Metafield: custom.CWS_A[list.single_line_text]', MatchType.METAFIELD_CWS_A),
            ('Metafield: custom.CWS_Catalog[list.single_line_text]', MatchType.METAFIELD_CWS_CATALOG),
            ('Metafield: custom.SPRC[list.single_line_text]', MatchType.METAFIELD_SPRC)
        ]
        
        for metafield_name, match_type in metafield_types:
            metafield_values = identifiers.get(metafield_name, [])
            
            for value in metafield_values:
                if value in reference_index['base_part_number']:
                    record = reference_index['base_part_number'][value]
                    return MatchResult(
                        match_type=match_type,
                        quality=MatchQuality.HIGH,
                        confidence=0.9,
                        matched_sku=record.get('ItemNumber'),
                        reference_record=record,
                        similarity_score=1.0,
                        metadata={'metafield_value': value}
                    )
        
        return MatchResult(
            match_type=MatchType.NO_MATCH,
            quality=MatchQuality.NONE,
            confidence=0.0
        )
    
    def _try_fuzzy_matching(
        self,
        identifiers: Dict[str, Any],
        reference_data: Optional[Dict[str, Any]]
    ) -> MatchResult:
        """Try fuzzy matching on identifiers."""
        if not reference_data:
            return MatchResult(
                match_type=MatchType.NO_MATCH,
                quality=MatchQuality.NONE,
                confidence=0.0
            )
        
        best_match = None
        best_score = 0.0
        
        # Create list of all reference identifiers
        reference_records = reference_data.get('records', [])
        
        # Try fuzzy matching on SKU
        sku = identifiers.get('sku')
        if sku:
            for record in reference_records:
                ref_sku = record.get('ItemNumber')
                if ref_sku:
                    normalized_ref_sku = self._normalize_sku(ref_sku)
                    similarity = SequenceMatcher(None, sku, normalized_ref_sku).ratio()
                    
                    if similarity > best_score and similarity >= 0.8:  # 80% similarity threshold
                        best_match = MatchResult(
                            match_type=MatchType.FUZZY_SKU,
                            quality=MatchQuality.MEDIUM if similarity >= 0.9 else MatchQuality.LOW,
                            confidence=similarity,
                            matched_sku=ref_sku,
                            reference_record=record,
                            similarity_score=similarity
                        )
                        best_score = similarity
        
        # Try fuzzy matching on MPN
        mpn = identifiers.get('mpn')
        if mpn:
            for record in reference_records:
                ref_mpn = record.get('BasePartNumber')
                if ref_mpn:
                    normalized_ref_mpn = self._normalize_mpn(ref_mpn)
                    similarity = SequenceMatcher(None, mpn, normalized_ref_mpn).ratio()
                    
                    if similarity > best_score and similarity >= 0.8:
                        best_match = MatchResult(
                            match_type=MatchType.FUZZY_MPN,
                            quality=MatchQuality.MEDIUM if similarity >= 0.9 else MatchQuality.LOW,
                            confidence=similarity,
                            matched_sku=record.get('ItemNumber'),
                            reference_record=record,
                            similarity_score=similarity
                        )
                        best_score = similarity
        
        return best_match or MatchResult(
            match_type=MatchType.NO_MATCH,
            quality=MatchQuality.NONE,
            confidence=0.0
        )
    
    def _create_reference_index(self, reference_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Create lookup indexes from reference data."""
        records = reference_data.get('records', [])
        
        indexes = {
            'sku': {},
            'base_part_number': {}
        }
        
        for record in records:
            # Index by ItemNumber (SKU)
            item_number = record.get('ItemNumber')
            if item_number:
                normalized_sku = self._normalize_sku(item_number)
                indexes['sku'][normalized_sku] = record
            
            # Index by BasePartNumber (MPN)
            base_part_number = record.get('BasePartNumber')
            if base_part_number:
                normalized_mpn = self._normalize_mpn(base_part_number)
                indexes['base_part_number'][normalized_mpn] = record
        
        return indexes
    
    def _calculate_match_quality(self, match_result: MatchResult) -> MatchResult:
        """Calculate overall match quality and confidence."""
        if match_result.match_type == MatchType.NO_MATCH:
            return match_result
        
        # Adjust quality based on match type and similarity
        if match_result.match_type in [MatchType.EXACT_SKU, MatchType.EXACT_MPN]:
            match_result.quality = MatchQuality.PERFECT
            match_result.confidence = 1.0
        elif match_result.match_type in [MatchType.METAFIELD_CWS_A, MatchType.METAFIELD_CWS_CATALOG, MatchType.METAFIELD_SPRC]:
            match_result.quality = MatchQuality.HIGH
            match_result.confidence = 0.9
        elif match_result.similarity_score >= 0.9:
            match_result.quality = MatchQuality.MEDIUM
        else:
            match_result.quality = MatchQuality.LOW
        
        return match_result
    
    def _load_default_validation_rules(self) -> List[ValidationRule]:
        """Load default validation rules."""
        return [
            ValidationRule(
                name="required_sku",
                field="sku",
                rule_type="required",
                rule_value=True,
                error_message="SKU is required"
            ),
            ValidationRule(
                name="required_title",
                field="title",
                rule_type="required",
                rule_value=True,
                error_message="Product title is required"
            ),
            ValidationRule(
                name="price_format",
                field="price",
                rule_type="format",
                rule_value=r'^\d+(\.\d{1,2})?$',
                error_message="Price must be a valid decimal number"
            ),
            ValidationRule(
                name="weight_range",
                field="weight",
                rule_type="range",
                rule_value=(0, 10000),
                error_message="Weight must be between 0 and 10000"
            ),
            ValidationRule(
                name="sku_format",
                field="sku",
                rule_type="format",
                rule_value=r'^[A-Z0-9\-]{3,50}$',
                error_message="SKU must be 3-50 characters, alphanumeric and hyphens only",
                severity="warning"
            )
        ]
    
    def _apply_validation_rule(
        self,
        product_data: Dict[str, Any],
        rule: ValidationRule
    ) -> Optional[str]:
        """Apply a single validation rule."""
        value = product_data.get(rule.field)
        
        if rule.rule_type == "required":
            if rule.rule_value and (value is None or str(value).strip() == ''):
                return rule.error_message
        
        elif rule.rule_type == "format":
            if value is not None and not re.match(rule.rule_value, str(value)):
                return rule.error_message
        
        elif rule.rule_type == "range":
            if value is not None:
                try:
                    num_value = float(value)
                    min_val, max_val = rule.rule_value
                    if not (min_val <= num_value <= max_val):
                        return rule.error_message
                except (ValueError, TypeError):
                    return f"Invalid numeric value for {rule.field}"
        
        return None
    
    def _calculate_completeness_score(self, product_data: Dict[str, Any]) -> float:
        """Calculate completeness score (0-100)."""
        required_fields = ['sku', 'title', 'price', 'description']
        optional_fields = ['brand', 'weight', 'vendor', 'product_type']
        
        required_score = 0
        for field in required_fields:
            if product_data.get(field) and str(product_data[field]).strip():
                required_score += 1
        
        optional_score = 0
        for field in optional_fields:
            if product_data.get(field) and str(product_data[field]).strip():
                optional_score += 1
        
        # Required fields are 70% of score, optional are 30%
        total_score = (required_score / len(required_fields)) * 70 + (optional_score / len(optional_fields)) * 30
        return round(total_score, 2)
    
    def _calculate_accuracy_score(self, product_data: Dict[str, Any]) -> float:
        """Calculate accuracy score based on data format validation."""
        accuracy_checks = []
        
        # Check price format
        price = product_data.get('price')
        if price:
            try:
                float_price = float(price)
                accuracy_checks.append(float_price >= 0)
            except (ValueError, TypeError):
                accuracy_checks.append(False)
        
        # Check weight format
        weight = product_data.get('weight')
        if weight:
            try:
                float_weight = float(weight)
                accuracy_checks.append(0 <= float_weight <= 10000)
            except (ValueError, TypeError):
                accuracy_checks.append(False)
        
        # Check SKU format
        sku = product_data.get('sku')
        if sku:
            accuracy_checks.append(bool(re.match(r'^[A-Z0-9\-]{3,50}$', str(sku))))
        
        # If no checks performed, assume perfect accuracy
        if not accuracy_checks:
            return 100.0
        
        accuracy_score = (sum(accuracy_checks) / len(accuracy_checks)) * 100
        return round(accuracy_score, 2)
    
    def _calculate_consistency_score(self, product_data: Dict[str, Any]) -> float:
        """Calculate consistency score based on field relationships."""
        consistency_checks = []
        
        # Check if vendor and brand are consistent
        vendor = product_data.get('vendor', '').lower()
        brand = product_data.get('brand', '').lower()
        if vendor and brand:
            consistency_checks.append(vendor == brand or vendor in brand or brand in vendor)
        
        # Check if title contains SKU
        title = product_data.get('title', '').upper()
        sku = product_data.get('sku', '').upper()
        if title and sku:
            consistency_checks.append(sku in title)
        
        # If no checks performed, assume perfect consistency
        if not consistency_checks:
            return 100.0
        
        consistency_score = (sum(consistency_checks) / len(consistency_checks)) * 100
        return round(consistency_score, 2)
    
    def _calculate_validity_score(self, product_data: Dict[str, Any]) -> float:
        """Calculate validity score based on business rules."""
        validity_checks = []
        
        # Check for reasonable price
        price = product_data.get('price')
        if price:
            try:
                float_price = float(price)
                validity_checks.append(0.01 <= float_price <= 100000)  # Reasonable price range
            except (ValueError, TypeError):
                validity_checks.append(False)
        
        # Check for reasonable description length
        description = product_data.get('description', '')
        if description:
            validity_checks.append(10 <= len(description.strip()) <= 5000)
        
        # If no checks performed, assume perfect validity
        if not validity_checks:
            return 100.0
        
        validity_score = (sum(validity_checks) / len(validity_checks)) * 100
        return round(validity_score, 2)
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    def _generate_quality_recommendations(self, components: Dict[str, float]) -> List[str]:
        """Generate recommendations based on quality scores."""
        recommendations = []
        
        if components.get('completeness', 0) < 80:
            recommendations.append("Add missing required fields (SKU, title, price, description)")
        
        if components.get('accuracy', 0) < 80:
            recommendations.append("Fix data format issues (price, weight, SKU format)")
        
        if components.get('consistency', 0) < 80:
            recommendations.append("Improve data consistency (vendor/brand alignment, title/SKU relationship)")
        
        if components.get('validity', 0) < 80:
            recommendations.append("Review business rule violations (price range, description length)")
        
        if not recommendations:
            recommendations.append("Data quality is excellent!")
        
        return recommendations