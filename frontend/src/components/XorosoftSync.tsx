import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  Truck,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Package,
  BarChart,
  TrendingUp,
  TrendingDown,
  Minus,
  Settings,
  Calendar,
  ArrowUpDown,
  Database,
  GitCompare
} from 'lucide-react';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { apiClient } from '@/lib/api';

interface XorosoftSyncProps {
  className?: string;
}

interface XorosoftConfig {
  apiUrl: string;
  apiKey: string;
  syncMode: 'full' | 'incremental' | 'changes-only';
  syncSchedule: 'manual' | 'hourly' | 'daily' | 'realtime';
  inventoryThreshold: number;
  priceUpdateEnabled: boolean;
  stockUpdateEnabled: boolean;
  locationMapping: Record<string, string>;
}

interface InventoryItem {
  sku: string;
  productTitle: string;
  currentStock: number;
  xorosoftStock: number;
  difference: number;
  lastUpdated: string;
  location: string;
  status: 'in-sync' | 'needs-update' | 'low-stock' | 'out-of-stock';
}

interface SyncResult {
  totalItems: number;
  updatedItems: number;
  failedItems: number;
  skippedItems: number;
  duration: number;
  timestamp: string;
}

interface StockMovement {
  sku: string;
  type: 'increase' | 'decrease' | 'adjustment';
  quantity: number;
  previousStock: number;
  newStock: number;
  reason: string;
  timestamp: string;
}

