import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Checkbox } from '@/components/ui/checkbox';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Package, 
  Search, 
  Filter, 
  MoreHorizontal, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  ExternalLink, 
  Edit, 
  Download,
  Eye,
  History,
  GitBranch,
  Zap,
  Upload,
  X,
  Play,
  Pause,
  RotateCcw
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { apiClient } from '@/lib/api';

interface Product {
  id: number;
  sku: string;
  name: string;
  brand: string;
  price: number;
  inventory_quantity: number;
  status: string;
  shopify_id?: string;
  shopify_handle?: string;
  shopify_sync_status: 'pending' | 'synced' | 'out_of_sync' | 'conflict' | 'error';
  shopify_synced_at?: string;
  last_modified?: string;
  has_changes: boolean;
  sync_conflicts?: string[];
  featured_image_url?: string;
  category?: {
    id: number;
    name: string;
  };
  change_summary?: {
    modified_fields: string[];
    last_change_at: string;
    last_change_by: string;
  };
}

interface SyncStatus {
  pending_changes: number;
  conflicts: number;
  queue_size: number;
  last_sync: string;
  sync_rate: number;
  active_operations: number;
}

interface BatchOperation {
  id: string;
  type: 'sync' | 'update' | 'delete';
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused';
  progress: number;
  total: number;
  started_at?: string;
  completed_at?: string;
  error?: string;
  estimated_completion?: string;
}

interface ChangeVersion {
  id: string;
  product_id: number;
  changes: Record<string, any>;
  created_at: string;
  created_by: string;
  change_type: 'update' | 'sync' | 'bulk_edit';
  is_applied: boolean;
}

