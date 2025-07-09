# Sync System Implementation Examples

Based on analysis of the existing codebase, here are concrete implementation examples that leverage existing components:

## 1. Etilize Sync Implementation

### Using Existing FTP Downloader

```python
# scripts/etilize/etilize_sync_manager.py
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utilities.ftp_downloader import FTPDownloader
from scripts.data_processing.filter_products_api import filter_products_api
from web_dashboard.backend.models import EtilizeSyncJob, SyncStaging, Product
from web_dashboard.backend.database import db_session

class EtilizeSyncManager:
    """
    Manages the complete Etilize sync workflow
    """
    def __init__(self):
        self.ftp_downloader = FTPDownloader(
            host=os.getenv('ETILIZE_FTP_HOST'),
            username=os.getenv('ETILIZE_FTP_USER'),
            password=os.getenv('ETILIZE_FTP_PASS')
        )
        self.download_path = Path("data/etilize")
        self.download_path.mkdir(parents=True, exist_ok=True)
    
    def start_sync_job(self, auto_approve_threshold=0.95):
        """Start a new Etilize sync job"""
        with db_session() as session:
            # Create sync job
            job = EtilizeSyncJob(
                status='pending',
                started_at=datetime.utcnow()
            )
            session.add(job)
            session.commit()
            
            try:
                # Download latest file
                self._download_latest_file(job)
                
                # Process with Xorosoft filtering
                self._process_with_filtering(job)
                
                # Create staging entries
                self._create_staging_entries(job, auto_approve_threshold)
                
                # Update job status
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                
            except Exception as e:
                job.status = 'failed'
                job.error_log = str(e)
                raise
            
            finally:
                session.commit()
            
            return job.job_id
    
    def _download_latest_file(self, job):
        """Download latest file from FTP"""
        # Connect to FTP
        self.ftp_downloader.connect()
        
        # Find latest file
        latest_file = self.ftp_downloader.find_latest_zip()
        if not latest_file:
            raise ValueError("No files found on FTP")
        
        # Update job
        job.ftp_filename = latest_file['filename']
        job.ftp_file_size = latest_file['size']
        job.download_started_at = datetime.utcnow()
        
        # Download and extract
        local_file = self.ftp_downloader.download_file(
            latest_file['filename'],
            self.download_path
        )
        
        extracted_files = self.ftp_downloader.extract_zip(local_file)
        job.download_completed_at = datetime.utcnow()
        
        # Find CSV file
        csv_file = next((f for f in extracted_files if f.endswith('.csv')), None)
        if not csv_file:
            raise ValueError("No CSV file found in archive")
        
        job.csv_output_path = csv_file
        return csv_file
    
    def _process_with_filtering(self, job):
        """Process CSV with Xorosoft API filtering"""
        # Use existing filter_products_api function
        filtered_csv = filter_products_api(
            primary_file=job.csv_output_path,
            output_file=None,  # Auto-generate name
            debug=False,
            use_metafields=True,
            check_inventory=True,
            batch_size=100
        )
        
        # Update job with results
        job.csv_output_path = filtered_csv
        job.xorosoft_api_calls = 100  # This would come from the function
        job.processing_notes = {
            'filtered_file': filtered_csv,
            'processing_time': datetime.utcnow().isoformat()
        }
```

## 2. Enhanced Shopify Sync Service

### Extending Existing Sync Engine

