import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Checkbox } from '@/components/ui/checkbox';
import { 
  RefreshCw, 
  Download, 
  Upload, 
  CheckCircle2, 
  XCircle,
  AlertCircle,
  ExternalLink,
  Package,
  ShoppingCart,
  DollarSign,
  TrendingUp,
  Clock,
  Database,
  Zap,
  Layers
} from 'lucide-react';
import { ProductTypeCollectionManager } from './ProductTypeCollectionManager';
import { apiClient } from '@/lib/api';

interface Product {
  id: number;
  sku: string;
  name: string;
  price: number | null;
  compare_at_price: number | null;
  inventory_quantity: number;
  status: string;
  category_name: string | null;
  shopify_product_id: string | null;
  shopify_synced_at: string | null;
  shopify_sync_status: string | null;
  featured_image_url: string | null;
  vendor: string | null;
  product_type: string | null;
  tags: string | null;
  created_at: string;
  updated_at: string;
}

interface SyncStatistics {
  total_products: number;
  synced_products: number;
  sync_percentage: number;
  categories_with_shopify: number;
}

interface SyncResult {
  total_products: number;
  created: number;
  updated: number;
  skipped: number;
  errors: number;
  error_details: Array<{
    product_id: string;
    title: string;
    error: string;
  }>;
}

interface ShopifyProductSyncManagerProps {
  className?: string;
}

