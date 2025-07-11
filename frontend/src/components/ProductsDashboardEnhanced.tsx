import React, { useState, useEffect } from 'react';
import { DashboardSection, DashboardGrid, DashboardCard } from './DashboardLayout';
import { ProductCreationForm, ProductFormData } from './ProductCreationForm';
import { ProductsTableView } from './ProductsTableView';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Plus, Package, TrendingUp, ShoppingCart, List, BarChart3, GitBranch } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CheckCircle2, AlertCircle } from 'lucide-react';
import { apiClient } from '@/lib/api';

interface ProductStats {
  totalProducts: number;
  shopifySynced: number;
  stagingChanges: number;
}

export function ProductsDashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
  const [stats, setStats] = useState<ProductStats>({
    totalProducts: 0,
    shopifySynced: 0,
    stagingChanges: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardStats();
    const interval = setInterval(fetchDashboardStats, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardStats = async () => {
    try {
      const data = await apiClient.get('/dashboard/products/enhanced-stats');
      if (data && typeof data === 'object') {
        setStats(data as ProductStats);
      } else {
        // Keep default stats if API returns invalid data
        console.warn('Invalid stats data received:', data);
      }
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error);
      // Keep default stats on error
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProduct = async (productData: ProductFormData) => {
    setIsCreating(true);
    setCreateError(null);
    setCreateSuccess(null);

    try {
      const result = await apiClient.post('/shopify/products', productData);
      setCreateSuccess(`Product "${productData.title}" created successfully!`);
      // Auto-switch to products tab after success
      setTimeout(() => {
        setActiveTab('products');
        setCreateSuccess(null);
      }, 2000);
    } catch (error: any) {
      console.error('Error creating product:', error);
      setCreateError(error.message || 'Network error. Please try again.');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Products</h1>
          <p className="text-muted-foreground">
            Manage your product catalog with staging layer and Shopify sync
          </p>
        </div>
        <Button 
          onClick={() => setActiveTab('create')}
          className="flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Create New Product
        </Button>
      </div>

      {/* Main Content with Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="products" className="flex items-center gap-2">
            <List className="h-4 w-4" />
            Product List
          </TabsTrigger>
          <TabsTrigger value="create" className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Create Product
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {/* Stats Cards */}
          <DashboardGrid columns={3}>
            <DashboardCard
              title="Total Products"
              description="Products in your catalog"
              className="flex flex-col"
            >
              <div className="flex items-center gap-4">
                <div className="flex items-center justify-center w-12 h-12 bg-blue-100 rounded-lg">
                  <Package className="h-6 w-6 text-blue-600" />
                </div>
                <div>
                  <div className="text-2xl font-bold">
                    {loading ? '...' : (stats?.totalProducts || 0).toLocaleString()}
                  </div>
                  <p className="text-sm text-muted-foreground">Active products</p>
                </div>
              </div>
            </DashboardCard>

            <DashboardCard
              title="Shopify Synced"
              description="Products synced to Shopify"
              className="flex flex-col"
            >
              <div className="flex items-center gap-4">
                <div className="flex items-center justify-center w-12 h-12 bg-green-100 rounded-lg">
                  <ShoppingCart className="h-6 w-6 text-green-600" />
                </div>
                <div>
                  <div className="text-2xl font-bold">
                    {loading ? '...' : (stats?.shopifySynced || 0).toLocaleString()}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {loading ? '...' : `${Math.round(((stats?.shopifySynced || 0) / (stats?.totalProducts || 1)) * 100)}% sync rate`}
                  </p>
                </div>
              </div>
            </DashboardCard>

            <DashboardCard
              title="Staging Changes"
              description="Pending sync operations"
              className="flex flex-col"
            >
              <div className="flex items-center gap-4">
                <div className="flex items-center justify-center w-12 h-12 bg-orange-100 rounded-lg">
                  <GitBranch className="h-6 w-6 text-orange-600" />
                </div>
                <div>
                  <div className="text-2xl font-bold">
                    {loading ? '...' : (stats?.stagingChanges || 0)}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {(stats?.stagingChanges || 0) > 0 ? 'Pending changes' : 'All up to date'}
                  </p>
                </div>
              </div>
            </DashboardCard>
          </DashboardGrid>

          {/* Quick Actions */}
          <DashboardSection>
            <div className="text-center py-12">
              <Package className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">Product Management Hub</h3>
              <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                Create new products, manage inventory, sync with Shopify, and track performance with visual staging layer.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button 
                  onClick={() => setActiveTab('create')}
                  className="flex items-center gap-2"
                >
                  <Plus className="h-4 w-4" />
                  Create Product
                </Button>
                <Button 
                  variant="outline" 
                  className="flex items-center gap-2"
                  onClick={() => setActiveTab('products')}
                >
                  <List className="h-4 w-4" />
                  Browse Products
                </Button>
                <Button variant="outline" className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  View Analytics
                </Button>
              </div>
            </div>
          </DashboardSection>
        </TabsContent>

        <TabsContent value="products">
          <ProductsTableView />
        </TabsContent>

        <TabsContent value="create">
          <div className="space-y-6">
            {/* Success/Error Messages */}
            {createSuccess && (
              <Alert>
                <CheckCircle2 className="h-4 w-4" />
                <AlertDescription>{createSuccess}</AlertDescription>
              </Alert>
            )}

            {createError && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{createError}</AlertDescription>
              </Alert>
            )}

            {/* Product Creation Form */}
            <ProductCreationForm
              onSubmit={handleCreateProduct}
              onCancel={() => setActiveTab('overview')}
              isLoading={isCreating}
              error={createError}
            />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}