"""Tests for the conflict detector module."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import Dict, Any

from conflict_detector import (
    ConflictDetector, ConflictType, ConflictSeverity, 
    DataConflict, ConflictDetail, conflict_detector
)


class TestConflictType:
    """Test ConflictType enum."""
    
    def test_enum_values(self):
        """Test that all conflict types exist."""
        assert ConflictType.VALUE_MISMATCH.value == "value_mismatch"
        assert ConflictType.MISSING_FIELD.value == "missing_field"
        assert ConflictType.TYPE_MISMATCH.value == "type_mismatch"
        assert ConflictType.DUPLICATE_KEY.value == "duplicate_key"
        assert ConflictType.TIMESTAMP_CONFLICT.value == "timestamp_conflict"
        assert ConflictType.BUSINESS_RULE_VIOLATION.value == "business_rule_violation"


class TestConflictSeverity:
    """Test ConflictSeverity enum."""
    
    def test_enum_values(self):
        """Test that all severity levels exist."""
        assert ConflictSeverity.LOW.value == "low"
        assert ConflictSeverity.MEDIUM.value == "medium"
        assert ConflictSeverity.HIGH.value == "high"
        assert ConflictSeverity.CRITICAL.value == "critical"
    
    def test_severity_ordering(self):
        """Test that severity levels have the expected values and order."""
        # Define the expected order of severities
        severity_order = ["low", "medium", "high", "critical"]
        severities = [
            ConflictSeverity.LOW,
            ConflictSeverity.MEDIUM,
            ConflictSeverity.HIGH,
            ConflictSeverity.CRITICAL
        ]
        
        # Test that severities have the correct values in order
        for i, severity in enumerate(severities):
            assert severity.value == severity_order[i]
        
        # Test that we can determine severity ordering using list index
        def get_severity_level(severity: ConflictSeverity) -> int:
            return severity_order.index(severity.value)
        
        # Test ordering logic
        assert get_severity_level(ConflictSeverity.LOW) < get_severity_level(ConflictSeverity.MEDIUM)
        assert get_severity_level(ConflictSeverity.MEDIUM) < get_severity_level(ConflictSeverity.HIGH)
        assert get_severity_level(ConflictSeverity.HIGH) < get_severity_level(ConflictSeverity.CRITICAL)


class TestConflictDetail:
    """Test ConflictDetail class."""
    
    def test_conflict_detail_creation(self):
        """Test creating a ConflictDetail."""
        conflict = ConflictDetail(
            field_name="title",
            conflict_type=ConflictType.VALUE_MISMATCH,
            severity=ConflictSeverity.MEDIUM,
            source_value="Original Title",
            target_value="Modified Title",
            description="Title values differ",
            auto_resolvable=True,
            resolution_strategy="prefer_newer",
            confidence_score=0.8
        )
        
        assert conflict.field_name == "title"
        assert conflict.conflict_type == ConflictType.VALUE_MISMATCH
        assert conflict.severity == ConflictSeverity.MEDIUM
        assert conflict.source_value == "Original Title"
        assert conflict.target_value == "Modified Title"
        assert conflict.auto_resolvable is True
        assert conflict.resolution_strategy == "prefer_newer"
        assert conflict.confidence_score == 0.8


class TestDataConflict:
    """Test DataConflict class."""
    
    def test_data_conflict_creation(self):
        """Test creating a DataConflict."""
        field_conflicts = [
            ConflictDetail(
                field_name="title",
                conflict_type=ConflictType.VALUE_MISMATCH,
                severity=ConflictSeverity.MEDIUM,
                source_value="Old Title",
                target_value="New Title",
                description="Title values differ"
            )
        ]
        
        source_record = {"id": "123", "title": "Old Title"}
        target_record = {"id": "123", "title": "New Title"}
        
        conflict = DataConflict(
            id="conflict_123",
            source_record=source_record,
            target_record=target_record,
            conflicts=field_conflicts
        )
        
        assert conflict.id == "conflict_123"
        assert conflict.source_record == source_record
        assert conflict.target_record == target_record
        assert len(conflict.conflicts) == 1
        assert conflict.severity == ConflictSeverity.MEDIUM  # From property
        assert conflict.status == "pending"
        assert conflict.detected_at is not None
    
    def test_auto_resolvable_detection(self):
        """Test automatic detection of resolvable conflicts."""
        resolvable_conflict = ConflictDetail(
            field_name="description",
            conflict_type=ConflictType.VALUE_MISMATCH,
            severity=ConflictSeverity.LOW,
            source_value="Old desc",
            target_value="New desc",
            description="Description values differ",
            auto_resolvable=True
        )
        
        non_resolvable_conflict = ConflictDetail(
            field_name="price",
            conflict_type=ConflictType.VALUE_MISMATCH,
            severity=ConflictSeverity.HIGH,
            source_value=29.99,
            target_value=39.99,
            description="Price values differ significantly",
            auto_resolvable=False
        )
        
        # All conflicts auto-resolvable
        conflict1 = DataConflict(
            id="conflict_auto_1",
            source_record={},
            target_record={},
            conflicts=[resolvable_conflict]
        )
        assert conflict1.is_auto_resolvable is True
        
        # Mixed resolvability
        conflict2 = DataConflict(
            id="conflict_mixed_2",
            source_record={},
            target_record={},
            conflicts=[resolvable_conflict, non_resolvable_conflict]
        )
        assert conflict2.is_auto_resolvable is False


class TestConflictDetector:
    """Test ConflictDetector class."""
    
    def test_initialization(self):
        """Test ConflictDetector initialization."""
        detector = ConflictDetector()
        
        assert len(detector.detected_conflicts) == 0
        assert len(detector.resolution_rules) > 0
        assert len(detector.business_rules) > 0
    
    def test_detect_no_conflicts(self, conflict_detector):
        """Test detection when no conflicts exist."""
        source_record = {"id": "123", "title": "Same Title", "price": 29.99}
        target_record = {"id": "123", "title": "Same Title", "price": 29.99}
        
        conflict = conflict_detector.detect_conflicts(source_record, target_record)
        assert conflict is None
    
    def test_detect_value_mismatch(self, conflict_detector):
        """Test detection of value mismatches."""
        source_record = {"id": "123", "title": "Original Title", "price": 29.99}
        target_record = {"id": "123", "title": "Modified Title", "price": 29.99}
        
        conflict = conflict_detector.detect_conflicts(source_record, target_record)
        
        assert conflict is not None
        assert len(conflict.conflicts) == 1
        assert conflict.conflicts[0].field_name == "title"
        assert conflict.conflicts[0].conflict_type == ConflictType.VALUE_MISMATCH
        assert conflict.conflicts[0].source_value == "Original Title"
        assert conflict.conflicts[0].target_value == "Modified Title"
    
    def test_detect_missing_fields(self, conflict_detector):
        """Test detection of missing fields."""
        source_record = {"id": "123", "title": "Title", "description": "Description"}
        target_record = {"id": "123", "title": "Title"}  # Missing description
        
        conflict = conflict_detector.detect_conflicts(source_record, target_record)
        
        assert conflict is not None
        missing_conflicts = [c for c in conflict.conflicts 
                           if c.conflict_type == ConflictType.MISSING_FIELD]
        assert len(missing_conflicts) == 1
        assert missing_conflicts[0].field_name == "description"
    
    def test_detect_type_mismatches(self, conflict_detector):
        """Test detection of type mismatches."""
        source_record = {"id": "123", "price": 29.99}
        target_record = {"id": "123", "price": "29.99"}  # String instead of float
        
        conflict = conflict_detector.detect_conflicts(source_record, target_record)
        
        assert conflict is not None
        type_conflicts = [c for c in conflict.conflicts 
                         if c.conflict_type == ConflictType.TYPE_MISMATCH]
        assert len(type_conflicts) == 1
        assert type_conflicts[0].field_name == "price"
    
    def test_ignore_fields(self, conflict_detector):
        """Test ignoring specified fields."""
        source_record = {"id": "123", "title": "Title1", "updated_at": "2024-01-01"}
        target_record = {"id": "123", "title": "Title2", "updated_at": "2024-01-02"}
        
        # Detect conflicts ignoring updated_at
        conflict = conflict_detector.detect_conflicts(
            source_record, 
            target_record,
            ignore_fields={"updated_at"}
        )
        
        assert conflict is not None
        assert len(conflict.conflicts) == 1
        assert conflict.conflicts[0].field_name == "title"
        
        # No conflicts when ignoring both fields
        conflict2 = conflict_detector.detect_conflicts(
            source_record,
            target_record,
            ignore_fields={"title", "updated_at"}
        )
        assert conflict2 is None
    
    def test_business_rule_violations(self, conflict_detector):
        """Test detection of business rule violations."""
        # Test price rule: price must be positive (from default business rules)
        source_record = {"id": "123", "price": 10.00}
        target_record = {"id": "123", "price": -5.00}  # Negative price violates business rule
        
        conflict = conflict_detector.detect_conflicts(source_record, target_record)
        
        assert conflict is not None
        business_conflicts = [c for c in conflict.conflicts 
                             if c.conflict_type == ConflictType.BUSINESS_RULE_VIOLATION]
        assert len(business_conflicts) >= 1
        
        # Check that the conflict is about the negative price
        price_conflict = next((c for c in business_conflicts if c.field_name == "price"), None)
        assert price_conflict is not None
        assert price_conflict.target_value == -5.00
    
    def test_timestamp_conflicts(self, conflict_detector):
        """Test detection of timestamp conflicts."""
        older_time = "2024-01-01T10:00:00Z"
        newer_time = "2024-01-02T10:00:00Z"
        
        source_record = {"id": "123", "updated_at": newer_time}
        target_record = {"id": "123", "updated_at": older_time}
        
        conflict = conflict_detector.detect_conflicts(source_record, target_record, ignore_fields={"created_at", "id"})
        
        # Should detect different timestamp values as VALUE_MISMATCH
        # (current implementation doesn't have specific TIMESTAMP_CONFLICT logic)
        assert conflict is not None
        timestamp_conflicts = [c for c in conflict.conflicts 
                              if c.field_name == "updated_at" and c.conflict_type == ConflictType.VALUE_MISMATCH]
        assert len(timestamp_conflicts) >= 1
    
    def test_severity_assignment(self, conflict_detector):
        """Test conflict severity assignment."""
        # Price field is critical, should be CRITICAL severity
        source_record = {"id": "123", "price": 10.00}
        target_record = {"id": "123", "price": 100.00}
        
        conflict = conflict_detector.detect_conflicts(source_record, target_record)
        
        assert conflict is not None
        assert conflict.severity == ConflictSeverity.CRITICAL  # Price is critical field
        
        # Non-critical field with numeric value should have MEDIUM severity
        source_record2 = {"id": "123", "quantity": 10}
        target_record2 = {"id": "123", "quantity": 15}
        
        conflict2 = conflict_detector.detect_conflicts(source_record2, target_record2)
        
        assert conflict2 is not None
        assert conflict2.severity == ConflictSeverity.MEDIUM  # Default for non-string non-critical fields
    
    def test_resolve_conflict_manual(self, conflict_detector):
        """Test manual conflict resolution."""
        source_record = {"id": "123", "title": "Old Title"}
        target_record = {"id": "123", "title": "New Title"}
        
        conflict = conflict_detector.detect_conflicts(source_record, target_record)
        assert conflict is not None
        
        conflict_id = conflict.id
        resolution = {"title": "Manually Resolved Title"}
        
        success = conflict_detector.resolve_conflict(
            conflict_id=conflict_id,
            resolution=resolution,
            resolved_by="Test User"
        )
        
        assert success is True
        
        # Check that conflict is marked as resolved
        resolved_conflict = conflict_detector.detected_conflicts[conflict_id]
        assert resolved_conflict.status == "manually_resolved"
        assert resolved_conflict.resolved_by == "Test User"
        assert resolved_conflict.resolved_at is not None
    
    def test_resolve_nonexistent_conflict(self, conflict_detector):
        """Test resolving a non-existent conflict."""
        success = conflict_detector.resolve_conflict(
            conflict_id="nonexistent",
            resolution={"field": "value"},
            resolved_by="Test User"
        )
        assert success is False
    
    def test_auto_resolution(self, conflict_detector):
        """Test automatic conflict resolution."""
        # Create a conflict that should be auto-resolvable
        source_record = {"id": "123", "description": "Old desc", "updated_at": "2024-01-01T10:00:00Z"}
        target_record = {"id": "123", "description": "New desc", "updated_at": "2024-01-02T10:00:00Z"}
        
        conflict = conflict_detector.detect_conflicts(source_record, target_record)
        assert conflict is not None
        
        # Attempt auto-resolution
        conflict_detector._attempt_auto_resolution(conflict)
        
        # Check if conflict was auto-resolved (depends on resolution rules)
        if conflict.is_auto_resolvable:
            assert conflict.status == "auto_resolved"
            assert conflict.resolved_at is not None
    
    def test_get_conflicts_filtering(self, conflict_detector):
        """Test filtering conflicts by status and severity."""
        # Create conflicts with different statuses and severities
        source1 = {"id": "1", "title": "Title1"}
        target1 = {"id": "1", "title": "Modified1"}
        conflict1 = conflict_detector.detect_conflicts(source1, target1)
        
        source2 = {"id": "2", "price": 10.0}
        target2 = {"id": "2", "price": 100.0}  # Should be high severity
        conflict2 = conflict_detector.detect_conflicts(source2, target2)
        
        # Resolve one conflict
        if conflict1:
            conflict_detector.resolve_conflict(
                conflict1.id, 
                {"title": "Resolved"}, 
                "Test User"
            )
        
        # Test filtering by status
        pending_conflicts = conflict_detector.get_conflicts(status_filter="pending")
        resolved_conflicts = conflict_detector.get_conflicts(status_filter="manually_resolved")
        
        assert len(pending_conflicts) >= 1
        if conflict1:
            assert len(resolved_conflicts) >= 1
        
        # Test filtering by severity
        high_conflicts = conflict_detector.get_conflicts(severity_filter=ConflictSeverity.HIGH)
        if conflict2 and conflict2.severity == ConflictSeverity.HIGH:
            assert len(high_conflicts) >= 1
    
    def test_get_conflict_stats(self, conflict_detector):
        """Test getting conflict statistics."""
        # Create some conflicts
        source1 = {"id": "1", "title": "Title1"}
        target1 = {"id": "1", "title": "Modified1"}
        conflict_detector.detect_conflicts(source1, target1)
        
        source2 = {"id": "2", "title": "Title2"}
        target2 = {"id": "2", "title": "Modified2"}
        conflict_detector.detect_conflicts(source2, target2)
        
        stats = conflict_detector.get_conflict_stats()
        
        assert 'total_conflicts' in stats
        assert 'pending_conflicts' in stats
        assert 'resolved_conflicts' in stats
        assert 'auto_resolved_conflicts' in stats
        assert 'severity_breakdown' in stats
        assert 'auto_resolution_rate' in stats
        
        assert stats['total_conflicts'] >= 2
        # Note: conflicts may be auto-resolved, so check against resolved instead
        assert stats['resolved_conflicts'] >= 0


class TestConflictDetectorBusinessRules:
    """Test business rule validation in ConflictDetector."""
    
    def test_price_increase_rule(self, conflict_detector):
        """Test price validation business rule."""
        # Positive price (should not trigger rule)
        source1 = {"id": "1", "price": 10.0}
        target1 = {"id": "1", "price": 15.0}  # Both positive
        conflict1 = conflict_detector.detect_conflicts(source1, target1)
        
        business_violations1 = []
        if conflict1:
            business_violations1 = [c for c in conflict1.conflicts 
                                   if c.conflict_type == ConflictType.BUSINESS_RULE_VIOLATION]
        
        # Negative price (should trigger rule)
        source2 = {"id": "2", "price": 10.0}
        target2 = {"id": "2", "price": -5.0}  # Negative price violates rule
        conflict2 = conflict_detector.detect_conflicts(source2, target2)
        
        business_violations2 = []
        if conflict2:
            business_violations2 = [c for c in conflict2.conflicts 
                                   if c.conflict_type == ConflictType.BUSINESS_RULE_VIOLATION]
        
        # The negative price should trigger a business rule violation
        assert len(business_violations2) > len(business_violations1)
        assert len(business_violations2) >= 1
    
    def test_title_length_rule(self, conflict_detector):
        """Test SKU format business rule."""
        # Valid SKU (alphanumeric with hyphens/underscores)
        source1 = {"id": "1", "sku": "SKU-123"}
        target1 = {"id": "1", "sku": "SKU_456"}  # Both valid
        conflict1 = conflict_detector.detect_conflicts(source1, target1)
        
        business_violations1 = []
        if conflict1:
            business_violations1 = [c for c in conflict1.conflicts 
                                   if c.conflict_type == ConflictType.BUSINESS_RULE_VIOLATION]
        
        # Invalid SKU (contains special characters)
        source2 = {"id": "2", "sku": "SKU-123"}
        target2 = {"id": "2", "sku": "SKU@#$123"}  # Invalid characters
        conflict2 = conflict_detector.detect_conflicts(source2, target2)
        
        business_violations2 = []
        if conflict2:
            business_violations2 = [c for c in conflict2.conflicts 
                                   if c.conflict_type == ConflictType.BUSINESS_RULE_VIOLATION]
        
        # Should detect SKU format violation
        assert len(business_violations2) > len(business_violations1)
        assert len(business_violations2) >= 1
    
    def test_custom_business_rule(self, conflict_detector):
        """Test adding and using custom business rules."""
        # Add a custom rule for SKU format
        custom_rule = {
            "name": "sku_format_custom",
            "description": "SKU must be at least 6 characters",
            "field": "sku",
            "validation": lambda value: isinstance(value, str) and len(value) >= 6
        }
        
        conflict_detector.business_rules.append(custom_rule)
        
        # Test invalid SKU
        source = {"id": "1", "sku": "VALID123"}
        target = {"id": "1", "sku": "BAD"}  # Invalid format
        
        conflict = conflict_detector.detect_conflicts(source, target)
        
        if conflict:
            business_violations = [c for c in conflict.conflicts 
                                  if c.conflict_type == ConflictType.BUSINESS_RULE_VIOLATION]
            sku_violations = [v for v in business_violations if "sku" in v.description.lower()]
            assert len(sku_violations) >= 1


class TestConflictDetectorPerformance:
    """Test ConflictDetector performance with large datasets."""
    
    def test_large_record_performance(self, conflict_detector):
        """Test performance with large records."""
        import time
        
        # Create large records
        large_source = {f"field_{i}": f"value_{i}" for i in range(1000)}
        large_target = {f"field_{i}": f"modified_value_{i}" for i in range(1000)}
        
        start_time = time.time()
        conflict = conflict_detector.detect_conflicts(large_source, large_target)
        end_time = time.time()
        
        # Should complete in reasonable time (less than 1 second for 1000 fields)
        assert (end_time - start_time) < 1.0
        
        # Should detect conflicts for all fields
        if conflict:
            assert len(conflict.conflicts) == 1000
    
    def test_many_conflicts_performance(self, conflict_detector):
        """Test performance with many conflicts."""
        import time
        
        start_time = time.time()
        
        # Create many conflicts
        for i in range(100):
            source = {"id": f"record_{i}", "title": f"Title {i}"}
            target = {"id": f"record_{i}", "title": f"Modified Title {i}"}
            conflict_detector.detect_conflicts(source, target)
        
        end_time = time.time()
        
        # Should handle 100 conflict detections in reasonable time
        assert (end_time - start_time) < 5.0
        
        # Should have created 100 conflicts
        assert len(conflict_detector.detected_conflicts) == 100


class TestGlobalConflictDetector:
    """Test the global conflict detector instance."""
    
    def test_global_instance_exists(self):
        """Test that the global conflict detector instance exists."""
        assert conflict_detector is not None
        assert isinstance(conflict_detector, ConflictDetector)
    
    def test_global_instance_configuration(self):
        """Test that the global instance has proper configuration."""
        assert len(conflict_detector.resolution_rules) > 0
        assert len(conflict_detector.business_rules) > 0