/**
 * Enhanced Categories Panel with Shopify Integration
 * 
 * Provides comprehensive category management with Shopify sync and batch operations
 */

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  RefreshCw, 
  Download, 
  BarChart3, 
  ShoppingCart, 
  Package, 
  Tag, 
  Layers,
  AlertCircle,
  CheckCircle,
  Loader2,
  Plus,
  Settings,
  TrendingUp,
  ExternalLink,
  Users
} from 'lucide-react';

import { BatchCategoryAssignment, Product, Category, Collection, CategoryAssignments } from './BatchCategoryAssignment';

interface CategoryAnalytics {
  category_id: number;
  name: string;
  product_count: number;
  total_value: number;
  average_price: number;
  has_shopify_integration: boolean;
  top_products: Array<{
    id: number;
    name: string;
    price: number;
    sku: string;
  }>;
}

interface SyncResults {
  product_types: { synced: number; created: number; updated: number; errors: string[] };
  collections: { synced: number; created: number; updated: number; errors: string[] };
  tags: { synced: number; created: number; updated: number; errors: string[] };
  total_categories: number;
}

interface ShopifyTaxonomy {
  product_types: Array<{ name: string; product_count: number }>;
  collections: Array<{ name: string; product_count: number }>;
  popular_tags: Array<{ name: string; product_count: number }>;
  total_products: number;
}

