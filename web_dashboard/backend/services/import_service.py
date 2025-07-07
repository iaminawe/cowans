"""
Etilize Import Service

This service handles the complete import workflow from Etilize CSV files
to the database, including validation, transformation, and staging.
"""

import os
import csv
import hashlib
import uuid
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Iterator
from dataclasses import dataclass, asdict
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models import (
    EtilizeImportBatch, EtilizeStagingProduct, Product, Category,
    ImportBatchStatus, ProcessingStatus, ProductStatus
)
from repositories import ProductRepository, CategoryRepository
from database import db_session_scope

logger = logging.getLogger(__name__)

@dataclass
class ImportConfiguration:
    """Configuration for import operations."""
    batch_size: int = 100
    max_errors: int = 50
    validate_references: bool = True
    create_missing_categories: bool = False
    skip_duplicates: bool = True
    encoding: str = 'utf-8-sig'
    delimiter: str = ','
    quote_char: str = '"'
    
@dataclass
class ImportProgress:
    """Real-time import progress tracking."""
    import_id: str
    status: str
    stage: str
    total_records: int = 0
    processed_records: int = 0
    imported_records: int = 0
    failed_records: int = 0
    progress_percentage: float = 0.0
    current_operation: str = ""
    estimated_completion: Optional[datetime] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

@dataclass 
class ImportResult:
    """Final result of import operation."""
    import_id: str
    success: bool
    total_records: int
    imported_records: int
    updated_records: int
    failed_records: int
    skipped_records: int
    duration_seconds: int
    errors: List[str]
    warnings: List[str]
    batch_id: int