```python
# web_dashboard/backend/enhanced_shopify_sync.py
from datetime import datetime
from typing import List, Dict, Optional
import json

from parallel_sync_engine import ParallelSyncEngine, SyncOperation, OperationType
from models import Product, ProductVersion, SyncStaging, SyncConflict
from shopify_sync_api import get_shopify_client
from database import db_session

class EnhancedShopifySyncService:
    """
    Enhanced Shopify sync with staging and versioning
    """
    def __init__(self):
        self.sync_engine = ParallelSyncEngine(
            min_workers=4,
            max_workers=16,
            enable_batching=True
        )
        self.shopify_client = get_shopify_client()
    
    def sync_down_with_versioning(self, since_date: Optional[datetime] = None):
        """
        Sync products from Shopify to Supabase with version tracking
        """
        with db_session() as session:
            # Fetch products from Shopify
            shopify_products = self._fetch_shopify_products(since_date)
            
            # Process in batches
            operations = []
            for batch in self._chunk_products(shopify_products, 50):
                operations.append(
                    SyncOperation(
                        operation_type=OperationType.UPDATE,
                        product_ids=[p['id'] for p in batch],
                        data={'products': batch, 'create_versions': True}
                    )
                )
            
            # Execute sync
            results = self.sync_engine.execute_batch(operations)
            
            # Process results
            sync_summary = {
                'total_products': len(shopify_products),
                'synced': 0,
                'conflicts': 0,
                'errors': 0
            }
            
            for result in results:
                if result.error:
                    sync_summary['errors'] += 1
                    continue
                
                for product_data in result.data['products']:
                    self._process_product_sync(session, product_data, sync_summary)
            
            session.commit()
            return sync_summary
    
    def _process_product_sync(self, session, shopify_product, summary):
        """Process individual product sync with conflict detection"""
        # Find local product
        local_product = session.query(Product).filter_by(
            shopify_product_id=shopify_product['id']
        ).first()
        
        if local_product:
            # Check for conflicts
            conflicts = self._detect_conflicts(local_product, shopify_product)
            
            if conflicts:
                summary['conflicts'] += len(conflicts)
                for conflict in conflicts:
                    self._create_conflict_record(session, local_product, conflict)
            
            # Create version snapshot
            self._create_product_version(session, local_product, shopify_product)
            
            # Update local product
            self._update_local_product(local_product, shopify_product)
        else:
            # Create new product
            self._create_local_product(session, shopify_product)
        
        summary['synced'] += 1
    
    def _detect_conflicts(self, local_product, shopify_product):
        """Detect conflicts between local and Shopify data"""
        conflicts = []
        
        # Define conflict detection rules
        conflict_fields = [
            ('name', 'title'),
            ('price', lambda p: p['variants'][0]['price'] if p['variants'] else None),
            ('description', 'body_html'),
            ('inventory_quantity', lambda p: p['variants'][0]['inventory_quantity'] if p['variants'] else 0)
        ]
        
        for local_field, shopify_field in conflict_fields:
            local_value = getattr(local_product, local_field)
            
            # Handle callable shopify fields
            if callable(shopify_field):
                shopify_value = shopify_field(shopify_product)
            else:
                shopify_value = shopify_product.get(shopify_field)
            
            # Check if values differ significantly
            if self._values_conflict(local_value, shopify_value):
                conflicts.append({
                    'field': local_field,
                    'local_value': local_value,
                    'shopify_value': shopify_value,
                    'local_updated': local_product.updated_at,
                    'shopify_updated': shopify_product.get('updated_at')
                })
        
        return conflicts
    
    def _create_product_version(self, session, product, shopify_data):
        """Create a version snapshot of the product"""
        # Get latest version number
        latest_version = session.query(ProductVersion).filter_by(
            product_id=product.id
        ).order_by(ProductVersion.version_number.desc()).first()
        
        version_number = (latest_version.version_number + 1) if latest_version else 1
        
        # Create version record
        version = ProductVersion(
            product_id=product.id,
            version_number=version_number,
            product_data=product.to_dict(),
            shopify_data=shopify_data,
            changed_fields=self._get_changed_fields(product, shopify_data),
            change_source='shopify',
            change_type='update'
        )
        
        session.add(version)
```

## 3. Staged Sync Up Implementation

### Using Existing Components