export function EnhancedCategoriesPanel() {
  const [activeTab, setActiveTab] = useState<'overview' | 'analytics' | 'sync' | 'batch'>('overview');
  const [categories, setCategories] = useState<Category[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<Product[]>([]);
  const [analytics, setAnalytics] = useState<CategoryAnalytics[]>([]);
  const [shopifyTaxonomy, setShopifyTaxonomy] = useState<ShopifyTaxonomy | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncLoading, setSyncLoading] = useState(false);
  const [batchAssignmentOpen, setBatchAssignmentOpen] = useState(false);
  const [syncResults, setSyncResults] = useState<SyncResults | null>(null);
  const [syncProgress, setSyncProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Sync options
  const [syncOptions, setSyncOptions] = useState({
    sync_product_types: true,
    sync_collections: true,
    sync_tags: false,
    create_hierarchy: true,
    min_product_count: 5
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        loadCategories(),
        loadAnalytics(),
        loadShopifyTaxonomy(),
        loadCollections()
      ]);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadCollections = async () => {
    try {
      const response = await fetch('/api/collections', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setCollections(data.collections || []);
      } else {
        console.warn('Collections endpoint not available, using fallback');
        setCollections([]); // Fallback to empty array
      }
    } catch (error) {
      console.error('Error loading collections:', error);
      setCollections([]); // Fallback to empty array
    }
  };

  const loadCategories = async () => {
    try {
      const response = await fetch('/api/categories', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setCategories(data.categories || []);
      } else {
        console.warn('Categories endpoint not available, using fallback');
        setCategories([]); // Fallback to empty array
      }
    } catch (error) {
      console.error('Error loading categories:', error);
      setCategories([]); // Fallback to empty array
    }
  };

  const loadAnalytics = async () => {
    try {
      const response = await fetch('/api/categories/enhanced/analytics', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setAnalytics(data.analytics || []);
      } else {
        console.warn('Analytics endpoint not available, using fallback');
        setAnalytics([]); // Fallback to empty array
      }
    } catch (error) {
      console.error('Error loading analytics:', error);
      setAnalytics([]); // Fallback to empty array
    }
  };

  const loadShopifyTaxonomy = async () => {
    try {
      const response = await fetch('/api/categories/enhanced/shopify-taxonomy', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setShopifyTaxonomy(data.taxonomy);
      } else {
        console.warn('Shopify taxonomy endpoint not available, using fallback');
        setShopifyTaxonomy(null); // Fallback to null
      }
    } catch (error) {
      console.error('Error loading Shopify taxonomy:', error);
      setShopifyTaxonomy(null); // Fallback to null
    }
  };

  const syncFromShopify = async () => {
    setSyncLoading(true);
    setSyncProgress(0);
    setError(null);
    setSuccess(null);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setSyncProgress(prev => Math.min(prev + 5, 90));
      }, 500);

      const response = await fetch('/api/categories/enhanced/sync-from-shopify', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(syncOptions),
      });

      clearInterval(progressInterval);
      setSyncProgress(100);

      if (response.ok) {
        const data = await response.json();
        setSyncResults(data.results);
        setSuccess(`Successfully synced ${data.results.total_categories} categories from Shopify`);
        await loadData(); // Refresh data
      } else {
        const error = await response.json();
        setError(error.error || 'Failed to sync categories');
      }
    } catch (error: any) {
      setError(error.message || 'Failed to sync categories');
    } finally {
      setSyncLoading(false);
      setSyncProgress(0);
    }
  };

  const handleBatchAssignment = async (assignments: CategoryAssignments) => {
    try {
      const response = await fetch('/api/categories/enhanced/batch-assign-products', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          product_ids: selectedProducts.map(p => p.id),
          category_assignments: assignments,
          sync_to_shopify: assignments.sync_to_shopify,
          remove_existing: assignments.remove_existing
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setSuccess(`Successfully processed ${data.results.processed_products} products`);
        await loadData(); // Refresh data
      } else {
        const error = await response.json();
        throw new Error(error.error || 'Failed to assign categories');
      }
    } catch (error: any) {
      throw new Error(error.message || 'Failed to assign categories');
    }
  };

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Statistics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Categories</CardTitle>
            <Layers className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{categories.length}</div>
            <p className="text-xs text-muted-foreground">
              Local categories created
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Shopify Integration</CardTitle>
            <ShoppingCart className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {categories.filter(c => c.shopify_collection_id).length}
            </div>
            <p className="text-xs text-muted-foreground">
              Categories synced with Shopify
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Product Types</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {shopifyTaxonomy?.product_types.length || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              From Shopify products
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Popular Tags</CardTitle>
            <Tag className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {shopifyTaxonomy?.popular_tags.length || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Frequently used tags
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Categories */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Categories</CardTitle>
          <CardDescription>
            Your most recently created or updated categories
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {categories.slice(0, 5).map((category) => (
                <div
                  key={category.id}
                  className="flex items-center justify-between p-3 border rounded-lg"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium">{category.name}</h4>
                      {category.shopify_collection_id && (
                        <Badge variant="outline">
                          <ShoppingCart className="h-3 w-3 mr-1" />
                          Shopify
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {category.product_count} products
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline">
                      <Settings className="h-3 w-3 mr-1" />
                      Edit
                    </Button>
                    {category.shopify_collection_id && (
                      <Button size="sm" variant="outline" asChild>
                        <a
                          href={`https://admin.shopify.com/store/collections/${category.shopify_collection_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );

  const renderAnalytics = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Category Performance</CardTitle>
          <CardDescription>
            Analytics for your categories including product counts and revenue
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              {analytics.map((categoryAnalytics) => (
                <div
                  key={categoryAnalytics.category_id}
                  className="p-4 border rounded-lg"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium">{categoryAnalytics.name}</h4>
                      {categoryAnalytics.has_shopify_integration && (
                        <Badge variant="outline">
                          <ShoppingCart className="h-3 w-3 mr-1" />
                          Shopify
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Package className="h-3 w-3" />
                        {categoryAnalytics.product_count} products
                      </div>
                      <div className="flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" />
                        ${categoryAnalytics.total_value.toFixed(2)} value
                      </div>
                      <div className="flex items-center gap-1">
                        <BarChart3 className="h-3 w-3" />
                        ${categoryAnalytics.average_price.toFixed(2)} avg
                      </div>
                    </div>
                  </div>
                  
                  {categoryAnalytics.top_products.length > 0 && (
                    <div className="mt-3">
                      <p className="text-sm font-medium mb-2">Top Products:</p>
                      <div className="flex flex-wrap gap-2">
                        {categoryAnalytics.top_products.map((product) => (
                          <Badge key={product.id} variant="secondary">
                            {product.name} (${product.price})
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );

  const renderSync = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Sync from Shopify</CardTitle>
          <CardDescription>
            Import categories from your Shopify store taxonomy
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Sync Options */}
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-3">
                <Label className="text-sm font-medium">What to Sync</Label>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="sync-product-types"
                      checked={syncOptions.sync_product_types}
                      onCheckedChange={(checked) => setSyncOptions(prev => ({
                        ...prev,
                        sync_product_types: checked as boolean
                      }))}
                    />
                    <Label htmlFor="sync-product-types">Product Types</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="sync-collections"
                      checked={syncOptions.sync_collections}
                      onCheckedChange={(checked) => setSyncOptions(prev => ({
                        ...prev,
                        sync_collections: checked as boolean
                      }))}
                    />
                    <Label htmlFor="sync-collections">Collections</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="sync-tags"
                      checked={syncOptions.sync_tags}
                      onCheckedChange={(checked) => setSyncOptions(prev => ({
                        ...prev,
                        sync_tags: checked as boolean
                      }))}
                    />
                    <Label htmlFor="sync-tags">Popular Tags</Label>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <Label className="text-sm font-medium">Options</Label>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="create-hierarchy"
                      checked={syncOptions.create_hierarchy}
                      onCheckedChange={(checked) => setSyncOptions(prev => ({
                        ...prev,
                        create_hierarchy: checked as boolean
                      }))}
                    />
                    <Label htmlFor="create-hierarchy">Create Hierarchy</Label>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="min-product-count">Minimum Product Count</Label>
                    <Input
                      id="min-product-count"
                      type="number"
                      value={syncOptions.min_product_count}
                      onChange={(e) => setSyncOptions(prev => ({
                        ...prev,
                        min_product_count: parseInt(e.target.value) || 5
                      }))}
                      min="1"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Sync Button */}
            <Button 
              onClick={syncFromShopify} 
              disabled={syncLoading}
              className="w-full"
            >
              {syncLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Syncing...
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Sync from Shopify
                </>
              )}
            </Button>

            {/* Progress Bar */}
            {syncLoading && (
              <Progress value={syncProgress} className="w-full" />
            )}

            {/* Sync Results */}
            {syncResults && (
              <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                <h4 className="font-medium mb-2">Sync Results:</h4>
                <div className="grid gap-2 md:grid-cols-3">
                  <div className="text-sm">
                    <strong>Product Types:</strong> {syncResults.product_types.created} created, {syncResults.product_types.updated} updated
                  </div>
                  <div className="text-sm">
                    <strong>Collections:</strong> {syncResults.collections.created} created, {syncResults.collections.updated} updated
                  </div>
                  <div className="text-sm">
                    <strong>Tags:</strong> {syncResults.tags.created} created, {syncResults.tags.updated} updated
                  </div>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Shopify Taxonomy Overview */}
      {shopifyTaxonomy && (
        <Card>
          <CardHeader>
            <CardTitle>Current Shopify Taxonomy</CardTitle>
            <CardDescription>
              Overview of your Shopify store's category structure
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <h4 className="font-medium flex items-center gap-2">
                  <Package className="h-4 w-4" />
                  Product Types ({shopifyTaxonomy.product_types.length})
                </h4>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {shopifyTaxonomy.product_types.slice(0, 10).map((type) => (
                    <div key={type.name} className="flex justify-between text-sm">
                      <span>{type.name}</span>
                      <span className="text-muted-foreground">{type.product_count}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="font-medium flex items-center gap-2">
                  <ShoppingCart className="h-4 w-4" />
                  Collections ({shopifyTaxonomy.collections.length})
                </h4>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {shopifyTaxonomy.collections.slice(0, 10).map((collection) => (
                    <div key={collection.name} className="flex justify-between text-sm">
                      <span>{collection.name}</span>
                      <span className="text-muted-foreground">{collection.product_count}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="font-medium flex items-center gap-2">
                  <Tag className="h-4 w-4" />
                  Popular Tags ({shopifyTaxonomy.popular_tags.length})
                </h4>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {shopifyTaxonomy.popular_tags.slice(0, 10).map((tag) => (
                    <div key={tag.name} className="flex justify-between text-sm">
                      <span>{tag.name}</span>
                      <span className="text-muted-foreground">{tag.product_count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );

  const renderBatch = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Batch Category Assignment</CardTitle>
          <CardDescription>
            Assign multiple products to categories and collections in bulk
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="text-center p-8 border-2 border-dashed rounded-lg">
              <Users className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="font-medium mb-2">Select Products for Batch Assignment</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Choose products from the Products dashboard to assign them to categories in bulk
              </p>
              <Button
                onClick={() => setBatchAssignmentOpen(true)}
                disabled={selectedProducts.length === 0}
              >
                <Plus className="mr-2 h-4 w-4" />
                Open Batch Assignment
              </Button>
            </div>

            {selectedProducts.length > 0 && (
              <div className="p-4 bg-blue-50 rounded-lg">
                <p className="text-sm font-medium mb-2">
                  Selected Products ({selectedProducts.length}):
                </p>
                <div className="flex flex-wrap gap-2">
                  {selectedProducts.slice(0, 5).map((product) => (
                    <Badge key={product.id} variant="secondary">
                      {product.name}
                    </Badge>
                  ))}
                  {selectedProducts.length > 5 && (
                    <Badge variant="outline">
                      +{selectedProducts.length - 5} more
                    </Badge>
                  )}
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Enhanced Categories</h2>
          <p className="text-muted-foreground">
            Manage categories with Shopify integration and batch operations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert>
          <CheckCircle className="h-4 w-4" />
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">
            <Layers className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="analytics">
            <BarChart3 className="h-4 w-4 mr-2" />
            Analytics
          </TabsTrigger>
          <TabsTrigger value="sync">
            <RefreshCw className="h-4 w-4 mr-2" />
            Shopify Sync
          </TabsTrigger>
          <TabsTrigger value="batch">
            <Users className="h-4 w-4 mr-2" />
            Batch Assignment
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">{renderOverview()}</TabsContent>
        <TabsContent value="analytics">{renderAnalytics()}</TabsContent>
        <TabsContent value="sync">{renderSync()}</TabsContent>
        <TabsContent value="batch">{renderBatch()}</TabsContent>
      </Tabs>

      {/* Batch Assignment Dialog */}
      <BatchCategoryAssignment
        selectedProducts={selectedProducts}
        isOpen={batchAssignmentOpen}
        onClose={() => setBatchAssignmentOpen(false)}
        onAssign={handleBatchAssignment}
      />
    </div>
  );
}