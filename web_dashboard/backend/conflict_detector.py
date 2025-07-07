"""Data conflict detection service for identifying and resolving data conflicts."""
import logging
import hashlib
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import difflib

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of data conflicts."""
    VALUE_MISMATCH = "value_mismatch"
    MISSING_FIELD = "missing_field"
    TYPE_MISMATCH = "type_mismatch"
    DUPLICATE_KEY = "duplicate_key"
    TIMESTAMP_CONFLICT = "timestamp_conflict"
    BUSINESS_RULE_VIOLATION = "business_rule_violation"


class ConflictSeverity(Enum):
    """Severity levels for conflicts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ConflictDetail:
    """Detailed information about a specific conflict."""
    field_name: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    source_value: Any
    target_value: Any
    description: str
    auto_resolvable: bool = False
    resolution_strategy: Optional[str] = None
    confidence_score: float = 0.0  # 0.0 to 1.0


@dataclass
class DataConflict:
    """Represents a conflict between two data records."""
    id: str
    source_record: Dict[str, Any]
    target_record: Dict[str, Any]
    conflicts: List[ConflictDetail] = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolution_method: Optional[str] = None
    resolved_by: Optional[str] = None
    status: str = "pending"  # pending, resolved, ignored
    
    @property
    def severity(self) -> ConflictSeverity:
        """Get overall conflict severity."""
        if not self.conflicts:
            return ConflictSeverity.LOW
        
        # Define severity order for comparison
        severity_order = {
            ConflictSeverity.LOW: 0,
            ConflictSeverity.MEDIUM: 1,
            ConflictSeverity.HIGH: 2,
            ConflictSeverity.CRITICAL: 3
        }
        
        # Find the highest severity
        max_severity = ConflictSeverity.LOW
        max_value = 0
        
        for conflict in self.conflicts:
            value = severity_order.get(conflict.severity, 0)
            if value > max_value:
                max_value = value
                max_severity = conflict.severity
        
        return max_severity
    
    @property
    def is_auto_resolvable(self) -> bool:
        """Check if all conflicts can be auto-resolved."""
        return all(conflict.auto_resolvable for conflict in self.conflicts)


