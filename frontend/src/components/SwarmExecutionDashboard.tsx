import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { DashboardCard, DashboardGrid } from './DashboardLayout';
import { APIStatusIndicator, APIEndpoint } from './APIStatusIndicator';
import { BatchIconGenerationForm, IconGenerationConfig, CategoryData } from './BatchIconGenerationForm';
import { IconPreviewGrid, GeneratedIcon } from './IconPreviewGrid';
import { CategoryManagementPanel, Category } from './CategoryManagementPanel';
import { BatchProgressTracker, BatchOperation, BatchStage } from './BatchProgressTracker';
import { ShopifyCollectionManager } from './ShopifyCollectionManager';

// Component interfaces for imported components
interface APIStatusIndicatorProps {
  endpoints: APIEndpoint[];
  onRefresh: (endpointId?: string) => void;
  onConfigure: (id: string) => void;
}

interface BatchIconGenerationFormProps {
  categories: CategoryData[];
  onGenerate: (categoryIds: string[], config: IconGenerationConfig) => void;
  isGenerating: boolean;
  progress: number;
  generatedCount: number;
  totalCount: number;
}

interface IconPreviewGridProps {
  icons: GeneratedIcon[];
  selectedIcons: string[];
  viewMode: 'grid' | 'list';
  onViewModeChange: (mode: 'grid' | 'list') => void;
  onIconSelect: (iconId: string, selected: boolean) => void;
  onIconFavorite: (iconId: string, favorite: boolean) => void;
  onIconDelete: (iconId: string) => void;
  onIconDownload: (iconId: string) => void;
  onBulkDownload: (iconIds: string[]) => void;
  onBulkDelete: (iconIds: string[]) => void;
  onPreview: (icon: GeneratedIcon) => void;
}

interface CategoryManagementPanelProps {
  categories: (CategoryData & { level: number })[];
  availableIcons: GeneratedIcon[];
  onCategoryCreate: (parentId: string | null, name: string, description?: string) => void;
  onCategoryUpdate: (categoryId: string, updates: Partial<CategoryData>) => void;
  onCategoryDelete: (categoryId: string) => void;
  onIconAssign: (categoryId: string, iconId: string) => void;
  onIconUnassign: (categoryId: string) => void;
  onCategoriesExport: () => void;
}

interface BatchProgressTrackerProps {
  operation: BatchOperation;
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
  showDetails?: boolean;
}

interface ShopifyCollectionManagerProps {
  onGenerateIcon?: (collection: any) => void;
  onSyncIcon?: (collectionId: string, iconPath: string) => void;
}
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Zap, 
  Image, 
  FolderTree, 
  Activity, 
  Settings,
  Download,
  Upload,
  RefreshCw,
  CheckCircle2
} from 'lucide-react';
// import { shopifyApi, ShopifyCollection } from '@/lib/shopifyApi';

// Define ShopifyCollection interface locally since import may be missing
interface ShopifyCollection {
  id: string;
  graphql_id: string;
  handle: string;
  title: string;
  description: string;
  products_count: number;
  image_url?: string;
  has_icon?: boolean;
  updated_at: string;
  metafields: Record<string, any>;
}
import { IconPreviewModal } from './IconPreviewModal';

interface SwarmExecutionDashboardProps {
  className?: string;
}

// Mock data for demonstration
const mockAPIEndpoints: APIEndpoint[] = [
  {
    id: 'openai',
    name: 'OpenAI API',
    url: 'https://api.openai.com/v1',
    status: 'connected',
    lastChecked: new Date().toISOString(),
    responseTime: 245,
    rateLimitRemaining: 4500,
    rateLimitReset: new Date(Date.now() + 3600000).toISOString()
  },
  {
    id: 'anthropic',
    name: 'Anthropic API',
    url: 'https://api.anthropic.com/v1',
    status: 'connected',
    lastChecked: new Date().toISOString(),
    responseTime: 189,
    rateLimitRemaining: 8900,
    rateLimitReset: new Date(Date.now() + 3600000).toISOString()
  },
  {
    id: 'stability',
    name: 'Stability AI',
    url: 'https://api.stability.ai/v1',
    status: 'error',
    lastChecked: new Date().toISOString(),
    errorMessage: 'Rate limit exceeded',
    rateLimitRemaining: 0,
    rateLimitReset: new Date(Date.now() + 1800000).toISOString()
  }
];

