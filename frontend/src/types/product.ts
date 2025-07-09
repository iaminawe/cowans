// Comprehensive TypeScript interfaces for Shopify Product API

export interface ShopifyProductVariant {
  id?: string;
  product_id?: string;
  title?: string;
  price: string;
  sku: string;
  position?: number;
  inventory_policy: 'deny' | 'continue';
  compare_at_price?: string;
  fulfillment_service: 'manual' | 'fulfillment_service';
  inventory_management: 'shopify' | 'not_managed' | null;
  option1?: string;
  option2?: string;
  option3?: string;
  created_at?: string;
  updated_at?: string;
  taxable: boolean;
  barcode?: string;
  grams?: number;
  weight?: number;
  weight_unit: 'g' | 'kg' | 'oz' | 'lb';
  inventory_item_id?: string;
  inventory_quantity: number;
  old_inventory_quantity?: number;
  requires_shipping: boolean;
  admin_graphql_api_id?: string;
  image_id?: string;
}

export interface ShopifyProductImage {
  id?: string;
  product_id?: string;
  position?: number;
  created_at?: string;
  updated_at?: string;
  alt?: string;
  width?: number;
  height?: number;
  src: string;
  variant_ids?: string[];
  admin_graphql_api_id?: string;
  filename?: string;
}

export interface ShopifyProductOption {
  id?: string;
  product_id?: string;
  name: string;
  position: number;
  values: string[];
}

export interface ShopifyProductSEO {
  title: string;
  description: string;
}

export interface ShopifyMetafield {
  key: string;
  value: string;
  type: 'single_line_text_field' | 'multi_line_text_field' | 'number_integer' | 'number_decimal' | 'date' | 'date_time' | 'boolean' | 'color' | 'weight' | 'volume' | 'dimension' | 'rating' | 'url' | 'json';
  namespace: string;
  description?: string;
}

export interface ShopifyProduct {
  id?: string;
  title: string;
  body_html: string;
  vendor: string;
  product_type: string;
  created_at?: string;
  handle: string;
  updated_at?: string;
  published_at?: string;
  template_suffix?: string;
  status: 'active' | 'archived' | 'draft';
  published_scope: 'global' | 'web';
  tags: string[];
  admin_graphql_api_id?: string;
  variants: ShopifyProductVariant[];
  options: ShopifyProductOption[];
  images: ShopifyProductImage[];
  image?: ShopifyProductImage;
  seo: ShopifyProductSEO;
  metafields?: ShopifyMetafield[];
}

// Form-specific interfaces
export interface ProductFormData extends Omit<ShopifyProduct, 'id' | 'created_at' | 'updated_at' | 'published_at' | 'admin_graphql_api_id'> {
  published: boolean;
}

export interface ProductFormErrors {
  [key: string]: string;
}

export interface ProductValidationResult {
  isValid: boolean;
  errors: ProductFormErrors;
}

// API Response interfaces
export interface ProductCreationResponse {
  success: boolean;
  product?: ShopifyProduct;
  errors?: Array<{
    field: string;
    message: string;
  }>;
  message?: string;
}

export interface ProductUpdateResponse extends ProductCreationResponse {}

export interface ProductDeletionResponse {
  success: boolean;
  message?: string;
  errors?: Array<{
    field: string;
    message: string;
  }>;
}

// Form field configurations
export interface FormFieldConfig {
  label: string;
  placeholder?: string;
  helpText?: string;
  required?: boolean;
  validation?: {
    min?: number;
    max?: number;
    pattern?: RegExp;
    custom?: (value: any) => string | null;
  };
}

export interface ProductFormConfig {
  fields: {
    [K in keyof ProductFormData]?: FormFieldConfig;
  };
  sections: {
    basic: {
      title: string;
      description: string;
      fields: (keyof ProductFormData)[];
    };
    variants: {
      title: string;
      description: string;
      fields: (keyof ShopifyProductVariant)[];
    };
    images: {
      title: string;
      description: string;
      maxImages?: number;
      acceptedFormats?: string[];
      maxFileSize?: number;
    };
    seo: {
      title: string;
      description: string;
      fields: (keyof ShopifyProductSEO)[];
    };
    organization: {
      title: string;
      description: string;
      fields: string[];
    };
    visibility: {
      title: string;
      description: string;
      fields: string[];
    };
  };
}

// Predefined options
export interface ProductTypeOption {
  value: string;
  label: string;
  category?: string;
}

export interface VendorOption {
  value: string;
  label: string;
  default?: boolean;
}