class ConflictDetector:
    """Service for detecting conflicts between data records."""
    
    def __init__(self):
        """Initialize conflict detector."""
        self.detected_conflicts: Dict[str, DataConflict] = {}
        self.resolution_rules: Dict[str, Dict[str, Any]] = {}
        self.business_rules: List[Dict[str, Any]] = []
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Set up default conflict resolution rules."""
        self.resolution_rules = {
            "timestamp_newest": {
                "description": "Use the record with the newest timestamp",
                "applicable_fields": ["updated_at", "modified_at", "last_sync"],
                "strategy": "newest_wins"
            },
            "source_priority": {
                "description": "Prioritize specific data sources",
                "source_priority": ["manual", "api", "import", "sync"],
                "strategy": "source_priority"
            },
            "non_empty_preferred": {
                "description": "Prefer non-empty values over empty ones",
                "strategy": "non_empty_wins"
            },
            "length_preferred": {
                "description": "Prefer longer text values (more descriptive)",
                "applicable_types": ["str"],
                "strategy": "longer_wins"
            }
        }
        
        # Set up business rules
        self.business_rules = [
            {
                "name": "price_validation",
                "description": "Price must be positive",
                "field": "price",
                "validation": lambda x: x > 0 if isinstance(x, (int, float)) else True
            },
            {
                "name": "sku_format",
                "description": "SKU must be alphanumeric",
                "field": "sku",
                "validation": lambda x: x.replace('-', '').replace('_', '').isalnum() if isinstance(x, str) else True
            },
            {
                "name": "email_format",
                "description": "Email must contain @ symbol",
                "field": "email",
                "validation": lambda x: '@' in x if isinstance(x, str) else True
            }
        ]
    
    def detect_conflicts(self, 
                        source_record: Dict[str, Any], 
                        target_record: Dict[str, Any],
                        key_field: str = "id",
                        ignore_fields: Optional[Set[str]] = None) -> Optional[DataConflict]:
        """Detect conflicts between two records.
        
        Args:
            source_record: Source data record
            target_record: Target data record to compare against
            key_field: Field to use as record identifier
            ignore_fields: Fields to ignore during comparison
            
        Returns:
            DataConflict object if conflicts found, None otherwise
        """
        ignore_fields = ignore_fields or {"created_at", "id", "updated_at"}
        
        # Generate conflict ID
        record_id = source_record.get(key_field, "unknown")
        conflict_id = self._generate_conflict_id(source_record, target_record)
        
        conflicts = []
        
        # Get all fields to compare
        all_fields = set(source_record.keys()) | set(target_record.keys())
        compare_fields = all_fields - ignore_fields
        
        for field in compare_fields:
            field_conflicts = self._compare_field(field, source_record, target_record)
            conflicts.extend(field_conflicts)
        
        # Check business rules
        business_conflicts = self._check_business_rules(source_record, target_record)
        conflicts.extend(business_conflicts)
        
        if conflicts:
            data_conflict = DataConflict(
                id=conflict_id,
                source_record=source_record,
                target_record=target_record,
                conflicts=conflicts
            )
            
            # Auto-resolve if possible
            self._attempt_auto_resolution(data_conflict)
            
            self.detected_conflicts[conflict_id] = data_conflict
            logger.info(f"Detected {len(conflicts)} conflicts for record {record_id}")
            return data_conflict
        
        return None
    
    def _compare_field(self, 
                      field: str, 
                      source_record: Dict[str, Any], 
                      target_record: Dict[str, Any]) -> List[ConflictDetail]:
        """Compare a specific field between two records."""
        conflicts = []
        
        source_value = source_record.get(field)
        target_value = target_record.get(field)
        
        # Missing field check
        if field in source_record and field not in target_record:
            conflicts.append(ConflictDetail(
                field_name=field,
                conflict_type=ConflictType.MISSING_FIELD,
                severity=ConflictSeverity.MEDIUM,
                source_value=source_value,
                target_value=None,
                description=f"Field '{field}' exists in source but missing in target",
                auto_resolvable=True,
                resolution_strategy="use_source"
            ))
        elif field not in source_record and field in target_record:
            conflicts.append(ConflictDetail(
                field_name=field,
                conflict_type=ConflictType.MISSING_FIELD,
                severity=ConflictSeverity.MEDIUM,
                source_value=None,
                target_value=target_value,
                description=f"Field '{field}' exists in target but missing in source",
                auto_resolvable=True,
                resolution_strategy="use_target"
            ))
        elif field in source_record and field in target_record:
            # Both fields exist, compare values
            if source_value != target_value:
                # Type mismatch check
                if type(source_value) != type(target_value):
                    conflicts.append(ConflictDetail(
                        field_name=field,
                        conflict_type=ConflictType.TYPE_MISMATCH,
                        severity=ConflictSeverity.HIGH,
                        source_value=source_value,
                        target_value=target_value,
                        description=f"Type mismatch for field '{field}': {type(source_value).__name__} vs {type(target_value).__name__}",
                        auto_resolvable=False
                    ))
                else:
                    # Value mismatch
                    severity = self._determine_value_conflict_severity(field, source_value, target_value)
                    auto_resolvable, strategy = self._can_auto_resolve_value_conflict(field, source_value, target_value)
                    
                    conflicts.append(ConflictDetail(
                        field_name=field,
                        conflict_type=ConflictType.VALUE_MISMATCH,
                        severity=severity,
                        source_value=source_value,
                        target_value=target_value,
                        description=f"Value mismatch for field '{field}': '{source_value}' vs '{target_value}'",
                        auto_resolvable=auto_resolvable,
                        resolution_strategy=strategy,
                        confidence_score=self._calculate_confidence_score(field, source_value, target_value)
                    ))
        
        return conflicts
    
    def _check_business_rules(self, 
                             source_record: Dict[str, Any], 
                             target_record: Dict[str, Any]) -> List[ConflictDetail]:
        """Check business rules violations."""
        conflicts = []
        
        for rule in self.business_rules:
            field = rule["field"]
            validation = rule["validation"]
            
            # Check source record
            if field in source_record:
                if not validation(source_record[field]):
                    conflicts.append(ConflictDetail(
                        field_name=field,
                        conflict_type=ConflictType.BUSINESS_RULE_VIOLATION,
                        severity=ConflictSeverity.HIGH,
                        source_value=source_record[field],
                        target_value=target_record.get(field),
                        description=f"Business rule violation in source: {rule['description']}",
                        auto_resolvable=field in target_record and validation(target_record[field]),
                        resolution_strategy="use_target" if field in target_record else None
                    ))
            
            # Check target record
            if field in target_record:
                if not validation(target_record[field]):
                    conflicts.append(ConflictDetail(
                        field_name=field,
                        conflict_type=ConflictType.BUSINESS_RULE_VIOLATION,
                        severity=ConflictSeverity.HIGH,
                        source_value=source_record.get(field),
                        target_value=target_record[field],
                        description=f"Business rule violation in target: {rule['description']}",
                        auto_resolvable=field in source_record and validation(source_record[field]),
                        resolution_strategy="use_source" if field in source_record else None
                    ))
        
        return conflicts
    
    def _determine_value_conflict_severity(self, 
                                          field: str, 
                                          source_value: Any, 
                                          target_value: Any) -> ConflictSeverity:
        """Determine severity of a value conflict."""
        # Critical fields
        critical_fields = {"id", "sku", "email", "price"}
        if field in critical_fields:
            return ConflictSeverity.CRITICAL
        
        # High importance fields
        high_fields = {"title", "name", "description", "status"}
        if field in high_fields:
            return ConflictSeverity.HIGH
        
        # Check if values are similar (for strings)
        if isinstance(source_value, str) and isinstance(target_value, str):
            similarity = difflib.SequenceMatcher(None, source_value, target_value).ratio()
            if similarity > 0.8:
                return ConflictSeverity.LOW
            elif similarity > 0.5:
                return ConflictSeverity.MEDIUM
            else:
                return ConflictSeverity.HIGH
        
        return ConflictSeverity.MEDIUM
    
    def _can_auto_resolve_value_conflict(self, 
                                        field: str, 
                                        source_value: Any, 
                                        target_value: Any) -> Tuple[bool, Optional[str]]:
        """Determine if a value conflict can be auto-resolved."""
        
        # Non-empty vs empty
        if not source_value and target_value:
            return True, "use_target"
        elif source_value and not target_value:
            return True, "use_source"
        
        # Length-based resolution for strings
        if isinstance(source_value, str) and isinstance(target_value, str):
            if len(source_value) > len(target_value) * 1.5:  # Significantly longer
                return True, "use_source"
            elif len(target_value) > len(source_value) * 1.5:
                return True, "use_target"
        
        # Numeric comparisons
        if isinstance(source_value, (int, float)) and isinstance(target_value, (int, float)):
            # For prices, prefer higher value (might be more recent)
            if field.lower() in ["price", "cost", "amount"]:
                if abs(source_value - target_value) / max(source_value, target_value) < 0.1:  # Within 10%
                    return True, "use_source"  # Default to source
        
        return False, None
    
    def _calculate_confidence_score(self, 
                                   field: str, 
                                   source_value: Any, 
                                   target_value: Any) -> float:
        """Calculate confidence score for conflict resolution."""
        if isinstance(source_value, str) and isinstance(target_value, str):
            # String similarity
            similarity = difflib.SequenceMatcher(None, source_value, target_value).ratio()
            return similarity
        
        if isinstance(source_value, (int, float)) and isinstance(target_value, (int, float)):
            # Numeric similarity
            if max(source_value, target_value) == 0:
                return 1.0 if source_value == target_value else 0.0
            
            diff_ratio = abs(source_value - target_value) / max(source_value, target_value)
            return max(0.0, 1.0 - diff_ratio)
        
        # Exact match
        return 1.0 if source_value == target_value else 0.0
    
    def _attempt_auto_resolution(self, conflict: DataConflict) -> None:
        """Attempt to auto-resolve conflicts."""
        if not conflict.is_auto_resolvable:
            return
        
        resolved_record = conflict.source_record.copy()
        
        for conflict_detail in conflict.conflicts:
            if conflict_detail.auto_resolvable and conflict_detail.resolution_strategy:
                field = conflict_detail.field_name
                
                if conflict_detail.resolution_strategy == "use_source":
                    resolved_record[field] = conflict_detail.source_value
                elif conflict_detail.resolution_strategy == "use_target":
                    resolved_record[field] = conflict_detail.target_value
        
        # Mark as auto-resolved
        conflict.status = "auto_resolved"
        conflict.resolved_at = datetime.utcnow()
        conflict.resolution_method = "automatic"
        
        logger.info(f"Auto-resolved conflict {conflict.id}")
    
    def _generate_conflict_id(self, 
                             source_record: Dict[str, Any], 
                             target_record: Dict[str, Any]) -> str:
        """Generate unique conflict ID."""
        content = json.dumps([source_record, target_record], sort_keys=True, default=str)
        return hashlib.md5(content.encode()).hexdigest()
    
    def resolve_conflict(self, 
                        conflict_id: str, 
                        resolution: Dict[str, Any],
                        resolved_by: str) -> bool:
        """Manually resolve a conflict.
        
        Args:
            conflict_id: ID of the conflict to resolve
            resolution: Dictionary with field resolutions
            resolved_by: User who resolved the conflict
            
        Returns:
            True if resolved successfully
        """
        if conflict_id not in self.detected_conflicts:
            return False
        
        conflict = self.detected_conflicts[conflict_id]
        
        # Apply resolution
        resolved_record = conflict.source_record.copy()
        for field, value in resolution.items():
            resolved_record[field] = value
        
        # Mark as resolved
        conflict.status = "manually_resolved"
        conflict.resolved_at = datetime.utcnow()
        conflict.resolution_method = "manual"
        conflict.resolved_by = resolved_by
        
        logger.info(f"Manually resolved conflict {conflict_id} by {resolved_by}")
        return True
    
    def get_conflicts(self, 
                     status_filter: Optional[str] = None,
                     severity_filter: Optional[ConflictSeverity] = None) -> List[DataConflict]:
        """Get conflicts with optional filtering."""
        conflicts = list(self.detected_conflicts.values())
        
        if status_filter:
            conflicts = [c for c in conflicts if c.status == status_filter]
        
        if severity_filter:
            conflicts = [c for c in conflicts if c.severity == severity_filter]
        
        return sorted(conflicts, key=lambda x: x.detected_at, reverse=True)
    
    def get_conflict_stats(self) -> Dict[str, Any]:
        """Get conflict statistics."""
        conflicts = list(self.detected_conflicts.values())
        
        total_conflicts = len(conflicts)
        pending_conflicts = len([c for c in conflicts if c.status == "pending"])
        resolved_conflicts = len([c for c in conflicts if c.status in ["auto_resolved", "manually_resolved"]])
        auto_resolved = len([c for c in conflicts if c.status == "auto_resolved"])
        
        severity_counts = {
            "critical": len([c for c in conflicts if c.severity == ConflictSeverity.CRITICAL]),
            "high": len([c for c in conflicts if c.severity == ConflictSeverity.HIGH]),
            "medium": len([c for c in conflicts if c.severity == ConflictSeverity.MEDIUM]),
            "low": len([c for c in conflicts if c.severity == ConflictSeverity.LOW])
        }
        
        return {
            "total_conflicts": total_conflicts,
            "pending_conflicts": pending_conflicts,
            "resolved_conflicts": resolved_conflicts,
            "auto_resolved_conflicts": auto_resolved,
            "auto_resolution_rate": (auto_resolved / total_conflicts * 100) if total_conflicts > 0 else 0,
            "severity_breakdown": severity_counts
        }


# Global conflict detector instance
conflict_detector = ConflictDetector()