```python
# web_dashboard/backend/staged_sync_service.py
from datetime import datetime
from typing import List, Dict, Optional
import json

from models import Product, SyncStaging, SyncStatus
from parallel_sync_api import get_parallel_engine
from database import db_session

class StagedSyncService:
    """
    Handles staged synchronization from Supabase to Shopify
    """
    def __init__(self):
        self.sync_engine = get_parallel_engine()
    
    def create_staged_sync(self, product_ids: List[int], sync_fields: List[str], 
                          auto_approve: bool = False) -> str:
        """
        Create staged sync entries for review
        """
        with db_session() as session:
            staging_id = str(uuid.uuid4())
            staging_entries = []
            
            # Load products
            products = session.query(Product).filter(
                Product.id.in_(product_ids)
            ).all()
            
            for product in products:
                # Get current Shopify data
                shopify_data = self._fetch_shopify_product(product.shopify_product_id)
                
                # Calculate changes
                changes = self._calculate_changes(product, shopify_data, sync_fields)
                
                if changes:
                    # Create staging entry
                    entry = SyncStaging(
                        staging_id=staging_id,
                        product_id=product.id,
                        operation_type='update',
                        source='manual',
                        current_data=shopify_data,
                        proposed_data=self._merge_changes(shopify_data, changes),
                        changes=changes,
                        auto_approve=auto_approve,
                        priority=3  # Normal priority
                    )
                    staging_entries.append(entry)
            
            # Bulk save
            session.bulk_save_objects(staging_entries)
            session.commit()
            
            # Auto-approve if requested
            if auto_approve:
                self._auto_approve_entries(staging_id)
            
            return staging_id
    
    def review_staged_changes(self, staging_id: str) -> Dict:
        """Get staged changes for review"""
        with db_session() as session:
            entries = session.query(SyncStaging).filter_by(
                staging_id=staging_id,
                status='pending'
            ).all()
            
            return {
                'staging_id': staging_id,
                'total_items': len(entries),
                'items': [
                    {
                        'id': entry.id,
                        'product_id': entry.product_id,
                        'product_name': entry.product.name,
                        'sku': entry.product.sku,
                        'changes': entry.changes,
                        'priority': entry.priority
                    }
                    for entry in entries
                ],
                'summary': self._summarize_changes(entries)
            }
    
    def execute_staged_sync(self, staging_id: str, approved_ids: List[int], 
                           rejected_ids: List[int] = None) -> Dict:
        """Execute approved staged changes"""
        with db_session() as session:
            # Update rejected entries
            if rejected_ids:
                session.query(SyncStaging).filter(
                    SyncStaging.staging_id == staging_id,
                    SyncStaging.id.in_(rejected_ids)
                ).update({
                    'status': 'rejected',
                    'reviewed_at': datetime.utcnow()
                }, synchronize_session=False)
            
            # Get approved entries
            approved_entries = session.query(SyncStaging).filter(
                SyncStaging.staging_id == staging_id,
                SyncStaging.id.in_(approved_ids),
                SyncStaging.status == 'pending'
            ).all()
            
            # Create sync operations
            operations = []
            for entry in approved_entries:
                operations.append({
                    'entry_id': entry.id,
                    'operation': SyncOperation(
                        operation_type=OperationType.UPDATE,
                        product_ids=[entry.product_id],
                        data=entry.proposed_data,
                        priority=SyncPriority(entry.priority)
                    )
                })
            
            # Execute sync
            results = self.sync_engine.execute_batch(
                [op['operation'] for op in operations]
            )
            
            # Update staging entries with results
            for op, result in zip(operations, results):
                entry = next(e for e in approved_entries if e.id == op['entry_id'])
                
                if result.error:
                    entry.status = 'failed'
                    entry.error_message = result.error
                else:
                    entry.status = 'synced'
                    entry.sync_completed_at = datetime.utcnow()
                    entry.sync_result = result.result
            
            session.commit()
            
            # Return summary
            return {
                'staging_id': staging_id,
                'total_synced': sum(1 for r in results if not r.error),
                'total_failed': sum(1 for r in results if r.error),
                'results': [
                    {
                        'product_id': op['operation'].product_ids[0],
                        'success': not result.error,
                        'error': result.error
                    }
                    for op, result in zip(operations, results)
                ]
            }
```

## 4. Xorosoft Integration Service

### Extending Existing API Service

