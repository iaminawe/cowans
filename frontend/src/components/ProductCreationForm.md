# Product Creation Form Component

## Overview

The `ProductCreationForm` component is a comprehensive React form for creating Shopify products. It provides a complete interface for all aspects of product creation, from basic information to advanced settings like variants, SEO, and visibility controls.

## Features

### ✅ Complete Shopify Product API Support
- **Basic Information**: Title, description, handle, vendor, product type
- **Variants Management**: Multiple variants with pricing, inventory, and shipping options
- **Image Upload**: Drag-and-drop interface with positioning controls
- **SEO Optimization**: Custom titles and descriptions with character limits
- **Organization**: Tag management and template customization
- **Visibility Controls**: Publishing status and sales channel management

### ✅ User Experience & Accessibility
- **Tabbed Interface**: Logical organization following Shopify admin patterns
- **Real-time Validation**: Instant feedback with field-level error states
- **Auto-generation**: Handle and SEO title auto-generated from product title
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Keyboard Navigation**: Full keyboard accessibility support
- **Screen Reader Support**: Comprehensive ARIA labels and descriptions

### ✅ Developer Experience
- **TypeScript Support**: Comprehensive type definitions for all data structures
- **Validation Helpers**: Reusable validation functions for common fields
- **Modular Design**: Easy to extend and customize
- **Error Handling**: Structured error management with clear messaging
- **API Integration Ready**: Direct mapping to Shopify Product API

## Component Structure

```
ProductCreationForm/
├── ProductCreationForm.tsx       # Main form component
├── ProductCreationDemo.tsx       # Demo/example usage
├── ProductCreationForm.md        # This documentation
└── types/
    └── product.ts               # TypeScript interfaces
```

## Usage

### Basic Usage

```tsx
import { ProductCreationForm } from '@/components/ProductCreationForm';

function CreateProductPage() {
  const handleSubmit = async (productData) => {
    try {
      const response = await fetch('/api/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(productData)
      });
      
      if (response.ok) {
        // Handle success
        console.log('Product created successfully');
      }
    } catch (error) {
      // Handle error
      console.error('Failed to create product:', error);
    }
  };

  return (
    <ProductCreationForm
      onSubmit={handleSubmit}
      onCancel={() => router.back()}
    />
  );
}
```

### With Initial Data (Edit Mode)

```tsx
const initialData = {
  title: 'Existing Product',
  body_html: 'Product description',
  vendor: 'My Vendor',
  product_type: 'Office Supplies',
  // ... other fields
};

<ProductCreationForm
  onSubmit={handleSubmit}
  onCancel={handleCancel}
  initialData={initialData}
/>
```

## Form Sections

### 1. Basic Information
- **Product Title** (required): Main product name
- **Handle** (required): URL-friendly identifier (auto-generated)
- **Description**: HTML product description
- **Vendor** (required): Product manufacturer/brand
- **Product Type** (required): Category classification

### 2. Variants & Pricing
- **Multiple Variants**: Support for size, color, style variations
- **Pricing**: Base price and compare-at-price
- **Inventory**: Quantity tracking and policies
- **Physical Properties**: Weight, dimensions, shipping requirements
- **SKU Management**: Unique identifiers and barcodes

### 3. Images
- **Upload Interface**: Drag-and-drop or click to upload
- **Multiple Images**: Support for product galleries
- **Image Positioning**: Reorder images for display priority
- **Alt Text**: Accessibility and SEO descriptions

### 4. SEO Optimization
- **SEO Title**: Custom search engine title (60 char limit)
- **SEO Description**: Meta description (160 char limit)
- **Character Counters**: Real-time feedback on optimal lengths
- **Auto-generation**: Intelligent defaults from product data

### 5. Organization
- **Tag Management**: Add/remove product tags
- **Template Suffix**: Custom Liquid template selection
- **Categorization**: Product type and vendor organization

### 6. Visibility & Publishing
- **Product Status**: Active, Draft, or Archived
- **Publishing**: Control product visibility
- **Sales Channels**: Global or web-only availability

## Validation

### Client-Side Validation
- **Required Fields**: Title, vendor, product type, handle
- **Format Validation**: Handle format, price validation, SKU format
- **Length Limits**: SEO fields, character limits
- **Real-time Feedback**: Instant validation on field changes

### Validation Rules
```typescript
// Handle validation
const handleValidation = {
  required: true,
  pattern: /^[a-z0-9\-]+$/,
  maxLength: 255,
  noConsecutiveHyphens: true
};

// Price validation
const priceValidation = {
  required: true,
  min: 0,
  max: 999999.99,
  decimal: true
};

// SKU validation
const skuValidation = {
  required: true,
  pattern: /^[a-zA-Z0-9\-_]+$/,
  maxLength: 255,
  unique: true
};
```

## TypeScript Support

### Core Interfaces

```typescript
interface ProductFormData {
  title: string;
  body_html: string;
  vendor: string;
  product_type: string;
  handle: string;
  tags: string[];
  published: boolean;
  status: 'active' | 'archived' | 'draft';
  seo: ProductSEO;
  variants: ProductVariant[];
  images: ProductImage[];
  // ... other fields
}

interface ProductVariant {
  sku: string;
  price: string;
  inventory_quantity: number;
  weight?: number;
  weight_unit: 'g' | 'kg' | 'oz' | 'lb';
  requires_shipping: boolean;
  taxable: boolean;
  // ... other fields
}
```

### Validation Helpers