export function ProductsTableView() {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<Set<number>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [syncFilter, setSyncFilter] = useState<string>('all');
  const [loading, setLoading] = useState(false);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [batchOperations, setBatchOperations] = useState<BatchOperation[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [showChangeHistory, setShowChangeHistory] = useState(false);
  const [changeVersions, setChangeVersions] = useState<ChangeVersion[]>([]);
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalProducts, setTotalProducts] = useState(0);
  const itemsPerPage = 50;

  // Real-time updates
  useEffect(() => {
    loadProducts();
    loadSyncStatus();
    loadBatchOperations();
    
    const interval = setInterval(() => {
      loadSyncStatus();
      loadBatchOperations();
    }, 10000); // Update every 10 seconds
    
    return () => clearInterval(interval);
  }, [currentPage, searchTerm, statusFilter, syncFilter]);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: currentPage.toString(),
        limit: itemsPerPage.toString(),
        search: searchTerm,
        status: statusFilter !== 'all' ? statusFilter : '',
        sync_status: syncFilter !== 'all' ? syncFilter : '',
        include_changes: 'true'
      });

      const data = await apiClient.get<{
        success: boolean;
        products: Product[];
        total: number;
        page: number;
        limit: number;
        total_pages: number;
      }>(`/products?${params}`);
      
      setProducts(data.products || []);
      setTotalPages(data.total_pages || Math.ceil(data.total / itemsPerPage));
      setTotalProducts(data.total || 0);
    } catch (error) {
      console.error('Error loading products:', error);
      setProducts([]);
      setTotalPages(1);
      setTotalProducts(0);
    } finally {
      setLoading(false);
    }
  };

  const loadSyncStatus = async () => {
    try {
      const data = await apiClient.get<SyncStatus>('/products/sync/status');
      setSyncStatus(data);
    } catch (error) {
      console.error('Error loading sync status:', error);
    }
  };

  const loadBatchOperations = async () => {
    try {
      const data = await apiClient.get<{operations: BatchOperation[]}>('/products/sync/operations');
      setBatchOperations(data.operations || []);
    } catch (error) {
      console.error('Error loading batch operations:', error);
    }
  };

  const loadChangeHistory = async (productId: number) => {
    try {
      const data = await apiClient.get<{changes: ChangeVersion[]}>(`/products/${productId}/changes`);
      setChangeVersions(data.changes || []);
    } catch (error) {
      console.error('Error loading change history:', error);
    }
  };

  const getSyncStatusBadge = (product: Product) => {
    const status = product.shopify_sync_status;
    const variants = {
      pending: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      synced: 'bg-green-100 text-green-800 border-green-200',
      out_of_sync: 'bg-orange-100 text-orange-800 border-orange-200',
      conflict: 'bg-red-100 text-red-800 border-red-200',
      error: 'bg-red-100 text-red-800 border-red-200'
    };

    const icons = {
      pending: <Clock className="w-3 h-3" />,
      synced: <CheckCircle className="w-3 h-3" />,
      out_of_sync: <RefreshCw className="w-3 h-3" />,
      conflict: <AlertTriangle className="w-3 h-3" />,
      error: <AlertTriangle className="w-3 h-3" />
    };

    const labels = {
      pending: 'Pending',
      synced: 'Synced',
      out_of_sync: 'Out of Sync',
      conflict: 'Conflict',
      error: 'Error'
    };

    return (
      <Badge variant="outline" className={cn('gap-1', variants[status])}>
        {icons[status]}
        {labels[status]}
      </Badge>
    );
  };

  const getChangeIndicator = (product: Product) => {
    if (!product.has_changes) return null;

    return (
      <div className="flex items-center gap-1 text-xs">
        <GitBranch className="w-3 h-3 text-orange-600" />
        <span className="text-orange-600">
          {product.change_summary?.modified_fields.length || 0} fields changed
        </span>
      </div>
    );
  };

  const handleProductSelect = (productId: number, checked: boolean) => {
    const newSelected = new Set(selectedProducts);
    if (checked) {
      newSelected.add(productId);
    } else {
      newSelected.delete(productId);
    }
    setSelectedProducts(newSelected);
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedProducts(new Set(products.map(p => p.id)));
    } else {
      setSelectedProducts(new Set());
    }
  };

  const handleBatchSync = async () => {
    if (selectedProducts.size === 0) return;

    try {
      const result = await apiClient.post<{success: boolean, operation: BatchOperation}>('/products/sync/batch', {
        product_ids: Array.from(selectedProducts),
        operation: 'sync'
      });

      if (result.success) {
        setBatchOperations(prev => [...prev, result.operation]);
        setSelectedProducts(new Set());
        loadProducts();
      }
    } catch (error) {
      console.error('Error starting batch sync:', error);
    }
  };

  const handleProductSync = async (productId: number) => {
    try {
      const result = await apiClient.post<{success: boolean}>(`/products/${productId}/sync`);
      
      if (result.success) {
        loadProducts();
      }
    } catch (error) {
      console.error('Error syncing product:', error);
    }
  };

  const handleBatchOperationControl = async (operationId: string, action: 'pause' | 'resume' | 'cancel') => {
    try {
      const result = await apiClient.post<{success: boolean}>(`/products/sync/operations/${operationId}/${action}`);

      if (result.success) {
        loadBatchOperations();
      }
    } catch (error) {
      console.error(`Error ${action}ing operation:`, error);
    }
  };

  const handleVersionRevert = async (versionId: string) => {
    try {
      const result = await apiClient.post<{success: boolean}>(`/products/changes/${versionId}/revert`);

      if (result.success) {
        loadProducts();
        if (selectedProduct) {
          loadChangeHistory(selectedProduct.id);
        }
      }
    } catch (error) {
      console.error('Error reverting version:', error);
    }
  };

  const filteredProducts = products.filter(product => {
    const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         product.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         product.brand?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || product.status === statusFilter;
    const matchesSync = syncFilter === 'all' || product.shopify_sync_status === syncFilter;
    
    return matchesSearch && matchesStatus && matchesSync;
  });

  return (
    <div className="space-y-6">
      {/* Header with Real-time Stats */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Products</h1>
          <p className="text-muted-foreground">
            Manage and sync your product catalog with staging layer
          </p>
        </div>
        
        {syncStatus && (
          <div className="flex items-center gap-6">
            <div className="text-sm text-right">
              <div className="flex items-center gap-2 justify-end">
                <Package className="w-4 h-4" />
                <span>{totalProducts} total products</span>
              </div>
              <div className="flex items-center gap-2 justify-end text-orange-600">
                <Clock className="w-4 h-4" />
                <span>{syncStatus.pending_changes} pending changes</span>
              </div>
              {syncStatus.conflicts > 0 && (
                <div className="flex items-center gap-2 justify-end text-red-600">
                  <AlertTriangle className="w-4 h-4" />
                  <span>{syncStatus.conflicts} conflicts</span>
                </div>
              )}
              {syncStatus.active_operations > 0 && (
                <div className="flex items-center gap-2 justify-end text-blue-600">
                  <Zap className="w-4 h-4" />
                  <span>{syncStatus.active_operations} operations running</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Filters and Search */}
      <Card>
        <CardHeader>
          <CardTitle>Filters & Search</CardTitle>
          <CardDescription>Filter products by status, sync state, and search criteria</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search products by name, SKU, or brand..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="gap-2">
                  <Filter className="w-4 h-4" />
                  Status: {statusFilter === 'all' ? 'All' : statusFilter}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => setStatusFilter('all')}>All</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setStatusFilter('active')}>Active</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setStatusFilter('draft')}>Draft</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setStatusFilter('archived')}>Archived</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="gap-2">
                  <RefreshCw className="w-4 h-4" />
                  Sync: {syncFilter === 'all' ? 'All' : syncFilter.replace('_', ' ')}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => setSyncFilter('all')}>All</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setSyncFilter('synced')}>Synced</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setSyncFilter('out_of_sync')}>Out of Sync</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setSyncFilter('pending')}>Pending</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setSyncFilter('conflict')}>Conflicts</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setSyncFilter('error')}>Errors</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Button 
              onClick={loadProducts} 
              variant="outline" 
              size="icon"
              disabled={loading}
            >
              <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Batch Operations Bar */}
      {selectedProducts.size > 0 && (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={selectedProducts.size === products.length}
                  onCheckedChange={handleSelectAll}
                />
                <span className="text-sm font-medium">
                  {selectedProducts.size} product{selectedProducts.size !== 1 ? 's' : ''} selected
                </span>
              </div>
              
              <div className="flex items-center gap-2">
                <Button onClick={handleBatchSync} className="gap-2">
                  <RefreshCw className="w-4 h-4" />
                  Sync to Shopify
                </Button>
                <Button variant="outline" className="gap-2">
                  <Edit className="w-4 h-4" />
                  Bulk Edit
                </Button>
                <Button variant="outline" className="gap-2">
                  <Download className="w-4 h-4" />
                  Export
                </Button>
                <Button 
                  variant="outline" 
                  size="icon"
                  onClick={() => setSelectedProducts(new Set())}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Active Batch Operations Status */}
      {batchOperations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="w-5 h-5" />
              Active Operations
            </CardTitle>
            <CardDescription>Monitor and control running sync operations</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {batchOperations.map((operation) => (
                <div key={operation.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "w-2 h-2 rounded-full",
                      operation.status === 'running' && "bg-blue-500 animate-pulse",
                      operation.status === 'completed' && "bg-green-500",
                      operation.status === 'failed' && "bg-red-500",
                      operation.status === 'paused' && "bg-yellow-500",
                      operation.status === 'pending' && "bg-gray-500"
                    )} />
                    <div>
                      <div className="font-medium capitalize">{operation.type} operation</div>
                      <div className="text-sm text-muted-foreground">
                        {operation.progress}/{operation.total} completed
                        {operation.estimated_completion && operation.status === 'running' && (
                          <span> • ETA: {operation.estimated_completion}</span>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-3">
                    <Progress 
                      value={(operation.progress / operation.total) * 100} 
                      className="w-32"
                    />
                    <Badge variant={
                      operation.status === 'completed' ? 'default' :
                      operation.status === 'failed' ? 'destructive' :
                      operation.status === 'running' ? 'secondary' :
                      'outline'
                    }>
                      {operation.status}
                    </Badge>
                    
                    <div className="flex items-center gap-1">
                      {operation.status === 'running' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleBatchOperationControl(operation.id, 'pause')}
                        >
                          <Pause className="w-3 h-3" />
                        </Button>
                      )}
                      {operation.status === 'paused' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleBatchOperationControl(operation.id, 'resume')}
                        >
                          <Play className="w-3 h-3" />
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleBatchOperationControl(operation.id, 'cancel')}
                      >
                        <X className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Products Table */}
      <Card>
        <CardHeader>
          <CardTitle>Product Catalog</CardTitle>
          <CardDescription>
            {filteredProducts.length} of {totalProducts} products shown
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin" />
              <span className="ml-2">Loading products...</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <Checkbox
                        checked={selectedProducts.size === products.length && products.length > 0}
                        onCheckedChange={handleSelectAll}
                      />
                    </TableHead>
                    <TableHead>Product</TableHead>
                    <TableHead>SKU</TableHead>
                    <TableHead>Brand</TableHead>
                    <TableHead>Price</TableHead>
                    <TableHead>Stock</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Sync Status</TableHead>
                    <TableHead>Changes</TableHead>
                    <TableHead>Last Sync</TableHead>
                    <TableHead className="w-12"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredProducts.map((product) => (
                    <TableRow 
                      key={product.id}
                      className={cn(
                        product.has_changes && "bg-orange-50 border-l-4 border-orange-400",
                        product.shopify_sync_status === 'conflict' && "bg-red-50 border-l-4 border-red-400"
                      )}
                    >
                      <TableCell>
                        <Checkbox
                          checked={selectedProducts.has(product.id)}
                          onCheckedChange={(checked) => handleProductSelect(product.id, checked as boolean)}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          {product.featured_image_url && (
                            <img 
                              src={product.featured_image_url} 
                              alt={product.name}
                              className="w-10 h-10 rounded object-cover border"
                            />
                          )}
                          <div>
                            <div className="font-medium line-clamp-1">{product.name}</div>
                            {product.category && (
                              <div className="text-sm text-muted-foreground">{product.category.name}</div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-sm">{product.sku}</TableCell>
                      <TableCell>{product.brand}</TableCell>
                      <TableCell>${product.price.toFixed(2)}</TableCell>
                      <TableCell>
                        <span className={cn(
                          product.inventory_quantity === 0 && "text-red-600 font-medium",
                          product.inventory_quantity < 10 && product.inventory_quantity > 0 && "text-orange-600"
                        )}>
                          {product.inventory_quantity}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge 
                          variant={product.status === 'active' ? 'default' : 'secondary'}
                        >
                          {product.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {getSyncStatusBadge(product)}
                      </TableCell>
                      <TableCell>
                        {getChangeIndicator(product)}
                        {product.change_summary && (
                          <div className="text-xs text-muted-foreground mt-1">
                            Last: {new Date(product.change_summary.last_change_at).toLocaleDateString()}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        {product.shopify_synced_at ? (
                          <span className="text-sm text-muted-foreground">
                            {new Date(product.shopify_synced_at).toLocaleDateString()}
                          </span>
                        ) : (
                          <span className="text-sm text-muted-foreground">Never</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            <DropdownMenuItem onClick={() => setSelectedProduct(product)}>
                              <Eye className="mr-2 h-4 w-4" />
                              View Details
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Edit className="mr-2 h-4 w-4" />
                              Edit Product
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => handleProductSync(product.id)}>
                              <RefreshCw className="mr-2 h-4 w-4" />
                              Sync to Shopify
                            </DropdownMenuItem>
                            {product.shopify_id && (
                              <DropdownMenuItem>
                                <ExternalLink className="mr-2 h-4 w-4" />
                                View in Shopify
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => {
                              setSelectedProduct(product);
                              setShowChangeHistory(true);
                              loadChangeHistory(product.id);
                            }}>
                              <History className="mr-2 h-4 w-4" />
                              View History
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-4 border-t">
              <div className="text-sm text-muted-foreground">
                Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, totalProducts)} of {totalProducts} products
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
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
                  disabled={currentPage === totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Change History Dialog */}
      <Dialog open={showChangeHistory} onOpenChange={setShowChangeHistory}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Change History</DialogTitle>
            <DialogDescription>
              {selectedProduct && `Version history for ${selectedProduct.name}`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {changeVersions.map((version) => (
              <div key={version.id} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Badge variant={version.is_applied ? 'default' : 'outline'}>
                      {version.change_type}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      {new Date(version.created_at).toLocaleString()}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      by {version.created_by}
                    </span>
                  </div>
                  {!version.is_applied && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleVersionRevert(version.id)}
                    >
                      <RotateCcw className="w-3 h-3 mr-1" />
                      Revert
                    </Button>
                  )}
                </div>
                <div className="text-sm space-y-1">
                  {Object.entries(version.changes).map(([field, value]) => (
                    <div key={field} className="flex items-center gap-2">
                      <span className="font-medium">{field}:</span>
                      <span className="text-muted-foreground">{JSON.stringify(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}