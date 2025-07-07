import React, { useState, useEffect, useMemo } from 'react';
import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { apiClient } from '@/lib/api';
import { 
  Package,
  Search,
  Filter,
  MoreHorizontal,
  Edit,
  Trash2,
  Upload,
  Tag,
  DollarSign,
  Archive,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ExternalLink,
  RefreshCw,
  Download,
  ChevronDown,
  Layers,
  Copy,
  Eye
} from 'lucide-react';

interface Product {
  id: number;
  sku: string;
  name: string;
  description?: string;
  price: number;
  category?: {
    id: number;
    name: string;
  };
  brand?: string;
  manufacturer?: string;
  status: string;
  inventory_quantity?: number;
  shopify_product_id?: string;
  shopify_sync_status?: string;
  created_at: string;
  updated_at: string;
  product_type?: string;
}

interface ProductsTableProps {
  onSelectProduct?: (product: Product) => void;
  onBatchAction?: (action: string, productIds: number[]) => void;
  className?: string;
}

export function ProductsTable({ 
  onSelectProduct,
  onBatchAction,
  className 
}: ProductsTableProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProducts, setSelectedProducts] = useState<Set<number>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterCategory, setFilterCategory] = useState('all');
  const [sortBy, setSortBy] = useState('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(1);
  const [perPage] = useState(50);
  const [totalProducts, setTotalProducts] = useState(0);
  const [isBatchDialogOpen, setIsBatchDialogOpen] = useState(false);
  const [batchAction, setBatchAction] = useState<string>('');
  const [batchData, setBatchData] = useState<any>({});

  useEffect(() => {
    loadProducts();
  }, [page, perPage, filterStatus, filterCategory, sortBy, sortOrder]);

  const loadProducts = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const params = {
        limit: perPage,
        offset: (page - 1) * perPage,
        status: filterStatus !== 'all' ? filterStatus : undefined,
        category: filterCategory !== 'all' ? filterCategory : undefined,
        sort_by: sortBy,
        sort_order: sortOrder
      };
      
      const response = await fetch(`http://localhost:3560/api/products?${new URLSearchParams(params as any)}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setProducts(data.products);
        setTotalProducts(data.total);
      } else {
        throw new Error('Failed to load products');
      }
    } catch (error: any) {
      console.error('Error loading products:', error);
      setError(error.message || 'Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  const filteredProducts = useMemo(() => {
    return products.filter(product => {
      const matchesSearch = !searchTerm || 
        product.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
        product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        product.brand?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        product.manufacturer?.toLowerCase().includes(searchTerm.toLowerCase());
      
      return matchesSearch;
    });
  }, [products, searchTerm]);

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedProducts(new Set(filteredProducts.map(p => p.id)));
    } else {
      setSelectedProducts(new Set());
    }
  };

  const handleSelectProduct = (productId: number, checked: boolean) => {
    const newSelection = new Set(selectedProducts);
    if (checked) {
      newSelection.add(productId);
    } else {
      newSelection.delete(productId);
    }
    setSelectedProducts(newSelection);
  };

  const handleBatchAction = async (action: string) => {
    if (selectedProducts.size === 0) {
      alert('Please select at least one product');
      return;
    }

    setBatchAction(action);
    setIsBatchDialogOpen(true);
  };

  const executeBatchAction = async () => {
    const productIds = Array.from(selectedProducts);
    
    try {
      switch (batchAction) {
        case 'update_status':
          await updateProductsStatus(productIds, batchData.status);
          break;
        case 'update_category':
          await updateProductsCategory(productIds, batchData.categoryId);
          break;
        case 'add_to_collection':
          await addProductsToCollection(productIds, batchData.collectionId);
          break;
        case 'sync_to_shopify':
          await syncProductsToShopify(productIds);
          break;
        case 'update_price':
          await updateProductsPricing(productIds, batchData);
          break;
        case 'delete':
          await deleteProducts(productIds);
          break;
      }
      
      setIsBatchDialogOpen(false);
      setBatchData({});
      setSelectedProducts(new Set());
      loadProducts();
      
      if (onBatchAction) {
        onBatchAction(batchAction, productIds);
      }
    } catch (error: any) {
      console.error('Batch action failed:', error);
      alert(error.message || 'Batch action failed');
    }
  };

  const updateProductsStatus = async (productIds: number[], status: string) => {
    const response = await fetch('http://localhost:3560/api/products/batch/update-status', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ product_ids: productIds, status })
    });
    
    if (!response.ok) {
      throw new Error('Failed to update products status');
    }
  };

  const updateProductsCategory = async (productIds: number[], categoryId: number) => {
    const response = await fetch('http://localhost:3560/api/products/batch/update-category', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ product_ids: productIds, category_id: categoryId })
    });
    
    if (!response.ok) {
      throw new Error('Failed to update products category');
    }
  };

  const addProductsToCollection = async (productIds: number[], collectionId: number) => {
    await apiClient.addProductsToCollection(collectionId, productIds);
  };

  const syncProductsToShopify = async (productIds: number[]) => {
    const response = await fetch('http://localhost:3560/api/shopify/sync/products', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ product_ids: productIds })
    });
    
    if (!response.ok) {
      throw new Error('Failed to sync products to Shopify');
    }
  };

  const updateProductsPricing = async (productIds: number[], priceData: any) => {
    const response = await fetch('http://localhost:3560/api/products/batch/update-pricing', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        product_ids: productIds,
        ...priceData
      })
    });
    
    if (!response.ok) {
      throw new Error('Failed to update products pricing');
    }
  };

  const deleteProducts = async (productIds: number[]) => {
    const response = await fetch('http://localhost:3560/api/products/batch/delete', {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ product_ids: productIds })
    });
    
    if (!response.ok) {
      throw new Error('Failed to delete products');
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge variant="default" className="bg-green-100 text-green-800">Active</Badge>;
      case 'draft':
        return <Badge variant="outline">Draft</Badge>;
      case 'archived':
        return <Badge variant="secondary">Archived</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getSyncStatusIcon = (product: Product) => {
    if (!product.shopify_product_id) {
      return <XCircle className="h-4 w-4 text-gray-400" />;
    }
    
    switch (product.shopify_sync_status) {
      case 'synced':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'pending':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-400" />;
    }
  };

  const totalPages = Math.ceil(totalProducts / perPage);

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Products</h2>
          <p className="text-muted-foreground">
            Manage your product catalog and inventory
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={loadProducts}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button>
            <Upload className="h-4 w-4 mr-2" />
            Import Products
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Filters and Search */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by SKU, name, brand, or manufacturer..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="All Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="archived">Archived</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="name">Name</SelectItem>
                <SelectItem value="sku">SKU</SelectItem>
                <SelectItem value="price">Price</SelectItem>
                <SelectItem value="created_at">Date Created</SelectItem>
                <SelectItem value="updated_at">Last Updated</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Batch Actions */}
      {selectedProducts.size > 0 && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">{selectedProducts.size} selected</Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedProducts(new Set())}
                >
                  Clear selection
                </Button>
              </div>
              <div className="flex items-center gap-2">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline">
                      Batch Actions
                      <ChevronDown className="h-4 w-4 ml-2" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56">
                    <DropdownMenuLabel>Status Updates</DropdownMenuLabel>
                    <DropdownMenuItem onClick={() => handleBatchAction('update_status')}>
                      <Tag className="h-4 w-4 mr-2" />
                      Update Status
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleBatchAction('update_category')}>
                      <Layers className="h-4 w-4 mr-2" />
                      Change Category
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuLabel>Collections</DropdownMenuLabel>
                    <DropdownMenuItem onClick={() => handleBatchAction('add_to_collection')}>
                      <Layers className="h-4 w-4 mr-2" />
                      Add to Collection
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuLabel>Shopify</DropdownMenuLabel>
                    <DropdownMenuItem onClick={() => handleBatchAction('sync_to_shopify')}>
                      <Upload className="h-4 w-4 mr-2" />
                      Sync to Shopify
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuLabel>Pricing</DropdownMenuLabel>
                    <DropdownMenuItem onClick={() => handleBatchAction('update_price')}>
                      <DollarSign className="h-4 w-4 mr-2" />
                      Update Pricing
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem 
                      onClick={() => handleBatchAction('delete')}
                      className="text-red-600"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete Products
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Products Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50/50">
                  <th className="p-3 text-left">
                    <Checkbox
                      checked={selectedProducts.size === filteredProducts.length && filteredProducts.length > 0}
                      onCheckedChange={handleSelectAll}
                    />
                  </th>
                  <th className="p-3 text-left font-medium">SKU</th>
                  <th className="p-3 text-left font-medium">Product</th>
                  <th className="p-3 text-left font-medium">Category</th>
                  <th className="p-3 text-left font-medium">Price</th>
                  <th className="p-3 text-left font-medium">Inventory</th>
                  <th className="p-3 text-left font-medium">Status</th>
                  <th className="p-3 text-left font-medium">Shopify</th>
                  <th className="p-3 text-left font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 5 }).map((_, idx) => (
                    <tr key={idx} className="border-b">
                      <td className="p-3" colSpan={9}>
                        <Skeleton className="h-6 w-full" />
                      </td>
                    </tr>
                  ))
                ) : filteredProducts.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="p-8 text-center text-muted-foreground">
                      <Package className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                      <p>No products found</p>
                    </td>
                  </tr>
                ) : (
                  filteredProducts.map((product) => (
                    <tr key={product.id} className="border-b hover:bg-gray-50/50">
                      <td className="p-3">
                        <Checkbox
                          checked={selectedProducts.has(product.id)}
                          onCheckedChange={(checked) => handleSelectProduct(product.id, checked as boolean)}
                        />
                      </td>
                      <td className="p-3">
                        <div className="font-mono text-sm">{product.sku}</div>
                      </td>
                      <td className="p-3">
                        <div>
                          <div className="font-medium">{product.name}</div>
                          {product.brand && (
                            <div className="text-sm text-muted-foreground">{product.brand}</div>
                          )}
                        </div>
                      </td>
                      <td className="p-3">
                        <div className="text-sm">
                          {product.category?.name || 'Uncategorized'}
                        </div>
                      </td>
                      <td className="p-3">
                        <div className="font-medium">${product.price.toFixed(2)}</div>
                      </td>
                      <td className="p-3">
                        <div className="text-sm">
                          {product.inventory_quantity !== undefined ? product.inventory_quantity : '-'}
                        </div>
                      </td>
                      <td className="p-3">
                        {getStatusBadge(product.status)}
                      </td>
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          {getSyncStatusIcon(product)}
                          {product.shopify_product_id && (
                            <a
                              href={`https://${process.env.REACT_APP_SHOPIFY_SHOP_URL}/admin/products/${product.shopify_product_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-muted-foreground hover:text-foreground"
                            >
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                      </td>
                      <td className="p-3">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => onSelectProduct?.(product)}>
                              <Eye className="h-4 w-4 mr-2" />
                              View Details
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Edit className="h-4 w-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Copy className="h-4 w-4 mr-2" />
                              Duplicate
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-red-600">
                              <Trash2 className="h-4 w-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between p-4 border-t">
              <div className="text-sm text-muted-foreground">
                Showing {((page - 1) * perPage) + 1} to {Math.min(page * perPage, totalProducts)} of {totalProducts} products
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    const pageNum = i + 1;
                    return (
                      <Button
                        key={pageNum}
                        variant={pageNum === page ? "default" : "outline"}
                        size="sm"
                        onClick={() => setPage(pageNum)}
                      >
                        {pageNum}
                      </Button>
                    );
                  })}
                  {totalPages > 5 && <span className="px-2">...</span>}
                  {totalPages > 5 && (
                    <Button
                      variant={totalPages === page ? "default" : "outline"}
                      size="sm"
                      onClick={() => setPage(totalPages)}
                    >
                      {totalPages}
                    </Button>
                  )}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page + 1)}
                  disabled={page === totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Batch Action Dialog */}
      <Dialog open={isBatchDialogOpen} onOpenChange={setIsBatchDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Batch Update Products</DialogTitle>
            <DialogDescription>
              Update {selectedProducts.size} selected products
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            {batchAction === 'update_status' && (
              <div>
                <Label>New Status</Label>
                <Select
                  value={batchData.status || ''}
                  onValueChange={(value) => setBatchData({ ...batchData, status: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="draft">Draft</SelectItem>
                    <SelectItem value="archived">Archived</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            
            {batchAction === 'update_price' && (
              <>
                <div>
                  <Label>Price Adjustment Type</Label>
                  <Select
                    value={batchData.adjustmentType || ''}
                    onValueChange={(value) => setBatchData({ ...batchData, adjustmentType: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select adjustment type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="fixed">Fixed Price</SelectItem>
                      <SelectItem value="percentage_increase">Percentage Increase</SelectItem>
                      <SelectItem value="percentage_decrease">Percentage Decrease</SelectItem>
                      <SelectItem value="amount_increase">Amount Increase</SelectItem>
                      <SelectItem value="amount_decrease">Amount Decrease</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Value</Label>
                  <Input
                    type="number"
                    value={batchData.value || ''}
                    onChange={(e) => setBatchData({ ...batchData, value: e.target.value })}
                    placeholder="Enter value"
                  />
                </div>
              </>
            )}
            
            {batchAction === 'add_to_collection' && (
              <div>
                <Label>Select Collection</Label>
                <Select
                  value={batchData.collectionId?.toString() || ''}
                  onValueChange={(value) => setBatchData({ ...batchData, collectionId: parseInt(value) })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select collection" />
                  </SelectTrigger>
                  <SelectContent>
                    {/* Collections would be loaded here */}
                    <SelectItem value="1">Summer Collection</SelectItem>
                    <SelectItem value="2">Featured Products</SelectItem>
                    <SelectItem value="3">Best Sellers</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            
            {batchAction === 'delete' && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  This action cannot be undone. {selectedProducts.size} products will be permanently deleted.
                </AlertDescription>
              </Alert>
            )}
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsBatchDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={executeBatchAction} variant={batchAction === 'delete' ? 'destructive' : 'default'}>
              {batchAction === 'delete' ? 'Delete Products' : 'Update Products'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}