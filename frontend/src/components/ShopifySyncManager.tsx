import React, { useState, useEffect, useCallback } from 'react';
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { 
  Store,
  Settings,
  Play,
  Pause,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  RefreshCw,
  Upload,
  FileText,
  Filter,
  Download,
  ShoppingCart,
  Zap,
  BarChart2,
  Package
} from 'lucide-react';
import { ShopifyProductSyncManager } from './ShopifyProductSyncManager';
import { ParallelSyncControl } from './ParallelSyncControl';
import { SyncPerformanceMonitor } from './SyncPerformanceMonitor';
import { BulkOperationStatus } from './BulkOperationStatus';
import { 
  apiClient, 
  type ShopifySyncConfiguration,
  type ShopifySyncStatus,
  type ShopifySyncHistoryItem,
  type SyncMode,
  type SyncFlag,
  type ImportBatch,
  type SyncableProduct
} from '@/lib/api';
import {
  ParallelSyncConfig,
  SyncMetrics,
  WorkerPoolStatus,
  QueueDepth,
  SystemResources,
  SyncAlert,
  BulkOperation,
  PerformancePrediction,
  ParallelSyncStatusResponse
} from '@/types/sync';

interface ShopifySyncManagerProps {
  className?: string;
}

interface SyncJob {
  id: string;
  status: ShopifySyncStatus;
  startTime: Date;
}

