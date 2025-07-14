import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { 
  Download,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Filter,
  GitBranch,
  FileText,
  Diff,
  Eye,
  Database,
  Calendar,
  Package,
  TrendingUp
} from 'lucide-react';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { apiClient } from '@/lib/api';
import { OutgoingWebSocketMessage } from '@/types/websocket';

interface ShopifySyncDownProps {
  onSyncComplete?: () => void;
  className?: string;
}

interface SyncDownOptions {
  modifiedSince?: string;
  includeArchived: boolean;
  includeVariants: boolean;
  includeMetafields: boolean;
  includeInventory: boolean;
  detectChanges: boolean;
  batchSize: number;
  collections?: string[];
  productTypes?: string[];
}

interface ChangeDetectionResult {
  totalProducts: number;
  productsWithChanges: number;
  newProducts: number;
  deletedProducts: number;
  changes: ProductChange[];
}

interface ProductChange {
  productId: string;
  sku: string;
  title: string;
  changeType: 'new' | 'modified' | 'deleted';
  fields: string[];
  oldValues?: Record<string, any>;
  newValues?: Record<string, any>;
  timestamp: string;
}

export function ShopifySyncDown({ onSyncComplete, className }: ShopifySyncDownProps) {
  const [activeTab, setActiveTab] = useState<'configure' | 'progress' | 'changes'>('configure');
  const [syncOptions, setSyncOptions] = useState<SyncDownOptions>({
    includeArchived: false,
    includeVariants: true,
    includeMetafields: true,
    includeInventory: true,
    detectChanges: true,
    batchSize: 250
  });
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<string>('');
  const [changeResults, setChangeResults] = useState<ChangeDetectionResult | null>(null);
  const [selectedChanges, setSelectedChanges] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [collections, setCollections] = useState<any[]>([]);
  const [productTypes, setProductTypes] = useState<string[]>([]);
  const { subscribe, subscribeCustom, sendMessage, isConnected } = useWebSocket();

  useEffect(() => {
    loadFilterOptions();
  }, []);

  useEffect(() => {
    if (!isConnected || !isRunning) return;

    const unsubscribeProgress = subscribeCustom('shopify-sync-down-progress', (data: any) => {
      setProgress(data.progress);
      setStatus(data.status);
      
      if (data.completed) {
        setIsRunning(false);
        if (data.changeResults) {
          setChangeResults(data.changeResults);
          setActiveTab('changes');
        }
      }
    });

    const unsubscribeError = subscribeCustom('shopify-sync-down-error', (data: any) => {
      setError(data.message);
      setIsRunning(false);
    });

    return () => {
      unsubscribeProgress();
      unsubscribeError();
    };
  }, [subscribe, isConnected, isRunning]);

  const loadFilterOptions = async () => {
    try {
      const [collectionsData, typesData] = await Promise.all([
        apiClient.getShopifyCollections(),
        apiClient.getProductTypes()
      ]);
      setCollections(collectionsData.collections || []);
      setProductTypes(typesData.types || []);
    } catch (err) {
      console.error('Failed to load filter options:', err);
      // Don't show error to user - filters are optional
      setCollections([]);
      setProductTypes([]);
    }
  };

  const handleOptionChange = (field: keyof SyncDownOptions, value: any) => {
    setSyncOptions(prev => ({ ...prev, [field]: value }));
  };

  const handleStartSync = async () => {
    setError(null);
    setIsRunning(true);
    setProgress(0);
    setStatus('Initializing sync...');
    setActiveTab('progress');
    setChangeResults(null);
    setSelectedChanges(new Set());

    try {
      const response = await apiClient.startShopifySyncDown(syncOptions);
      
      if (response.sync_id) {
        // WebSocket will handle progress updates if connected
        if (isConnected) {
          sendMessage({
            type: 'monitor-sync',
            syncId: response.sync_id
          } as OutgoingWebSocketMessage);
        } else {
          // Fallback: poll for status if WebSocket is not available
          console.log('WebSocket not connected, will poll for updates');
        }
      }
    } catch (err) {
      console.error('Sync down error:', err);
      setError(err instanceof Error ? err.message : 'Failed to start sync');
      setIsRunning(false);
    }
  };

  const handleCancelSync = () => {
    sendMessage({
      type: 'cancel-sync',
      syncType: 'shopify-down'
    } as OutgoingWebSocketMessage);
    setIsRunning(false);
  };

  const handleChangeSelection = (changeId: string, selected: boolean) => {
    setSelectedChanges(prev => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(changeId);
      } else {
        newSet.delete(changeId);
      }
      return newSet;
    });
  };

  const handleSelectAllChanges = (selected: boolean) => {
    if (selected && changeResults) {
      setSelectedChanges(new Set(changeResults.changes.map(c => c.productId)));
    } else {
      setSelectedChanges(new Set());
    }
  };

  const handleApproveChanges = async () => {
    if (selectedChanges.size === 0) return;

    try {
      await apiClient.stageProductChanges({
        productIds: Array.from(selectedChanges),
        source: 'shopify-sync-down'
      });

      if (onSyncComplete) {
        onSyncComplete();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stage changes');
    }
  };

  const getChangeTypeIcon = (type: string) => {
    switch (type) {
      case 'new':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'modified':
        return <Diff className="h-4 w-4 text-blue-500" />;
      case 'deleted':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getChangeTypeBadge = (type: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      new: 'default',
      modified: 'secondary',
      deleted: 'destructive'
    };
    return <Badge variant={variants[type] || 'secondary'}>{type}</Badge>;
  };

  return (
    <div className={cn("space-y-6", className)}>
      {error && (
        <Alert variant="destructive">
          <XCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="configure" disabled={isRunning}>
            <Filter className="h-4 w-4 mr-2" />
            Configure
          </TabsTrigger>
          <TabsTrigger value="progress" disabled={!isRunning && !changeResults}>
            <Download className="h-4 w-4 mr-2" />
            Progress
          </TabsTrigger>
          <TabsTrigger value="changes" disabled={!changeResults}>
            <GitBranch className="h-4 w-4 mr-2" />
            Changes ({changeResults?.productsWithChanges || 0})
          </TabsTrigger>
        </TabsList>

        {/* Configure Tab */}
        <TabsContent value="configure" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Sync Configuration</CardTitle>
              <CardDescription>
                Configure how to pull product data from Shopify with change detection
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Time Filter */}
              <div className="space-y-2">
                <Label htmlFor="modified-since">Modified Since (Optional)</Label>
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <Input
                    id="modified-since"
                    type="datetime-local"
                    value={syncOptions.modifiedSince || ''}
                    onChange={(e) => handleOptionChange('modifiedSince', e.target.value)}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Only sync products modified after this date/time
                </p>
              </div>

              {/* Collection Filter */}
              <div className="space-y-2">
                <Label>Collections (Optional)</Label>
                <Select
                  value={syncOptions.collections?.join(',') || 'all'}
                  onValueChange={(value) => handleOptionChange('collections', value === 'all' ? undefined : value.split(','))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All collections" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All collections</SelectItem>
                    {collections.map((collection) => (
                      <SelectItem key={collection.id} value={collection.id}>
                        {collection.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Product Type Filter */}
              <div className="space-y-2">
                <Label>Product Types (Optional)</Label>
                <Select
                  value={syncOptions.productTypes?.join(',') || 'all'}
                  onValueChange={(value) => handleOptionChange('productTypes', value === 'all' ? undefined : value.split(','))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All product types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All product types</SelectItem>
                    {productTypes.map((type) => (
                      <SelectItem key={type} value={type}>
                        {type}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Sync Options */}
              <div className="space-y-3">
                <Label>Sync Options</Label>
                <div className="space-y-3">
                  <div className="flex items-center space-x-3">
                    <Checkbox
                      id="include-archived"
                      checked={syncOptions.includeArchived}
                      onCheckedChange={(checked) => handleOptionChange('includeArchived', checked)}
                    />
                    <div className="grid gap-1.5 leading-none">
                      <label htmlFor="include-archived" className="text-sm font-medium">
                        Include Archived Products
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Sync products that are archived in Shopify
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <Checkbox
                      id="include-variants"
                      checked={syncOptions.includeVariants}
                      onCheckedChange={(checked) => handleOptionChange('includeVariants', checked)}
                    />
                    <div className="grid gap-1.5 leading-none">
                      <label htmlFor="include-variants" className="text-sm font-medium">
                        Include All Variants
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Sync all product variants and their details
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <Checkbox
                      id="include-metafields"
                      checked={syncOptions.includeMetafields}
                      onCheckedChange={(checked) => handleOptionChange('includeMetafields', checked)}
                    />
                    <div className="grid gap-1.5 leading-none">
                      <label htmlFor="include-metafields" className="text-sm font-medium">
                        Include Metafields
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Sync custom metafield data
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <Checkbox
                      id="include-inventory"
                      checked={syncOptions.includeInventory}
                      onCheckedChange={(checked) => handleOptionChange('includeInventory', checked)}
                    />
                    <div className="grid gap-1.5 leading-none">
                      <label htmlFor="include-inventory" className="text-sm font-medium">
                        Include Inventory Levels
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Sync current inventory quantities
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <Checkbox
                      id="detect-changes"
                      checked={syncOptions.detectChanges}
                      onCheckedChange={(checked) => handleOptionChange('detectChanges', checked)}
                    />
                    <div className="grid gap-1.5 leading-none">
                      <label htmlFor="detect-changes" className="text-sm font-medium">
                        Enable Change Detection
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Compare with existing data to detect changes
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Batch Size */}
              <div className="space-y-2">
                <Label htmlFor="batch-size">Batch Size</Label>
                <Select
                  value={syncOptions.batchSize.toString()}
                  onValueChange={(value) => handleOptionChange('batchSize', parseInt(value))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="50">50 products per batch</SelectItem>
                    <SelectItem value="100">100 products per batch</SelectItem>
                    <SelectItem value="250">250 products per batch</SelectItem>
                    <SelectItem value="500">500 products per batch</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button 
                onClick={handleStartSync}
                disabled={isRunning || !isConnected}
                className="w-full"
              >
                {isRunning ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    Syncing...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4 mr-2" />
                    Start Sync Down
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Progress Tab */}
        <TabsContent value="progress" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Sync Progress</CardTitle>
              <CardDescription>{status}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>Overall Progress</span>
                  <span>{progress.toFixed(1)}%</span>
                </div>
                <Progress value={progress} />
              </div>

              {isRunning && (
                <div className="flex items-center justify-center py-8">
                  <div className="text-center space-y-4">
                    <RefreshCw className="h-8 w-8 mx-auto text-primary animate-spin" />
                    <p className="text-sm text-muted-foreground">
                      Pulling product data from Shopify...
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCancelSync}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {!isRunning && changeResults && (
                <Alert>
                  <CheckCircle className="h-4 w-4" />
                  <AlertDescription>
                    Sync completed! Found {changeResults.productsWithChanges} products with changes.
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Changes Tab */}
        <TabsContent value="changes" className="space-y-6">
          {changeResults && (
            <>
              {/* Summary Card */}
              <Card>
                <CardHeader>
                  <CardTitle>Change Summary</CardTitle>
                  <CardDescription>
                    Review detected changes before staging
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-4 gap-4">
                    <div className="text-center">
                      <Database className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                      <p className="text-2xl font-bold">{changeResults.totalProducts}</p>
                      <p className="text-xs text-muted-foreground">Total Products</p>
                    </div>
                    <div className="text-center">
                      <Diff className="h-8 w-8 mx-auto text-blue-500 mb-2" />
                      <p className="text-2xl font-bold">{changeResults.productsWithChanges}</p>
                      <p className="text-xs text-muted-foreground">With Changes</p>
                    </div>
                    <div className="text-center">
                      <TrendingUp className="h-8 w-8 mx-auto text-green-500 mb-2" />
                      <p className="text-2xl font-bold">{changeResults.newProducts}</p>
                      <p className="text-xs text-muted-foreground">New Products</p>
                    </div>
                    <div className="text-center">
                      <XCircle className="h-8 w-8 mx-auto text-red-500 mb-2" />
                      <p className="text-2xl font-bold">{changeResults.deletedProducts}</p>
                      <p className="text-xs text-muted-foreground">Deleted</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Changes List */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Product Changes</CardTitle>
                      <CardDescription>
                        Select changes to stage for review
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <Checkbox
                        checked={selectedChanges.size === changeResults.changes.length}
                        onCheckedChange={handleSelectAllChanges}
                      />
                      <Label className="text-sm font-normal">Select All</Label>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {changeResults.changes.map((change) => (
                      <div key={change.productId} className="border rounded-lg p-4">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-3">
                            <Checkbox
                              checked={selectedChanges.has(change.productId)}
                              onCheckedChange={(checked) => handleChangeSelection(change.productId, checked as boolean)}
                            />
                            <div className="space-y-2">
                              <div className="flex items-center gap-2">
                                {getChangeTypeIcon(change.changeType)}
                                <h4 className="font-medium">{change.title}</h4>
                                {getChangeTypeBadge(change.changeType)}
                              </div>
                              <p className="text-sm text-muted-foreground">
                                SKU: {change.sku} • Product ID: {change.productId}
                              </p>
                              {change.fields.length > 0 && (
                                <div className="text-sm">
                                  <span className="font-medium">Changed fields:</span>{' '}
                                  <span className="text-muted-foreground">
                                    {change.fields.join(', ')}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              // TODO: Implement preview modal
                              console.log('Preview change:', change);
                            }}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>

                  {selectedChanges.size > 0 && (
                    <div className="mt-6 flex items-center justify-between border-t pt-6">
                      <p className="text-sm text-muted-foreground">
                        {selectedChanges.size} changes selected
                      </p>
                      <Button
                        onClick={handleApproveChanges}
                        disabled={selectedChanges.size === 0}
                      >
                        <GitBranch className="h-4 w-4 mr-2" />
                        Stage Selected Changes
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}