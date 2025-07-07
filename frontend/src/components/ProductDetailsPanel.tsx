import React from 'react';
import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  X,
  Package,
  DollarSign,
  Tag,
  Calendar,
  ExternalLink,
  Edit,
  Copy,
  Trash2
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

interface ProductDetailsPanelProps {
  product: Product;
  onClose: () => void;
}

export function ProductDetailsPanel({ product, onClose }: ProductDetailsPanelProps) {
  return (
    <Sheet open={true} onOpenChange={onClose}>
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <div className="flex items-start justify-between">
            <div>
              <SheetTitle>{product.name}</SheetTitle>
              <SheetDescription className="flex items-center gap-2 mt-1">
                <span className="font-mono text-sm">{product.sku}</span>
                {product.shopify_product_id && (
                  <a
                    href={`https://${process.env.REACT_APP_SHOPIFY_SHOP_URL}/admin/products/${product.shopify_product_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800"
                  >
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </SheetDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm">
                <Edit className="h-4 w-4 mr-2" />
                Edit
              </Button>
              <Button variant="ghost" size="sm" onClick={onClose}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </SheetHeader>

        <Tabs defaultValue="details" className="mt-6">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="inventory">Inventory</TabsTrigger>
            <TabsTrigger value="metadata">Metadata</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
          </TabsList>

          <TabsContent value="details" className="space-y-6">
            {/* Basic Information */}
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-3">Basic Information</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Status</span>
                  <Badge>{product.status}</Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Category</span>
                  <span className="text-sm">{product.category?.name || 'Uncategorized'}</span>
                </div>
                {product.product_type && (
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">Product Type</span>
                    <span className="text-sm">{product.product_type}</span>
                  </div>
                )}
                {product.brand && (
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">Brand</span>
                    <span className="text-sm">{product.brand}</span>
                  </div>
                )}
                {product.manufacturer && (
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">Manufacturer</span>
                    <span className="text-sm">{product.manufacturer}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Pricing */}
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-3">Pricing</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Regular Price</span>
                  <span className="text-sm font-medium">${product.price.toFixed(2)}</span>
                </div>
              </div>
            </div>

            {/* Description */}
            {product.description && (
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-3">Description</h3>
                <p className="text-sm">{product.description}</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="inventory" className="space-y-6">
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-3">Stock Levels</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Available</span>
                  <span className="text-sm font-medium">
                    {product.inventory_quantity !== undefined ? product.inventory_quantity : 'Not tracked'}
                  </span>
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="metadata" className="space-y-6">
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-3">Shopify Integration</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Shopify ID</span>
                  <span className="text-sm font-mono">
                    {product.shopify_product_id || 'Not synced'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Sync Status</span>
                  <Badge variant={product.shopify_sync_status === 'synced' ? 'default' : 'outline'}>
                    {product.shopify_sync_status || 'Not synced'}
                  </Badge>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-3">System Information</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Product ID</span>
                  <span className="text-sm font-mono">{product.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Created</span>
                  <span className="text-sm">
                    {new Date(product.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Last Updated</span>
                  <span className="text-sm">
                    {new Date(product.updated_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="history" className="space-y-6">
            <p className="text-sm text-muted-foreground">Product history and audit trail coming soon...</p>
          </TabsContent>
        </Tabs>

        <div className="mt-6 pt-6 border-t flex justify-end gap-2">
          <Button variant="outline" size="sm">
            <Copy className="h-4 w-4 mr-2" />
            Duplicate
          </Button>
          <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}