```python
# web_dashboard/backend/services/xorosoft_sync_service.py
from datetime import datetime
from typing import List, Dict, Optional
import logging

from web_dashboard.backend.services.xorosoft_api_service import XorosoftAPIService
from models import Product, XorosoftProduct
from database import db_session

logger = logging.getLogger(__name__)

class XorosoftSyncService:
    """
    Handles synchronization with Xorosoft for inventory and validation
    """
    def __init__(self):
        self.api_service = XorosoftAPIService()
    
    def sync_inventory_levels(self, product_skus: Optional[List[str]] = None,
                            update_shopify: bool = True) -> Dict:
        """
        Sync inventory levels from Xorosoft
        """
        with db_session() as session:
            # Get products to sync
            query = session.query(Product)
            if product_skus:
                query = query.filter(Product.sku.in_(product_skus))
            products = query.all()
            
            sync_results = {
                'total_products': len(products),
                'inventory_updates': 0,
                'out_of_stock': 0,
                'errors': 0
            }
            
            # Process in batches
            for batch in self._chunk_products(products, 50):
                try:
                    # Get Xorosoft data
                    xoro_data = self.api_service.batch_product_lookup(
                        [p.sku for p in batch]
                    )
                    
                    for product in batch:
                        if product.sku in xoro_data:
                            self._update_inventory(
                                session, 
                                product, 
                                xoro_data[product.sku],
                                sync_results,
                                update_shopify
                            )
                        else:
                            logger.warning(f"Product {product.sku} not found in Xorosoft")
                            
                except Exception as e:
                    logger.error(f"Error syncing batch: {e}")
                    sync_results['errors'] += len(batch)
            
            session.commit()
            return sync_results
    
    def _update_inventory(self, session, product, xoro_data, results, update_shopify):
        """Update inventory for a single product"""
        # Update or create Xorosoft product record
        xoro_product = session.query(XorosoftProduct).filter_by(
            base_part=product.sku
        ).first()
        
        if not xoro_product:
            xoro_product = XorosoftProduct(base_part=product.sku)
            session.add(xoro_product)
        
        # Update fields
        old_stock = xoro_product.stock_level
        xoro_product.stock_level = xoro_data.get('stock_level', 0)
        xoro_product.price = xoro_data.get('price')
        xoro_product.cost_price = xoro_data.get('cost_price')
        xoro_product.manufacturer = xoro_data.get('manufacturer')
        xoro_product.last_updated = datetime.utcnow()
        xoro_product.api_response = xoro_data
        
        # Check if inventory changed
        if old_stock != xoro_product.stock_level:
            results['inventory_updates'] += 1
            
            if xoro_product.stock_level == 0:
                results['out_of_stock'] += 1
            
            # Update local product
            product.inventory_quantity = xoro_product.stock_level
            
            # Queue Shopify update if requested
            if update_shopify and product.shopify_variant_id:
                self._queue_shopify_inventory_update(
                    product.shopify_variant_id,
                    xoro_product.stock_level
                )
    
    def validate_products(self, product_skus: List[str]) -> Dict:
        """
        Validate products against Xorosoft catalog
        """
        results = {
            'total': len(product_skus),
            'valid': 0,
            'invalid': 0,
            'matches': {}
        }
        
        for sku in product_skus:
            match = self.api_service.find_product(sku)
            
            if match:
                results['valid'] += 1
                results['matches'][sku] = {
                    'valid': True,
                    'match_type': match.match_type.value,
                    'confidence': match.confidence,
                    'xorosoft_data': match.product_data
                }
            else:
                results['invalid'] += 1
                results['matches'][sku] = {
                    'valid': False,
                    'match_type': None,
                    'confidence': 0,
                    'xorosoft_data': None
                }
        
        return results
```

## 5. Frontend React Components

### Sync Dashboard Component

