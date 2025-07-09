/**
 * Batch Category Assignment Component
 * 
 * Provides batch assignment of products to categories with Shopify integration
 */

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Package, 
  Tag, 
  Layers, 
  ShoppingCart, 
  CheckCircle, 
  AlertCircle, 
  Loader2,
  X,
  Plus
} from 'lucide-react';

export interface Product {
  id: number;
  name: string;
  sku: string;
  price: number;
  category_id?: number;
  product_type?: string;
  collections?: number[];
  shopify_product_id?: string;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  product_count: number;
  shopify_collection_id?: string;
}

export interface Collection {
  id: number;
  name: string;
  handle: string;
  product_count: number;
  shopify_collection_id?: string;
}

export interface ShopifyTaxonomy {
  product_types: Array<{
    name: string;
    product_count: number;
  }>;
  collections: Collection[];
  popular_tags: Array<{
    name: string;
    product_count: number;
  }>;
}

export interface BatchAssignmentProps {
  selectedProducts: Product[];
  isOpen: boolean;
  onClose: () => void;
  onAssign: (assignments: CategoryAssignments) => Promise<void>;
}

export interface CategoryAssignments {
  category_ids?: number[];
  product_type?: string;
  collections?: number[];
  tags?: string[];
  sync_to_shopify?: boolean;
  remove_existing?: boolean;
}

