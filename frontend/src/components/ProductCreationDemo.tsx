import React, { useState } from 'react';
import { ProductCreationForm } from './ProductCreationForm';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { 
  CheckCircle2, 
  AlertCircle, 
  Plus, 
  Package,
  ArrowLeft 
} from 'lucide-react';

interface ProductCreationDemoProps {
  className?: string;
}

export function ProductCreationDemo({ className }: ProductCreationDemoProps) {
  const [showForm, setShowForm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{
    success: boolean;
    message: string;
    productId?: string;
  } | null>(null);

  const handleSubmit = async (formData: any) => {
    setIsSubmitting(true);
    setSubmitResult(null);
    
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Mock response
      const mockResponse = {
        success: true,
        message: 'Product created successfully!',
        productId: 'gid://shopify/Product/12345678901234',
        data: {
          id: '12345678901234',
          title: formData.title,
          handle: formData.handle,
          status: formData.status,
        }
      };
      
      setSubmitResult(mockResponse);
      setShowForm(false);
    } catch (error) {
      setSubmitResult({
        success: false,
        message: 'Failed to create product. Please try again.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    setShowForm(false);
    setSubmitResult(null);
  };

  if (showForm) {
    return (
      <div className={className}>
        <div className="mb-4">
          <Button 
            variant="outline" 
            onClick={handleCancel}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Demo
          </Button>
        </div>
        
        <ProductCreationForm
          onSubmit={handleSubmit}
          onCancel={handleCancel}
          initialData={{
            title: 'Sample Product',
            vendor: 'Cowan\'s Office Products',
            productType: 'Office Supplies',
            tags: ['office', 'supplies']
          }}
        />
      </div>
    );
  }

  return (
    <div className={className}>
      <div className="space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Product Creation Form Demo</h1>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            A comprehensive form component for creating Shopify products with all the features
            you need: variants, images, SEO, inventory management, and more.
          </p>
        </div>

        {/* Result Alert */}
        {submitResult && (
          <Alert className={submitResult.success ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"}>
            {submitResult.success ? (
              <CheckCircle2 className="h-4 w-4 text-green-600" />
            ) : (
              <AlertCircle className="h-4 w-4 text-red-600" />
            )}
            <AlertDescription className={submitResult.success ? "text-green-800" : "text-red-800"}>
              {submitResult.message}
              {submitResult.productId && (
                <div className="mt-2">
                  <Badge variant="outline">Product ID: {submitResult.productId}</Badge>
                </div>
              )}
            </AlertDescription>
          </Alert>
        )}

        {/* Features Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                Basic Information
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                <li>• Product title and description</li>
                <li>• Auto-generated handle</li>
                <li>• Vendor and product type</li>
                <li>• Custom vendor/type options</li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                Variants & Pricing
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                <li>• Multiple product variants</li>
                <li>• Price and compare-at-price</li>
                <li>• Inventory management</li>
                <li>• Weight and dimensions</li>
                <li>• SKU and barcode support</li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                Images & Media
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                <li>• Multiple image upload</li>
                <li>• Drag-and-drop interface</li>
                <li>• Image positioning</li>
                <li>• Alt text support</li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                SEO Optimization
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                <li>• Custom SEO title</li>
                <li>• Meta description</li>
                <li>• Character count validation</li>
                <li>• Auto-generated from title</li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                Organization
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                <li>• Tag management</li>
                <li>• Custom template suffix</li>
                <li>• Product categorization</li>
                <li>• Bulk tag operations</li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                Visibility & Publishing
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                <li>• Draft/Active/Archived status</li>
                <li>• Sales channel selection</li>
                <li>• Published state control</li>
                <li>• Visibility management</li>
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* Design Features */}
        <Card>
          <CardHeader>
            <CardTitle>Design & UX Features</CardTitle>
            <CardDescription>
              Built with accessibility and user experience in mind
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-semibold mb-2">Accessibility</h4>
                <ul className="space-y-1 text-sm">
                  <li>• ARIA labels and descriptions</li>
                  <li>• Keyboard navigation support</li>
                  <li>• Screen reader compatibility</li>
                  <li>• Focus management</li>
                  <li>• Color contrast compliance</li>
                </ul>
              </div>
              <div>
                <h4 className="font-semibold mb-2">User Experience</h4>
                <ul className="space-y-1 text-sm">
                  <li>• Real-time validation</li>
                  <li>• Auto-save functionality</li>
                  <li>• Progress indicators</li>
                  <li>• Contextual help text</li>
                  <li>• Responsive design</li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Action Button */}
        <div className="text-center">
          <Button 
            onClick={() => setShowForm(true)}
            className="px-8 py-3"
            size="lg"
          >
            <Plus className="h-5 w-5 mr-2" />
            Try the Form
          </Button>
        </div>

        {/* Technical Details */}
        <Card>
          <CardHeader>
            <CardTitle>Technical Implementation</CardTitle>
            <CardDescription>
              Component architecture and integration details
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold mb-2">Form Structure</h4>
                <p className="text-sm text-muted-foreground">
                  The form is organized into logical tabs (Basic Info, Variants, Images, SEO, Organization, Visibility) 
                  following Shopify's admin interface patterns for familiar user experience.
                </p>
              </div>
              
              <div>
                <h4 className="font-semibold mb-2">Validation</h4>
                <p className="text-sm text-muted-foreground">
                  Comprehensive client-side validation with real-time feedback, field-level error states, 
                  and form-level validation before submission.
                </p>
              </div>
              
              <div>
                <h4 className="font-semibold mb-2">Data Flow</h4>
                <p className="text-sm text-muted-foreground">
                  Structured data interfaces matching Shopify's Product API, with TypeScript types for 
                  type safety and better developer experience.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}