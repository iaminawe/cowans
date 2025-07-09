import React, { useState, useRef } from 'react';
import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { 
  Package, 
  DollarSign, 
  Warehouse, 
  Truck, 
  Search,
  Plus,
  X,
  Save,
  AlertCircle,
  Loader2,
  Image as ImageIcon,
  Upload
} from 'lucide-react';

export interface ProductFormData {
  title: string;
  description: string;
  handle: string;
  vendor: string;
  productType: string;
  tags: string[];
  status: 'DRAFT' | 'ACTIVE' | 'ARCHIVED';
  price: string;
  compareAtPrice: string;
  costPerItem: string;
  taxable: boolean;
  sku: string;
  barcode: string;
  inventoryQuantity: string;
  inventoryPolicy: 'DENY' | 'CONTINUE';
  inventoryTracked: boolean;
  weight: string;
  weightUnit: 'GRAMS' | 'KILOGRAMS' | 'POUNDS' | 'OUNCES';
  requiresShipping: boolean;
  seoTitle: string;
  seoDescription: string;
  images: File[];
}

interface ProductCreationFormProps {
  onSubmit: (data: ProductFormData) => Promise<void>;
  onCancel: () => void;
  initialData?: Partial<ProductFormData>;
  isLoading?: boolean;
  error?: string | null;
  className?: string;
}

const defaultFormData: ProductFormData = {
  title: '',
  description: '',
  handle: '',
  vendor: '',
  productType: '',
  tags: [],
  status: 'DRAFT',
  price: '',
  compareAtPrice: '',
  costPerItem: '',
  taxable: true,
  sku: '',
  barcode: '',
  inventoryQuantity: '0',
  inventoryPolicy: 'DENY',
  inventoryTracked: true,
  weight: '',
  weightUnit: 'POUNDS',
  requiresShipping: true,
  seoTitle: '',
  seoDescription: '',
  images: []
};

