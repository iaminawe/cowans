import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { BulkIconPreview } from './BulkIconPreview';
import { BulkGenerationProgress } from './BulkGenerationProgress';
import { useNotifications } from './NotificationSystem';
import { 
  Image, Wand2, Download, Trash2, RefreshCw, 
  CheckCircle, XCircle, Clock, Sparkles, Grid3X3,
  Palette, Zap, AlertTriangle, FolderOpen, Activity,
  CheckSquare, Square, Eye, FileImage, Upload,
  Loader2, CheckCircle2, Info
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useWebSocket } from '@/contexts/WebSocketContext';

interface GeneratedIcon {
  id: string;
  category: string;
  image_url: string;
  local_path: string;
  generation_time: number;
  metadata?: {
    style?: string;
    color_scheme?: string;
    model?: string;
    size?: string;
  };
  created_at: string;
}

interface BatchJob {
  batch_id: string;
  status: string;
  progress: number;
  current_category?: string;
  total_categories: number;
  completed_categories: number;
  created_at: string;
  completed_at?: string;
}

interface CategorySuggestion {
  id: number;
  name: string;
  slug: string;
  has_icon: boolean;
}

interface Collection {
  id: string;
  title: string;
  handle: string;
  products_count: number;
  image_url?: string;
  has_icon: boolean;
}

interface BulkGenerationResult {
  successful: string[];
  failed: Array<{ collection_id: string; error: string }>;
  total: number;
}

