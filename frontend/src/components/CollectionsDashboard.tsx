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
import { apiClient, Collection } from '@/lib/api';
import { ShopifyCollectionManager } from './ShopifyCollectionManager';
import { ProductTypeCollectionManager } from './ProductTypeCollectionManager';
import { CollectionIconManager } from './CollectionIconManager';

// Component interfaces for imported components
interface ShopifyCollectionManagerProps {
  onGenerateIcon?: (collection: any) => void;
  onSyncIcon?: (collectionId: string, iconPath: string) => void;
}

interface ProductTypeCollectionManagerProps {
  // Add props as needed
}

interface CollectionIconManagerProps {
  // Add props as needed
}
import { 
  Layers,
  Plus,
  Package,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Upload,
  RefreshCw,
  Search,
  Filter,
  Tag,
  TrendingUp,
  Brain,
  Eye,
  Edit,
  Trash2,
  Store,
  BarChart,
  Grid,
  Settings
} from 'lucide-react';

// Using Collection interface from API types

interface CollectionStats {
  total_collections: number;
  active_collections: number;
  draft_collections: number;
  synced_collections: number;
  total_products_in_collections: number;
  custom_collections?: number;
  smart_collections?: number;
}

export function CollectionsDashboard() {
  const [activeTab, setActiveTab] = useState<'overview' | 'manage' | 'shopify' | 'product-types' | 'icons'>('overview');
  const [collections, setCollections] = useState<Collection[]>([]);
  const [stats, setStats] = useState<CollectionStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [newCollection, setNewCollection] = useState({
    name: '',
    handle: '',
    description: '',
    rules_type: 'manual' as 'manual' | 'automatic'
  });

  useEffect(() => {
    loadCollections();
    loadStats();
  }, []);

  const loadCollections = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getCollections();
      // Ensure status has a default value if undefined
      const collectionsWithStatus = response.collections.map(collection => ({
        ...collection,
        status: collection.status || 'draft' as const
      }));
      setCollections(collectionsWithStatus);
    } catch (error: any) {
      console.error('Error loading collections:', error);
      setError(error.response?.data?.message || 'Failed to load collections');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await apiClient.get('/dashboard/collections/summary');
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch collection stats:', error);
    }
  };

  const loadStatsOld = async () => {
    try {
      // Calculate stats from collections data
      const stats: CollectionStats = {
        total_collections: collections.length,
        active_collections: collections.filter(c => c.status === 'active').length,
        draft_collections: collections.filter(c => c.status === 'draft').length,
        synced_collections: collections.filter(c => c.shopify_collection_id).length,
        total_products_in_collections: collections.reduce((sum, c) => sum + (c.products_count || c.product_count || 0), 0)
      };
      setStats(stats);
    } catch (error) {
      console.error('Error calculating stats:', error);
    }
  };

  const createCollection = async () => {
    try {
      if (!newCollection.name || !newCollection.handle) {
        alert('Please provide a collection name and handle');
        return;
      }

      const response = await apiClient.createCollection(newCollection);
      
      if (response.collection) {
        const collectionWithStatus = {
          ...response.collection,
          status: response.collection.status || 'draft' as const
        };
        setCollections(prev => [...prev, collectionWithStatus]);
        setIsCreateDialogOpen(false);
        setNewCollection({
          name: '',
          handle: '',
          description: '',
          rules_type: 'manual'
        });
        loadStats();
      }
    } catch (error: any) {
      console.error('Error creating collection:', error);
      alert(error.response?.data?.message || 'Failed to create collection');
    }
  };

  const syncCollectionToShopify = async (collectionId: number) => {
    try {
      await apiClient.syncCollectionToShopify(collectionId);
      await loadCollections();
    } catch (error: any) {
      console.error('Error syncing collection:', error);
      alert(error.response?.data?.message || 'Failed to sync collection');
    }
  };

  const filteredCollections = collections.filter(c => {
    const matchesSearch = c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         c.handle.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         c.description?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = selectedStatus === 'all' || c.status === selectedStatus;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge variant="default" className="bg-green-100 text-green-800">Active</Badge>;
      case 'draft':
        return <Badge variant="outline">Draft</Badge>;
      case 'archived':
        return <Badge variant="secondary">Archived</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getSyncStatusBadge = (collection: Collection) => {
    if (collection.shopify_collection_id) {
      if (collection.shopify_sync_status === 'synced') {
        return <Badge variant="default" className="bg-purple-100 text-purple-800">Synced</Badge>;
      } else {
        return <Badge variant="outline" className="bg-yellow-100 text-yellow-800">Pending Sync</Badge>;
      }
    }
    return <Badge variant="outline">Not Synced</Badge>;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Collections</h2>
          <p className="text-muted-foreground">
            Organize products into collections for better navigation and merchandising
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={loadCollections}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
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
                  Create a new collection to organize your products
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="collection-name">Collection Name</Label>
                  <Input
                    id="collection-name"
                    value={newCollection.name}
                    onChange={(e) => setNewCollection(prev => ({ 
                      ...prev, 
                      name: e.target.value,
                      handle: e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-')
                    }))}
                    placeholder="e.g., Summer Collection"
                  />
                </div>
                <div>
                  <Label htmlFor="collection-handle">Handle</Label>
                  <Input
                    id="collection-handle"
                    value={newCollection.handle}
                    onChange={(e) => setNewCollection(prev => ({ ...prev, handle: e.target.value }))}
                    placeholder="e.g., summer-collection"
                  />
                </div>
                <div>
                  <Label htmlFor="collection-description">Description</Label>
                  <Input
                    id="collection-description"
                    value={newCollection.description}
                    onChange={(e) => setNewCollection(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Describe this collection..."
                  />
                </div>
                <div>
                  <Label>Collection Type</Label>
                  <div className="flex items-center gap-4 mt-2">
                    <label className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="rules_type"
                        value="manual"
                        checked={newCollection.rules_type === 'manual'}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewCollection(prev => ({ ...prev, rules_type: 'manual' }))}
                      />
                      <span>Manual</span>
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="rules_type"
                        value="automatic"
                        checked={newCollection.rules_type === 'automatic'}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewCollection(prev => ({ ...prev, rules_type: 'automatic' }))}
                      />
                      <span>Automatic</span>
                    </label>
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={createCollection}>
                  Create Collection
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">
            <BarChart className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="manage">
            <Grid className="h-4 w-4 mr-2" />
            Manage Collections
          </TabsTrigger>
          <TabsTrigger value="icons">
            <Brain className="h-4 w-4 mr-2" />
            Icon Manager
          </TabsTrigger>
          <TabsTrigger value="shopify">
            <Store className="h-4 w-4 mr-2" />
            Shopify Sync
          </TabsTrigger>
          <TabsTrigger value="product-types">
            <Package className="h-4 w-4 mr-2" />
            Product Types
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Stats Cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Collections</CardTitle>
                <Layers className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {loading ? '...' : (stats?.total_collections || 0)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {stats?.custom_collections || 0} custom, {stats?.smart_collections || 0} smart
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Active Collections</CardTitle>
                <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {loading ? '...' : (stats?.active_collections || 0)}
                </div>
                <p className="text-xs text-muted-foreground">
                  Available to customers
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Synced to Shopify</CardTitle>
                <Store className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {loading ? '...' : (stats?.synced_collections || 0)}
                </div>
                <p className="text-xs text-muted-foreground">
                  Live on your store
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Products</CardTitle>
                <Package className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {loading ? '...' : (stats?.total_products_in_collections || 0).toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">
                  In categorized collections
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Recent Collections */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Collections</CardTitle>
              <CardDescription>
                Your most recently created or updated collections
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-20 w-full" />
                  ))}
                </div>
              ) : collections.slice(0, 5).map((collection) => (
                <div
                  key={collection.id}
                  className="flex items-center justify-between p-3 border-b last:border-0"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium">{collection.name}</h4>
                      {getStatusBadge(collection.status)}
                      {getSyncStatusBadge(collection)}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {collection.products_count || collection.product_count || 0} products • {collection.rules_type} collection
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" asChild>
                      <a href={`/collections/${collection.id}`}>
                        <Eye className="h-3 w-3 mr-1" />
                        View
                      </a>
                    </Button>
                    {collection.shopify_collection_id && (
                      <Button size="sm" variant="outline" asChild>
                        <a 
                          href={`https://e19833-4.myshopify.com/admin/collections/${collection.shopify_collection_id}`} 
                          target="_blank" 
                          rel="noopener noreferrer"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Manage Collections Tab */}
        <TabsContent value="manage" className="space-y-4">
          {/* Search and Filters */}
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search collections..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex items-center gap-2">
              <select
                value={selectedStatus}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedStatus(e.target.value)}
                className="px-3 py-2 border rounded-md"
              >
                <option value="all">All Status</option>
                <option value="active">Active</option>
                <option value="draft">Draft</option>
                <option value="archived">Archived</option>
              </select>
            </div>
          </div>

          {/* Collections Grid */}
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
            ) : filteredCollections.length === 0 ? (
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
                          {getSyncStatusBadge(collection)}
                          <Badge variant="outline" className="text-xs">
                            {collection.rules_type === 'automatic' ? 'Automatic' : 'Manual'}
                          </Badge>
                        </div>
                        
                        <p className="text-sm text-muted-foreground mb-3">{collection.description}</p>
                        
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground">Handle:</span>
                            <span className="ml-1 font-mono text-xs">{collection.handle}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Products:</span>
                            <span className="ml-1 font-medium">{collection.products_count || collection.product_count || 0}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Created:</span>
                            <span className="ml-1">{collection.created_at ? new Date(collection.created_at).toLocaleDateString() : 'Unknown'}</span>
                          </div>
                          {collection.shopify_synced_at && (
                            <div>
                              <span className="text-muted-foreground">Synced:</span>
                              <span className="ml-1">{new Date(collection.shopify_synced_at).toLocaleDateString()}</span>
                            </div>
                          )}
                        </div>

                        {collection.rules_type === 'automatic' && collection.rules_conditions && (
                          <div className="mt-3 p-2 bg-gray-50 rounded">
                            <p className="text-xs font-medium mb-1">Automatic Rules:</p>
                            <p className="text-xs text-muted-foreground">
                              {collection.rules_conditions.length} condition(s) • 
                              {collection.disjunctive ? ' Match ANY' : ' Match ALL'}
                            </p>
                          </div>
                        )}
                      </div>
                      
                      <div className="flex flex-col gap-2 ml-4">
                        <Button size="sm" variant="outline" asChild>
                          <a href={`/collections/${collection.id}`}>
                            <Eye className="h-3 w-3 mr-1" />
                            View
                          </a>
                        </Button>
                        <Button size="sm" variant="outline">
                          <Edit className="h-3 w-3 mr-1" />
                          Edit
                        </Button>
                        {!collection.shopify_collection_id && (
                          <Button
                            size="sm"
                            onClick={() => syncCollectionToShopify(collection.id)}
                          >
                            <Upload className="h-3 w-3 mr-1" />
                            Sync
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

        {/* Icon Manager Tab */}
        <TabsContent value="icons">
          <CollectionIconManager />
        </TabsContent>

        {/* Shopify Sync Tab */}
        <TabsContent value="shopify">
          <ShopifyCollectionManager />
        </TabsContent>

        {/* Product Types Tab */}
        <TabsContent value="product-types">
          <ProductTypeCollectionManager />
        </TabsContent>
      </Tabs>
    </div>
  );
}