export function ProductCreationForm({
  onSubmit,
  onCancel,
  initialData = {},
  isLoading = false,
  error = null,
  className
}: ProductCreationFormProps) {
  const [formData, setFormData] = useState<ProductFormData>({
    ...defaultFormData,
    ...initialData
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [currentTag, setCurrentTag] = useState('');
  const [activeTab, setActiveTab] = useState('general');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-generate handle from title
  const generateHandle = (title: string): string => {
    return title
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .trim()
      .substring(0, 100);
  };

  const updateFormData = (field: keyof ProductFormData, value: any) => {
    setFormData(prev => {
      const updated = { ...prev, [field]: value };
      
      // Auto-generate handle when title changes
      if (field === 'title' && value) {
        updated.handle = generateHandle(value);
        // Auto-generate SEO title if not manually set
        if (!prev.seoTitle || prev.seoTitle === prev.title) {
          updated.seoTitle = value.substring(0, 60);
        }
      }
      
      return updated;
    });
    
    // Clear error when field is updated
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.title.trim()) {
      newErrors.title = 'Product title is required';
    }

    if (!formData.description.trim()) {
      newErrors.description = 'Product description is required';
    }

    if (!formData.vendor.trim()) {
      newErrors.vendor = 'Vendor is required';
    }

    if (!formData.productType.trim()) {
      newErrors.productType = 'Product type is required';
    }

    if (!formData.price || parseFloat(formData.price) <= 0) {
      newErrors.price = 'Valid price is required';
    }

    if (formData.compareAtPrice && parseFloat(formData.compareAtPrice) <= parseFloat(formData.price)) {
      newErrors.compareAtPrice = 'Compare at price must be higher than price';
    }

    if (formData.requiresShipping && (!formData.weight || parseFloat(formData.weight) <= 0)) {
      newErrors.weight = 'Weight is required for shippable products';
    }

    if (formData.seoTitle && formData.seoTitle.length > 60) {
      newErrors.seoTitle = 'SEO title must be 60 characters or less';
    }

    if (formData.seoDescription && formData.seoDescription.length > 160) {
      newErrors.seoDescription = 'SEO description must be 160 characters or less';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      await onSubmit(formData);
    } catch (err) {
      console.error('Form submission error:', err);
    }
  };

  const addTag = (tag: string) => {
    const trimmedTag = tag.trim();
    if (trimmedTag && !formData.tags.includes(trimmedTag)) {
      updateFormData('tags', [...formData.tags, trimmedTag]);
    }
    setCurrentTag('');
  };

  const removeTag = (tagToRemove: string) => {
    updateFormData('tags', formData.tags.filter(tag => tag !== tagToRemove));
  };

  const handleTagInput = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(currentTag);
    }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    updateFormData('images', [...formData.images, ...files]);
  };

  const removeImage = (index: number) => {
    updateFormData('images', formData.images.filter((_, i) => i !== index));
  };

  return (
    <Card className={cn("max-w-4xl mx-auto", className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Package className="h-5 w-5" />
          Create New Product
        </CardTitle>
        <CardDescription>
          Add a new product to your Shopify store with all the details
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-5">
              <TabsTrigger value="general">General</TabsTrigger>
              <TabsTrigger value="pricing">Pricing</TabsTrigger>
              <TabsTrigger value="inventory">Inventory</TabsTrigger>
              <TabsTrigger value="shipping">Shipping</TabsTrigger>
              <TabsTrigger value="seo">SEO</TabsTrigger>
            </TabsList>

            {/* General Tab */}
            <TabsContent value="general" className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <Label htmlFor="title">Product Title *</Label>
                  <Input
                    id="title"
                    value={formData.title}
                    onChange={(e) => updateFormData('title', e.target.value)}
                    placeholder="Enter product title"
                    className={errors.title ? 'border-red-500' : ''}
                  />
                  {errors.title && <p className="text-sm text-red-500 mt-1">{errors.title}</p>}
                </div>

                <div className="md:col-span-2">
                  <Label htmlFor="description">Description *</Label>
                  <Textarea
                    id="description"
                    value={formData.description}
                    onChange={(e) => updateFormData('description', e.target.value)}
                    placeholder="Enter product description"
                    rows={4}
                    className={errors.description ? 'border-red-500' : ''}
                  />
                  {errors.description && <p className="text-sm text-red-500 mt-1">{errors.description}</p>}
                </div>

                <div>
                  <Label htmlFor="handle">URL Handle</Label>
                  <Input
                    id="handle"
                    value={formData.handle}
                    onChange={(e) => updateFormData('handle', e.target.value)}
                    placeholder="product-handle"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Auto-generated from title. Used in product URL.
                  </p>
                </div>

                <div>
                  <Label htmlFor="vendor">Vendor *</Label>
                  <Input
                    id="vendor"
                    value={formData.vendor}
                    onChange={(e) => updateFormData('vendor', e.target.value)}
                    placeholder="Enter vendor name"
                    className={errors.vendor ? 'border-red-500' : ''}
                  />
                  {errors.vendor && <p className="text-sm text-red-500 mt-1">{errors.vendor}</p>}
                </div>

                <div>
                  <Label htmlFor="productType">Product Type *</Label>
                  <Input
                    id="productType"
                    value={formData.productType}
                    onChange={(e) => updateFormData('productType', e.target.value)}
                    placeholder="Enter product type"
                    className={errors.productType ? 'border-red-500' : ''}
                  />
                  {errors.productType && <p className="text-sm text-red-500 mt-1">{errors.productType}</p>}
                </div>

                <div>
                  <Label htmlFor="status">Status</Label>
                  <Select value={formData.status} onValueChange={(value: 'DRAFT' | 'ACTIVE' | 'ARCHIVED') => updateFormData('status', value)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="DRAFT">Draft</SelectItem>
                      <SelectItem value="ACTIVE">Active</SelectItem>
                      <SelectItem value="ARCHIVED">Archived</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="md:col-span-2">
                  <Label htmlFor="tags">Tags</Label>
                  <div className="space-y-2">
                    <Input
                      id="tags"
                      value={currentTag}
                      onChange={(e) => setCurrentTag(e.target.value)}
                      onKeyDown={handleTagInput}
                      placeholder="Enter tags and press Enter or comma"
                    />
                    <div className="flex flex-wrap gap-2">
                      {formData.tags.map((tag, index) => (
                        <Badge key={index} variant="secondary" className="flex items-center gap-1">
                          {tag}
                          <X
                            className="h-3 w-3 cursor-pointer"
                            onClick={() => removeTag(tag)}
                          />
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="md:col-span-2">
                  <Label>Product Images</Label>
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      accept="image/*"
                      onChange={handleImageUpload}
                      className="hidden"
                    />
                    <div className="text-center">
                      <ImageIcon className="h-12 w-12 text-gray-400 mx-auto mb-2" />
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => fileInputRef.current?.click()}
                      >
                        <Upload className="h-4 w-4 mr-2" />
                        Upload Images
                      </Button>
                      <p className="text-sm text-muted-foreground mt-2">
                        PNG, JPG, GIF up to 10MB each
                      </p>
                    </div>
                    {formData.images.length > 0 && (
                      <div className="mt-4 grid grid-cols-3 gap-2">
                        {formData.images.map((file, index) => (
                          <div key={index} className="relative">
                            <img
                              src={URL.createObjectURL(file)}
                              alt={`Upload ${index + 1}`}
                              className="w-full h-20 object-cover rounded"
                            />
                            <Button
                              type="button"
                              variant="destructive"
                              size="sm"
                              className="absolute -top-2 -right-2 h-6 w-6 p-0"
                              onClick={() => removeImage(index)}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* Pricing Tab */}
            <TabsContent value="pricing" className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label htmlFor="price">Price * ($)</Label>
                  <div className="relative">
                    <DollarSign className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="price"
                      type="number"
                      step="0.01"
                      value={formData.price}
                      onChange={(e) => updateFormData('price', e.target.value)}
                      placeholder="0.00"
                      className={cn("pl-8", errors.price ? 'border-red-500' : '')}
                    />
                  </div>
                  {errors.price && <p className="text-sm text-red-500 mt-1">{errors.price}</p>}
                </div>

                <div>
                  <Label htmlFor="compareAtPrice">Compare at Price ($)</Label>
                  <div className="relative">
                    <DollarSign className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="compareAtPrice"
                      type="number"
                      step="0.01"
                      value={formData.compareAtPrice}
                      onChange={(e) => updateFormData('compareAtPrice', e.target.value)}
                      placeholder="0.00"
                      className={cn("pl-8", errors.compareAtPrice ? 'border-red-500' : '')}
                    />
                  </div>
                  {errors.compareAtPrice && <p className="text-sm text-red-500 mt-1">{errors.compareAtPrice}</p>}
                  <p className="text-xs text-muted-foreground mt-1">
                    Used to show sale pricing
                  </p>
                </div>

                <div>
                  <Label htmlFor="costPerItem">Cost per Item ($)</Label>
                  <div className="relative">
                    <DollarSign className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="costPerItem"
                      type="number"
                      step="0.01"
                      value={formData.costPerItem}
                      onChange={(e) => updateFormData('costPerItem', e.target.value)}
                      placeholder="0.00"
                      className="pl-8"
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    For profit calculations
                  </p>
                </div>

                <div className="md:col-span-3">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="taxable"
                      checked={formData.taxable}
                      onCheckedChange={(checked: boolean) => updateFormData('taxable', checked)}
                    />
                    <Label htmlFor="taxable">Charge tax on this product</Label>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* Inventory Tab */}
            <TabsContent value="inventory" className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="sku">SKU</Label>
                  <Input
                    id="sku"
                    value={formData.sku}
                    onChange={(e) => updateFormData('sku', e.target.value)}
                    placeholder="Enter SKU"
                  />
                </div>

                <div>
                  <Label htmlFor="barcode">Barcode</Label>
                  <Input
                    id="barcode"
                    value={formData.barcode}
                    onChange={(e) => updateFormData('barcode', e.target.value)}
                    placeholder="Enter barcode"
                  />
                </div>

                <div>
                  <Label htmlFor="inventoryQuantity">Inventory Quantity</Label>
                  <div className="relative">
                    <Warehouse className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="inventoryQuantity"
                      type="number"
                      value={formData.inventoryQuantity}
                      onChange={(e) => updateFormData('inventoryQuantity', e.target.value)}
                      placeholder="0"
                      className="pl-8"
                    />
                  </div>
                </div>

                <div>
                  <Label htmlFor="inventoryPolicy">When out of stock</Label>
                  <Select 
                    value={formData.inventoryPolicy} 
                    onValueChange={(value: 'DENY' | 'CONTINUE') => updateFormData('inventoryPolicy', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="DENY">Stop selling</SelectItem>
                      <SelectItem value="CONTINUE">Continue selling</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="md:col-span-2">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="inventoryTracked"
                      checked={formData.inventoryTracked}
                      onCheckedChange={(checked: boolean) => updateFormData('inventoryTracked', checked)}
                    />
                    <Label htmlFor="inventoryTracked">Track inventory for this product</Label>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* Shipping Tab */}
            <TabsContent value="shipping" className="space-y-4">
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="requiresShipping"
                    checked={formData.requiresShipping}
                    onCheckedChange={(checked: boolean) => updateFormData('requiresShipping', checked)}
                  />
                  <Label htmlFor="requiresShipping">This product requires shipping</Label>
                </div>

                {formData.requiresShipping && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="weight">Weight *</Label>
                      <div className="relative">
                        <Truck className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                          id="weight"
                          type="number"
                          step="0.01"
                          value={formData.weight}
                          onChange={(e) => updateFormData('weight', e.target.value)}
                          placeholder="0.00"
                          className={cn("pl-8", errors.weight ? 'border-red-500' : '')}
                        />
                      </div>
                      {errors.weight && <p className="text-sm text-red-500 mt-1">{errors.weight}</p>}
                    </div>

                    <div>
                      <Label htmlFor="weightUnit">Weight Unit</Label>
                      <Select 
                        value={formData.weightUnit} 
                        onValueChange={(value: 'GRAMS' | 'KILOGRAMS' | 'POUNDS' | 'OUNCES') => updateFormData('weightUnit', value)}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="POUNDS">Pounds</SelectItem>
                          <SelectItem value="OUNCES">Ounces</SelectItem>
                          <SelectItem value="KILOGRAMS">Kilograms</SelectItem>
                          <SelectItem value="GRAMS">Grams</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )}
              </div>
            </TabsContent>

            {/* SEO Tab */}
            <TabsContent value="seo" className="space-y-4">
              <div className="space-y-4">
                <div>
                  <Label htmlFor="seoTitle">SEO Title</Label>
                  <Input
                    id="seoTitle"
                    value={formData.seoTitle}
                    onChange={(e) => updateFormData('seoTitle', e.target.value)}
                    placeholder="Enter SEO title"
                    maxLength={60}
                    className={errors.seoTitle ? 'border-red-500' : ''}
                  />
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>{errors.seoTitle || 'Used as the page title in search results'}</span>
                    <span className={formData.seoTitle.length > 60 ? 'text-red-500' : ''}>
                      {formData.seoTitle.length}/60
                    </span>
                  </div>
                </div>

                <div>
                  <Label htmlFor="seoDescription">SEO Description</Label>
                  <Textarea
                    id="seoDescription"
                    value={formData.seoDescription}
                    onChange={(e) => updateFormData('seoDescription', e.target.value)}
                    placeholder="Enter SEO description"
                    maxLength={160}
                    rows={3}
                    className={errors.seoDescription ? 'border-red-500' : ''}
                  />
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>{errors.seoDescription || 'Used as the description in search results'}</span>
                    <span className={formData.seoDescription.length > 160 ? 'text-red-500' : ''}>
                      {formData.seoDescription.length}/160
                    </span>
                  </div>
                </div>

                {/* SEO Preview */}
                <div className="p-4 border rounded-lg bg-muted/50">
                  <h4 className="text-sm font-medium mb-2">Search Engine Preview</h4>
                  <div className="space-y-1">
                    <div className="text-blue-600 text-lg font-medium">
                      {formData.seoTitle || formData.title || 'Product Title'}
                    </div>
                    <div className="text-green-600 text-sm">
                      https://yourstore.com/products/{formData.handle || 'product-handle'}
                    </div>
                    <div className="text-gray-700 text-sm">
                      {formData.seoDescription || formData.description.substring(0, 160) || 'Product description...'}
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>

          {/* Form Actions */}
          <div className="flex items-center justify-between pt-6 border-t">
            <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Creating Product...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Create Product
                </>
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}