export function BatchCategoryAssignment({ 
  selectedProducts, 
  isOpen, 
  onClose, 
  onAssign 
}: BatchAssignmentProps) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [shopifyTaxonomy, setShopifyTaxonomy] = useState<ShopifyTaxonomy | null>(null);
  const [loading, setLoading] = useState(false);
  const [taxonomyLoading, setTaxonomyLoading] = useState(false);
  const [assignments, setAssignments] = useState<CategoryAssignments>({
    category_ids: [],
    collections: [],
    tags: [],
    sync_to_shopify: true,
    remove_existing: false
  });
  const [assignmentProgress, setAssignmentProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadCategories();
      loadCollections();
      loadShopifyTaxonomy();
    }
  }, [isOpen]);

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
      }
    } catch (error) {
      console.error('Error loading categories:', error);
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
      }
    } catch (error) {
      console.error('Error loading collections:', error);
    }
  };

  const loadShopifyTaxonomy = async () => {
    try {
      setTaxonomyLoading(true);
      const response = await fetch('/api/categories/enhanced/shopify-taxonomy', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setShopifyTaxonomy(data.taxonomy);
      }
    } catch (error) {
      console.error('Error loading Shopify taxonomy:', error);
    } finally {
      setTaxonomyLoading(false);
    }
  };

  const handleAssign = async () => {
    if (selectedProducts.length === 0) {
      setError('No products selected');
      return;
    }

    setLoading(true);
    setError(null);
    setAssignmentProgress(0);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setAssignmentProgress(prev => Math.min(prev + 10, 90));
      }, 200);

      await onAssign(assignments);
      
      clearInterval(progressInterval);
      setAssignmentProgress(100);
      
      setTimeout(() => {
        onClose();
        setAssignmentProgress(0);
      }, 1000);
    } catch (error: any) {
      setError(error.message || 'Failed to assign categories');
      setAssignmentProgress(0);
    } finally {
      setLoading(false);
    }
  };

  const addCustomTag = (tag: string) => {
    if (tag && !assignments.tags?.includes(tag)) {
      setAssignments(prev => ({
        ...prev,
        tags: [...(prev.tags || []), tag]
      }));
    }
  };

  const removeTag = (tagToRemove: string) => {
    setAssignments(prev => ({
      ...prev,
      tags: prev.tags?.filter(tag => tag !== tagToRemove) || []
    }));
  };

  const toggleCollection = (collectionId: number) => {
    setAssignments(prev => {
      const collections = prev.collections || [];
      const isSelected = collections.includes(collectionId);
      
      return {
        ...prev,
        collections: isSelected
          ? collections.filter(id => id !== collectionId)
          : [...collections, collectionId]
      };
    });
  };

  const toggleCategory = (categoryId: number) => {
    setAssignments(prev => {
      const categories = prev.category_ids || [];
      const isSelected = categories.includes(categoryId);
      
      return {
        ...prev,
        category_ids: isSelected
          ? categories.filter(id => id !== categoryId)
          : [...categories, categoryId]
      };
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Batch Category Assignment</DialogTitle>
          <DialogDescription>
            Assign {selectedProducts.length} product{selectedProducts.length !== 1 ? 's' : ''} to categories and collections
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Processing assignments...</span>
            </div>
            <Progress value={assignmentProgress} className="w-full" />
          </div>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Tabs defaultValue="categories" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="categories">Categories</TabsTrigger>
            <TabsTrigger value="collections">Collections</TabsTrigger>
            <TabsTrigger value="product-types">Product Types</TabsTrigger>
            <TabsTrigger value="tags">Tags</TabsTrigger>
          </TabsList>

          <TabsContent value="categories" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Layers className="h-5 w-5" />
                  Select Categories
                </CardTitle>
                <CardDescription>
                  Choose categories to assign to the selected products
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-60 overflow-y-auto">
                  {categories.map(category => (
                    <div
                      key={category.id}
                      className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                        assignments.category_ids?.includes(category.id)
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                      onClick={() => toggleCategory(category.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium">{category.name}</div>
                          <div className="text-sm text-gray-500">
                            {category.product_count} products
                          </div>
                        </div>
                        <Checkbox
                          checked={assignments.category_ids?.includes(category.id)}
                          disabled
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="collections" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShoppingCart className="h-5 w-5" />
                  Select Collections
                </CardTitle>
                <CardDescription>
                  Choose collections to assign to the selected products
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-60 overflow-y-auto">
                  {collections.map(collection => (
                    <div
                      key={collection.id}
                      className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                        assignments.collections?.includes(collection.id)
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                      onClick={() => toggleCollection(collection.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium">{collection.name}</div>
                          <div className="text-sm text-gray-500">
                            {collection.product_count} products
                            {collection.shopify_collection_id && (
                              <Badge variant="outline" className="ml-2">Shopify</Badge>
                            )}
                          </div>
                        </div>
                        <Checkbox
                          checked={assignments.collections?.includes(collection.id)}
                          disabled
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="product-types" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Package className="h-5 w-5" />
                  Product Type
                </CardTitle>
                <CardDescription>
                  Select a product type for the selected products
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <Select
                    value={assignments.product_type || ''}
                    onValueChange={(value) => setAssignments(prev => ({
                      ...prev,
                      product_type: value
                    }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select product type" />
                    </SelectTrigger>
                    <SelectContent>
                      {shopifyTaxonomy?.product_types.map(type => (
                        <SelectItem key={type.name} value={type.name}>
                          {type.name} ({type.product_count} products)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  {taxonomyLoading && (
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading Shopify product types...
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="tags" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Tag className="h-5 w-5" />
                  Tags
                </CardTitle>
                <CardDescription>
                  Add tags to the selected products
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {/* Custom tag input */}
                  <div className="flex gap-2">
                    <Input
                      placeholder="Add custom tag"
                      onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                          addCustomTag(e.currentTarget.value);
                          e.currentTarget.value = '';
                        }
                      }}
                    />
                    <Button
                      variant="outline"
                      onClick={() => {
                        const input = document.querySelector('input[placeholder="Add custom tag"]') as HTMLInputElement;
                        if (input?.value) {
                          addCustomTag(input.value);
                          input.value = '';
                        }
                      }}
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* Selected tags */}
                  {assignments.tags && assignments.tags.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {assignments.tags.map(tag => (
                        <Badge key={tag} variant="secondary" className="gap-1">
                          {tag}
                          <X
                            className="h-3 w-3 cursor-pointer"
                            onClick={() => removeTag(tag)}
                          />
                        </Badge>
                      ))}
                    </div>
                  )}

                  {/* Popular tags from Shopify */}
                  {shopifyTaxonomy?.popular_tags && shopifyTaxonomy.popular_tags.length > 0 && (
                    <div className="space-y-2">
                      <Label className="text-sm font-medium">Popular Tags:</Label>
                      <div className="flex flex-wrap gap-2">
                        {shopifyTaxonomy.popular_tags.map(tag => (
                          <Badge
                            key={tag.name}
                            variant="outline"
                            className="cursor-pointer hover:bg-gray-100"
                            onClick={() => addCustomTag(tag.name)}
                          >
                            {tag.name} ({tag.product_count})
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Assignment Options */}
        <Card>
          <CardHeader>
            <CardTitle>Assignment Options</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="sync-to-shopify"
                  checked={assignments.sync_to_shopify}
                  onCheckedChange={(checked) => setAssignments(prev => ({
                    ...prev,
                    sync_to_shopify: checked as boolean
                  }))}
                />
                <Label htmlFor="sync-to-shopify">
                  Sync changes to Shopify
                </Label>
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id="remove-existing"
                  checked={assignments.remove_existing}
                  onCheckedChange={(checked) => setAssignments(prev => ({
                    ...prev,
                    remove_existing: checked as boolean
                  }))}
                />
                <Label htmlFor="remove-existing">
                  Remove existing assignments before adding new ones
                </Label>
              </div>
            </div>
          </CardContent>
        </Card>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleAssign} disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <CheckCircle className="mr-2 h-4 w-4" />
                Assign Categories
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}