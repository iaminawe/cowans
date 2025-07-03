import React, { useState, useCallback, useRef } from 'react';
import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  Upload, 
  FileText, 
  Wand2, 
  Settings, 
  Trash2, 
  Download, 
  AlertCircle,
  CheckCircle2,
  Loader2,
  Image,
  Palette,
  Zap
} from 'lucide-react';

export interface IconGenerationConfig {
  style: 'modern' | 'flat' | 'outlined' | 'minimal' | 'filled' | 'rounded' | 'sharp';
  colorScheme: 'monochrome' | 'brand' | 'category' | 'auto';
  size: string; // Allow any size string, will be parsed to number
  format: 'svg' | 'png' | 'webp';
  backgroundColor: string;
  foregroundColor: string;
  theme: 'light' | 'dark' | 'auto';
  includeVariants: boolean;
  batchSize: number;
  model: 'gpt-image-1' | 'dall-e-3';
}

export interface CategoryData {
  id: string;
  name: string;
  description?: string;
  keywords: string[];
  parentCategory?: string;
}

interface BatchIconGenerationFormProps {
  categories: CategoryData[];
  onGenerate: (categories: string[], config: IconGenerationConfig) => void;
  onConfigChange?: (config: IconGenerationConfig) => void;
  isGenerating?: boolean;
  progress?: number;
  generatedCount?: number;
  totalCount?: number;
  className?: string;
}

const DEFAULT_CONFIG: IconGenerationConfig = {
  style: 'modern',
  colorScheme: 'brand',
  size: '128',
  format: 'png',
  backgroundColor: '#ffffff',
  foregroundColor: '#3B82F6',
  theme: 'light',
  includeVariants: false,
  batchSize: 10,
  model: 'gpt-image-1'
};

