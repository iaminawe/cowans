import React, { useState } from 'react';
import { cn } from "@/lib/utils";
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProductsTable } from './ProductsTable';
import { ProductDetailsPanel } from './ProductDetailsPanel';
import { ProductImporter } from './ProductImporter';
import { ProductAnalytics } from './ProductAnalytics';
import { 
  Package,
  BarChart,
  Upload,
  Grid
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

export function ProductsDashboard() {
  const [activeTab, setActiveTab] = useState<'browse' | 'import' | 'analytics'>('browse');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  const handleBatchAction = (action: string, productIds: number[]) => {
    console.log(`Batch action: ${action} on products:`, productIds);
    // Handle batch actions here
  };

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-3 max-w-md">
          <TabsTrigger value="browse">
            <Grid className="h-4 w-4 mr-2" />
            Browse
          </TabsTrigger>
          <TabsTrigger value="import">
            <Upload className="h-4 w-4 mr-2" />
            Import
          </TabsTrigger>
          <TabsTrigger value="analytics">
            <BarChart className="h-4 w-4 mr-2" />
            Analytics
          </TabsTrigger>
        </TabsList>

        <TabsContent value="browse" className="space-y-4">
          <ProductsTable 
            onSelectProduct={setSelectedProduct}
            onBatchAction={handleBatchAction}
          />
        </TabsContent>

        <TabsContent value="import" className="space-y-4">
          <ProductImporter />
        </TabsContent>

        <TabsContent value="analytics" className="space-y-4">
          <ProductAnalytics />
        </TabsContent>
      </Tabs>

      {/* Product Details Sidebar */}
      {selectedProduct && (
        <ProductDetailsPanel
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
        />
      )}
    </div>
  );
}