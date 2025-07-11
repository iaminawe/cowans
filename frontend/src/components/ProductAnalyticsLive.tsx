import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Package, 
  DollarSign, 
  TrendingUp, 
  AlertCircle,
  ShoppingCart,
  BarChart,
  PieChart,
  Activity
} from 'lucide-react';
import { apiClient } from '@/lib/api';

interface AnalyticsData {
  stats: {
    totalProducts: number;
    activeProducts: number;
    totalInventoryValue: number;
    averagePrice: number;
    lowStock: number;
    outOfStock: number;
  };
  categoryBreakdown: Array<{
    category: string;
    count: number;
    value: number;
  }>;
  priceDistribution: Array<{
    range?: string;
    price_range?: string;
    count: number;
  }>;
  inventoryTrends: Array<{
    date: string;
    total_inventory: number;
  }>;
  topProducts: Array<{
    name: string;
    price: number;
    inventory_quantity: number;
    total_value: number;
  }>;
  brandPerformance: Array<{
    vendor: string;
    product_count: number;
    avg_price: number;
    total_inventory: number;
  }>;
}

export function ProductAnalyticsLive() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const fetchAnalytics = async () => {
    try {
      const data = await apiClient.get('/dashboard/analytics/stats');
      setData(data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch analytics:', err);
      setError(err.message || 'Failed to load analytics data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="grid gap-4 md:gap-6">
        <div className="text-center py-12">
          <Activity className="h-8 w-8 animate-pulse mx-auto mb-4" />
          <p className="text-muted-foreground">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          {error || 'No data available'}
        </AlertDescription>
      </Alert>
    );
  }

  const { stats, categoryBreakdown, priceDistribution, topProducts, brandPerformance } = data;

  return (
    <div className="space-y-6">
      {/* Overview Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Products</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(stats?.totalProducts || 0).toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              {(stats?.activeProducts || 0).toLocaleString()} active
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Inventory Value</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${stats.totalInventoryValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <p className="text-xs text-muted-foreground">
              Avg price: ${stats.averagePrice.toFixed(2)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Stock Alerts</CardTitle>
            <AlertCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-4">
              <div>
                <div className="text-2xl font-bold text-yellow-600">{stats.lowStock}</div>
                <p className="text-xs text-muted-foreground">Low stock</p>
              </div>
              <div>
                <div className="text-2xl font-bold text-red-600">{stats.outOfStock}</div>
                <p className="text-xs text-muted-foreground">Out of stock</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Category Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Top Categories</CardTitle>
          <CardDescription>Products and value by category</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {categoryBreakdown.slice(0, 5).map((category, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{category.category || 'Uncategorized'}</span>
                    <span className="text-sm text-muted-foreground">
                      {category.count} products
                    </span>
                  </div>
                  <Progress 
                    value={(category.count / (stats?.totalProducts || 1)) * 100} 
                    className="h-2"
                  />
                </div>
                <Badge variant="secondary" className="ml-4">
                  ${(category.value || 0).toLocaleString()}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Price Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Price Distribution</CardTitle>
            <CardDescription>Products by price range</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {priceDistribution.map((range, index) => (
                <div key={index} className="flex items-center justify-between">
                  <span className="text-sm">{range.price_range || range.range || ''}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{range.count}</span>
                    <div className="w-24">
                      <Progress 
                        value={(range.count / (stats?.totalProducts || 1)) * 100} 
                        className="h-2"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top Products by Value */}
        <Card>
          <CardHeader>
            <CardTitle>Top Products by Value</CardTitle>
            <CardDescription>Highest inventory value items</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {topProducts.slice(0, 5).map((product, index) => (
                <div key={index} className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{product.name}</p>
                    <p className="text-xs text-muted-foreground">
                      ${product.price} × {product.inventory_quantity} units
                    </p>
                  </div>
                  <Badge variant="outline">
                    ${product.total_value.toLocaleString()}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Brand Performance */}
      <Card>
        <CardHeader>
          <CardTitle>Top Brands</CardTitle>
          <CardDescription>Performance by vendor</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {brandPerformance.slice(0, 10).map((brand, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex-1">
                  <p className="text-sm font-medium">{brand.vendor}</p>
                  <p className="text-xs text-muted-foreground">
                    {brand.product_count} products • Avg: ${brand.avg_price.toFixed(2)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium">{brand.total_inventory.toLocaleString()} units</p>
                  <p className="text-xs text-muted-foreground">Total inventory</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}