export function ShopifyProductSyncManager({ className }: ShopifyProductSyncManagerProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [statistics, setStatistics] = useState<SyncStatistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncProgress, setSyncProgress] = useState(0);
  const [lastSyncResult, setLastSyncResult] = useState<SyncResult | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'unknown' | 'connected' | 'error'>('unknown');
  const [shopInfo, setShopInfo] = useState<any>(null);
  const [includeDraft, setIncludeDraft] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [syncFilter, setSyncFilter] = useState<'all' | 'synced' | 'not_synced'>('all');
  const [resumeCursor, setResumeCursor] = useState<string | null>(null);

  useEffect(() => {
    loadSyncStatus();
    testConnection();
    loadProducts();
  }, [currentPage, syncFilter]);

  const testConnection = async () => {
    try {
      // First try authenticated endpoint
      let data;
      try {
        data = await apiClient.get('/shopify/test-connection');
        setConnectionStatus('connected');
        setShopInfo(data.shop);
      } catch (error: any) {
        // If auth fails, try debug endpoint (temporary)
        if (error.message?.includes('401')) {
          console.log('Auth failed, trying debug endpoint...');
          const response = await fetch(`${process.env.REACT_APP_API_URL || '/api'}/shopify/test-connection-debug`, {
            headers: {
              'Content-Type': 'application/json'
            }
          });
          if (response.ok) {
            data = await response.json();
            setConnectionStatus('connected');
            setShopInfo(data.shop);
          } else {
            setConnectionStatus('error');
            console.error('Shopify connection test failed');
          }
        } else {
          throw error;
        }
      }
    } catch (error) {
      setConnectionStatus('error');
      console.error('Error testing Shopify connection:', error);
    }
  };

  const loadSyncStatus = async () => {
    try {
      const data = await apiClient.get('/shopify/products/sync-status');
      setStatistics(data.statistics);
    } catch (error) {
      console.error('Error loading sync status:', error);
    }
  };

  const loadProducts = async () => {
    try {
      setLoading(true);
      let url = `/products/with-shopify-data?page=${currentPage}&per_page=50`;
      
      if (syncFilter === 'synced') {
        url += '&sync_status=success';
      } else if (syncFilter === 'not_synced') {
        url += '&sync_status=not_synced';
      }

      const data = await apiClient.get(url);
      setProducts(data.products);
      setTotalPages(data.pagination.total_pages);
    } catch (error) {
      console.error('Error loading products:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFullSync = async () => {
    const message = resumeCursor 
      ? `This will continue syncing products from where you left off. Continue?`
      : `This will sync ${includeDraft ? 'ALL' : 'ACTIVE'} products from Shopify. This may take several minutes. Continue?`;
      
    if (!confirm(message)) {
      return;
    }

    setSyncing(true);
    setSyncProgress(0);
    
    try {
      const requestBody: any = {
        include_draft: includeDraft
      };
      
      if (resumeCursor) {
        requestBody.resume_cursor = resumeCursor;
      }
      
      const data = await apiClient.post('/shopify/products/sync', requestBody);
      setLastSyncResult(data.results);
      
      // Handle rate limiting
      if (data.rate_limited && data.resume_cursor) {
        setResumeCursor(data.resume_cursor);
        // Show progress based on actual data
        if (data.progress) {
          setSyncProgress(data.progress.percentage);
        }
      } else {
        // Sync completed
        setResumeCursor(null);
        setSyncProgress(100);
      }

      // Reload data after sync
      await loadSyncStatus();
      await loadProducts();
    } catch (error: any) {
      console.error('Error during sync:', error);
      alert(error.message || 'Network error during sync');
    } finally {
      setSyncing(false);
      if (!resumeCursor) {
        setSyncProgress(0);
      }
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  const getSyncStatusBadge = (product: Product) => {
    if (product.shopify_product_id && product.shopify_synced_at) {
      return <Badge variant="default" className="bg-green-100 text-green-800">Synced</Badge>;
    } else if (product.shopify_product_id && !product.shopify_synced_at) {
      return <Badge variant="secondary">Partial</Badge>;
    } else {
      return <Badge variant="outline">Not Synced</Badge>;
    }
  };

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Shopify Product Sync</h1>
          <p className="text-muted-foreground">
            Synchronize products, prices, and inventory with Shopify
          </p>
        </div>
        <div className="flex items-center gap-2">
          {connectionStatus === 'connected' && (
            <Badge variant="default" className="bg-green-100 text-green-800 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3" />
              Connected to {shopInfo?.name}
            </Badge>
          )}
          {connectionStatus === 'error' && (
            <Badge variant="destructive" className="flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              Connection Failed
            </Badge>
          )}
          <Button variant="outline" onClick={testConnection} disabled={syncing}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Test Connection
          </Button>
        </div>
      </div>

      {/* Connection Alert */}
      {connectionStatus === 'error' && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Unable to connect to Shopify. Please check your credentials in the environment variables.
          </AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="sync">Sync Products</TabsTrigger>
          <TabsTrigger value="products">Product List</TabsTrigger>
          <TabsTrigger value="collections">Collections</TabsTrigger>
          <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Products</CardTitle>
                <Package className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{statistics?.total_products || 0}</div>
                <p className="text-xs text-muted-foreground">
                  In local database
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Synced Products</CardTitle>
                <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{statistics?.synced_products || 0}</div>
                <p className="text-xs text-muted-foreground">
                  {statistics?.sync_percentage || 0}% of total
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Categories</CardTitle>
                <Database className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{statistics?.categories_with_shopify || 0}</div>
                <p className="text-xs text-muted-foreground">
                  With Shopify mapping
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Sync Status</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {statistics?.sync_percentage || 0}%
                </div>
                <Progress value={statistics?.sync_percentage || 0} className="mt-2" />
              </CardContent>
            </Card>
          </div>

          {shopInfo && (
            <Card>
              <CardHeader>
                <CardTitle>Connected Shopify Store</CardTitle>
                <CardDescription>Current store information</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-sm font-medium">Store Name</p>
                    <p className="text-sm text-muted-foreground">{shopInfo.name}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Domain</p>
                    <p className="text-sm text-muted-foreground">{shopInfo.domain}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Plan</p>
                    <p className="text-sm text-muted-foreground">{shopInfo.plan}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Currency</p>
                    <p className="text-sm text-muted-foreground">{shopInfo.currency}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Sync Tab */}
        <TabsContent value="sync" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Full Product Sync</CardTitle>
              <CardDescription>
                Import all products from Shopify with complete details including prices, inventory, and images
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="include-draft"
                  checked={includeDraft}
                  onCheckedChange={(checked) => setIncludeDraft(checked as boolean)}
                  disabled={syncing}
                />
                <label htmlFor="include-draft" className="text-sm font-medium">
                  Include draft products
                </label>
              </div>

              {(syncing || syncProgress > 0) && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span>{syncing ? 'Syncing products...' : 'Sync paused (rate limited)'}</span>
                    <span>{syncProgress.toFixed(1)}%</span>
                  </div>
                  <Progress value={syncProgress} />
                  {!syncing && resumeCursor && (
                    <p className="text-xs text-muted-foreground">
                      Click "Continue Sync" to resume from where you left off
                    </p>
                  )}
                </div>
              )}

              <Button 
                onClick={handleFullSync} 
                disabled={syncing || connectionStatus !== 'connected'}
                className="w-full"
              >
                {syncing ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    Syncing...
                  </>
                ) : resumeCursor ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Continue Sync
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4 mr-2" />
                    Start Full Sync
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {lastSyncResult && (
            <Card>
              <CardHeader>
                <CardTitle>Last Sync Results</CardTitle>
                <CardDescription>Results from the most recent sync operation</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div>
                    <p className="text-sm font-medium">Total</p>
                    <p className="text-2xl font-bold">{lastSyncResult.total_products}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Created</p>
                    <p className="text-2xl font-bold text-green-600">{lastSyncResult.created}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Updated</p>
                    <p className="text-2xl font-bold text-blue-600">{lastSyncResult.updated}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Skipped</p>
                    <p className="text-2xl font-bold text-gray-600">{lastSyncResult.skipped}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Errors</p>
                    <p className="text-2xl font-bold text-red-600">{lastSyncResult.errors}</p>
                  </div>
                </div>

                {lastSyncResult.error_details.length > 0 && (
                  <div className="mt-4">
                    <p className="text-sm font-medium mb-2">Error Details:</p>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {lastSyncResult.error_details.map((error, idx) => (
                        <div key={idx} className="text-xs p-2 bg-red-50 rounded">
                          <span className="font-medium">{error.title}</span>: {error.error}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Products Tab */}
        <TabsContent value="products" className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button
                variant={syncFilter === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSyncFilter('all')}
              >
                All
              </Button>
              <Button
                variant={syncFilter === 'synced' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSyncFilter('synced')}
              >
                Synced
              </Button>
              <Button
                variant={syncFilter === 'not_synced' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSyncFilter('not_synced')}
              >
                Not Synced
              </Button>
            </div>
            <Button variant="outline" onClick={loadProducts}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>

          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b">
                    <tr className="bg-muted/50">
                      <th className="text-left p-4 font-medium">Product</th>
                      <th className="text-left p-4 font-medium">SKU</th>
                      <th className="text-left p-4 font-medium">Price</th>
                      <th className="text-left p-4 font-medium">Inventory</th>
                      <th className="text-left p-4 font-medium">Category</th>
                      <th className="text-left p-4 font-medium">Status</th>
                      <th className="text-left p-4 font-medium">Last Synced</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading ? (
                      Array.from({ length: 10 }).map((_, idx) => (
                        <tr key={idx} className="border-b">
                          <td className="p-4"><Skeleton className="h-4 w-48" /></td>
                          <td className="p-4"><Skeleton className="h-4 w-20" /></td>
                          <td className="p-4"><Skeleton className="h-4 w-16" /></td>
                          <td className="p-4"><Skeleton className="h-4 w-12" /></td>
                          <td className="p-4"><Skeleton className="h-4 w-24" /></td>
                          <td className="p-4"><Skeleton className="h-4 w-16" /></td>
                          <td className="p-4"><Skeleton className="h-4 w-32" /></td>
                        </tr>
                      ))
                    ) : products.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="text-center p-8 text-muted-foreground">
                          No products found
                        </td>
                      </tr>
                    ) : (
                      products.map((product) => (
                        <tr key={product.id} className="border-b hover:bg-muted/50">
                          <td className="p-4">
                            <div className="flex items-center gap-3">
                              {product.featured_image_url && (
                                <img 
                                  src={product.featured_image_url} 
                                  alt={product.name}
                                  className="w-8 h-8 rounded object-cover"
                                />
                              )}
                              <div>
                                <p className="font-medium">{product.name}</p>
                                {product.vendor && (
                                  <p className="text-xs text-muted-foreground">{product.vendor}</p>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="p-4 font-mono text-sm">{product.sku || '-'}</td>
                          <td className="p-4">
                            {product.price ? `$${product.price.toFixed(2)}` : '-'}
                          </td>
                          <td className="p-4">{product.inventory_quantity || 0}</td>
                          <td className="p-4">{product.category_name || '-'}</td>
                          <td className="p-4">{getSyncStatusBadge(product)}</td>
                          <td className="p-4 text-sm">{formatDate(product.shopify_synced_at)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1 || loading}
              >
                Previous
              </Button>
              <span className="text-sm">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages || loading}
              >
                Next
              </Button>
            </div>
          )}
        </TabsContent>

        {/* Collections Tab */}
        <TabsContent value="collections" className="space-y-6">
          <ProductTypeCollectionManager />
        </TabsContent>

        {/* Monitoring Tab */}
        <TabsContent value="monitoring" className="space-y-6">
          <Alert>
            <Clock className="h-4 w-4" />
            <AlertDescription>
              Monitoring and detailed sync logs will be implemented in the next phase.
              For now, check the browser console for detailed sync information.
            </AlertDescription>
          </Alert>
        </TabsContent>
      </Tabs>
    </div>
  );
}