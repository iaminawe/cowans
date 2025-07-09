import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { 
  Package,
  Plus,
  Wand2,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Upload,
  RefreshCw,
  Search,
  Filter,
  Tag,
  Layers,
  TrendingUp,
  Brain,
  Eye,
  Edit,
  Trash2,
  Store
} from 'lucide-react';

interface ProductType {
  name: string;
  product_count: number;
  avg_price: number;
  categories: string[];
  vendors: string[];
  sample_products: string[];
  suggested_collection_name?: string;
  suggested_description?: string;
  existing_collection_id?: string;
  collection_status: 'none' | 'suggested' | 'created' | 'synced';
}

interface Collection {
  id: string;
  name: string;
  description: string;
  handle: string;
  product_count: number;
  product_types: string[];
  created_locally: boolean;
  shopify_collection_id?: string;
  shopify_synced_at?: string;
  status: 'draft' | 'review' | 'approved' | 'synced';
  ai_generated: boolean;
  rules?: {
    type: 'manual' | 'automatic';
    conditions: Array<{
      field: 'product_type' | 'vendor' | 'title' | 'tag';
      operator: 'equals' | 'contains' | 'starts_with' | 'ends_with';
      value: string;
    }>;
  };
}

interface ProductTypeCollectionManagerProps {
  className?: string;
}