export function ShopifySyncManager({ className }: ShopifySyncManagerProps) {
  const [activeTab, setActiveTab] = useState<'configure' | 'running' | 'history' | 'products' | 'product-sync' | 'parallel-sync' | 'performance' | 'bulk-operations'>('configure');
  
  // Configuration state
  const [syncConfig, setSyncConfig] = useState<Partial<ShopifySyncConfiguration>>({
    mode: 'full_sync',
    flags: [],
    batch_size: 25,
    max_workers: 1,
    data_source: 'database'
  });
  const [availableModes, setAvailableModes] = useState<SyncMode[]>([]);
  const [availableFlags, setAvailableFlags] = useState<SyncFlag[]>([]);
  const [importBatches, setImportBatches] = useState<ImportBatch[]>([]);
  
  // Sync state
  const [runningSyncs, setRunningSyncs] = useState<SyncJob[]>([]);
  const [syncHistory, setSyncHistory] = useState<ShopifySyncHistoryItem[]>([]);
  const [syncableProducts, setSyncableProducts] = useState<SyncableProduct[]>([]);
  const [productFilters, setProductFilters] = useState({
    import_batch_id: undefined as number | undefined,
    category: '',
    status: '',
    limit: 50,
    offset: 0
  });
  
  // UI state
  const [isCreatingSync, setIsCreatingSync] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingProducts, setIsLoadingProducts] = useState(false);

  // Parallel sync state
  const [parallelSyncStatus, setParallelSyncStatus] = useState<ParallelSyncStatusResponse | null>(null);
  const [isParallelSyncRunning, setIsParallelSyncRunning] = useState(false);
  const [parallelSyncMetrics, setParallelSyncMetrics] = useState<SyncMetrics>({
    operationsPerSecond: 0,
    successRate: 0,
    errorRate: 0,
    averageLatency: 0,
    totalOperations: 0,
    successfulOperations: 0,
    failedOperations: 0,
    retryCount: 0,
    throughput: 0,
    estimatedTimeRemaining: 0,
    memoryUsage: 0,
    cpuUsage: 0
  });
  const [workerPoolStatus, setWorkerPoolStatus] = useState<WorkerPoolStatus>({
    active: 0,
    idle: 0,
    total: 0,
    utilization: 0,
    tasksQueued: 0,
    tasksProcessing: 0,
    tasksCompleted: 0,
    tasksFailed: 0
  });
  const [queueDepth, setQueueDepth] = useState<QueueDepth>({
    total: 0,
    byPriority: { low: 0, normal: 0, high: 0 },
    byOperation: { create: 0, update: 0, delete: 0 },
    averageWaitTime: 0,
    oldestItemAge: 0
  });
  const [systemResources, setSystemResources] = useState<SystemResources>({
    memory: { used: 0, total: 0, percentage: 0 },
    cpu: { usage: 0, cores: 0 },
    network: { latency: 0, throughput: 0 }
  });
  const [syncAlerts, setSyncAlerts] = useState<SyncAlert[]>([]);
  const [bulkOperations, setBulkOperations] = useState<BulkOperation[]>([]);
  const [performancePrediction, setPerformancePrediction] = useState<PerformancePrediction | undefined>();

  // Load initial data
  useEffect(() => {
    loadSyncModes();
    loadImportBatches();
    loadSyncHistory();
    loadSyncableProducts();
  }, []);

  // Poll running syncs
  useEffect(() => {
    if (runningSyncs.length === 0) return;

    const interval = setInterval(async () => {
      const updatedJobs = await Promise.all(
        runningSyncs.map(async (job) => {
          try {
            const status = await apiClient.getShopifySyncStatus(job.id);
            return { ...job, status };
          } catch (err) {
            console.error(`Failed to get status for ${job.id}:`, err);
            return job;
          }
        })
      );

      // Remove completed jobs and update running ones
      const stillRunning = updatedJobs.filter(
        job => job.status.status === 'running' || job.status.status === 'queued'
      );
      
      setRunningSyncs(stillRunning);
      
      // If any jobs completed, refresh history
      if (stillRunning.length < runningSyncs.length) {
        loadSyncHistory();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [runningSyncs]);

  const loadSyncModes = useCallback(async () => {
    try {
      const response = await apiClient.getShopifySyncModes();
      setAvailableModes(response.modes);
      setAvailableFlags(response.flags);
    } catch (err) {
      console.error('Failed to load sync modes:', err);
    }
  }, []);

  const loadImportBatches = useCallback(async () => {
    try {
      const response = await apiClient.getImportBatches();
      setImportBatches(response.batches);
    } catch (err) {
      console.error('Failed to load import batches:', err);
    }
  }, []);

  const loadSyncHistory = useCallback(async () => {
    try {
      setIsLoadingHistory(true);
      const response = await apiClient.getShopifySyncHistory();
      setSyncHistory(response.history);
    } catch (err) {
      console.error('Failed to load sync history:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  const loadSyncableProducts = useCallback(async () => {
    try {
      setIsLoadingProducts(true);
      const response = await apiClient.getSyncableProducts(productFilters);
      setSyncableProducts(response.products);
    } catch (err) {
      console.error('Failed to load syncable products:', err);
    } finally {
      setIsLoadingProducts(false);
    }
  }, [productFilters]);

  const handleConfigChange = (field: string, value: any) => {
    setSyncConfig(prev => ({ ...prev, [field]: value }));
    setError(null);
  };

  const handleFlagToggle = (flag: string, checked: boolean) => {
    setSyncConfig(prev => ({
      ...prev,
      flags: checked 
        ? [...(prev.flags || []), flag]
        : (prev.flags || []).filter(f => f !== flag)
    }));
  };

  const validateConfig = async (): Promise<boolean> => {
    try {
      const response = await apiClient.validateShopifyConfig(syncConfig);
      if (!response.valid) {
        setError(response.errors?.join(', ') || 'Configuration is invalid');
        return false;
      }
      return true;
    } catch (err) {
      setError('Failed to validate configuration');
      return false;
    }
  };

  const handleStartSync = async () => {
    if (!await validateConfig()) return;

    try {
      setIsCreatingSync(true);
      setError(null);

      const response = await apiClient.executeShopifySync(syncConfig as ShopifySyncConfiguration);
      
      // Add to running syncs
      const newJob: SyncJob = {
        id: response.sync_id,
        status: {
          sync_id: response.sync_id,
          status: 'queued',
          mode: syncConfig.mode || 'full_sync',
          total_products: 0,
          successful_uploads: 0,
          failed_uploads: 0,
          skipped_uploads: 0,
          progress_percentage: 0,
          current_operation: 'Starting sync...',
          errors: [],
          warnings: []
        },
        startTime: new Date()
      };

      setRunningSyncs(prev => [...prev, newJob]);
      setSuccess('Shopify sync started successfully');
      setActiveTab('running');

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start sync');
    } finally {
      setIsCreatingSync(false);
    }
  };

  const handleCancelSync = async (syncId: string) => {
    try {
      await apiClient.cancelShopifySync(syncId);
      setRunningSyncs(prev => prev.filter(job => job.id !== syncId));
      setSuccess('Sync cancelled');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel sync');
    }
  };

  // Parallel sync methods
  const handleParallelSyncStart = async (config: ParallelSyncConfig) => {
    try {
      const response = await apiClient.startParallelSync({ config });
      setIsParallelSyncRunning(true);
      setSuccess('Parallel sync started successfully');
      
      // Start polling for status
      pollParallelSyncStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start parallel sync');
    }
  };

  const handleParallelSyncStop = async () => {
    try {
      if (parallelSyncStatus?.operations && parallelSyncStatus.operations.length > 0) {
        // Stop all running operations
        await Promise.all(
          parallelSyncStatus.operations
            .filter(op => op.status === 'processing' || op.status === 'queued')
            .map(op => apiClient.cancelBulkOperation(op.id))
        );
      }
      setIsParallelSyncRunning(false);
      setSuccess('Parallel sync stopped');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop parallel sync');
    }
  };

  const pollParallelSyncStatus = useCallback(async () => {
    if (!isParallelSyncRunning) return;

    try {
      const apiStatus = await apiClient.getParallelSyncStatus();
      
      // Convert API types to sync types
      const syncStatus: ParallelSyncStatusResponse = {
        operations: apiStatus.operations.map(op => ({
          id: op.operation_id,
          type: 'mixed' as const,
          status: op.status === 'pending' ? 'queued' as const : 
                  op.status === 'running' ? 'processing' as const :
                  op.status as any,
          totalItems: op.total_items,
          processedItems: op.processed_items,
          successfulItems: op.processed_items - op.failed_items,
          failedItems: op.failed_items,
          progress: op.total_items > 0 ? (op.processed_items / op.total_items) * 100 : 0,
          startTime: new Date(op.created_at),
          endTime: op.completed_at ? new Date(op.completed_at) : undefined,
          errors: [],
          config: {
            enabled: true,
            minWorkers: 1,
            maxWorkers: 5,
            batchSize: 25,
            priority: 'normal',
            operationType: 'all',
            strategy: 'balanced',
            retryAttempts: 3,
            timeout: 30000
          }
        })),
        metrics: apiStatus.metrics ? {
          operationsPerSecond: 0,
          successRate: apiStatus.metrics.successRate || 0,
          errorRate: 0,
          averageLatency: 0,
          totalOperations: apiStatus.metrics.productsToSync || 0,
          successfulOperations: apiStatus.metrics.approvedChanges || 0,
          failedOperations: apiStatus.metrics.failedSyncs || 0,
          retryCount: 0,
          throughput: 0,
          estimatedTimeRemaining: 0,
          memoryUsage: 0,
          cpuUsage: 0
        } : {
          operationsPerSecond: 0,
          successRate: 0,
          errorRate: 0,
          averageLatency: 0,
          totalOperations: 0,
          successfulOperations: 0,
          failedOperations: 0,
          retryCount: 0,
          throughput: 0,
          estimatedTimeRemaining: 0,
          memoryUsage: 0,
          cpuUsage: 0
        },
        workerPool: apiStatus.workerPool ? {
          active: apiStatus.workerPool.activeWorkers || 0,
          idle: apiStatus.workerPool.idleWorkers || 0,
          total: apiStatus.workerPool.totalWorkers || 0,
          utilization: apiStatus.workerPool.totalWorkers > 0 ? (apiStatus.workerPool.activeWorkers / apiStatus.workerPool.totalWorkers) * 100 : 0,
          tasksQueued: apiStatus.workerPool.queuedTasks || 0,
          tasksProcessing: apiStatus.workerPool.queuedTasks || 0,
          tasksCompleted: apiStatus.workerPool.completedTasks || 0,
          tasksFailed: apiStatus.workerPool.failedTasks || 0
        } : {
          active: 0,
          idle: 0,
          total: 0,
          utilization: 0,
          tasksQueued: 0,
          tasksProcessing: 0,
          tasksCompleted: 0,
          tasksFailed: 0
        },
        queue: apiStatus.queue ? {
          total: apiStatus.queue.pending || 0,
          byPriority: { low: 0, normal: 0, high: 0 },
          byOperation: { create: 0, update: 0, delete: 0 },
          averageWaitTime: 0,
          oldestItemAge: 0
        } : {
          total: 0,
          byPriority: { low: 0, normal: 0, high: 0 },
          byOperation: { create: 0, update: 0, delete: 0 },
          averageWaitTime: 0,
          oldestItemAge: 0
        },
        resources: apiStatus.resources ? {
          memory: { 
            used: apiStatus.resources.memoryUsage || 0, 
            total: 100, 
            percentage: apiStatus.resources.memoryUsage || 0 
          },
          cpu: { 
            usage: apiStatus.resources.cpuUsage || 0, 
            cores: 4 
          },
          network: { 
            latency: apiStatus.resources.networkIO || 0, 
            throughput: 0 
          }
        } : {
          memory: { used: 0, total: 0, percentage: 0 },
          cpu: { usage: 0, cores: 0 },
          network: { latency: 0, throughput: 0 }
        },
        alerts: apiStatus.alerts?.map(alert => ({
          id: alert.id,
          severity: alert.level as any,
          message: alert.message,
          timestamp: new Date(alert.timestamp),
          source: alert.operation || 'system',
          actionRequired: alert.level === 'error' || alert.level === 'warning',
          resolved: false
        })) || []
      };

      setParallelSyncStatus(syncStatus);
      setParallelSyncMetrics(syncStatus.metrics);
      setWorkerPoolStatus(syncStatus.workerPool);
      setQueueDepth(syncStatus.queue);
      setSystemResources(syncStatus.resources);
      setSyncAlerts(syncStatus.alerts);
      setBulkOperations(syncStatus.operations);

      // Check if any operations are still running
      const hasRunning = syncStatus.operations.some((op: BulkOperation) => 
        op.status === 'processing' || op.status === 'queued'
      );

      if (!hasRunning) {
        setIsParallelSyncRunning(false);
      }
    } catch (err) {
      console.error('Failed to poll parallel sync status:', err);
    }
  }, [isParallelSyncRunning]);

  // Poll parallel sync status
  useEffect(() => {
    if (!isParallelSyncRunning) return;

    const interval = setInterval(pollParallelSyncStatus, 2000);
    return () => clearInterval(interval);
  }, [isParallelSyncRunning, pollParallelSyncStatus]);

  const handleCancelBulkOperation = async (operationId: string) => {
    try {
      await apiClient.cancelBulkOperation(operationId);
      setSuccess('Bulk operation cancelled');
      pollParallelSyncStatus(); // Refresh status
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel operation');
    }
  };

  const handleRetryBulkOperation = async (operationId: string) => {
    try {
      await apiClient.retryBulkOperation(operationId);
      setSuccess('Bulk operation retried');
      pollParallelSyncStatus(); // Refresh status
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retry operation');
    }
  };

  const handleRefreshBulkOperations = () => {
    pollParallelSyncStatus();
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  const getStatusBadge = (status: string, success?: boolean) => {
    if (status === 'running' || status === 'queued') {
      return <Badge variant="default" className="bg-blue-500">Running</Badge>;
    }
    if (status === 'completed') {
      return success !== false ? 
        <Badge variant="default" className="bg-green-500">Completed</Badge> :
        <Badge variant="destructive">Failed</Badge>;
    }
    if (status === 'failed') {
      return <Badge variant="destructive">Failed</Badge>;
    }
    return <Badge variant="secondary">{status}</Badge>;
  };

  return (
    <div className={cn("space-y-6", className)}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Shopify Sync Manager</h2>
          <p className="text-muted-foreground">
            Configure and manage Shopify product synchronization
          </p>
        </div>
        <Button onClick={loadSyncHistory} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Alert Messages */}
      {error && (
        <Alert variant="destructive">
          <XCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert>
          <CheckCircle className="h-4 w-4" />
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-8">
          <TabsTrigger value="configure" className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Configure
          </TabsTrigger>
          <TabsTrigger value="product-sync" className="flex items-center gap-2">
            <ShoppingCart className="h-4 w-4" />
            Product Sync
          </TabsTrigger>
          <TabsTrigger value="parallel-sync" className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Parallel Sync
          </TabsTrigger>
          <TabsTrigger value="performance" className="flex items-center gap-2">
            <BarChart2 className="h-4 w-4" />
            Performance
          </TabsTrigger>
          <TabsTrigger value="bulk-operations" className="flex items-center gap-2">
            <Package className="h-4 w-4" />
            Bulk Ops ({bulkOperations.length})
          </TabsTrigger>
          <TabsTrigger value="running" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Running ({runningSyncs.length})
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            History
          </TabsTrigger>
          <TabsTrigger value="products" className="flex items-center gap-2">
            <Store className="h-4 w-4" />
            Products
          </TabsTrigger>
        </TabsList>

        {/* Configuration Tab */}
        <TabsContent value="configure" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Shopify Configuration</CardTitle>
              <CardDescription>
                Configure your Shopify store connection and sync settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="shop-url">Shop URL</Label>
                  <Input
                    id="shop-url"
                    placeholder="store.myshopify.com"
                    value={syncConfig.shop_url || ''}
                    onChange={(e) => handleConfigChange('shop_url', e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="access-token">Access Token</Label>
                  <Input
                    id="access-token"
                    type="password"
                    placeholder="shpat_xxxxx"
                    value={syncConfig.access_token || ''}
                    onChange={(e) => handleConfigChange('access_token', e.target.value)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="sync-mode">Sync Mode</Label>
                  <Select value={syncConfig.mode} onValueChange={(value) => handleConfigChange('mode', value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select sync mode" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableModes.map((mode) => (
                        <SelectItem key={mode.value} value={mode.value}>
                          <div>
                            <div className="font-medium">{mode.label}</div>
                            <div className="text-xs text-muted-foreground">{mode.description}</div>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="batch-size">Batch Size</Label>
                  <Input
                    id="batch-size"
                    type="number"
                    min="1"
                    max="100"
                    value={syncConfig.batch_size || 25}
                    onChange={(e) => handleConfigChange('batch_size', parseInt(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="import-batch">Import Batch (Optional)</Label>
                  <Select 
                    value={syncConfig.import_batch_id?.toString() || 'all'} 
                    onValueChange={(value) => handleConfigChange('import_batch_id', value === 'all' ? undefined : parseInt(value))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All products" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All products</SelectItem>
                      {importBatches.map((batch) => (
                        <SelectItem key={batch.id} value={batch.id.toString()}>
                          {batch.filename} ({batch.product_count} products)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-3">
                <Label>Sync Flags</Label>
                <div className="grid grid-cols-2 gap-3">
                  {availableFlags.map((flag) => (
                    <div key={flag.value} className="flex items-start space-x-3">
                      <Checkbox
                        id={flag.value}
                        checked={(syncConfig.flags || []).includes(flag.value)}
                        onCheckedChange={(checked) => handleFlagToggle(flag.value, checked as boolean)}
                      />
                      <div className="grid gap-1.5 leading-none">
                        <label
                          htmlFor={flag.value}
                          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                        >
                          {flag.label}
                        </label>
                        <p className="text-xs text-muted-foreground">
                          {flag.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="limit">Limit (Optional)</Label>
                  <Input
                    id="limit"
                    type="number"
                    min="1"
                    placeholder="No limit"
                    value={syncConfig.limit || ''}
                    onChange={(e) => handleConfigChange('limit', e.target.value ? parseInt(e.target.value) : undefined)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="start-from">Start From (Optional)</Label>
                  <Input
                    id="start-from"
                    type="number"
                    min="1"
                    placeholder="Start from beginning"
                    value={syncConfig.start_from || ''}
                    onChange={(e) => handleConfigChange('start_from', e.target.value ? parseInt(e.target.value) : undefined)}
                  />
                </div>
              </div>

              <Button 
                onClick={handleStartSync}
                disabled={isCreatingSync || !syncConfig.shop_url || !syncConfig.access_token}
                className="w-full"
              >
                {isCreatingSync ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    Starting Sync...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Start Shopify Sync
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Product Sync Tab */}
        <TabsContent value="product-sync" className="space-y-6">
          <ShopifyProductSyncManager />
        </TabsContent>

        {/* Parallel Sync Tab */}
        <TabsContent value="parallel-sync" className="space-y-6">
          <ParallelSyncControl
            onSyncStart={handleParallelSyncStart}
            onSyncStop={handleParallelSyncStop}
            isRunning={isParallelSyncRunning}
          />
        </TabsContent>

        {/* Performance Monitor Tab */}
        <TabsContent value="performance" className="space-y-6">
          <SyncPerformanceMonitor
            metrics={parallelSyncMetrics}
            workerPool={workerPoolStatus}
            queue={queueDepth}
            resources={systemResources}
            alerts={syncAlerts}
            prediction={performancePrediction}
          />
        </TabsContent>

        {/* Bulk Operations Tab */}
        <TabsContent value="bulk-operations" className="space-y-6">
          <BulkOperationStatus
            operations={bulkOperations}
            onCancelOperation={handleCancelBulkOperation}
            onRetryOperation={handleRetryBulkOperation}
            onRefresh={handleRefreshBulkOperations}
          />
        </TabsContent>

        {/* Running Syncs Tab */}
        <TabsContent value="running" className="space-y-4">
          {runningSyncs.length === 0 ? (
            <Card>
              <CardContent className="flex items-center justify-center py-8">
                <div className="text-center">
                  <Clock className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-muted-foreground">No syncs currently running</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            runningSyncs.map((job) => (
              <Card key={job.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base">Sync {job.id.slice(0, 8)}</CardTitle>
                      <CardDescription>
                        {job.status.mode.replace('_', ' ')} • Started {job.startTime.toLocaleTimeString()}
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      {getStatusBadge(job.status.status)}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleCancelSync(job.id)}
                        disabled={job.status.status === 'completed'}
                      >
                        <Pause className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span>{job.status.current_operation}</span>
                      <span>{job.status.progress_percentage.toFixed(1)}%</span>
                    </div>
                    <Progress value={job.status.progress_percentage} />
                  </div>

                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Total:</span>
                      <span className="ml-2 font-medium">{job.status.total_products}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Synced:</span>
                      <span className="ml-2 font-medium text-green-600">{job.status.successful_uploads}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Failed:</span>
                      <span className="ml-2 font-medium text-red-600">{job.status.failed_uploads}</span>
                    </div>
                  </div>

                  {job.status.errors.length > 0 && (
                    <Alert variant="destructive">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>
                        {job.status.errors.slice(0, 2).join('; ')}
                        {job.status.errors.length > 2 && ` (and ${job.status.errors.length - 2} more)`}
                      </AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-4">
          {isLoadingHistory ? (
            <Card>
              <CardContent className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin" />
              </CardContent>
            </Card>
          ) : syncHistory.length === 0 ? (
            <Card>
              <CardContent className="flex items-center justify-center py-8">
                <div className="text-center">
                  <FileText className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-muted-foreground">No sync history available</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            syncHistory.map((item) => (
              <Card key={item.sync_id}>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h4 className="font-medium">Sync {item.sync_id.slice(0, 8)}</h4>
                      <p className="text-sm text-muted-foreground">
                        {item.mode.replace('_', ' ')} • {item.created_at ? new Date(item.created_at).toLocaleString() : 'N/A'}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {getStatusBadge(item.status, item.failed_uploads === 0)}
                      <span className="text-sm text-muted-foreground">
                        {formatDuration(item.duration_seconds)}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Total:</span>
                      <span className="ml-2 font-medium">{item.total_products}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Synced:</span>
                      <span className="ml-2 font-medium text-green-600">{item.successful_uploads}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Failed:</span>
                      <span className="ml-2 font-medium text-red-600">{item.failed_uploads}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Success Rate:</span>
                      <span className="ml-2 font-medium">
                        {item.total_products > 0 ? ((item.successful_uploads / item.total_products) * 100).toFixed(1) : 0}%
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        {/* Products Tab */}
        <TabsContent value="products" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Filter className="h-5 w-5" />
                Product Filters
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="space-y-2">
                  <Label>Import Batch</Label>
                  <Select 
                    value={productFilters.import_batch_id?.toString() || 'all'} 
                    onValueChange={(value) => setProductFilters(prev => ({ 
                      ...prev, 
                      import_batch_id: value === 'all' ? undefined : parseInt(value) 
                    }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All batches" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All batches</SelectItem>
                      {importBatches.map((batch) => (
                        <SelectItem key={batch.id} value={batch.id.toString()}>
                          {batch.filename}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Status</Label>
                  <Select 
                    value={productFilters.status || 'all'} 
                    onValueChange={(value) => setProductFilters(prev => ({ ...prev, status: value === 'all' ? '' : value }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All statuses" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All statuses</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="archived">Archived</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Limit</Label>
                  <Select 
                    value={productFilters.limit.toString()} 
                    onValueChange={(value) => setProductFilters(prev => ({ ...prev, limit: parseInt(value) }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="25">25</SelectItem>
                      <SelectItem value="50">50</SelectItem>
                      <SelectItem value="100">100</SelectItem>
                      <SelectItem value="200">200</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button onClick={loadSyncableProducts} variant="outline">
                <RefreshCw className="h-4 w-4 mr-2" />
                Apply Filters
              </Button>
            </CardContent>
          </Card>

          {isLoadingProducts ? (
            <Card>
              <CardContent className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin" />
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Syncable Products ({syncableProducts.length})</CardTitle>
                <CardDescription>
                  Products available for Shopify synchronization
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {syncableProducts.map((product) => (
                    <div key={product.id} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex-1">
                        <div className="font-medium">{product.title}</div>
                        <div className="text-sm text-muted-foreground">
                          SKU: {product.sku} • Category: {product.category}
                        </div>
                        {product.price && (
                          <div className="text-sm font-medium">${product.price.toFixed(2)}</div>
                        )}
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <div className="text-sm">{getStatusBadge(product.shopify_status)}</div>
                          {product.last_synced && (
                            <div className="text-xs text-muted-foreground">
                              Last synced: {new Date(product.last_synced).toLocaleDateString()}
                            </div>
                          )}
                        </div>
                        {product.has_conflicts && (
                          <Badge variant="destructive" className="text-xs">
                            Conflicts
                          </Badge>
                        )}
                        {product.shopify_id && (
                          <Badge variant="secondary" className="text-xs">
                            In Shopify
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}