export const DEFAULT_PRODUCT_TYPES: ProductTypeOption[] = [
  { value: 'accessories', label: 'Accessories', category: 'general' },
  { value: 'apparel', label: 'Apparel', category: 'clothing' },
  { value: 'books', label: 'Books', category: 'media' },
  { value: 'electronics', label: 'Electronics', category: 'technology' },
  { value: 'food-beverage', label: 'Food & Beverage', category: 'consumables' },
  { value: 'health-beauty', label: 'Health & Beauty', category: 'personal-care' },
  { value: 'home-garden', label: 'Home & Garden', category: 'home' },
  { value: 'office-supplies', label: 'Office Supplies', category: 'business' },
  { value: 'sports-recreation', label: 'Sports & Recreation', category: 'sports' },
  { value: 'toys-games', label: 'Toys & Games', category: 'entertainment' },
];

export const DEFAULT_VENDORS: VendorOption[] = [
  { value: 'cowans-office-products', label: 'Cowan\'s Office Products', default: true },
];

// Utility functions
export const createDefaultVariant = (): ShopifyProductVariant => ({
  sku: '',
  price: '',
  inventory_quantity: 0,
  inventory_policy: 'deny',
  inventory_management: 'shopify',
  fulfillment_service: 'manual',
  requires_shipping: true,
  taxable: true,
  weight_unit: 'g',
  weight: 0,
  grams: 0,
});

export const createDefaultProduct = (): ProductFormData => ({
  title: '',
  body_html: '',
  vendor: DEFAULT_VENDORS[0].value,
  product_type: '',
  handle: '',
  tags: [],
  published: false,
  status: 'draft',
  published_scope: 'global',
  seo: {
    title: '',
    description: '',
  },
  options: [],
  variants: [createDefaultVariant()],
  images: [],
});

// Validation helpers
export const validateSKU = (sku: string): string | null => {
  if (!sku.trim()) return 'SKU is required';
  if (sku.length > 255) return 'SKU must be 255 characters or less';
  if (!/^[a-zA-Z0-9\-_]+$/.test(sku)) return 'SKU can only contain letters, numbers, hyphens, and underscores';
  return null;
};

export const validatePrice = (price: string): string | null => {
  if (!price.trim()) return 'Price is required';
  const numPrice = parseFloat(price);
  if (isNaN(numPrice)) return 'Price must be a valid number';
  if (numPrice < 0) return 'Price cannot be negative';
  if (numPrice > 999999.99) return 'Price cannot exceed $999,999.99';
  return null;
};

export const validateHandle = (handle: string): string | null => {
  if (!handle.trim()) return 'Handle is required';
  if (handle.length > 255) return 'Handle must be 255 characters or less';
  if (!/^[a-z0-9\-]+$/.test(handle)) return 'Handle can only contain lowercase letters, numbers, and hyphens';
  if (handle.startsWith('-') || handle.endsWith('-')) return 'Handle cannot start or end with a hyphen';
  if (handle.includes('--')) return 'Handle cannot contain consecutive hyphens';
  return null;
};

export const generateHandle = (title: string): string => {
  return title
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s\-]/g, '') // Remove special characters except spaces and hyphens
    .replace(/\s+/g, '-') // Replace spaces with hyphens
    .replace(/\-+/g, '-') // Replace multiple hyphens with single hyphen
    .replace(/^-+|-+$/g, ''); // Remove leading/trailing hyphens
};

export const validateProductForm = (data: ProductFormData): ProductValidationResult => {
  const errors: ProductFormErrors = {};

  // Basic validation
  if (!data.title.trim()) errors.title = 'Product title is required';
  if (!data.vendor.trim()) errors.vendor = 'Vendor is required';
  if (!data.product_type.trim()) errors.product_type = 'Product type is required';
  
  const handleError = validateHandle(data.handle);
  if (handleError) errors.handle = handleError;

  // Validate variants
  data.variants.forEach((variant, index) => {
    const skuError = validateSKU(variant.sku);
    if (skuError) errors[`variant_${index}_sku`] = skuError;
    
    const priceError = validatePrice(variant.price);
    if (priceError) errors[`variant_${index}_price`] = priceError;
    
    if (variant.inventory_quantity < 0) {
      errors[`variant_${index}_inventory`] = 'Inventory quantity cannot be negative';
    }
  });

  // SEO validation
  if (data.seo.title.length > 60) {
    errors.seo_title = 'SEO title should be 60 characters or less';
  }
  
  if (data.seo.description.length > 160) {
    errors.seo_description = 'SEO description should be 160 characters or less';
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
};