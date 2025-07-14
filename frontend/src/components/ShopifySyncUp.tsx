import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { 
  Upload,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Package,
  Zap,
  Shield,
  Activity,
  FileText,
  GitCommit,
  Send,
  Pause,
  Play,
  SkipForward
} from 'lucide-react';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { apiClient } from '@/lib/api';
import { OutgoingWebSocketMessage } from '@/types/websocket';

interface ShopifySyncUpProps {
  onSyncComplete?: () => void;
  className?: string;
}

interface SyncUpOptions {
  batchSize: number;
  parallelWorkers: number;
  validateBeforeUpload: boolean;
  updateInventory: boolean;
  updatePricing: boolean;
  updateMetafields: boolean;
  publishProducts: boolean;
  retryFailedUploads: boolean;
  maxRetries: number;
}

interface UploadBatch {
  id: string;
  batchNumber: number;
  totalBatches: number;
  products: UploadProduct[];
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'partial';
  startTime?: string;
  endTime?: string;
  successCount: number;
  failureCount: number;
  errors: UploadError[];
}

interface UploadProduct {
  id: string;
  sku: string;
  title: string;
  status: 'pending' | 'uploading' | 'success' | 'failed' | 'skipped';
  error?: string;
  retryCount: number;
  uploadTime?: number;
}

interface UploadError {
  productId: string;
  sku: string;
  error: string;
  timestamp: string;
  retryable: boolean;
}

interface SyncMetrics {
  totalProducts: number;
  uploadedProducts: number;
  failedProducts: number;
  skippedProducts: number;
  averageUploadTime: number;
  estimatedTimeRemaining: number;
  throughput: number;
}