const mockCategories: CategoryData[] = [
  { id: '1', name: 'Office Supplies', keywords: ['pen', 'paper', 'desk', 'office'] },
  { id: '2', name: 'Technology', keywords: ['computer', 'laptop', 'phone', 'electronic'] },
  { id: '3', name: 'Furniture', keywords: ['chair', 'table', 'desk', 'cabinet'] },
  { id: '4', name: 'Art Supplies', keywords: ['paint', 'brush', 'canvas', 'art'] },
  { id: '5', name: 'Books & Media', keywords: ['book', 'magazine', 'cd', 'dvd'] }
];

const mockGeneratedIcons: GeneratedIcon[] = [
  {
    id: '1',
    categoryId: '1',
    categoryName: 'Office Supplies',
    name: 'office-pen',
    style: 'filled',
    size: '24',
    format: 'svg',
    imageUrl: '/api/placeholder/48/48',
    thumbnailUrl: '/api/placeholder/24/24',
    generatedAt: new Date().toISOString(),
    tags: ['pen', 'office', 'writing'],
    colorScheme: 'monochrome',
    isFavorite: false
  },
  {
    id: '2',
    categoryId: '2',
    categoryName: 'Technology',
    name: 'laptop-computer',
    style: 'outlined',
    size: '24',
    format: 'svg',
    imageUrl: '/api/placeholder/48/48',
    thumbnailUrl: '/api/placeholder/24/24',
    generatedAt: new Date().toISOString(),
    tags: ['laptop', 'computer', 'tech'],
    colorScheme: 'brand',
    isFavorite: true
  }
];