export function ProductTypeCollectionManager({ className }: ProductTypeCollectionManagerProps) {
  const [productTypes, setProductTypes] = useState<ProductType[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'types' | 'collections' | 'ai-suggestions'>('types');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isGeneratingAI, setIsGeneratingAI] = useState(false);
  const [newCollection, setNewCollection] = useState<Partial<Collection>>({
    name: '',
    description: '',
    status: 'draft',
    ai_generated: false,
    created_locally: true
  });

  useEffect(() => {
    loadProductTypes();
    loadCollections();
  }, []);

  const loadProductTypes = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:3560/api/collections/product-types-summary', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setProductTypes(data.product_types);
      } else {
        console.error('Failed to load product types');
      }
    } catch (error) {
      console.error('Error loading product types:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadCollections = async () => {
    try {
      const response = await fetch('http://localhost:3560/api/collections/managed', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setCollections(data.collections);
      } else {
        console.error('Failed to load collections');
      }
    } catch (error) {
      console.error('Error loading collections:', error);
    }
  };

  const generateAISuggestions = async () => {
    if (selectedTypes.length === 0) {
      alert('Please select at least one product type');
      return;
    }

    setIsGeneratingAI(true);
    try {
      const response = await fetch('http://localhost:3560/api/collections/ai-suggestions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          product_types: selectedTypes
        })
      });

      if (response.ok) {
        const data = await response.json();
        
        // Update product types with AI suggestions
        setProductTypes(prev => 
          prev.map(pt => {
            const suggestion = data.suggestions.find((s: any) => s.product_type === pt.name);
            if (suggestion) {
              return {
                ...pt,
                suggested_collection_name: suggestion.collection_name,
                suggested_description: suggestion.description,
                collection_status: 'suggested'
              };
            }
            return pt;
          })
        );

        console.log(`Generated AI suggestions for ${selectedTypes.length} product types`);
      } else {
        const errorData = await response.json();
        alert(`Failed to generate AI suggestions: ${errorData.message}`);
      }
    } catch (error) {
      console.error('Error generating AI suggestions:', error);
      alert('Network error while generating AI suggestions');
    } finally {
      setIsGeneratingAI(false);
    }
  };

  const createCollectionFromType = async (productType: ProductType) => {
    try {
      const collectionData = {
        name: productType.suggested_collection_name || productType.name,
        description: productType.suggested_description || `Products in the ${productType.name} category`,
        handle: (productType.suggested_collection_name || productType.name).toLowerCase().replace(/[^a-z0-9]+/g, '-'),
        product_types: [productType.name],
        status: 'draft',
        ai_generated: !!productType.suggested_collection_name,
        created_locally: true,
        rules: {
          type: 'automatic' as const,
          conditions: [{
            field: 'product_type' as const,
            operator: 'equals' as const,
            value: productType.name
          }]
        }
      };

      const response = await fetch('http://localhost:3560/api/collections/create', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(collectionData)
      });

      if (response.ok) {
        const data = await response.json();
        
        // Update product type status
        setProductTypes(prev =>
          prev.map(pt =>
            pt.name === productType.name
              ? { ...pt, collection_status: 'created', existing_collection_id: data.collection.id }
              : pt
          )
        );

        // Reload collections
        loadCollections();
        
        console.log(`Created collection for product type: ${productType.name}`);
      } else {
        const errorData = await response.json();
        alert(`Failed to create collection: ${errorData.message}`);
      }
    } catch (error) {
      console.error('Error creating collection:', error);
      alert('Network error while creating collection');
    }
  };

  const createCustomCollection = async () => {
    if (!newCollection.name || !newCollection.description) {
      alert('Please provide a collection name and description');
      return;
    }

    try {
      const collectionData = {
        ...newCollection,
        handle: newCollection.name!.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
        product_types: selectedTypes,
        rules: selectedTypes.length > 0 ? {
          type: 'automatic' as const,
          conditions: selectedTypes.map(type => ({
            field: 'product_type' as const,
            operator: 'equals' as const,
            value: type
          }))
        } : undefined
      };

      const response = await fetch('http://localhost:3560/api/collections/create', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(collectionData)
      });

      if (response.ok) {
        setIsCreateDialogOpen(false);
        setNewCollection({
          name: '',
          description: '',
          status: 'draft',
          ai_generated: false,
          created_locally: true
        });
        setSelectedTypes([]);
        
        // Reload collections
        loadCollections();
        
        console.log('Created custom collection successfully');
      } else {
        const errorData = await response.json();
        alert(`Failed to create collection: ${errorData.message}`);
      }
    } catch (error) {
      console.error('Error creating custom collection:', error);
      alert('Network error while creating collection');
    }
  };

  const syncCollectionToShopify = async (collection: Collection) => {
    try {
      const response = await fetch(`http://localhost:3560/api/collections/${collection.id}/sync-to-shopify`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken') || 'dev-token'}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        
        // Update collection status
        setCollections(prev =>
          prev.map(c =>
            c.id === collection.id
              ? { 
                  ...c, 
                  status: 'synced', 
                  shopify_collection_id: data.shopify_collection_id,
                  shopify_synced_at: new Date().toISOString()
                }
              : c
          )
        );
        
        console.log(`Synced collection to Shopify: ${collection.name}`);
      } else {
        const errorData = await response.json();
        alert(`Failed to sync collection: ${errorData.message}`);
      }
    } catch (error) {
      console.error('Error syncing collection:', error);
      alert('Network error while syncing collection');
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'none':
        return <Badge variant="outline">No Collection</Badge>;
      case 'suggested':
        return <Badge variant="secondary" className="bg-blue-100 text-blue-800">AI Suggested</Badge>;
      case 'created':
        return <Badge variant="default" className="bg-green-100 text-green-800">Created</Badge>;
      case 'synced':
        return <Badge variant="default" className="bg-purple-100 text-purple-800">Synced</Badge>;
      case 'draft':
        return <Badge variant="outline">Draft</Badge>;
      case 'review':
        return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">Review</Badge>;
      case 'approved':
        return <Badge variant="default" className="bg-green-100 text-green-800">Approved</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const filteredProductTypes = productTypes.filter(pt =>
    pt.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredCollections = collections.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Product Type Collections</h2>
          <p className="text-muted-foreground">
            Organize products into collections based on product types and AI recommendations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create Collection
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Collection</DialogTitle>
                <DialogDescription>
                  Create a new product collection with automatic or manual rules
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="collection-name">Collection Name</Label>
                  <Input
                    id="collection-name"
                    value={newCollection.name || ''}
                    onChange={(e) => setNewCollection(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="e.g., Office Supplies"
                  />
                </div>
                <div>
                  <Label htmlFor="collection-description">Description</Label>
                  <Input
                    id="collection-description"
                    value={newCollection.description || ''}
                    onChange={(e: any) => setNewCollection(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Describe this collection..."
                  />
                </div>
                {selectedTypes.length > 0 && (
                  <div>
                    <Label>Selected Product Types</Label>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {selectedTypes.map(type => (
                        <Badge key={type} variant="secondary">{type}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={createCustomCollection}>
                  Create Collection
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Button variant="outline" onClick={() => { loadProductTypes(); loadCollections(); }}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Search and Actions */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search product types or collections..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        {selectedTypes.length > 0 && (
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{selectedTypes.length} selected</Badge>
            <Button
              variant="outline"
              onClick={generateAISuggestions}
              disabled={isGeneratingAI}
            >
              {isGeneratingAI ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Brain className="h-4 w-4 mr-2" />
                  AI Suggestions
                </>
              )}
            </Button>
            <Button variant="outline" onClick={() => setSelectedTypes([])}>
              Clear Selection
            </Button>
          </div>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="types">
            Product Types ({productTypes.length})
          </TabsTrigger>
          <TabsTrigger value="collections">
            Collections ({collections.length})
          </TabsTrigger>
          <TabsTrigger value="ai-suggestions">
            AI Suggestions
          </TabsTrigger>
        </TabsList>

        {/* Product Types Tab */}
        <TabsContent value="types" className="space-y-4">
          <div className="grid gap-4">
            {loading ? (
              Array.from({ length: 6 }).map((_, idx) => (
                <Card key={idx}>
                  <CardContent className="p-4">
                    <Skeleton className="h-6 w-48 mb-2" />
                    <Skeleton className="h-4 w-full mb-1" />
                    <Skeleton className="h-4 w-3/4" />
                  </CardContent>
                </Card>
              ))
            ) : filteredProductTypes.length === 0 ? (
              <Card>
                <CardContent className="text-center py-8">
                  <Package className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">No product types found</p>
                </CardContent>
              </Card>
            ) : (
              filteredProductTypes.map((productType) => (
                <Card key={productType.name} className="hover:shadow-md transition-shadow">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3 flex-1">
                        <input
                          type="checkbox"
                          checked={selectedTypes.includes(productType.name)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedTypes(prev => [...prev, productType.name]);
                            } else {
                              setSelectedTypes(prev => prev.filter(t => t !== productType.name));
                            }
                          }}
                          className="mt-1"
                        />
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <h3 className="font-semibold">{productType.name}</h3>
                            {getStatusBadge(productType.collection_status)}
                          </div>
                          
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                            <div>
                              <span className="text-muted-foreground">Products:</span>
                              <span className="ml-1 font-medium">{productType.product_count}</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Avg Price:</span>
                              <span className="ml-1 font-medium">${productType.avg_price.toFixed(2)}</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Vendors:</span>
                              <span className="ml-1 font-medium">{productType.vendors.length}</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Categories:</span>
                              <span className="ml-1 font-medium">{productType.categories.length}</span>
                            </div>
                          </div>

                          {productType.suggested_collection_name && (
                            <div className="mt-2 p-2 bg-blue-50 rounded border-l-4 border-blue-400">
                              <p className="text-sm font-medium text-blue-800">
                                AI Suggestion: "{productType.suggested_collection_name}"
                              </p>
                              <p className="text-xs text-blue-600">{productType.suggested_description}</p>
                            </div>
                          )}

                          <div className="mt-2 flex flex-wrap gap-1">
                            {productType.sample_products.slice(0, 3).map((product, idx) => (
                              <Badge key={idx} variant="outline" className="text-xs">
                                {product}
                              </Badge>
                            ))}
                            {productType.sample_products.length > 3 && (
                              <Badge variant="outline" className="text-xs">
                                +{productType.sample_products.length - 3} more
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex flex-col gap-2">
                        {productType.collection_status === 'none' && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => createCollectionFromType(productType)}
                          >
                            <Plus className="h-3 w-3 mr-1" />
                            Create
                          </Button>
                        )}
                        {productType.collection_status === 'suggested' && (
                          <Button
                            size="sm"
                            onClick={() => createCollectionFromType(productType)}
                          >
                            <CheckCircle2 className="h-3 w-3 mr-1" />
                            Accept
                          </Button>
                        )}
                        {productType.existing_collection_id && (
                          <Button
                            size="sm"
                            variant="outline"
                          >
                            <Eye className="h-3 w-3 mr-1" />
                            View
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>

        {/* Collections Tab */}
        <TabsContent value="collections" className="space-y-4">
          <div className="grid gap-4">
            {filteredCollections.length === 0 ? (
              <Card>
                <CardContent className="text-center py-8">
                  <Layers className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">No collections found</p>
                </CardContent>
              </Card>
            ) : (
              filteredCollections.map((collection) => (
                <Card key={collection.id} className="hover:shadow-md transition-shadow">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <h3 className="font-semibold">{collection.name}</h3>
                          {getStatusBadge(collection.status)}
                          {collection.ai_generated && (
                            <Badge variant="outline" className="bg-purple-50 text-purple-700">
                              <Brain className="h-3 w-3 mr-1" />
                              AI Generated
                            </Badge>
                          )}
                        </div>
                        
                        <p className="text-sm text-muted-foreground mb-3">{collection.description}</p>
                        
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm mb-3">
                          <div>
                            <span className="text-muted-foreground">Products:</span>
                            <span className="ml-1 font-medium">{collection.product_count}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Handle:</span>
                            <span className="ml-1 font-mono text-xs">{collection.handle}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Rule Type:</span>
                            <span className="ml-1 font-medium capitalize">{collection.rules?.type || 'Manual'}</span>
                          </div>
                        </div>

                        <div className="flex flex-wrap gap-1 mb-2">
                          {collection.product_types.map((type) => (
                            <Badge key={type} variant="secondary" className="text-xs">
                              <Tag className="h-3 w-3 mr-1" />
                              {type}
                            </Badge>
                          ))}
                        </div>

                        {collection.shopify_synced_at && (
                          <p className="text-xs text-muted-foreground">
                            Synced to Shopify: {new Date(collection.shopify_synced_at).toLocaleString()}
                          </p>
                        )}
                      </div>
                      
                      <div className="flex flex-col gap-2">
                        {collection.status !== 'synced' && (
                          <Button
                            size="sm"
                            onClick={() => syncCollectionToShopify(collection)}
                          >
                            <Upload className="h-3 w-3 mr-1" />
                            Sync to Shopify
                          </Button>
                        )}
                        {collection.shopify_collection_id && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => window.open(`https://e19833-4.myshopify.com/admin/collections/${collection.shopify_collection_id}`, '_blank')}
                          >
                            <ExternalLink className="h-3 w-3 mr-1" />
                            View in Shopify
                          </Button>
                        )}
                        <Button size="sm" variant="outline">
                          <Edit className="h-3 w-3 mr-1" />
                          Edit
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>

        {/* AI Suggestions Tab */}
        <TabsContent value="ai-suggestions" className="space-y-4">
          <Alert>
            <Brain className="h-4 w-4" />
            <AlertDescription>
              AI-powered collection suggestions will analyze your product data to recommend optimal collection structures, 
              naming conventions, and product groupings based on market trends and e-commerce best practices.
            </AlertDescription>
          </Alert>
          
          <Card>
            <CardHeader>
              <CardTitle>Coming Soon: Advanced AI Features</CardTitle>
              <CardDescription>
                Enhanced AI capabilities for intelligent product categorization and collection optimization
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <TrendingUp className="h-5 w-5 text-blue-500" />
                  <span>Market trend analysis for collection optimization</span>
                </div>
                <div className="flex items-center gap-3">
                  <Brain className="h-5 w-5 text-purple-500" />
                  <span>Semantic product similarity detection</span>
                </div>
                <div className="flex items-center gap-3">
                  <Store className="h-5 w-5 text-green-500" />
                  <span>Cross-selling opportunity identification</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}