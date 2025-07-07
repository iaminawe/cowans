"""
Staging Data Service

Manages staging data for imports with conflict resolution, batch operations,
and transaction management for import operations.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from models import Product, Category, ProductStatus, SyncStatus
from repositories import ProductRepository, CategoryRepository


class ImportMode(Enum):
    """Import modes for handling existing products."""
    IMPORT_NEW = "import_new"
    UPDATE_EXISTING = "update_existing"
    UPSERT = "upsert"


class StagingStatus(Enum):
    """Status of staged records."""
    PENDING = "pending"
    VALIDATED = "validated"
    READY = "ready"
    CONFLICT = "conflict"
    ERROR = "error"


class ConflictStrategy(Enum):
    """Strategy for handling conflicts."""
    SKIP = "skip"
    OVERWRITE = "overwrite"
    MERGE = "merge"
    CREATE_NEW = "create_new"
    MANUAL = "manual"


@dataclass
class StagedRecord:
    """A record staged for import."""
    source_data: Dict[str, Any]
    transformed_data: Dict[str, Any]
    metafields: List[Dict[str, Any]] = field(default_factory=list)
    status: StagingStatus = StagingStatus.PENDING
    existing_product_id: Optional[int] = None
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StagingBatch:
    """A batch of staged records."""
    batch_id: str
    records: List[StagedRecord]
    created_at: datetime = field(default_factory=datetime.now)
    total_records: int = 0
    ready_records: int = 0
    conflict_records: int = 0
    error_records: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class StagingDataService:
    """
    Service for staging import data with conflict resolution and validation.
    
    Features:
    - Stage data for batch processing
    - Detect and resolve conflicts
    - Validate data integrity
    - Manage staging transactions
    - Optimize batch operations
    """
    
    def __init__(self, session: Session, logger: Optional[logging.Logger] = None):
        """Initialize the staging service."""
        self.session = session
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize repositories
        self.product_repo = ProductRepository(session)
        self.category_repo = CategoryRepository(session)
        
        # Staging cache
        self._staging_batches: Dict[str, StagingBatch] = {}
    
    def prepare_import_batch(
        self,
        transformed_data: List[Dict[str, Any]],
        mode: ImportMode = ImportMode.UPSERT,
        create_missing_categories: bool = True,
        skip_duplicates: bool = True,
        conflict_strategy: ConflictStrategy = ConflictStrategy.MERGE
    ) -> List[Dict[str, Any]]:
        """
        Prepare a batch of transformed data for import.
        
        Args:
            transformed_data: List of transformed product data
            mode: Import mode
            create_missing_categories: Whether to create missing categories
            skip_duplicates: Whether to skip duplicate records
            conflict_strategy: Strategy for resolving conflicts
            
        Returns:
            List of staged records ready for import
        """
        try:
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.logger.info(f"Preparing import batch {batch_id} with {len(transformed_data)} records")
            
            # Create staging batch
            staged_records = []
            
            for i, record_data in enumerate(transformed_data):
                try:
                    staged_record = self._stage_single_record(
                        record_data,
                        mode,
                        create_missing_categories,
                        skip_duplicates,
                        conflict_strategy
                    )
                    staged_records.append(staged_record)
                    
                except Exception as e:
                    self.logger.error(f"Failed to stage record {i}: {str(e)}")
                    # Create error record
                    error_record = StagedRecord(
                        source_data=record_data,
                        transformed_data={},
                        status=StagingStatus.ERROR,
                        errors=[f"Staging error: {str(e)}"]
                    )
                    staged_records.append(error_record)
            
            # Create staging batch
            staging_batch = StagingBatch(
                batch_id=batch_id,
                records=staged_records,
                total_records=len(staged_records)
            )
            
            # Calculate statistics
            self._update_batch_statistics(staging_batch)
            
            # Cache batch
            self._staging_batches[batch_id] = staging_batch
            
            # Convert to list for import
            ready_records = []
            for record in staged_records:
                if record.status in [StagingStatus.READY, StagingStatus.VALIDATED]:
                    # Convert to import format
                    import_record = record.transformed_data.copy()
                    import_record['_staging_metadata'] = {
                        'existing_product_id': record.existing_product_id,
                        'conflicts': record.conflicts,
                        'metafields': record.metafields,
                        'status': record.status.value
                    }
                    ready_records.append(import_record)
            
            self.logger.info(f"Batch {batch_id} prepared: {len(ready_records)} ready records")
            return ready_records
            
        except Exception as e:
            self.logger.error(f"Failed to prepare import batch: {str(e)}")
            raise
    
    def _stage_single_record(
        self,
        record_data: Dict[str, Any],
        mode: ImportMode,
        create_missing_categories: bool,
        skip_duplicates: bool,
        conflict_strategy: ConflictStrategy
    ) -> StagedRecord:
        """Stage a single record for import."""
        staged_record = StagedRecord(
            source_data=record_data.copy(),
            transformed_data=record_data.copy()
        )
        
        # Extract metafields if present
        if '_metafields' in record_data:
            staged_record.metafields = record_data.pop('_metafields')
        
        # Check for existing product
        existing_product = self._find_existing_product(record_data)
        if existing_product:
            staged_record.existing_product_id = existing_product.id
            
            # Handle based on import mode
            if mode == ImportMode.IMPORT_NEW:
                if skip_duplicates:
                    staged_record.status = StagingStatus.ERROR
                    staged_record.errors.append(f"Product with SKU {record_data.get('sku')} already exists")
                    return staged_record
                else:
                    # Create new with modified SKU
                    new_sku = self._generate_unique_sku(record_data.get('sku'))
                    staged_record.transformed_data['sku'] = new_sku
                    staged_record.warnings.append(f"SKU changed from {record_data.get('sku')} to {new_sku}")
            
            elif mode == ImportMode.UPDATE_EXISTING:
                # Detect conflicts
                conflicts = self._detect_conflicts(record_data, existing_product)
                staged_record.conflicts = conflicts
                
                if conflicts and conflict_strategy == ConflictStrategy.SKIP:
                    staged_record.status = StagingStatus.CONFLICT
                    return staged_record
                elif conflicts:
                    # Resolve conflicts
                    resolved_data = self._resolve_conflicts(
                        record_data, 
                        existing_product, 
                        conflicts, 
                        conflict_strategy
                    )
                    staged_record.transformed_data.update(resolved_data)
            
            elif mode == ImportMode.UPSERT:
                # Merge with existing data
                merged_data = self._merge_with_existing(record_data, existing_product)
                staged_record.transformed_data.update(merged_data)
        
        # Validate category
        category_validation = self._validate_category(
            staged_record.transformed_data, 
            create_missing_categories
        )
        
        if not category_validation['valid']:
            if category_validation['can_create']:
                # Create category
                new_category_id = self._create_category(category_validation['category_data'])
                staged_record.transformed_data['category_id'] = new_category_id
                staged_record.warnings.append(f"Created new category: {category_validation['category_data']['name']}")
            else:
                staged_record.status = StagingStatus.ERROR
                staged_record.errors.append(category_validation['error'])
                return staged_record
        
        # Validate required fields
        validation_result = self._validate_required_fields(staged_record.transformed_data)
        if not validation_result['valid']:
            staged_record.status = StagingStatus.ERROR
            staged_record.errors.extend(validation_result['errors'])
            return staged_record
        
        # Final validation passed
        staged_record.status = StagingStatus.READY
        return staged_record
    
    def _find_existing_product(self, record_data: Dict[str, Any]) -> Optional[Product]:
        """Find existing product by SKU or other identifiers."""
        sku = record_data.get('sku')
        if not sku:
            return None
        
        # Try exact SKU match first
        product = self.product_repo.get_by_sku(sku)
        if product:
            return product
        
        # Try MPN match
        mpn = record_data.get('manufacturer_part_number')
        if mpn:
            product = self.product_repo.get_by_mpn(mpn)
            if product:
                return product
        
        # Try Shopify ID match
        shopify_id = record_data.get('shopify_product_id')
        if shopify_id:
            product = self.product_repo.get_by_shopify_id(shopify_id)
            if product:
                return product
        
        return None
    
    def _generate_unique_sku(self, base_sku: str) -> str:
        """Generate unique SKU by appending suffix."""
        if not base_sku:
            base_sku = "PRODUCT"
        
        counter = 1
        while True:
            new_sku = f"{base_sku}_{counter:03d}"
            if not self.product_repo.get_by_sku(new_sku):
                return new_sku
            counter += 1
            
            # Safety check
            if counter > 999:
                raise ValueError(f"Could not generate unique SKU for {base_sku}")
    
    def _detect_conflicts(
        self,
        new_data: Dict[str, Any],
        existing_product: Product
    ) -> List[Dict[str, Any]]:
        """Detect conflicts between new and existing data."""
        conflicts = []
        
        # Fields to check for conflicts
        conflict_fields = {
            'name': 'Product name',
            'price': 'Price',
            'description': 'Description',
            'brand': 'Brand',
            'manufacturer': 'Manufacturer',
            'weight': 'Weight',
            'inventory_quantity': 'Inventory quantity'
        }
        
        for field, display_name in conflict_fields.items():
            new_value = new_data.get(field)
            existing_value = getattr(existing_product, field, None)
            
            # Skip if either value is None or empty
            if not new_value or not existing_value:
                continue
            
            # Compare values
            if str(new_value).strip() != str(existing_value).strip():
                conflict = {
                    'field': field,
                    'display_name': display_name,
                    'new_value': new_value,
                    'existing_value': existing_value,
                    'severity': self._assess_conflict_severity(field, new_value, existing_value)
                }
                conflicts.append(conflict)
        
        return conflicts
    
    def _assess_conflict_severity(self, field: str, new_value: Any, existing_value: Any) -> str:
        """Assess the severity of a conflict."""
        # Critical fields
        if field in ['price', 'sku']:
            return 'critical'
        
        # Important fields
        if field in ['name', 'description', 'brand']:
            # Check similarity for text fields
            if isinstance(new_value, str) and isinstance(existing_value, str):
                from difflib import SequenceMatcher
                similarity = SequenceMatcher(None, new_value.lower(), existing_value.lower()).ratio()
                if similarity < 0.7:
                    return 'high'
                elif similarity < 0.9:
                    return 'medium'
                else:
                    return 'low'
            return 'medium'
        
        # Other fields
        return 'low'
    
    def _resolve_conflicts(
        self,
        new_data: Dict[str, Any],
        existing_product: Product,
        conflicts: List[Dict[str, Any]],
        strategy: ConflictStrategy
    ) -> Dict[str, Any]:
        """Resolve conflicts using the specified strategy."""
        resolved_data = {}
        
        for conflict in conflicts:
            field = conflict['field']
            new_value = conflict['new_value']
            existing_value = conflict['existing_value']
            
            if strategy == ConflictStrategy.OVERWRITE:
                resolved_data[field] = new_value
            
            elif strategy == ConflictStrategy.MERGE:
                # Field-specific merge logic
                if field in ['description'] and isinstance(new_value, str) and isinstance(existing_value, str):
                    # Merge descriptions
                    if len(new_value) > len(existing_value):
                        resolved_data[field] = new_value
                    else:
                        resolved_data[field] = existing_value
                elif field == 'price':
                    # Use higher price for safety
                    resolved_data[field] = max(float(new_value), float(existing_value))
                elif field == 'inventory_quantity':
                    # Use higher inventory
                    resolved_data[field] = max(int(new_value), int(existing_value))
                else:
                    # Default to new value
                    resolved_data[field] = new_value
            
            elif strategy == ConflictStrategy.CREATE_NEW:
                # Keep existing, will create new product
                pass
            
            # Skip strategy - don't include conflicting field
        
        return resolved_data
    
    def _merge_with_existing(
        self,
        new_data: Dict[str, Any],
        existing_product: Product
    ) -> Dict[str, Any]:
        """Merge new data with existing product data."""
        merged_data = {}
        
        # Merge strategy by field type
        merge_rules = {
            'name': 'prefer_longer',
            'description': 'prefer_longer',
            'price': 'prefer_new',
            'compare_at_price': 'prefer_new',
            'brand': 'prefer_existing',
            'manufacturer': 'prefer_existing',
            'weight': 'prefer_new',
            'inventory_quantity': 'prefer_new',
            'featured_image_url': 'prefer_new_if_exists'
        }
        
        for field, rule in merge_rules.items():
            new_value = new_data.get(field)
            existing_value = getattr(existing_product, field, None)
            
            if rule == 'prefer_new':
                if new_value is not None:
                    merged_data[field] = new_value
            
            elif rule == 'prefer_existing':
                if existing_value is not None:
                    merged_data[field] = existing_value
                elif new_value is not None:
                    merged_data[field] = new_value
            
            elif rule == 'prefer_longer':
                if new_value and existing_value:
                    if len(str(new_value)) > len(str(existing_value)):
                        merged_data[field] = new_value
                    else:
                        merged_data[field] = existing_value
                elif new_value:
                    merged_data[field] = new_value
                elif existing_value:
                    merged_data[field] = existing_value
            
            elif rule == 'prefer_new_if_exists':
                if new_value and str(new_value).strip():
                    merged_data[field] = new_value
                elif existing_value:
                    merged_data[field] = existing_value
        
        return merged_data
    
    def _validate_category(
        self,
        record_data: Dict[str, Any],
        create_missing_categories: bool
    ) -> Dict[str, Any]:
        """Validate product category."""
        category_id = record_data.get('category_id')
        
        if not category_id:
            # Try to determine category from product type
            product_type = record_data.get('product_type') or record_data.get('Type')
            if product_type and create_missing_categories:
                return {
                    'valid': False,
                    'can_create': True,
                    'category_data': {
                        'name': product_type,
                        'slug': self._create_slug(product_type),
                        'description': f'Auto-created category for {product_type}',
                        'is_active': True
                    }
                }
            else:
                return {
                    'valid': False,
                    'can_create': False,
                    'error': 'No category specified and cannot create missing categories'
                }
        
        # Check if category exists
        category = self.category_repo.get(category_id)
        if not category:
            return {
                'valid': False,
                'can_create': False,
                'error': f'Category with ID {category_id} does not exist'
            }
        
        return {'valid': True}
    
    def _create_category(self, category_data: Dict[str, Any]) -> int:
        """Create a new category."""
        category = self.category_repo.create(**category_data)
        self.session.flush()
        return category.id
    
    def _create_slug(self, name: str) -> str:
        """Create URL-friendly slug from name."""
        import re
        slug = name.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')
    
    def _validate_required_fields(self, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate required fields are present."""
        required_fields = ['sku', 'name', 'price']
        errors = []
        
        for field in required_fields:
            value = record_data.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                errors.append(f"Required field '{field}' is missing or empty")
        
        # Validate data types
        if 'price' in record_data:
            try:
                float(record_data['price'])
            except (ValueError, TypeError):
                errors.append("Price must be a valid number")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _update_batch_statistics(self, batch: StagingBatch) -> None:
        """Update batch statistics."""
        batch.total_records = len(batch.records)
        batch.ready_records = sum(1 for r in batch.records if r.status == StagingStatus.READY)
        batch.conflict_records = sum(1 for r in batch.records if r.status == StagingStatus.CONFLICT)
        batch.error_records = sum(1 for r in batch.records if r.status == StagingStatus.ERROR)
    
    def get_staging_batch(self, batch_id: str) -> Optional[StagingBatch]:
        """Get staging batch by ID."""
        return self._staging_batches.get(batch_id)
    
    def get_batch_summary(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of staging batch."""
        batch = self.get_staging_batch(batch_id)
        if not batch:
            return None
        
        return {
            'batch_id': batch.batch_id,
            'created_at': batch.created_at.isoformat(),
            'total_records': batch.total_records,
            'ready_records': batch.ready_records,
            'conflict_records': batch.conflict_records,
            'error_records': batch.error_records,
            'success_rate': (batch.ready_records / batch.total_records) * 100 if batch.total_records > 0 else 0
        }
    
    def clear_staging_batch(self, batch_id: str) -> bool:
        """Clear staging batch from memory."""
        if batch_id in self._staging_batches:
            del self._staging_batches[batch_id]
            return True
        return False