export function SwarmExecutionDashboard({ className }: SwarmExecutionDashboardProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'generate' | 'icons' | 'categories' | 'shopify'>('overview');
  const [apiEndpoints, setApiEndpoints] = useState<APIEndpoint[]>(mockAPIEndpoints);
  const [categories, setCategories] = useState<CategoryData[]>(mockCategories);
  const [generatedIcons, setGeneratedIcons] = useState<GeneratedIcon[]>(mockGeneratedIcons);
  const [selectedIcons, setSelectedIcons] = useState<string[]>([]);
  const [currentOperation, setCurrentOperation] = useState<BatchOperation | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [shopifyCollections, setShopifyCollections] = useState<ShopifyCollection[]>([]);

  // Simulate batch operation
  const [isGenerating, setIsGenerating] = useState(false);
  
  // Preview modal state
  const [previewIcon, setPreviewIcon] = useState<GeneratedIcon | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  // Load initial data on mount
  useEffect(() => {
    loadCategoriesFromAPI();
    loadShopifyCollections();
    loadIconsFromAPI();
  }, []);

  const loadCategoriesFromAPI = async () => {
    try {
      const response = await fetch('http://localhost:3560/api/categories', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        const apiCategories: CategoryData[] = data.categories.map((category: any) => ({
          id: category.id.toString(),
          name: category.name,
          description: category.description,
          keywords: [] // Could extract from metadata or other fields
        }));
        
        setCategories(apiCategories);
        console.log(`Loaded ${apiCategories.length} categories from API`);
      } else {
        console.error('Failed to load categories from API:', response.status);
        // Keep mock categories as fallback
      }
    } catch (error) {
      console.error('Failed to load categories from API:', error);
      // Keep mock categories as fallback
    }
  };

  const loadIconsFromAPI = async () => {
    try {
      const response = await fetch('http://localhost:3560/api/icons?limit=100', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        const apiIcons: GeneratedIcon[] = data.icons.map((icon: any) => ({
          id: icon.id.toString(),
          categoryId: icon.category_id.toString(),
          categoryName: icon.category_name,
          name: icon.filename.replace(/\.[^/.]+$/, ''), // Remove file extension
          style: icon.style || 'modern',
          size: icon.width?.toString() || '128',
          format: icon.format?.toLowerCase() || 'png',
          imageUrl: `http://localhost:3560/api/icons/categories/${icon.category_id}/icon`,
          thumbnailUrl: `http://localhost:3560/api/icons/categories/${icon.category_id}/icon`,
          generatedAt: icon.created_at,
          tags: [], // Could be extracted from metadata
          colorScheme: 'brand',
          isFavorite: icon.isFavorite || false
        }));
        
        setGeneratedIcons(apiIcons);
      }
    } catch (error) {
      console.error('Failed to load icons from API:', error);
      // Keep mock data as fallback
    }
  };

  const loadShopifyCollections = async () => {
    try {
      // Load collections from our database (categories with Shopify integration)
      const response = await fetch('http://localhost:3560/api/collections', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        
        // Convert to ShopifyCollection format for the ShopifyCollectionManager
        const collections: ShopifyCollection[] = data.collections
          .filter((cat: any) => cat.shopify_collection_id) // Only categories linked to Shopify
          .map((cat: any) => ({
            id: cat.shopify_collection_id,
            graphql_id: `gid://shopify/Collection/${cat.shopify_collection_id}`,
            handle: cat.shopify_handle || cat.slug,
            title: cat.name,
            description: cat.description || '',
            products_count: 0, // Could be fetched if needed
            image_url: cat.icon_url,
            has_icon: cat.has_icon,
            updated_at: cat.updated_at,
            metafields: {}
          }));
        
        setShopifyCollections(collections);
        console.log(`Loaded ${collections.length} Shopify-linked collections from database`);
      } else {
        console.error('Failed to load collections from database:', response.status);
      }
    } catch (error) {
      console.error('Failed to load collections from database:', error);
    }
  };

  const handleAPIRefresh = (endpointId?: string) => {
    setApiEndpoints(prev => prev.map(endpoint => {
      if (!endpointId || endpoint.id === endpointId) {
        return {
          ...endpoint,
          status: 'checking',
          lastChecked: new Date().toISOString()
        };
      }
      return endpoint;
    }));

    // Simulate API check
    setTimeout(() => {
      setApiEndpoints(prev => prev.map(endpoint => {
        if (!endpointId || endpoint.id === endpointId) {
          return {
            ...endpoint,
            status: Math.random() > 0.2 ? 'connected' : 'error',
            responseTime: Math.floor(Math.random() * 500) + 100,
            lastChecked: new Date().toISOString()
          };
        }
        return endpoint;
      }));
    }, 2000);
  };

  const handleIconGeneration = async (categoryIds: string[], config: IconGenerationConfig) => {
    setIsGenerating(true);
    
    // Create initial batch operation
    const operation: BatchOperation = {
      id: 'icon-generation-' + Date.now(),
      name: 'Icon Generation',
      description: `Generating icons for ${categoryIds.length} categories`,
      status: 'running',
      stages: [
        {
          id: 'prepare',
          name: 'Preparing',
          status: 'completed',
          progress: 100,
          startTime: new Date().toISOString(),
          endTime: new Date().toISOString(),
          duration: 1
        },
        {
          id: 'generate',
          name: 'Generating Icons',
          status: 'running',
          progress: 0,
          currentItem: 'Starting generation...',
          totalItems: categoryIds.length,
          completedItems: 0,
          startTime: new Date().toISOString(),
          estimatedTimeRemaining: categoryIds.length * 25 // Estimate 25 seconds per icon
        },
        {
          id: 'optimize',
          name: 'Optimizing',
          status: 'pending',
          progress: 0
        },
        {
          id: 'save',
          name: 'Saving Icons',
          status: 'pending',
          progress: 0
        }
      ],
      totalProgress: 10,
      startTime: new Date().toISOString(),
      estimatedTimeRemaining: categoryIds.length * 25,
      itemsProcessed: 0,
      totalItems: categoryIds.length,
      successfulItems: 0,
      failedItems: 0,
      canPause: false,
      canCancel: true
    };

    setCurrentOperation(operation);

    // Process each category one by one
    let completed = 0;
    let failed = 0;
    
    for (let i = 0; i < categoryIds.length; i++) {
      const categoryId = categoryIds[i];
      const category = categories.find(c => c.id === categoryId);
      if (!category) continue;
      
      // Update progress
      const progress = Math.round(((i + 0.5) / categoryIds.length) * 100);
      setCurrentOperation(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          totalProgress: progress,
          itemsProcessed: i,
          stages: prev.stages.map(stage => {
            if (stage.id === 'generate' && stage.status === 'running') {
              return {
                ...stage,
                progress: progress,
                currentItem: `Generating icon for ${category.name}...`,
                completedItems: i
              };
            }
            return stage;
          })
        };
      });
      
      try {
        // Call the actual API to generate icon
        const response = await fetch('http://localhost:3560/api/icons/generate', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            category_id: parseInt(categoryId.replace(/\D/g, '')) || 999,
            category_name: category.name,
            style: (['modern', 'flat', 'outlined', 'minimal'].includes(config.style) ? config.style : 'modern'),
            color: config.foregroundColor || '#3B82F6',
            size: Math.min(512, Math.max(32, parseInt(config.size) || 128)),
            background: config.backgroundColor === 'transparent' ? 'transparent' : 'white'
          })
        });
        
        if (response.ok) {
          const result = await response.json();
          completed++;
          
          // Add the generated icon to the list
          const numericId = parseInt(categoryId.replace(/\D/g, '')) || 999;
          const iconUrl = `http://localhost:3560/api/icons/categories/${numericId}/icon`;
          const newIcon: GeneratedIcon = {
            id: result.icon.id,
            categoryId: categoryId,
            categoryName: category.name,
            name: category.name + ' Icon',
            imageUrl: iconUrl,
            thumbnailUrl: iconUrl,
            format: 'png',
            size: config.size || '128',
            style: config.style || 'modern',
            generatedAt: result.icon.created_at,
            tags: category.keywords || [],
            colorScheme: config.colorScheme || 'brand',
            isFavorite: false
          };
          
          setGeneratedIcons(prev => [...prev, newIcon]);
          
          // Refresh icons from API to get the latest data
          loadIconsFromAPI();
        } else {
          failed++;
          const errorData = await response.json();
          console.error('Failed to generate icon for', category.name, '- Error:', errorData);
        }
      } catch (error) {
        failed++;
        console.error('Error generating icon:', error);
      }
    }
    
    // Final update
    setCurrentOperation(prev => prev ? {
      ...prev,
      status: 'completed',
      totalProgress: 100,
      endTime: new Date().toISOString(),
      itemsProcessed: categoryIds.length,
      successfulItems: completed,
      failedItems: failed,
      stages: prev.stages.map(stage => ({
        ...stage,
        status: 'completed',
        progress: 100,
        endTime: new Date().toISOString()
      }))
    } : null);
    
    setIsGenerating(false);
  };

  const handleIconSelect = (iconId: string, selected: boolean) => {
    setSelectedIcons(prev => 
      selected 
        ? [...prev, iconId]
        : prev.filter(id => id !== iconId)
    );
  };

  const handleIconFavorite = async (iconId: string, favorite: boolean) => {
    try {
      const response = await fetch(`http://localhost:3560/api/icons/${iconId}/favorite`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ favorite })
      });

      if (response.ok) {
        setGeneratedIcons(prev => prev.map(icon =>
          icon.id === iconId ? { ...icon, isFavorite: favorite } : icon
        ));
      } else {
        console.error('Failed to update favorite status');
      }
    } catch (error) {
      console.error('Error updating favorite status:', error);
    }
  };

  const handleIconDelete = async (iconId: string) => {
    if (!confirm('Are you sure you want to delete this icon? This cannot be undone.')) {
      return;
    }
    
    try {
      const response = await fetch(`http://localhost:3560/api/icons/${iconId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        setGeneratedIcons(prev => prev.filter(icon => icon.id !== iconId));
        console.log(`Icon ${iconId} deleted successfully`);
        
        // Also refresh from API to ensure consistency
        loadIconsFromAPI();
      } else if (response.status === 401) {
        console.error('Authentication failed - please refresh the page');
        alert('Authentication failed - please refresh the page and try again');
      } else if (response.status === 404) {
        console.error('Icon not found - it may have already been deleted');
        // Remove from frontend state anyway
        setGeneratedIcons(prev => prev.filter(icon => icon.id !== iconId));
        loadIconsFromAPI();
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('Failed to delete icon:', errorData.message || 'Unknown error');
        alert(`Failed to delete icon: ${errorData.message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error deleting icon:', error);
      alert('Network error while deleting icon');
    }
  };

  const handleBulkDelete = async (iconIds: string[]) => {
    if (!iconIds.length) {
      alert('No icons selected for deletion');
      return;
    }
    
    if (!confirm(`Are you sure you want to delete ${iconIds.length} icon(s)? This cannot be undone.`)) {
      return;
    }
    
    try {
      const response = await fetch('http://localhost:3560/api/icons/bulk', {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ icon_ids: iconIds.map(id => parseInt(id)) })
      });

      if (response.ok) {
        const result = await response.json();
        setGeneratedIcons(prev => prev.filter(icon => !iconIds.includes(icon.id)));
        setSelectedIcons([]);
        console.log(`${result.deleted_count} icons deleted successfully`);
        
        // Refresh from API to ensure consistency
        loadIconsFromAPI();
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('Failed to bulk delete icons:', errorData.message || 'Unknown error');
        alert(`Failed to delete icons: ${errorData.message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error bulk deleting icons:', error);
      alert('Network error while deleting icons');
    }
  };

  const connectedAPIs = apiEndpoints.filter(api => api.status === 'connected').length;
  const totalAPIs = apiEndpoints.length;

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Icon Generation Dashboard</h1>
          <p className="text-muted-foreground">
            AI-powered batch icon generation for product categories
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="flex items-center gap-1">
            <Activity className="h-3 w-3" />
            {connectedAPIs}/{totalAPIs} APIs Connected
          </Badge>
          <Button variant="outline" onClick={() => handleAPIRefresh()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh Status
          </Button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="generate" className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Generate Icons
          </TabsTrigger>
          <TabsTrigger value="icons" className="flex items-center gap-2">
            <Image className="h-4 w-4" />
            Icon Library
            <Badge variant="secondary">{generatedIcons.length}</Badge>
          </TabsTrigger>
          <TabsTrigger value="categories" className="flex items-center gap-2">
            <FolderTree className="h-4 w-4" />
            Categories
            <Badge variant="secondary">{categories.length}</Badge>
          </TabsTrigger>
          <TabsTrigger value="shopify" className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            Shopify
            <Badge variant="secondary">{shopifyCollections.length}</Badge>
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <DashboardGrid columns={2}>
            {/* API Status */}
            <APIStatusIndicator
              endpoints={apiEndpoints}
              onRefresh={handleAPIRefresh}
              onConfigure={(id) => console.log('Configure API:', id)}
            />

            {/* Quick Stats */}
            <DashboardCard
              title="System Overview"
              description="Current status and quick statistics"
            >
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
                  <div className="text-2xl font-bold text-primary">{generatedIcons.length}</div>
                  <div className="text-sm text-muted-foreground">Generated Icons</div>
                </div>
                <div className="text-center p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
                  <div className="text-2xl font-bold text-primary">{categories.length}</div>
                  <div className="text-sm text-muted-foreground">Categories</div>
                </div>
                <div className="text-center p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
                  <div className="text-2xl font-bold text-green-600">{connectedAPIs}</div>
                  <div className="text-sm text-muted-foreground">Connected APIs</div>
                </div>
                <div className="text-center p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
                  <div className="text-2xl font-bold text-blue-600">
                    {Math.round((generatedIcons.filter(i => i.isFavorite).length / generatedIcons.length) * 100) || 0}%
                  </div>
                  <div className="text-sm text-muted-foreground">Favorite Rate</div>
                </div>
              </div>
            </DashboardCard>
          </DashboardGrid>

          {/* Active Operation */}
          {currentOperation && (
            <BatchProgressTracker
              operation={currentOperation}
              onPause={() => console.log('Pause operation')}
              onResume={() => console.log('Resume operation')}
              onCancel={() => setCurrentOperation(null)}
            />
          )}

          {/* Recent Activity */}
          <DashboardCard
            title="Recent Activity"
            description="Latest icon generation and system events"
          >
            <div className="space-y-3">
              {generatedIcons.slice(0, 5).map((icon) => (
                <div key={icon.id} className="flex items-center gap-3 p-2 rounded border">
                  <img 
                    src={icon.thumbnailUrl} 
                    alt={icon.name}
                    className="w-8 h-8 rounded border"
                  />
                  <div className="flex-1">
                    <div className="font-medium text-sm">{icon.name}</div>
                    <div className="text-xs text-muted-foreground">{icon.categoryName}</div>
                  </div>
                  <Badge variant="outline" className="text-xs">{icon.style}</Badge>
                  <div className="text-xs text-muted-foreground">
                    {new Date(icon.generatedAt).toLocaleTimeString()}
                  </div>
                </div>
              ))}
            </div>
          </DashboardCard>
        </TabsContent>

        {/* Generate Tab */}
        <TabsContent value="generate" className="space-y-6">
          <BatchIconGenerationForm
            categories={categories}
            onGenerate={handleIconGeneration}
            isGenerating={isGenerating}
            progress={currentOperation?.totalProgress || 0}
            generatedCount={currentOperation?.itemsProcessed || 0}
            totalCount={currentOperation?.totalItems || 0}
          />

          {currentOperation && (
            <BatchProgressTracker
              operation={currentOperation}
              onPause={() => console.log('Pause')}
              onResume={() => console.log('Resume')}
              onCancel={() => setCurrentOperation(null)}
              showDetails={true}
            />
          )}
        </TabsContent>

        {/* Icons Tab */}
        <TabsContent value="icons" className="space-y-6">
          <IconPreviewGrid
            icons={generatedIcons}
            selectedIcons={selectedIcons}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            onIconSelect={handleIconSelect}
            onIconFavorite={handleIconFavorite}
            onIconDelete={handleIconDelete}
            onIconDownload={(iconId) => console.log('Download icon:', iconId)}
            onBulkDownload={(iconIds) => console.log('Bulk download:', iconIds)}
            onBulkDelete={handleBulkDelete}
            onPreview={(icon) => {
              setPreviewIcon(icon);
              setIsPreviewOpen(true);
            }}
          />
        </TabsContent>

        {/* Categories Tab */}
        <TabsContent value="categories" className="space-y-6">
          <CategoryManagementPanel
            categories={categories.map(cat => ({ ...cat, level: 0 }))}
            availableIcons={generatedIcons}
            onCategoryCreate={(parentId, name, description) => {
              const newCategory: CategoryData = {
                id: Date.now().toString(),
                name,
                description,
                keywords: []
              };
              setCategories(prev => [...prev, newCategory]);
            }}
            onCategoryUpdate={(categoryId, updates) => {
              setCategories(prev => prev.map(cat =>
                cat.id === categoryId ? { ...cat, ...updates } : cat
              ));
            }}
            onCategoryDelete={(categoryId) => {
              setCategories(prev => prev.filter(cat => cat.id !== categoryId));
            }}
            onIconAssign={(categoryId, iconId) => {
              console.log('Assign icon:', iconId, 'to category:', categoryId);
            }}
            onIconUnassign={(categoryId) => {
              console.log('Unassign icon from category:', categoryId);
            }}
            onCategoriesExport={() => console.log('Export categories')}
          />
        </TabsContent>

        {/* Shopify Tab */}
        <TabsContent value="shopify" className="space-y-6">
          <ShopifyCollectionManager
            onGenerateIcon={(collection) => {
              // Convert Shopify collection to category and trigger generation
              const category: CategoryData = {
                id: collection.id,
                name: collection.title,
                description: collection.description,
                keywords: []
              };
              
              // Trigger single icon generation
              handleIconGeneration([category.id], {
                style: 'modern',
                colorScheme: 'brand',
                size: '128',
                format: 'png',
                backgroundColor: '#ffffff',
                foregroundColor: '#3B82F6',
                theme: 'light',
                includeVariants: false,
                batchSize: 1,
                model: 'gpt-image-1'
              });
            }}
            onSyncIcon={(collectionId, iconPath) => {
              // Handle syncing a local icon to Shopify
              console.log('Sync icon to Shopify collection:', collectionId, iconPath);
            }}
          />
        </TabsContent>
      </Tabs>

      {/* Icon Preview Modal */}
      <IconPreviewModal
        icon={previewIcon}
        isOpen={isPreviewOpen}
        onClose={() => {
          setIsPreviewOpen(false);
          setPreviewIcon(null);
        }}
        onDownload={(iconId) => {
          console.log('Download icon:', iconId);
          // Implement actual download logic here
          const icon = generatedIcons.find(i => i.id === iconId);
          if (icon) {
            window.open(icon.imageUrl, '_blank');
          }
        }}
        onFavorite={(iconId, favorite) => {
          handleIconFavorite(iconId, favorite);
          // Update the preview icon if it's the same one
          if (previewIcon?.id === iconId) {
            setPreviewIcon(prev => prev ? { ...prev, isFavorite: favorite } : null);
          }
        }}
        onRegenerate={async (iconId, style) => {
          // Find the icon to regenerate
          const icon = generatedIcons.find(i => i.id === iconId);
          if (!icon) return;
          
          // Update UI to show regenerating state
          setIsRegenerating(true);
          
          try {
            // Call the API to regenerate the icon
            const response = await fetch('http://localhost:3560/api/icons/generate', {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                category_id: parseInt(icon.categoryId.replace(/\D/g, '')) || 999,
                category_name: icon.categoryName,
                style: style,
                color: '#3B82F6', // Use default or extract from current icon
                size: parseInt(icon.size) || 128,
                background: 'white'
              })
            });
            
            if (response.ok) {
              const result = await response.json();
              
              // Refresh the entire icon list from API to get updated data
              loadIconsFromAPI();
              
              // Update preview if it's the same icon
              if (previewIcon?.id === iconId) {
                const updatedIcon: GeneratedIcon = {
                  ...icon,
                  style: style,
                  generatedAt: new Date().toISOString(),
                  // Force refresh the image URL by adding timestamp
                  imageUrl: `${icon.imageUrl}?t=${Date.now()}`
                };
                setPreviewIcon(updatedIcon);
              }
            } else {
              console.error('Failed to regenerate icon');
              // Could add toast notification here
            }
          } catch (error) {
            console.error('Error regenerating icon:', error);
            // Could add toast notification here
          } finally {
            setIsRegenerating(false);
          }
        }}
        isRegenerating={isRegenerating}
      />
    </div>
  );
}
