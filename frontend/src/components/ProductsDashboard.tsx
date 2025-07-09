import React, { useState } from 'react';
import { DashboardSection, DashboardGrid, DashboardCard } from './DashboardLayout';
import { ProductCreationForm, ProductFormData } from './ProductCreationForm';
import { Button } from '@/components/ui/button';
import { Plus, Package, TrendingUp, ShoppingCart, ArrowLeft } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CheckCircle2, AlertCircle } from 'lucide-react';

export function ProductsDashboard() {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);

  const handleCreateProduct = async (productData: ProductFormData) => {
    setIsCreating(true);
    setCreateError(null);
    setCreateSuccess(null);

    try {
      const token = localStorage.getItem('authToken') || 'dev-token';
      
      const response = await fetch('http://localhost:3560/api/shopify/products', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(productData)
      });

      const result = await response.json();

      if (response.ok) {
        setCreateSuccess(`Product "${productData.title}" created successfully!`);
        // Auto-close form after success
        setTimeout(() => {
          setShowCreateForm(false);
          setCreateSuccess(null);
        }, 2000);
      } else {
        setCreateError(result.error || 'Failed to create product');
      }
    } catch (error) {
      console.error('Error creating product:', error);
      setCreateError('Network error. Please try again.');
    } finally {
      setIsCreating(false);
    }
  };

  const handleCancelCreate = () => {
    setShowCreateForm(false);
    setCreateError(null);
    setCreateSuccess(null);
  };

  if (showCreateForm) {
    return (
      <div className="space-y-6">
        {/* Header with back button */}
        <div className="flex items-center gap-4 mb-6">
          <Button 
            variant="outline" 
            onClick={handleCancelCreate}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Products
          </Button>
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Create New Product</h2>
            <p className="text-muted-foreground">Add a new product to your Shopify store</p>
          </div>
        </div>

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
          onCancel={handleCancelCreate}
          isLoading={isCreating}
          error={createError}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Products</h1>
          <p className="text-muted-foreground">
            Manage your product catalog and create new products for Shopify
          </p>
        </div>
        <Button 
          onClick={() => setShowCreateForm(true)}
          className="flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Create New Product
        </Button>
      </div>

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
              <div className="text-2xl font-bold">1,234</div>
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
              <div className="text-2xl font-bold">987</div>
              <p className="text-sm text-muted-foreground">80% sync rate</p>
            </div>
          </div>
        </DashboardCard>

        <DashboardCard
          title="Revenue"
          description="This month's performance"
          className="flex flex-col"
        >
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center w-12 h-12 bg-purple-100 rounded-lg">
              <TrendingUp className="h-6 w-6 text-purple-600" />
            </div>
            <div>
              <div className="text-2xl font-bold">$24,590</div>
              <p className="text-sm text-muted-foreground">+12% from last month</p>
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
            Create new products, manage inventory, sync with Shopify, and track performance all from one central dashboard.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button 
              onClick={() => setShowCreateForm(true)}
              className="flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              Create Product
            </Button>
            <Button variant="outline" className="flex items-center gap-2">
              <Package className="h-4 w-4" />
              Browse Products
            </Button>
            <Button variant="outline" className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              View Analytics
            </Button>
          </div>
        </div>
      </DashboardSection>
    </div>
  );
}