```typescript
// frontend/src/components/SyncDashboard.tsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
import { Badge } from './ui/badge';
import { RefreshCw, Download, Upload, AlertCircle } from 'lucide-react';

interface SyncMetrics {
  totalOperations: number;
  completedOperations: number;
  failedOperations: number;
  operationsPerSecond: number;
  queueDepth: number;
  activeWorkers: number;
  lastUpdated: string;
}

interface ActiveJob {
  jobId: string;
  type: string;
  status: string;
  progress: number;
  startedAt: string;
  estimatedCompletion?: string;
}

export const SyncDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<SyncMetrics | null>(null);
  const [activeJobs, setActiveJobs] = useState<ActiveJob[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadDashboardData();
    const interval = setInterval(loadDashboardData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      const [metricsRes, jobsRes] = await Promise.all([
        fetch('/api/sync/metrics'),
        fetch('/api/sync/jobs/active')
      ]);
      
      if (metricsRes.ok) {
        setMetrics(await metricsRes.json());
      }
      
      if (jobsRes.ok) {
        setActiveJobs(await jobsRes.json());
      }
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    }
  };

  const startEtilizeSync = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/etilize/sync/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          auto_download: true,
          apply_xorosoft_filter: true,
          create_staging_entries: true,
          auto_approve_threshold: 0.95
        })
      });
      
      if (response.ok) {
        await loadDashboardData();
      }
    } finally {
      setLoading(false);
    }
  };

  const startShopifySync = async (direction: 'up' | 'down') => {
    setLoading(true);
    try {
      const response = await fetch(`/api/shopify/sync/${direction}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sync_mode: 'incremental',
          create_versions: true,
          detect_conflicts: true
        })
      });
      
      if (response.ok) {
        await loadDashboardData();
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sync-dashboard space-y-6">
      {/* Metrics Overview */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Total Operations</p>
                  <p className="text-2xl font-bold">{metrics.totalOperations}</p>
                </div>
                <RefreshCw className="h-4 w-4 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Success Rate</p>
                  <p className="text-2xl font-bold">
                    {((metrics.completedOperations / metrics.totalOperations) * 100).toFixed(1)}%
                  </p>
                </div>
                <Badge variant={metrics.failedOperations > 0 ? "destructive" : "success"}>
                  {metrics.failedOperations} Failed
                </Badge>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Queue Depth</p>
                  <p className="text-2xl font-bold">{metrics.queueDepth}</p>
                </div>
                <p className="text-sm text-muted-foreground">
                  {metrics.operationsPerSecond.toFixed(1)} ops/sec
                </p>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Active Workers</p>
                  <p className="text-2xl font-bold">{metrics.activeWorkers}</p>
                </div>
                <p className="text-sm text-muted-foreground">
                  Last updated: {new Date(metrics.lastUpdated).toLocaleTimeString()}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Active Jobs */}
      <Card>
        <CardHeader>
          <CardTitle>Active Sync Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {activeJobs.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">No active sync jobs</p>
            ) : (
              activeJobs.map((job) => (
                <div key={job.jobId} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Badge variant={job.status === 'running' ? 'default' : 'secondary'}>
                        {job.type}
                      </Badge>
                      <span className="text-sm font-medium">{job.jobId.slice(0, 8)}</span>
                    </div>
                    <span className="text-sm text-muted-foreground">
                      Started {new Date(job.startedAt).toLocaleTimeString()}
                    </span>
                  </div>
                  <Progress value={job.progress} className="h-2" />
                  {job.estimatedCompletion && (
                    <p className="text-xs text-muted-foreground">
                      Est. completion: {new Date(job.estimatedCompletion).toLocaleTimeString()}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <Button
              onClick={startEtilizeSync}
              disabled={loading}
              className="flex items-center space-x-2"
            >
              <Download className="h-4 w-4" />
              <span>Start Etilize Sync</span>
            </Button>
            
            <Button
              onClick={() => startShopifySync('down')}
              disabled={loading}
              variant="outline"
              className="flex items-center space-x-2"
            >
              <Download className="h-4 w-4" />
              <span>Sync from Shopify</span>
            </Button>
            
            <Button
              onClick={() => startShopifySync('up')}
              disabled={loading}
              variant="outline"
              className="flex items-center space-x-2"
            >
              <Upload className="h-4 w-4" />
              <span>Sync to Shopify</span>
            </Button>
            
            <Button
              onClick={() => window.location.href = '/sync/staging'}
              variant="outline"
              className="flex items-center space-x-2"
            >
              <AlertCircle className="h-4 w-4" />
              <span>View Staged Changes</span>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
```

### Staged Changes Review Component

```typescript
// frontend/src/components/StagedChangesReview.tsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';
import { Badge } from './ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Eye, Check, X } from 'lucide-react';

interface StagedItem {
  id: number;
  productId: number;
  productName: string;
  sku: string;
  changes: Record<string, any>;
  priority: number;
}

interface StagedChangesReviewProps {
  stagingId: string;
}

export const StagedChangesReview: React.FC<StagedChangesReviewProps> = ({ stagingId }) => {
  const [items, setItems] = useState<StagedItem[]>([]);
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'table' | 'diff'>('table');

  useEffect(() => {
    loadStagedChanges();
  }, [stagingId]);

  const loadStagedChanges = async () => {
    try {
      const response = await fetch(`/api/shopify/sync/staging/${stagingId}`);
      if (response.ok) {
        const data = await response.json();
        setItems(data.items);
      }
    } finally {
      setLoading(false);
    }
  };

  const toggleSelection = (itemId: number) => {
    const newSelection = new Set(selectedItems);
    if (newSelection.has(itemId)) {
      newSelection.delete(itemId);
    } else {
      newSelection.add(itemId);
    }
    setSelectedItems(newSelection);
  };

  const selectAll = () => {
    setSelectedItems(new Set(items.map(item => item.id)));
  };

  const deselectAll = () => {
    setSelectedItems(new Set());
  };

  const approveSelected = async () => {
    const approved = Array.from(selectedItems);
    const response = await fetch(`/api/shopify/sync/staging/${stagingId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        approved_items: approved,
        rejected_items: [],
        approval_notes: 'Bulk approval'
      })
    });

    if (response.ok) {
      // Redirect to sync dashboard
      window.location.href = '/sync';
    }
  };

  const rejectSelected = async () => {
    const rejected = Array.from(selectedItems);
    const response = await fetch(`/api/shopify/sync/staging/${stagingId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        approved_items: [],
        rejected_items: rejected,
        approval_notes: 'Bulk rejection'
      })
    });

    if (response.ok) {
      // Reload the page
      await loadStagedChanges();
      setSelectedItems(new Set());
    }
  };

  const renderChangeValue = (field: string, change: any) => {
    if (change.current === change.proposed) {
      return <span className="text-muted-foreground">No change</span>;
    }

    return (
      <div className="space-y-1">
        <div className="flex items-center space-x-2">
          <span className="text-sm text-muted-foreground">Current:</span>
          <span className="text-sm font-mono">{change.current || 'null'}</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-muted-foreground">Proposed:</span>
          <span className="text-sm font-mono font-semibold">{change.proposed || 'null'}</span>
        </div>
        {change.change_percent && (
          <Badge variant={change.change_percent > 0 ? 'default' : 'secondary'}>
            {change.change_percent > 0 ? '+' : ''}{change.change_percent.toFixed(1)}%
          </Badge>
        )}
      </div>
    );
  };

  if (loading) {
    return <div>Loading staged changes...</div>;
  }

  return (
    <div className="staged-changes-review space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Review Staged Changes ({items.length} items)</CardTitle>
            <div className="flex items-center space-x-2">
              <Button
                variant="success"
                onClick={approveSelected}
                disabled={selectedItems.size === 0}
                className="flex items-center space-x-2"
              >
                <Check className="h-4 w-4" />
                <span>Approve Selected ({selectedItems.size})</span>
              </Button>
              <Button
                variant="destructive"
                onClick={rejectSelected}
                disabled={selectedItems.size === 0}
                className="flex items-center space-x-2"
              >
                <X className="h-4 w-4" />
                <span>Reject Selected</span>
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as any)}>
            <TabsList>
              <TabsTrigger value="table">Table View</TabsTrigger>
              <TabsTrigger value="diff">Diff View</TabsTrigger>
            </TabsList>

            <TabsContent value="table">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Button variant="outline" size="sm" onClick={selectAll}>
                      Select All
                    </Button>
                    <Button variant="outline" size="sm" onClick={deselectAll}>
                      Deselect All
                    </Button>
                  </div>
                </div>

                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12"></TableHead>
                      <TableHead>Product</TableHead>
                      <TableHead>SKU</TableHead>
                      <TableHead>Changes</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <Checkbox
                            checked={selectedItems.has(item.id)}
                            onCheckedChange={() => toggleSelection(item.id)}
                          />
                        </TableCell>
                        <TableCell className="font-medium">{item.productName}</TableCell>
                        <TableCell className="font-mono text-sm">{item.sku}</TableCell>
                        <TableCell>
                          <div className="space-y-1">
                            {Object.entries(item.changes).map(([field, change]) => (
                              <div key={field} className="text-sm">
                                <span className="font-medium">{field}:</span>
                                {' '}
                                {renderChangeValue(field, change)}
                              </div>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={item.priority <= 2 ? 'destructive' : 'default'}>
                            P{item.priority}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => window.open(`/products/${item.productId}`, '_blank')}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </TabsContent>

            <TabsContent value="diff">
              <div className="space-y-4">
                {items.map((item) => (
                  <Card key={item.id}>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Checkbox
                            checked={selectedItems.has(item.id)}
                            onCheckedChange={() => toggleSelection(item.id)}
                          />
                          <div>
                            <h3 className="font-semibold">{item.productName}</h3>
                            <p className="text-sm text-muted-foreground">SKU: {item.sku}</p>
                          </div>
                        </div>
                        <Badge variant={item.priority <= 2 ? 'destructive' : 'default'}>
                          Priority {item.priority}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {Object.entries(item.changes).map(([field, change]) => (
                          <div key={field} className="border-l-2 border-muted pl-4">
                            <h4 className="font-medium mb-1">{field}</h4>
                            {renderChangeValue(field, change)}
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};
```

## Conclusion

These implementation examples demonstrate how to build the enhanced sync system by:

1. **Leveraging existing components** - Using the FTP downloader, Xorosoft API service, and parallel sync engine
2. **Extending current functionality** - Adding versioning, staging, and conflict detection to existing sync services
3. **Following established patterns** - Using the same database session management and error handling patterns
4. **Building incremental value** - Each component can be implemented and tested independently

The modular approach allows for gradual rollout while maintaining system stability and providing immediate value through enhanced sync capabilities.