export function BatchIconGenerationForm({
  categories,
  onGenerate,
  onConfigChange,
  isGenerating = false,
  progress = 0,
  generatedCount = 0,
  totalCount = 0,
  className
}: BatchIconGenerationFormProps) {
  const [config, setConfig] = useState<IconGenerationConfig>(DEFAULT_CONFIG);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleConfigChange = useCallback((updates: Partial<IconGenerationConfig>) => {
    const newConfig = { ...config, ...updates };
    setConfig(newConfig);
    onConfigChange?.(newConfig);
  }, [config, onConfigChange]);

  const handleCategoryToggle = (categoryId: string) => {
    setSelectedCategories(prev => 
      prev.includes(categoryId) 
        ? prev.filter(id => id !== categoryId)
        : [...prev, categoryId]
    );
  };

  const handleSelectAll = () => {
    const visibleCategories = filteredCategories.map(c => c.id);
    setSelectedCategories(visibleCategories);
  };

  const handleClearSelection = () => {
    setSelectedCategories([]);
  };

  const handleGenerate = () => {
    if (selectedCategories.length === 0) return;
    onGenerate(selectedCategories, config);
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && file.type === 'text/csv') {
      // Handle CSV file upload for bulk category import
      const reader = new FileReader();
      reader.onload = (e) => {
        const csv = e.target?.result as string;
        // Parse CSV and extract category names
        const lines = csv.split('\n').slice(1); // Skip header
        const categoryIds = lines
          .map(line => line.split(',')[0]?.trim())
          .filter(id => id && categories.some(c => c.id === id));
        setSelectedCategories(categoryIds);
      };
      reader.readAsText(file);
    }
  };

  const filteredCategories = categories.filter(category =>
    category.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    category.keywords.some(keyword => 
      keyword.toLowerCase().includes(searchTerm.toLowerCase())
    )
  );

  const estimatedTime = Math.ceil(selectedCategories.length / config.batchSize) * 2; // 2 minutes per batch

  return (
    <Card className={cn("", className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Wand2 className="h-5 w-5 text-primary" />
            Batch Icon Generation
          </CardTitle>
          <Badge variant="secondary" className="flex items-center gap-1">
            <Image className="h-3 w-3" />
            {selectedCategories.length} selected
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Category Selection */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label className="text-base font-medium">Categories</Label>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                className="text-xs"
              >
                <Upload className="h-3 w-3 mr-1" />
                Import CSV
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSelectAll}
                className="text-xs"
              >
                Select All
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearSelection}
                className="text-xs"
                disabled={selectedCategories.length === 0}
              >
                Clear
              </Button>
            </div>
          </div>

          <Input
            placeholder="Search categories..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full"
          />

          <div className="border rounded-lg p-4 max-h-60 overflow-y-auto">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {filteredCategories.map((category) => (
                <div
                  key={category.id}
                  className={cn(
                    "flex items-center space-x-2 p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer",
                    selectedCategories.includes(category.id) && "bg-primary/10 border border-primary/20"
                  )}
                  onClick={() => handleCategoryToggle(category.id)}
                >
                  <Checkbox
                    checked={selectedCategories.includes(category.id)}
                    onChange={() => handleCategoryToggle(category.id)}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{category.name}</div>
                    {category.keywords.length > 0 && (
                      <div className="text-xs text-muted-foreground truncate">
                        {category.keywords.slice(0, 3).join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
            
            {filteredCategories.length === 0 && (
              <div className="text-center text-muted-foreground py-8">
                <FileText className="h-8 w-8 mx-auto mb-2" />
                <p>No categories found matching "{searchTerm}"</p>
              </div>
            )}
          </div>
        </div>

        {/* Configuration */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label className="text-base font-medium">Configuration</Label>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <Settings className="h-4 w-4 mr-1" />
              {showAdvanced ? 'Hide' : 'Show'} Advanced
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-2">
              <Label htmlFor="style">Style</Label>
              <Select value={config.style} onValueChange={(value) => handleConfigChange({ style: value as IconGenerationConfig['style'] })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select style" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="modern">Modern</SelectItem>
                  <SelectItem value="flat">Flat</SelectItem>
                  <SelectItem value="outlined">Outlined</SelectItem>
                  <SelectItem value="minimal">Minimal</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="size">Size</Label>
              <Select value={config.size} onValueChange={(value) => handleConfigChange({ size: value as IconGenerationConfig['size'] })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select size" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="32">32px</SelectItem>
                  <SelectItem value="64">64px</SelectItem>
                  <SelectItem value="128">128px</SelectItem>
                  <SelectItem value="256">256px</SelectItem>
                  <SelectItem value="512">512px</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="format">Format</Label>
              <Select value={config.format} onValueChange={(value) => handleConfigChange({ format: value as IconGenerationConfig['format'] })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select format" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="svg">SVG</SelectItem>
                  <SelectItem value="png">PNG</SelectItem>
                  <SelectItem value="webp">WebP</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="colorScheme">Color Scheme</Label>
              <Select value={config.colorScheme} onValueChange={(value) => handleConfigChange({ colorScheme: value as IconGenerationConfig['colorScheme'] })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select scheme" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Auto</SelectItem>
                  <SelectItem value="monochrome">Monochrome</SelectItem>
                  <SelectItem value="brand">Brand Colors</SelectItem>
                  <SelectItem value="category">Category Based</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="model">AI Model</Label>
              <Select value={config.model} onValueChange={(value) => handleConfigChange({ model: value as IconGenerationConfig['model'] })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gpt-image-1">ChatGPT 4 Image</SelectItem>
                  <SelectItem value="dall-e-3">DALL-E 3</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {showAdvanced && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t">
              <div className="space-y-2">
                <Label htmlFor="backgroundColor">Background Color</Label>
                <div className="flex items-center gap-2">
                  <Input
                    type="color"
                    value={config.backgroundColor}
                    onChange={(e) => handleConfigChange({ backgroundColor: e.target.value })}
                    className="w-12 h-8 p-1 rounded cursor-pointer"
                  />
                  <Input
                    value={config.backgroundColor}
                    onChange={(e) => handleConfigChange({ backgroundColor: e.target.value })}
                    placeholder="#ffffff"
                    className="flex-1"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="foregroundColor">Foreground Color</Label>
                <div className="flex items-center gap-2">
                  <Input
                    type="color"
                    value={config.foregroundColor}
                    onChange={(e) => handleConfigChange({ foregroundColor: e.target.value })}
                    className="w-12 h-8 p-1 rounded cursor-pointer"
                  />
                  <Input
                    value={config.foregroundColor}
                    onChange={(e) => handleConfigChange({ foregroundColor: e.target.value })}
                    placeholder="#1f2937"
                    className="flex-1"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="theme">Theme</Label>
                <Select value={config.theme} onValueChange={(value) => handleConfigChange({ theme: value as IconGenerationConfig['theme'] })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select theme" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="light">Light</SelectItem>
                    <SelectItem value="dark">Dark</SelectItem>
                    <SelectItem value="auto">Auto</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="batchSize">Batch Size</Label>
                <Select value={config.batchSize.toString()} onValueChange={(value) => handleConfigChange({ batchSize: parseInt(value) })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select batch size" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="5">5 icons</SelectItem>
                    <SelectItem value="10">10 icons</SelectItem>
                    <SelectItem value="20">20 icons</SelectItem>
                    <SelectItem value="50">50 icons</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center space-x-2 col-span-2">
                <Checkbox
                  id="includeVariants"
                  checked={config.includeVariants}
                  onCheckedChange={(checked) => handleConfigChange({ includeVariants: checked as boolean })}
                />
                <Label htmlFor="includeVariants" className="text-sm">
                  Include style variants (outline, filled, etc.)
                </Label>
              </div>
            </div>
          )}
        </div>

        {/* Generation Progress */}
        {isGenerating && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating icons...
              </span>
              <span className="text-muted-foreground">
                {generatedCount}/{totalCount} completed
              </span>
            </div>
            <Progress value={progress} className="w-full" />
            <div className="text-xs text-muted-foreground">
              Estimated time remaining: {Math.max(0, Math.ceil((totalCount - generatedCount) / config.batchSize * 2))} minutes
            </div>
          </div>
        )}

        {/* Summary */}
        {selectedCategories.length > 0 && !isGenerating && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <div className="flex items-center justify-between">
                <div>
                  Ready to generate <strong>{selectedCategories.length}</strong> icons
                  {config.includeVariants && <span> with variants</span>}
                  <div className="text-xs text-muted-foreground mt-1">
                    Estimated time: ~{estimatedTime} minutes • Batch size: {config.batchSize}
                  </div>
                </div>
                <Button
                  onClick={handleGenerate}
                  disabled={isGenerating}
                  className="ml-4"
                >
                  <Zap className="h-4 w-4 mr-2" />
                  Generate Icons
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}

        {/* Action Buttons */}
        {selectedCategories.length === 0 && !isGenerating && (
          <Alert variant="warning">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Please select at least one category to generate icons.
            </AlertDescription>
          </Alert>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={handleFileUpload}
          className="hidden"
        />
      </CardContent>
    </Card>
  );
}