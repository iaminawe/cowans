"""
Enhanced Staging Service for Sync Operations

This service provides high-level methods for managing staged changes,
conflict resolution, and sync operations.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from models import Product, Category
from staging_models import (
    StagedProductChange, StagedCategoryChange, SyncVersion,
    SyncBatch, SyncApprovalRule, SyncRollback,
    StagedChangeStatus, SyncDirection, ChangeType
)
from repositories import ProductRepository, CategoryRepository


@dataclass
class StagingMetrics:
    """Metrics for staging operations."""
    total_changes: int = 0
    pending_changes: int = 0
    approved_changes: int = 0
    rejected_changes: int = 0
    applied_changes: int = 0
    conflicts: int = 0
    auto_approved: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_changes': self.total_changes,
            'pending_changes': self.pending_changes,
            'approved_changes': self.approved_changes,
            'rejected_changes': self.rejected_changes,
            'applied_changes': self.applied_changes,
            'conflicts': self.conflicts,
            'auto_approved': self.auto_approved,
            'approval_rate': (self.approved_changes / self.total_changes * 100) if self.total_changes > 0 else 0,
            'conflict_rate': (self.conflicts / self.total_changes * 100) if self.total_changes > 0 else 0
        }


class ConflictResolutionStrategy(Enum):
    """Strategies for resolving conflicts."""
    PREFER_LOCAL = "prefer_local"
    PREFER_REMOTE = "prefer_remote"
    MERGE_NEWEST = "merge_newest"
    MERGE_CUSTOM = "merge_custom"
    MANUAL = "manual"


class EnhancedStagingService:
    """
    Enhanced service for managing staging operations with advanced features:
    - Intelligent conflict detection and resolution
    - Batch processing with transaction management
    - Version tracking and rollback support
    - Performance optimization
    - Real-time metrics
    """
    
    def __init__(self, session: Session, logger: Optional[logging.Logger] = None):
        """Initialize the service."""
        self.session = session
        self.logger = logger or logging.getLogger(__name__)
        self.product_repo = ProductRepository(session)
        self.category_repo = CategoryRepository(session)
    
    def get_staging_metrics(self, batch_id: Optional[str] = None) -> StagingMetrics:
        """Get metrics for staging operations."""
        metrics = StagingMetrics()
        
        query = self.session.query(StagedProductChange)
        if batch_id:
            query = query.filter(StagedProductChange.batch_id == batch_id)
        
        # Get counts by status
        status_counts = query.with_entities(
            StagedProductChange.status,
            func.count(StagedProductChange.id)
        ).group_by(StagedProductChange.status).all()
        
        for status, count in status_counts:
            metrics.total_changes += count
            if status == StagedChangeStatus.PENDING.value:
                metrics.pending_changes = count
            elif status == StagedChangeStatus.APPROVED.value:
                metrics.approved_changes = count
            elif status == StagedChangeStatus.REJECTED.value:
                metrics.rejected_changes = count
            elif status == StagedChangeStatus.APPLIED.value:
                metrics.applied_changes = count
        
        # Get conflict count
        metrics.conflicts = query.filter(
            StagedProductChange.has_conflicts == True
        ).count()
        
        # Get auto-approved count
        metrics.auto_approved = query.filter(
            StagedProductChange.auto_approved == True
        ).count()
        
        return metrics
    
    def detect_conflicts_advanced(
        self,
        product_id: int,
        proposed_changes: Dict[str, Any],
        check_related: bool = True
    ) -> Dict[str, Any]:
        """
        Advanced conflict detection with related entity checks.
        
        Args:
            product_id: Product ID to check
            proposed_changes: Proposed changes
            check_related: Whether to check related entities
            
        Returns:
            Dict with conflict information
        """
        conflicts = {
            'has_conflicts': False,
            'conflict_fields': [],
            'related_conflicts': [],
            'severity': 'none'
        }
        
        # Get current product
        product = self.product_repo.get(product_id)
        if not product:
            return conflicts
        
        # Check for pending changes on same product
        pending_changes = self.session.query(StagedProductChange).filter(
            StagedProductChange.product_id == product_id,
            StagedProductChange.status.in_([
                StagedChangeStatus.PENDING.value,
                StagedChangeStatus.APPROVED.value
            ])
        ).all()
        
        if pending_changes:
            conflicts['has_conflicts'] = True
            conflicts['related_conflicts'].append({
                'type': 'pending_changes',
                'count': len(pending_changes),
                'changes': [c.change_id for c in pending_changes]
            })
            conflicts['severity'] = 'high'
        
        # Check for recent modifications
        if product.updated_at > datetime.utcnow() - timedelta(minutes=5):
            conflicts['has_conflicts'] = True
            conflicts['related_conflicts'].append({
                'type': 'recent_modification',
                'timestamp': product.updated_at.isoformat(),
                'age_minutes': (datetime.utcnow() - product.updated_at).total_seconds() / 60
            })
            if conflicts['severity'] != 'high':
                conflicts['severity'] = 'medium'
        
        # Check field-level conflicts
        critical_fields = ['sku', 'price', 'inventory_quantity']
        for field in critical_fields:
            if field in proposed_changes:
                current_value = getattr(product, field, None)
                new_value = proposed_changes[field]
                
                # Check for significant changes
                if field == 'price' and current_value and new_value:
                    price_change_pct = abs(new_value - current_value) / current_value * 100
                    if price_change_pct > 20:
                        conflicts['has_conflicts'] = True
                        conflicts['conflict_fields'].append({
                            'field': field,
                            'current': current_value,
                            'proposed': new_value,
                            'change_percentage': price_change_pct,
                            'severity': 'high' if price_change_pct > 50 else 'medium'
                        })
                        conflicts['severity'] = 'high'
        
        # Check related entities if requested
        if check_related and product.category_id:
            # Check if category is being modified
            category_changes = self.session.query(StagedCategoryChange).filter(
                StagedCategoryChange.category_id == product.category_id,
                StagedCategoryChange.status == StagedChangeStatus.PENDING.value
            ).count()
            
            if category_changes > 0:
                conflicts['has_conflicts'] = True
                conflicts['related_conflicts'].append({
                    'type': 'category_changes',
                    'category_id': product.category_id,
                    'count': category_changes
                })
                if conflicts['severity'] == 'none':
                    conflicts['severity'] = 'low'
        
        return conflicts
    
    def resolve_conflicts_intelligent(
        self,
        staged_change: StagedProductChange,
        strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.MERGE_NEWEST,
        custom_resolver: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Intelligently resolve conflicts based on strategy.
        
        Args:
            staged_change: The staged change with conflicts
            strategy: Resolution strategy to use
            custom_resolver: Optional custom resolver function
            
        Returns:
            Resolved data dictionary
        """
        if not staged_change.has_conflicts:
            return staged_change.proposed_data
        
        resolved_data = {}
        current_data = staged_change.current_data or {}
        proposed_data = staged_change.proposed_data or {}
        
        if strategy == ConflictResolutionStrategy.PREFER_LOCAL:
            # Keep current data for conflicting fields
            resolved_data = proposed_data.copy()
            for field in staged_change.conflict_fields or []:
                if field in current_data:
                    resolved_data[field] = current_data[field]
        
        elif strategy == ConflictResolutionStrategy.PREFER_REMOTE:
            # Use all proposed data
            resolved_data = proposed_data.copy()
        
        elif strategy == ConflictResolutionStrategy.MERGE_NEWEST:
            # Use newest data based on timestamps
            resolved_data = proposed_data.copy()
            
            # Get product to check update times
            if staged_change.product_id:
                product = self.product_repo.get(staged_change.product_id)
                if product and product.updated_at > staged_change.created_at:
                    # Local is newer, keep some fields
                    preserve_fields = ['price', 'inventory_quantity', 'status']
                    for field in preserve_fields:
                        if field in current_data:
                            resolved_data[field] = current_data[field]
        
        elif strategy == ConflictResolutionStrategy.MERGE_CUSTOM and custom_resolver:
            # Use custom resolver
            resolved_data = custom_resolver(current_data, proposed_data, staged_change.conflict_fields)
        
        else:
            # Default to manual resolution
            resolved_data = proposed_data.copy()
            staged_change.status = StagedChangeStatus.PENDING.value
            staged_change.review_notes = "Manual resolution required due to conflicts"
        
        # Update staged change with resolution
        staged_change.conflict_resolution = {
            'strategy': strategy.value,
            'resolved_at': datetime.utcnow().isoformat(),
            'resolved_fields': list(resolved_data.keys())
        }
        
        return resolved_data
    
    def create_approval_rules_default(self) -> List[SyncApprovalRule]:
        """Create default approval rules."""
        rules = [
            # Critical price changes require approval
            SyncApprovalRule(
                rule_name="Critical Price Changes",
                rule_description="Require approval for price changes over 20%",
                entity_type="product",
                change_type="update",
                field_patterns=["price"],
                value_thresholds={"price_change_percentage": 20},
                requires_approval=True,
                auto_approve_conditions={"max_price_change": 20},
                priority=1
            ),
            
            # Inventory reductions require approval
            SyncApprovalRule(
                rule_name="Inventory Reduction",
                rule_description="Require approval for significant inventory reductions",
                entity_type="product",
                change_type="update",
                field_patterns=["inventory_quantity"],
                value_thresholds={"inventory_reduction_percentage": 50},
                requires_approval=True,
                priority=2
            ),
            
            # Auto-approve minor updates
            SyncApprovalRule(
                rule_name="Minor Updates Auto-Approval",
                rule_description="Auto-approve minor updates without conflicts",
                entity_type="product",
                change_type="update",
                requires_approval=True,
                auto_approve_conditions={
                    "no_conflicts": True,
                    "exclude_fields": ["price", "sku", "inventory_quantity"],
                    "max_fields_changed": 3
                },
                priority=3
            ),
            
            # New products require approval
            SyncApprovalRule(
                rule_name="New Product Creation",
                rule_description="Require approval for new product creation",
                entity_type="product",
                change_type="create",
                requires_approval=True,
                priority=1
            )
        ]
        
        for rule in rules:
            rule.is_active = True
            rule.approval_level = 1
            self.session.add(rule)
        
        self.session.flush()
        return rules
    
    def process_batch_intelligent(
        self,
        batch_id: str,
        auto_resolve_conflicts: bool = True,
        conflict_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.MERGE_NEWEST
    ) -> Dict[str, Any]:
        """
        Process a batch with intelligent conflict resolution and approval.
        
        Args:
            batch_id: Batch ID to process
            auto_resolve_conflicts: Whether to auto-resolve conflicts
            conflict_strategy: Strategy for conflict resolution
            
        Returns:
            Processing results
        """
        results = {
            'batch_id': batch_id,
            'processed': 0,
            'approved': 0,
            'conflicts_resolved': 0,
            'errors': []
        }
        
        # Get all pending changes in batch
        changes = self.session.query(StagedProductChange).filter(
            StagedProductChange.batch_id == batch_id,
            StagedProductChange.status == StagedChangeStatus.PENDING.value
        ).all()
        
        for change in changes:
            try:
                results['processed'] += 1
                
                # Resolve conflicts if needed
                if change.has_conflicts and auto_resolve_conflicts:
                    resolved_data = self.resolve_conflicts_intelligent(
                        change, conflict_strategy
                    )
                    change.proposed_data = resolved_data
                    change.has_conflicts = False
                    results['conflicts_resolved'] += 1
                
                # Check approval rules
                if self.check_auto_approval_advanced(change):
                    change.status = StagedChangeStatus.APPROVED.value
                    change.auto_approved = True
                    change.reviewed_at = datetime.utcnow()
                    results['approved'] += 1
                
            except Exception as e:
                self.logger.error(f"Failed to process change {change.change_id}: {str(e)}")
                results['errors'].append({
                    'change_id': change.change_id,
                    'error': str(e)
                })
        
        self.session.flush()
        return results
    
    def check_auto_approval_advanced(self, change: StagedProductChange) -> bool:
        """
        Advanced auto-approval check with multiple criteria.
        
        Args:
            change: Staged change to check
            
        Returns:
            Whether change can be auto-approved
        """
        # Never auto-approve changes with unresolved conflicts
        if change.has_conflicts:
            return False
        
        # Get applicable rules
        rules = self.session.query(SyncApprovalRule).filter(
            SyncApprovalRule.is_active == True,
            or_(
                SyncApprovalRule.entity_type == 'all',
                SyncApprovalRule.entity_type == 'product'
            ),
            or_(
                SyncApprovalRule.change_type == 'all',
                SyncApprovalRule.change_type == change.change_type
            )
        ).order_by(SyncApprovalRule.priority.asc()).all()
        
        # Check each rule
        for rule in rules:
            if not rule.requires_approval:
                continue
            
            # Check if rule applies to changed fields
            if rule.field_patterns:
                changed_fields = set(change.field_changes.keys()) if change.field_changes else set()
                rule_fields = set(rule.field_patterns)
                if not changed_fields.intersection(rule_fields):
                    continue
            
            # Check auto-approve conditions
            if rule.auto_approve_conditions:
                conditions = rule.auto_approve_conditions
                
                # Check no conflicts requirement
                if conditions.get('no_conflicts') and change.has_conflicts:
                    return False
                
                # Check excluded fields
                if conditions.get('exclude_fields'):
                    changed_fields = set(change.field_changes.keys()) if change.field_changes else set()
                    excluded_fields = set(conditions['exclude_fields'])
                    if changed_fields.intersection(excluded_fields):
                        return False
                
                # Check max fields changed
                if conditions.get('max_fields_changed'):
                    if len(change.field_changes or {}) > conditions['max_fields_changed']:
                        return False
                
                # Check value thresholds
                if rule.value_thresholds:
                    for field, threshold in rule.value_thresholds.items():
                        if field in change.field_changes:
                            old_val = change.field_changes[field].get('old', 0)
                            new_val = change.field_changes[field].get('new', 0)
                            
                            # Calculate change percentage
                            if old_val and new_val:
                                change_pct = abs(new_val - old_val) / old_val * 100
                                if change_pct > threshold:
                                    return False
        
        # If no rules prevented approval, approve
        return True
    
    def get_rollback_candidates(
        self,
        entity_type: str = 'product',
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recently applied changes that can be rolled back."""
        # Get applied changes with versions
        changes = self.session.query(
            StagedProductChange,
            func.count(SyncVersion.id).label('version_count')
        ).join(
            SyncVersion,
            and_(
                SyncVersion.entity_type == 'product',
                SyncVersion.entity_id == StagedProductChange.product_id
            )
        ).filter(
            StagedProductChange.status == StagedChangeStatus.APPLIED.value,
            StagedProductChange.applied_at.isnot(None)
        ).group_by(
            StagedProductChange.id
        ).having(
            func.count(SyncVersion.id) > 1  # Has previous versions
        ).order_by(
            StagedProductChange.applied_at.desc()
        ).limit(limit).all()
        
        candidates = []
        for change, version_count in changes:
            candidates.append({
                'change_id': change.change_id,
                'product_id': change.product_id,
                'change_type': change.change_type,
                'applied_at': change.applied_at.isoformat(),
                'applied_by': change.applied_by,
                'version_count': version_count,
                'field_changes': change.field_changes
            })
        
        return candidates
    
    def create_smart_batch(
        self,
        name: str,
        sync_direction: SyncDirection,
        filters: Optional[Dict[str, Any]] = None
    ) -> SyncBatch:
        """
        Create a smart batch with automatic change detection.
        
        Args:
            name: Batch name
            sync_direction: Direction of sync
            filters: Optional filters for selecting changes
            
        Returns:
            Created batch
        """
        batch_id = f"smart_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        batch = SyncBatch(
            batch_id=batch_id,
            batch_name=name,
            sync_type='smart',
            sync_direction=sync_direction.value,
            status='pending',
            created_by=1,  # Should be actual user ID
            configuration=filters or {}
        )
        
        self.session.add(batch)
        self.session.flush()
        
        # Auto-detect changes based on filters
        if sync_direction == SyncDirection.PULL_FROM_SHOPIFY:
            # Detect products needing update from Shopify
            # This would integrate with Shopify API to check for updates
            pass
        elif sync_direction == SyncDirection.PUSH_TO_SHOPIFY:
            # Detect local changes to push
            # Query change tracking table for unsynced changes
            pass
        
        return batch