export function XorosoftSync({ className }: XorosoftSyncProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'inventory' | 'sync' | 'history' | 'settings'>('overview');
  const [config, setConfig] = useState<XorosoftConfig>({
    apiUrl: '',
    apiKey: '',
    syncMode: 'incremental',
    syncSchedule: 'manual',
    inventoryThreshold: 10,
    priceUpdateEnabled: false,
    stockUpdateEnabled: true,
    locationMapping: {}
  });
  const [inventoryItems, setInventoryItems] = useState<InventoryItem[]>([]);
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [syncResults, setSyncResults] = useState<SyncResult[]>([]);
  const [stockMovements, setStockMovements] = useState<StockMovement[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [lastSyncTime, setLastSyncTime] = useState<string | null>(null);
  const { subscribeCustom, sendMessage, isConnected: wsConnected } = useWebSocket();

  useEffect(() => {
    checkConnection();
    loadInventoryComparison();
    loadSyncHistory();
  }, []);

  useEffect(() => {
    if (!wsConnected) return;

    const unsubscribeInventoryUpdate = subscribeCustom('xorosoft-inventory-update', (data: any) => {
      setInventoryItems(prev => {
        const updated = [...prev];
        const index = updated.findIndex(item => item.sku === data.sku);
        if (index >= 0) {
          updated[index] = { ...updated[index], ...data };
        }
        return updated;
      });
    });

    const unsubscribeSyncProgress = subscribeCustom('xorosoft-sync-progress', (data: any) => {
      if (data.completed) {
        setIsSyncing(false);
        setSyncResults(prev => [data.result, ...prev]);
        setSuccess(`Sync completed: ${data.result.updatedItems} items updated`);
        loadInventoryComparison();
      }
    });

    const unsubscribeStockMovement = subscribeCustom('xorosoft-stock-movement', (data: any) => {
      setStockMovements(prev => [data as StockMovement, ...prev.slice(0, 99)]);
    });

    return () => {
      unsubscribeInventoryUpdate();
      unsubscribeSyncProgress();
      unsubscribeStockMovement();
    };
  }, [subscribeCustom, wsConnected]);

  const checkConnection = async () => {
    try {
      const status = await apiClient.checkXorosoftConnection();
      setIsConnected(status.connected);
      if (status.lastSync) {
        setLastSyncTime(status.lastSync);
      }
    } catch (err) {
      setIsConnected(false);
      setError('Failed to connect to Xorosoft');
    }
  };

  const loadInventoryComparison = async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.getXorosoftInventoryComparison();
      // Ensure each item has the required properties with defaults
      const inventoryItems = response.items.map(item => ({
        sku: item.sku || '',
        productTitle: item.productTitle || '',
        currentStock: item.currentStock || 0,
        xorosoftStock: item.xorosoftStock || 0,
        difference: item.difference || 0,
        lastUpdated: item.lastUpdated || new Date().toISOString(),
        location: item.location || '',
        status: item.status || 'needs-update' as const
      }));
      setInventoryItems(inventoryItems);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load inventory comparison');
    } finally {
      setIsLoading(false);
    }
  };

  const loadSyncHistory = async () => {
    try {
      const response = await apiClient.getXorosoftSyncHistory();
      // Ensure each result has the required properties with defaults
      const syncResults = response.results.map(result => ({
        totalItems: result.totalItems || 0,
        updatedItems: result.updatedItems || 0,
        failedItems: result.failedItems || 0,
        skippedItems: result.skippedItems || 0,
        duration: result.duration || 0,
        timestamp: result.timestamp || new Date().toISOString()
      }));
      
      const stockMovements = response.movements.map(movement => ({
        sku: movement.sku || '',
        type: movement.type || 'adjustment' as const,
        quantity: movement.quantity || 0,
        previousStock: movement.previousStock || 0,
        newStock: movement.newStock || 0,
        reason: movement.reason || '',
        timestamp: movement.timestamp || new Date().toISOString()
      }));
      
      setSyncResults(syncResults);
      setStockMovements(stockMovements);
    } catch (err) {
      console.error('Failed to load sync history:', err);
    }
  };

  const handleConfigChange = (field: keyof XorosoftConfig, value: any) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const handleItemSelection = (sku: string, selected: boolean) => {
    setSelectedItems(prev => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(sku);
      } else {
        newSet.delete(sku);
      }
      return newSet;
    });
  };

  const handleSelectAll = (selected: boolean) => {
    if (selected) {
      setSelectedItems(new Set(inventoryItems.map(item => item.sku)));
    } else {
      setSelectedItems(new Set());
    }
  };

  const handleSyncInventory = async (mode?: 'full' | 'selected') => {
    if (mode === 'selected' && selectedItems.size === 0) {
      setError('Please select items to sync');
      return;
    }

    setError(null);
    setIsSyncing(true);

    try {
      const response = await apiClient.startXorosoftSync({
        mode: mode === 'selected' ? 'selected' : config.syncMode,
        skus: mode === 'selected' ? Array.from(selectedItems) : undefined,
        updateStock: config.stockUpdateEnabled,
        updatePrice: config.priceUpdateEnabled
      });

      sendMessage({
        type: 'monitor-xorosoft-sync',
        data: {
          syncId: response.sync_id
        }
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start sync');
      setIsSyncing(false);
    }
  };

  const saveConfiguration = async () => {
    try {
      await apiClient.saveXorosoftConfig(config);
      setSuccess('Configuration saved successfully');
      checkConnection();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    }
  };

  const getStockStatusIcon = (status: string) => {
    switch (status) {
      case 'in-sync':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'needs-update':
        return <RefreshCw className="h-4 w-4 text-blue-500" />;
      case 'low-stock':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'out-of-stock':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getStockMovementIcon = (type: string) => {
    switch (type) {
      case 'increase':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'decrease':
        return <TrendingDown className="h-4 w-4 text-red-500" />;
      case 'adjustment':
        return <ArrowUpDown className="h-4 w-4 text-blue-500" />;
      default:
        return null;
    }
  };

  const inventoryStats = {
    total: inventoryItems.length,
    inSync: inventoryItems.filter(i => i.status === 'in-sync').length,
    needsUpdate: inventoryItems.filter(i => i.status === 'needs-update').length,
    lowStock: inventoryItems.filter(i => i.status === 'low-stock').length,
    outOfStock: inventoryItems.filter(i => i.status === 'out-of-stock').length
  };

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

      {/* Connection Status */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Xorosoft Connection</CardTitle>
            <Button
              size="sm"
              variant="outline"
              onClick={checkConnection}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {isConnected ? (
                <Database className="h-6 w-6 text-green-500" />
              ) : (
                <Database className="h-6 w-6 text-red-500" />
              )}
              <div>
                <p className="font-medium">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </p>
                {lastSyncTime && (
                  <p className="text-sm text-muted-foreground">
                    Last sync: {new Date(lastSyncTime).toLocaleString()}
                  </p>
                )}
              </div>
            </div>
            {isSyncing && (
              <Badge variant="default">
                <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                Syncing
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <BarChart className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="inventory" className="flex items-center gap-2">
            <Package className="h-4 w-4" />
            Inventory
          </TabsTrigger>
          <TabsTrigger value="sync" className="flex items-center gap-2">
            <RefreshCw className="h-4 w-4" />
            Sync
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            History
          </TabsTrigger>
          <TabsTrigger value="settings" className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Settings
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Inventory Stats */}
          <div className="grid grid-cols-5 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <Package className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-2xl font-bold">{inventoryStats.total}</p>
                  <p className="text-xs text-muted-foreground">Total Items</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <CheckCircle className="h-8 w-8 mx-auto text-green-500 mb-2" />
                  <p className="text-2xl font-bold text-green-600">{inventoryStats.inSync}</p>
                  <p className="text-xs text-muted-foreground">In Sync</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <RefreshCw className="h-8 w-8 mx-auto text-blue-500 mb-2" />
                  <p className="text-2xl font-bold text-blue-600">{inventoryStats.needsUpdate}</p>
                  <p className="text-xs text-muted-foreground">Needs Update</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <AlertTriangle className="h-8 w-8 mx-auto text-yellow-500 mb-2" />
                  <p className="text-2xl font-bold text-yellow-600">{inventoryStats.lowStock}</p>
                  <p className="text-xs text-muted-foreground">Low Stock</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <XCircle className="h-8 w-8 mx-auto text-red-500 mb-2" />
                  <p className="text-2xl font-bold text-red-600">{inventoryStats.outOfStock}</p>
                  <p className="text-xs text-muted-foreground">Out of Stock</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Recent Stock Movements */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Stock Movements</CardTitle>
              <CardDescription>Latest inventory changes</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[300px]">
                {stockMovements.length === 0 ? (
                  <div className="text-center py-8">
                    <ArrowUpDown className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                    <p className="text-muted-foreground">No recent movements</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {stockMovements.slice(0, 10).map((movement, idx) => (
                      <div key={idx} className="flex items-center justify-between p-3 border rounded-lg">
                        <div className="flex items-center gap-3">
                          {getStockMovementIcon(movement.type)}
                          <div>
                            <p className="font-medium">{movement.sku}</p>
                            <p className="text-sm text-muted-foreground">
                              {movement.previousStock} → {movement.newStock} ({movement.type === 'increase' ? '+' : ''}{movement.quantity})
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm">{movement.reason}</p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(movement.timestamp).toLocaleTimeString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Inventory Tab */}
        <TabsContent value="inventory" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Inventory Comparison</CardTitle>
                  <CardDescription>Compare local and Xorosoft inventory levels</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={loadInventoryComparison}
                    disabled={isLoading}
                  >
                    <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin" />
                </div>
              ) : (
                <ScrollArea className="h-[500px]">
                  <div className="space-y-2">
                    {inventoryItems.map((item) => (
                      <div
                        key={item.sku}
                        className={cn(
                          "flex items-center justify-between p-3 border rounded-lg",
                          item.status === 'needs-update' && "border-blue-200 bg-blue-50",
                          item.status === 'low-stock' && "border-yellow-200 bg-yellow-50",
                          item.status === 'out-of-stock' && "border-red-200 bg-red-50"
                        )}
                      >
                        <div className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={selectedItems.has(item.sku)}
                            onChange={(e) => handleItemSelection(item.sku, e.target.checked)}
                            className="rounded"
                          />
                          {getStockStatusIcon(item.status)}
                          <div>
                            <p className="font-medium">{item.productTitle}</p>
                            <p className="text-sm text-muted-foreground">
                              SKU: {item.sku} • Location: {item.location}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-6">
                          <div className="text-center">
                            <p className="text-sm text-muted-foreground">Current</p>
                            <p className="font-medium">{item.currentStock}</p>
                          </div>
                          <GitCompare className="h-4 w-4 text-muted-foreground" />
                          <div className="text-center">
                            <p className="text-sm text-muted-foreground">Xorosoft</p>
                            <p className="font-medium">{item.xorosoftStock}</p>
                          </div>
                          <div className="text-center">
                            <p className="text-sm text-muted-foreground">Diff</p>
                            <p className={cn(
                              "font-medium",
                              item.difference > 0 && "text-green-600",
                              item.difference < 0 && "text-red-600"
                            )}>
                              {item.difference > 0 ? '+' : ''}{item.difference}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}

              {selectedItems.size > 0 && (
                <div className="mt-4 pt-4 border-t flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    {selectedItems.size} items selected
                  </p>
                  <Button
                    onClick={() => handleSyncInventory('selected')}
                    disabled={isSyncing}
                  >
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Sync Selected
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sync Tab */}
        <TabsContent value="sync" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Manual Sync</CardTitle>
              <CardDescription>Manually trigger inventory synchronization</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <Button
                  variant="outline"
                  onClick={() => handleSyncInventory('full')}
                  disabled={!isConnected || isSyncing}
                  className="h-24"
                >
                  <div className="text-center">
                    <Database className="h-6 w-6 mx-auto mb-2" />
                    <p className="font-medium">Full Sync</p>
                    <p className="text-xs text-muted-foreground">Sync all products</p>
                  </div>
                </Button>
                <Button
                  variant="outline"
                  onClick={() => handleSyncInventory()}
                  disabled={!isConnected || isSyncing}
                  className="h-24"
                >
                  <div className="text-center">
                    <RefreshCw className="h-6 w-6 mx-auto mb-2" />
                    <p className="font-medium">Incremental</p>
                    <p className="text-xs text-muted-foreground">Only changes</p>
                  </div>
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setActiveTab('inventory')}
                  disabled={!isConnected || isSyncing}
                  className="h-24"
                >
                  <div className="text-center">
                    <Package className="h-6 w-6 mx-auto mb-2" />
                    <p className="font-medium">Selected Items</p>
                    <p className="text-xs text-muted-foreground">Choose specific</p>
                  </div>
                </Button>
              </div>

              {/* Last Sync Results */}
              {syncResults.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Last Sync Result</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-4 gap-4 text-sm">
                      <div>
                        <p className="text-muted-foreground">Total Items</p>
                        <p className="font-medium">{syncResults[0].totalItems}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Updated</p>
                        <p className="font-medium text-green-600">{syncResults[0].updatedItems}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Failed</p>
                        <p className="font-medium text-red-600">{syncResults[0].failedItems}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Duration</p>
                        <p className="font-medium">{syncResults[0].duration}s</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Sync History</CardTitle>
              <CardDescription>Previous synchronization results</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[500px]">
                {syncResults.length === 0 ? (
                  <div className="text-center py-8">
                    <Clock className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                    <p className="text-muted-foreground">No sync history</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {syncResults.map((result, idx) => (
                      <Card key={idx}>
                        <CardContent className="pt-6">
                          <div className="flex items-center justify-between mb-4">
                            <div>
                              <p className="font-medium">
                                {new Date(result.timestamp).toLocaleString()}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                Duration: {result.duration}s
                              </p>
                            </div>
                            <Badge variant={result.failedItems > 0 ? 'destructive' : 'default'}>
                              {result.failedItems > 0 ? 'Partial' : 'Success'}
                            </Badge>
                          </div>
                          <div className="grid grid-cols-4 gap-4 text-sm">
                            <div>
                              <p className="text-muted-foreground">Total</p>
                              <p className="font-medium">{result.totalItems}</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Updated</p>
                              <p className="font-medium text-green-600">{result.updatedItems}</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Failed</p>
                              <p className="font-medium text-red-600">{result.failedItems}</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Skipped</p>
                              <p className="font-medium text-yellow-600">{result.skippedItems}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Xorosoft Configuration</CardTitle>
              <CardDescription>Configure API connection and sync settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="api-url">API URL</Label>
                <Input
                  id="api-url"
                  placeholder="https://api.xorosoft.com"
                  value={config.apiUrl}
                  onChange={(e) => handleConfigChange('apiUrl', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="api-key">API Key</Label>
                <Input
                  id="api-key"
                  type="password"
                  placeholder="Your API key"
                  value={config.apiKey}
                  onChange={(e) => handleConfigChange('apiKey', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label>Sync Mode</Label>
                <Select
                  value={config.syncMode}
                  onValueChange={(value) => handleConfigChange('syncMode', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="full">Full Sync</SelectItem>
                    <SelectItem value="incremental">Incremental</SelectItem>
                    <SelectItem value="changes-only">Changes Only</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Sync Schedule</Label>
                <Select
                  value={config.syncSchedule}
                  onValueChange={(value) => handleConfigChange('syncSchedule', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual">Manual Only</SelectItem>
                    <SelectItem value="hourly">Every Hour</SelectItem>
                    <SelectItem value="daily">Daily</SelectItem>
                    <SelectItem value="realtime">Real-time</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="inventory-threshold">Low Inventory Threshold</Label>
                <Input
                  id="inventory-threshold"
                  type="number"
                  min="0"
                  value={config.inventoryThreshold}
                  onChange={(e) => handleConfigChange('inventoryThreshold', parseInt(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  Alert when stock falls below this level
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    id="stock-updates"
                    checked={config.stockUpdateEnabled}
                    onChange={(e) => handleConfigChange('stockUpdateEnabled', e.target.checked)}
                    className="rounded"
                  />
                  <Label htmlFor="stock-updates" className="font-normal">
                    Enable stock level updates
                  </Label>
                </div>

                <div className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    id="price-updates"
                    checked={config.priceUpdateEnabled}
                    onChange={(e) => handleConfigChange('priceUpdateEnabled', e.target.checked)}
                    className="rounded"
                  />
                  <Label htmlFor="price-updates" className="font-normal">
                    Enable price updates
                  </Label>
                </div>
              </div>

              <Button onClick={saveConfiguration} className="w-full">
                Save Configuration
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}