export function IconGenerationDashboard() {
  const [activeTab, setActiveTab] = useState('generate');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Bulk operations state
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCollections, setSelectedCollections] = useState<Set<string>>(new Set());
  const [bulkGenerating, setBulkGenerating] = useState(false);
  const [bulkProgress, setBulkProgress] = useState({ current: 0, total: 0 });
  const [showPreviewDialog, setShowPreviewDialog] = useState(false);
  const [bulkResults, setBulkResults] = useState<any[]>([]);
  
  // Single generation state
  const [category, setCategory] = useState('');
  const [style, setStyle] = useState('modern');
  const [colorScheme, setColorScheme] = useState('brand_colors');
  const [customElements, setCustomElements] = useState('');
  
  // Batch generation state
  const [batchCategories, setBatchCategories] = useState('');
  const [batchStyle, setBatchStyle] = useState('modern');
  const [batchColorScheme, setBatchColorScheme] = useState('brand_colors');
  const [variationsPerCategory, setVariationsPerCategory] = useState(1);
  
  // Results state
  const [generatedIcon, setGeneratedIcon] = useState<GeneratedIcon | null>(null);
  const [batchJobs, setBatchJobs] = useState<BatchJob[]>([]);
  const [cachedIcons, setCachedIcons] = useState<GeneratedIcon[]>([]);
  const [suggestions, setSuggestions] = useState<CategorySuggestion[]>([]);
  const [stats, setStats] = useState<any>(null);
  
  const { subscribe } = useWebSocket();
  const { addNotification } = useNotifications();

  useEffect(() => {
    loadInitialData();
    loadCollections();
    
    // Subscribe to batch progress updates
    const unsubscribe = subscribe('batch_progress', (data) => {
      updateBatchProgress(data.batch_id, data);
    });
    
    // Subscribe to bulk generation updates
    const unsubscribeBulk = subscribe('bulk_generation_progress', (data) => {
      setBulkProgress({ current: data.completed, total: data.total });
      if (data.status === 'completed') {
        handleBulkGenerationComplete(data.results);
      }
    });
    
    return () => {
      unsubscribe();
      unsubscribeBulk();
    };
  }, [subscribe]);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      
      // Load active batch jobs
      const jobs = await apiClient.get<BatchJob[]>('/icons/batches');
      setBatchJobs(jobs);
      
      // Load cached icons
      const icons = await apiClient.get<GeneratedIcon[]>('/icons/cached');
      setCachedIcons(icons);
      
      // Load stats
      const statsData = await apiClient.get<any>('/icons/stats');
      setStats(statsData);
      
    } catch (err) {
      console.error('Failed to load initial data:', err);
    } finally {
      setLoading(false);
    }
  };
  
  const loadCollections = async () => {
    try {
      const data = await apiClient.get<any>('/collections');
      // Handle different response formats
      const collectionsArray = Array.isArray(data) ? data : (data?.collections || []);
      setCollections(collectionsArray);
    } catch (err) {
      console.error('Failed to load collections:', err);
      setCollections([]); // Ensure collections is always an array
    }
  };

  const updateBatchProgress = (batchId: string, progressData: any) => {
    setBatchJobs(prev => prev.map(job => 
      job.batch_id === batchId 
        ? {
            ...job,
            progress: progressData.progress,
            current_category: progressData.current_category,
            completed_categories: progressData.completed
          }
        : job
    ));
  };

  const handleCategorySuggestions = async (value: string) => {
    if (value.length < 2) {
      setSuggestions([]);
      return;
    }
    
    try {
      const results = await apiClient.get<CategorySuggestion[]>(`/icons/categories/suggestions?q=${encodeURIComponent(value)}`);
      setSuggestions(results);
    } catch (err) {
      console.error('Failed to get suggestions:', err);
    }
  };

  const handleSingleGeneration = async () => {
    if (!category.trim()) {
      setError('Category is required');
      return;
    }
    
    try {
      setGenerating(true);
      setError(null);
      setGeneratedIcon(null);
      
      const result = await apiClient.post<any>('/icons/generate', {
        category: category.trim(),
        style,
        color_scheme: colorScheme,
        custom_elements: customElements.split(',').map(e => e.trim()).filter(Boolean)
      });
      
      if (result.success) {
        setGeneratedIcon({
          id: `icon-${Date.now()}`,
          category: category.trim(),
          image_url: result.image_url,
          local_path: result.local_path,
          generation_time: result.generation_time,
          metadata: result.metadata,
          created_at: new Date().toISOString()
        });
        
        // Refresh cached icons
        const icons = await apiClient.get<GeneratedIcon[]>('/icons/cached');
        setCachedIcons(icons);
      } else {
        setError(result.error || 'Failed to generate icon');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to generate icon');
    } finally {
      setGenerating(false);
    }
  };

  const handleBatchGeneration = async () => {
    const categories = batchCategories.split('\n').map(c => c.trim()).filter(Boolean);
    
    if (categories.length === 0) {
      setError('At least one category is required');
      return;
    }
    
    try {
      setGenerating(true);
      setError(null);
      
      const result = await apiClient.post<any>('/icons/generate/batch', {
        categories,
        style: batchStyle,
        color_scheme: batchColorScheme,
        variations_per_category: variationsPerCategory
      });
      
      // Reload batch jobs
      const jobs = await apiClient.get<BatchJob[]>('/icons/batches');
      setBatchJobs(jobs);
      
      // Clear form
      setBatchCategories('');
      setActiveTab('monitor');
      
    } catch (err: any) {
      setError(err.message || 'Failed to start batch generation');
    } finally {
      setGenerating(false);
    }
  };

  const handleCancelBatch = async (batchId: string) => {
    try {
      await apiClient.post(`/icons/batch/${batchId}/cancel`);
      
      // Reload batch jobs
      const jobs = await apiClient.get<BatchJob[]>('/icons/batches');
      setBatchJobs(jobs);
    } catch (err) {
      console.error('Failed to cancel batch:', err);
    }
  };

  const handleClearCache = async () => {
    try {
      await apiClient.post('/icons/cache/clear', {
        older_than_days: 7
      });
      
      // Reload cached icons
      const icons = await apiClient.get<GeneratedIcon[]>('/icons/cached');
      setCachedIcons(icons);
    } catch (err) {
      console.error('Failed to clear cache:', err);
    }
  };

  const downloadIcon = (imageUrl: string, category: string) => {
    const link = document.createElement('a');
    link.href = imageUrl;
    link.download = `${category.toLowerCase().replace(/\s+/g, '-')}-icon.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };
  
  // Bulk operations handlers
  const handleSelectAll = () => {
    if (Array.isArray(collections) && selectedCollections.size === collections.length) {
      setSelectedCollections(new Set());
    } else {
      setSelectedCollections(new Set(Array.isArray(collections) ? collections.map(c => c.id) : []));
    }
  };
  
  const handleSelectCollection = (collectionId: string) => {
    const newSelected = new Set(selectedCollections);
    if (newSelected.has(collectionId)) {
      newSelected.delete(collectionId);
    } else {
      newSelected.add(collectionId);
    }
    setSelectedCollections(newSelected);
  };
  
  const handleBulkPreview = () => {
    if (selectedCollections.size === 0) {
      addNotification({
        type: 'warning',
        title: 'No collections selected',
        description: 'Please select at least one collection to preview.'
      });
      return;
    }
    setShowPreviewDialog(true);
  };
  
  const handleBulkGenerate = async () => {
    if (selectedCollections.size === 0) {
      addNotification({
        type: 'warning',
        title: 'No collections selected',
        description: 'Please select at least one collection to generate icons for.'
      });
      return;
    }
    
    try {
      setBulkGenerating(true);
      setBulkProgress({ current: 0, total: selectedCollections.size });
      
      const collectionIds = Array.from(selectedCollections);
      const result = await apiClient.post<any>('/icons/generate/bulk', {
        collection_ids: collectionIds,
        style: batchStyle,
        color_scheme: batchColorScheme,
        priority: true
      });
      
      if (result.job_id) {
        addNotification({
          type: 'info',
          title: 'Bulk generation started',
          description: `Generating icons for ${collectionIds.length} collections. Job ID: ${result.job_id}`
        });
      }
    } catch (err: any) {
      addNotification({
        type: 'error',
        title: 'Bulk generation failed',
        description: err.message || 'Failed to start bulk icon generation'
      });
    } finally {
      setBulkGenerating(false);
      setShowPreviewDialog(false);
    }
  };
  
  const handleBulkGenerationComplete = (results: BulkGenerationResult) => {
    setBulkGenerating(false);
    setBulkProgress({ current: 0, total: 0 });
    setSelectedCollections(new Set());
    
    // Refresh data
    loadInitialData();
    loadCollections();
    
    // Show completion notification
    addNotification({
      type: results.failed.length === 0 ? 'success' : 'warning',
      title: 'Bulk generation completed',
      description: `Successfully generated ${results.successful.length}/${results.total} icons${results.failed.length > 0 ? `. ${results.failed.length} failed.` : '.'}`
    });
  };
  

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600';
      case 'failed':
        return 'text-red-600';
      case 'running':
        return 'text-blue-600';
      default:
        return 'text-gray-600';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4" />;
      case 'failed':
        return <XCircle className="w-4 h-4" />;
      case 'running':
        return <Clock className="w-4 h-4 animate-spin" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Bulk Icon Preview Dialog */}
      <BulkIconPreview
        open={showPreviewDialog}
        onOpenChange={setShowPreviewDialog}
        collections={Array.isArray(collections) ? collections.filter(c => selectedCollections.has(c.id)) : []}
        style={batchStyle}
        colorScheme={batchColorScheme}
        onGenerate={handleBulkGenerate}
        isGenerating={bulkGenerating}
      />
      
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Icon Generation</h2>
          <p className="text-muted-foreground">Generate AI-powered category icons using OpenAI</p>
        </div>
        {stats && (
          <div className="flex gap-4 text-sm">
            <div className="text-center">
              <div className="text-2xl font-bold">{stats.total_generated}</div>
              <div className="text-muted-foreground">Total Icons</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{stats.categories_covered}</div>
              <div className="text-muted-foreground">Categories</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{stats.cache_size}</div>
              <div className="text-muted-foreground">Cached</div>
            </div>
          </div>
        )}
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="generate">
            <Wand2 className="w-4 h-4 mr-2" />
            Generate
          </TabsTrigger>
          <TabsTrigger value="batch">
            <Grid3X3 className="w-4 h-4 mr-2" />
            Batch
          </TabsTrigger>
          <TabsTrigger value="monitor">
            <Activity className="w-4 h-4 mr-2" />
            Monitor
          </TabsTrigger>
          <TabsTrigger value="library">
            <FolderOpen className="w-4 h-4 mr-2" />
            Library
          </TabsTrigger>
        </TabsList>

        {/* Single Generation Tab */}
        <TabsContent value="generate" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Generate Single Icon</CardTitle>
              <CardDescription>Create a custom icon for a specific category</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="category">Category Name</Label>
                  <Input
                    id="category"
                    value={category}
                    onChange={(e) => {
                      setCategory(e.target.value);
                      handleCategorySuggestions(e.target.value);
                    }}
                    placeholder="e.g., Electronics, Office Supplies"
                    disabled={generating}
                  />
                  {suggestions.length > 0 && (
                    <div className="border rounded-md p-2 space-y-1 max-h-32 overflow-y-auto">
                      {suggestions.map(s => (
                        <div
                          key={s.id}
                          className="flex items-center justify-between p-1 hover:bg-accent rounded cursor-pointer"
                          onClick={() => {
                            setCategory(s.name);
                            setSuggestions([]);
                          }}
                        >
                          <span className="text-sm">{s.name}</span>
                          {s.has_icon && (
                            <Badge variant="secondary" className="text-xs">Has Icon</Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="style">Style</Label>
                  <Select value={style} onValueChange={setStyle} disabled={generating}>
                    <SelectTrigger id="style">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="modern">Modern</SelectItem>
                      <SelectItem value="minimalist">Minimalist</SelectItem>
                      <SelectItem value="detailed">Detailed</SelectItem>
                      <SelectItem value="abstract">Abstract</SelectItem>
                      <SelectItem value="flat">Flat Design</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="colorScheme">Color Scheme</Label>
                  <Select value={colorScheme} onValueChange={setColorScheme} disabled={generating}>
                    <SelectTrigger id="colorScheme">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="brand_colors">Brand Colors</SelectItem>
                      <SelectItem value="monochrome">Monochrome</SelectItem>
                      <SelectItem value="vibrant">Vibrant</SelectItem>
                      <SelectItem value="pastel">Pastel</SelectItem>
                      <SelectItem value="natural">Natural</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="customElements">Custom Elements (comma-separated)</Label>
                  <Input
                    id="customElements"
                    value={customElements}
                    onChange={(e) => setCustomElements(e.target.value)}
                    placeholder="e.g., modern, tech, professional"
                    disabled={generating}
                  />
                </div>
              </div>
              
              <Button 
                onClick={handleSingleGeneration} 
                disabled={generating || !category.trim()}
                className="w-full"
              >
                {generating ? (
                  <>
                    <Sparkles className="w-4 h-4 mr-2 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Wand2 className="w-4 h-4 mr-2" />
                    Generate Icon
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Generated Icon Result */}
          {generatedIcon && (
            <Card>
              <CardHeader>
                <CardTitle>Generated Icon</CardTitle>
                <CardDescription>
                  Generated in {generatedIcon.generation_time}s
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex gap-4">
                  <div className="relative group">
                    <img
                      src={generatedIcon.image_url}
                      alt={generatedIcon.category}
                      className="w-32 h-32 rounded-lg border"
                    />
                    <div className="absolute inset-0 bg-black bg-opacity-50 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-white hover:text-white"
                        onClick={() => downloadIcon(generatedIcon.image_url, generatedIcon.category)}
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex-1 space-y-2">
                    <h4 className="font-semibold">{generatedIcon.category}</h4>
                    <div className="flex gap-2">
                      <Badge variant="secondary">{generatedIcon.metadata?.style || style}</Badge>
                      <Badge variant="secondary">{generatedIcon.metadata?.color_scheme || colorScheme}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Model: {generatedIcon.metadata?.model || 'dall-e-3'}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Batch Generation Tab */}
        <TabsContent value="batch" className="space-y-4">
          {/* Bulk Selection Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Bulk Icon Generation</CardTitle>
                  <CardDescription>Select collections to generate icons for</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">
                    {selectedCollections.size} selected
                  </Badge>
                  {selectedCollections.size > 0 && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleBulkPreview}
                      >
                        <Eye className="w-4 h-4 mr-2" />
                        Preview
                      </Button>
                      <Button
                        size="sm"
                        onClick={handleBulkGenerate}
                        disabled={bulkGenerating}
                      >
                        {bulkGenerating ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Generating...
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-4 h-4 mr-2" />
                            Generate Icons
                          </>
                        )}
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {/* Select All / Filters */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      checked={Array.isArray(collections) && selectedCollections.size === collections.length && collections.length > 0}
                      onCheckedChange={handleSelectAll}
                    />
                    <Label className="text-sm font-medium">Select All</Label>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        // Filter to show only collections without icons
                        const withoutIcons = Array.isArray(collections) ? collections.filter(c => !c.has_icon) : [];
                        setSelectedCollections(new Set(withoutIcons.map(c => c.id)));
                      }}
                    >
                      Select Without Icons
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setSelectedCollections(new Set())}
                    >
                      Clear Selection
                    </Button>
                  </div>
                </div>
                
                {/* Collections List */}
                <ScrollArea className="h-[400px] border rounded-lg">
                  <div className="p-4 space-y-2">
                    {!Array.isArray(collections) || collections.length === 0 ? (
                      <div className="text-center py-8 text-muted-foreground">
                        <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                        Loading collections...
                      </div>
                    ) : (
                      (Array.isArray(collections) ? collections : []).map((collection) => (
                        <div
                          key={collection.id}
                          className={cn(
                            "flex items-center gap-3 p-3 rounded-lg border transition-colors",
                            selectedCollections.has(collection.id) && "bg-accent"
                          )}
                        >
                          <Checkbox
                            checked={selectedCollections.has(collection.id)}
                            onCheckedChange={() => handleSelectCollection(collection.id)}
                          />
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <span className="font-medium">{collection.title}</span>
                              <Badge variant="outline" className="text-xs">
                                {collection.products_count} products
                              </Badge>
                              {collection.has_icon && (
                                <Badge variant="secondary" className="text-xs">
                                  <CheckCircle2 className="w-3 h-3 mr-1" />
                                  Has Icon
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground">
                              Handle: {collection.handle}
                            </p>
                          </div>
                          {collection.image_url && (
                            <img
                              src={collection.image_url}
                              alt={collection.title}
                              className="w-12 h-12 rounded object-cover"
                            />
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </ScrollArea>
                
                {/* Bulk Progress */}
                {bulkGenerating && bulkProgress.total > 0 && (
                  <div className="border rounded-lg p-4 space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">Generating icons...</span>
                      <span className="text-muted-foreground">
                        {bulkProgress.current}/{bulkProgress.total}
                      </span>
                    </div>
                    <Progress 
                      value={(bulkProgress.current / bulkProgress.total) * 100} 
                      className="h-2"
                    />
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
          
          {/* Manual Batch Input Card */}
          <Card>
            <CardHeader>
              <CardTitle>Manual Batch Input</CardTitle>
              <CardDescription>Enter categories manually for batch generation</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="batchCategories">Categories (one per line)</Label>
                <Textarea
                  id="batchCategories"
                  value={batchCategories}
                  onChange={(e) => setBatchCategories(e.target.value)}
                  placeholder="Electronics&#10;Office Supplies&#10;Cleaning Products&#10;Tools & Hardware"
                  rows={6}
                  disabled={generating}
                />
                <p className="text-sm text-muted-foreground">
                  {batchCategories.split('\n').filter(c => c.trim()).length} categories
                </p>
              </div>
              
              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="batchStyle">Style</Label>
                  <Select value={batchStyle} onValueChange={setBatchStyle} disabled={generating}>
                    <SelectTrigger id="batchStyle">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="modern">Modern</SelectItem>
                      <SelectItem value="minimalist">Minimalist</SelectItem>
                      <SelectItem value="detailed">Detailed</SelectItem>
                      <SelectItem value="abstract">Abstract</SelectItem>
                      <SelectItem value="flat">Flat Design</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="batchColorScheme">Color Scheme</Label>
                  <Select value={batchColorScheme} onValueChange={setBatchColorScheme} disabled={generating}>
                    <SelectTrigger id="batchColorScheme">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="brand_colors">Brand Colors</SelectItem>
                      <SelectItem value="monochrome">Monochrome</SelectItem>
                      <SelectItem value="vibrant">Vibrant</SelectItem>
                      <SelectItem value="pastel">Pastel</SelectItem>
                      <SelectItem value="natural">Natural</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="variations">Variations per Category</Label>
                  <Select 
                    value={String(variationsPerCategory)} 
                    onValueChange={(v) => setVariationsPerCategory(Number(v))} 
                    disabled={generating}
                  >
                    <SelectTrigger id="variations">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1 variation</SelectItem>
                      <SelectItem value="2">2 variations</SelectItem>
                      <SelectItem value="3">3 variations</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <Button 
                onClick={handleBatchGeneration} 
                disabled={generating || batchCategories.split('\n').filter(c => c.trim()).length === 0}
                className="w-full"
              >
                {generating ? (
                  <>
                    <Sparkles className="w-4 h-4 mr-2 animate-spin" />
                    Starting Batch...
                  </>
                ) : (
                  <>
                    <Grid3X3 className="w-4 h-4 mr-2" />
                    Start Batch Generation
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Monitor Tab */}
        <TabsContent value="monitor" className="space-y-4">
          {/* Bulk Generation Progress */}
          {(bulkGenerating || bulkResults.length > 0) && (
            <BulkGenerationProgress
              isGenerating={bulkGenerating}
              progress={bulkProgress}
              results={bulkResults}
              onCancel={() => {
                // Cancel bulk generation
                setBulkGenerating(false);
                addNotification({
                  type: 'warning',
                  title: 'Generation cancelled',
                  description: 'Bulk icon generation has been cancelled.'
                });
              }}
            />
          )}
          
          <Card>
            <CardHeader>
              <CardTitle>Active Batch Jobs</CardTitle>
              <CardDescription>Monitor ongoing icon generation batches</CardDescription>
            </CardHeader>
            <CardContent>
              {batchJobs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No active batch jobs
                </div>
              ) : (
                <div className="space-y-4">
                  {batchJobs.map((job) => (
                    <div key={job.batch_id} className="border rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className={cn("flex items-center", getStatusColor(job.status))}>
                            {getStatusIcon(job.status)}
                          </div>
                          <span className="font-medium">Batch {job.batch_id.slice(0, 8)}</span>
                          <Badge variant="secondary">
                            {job.total_categories} categories
                          </Badge>
                        </div>
                        {job.status === 'running' && (
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleCancelBatch(job.batch_id)}
                          >
                            Cancel
                          </Button>
                        )}
                      </div>
                      
                      {job.status === 'running' && (
                        <>
                          <Progress value={job.progress} className="h-2" />
                          <div className="flex justify-between text-sm text-muted-foreground">
                            <span>
                              {job.current_category && `Generating: ${job.current_category}`}
                            </span>
                            <span>
                              {job.completed_categories}/{job.total_categories} completed
                            </span>
                          </div>
                        </>
                      )}
                      
                      <div className="text-sm text-muted-foreground">
                        Started: {new Date(job.created_at).toLocaleString()}
                        {job.completed_at && (
                          <> • Completed: {new Date(job.completed_at).toLocaleString()}</>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Library Tab */}
        <TabsContent value="library" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Icon Library</CardTitle>
                  <CardDescription>
                    Browse and manage generated icons
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button size="sm" variant="outline">
                        <Download className="w-4 h-4 mr-2" />
                        Export
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuItem onClick={() => {
                        // Export selected icons
                        addNotification({
                          type: 'info',
                          title: 'Export started',
                          description: 'Preparing icon export...'
                        });
                      }}>
                        Export Selected
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => {
                        // Export all icons
                        addNotification({
                          type: 'info',
                          title: 'Export started',
                          description: 'Exporting all icons...'
                        });
                      }}>
                        Export All
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleClearCache}
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Clear Old Cache
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {cachedIcons.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No cached icons available
                </div>
              ) : (
                <ScrollArea className="h-[500px]">
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                    {cachedIcons.map((icon) => (
                      <div key={icon.id} className="group relative">
                        <div className="aspect-square rounded-lg overflow-hidden border">
                          <img
                            src={icon.image_url}
                            alt={icon.category}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                          />
                        </div>
                        <div className="absolute inset-0 bg-black bg-opacity-75 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center p-2">
                          <p className="text-white text-xs font-medium text-center mb-2">
                            {icon.category}
                          </p>
                          <div className="flex gap-1">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-white hover:text-white"
                              onClick={() => downloadIcon(icon.image_url, icon.category)}
                            >
                              <Download className="w-4 h-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-white hover:text-white"
                              onClick={() => {
                                // TODO: Implement collection assignment
                                console.log('Assign icon to collection:', icon);
                              }}
                            >
                              <FolderOpen className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}