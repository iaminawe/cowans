import React, { useState } from 'react';
import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { 
  Upload,
  FileText,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Download,
  RefreshCw
} from 'lucide-react';

export function ProductImporter() {
  const [isImporting, setIsImporting] = useState(false);
  const [importProgress, setImportProgress] = useState(0);
  const [importStatus, setImportStatus] = useState<'idle' | 'uploading' | 'processing' | 'complete' | 'error'>('idle');

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    setImportStatus('uploading');
    setImportProgress(0);

    // Simulate file upload and processing
    try {
      // Simulate progress
      for (let i = 0; i <= 100; i += 10) {
        await new Promise(resolve => setTimeout(resolve, 200));
        setImportProgress(i);
        if (i === 50) setImportStatus('processing');
      }
      
      setImportStatus('complete');
    } catch (error) {
      setImportStatus('error');
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Import Products</CardTitle>
          <CardDescription>
            Upload a CSV or Excel file to import products in bulk
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Upload Area */}
          <div className="border-2 border-dashed rounded-lg p-8 text-center">
            <Upload className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">Upload Product File</h3>
            <p className="text-sm text-muted-foreground mb-4">
              CSV or XLSX files, up to 10MB
            </p>
            <input
              type="file"
              id="file-upload"
              className="hidden"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileUpload}
              disabled={isImporting}
            />
            <label htmlFor="file-upload">
              <Button disabled={isImporting} asChild>
                <span>
                  {isImporting ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      Importing...
                    </>
                  ) : (
                    <>
                      <Upload className="h-4 w-4 mr-2" />
                      Choose File
                    </>
                  )}
                </span>
              </Button>
            </label>
          </div>

          {/* Progress */}
          {isImporting && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>{importStatus === 'uploading' ? 'Uploading...' : 'Processing...'}</span>
                <span>{importProgress}%</span>
              </div>
              <Progress value={importProgress} />
            </div>
          )}

          {/* Status Messages */}
          {importStatus === 'complete' && (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                Products imported successfully! Check the products table to view your imported items.
              </AlertDescription>
            </Alert>
          )}

          {importStatus === 'error' && (
            <Alert variant="destructive">
              <XCircle className="h-4 w-4" />
              <AlertDescription>
                Import failed. Please check your file format and try again.
              </AlertDescription>
            </Alert>
          )}

          {/* Template Download */}
          <div className="border rounded-lg p-4 bg-gray-50 dark:bg-gray-900">
            <div className="flex items-start gap-3">
              <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div className="flex-1">
                <h4 className="text-sm font-medium">Need a template?</h4>
                <p className="text-sm text-muted-foreground mt-1">
                  Download our product import template with all required fields
                </p>
                <Button variant="link" className="px-0 h-auto mt-2">
                  <Download className="h-4 w-4 mr-2" />
                  Download CSV Template
                </Button>
              </div>
            </div>
          </div>

          {/* Import Guidelines */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium">Import Guidelines</h4>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Required fields: SKU, Name, Price</li>
              <li>• Optional fields: Description, Category, Brand, Manufacturer, Inventory</li>
              <li>• SKUs must be unique across your catalog</li>
              <li>• Prices should be in USD without currency symbols</li>
              <li>• Categories must match existing categories or will be created</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* Recent Imports */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Imports</CardTitle>
          <CardDescription>
            View your import history and download reports
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No recent imports</p>
        </CardContent>
      </Card>
    </div>
  );
}