class EtilizeImportService:
    """Service for handling Etilize CSV imports to database."""
    
    def __init__(self, session: Session, user_id: int):
        """Initialize the import service.
        
        Args:
            session: Database session
            user_id: ID of user triggering the import
        """
        self.session = session
        self.user_id = user_id
        self.product_repo = ProductRepository(session)
        self.category_repo = CategoryRepository(session)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Progress tracking
        self._progress_callbacks = []
        self._current_progress = None
        
    def add_progress_callback(self, callback):
        """Add a callback function for progress updates."""
        self._progress_callbacks.append(callback)
    
    def _update_progress(self, progress: ImportProgress):
        """Update progress and notify callbacks."""
        self._current_progress = progress
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")
    
    def import_from_csv(
        self, 
        csv_file_path: str, 
        reference_file_path: Optional[str] = None,
        config: Optional[ImportConfiguration] = None
    ) -> ImportResult:
        """Import products from Etilize CSV file.
        
        Args:
            csv_file_path: Path to the Etilize CSV file
            reference_file_path: Optional path to reference data for filtering
            config: Import configuration options
            
        Returns:
            ImportResult with statistics and status
        """
        if config is None:
            config = ImportConfiguration()
            
        start_time = datetime.now()
        import_id = str(uuid.uuid4())
        
        self.logger.info(f"Starting import {import_id} from {csv_file_path}")
        
        try:
            # Create import batch record
            batch = self._create_import_batch(csv_file_path, config, import_id)
            
            # Initialize progress tracking
            progress = ImportProgress(
                import_id=import_id,
                status=ImportBatchStatus.PROCESSING.value,
                stage="initializing"
            )
            self._update_progress(progress)
            
            # Phase 1: Parse and validate CSV
            progress.stage = "parsing"
            self._update_progress(progress)
            
            csv_data = self._parse_csv_file(csv_file_path, config)
            progress.total_records = len(csv_data)
            self._update_progress(progress)
            
            # Phase 2: Load reference data if provided
            reference_data = {}
            if reference_file_path:
                progress.stage = "loading_reference"
                self._update_progress(progress)
                reference_data = self._load_reference_data(reference_file_path)
            
            # Phase 3: Process records in batches
            progress.stage = "processing"
            self._update_progress(progress)
            
            result = self._process_records_in_batches(
                csv_data, reference_data, batch, config, progress
            )
            
            # Phase 4: Finalize import
            progress.stage = "finalizing"
            self._update_progress(progress)
            
            duration_seconds = int((datetime.now() - start_time).total_seconds())
            
            # Update batch status
            batch.status = ImportBatchStatus.COMPLETED.value
            batch.completed_at = datetime.now()
            batch.duration = duration_seconds
            batch.total_records = progress.total_records
            batch.records_processed = progress.processed_records
            batch.records_imported = progress.imported_records
            batch.records_failed = progress.failed_records
            
            self.session.commit()
            
            # Final progress update
            progress.status = ImportBatchStatus.COMPLETED.value
            progress.stage = "completed"
            progress.progress_percentage = 100.0
            self._update_progress(progress)
            
            self.logger.info(f"Import {import_id} completed successfully")
            
            return ImportResult(
                import_id=import_id,
                success=True,
                total_records=progress.total_records,
                imported_records=progress.imported_records,
                updated_records=0,  # Will be updated in future versions
                failed_records=progress.failed_records,
                skipped_records=0,  # Will be calculated in future versions
                duration_seconds=duration_seconds,
                errors=progress.errors,
                warnings=[],  # Will be populated in future versions
                batch_id=batch.id
            )
            
        except Exception as e:
            self.logger.error(f"Import {import_id} failed: {str(e)}")
            
            # Update batch with error status
            try:
                if 'batch' in locals():
                    batch.status = ImportBatchStatus.FAILED.value
                    batch.error_details = {"error": str(e)}
                    batch.completed_at = datetime.now()
                    self.session.commit()
            except Exception:
                self.session.rollback()
            
            # Update progress with error
            if self._current_progress:
                self._current_progress.status = ImportBatchStatus.FAILED.value
                self._current_progress.errors.append(str(e))
                self._update_progress(self._current_progress)
            
            duration_seconds = int((datetime.now() - start_time).total_seconds())
            
            return ImportResult(
                import_id=import_id,
                success=False,
                total_records=0,
                imported_records=0,
                updated_records=0,
                failed_records=0,
                skipped_records=0,
                duration_seconds=duration_seconds,
                errors=[str(e)],
                warnings=[],
                batch_id=batch.id if 'batch' in locals() else 0
            )
    
    def _create_import_batch(
        self, 
        csv_file_path: str, 
        config: ImportConfiguration,
        import_id: str
    ) -> EtilizeImportBatch:
        """Create import batch record in database."""
        file_path = Path(csv_file_path)
        file_stats = file_path.stat()
        
        # Calculate file hash
        file_hash = self._calculate_file_hash(csv_file_path)
        
        batch = EtilizeImportBatch(
            batch_uuid=import_id,
            import_type="manual",
            source_file_path=str(file_path.absolute()),
            source_file_hash=file_hash,
            source_file_size=file_stats.st_size,
            source_file_modified=datetime.fromtimestamp(file_stats.st_mtime),
            status=ImportBatchStatus.PROCESSING.value,
            stage="initializing",
            triggered_by=self.user_id,
            import_config=asdict(config),
            started_at=datetime.now()
        )
        
        self.session.add(batch)
        self.session.commit()
        
        self.logger.info(f"Created import batch {batch.id} for file {csv_file_path}")
        return batch
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _parse_csv_file(self, csv_file_path: str, config: ImportConfiguration) -> List[Dict[str, Any]]:
        """Parse CSV file and return list of records."""
        records = []
        
        try:
            with open(csv_file_path, 'r', encoding=config.encoding) as csvfile:
                # Detect CSV dialect
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                
                try:
                    dialect = sniffer.sniff(sample, delimiters=config.delimiter)
                except csv.Error:
                    # Use default if sniffing fails
                    dialect = csv.excel
                    dialect.delimiter = config.delimiter
                    dialect.quotechar = config.quote_char
                
                reader = csv.DictReader(csvfile, dialect=dialect)
                
                for row_num, row in enumerate(reader, 1):
                    # Clean and normalize the row data
                    cleaned_row = {k.strip(): v.strip() if v else None for k, v in row.items()}
                    cleaned_row['_row_number'] = row_num
                    records.append(cleaned_row)
                    
                    # Limit for memory management
                    if len(records) >= 10000:  # Configurable limit
                        self.logger.warning(f"CSV file has more than 10,000 records. Only processing first 10,000.")
                        break
                        
        except Exception as e:
            raise ValueError(f"Failed to parse CSV file: {str(e)}")
            
        self.logger.info(f"Parsed {len(records)} records from CSV file")
        return records
    
    def _load_reference_data(self, reference_file_path: str) -> Dict[str, Any]:
        """Load reference data for product filtering."""
        # This will be implemented in future iterations
        # For now, return empty reference data
        return {}
    
    def _process_records_in_batches(
        self,
        csv_data: List[Dict[str, Any]],
        reference_data: Dict[str, Any],
        batch: EtilizeImportBatch,
        config: ImportConfiguration,
        progress: ImportProgress
    ) -> Dict[str, Any]:
        """Process CSV records in batches."""
        total_records = len(csv_data)
        processed_count = 0
        imported_count = 0
        failed_count = 0
        
        # Process in batches
        for i in range(0, total_records, config.batch_size):
            batch_records = csv_data[i:i + config.batch_size]
            
            try:
                # Process each record in the batch
                for record in batch_records:
                    try:
                        self._process_single_record(record, batch, config)
                        imported_count += 1
                    except Exception as e:
                        failed_count += 1
                        error_msg = f"Row {record.get('_row_number', 'unknown')}: {str(e)}"
                        progress.errors.append(error_msg)
                        self.logger.warning(error_msg)
                        
                        # Stop if too many errors
                        if failed_count >= config.max_errors:
                            raise ValueError(f"Too many errors ({failed_count}). Import stopped.")
                    
                    processed_count += 1
                    
                    # Update progress
                    progress.processed_records = processed_count
                    progress.imported_records = imported_count
                    progress.failed_records = failed_count
                    progress.progress_percentage = (processed_count / total_records) * 100
                    progress.current_operation = f"Processing record {processed_count} of {total_records}"
                    
                    # Update progress every 10 records for performance
                    if processed_count % 10 == 0:
                        self._update_progress(progress)
                
                # Commit batch to database
                self.session.commit()
                
            except Exception as e:
                self.session.rollback()
                self.logger.error(f"Batch processing failed: {str(e)}")
                raise
        
        return {
            "processed": processed_count,
            "imported": imported_count,
            "failed": failed_count
        }
    
    def _process_single_record(
        self, 
        record: Dict[str, Any], 
        batch: EtilizeImportBatch,
        config: ImportConfiguration
    ):
        """Process a single CSV record into staging table."""
        
        # Extract key fields from the record
        sku = record.get('SKU') or record.get('sku') or record.get('Product SKU')
        title = record.get('Product Title') or record.get('title') or record.get('Name')
        mpn = record.get('Manufacturer Part Number') or record.get('MPN') or record.get('mpn')
        brand = record.get('Brand') or record.get('brand') or record.get('Manufacturer')
        price_str = record.get('Price') or record.get('price') or record.get('Unit Price')
        description = record.get('Description') or record.get('description')
        
        # Validate required fields
        if not sku:
            raise ValueError("SKU is required but missing")
        if not title:
            raise ValueError("Product Title is required but missing")
        
        # Parse price
        price = None
        if price_str:
            try:
                # Remove currency symbols and clean price string
                price_clean = str(price_str).replace('$', '').replace(',', '').strip()
                price = float(price_clean) if price_clean else None
            except ValueError:
                self.logger.warning(f"Invalid price format: {price_str}")
        
        # Create staging record
        staging_product = EtilizeStagingProduct(
            batch_id=batch.id,
            etilize_id=record.get('Product ID'),
            raw_data=record,
            title=title[:1000] if title else None,  # Truncate if too long
            sku=sku[:200] if sku else None,
            manufacturer_part_number=mpn[:200] if mpn else None,
            brand=brand[:200] if brand else None,
            manufacturer=brand[:200] if brand else None,  # Use brand as manufacturer for now
            description=description,
            price=price,
            processing_status=ProcessingStatus.PENDING.value,
            validation_status=ProcessingStatus.PENDING.value,
            mapping_status=ProcessingStatus.PENDING.value,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.session.add(staging_product)
        
        self.logger.debug(f"Created staging record for SKU: {sku}")
    
    def get_import_status(self, import_id: str) -> Optional[ImportProgress]:
        """Get current status of an import operation."""
        try:
            batch = self.session.query(EtilizeImportBatch).filter_by(batch_uuid=import_id).first()
            if not batch:
                return None
            
            return ImportProgress(
                import_id=import_id,
                status=batch.status,
                stage=batch.stage,
                total_records=batch.total_records or 0,
                processed_records=batch.records_processed or 0,
                imported_records=batch.records_imported or 0,
                failed_records=batch.records_failed or 0,
                progress_percentage=batch.progress or 0.0,
                current_operation=f"Stage: {batch.stage}",
                estimated_completion=None,  # Will be calculated in future versions
                errors=[]  # Will be populated from error_details in future versions
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get import status: {str(e)}")
            return None
    
    def get_import_history(self, limit: int = 50) -> List[ImportResult]:
        """Get history of recent imports."""
        try:
            batches = (self.session.query(EtilizeImportBatch)
                      .filter_by(triggered_by=self.user_id)
                      .order_by(EtilizeImportBatch.created_at.desc())
                      .limit(limit)
                      .all())
            
            results = []
            for batch in batches:
                results.append(ImportResult(
                    import_id=batch.batch_uuid,
                    success=batch.status == ImportBatchStatus.COMPLETED.value,
                    total_records=batch.total_records or 0,
                    imported_records=batch.records_imported or 0,
                    updated_records=batch.records_updated or 0,
                    failed_records=batch.records_failed or 0,
                    skipped_records=batch.records_skipped or 0,
                    duration_seconds=batch.duration or 0,
                    errors=[],  # Will extract from error_details in future versions
                    warnings=[],
                    batch_id=batch.id
                ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to get import history: {str(e)}")
            return []
    
    def cancel_import(self, import_id: str) -> bool:
        """Cancel a running import operation."""
        try:
            batch = self.session.query(EtilizeImportBatch).filter_by(batch_uuid=import_id).first()
            if not batch:
                return False
            
            if batch.status in [ImportBatchStatus.COMPLETED.value, ImportBatchStatus.FAILED.value]:
                return False  # Cannot cancel completed imports
            
            batch.status = ImportBatchStatus.CANCELLED.value
            batch.completed_at = datetime.now()
            self.session.commit()
            
            self.logger.info(f"Import {import_id} cancelled successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel import: {str(e)}")
            self.session.rollback()
            return False