export function ShopifySyncUp({ onSyncComplete, className }: ShopifySyncUpProps) {
  const [activeTab, setActiveTab] = useState<'ready' | 'progress' | 'results'>('ready');
  const [syncOptions, setSyncOptions] = useState<SyncUpOptions>({
    batchSize: 10,
    parallelWorkers: 3,
    validateBeforeUpload: true,
    updateInventory: true,
    updatePricing: true,
    updateMetafields: true,
    publishProducts: false,
    retryFailedUploads: true,
    maxRetries: 3
  });
  const [approvedProducts, setApprovedProducts] = useState<any[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set());
  const [isRunning, setIsRunning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentBatch, setCurrentBatch] = useState<UploadBatch | null>(null);
  const [completedBatches, setCompletedBatches] = useState<UploadBatch[]>([]);
  const [syncMetrics, setSyncMetrics] = useState<SyncMetrics>({
    totalProducts: 0,
    uploadedProducts: 0,
    failedProducts: 0,
    skippedProducts: 0,
    averageUploadTime: 0,
    estimatedTimeRemaining: 0,
    throughput: 0
  });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const { subscribe, subscribeCustom, sendMessage, isConnected } = useWebSocket();

  useEffect(() => {
    loadApprovedProducts();
  }, []);

  useEffect(() => {
    if (!isConnected || !isRunning) return;

    const unsubscribeBatch = subscribeCustom('shopify-sync-up-batch', (data: any) => {
      setCurrentBatch(data.batch);
      setSyncMetrics(data.metrics);
    });

    const unsubscribeBatchComplete = subscribeCustom('shopify-sync-up-batch-complete', (data: any) => {
      setCompletedBatches(prev => [...prev, data.batch]);
      
      if (data.isLastBatch) {
        handleSyncComplete();
      }
    });

    const unsubscribeError = subscribeCustom('shopify-sync-up-error', (data: any) => {
      setError(data.message);
      setIsRunning(false);
    });

    return () => {
      unsubscribeBatch();
      unsubscribeBatchComplete();
      unsubscribeError();
    };
  }, [subscribe, isConnected, isRunning]);

  const loadApprovedProducts = async () => {
    try {
      const response = await apiClient.getApprovedProducts();
      setApprovedProducts(response.products);
      setSyncMetrics(prev => ({
        ...prev,
        totalProducts: response.products.length
      }));
      // Select all by default
      setSelectedProducts(new Set(response.products.map((p: any) => p.id)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load approved products');
    }
  };

  const handleOptionChange = (field: keyof SyncUpOptions, value: any) => {
    setSyncOptions(prev => ({ ...prev, [field]: value }));
  };

  const handleProductSelection = (productId: string, selected: boolean) => {
    setSelectedProducts(prev => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(productId);
      } else {
        newSet.delete(productId);
      }
      return newSet;
    });
  };

  const handleSelectAll = (selected: boolean) => {
    if (selected) {
      setSelectedProducts(new Set(approvedProducts.map(p => p.id)));
    } else {
      setSelectedProducts(new Set());
    }
  };

  const handleStartSync = async () => {
    if (selectedProducts.size === 0) {
      setError('Please select at least one product to sync');
      return;
    }

    setError(null);
    setSuccess(null);
    setIsRunning(true);
    setIsPaused(false);
    setActiveTab('progress');
    setCompletedBatches([]);

    try {
      const response = await apiClient.startShopifySyncUp({
        productIds: Array.from(selectedProducts),
        options: syncOptions
      });

      if (response.sync_id) {
        sendMessage({
          type: 'monitor-sync-up',
          syncId: response.sync_id
        } as OutgoingWebSocketMessage);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start sync');
      setIsRunning(false);
    }
  };

  const handlePauseSync = () => {
    sendMessage({
      type: 'pause-sync-up'
    } as OutgoingWebSocketMessage);
    setIsPaused(true);
  };

  const handleResumeSync = () => {
    sendMessage({
      type: 'resume-sync-up'
    } as OutgoingWebSocketMessage);
    setIsPaused(false);
  };

  const handleCancelSync = () => {
    sendMessage({
      type: 'cancel-sync-up'
    } as OutgoingWebSocketMessage);
    setIsRunning(false);
    setIsPaused(false);
  };

  const handleRetryFailed = async () => {
    const failedProducts = completedBatches
      .flatMap(b => b.products)
      .filter(p => p.status === 'failed')
      .map(p => p.id);

    if (failedProducts.length === 0) return;

    try {
      await apiClient.retryFailedUploads(failedProducts);
      setSuccess(`Retrying ${failedProducts.length} failed uploads`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retry uploads');
    }
  };

  const handleSyncComplete = () => {
    setIsRunning(false);
    setSuccess('Sync completed successfully!');
    setActiveTab('results');
    
    if (onSyncComplete) {
      onSyncComplete();
    }
  };

  const getProductStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="h-4 w-4 text-gray-500" />;
      case 'uploading':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'skipped':
        return <SkipForward className="h-4 w-4 text-yellow-500" />;
      default:
        return null;
    }
  };

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
  };

  const overallProgress = syncMetrics.totalProducts > 0
    ? ((syncMetrics.uploadedProducts + syncMetrics.failedProducts + syncMetrics.skippedProducts) / syncMetrics.totalProducts) * 100
    : 0;

  return (
    <div className={cn("space-y-6", className)}>
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
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="ready" disabled={isRunning}>
            <Package className="h-4 w-4 mr-2" />
            Ready ({selectedProducts.size})
          </TabsTrigger>
          <TabsTrigger value="progress" disabled={!isRunning && completedBatches.length === 0}>
            <Upload className="h-4 w-4 mr-2" />
            Progress
          </TabsTrigger>
          <TabsTrigger value="results" disabled={completedBatches.length === 0}>
            <Activity className="h-4 w-4 mr-2" />
            Results
          </TabsTrigger>
        </TabsList>

        {/* Ready Tab */}
        <TabsContent value="ready" className="space-y-6">
          {/* Configuration */}
          <Card>
            <CardHeader>
              <CardTitle>Upload Configuration</CardTitle>
              <CardDescription>Configure how products will be synced to Shopify</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="batch-size">Batch Size</Label>
                    <select
                      id="batch-size"
                      className="w-full h-10 px-3 border rounded-md"
                      value={syncOptions.batchSize}
                      onChange={(e) => handleOptionChange('batchSize', parseInt(e.target.value))}
                    >
                      <option value="5">5 products per batch</option>
                      <option value="10">10 products per batch</option>
                      <option value="25">25 products per batch</option>
                      <option value="50">50 products per batch</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="parallel-workers">Parallel Workers</Label>
                    <select
                      id="parallel-workers"
                      className="w-full h-10 px-3 border rounded-md"
                      value={syncOptions.parallelWorkers}
                      onChange={(e) => handleOptionChange('parallelWorkers', parseInt(e.target.value))}
                    >
                      <option value="1">1 worker (slowest, safest)</option>
                      <option value="3">3 workers (balanced)</option>
                      <option value="5">5 workers (fast)</option>
                      <option value="10">10 workers (fastest)</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center space-x-3">
                    <Checkbox
                      id="validate-before"
                      checked={syncOptions.validateBeforeUpload}
                      onCheckedChange={(checked) => handleOptionChange('validateBeforeUpload', checked)}
                    />
                    <div className="grid gap-1.5 leading-none">
                      <label htmlFor="validate-before" className="text-sm font-medium">
                        Validate Before Upload
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Check data integrity before sending
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <Checkbox
                      id="update-inventory"
                      checked={syncOptions.updateInventory}
                      onCheckedChange={(checked) => handleOptionChange('updateInventory', checked)}
                    />
                    <div className="grid gap-1.5 leading-none">
                      <label htmlFor="update-inventory" className="text-sm font-medium">
                        Update Inventory
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Sync inventory levels
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <Checkbox
                      id="publish-products"
                      checked={syncOptions.publishProducts}
                      onCheckedChange={(checked) => handleOptionChange('publishProducts', checked)}
                    />
                    <div className="grid gap-1.5 leading-none">
                      <label htmlFor="publish-products" className="text-sm font-medium">
                        Auto-Publish Products
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Make products visible immediately
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Product Selection */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Products to Sync</CardTitle>
                  <CardDescription>Select which approved products to upload</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={selectedProducts.size === approvedProducts.length && approvedProducts.length > 0}
                    onCheckedChange={handleSelectAll}
                  />
                  <Label className="text-sm font-normal">Select All</Label>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px]">
                <div className="space-y-2">
                  {approvedProducts.map((product) => (
                    <div key={product.id} className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50">
                      <div className="flex items-center gap-3">
                        <Checkbox
                          checked={selectedProducts.has(product.id)}
                          onCheckedChange={(checked) => handleProductSelection(product.id, checked as boolean)}
                        />
                        <div>
                          <p className="font-medium">{product.title}</p>
                          <p className="text-sm text-muted-foreground">
                            SKU: {product.sku} • ${product.price}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {product.hasVariants && (
                          <Badge variant="outline">{product.variantCount} variants</Badge>
                        )}
                        {product.changeType && (
                          <Badge variant="secondary">{product.changeType}</Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>

              {selectedProducts.size > 0 && (
                <div className="mt-4 pt-4 border-t">
                  <Button
                    onClick={handleStartSync}
                    disabled={isRunning}
                    className="w-full"
                  >
                    <Upload className="h-4 w-4 mr-2" />
                    Start Upload ({selectedProducts.size} products)
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Progress Tab */}
        <TabsContent value="progress" className="space-y-6">
          {/* Overall Progress */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Upload Progress</CardTitle>
                  <CardDescription>
                    {isRunning ? (isPaused ? 'Upload paused' : 'Uploading products to Shopify...') : 'Upload complete'}
                  </CardDescription>
                </div>
                {isRunning && (
                  <div className="flex items-center gap-2">
                    {isPaused ? (
                      <Button size="sm" variant="outline" onClick={handleResumeSync}>
                        <Play className="h-4 w-4 mr-1" />
                        Resume
                      </Button>
                    ) : (
                      <Button size="sm" variant="outline" onClick={handlePauseSync}>
                        <Pause className="h-4 w-4 mr-1" />
                        Pause
                      </Button>
                    )}
                    <Button size="sm" variant="destructive" onClick={handleCancelSync}>
                      <XCircle className="h-4 w-4 mr-1" />
                      Cancel
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>Overall Progress</span>
                  <span>{overallProgress.toFixed(1)}%</span>
                </div>
                <Progress value={overallProgress} />
              </div>

              <div className="grid grid-cols-4 gap-4">
                <div className="text-center">
                  <Zap className="h-6 w-6 mx-auto text-muted-foreground mb-1" />
                  <p className="text-2xl font-bold">{syncMetrics.throughput.toFixed(1)}</p>
                  <p className="text-xs text-muted-foreground">Products/min</p>
                </div>
                <div className="text-center">
                  <CheckCircle className="h-6 w-6 mx-auto text-green-500 mb-1" />
                  <p className="text-2xl font-bold">{syncMetrics.uploadedProducts}</p>
                  <p className="text-xs text-muted-foreground">Uploaded</p>
                </div>
                <div className="text-center">
                  <XCircle className="h-6 w-6 mx-auto text-red-500 mb-1" />
                  <p className="text-2xl font-bold">{syncMetrics.failedProducts}</p>
                  <p className="text-xs text-muted-foreground">Failed</p>
                </div>
                <div className="text-center">
                  <Clock className="h-6 w-6 mx-auto text-blue-500 mb-1" />
                  <p className="text-2xl font-bold">{formatTime(syncMetrics.estimatedTimeRemaining)}</p>
                  <p className="text-xs text-muted-foreground">Remaining</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Current Batch */}
          {currentBatch && (
            <Card>
              <CardHeader>
                <CardTitle>
                  Current Batch ({currentBatch.batchNumber} of {currentBatch.totalBatches})
                </CardTitle>
                <CardDescription>
                  Processing {currentBatch.products.length} products
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {currentBatch.products.map((product) => (
                    <div key={product.id} className="flex items-center justify-between p-2 border rounded">
                      <div className="flex items-center gap-2">
                        {getProductStatusIcon(product.status)}
                        <span className="text-sm font-medium">{product.title}</span>
                        <span className="text-xs text-muted-foreground">({product.sku})</span>
                      </div>
                      {product.error && (
                        <span className="text-xs text-red-600">{product.error}</span>
                      )}
                      {product.uploadTime && (
                        <span className="text-xs text-muted-foreground">{product.uploadTime}ms</span>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Results Tab */}
        <TabsContent value="results" className="space-y-6">
          {/* Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Upload Summary</CardTitle>
              <CardDescription>Final results of the sync operation</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-4 gap-4">
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-center">
                      <Package className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                      <p className="text-2xl font-bold">{syncMetrics.totalProducts}</p>
                      <p className="text-xs text-muted-foreground">Total Products</p>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-center">
                      <CheckCircle className="h-8 w-8 mx-auto text-green-500 mb-2" />
                      <p className="text-2xl font-bold text-green-600">{syncMetrics.uploadedProducts}</p>
                      <p className="text-xs text-muted-foreground">Successfully Uploaded</p>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-center">
                      <XCircle className="h-8 w-8 mx-auto text-red-500 mb-2" />
                      <p className="text-2xl font-bold text-red-600">{syncMetrics.failedProducts}</p>
                      <p className="text-xs text-muted-foreground">Failed</p>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-center">
                      <SkipForward className="h-8 w-8 mx-auto text-yellow-500 mb-2" />
                      <p className="text-2xl font-bold text-yellow-600">{syncMetrics.skippedProducts}</p>
                      <p className="text-xs text-muted-foreground">Skipped</p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              <div className="mt-6 pt-6 border-t">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">Success Rate</p>
                    <p className="text-2xl font-bold">
                      {syncMetrics.totalProducts > 0 
                        ? ((syncMetrics.uploadedProducts / syncMetrics.totalProducts) * 100).toFixed(1)
                        : 0}%
                    </p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Average Upload Time</p>
                    <p className="text-2xl font-bold">{syncMetrics.averageUploadTime.toFixed(0)}ms</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Total Duration</p>
                    <p className="text-2xl font-bold">
                      {formatTime(Math.floor((Date.now() - (completedBatches[0]?.startTime ? new Date(completedBatches[0].startTime).getTime() : Date.now())) / 1000))}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Failed Uploads */}
          {syncMetrics.failedProducts > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Failed Uploads</CardTitle>
                    <CardDescription>Products that couldn't be uploaded</CardDescription>
                  </div>
                  <Button size="sm" onClick={handleRetryFailed}>
                    <RefreshCw className="h-4 w-4 mr-1" />
                    Retry Failed
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px]">
                  <div className="space-y-2">
                    {completedBatches.flatMap(batch => 
                      batch.errors.map((error, idx) => (
                        <Alert key={`${batch.id}-${idx}`} variant="destructive">
                          <XCircle className="h-4 w-4" />
                          <AlertDescription>
                            <div className="flex items-center justify-between">
                              <div>
                                <span className="font-medium">SKU: {error.sku}</span>
                                <p className="text-sm mt-1">{error.error}</p>
                              </div>
                              {error.retryable && (
                                <Badge variant="outline">Retryable</Badge>
                              )}
                            </div>
                          </AlertDescription>
                        </Alert>
                      ))
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}