```typescript
import { validateProductForm, validateSKU, validatePrice } from '@/types/product';

const validation = validateProductForm(formData);
if (!validation.isValid) {
  console.log('Validation errors:', validation.errors);
}
```

## Styling & Theming

### Tailwind CSS Classes
The component uses Tailwind CSS for styling with the shadcn/ui design system:

```css
/* Form layout */
.form-section { @apply space-y-6; }
.form-grid { @apply grid grid-cols-1 md:grid-cols-2 gap-4; }
.form-field { @apply space-y-2; }

/* Input states */
.input-error { @apply border-red-500 focus:border-red-500; }
.input-success { @apply border-green-500 focus:border-green-500; }

/* Tab navigation */
.tab-nav { @apply grid w-full grid-cols-6; }
.tab-content { @apply space-y-6; }
```

### Customization
The component accepts a `className` prop for custom styling:

```tsx
<ProductCreationForm
  className="max-w-4xl mx-auto p-6"
  onSubmit={handleSubmit}
  onCancel={handleCancel}
/>
```

## Integration with Shopify API

### API Mapping
The form data directly maps to Shopify's Product API:

```typescript
// Direct API submission
const createProduct = async (formData: ProductFormData) => {
  const shopifyProduct = {
    product: {
      title: formData.title,
      body_html: formData.body_html,
      vendor: formData.vendor,
      product_type: formData.product_type,
      handle: formData.handle,
      status: formData.status,
      tags: formData.tags.join(','),
      variants: formData.variants,
      images: formData.images,
      metafields: [
        {
          namespace: 'seo',
          key: 'title',
          value: formData.seo.title
        },
        {
          namespace: 'seo',
          key: 'description',
          value: formData.seo.description
        }
      ]
    }
  };

  return fetch('/admin/api/2023-10/products.json', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Shopify-Access-Token': accessToken
    },
    body: JSON.stringify(shopifyProduct)
  });
};
```

## Performance Considerations

### Optimization Features
- **Lazy Loading**: Tab content loaded on demand
- **Debounced Validation**: Reduces API calls during typing
- **Image Optimization**: Automatic resizing and compression
- **Memory Management**: Proper cleanup of image URLs

### Bundle Size
- **Tree Shaking**: Only import needed UI components
- **Code Splitting**: Lazy load form sections if needed
- **Dependencies**: Minimal external dependencies

## Testing

### Unit Tests
```typescript
import { render, fireEvent, waitFor } from '@testing-library/react';
import { ProductCreationForm } from './ProductCreationForm';

test('validates required fields', async () => {
  const mockSubmit = jest.fn();
  const { getByLabelText, getByRole } = render(
    <ProductCreationForm onSubmit={mockSubmit} onCancel={() => {}} />
  );

  fireEvent.click(getByRole('button', { name: /create product/i }));
  
  await waitFor(() => {
    expect(getByLabelText(/product title/i)).toHaveClass('border-red-500');
  });
});
```

### Integration Tests
```typescript
test('submits valid product data', async () => {
  const mockSubmit = jest.fn();
  const { getByLabelText, getByRole } = render(
    <ProductCreationForm onSubmit={mockSubmit} onCancel={() => {}} />
  );

  fireEvent.change(getByLabelText(/product title/i), {
    target: { value: 'Test Product' }
  });
  
  fireEvent.click(getByRole('button', { name: /create product/i }));
  
  await waitFor(() => {
    expect(mockSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Test Product'
      })
    );
  });
});
```

## Browser Support

### Compatibility
- **Modern Browsers**: Chrome 80+, Firefox 75+, Safari 13+
- **Mobile**: iOS Safari 13+, Chrome Mobile 80+
- **Features**: ES2020, CSS Grid, Flexbox
- **Polyfills**: Not required for supported browsers

### Graceful Degradation
- **JavaScript Disabled**: Basic HTML form functionality
- **Slow Connections**: Progressive loading with skeletons
- **Touch Devices**: Optimized touch targets and gestures

## Security Considerations

### Input Sanitization
```typescript
import DOMPurify from 'dompurify';

const sanitizeHTML = (html: string) => {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li'],
    ALLOWED_ATTR: []
  });
};
```

### File Upload Security
- **Type Validation**: Only allow image files
- **Size Limits**: Maximum file size enforcement
- **Malware Scanning**: Server-side virus checking
- **CDN Upload**: Direct upload to secure CDN

## Future Enhancements

### Planned Features
- [ ] **Bulk Import**: CSV/Excel product import
- [ ] **AI Content**: Auto-generate descriptions and tags
- [ ] **Template Library**: Pre-built product templates
- [ ] **Advanced SEO**: Schema markup and analytics
- [ ] **Multi-language**: International product support
- [ ] **Advanced Variants**: Matrix-style variant management

### API Enhancements
- [ ] **GraphQL Support**: Modern API integration
- [ ] **Real-time Sync**: Live inventory updates
- [ ] **Conflict Resolution**: Handle concurrent edits
- [ ] **Audit Trail**: Track all product changes

## Support & Maintenance

### Documentation
- Component API documentation
- Integration examples
- Troubleshooting guide
- Best practices

### Updates
- Regular dependency updates
- Security patches
- Feature enhancements
- Bug fixes

---

## Contributing

When contributing to this component:

1. **Follow TypeScript**: Maintain type safety
2. **Test Coverage**: Add tests for new features
3. **Accessibility**: Ensure WCAG compliance
4. **Documentation**: Update this README
5. **Performance**: Consider bundle size impact

## License

This component is part of the Cowan's Office Products system and follows the project's licensing terms.