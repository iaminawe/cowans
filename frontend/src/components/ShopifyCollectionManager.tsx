import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { shopifyApi, ShopifyCollection } from '@/lib/shopifyApi';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { IconSyncDialog } from './IconSyncDialog';
import { 
  RefreshCw, 
  Upload, 
  Zap, 
  Image, 
  CheckCircle2, 
  XCircle,
  AlertCircle,
  ExternalLink,
  Download
} from 'lucide-react';

interface ShopifyCollectionManagerProps {
  onGenerateIcon?: (collection: ShopifyCollection) => void;
  onSyncIcon?: (collectionId: string, iconPath: string) => void;
  className?: string;
}

export function ShopifyCollectionManager({ 
  onGenerateIcon,
  onSyncIcon,
  className 
}: ShopifyCollectionManagerProps) {
  const [collections, setCollections] = useState<ShopifyCollection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [shopifyConnected, setShopifyConnected] = useState(false);
  const [syncDialogOpen, setSyncDialogOpen] = useState(false);
  const [selectedCollection, setSelectedCollection] = useState<ShopifyCollection | null>(null);

  useEffect(() => {
    loadCollections();
    checkShopifyConnection();
  }, []);

  const checkShopifyConnection = async () => {
    try {
      const status = await shopifyApi.checkStatus();
      setShopifyConnected(status.connected);
    } catch (error) {
      setShopifyConnected(false);
    }
  };

  const loadCollections = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await shopifyApi.getCollections();
      setCollections(data.collections);
    } catch (error: any) {
      console.error('Error loading collections:', error);
      setError(error.response?.data?.message || 'Failed to load collections');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadCollections();
    setRefreshing(false);
  };

  const handleGenerateAllIcons = async () => {
    try {
      const result = await shopifyApi.generateAllIcons({
        options: {
          only_missing: true,
          style: 'modern',
          color: '#3B82F6'
        }
      });
      
      // Handle job creation response
      if ('job_id' in result && result.job_id) {
        // You might want to integrate with your job tracking system here
        console.log('Job created:', result.job_id);
      }
    } catch (error: any) {
      console.error('Error generating icons:', error);
      setError(error.response?.data?.message || 'Failed to start icon generation');
    }
  };

  const handleSyncIcon = async (collectionId: string, localIconId: string) => {
    try {
      setSyncing(collectionId);
      
      // Use enhanced sync with retry support
      const result = await shopifyApi.syncIconEnhanced(
        parseInt(localIconId),
        collectionId
      );
      
      if (result.status === 'success') {
        // Refresh collections to show updated state
        await loadCollections();
        
        // Show success message if available
        if (result.shopify_image_url) {
          console.log('Icon synced successfully:', result.shopify_image_url);
        }
      } else if (result.error) {
        setError(`Sync failed: ${result.error}`);
      }
    } catch (error: any) {
      console.error('Error syncing icon:', error);
      setError(error.response?.data?.message || 'Failed to sync icon');
    } finally {
      setSyncing(null);
    }
  };

  const collectionsWithoutIcons = collections?.filter(c => !c.has_icon) || [];
  const collectionsWithIcons = collections?.filter(c => c.has_icon) || [];

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-64 mt-2" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Shopify Collections
            </CardTitle>
            <CardDescription>
              Manage collection icons directly in Shopify
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {shopifyConnected ? (
              <Badge variant="secondary" className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" />
                Connected
              </Badge>
            ) : (
              <Badge variant="destructive" className="flex items-center gap-1">
                <XCircle className="h-3 w-3" />
                Disconnected
              </Badge>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw className={cn("h-4 w-4 mr-2", refreshing && "animate-spin")} />
              Refresh
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Summary Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
            <div className="text-2xl font-bold text-primary">{collections?.length || 0}</div>
            <div className="text-sm text-muted-foreground">Total Collections</div>
          </div>
          <div className="text-center p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
            <div className="text-2xl font-bold text-green-600">{collectionsWithIcons.length}</div>
            <div className="text-sm text-muted-foreground">With Icons</div>
          </div>
          <div className="text-center p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
            <div className="text-2xl font-bold text-orange-600">{collectionsWithoutIcons.length}</div>
            <div className="text-sm text-muted-foreground">Need Icons</div>
          </div>
        </div>

        {/* Bulk Actions */}
        {collectionsWithoutIcons.length > 0 && (
          <div className="flex items-center justify-between p-4 rounded-lg border bg-gray-100 dark:bg-gray-800">
            <div>
              <div className="font-medium">Generate Missing Icons</div>
              <div className="text-sm text-muted-foreground">
                {collectionsWithoutIcons.length} collections need icons
              </div>
            </div>
            <Button onClick={handleGenerateAllIcons} className="flex items-center gap-2">
              <Zap className="h-4 w-4" />
              Generate All
            </Button>
          </div>
        )}

        {/* Collections List */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-muted-foreground">Collections</h4>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {collections?.map((collection) => (
              <div
                key={collection.id}
                className="flex items-center gap-3 p-3 rounded-lg border hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              >
                {collection.image_url ? (
                  <img
                    src={collection.image_url}
                    alt={collection.title}
                    className="w-12 h-12 rounded object-cover border"
                  />
                ) : (
                  <div className="w-12 h-12 rounded border bg-muted flex items-center justify-center">
                    <Image className="h-6 w-6 text-muted-foreground" />
                  </div>
                )}
                
                <div className="flex-1">
                  <div className="font-medium">{collection.title}</div>
                  <div className="text-sm text-muted-foreground">
                    {collection.products_count} products
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {collection.has_icon ? (
                    <Badge variant="secondary" className="text-xs">
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      Has Icon
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-xs">
                      No Icon
                    </Badge>
                  )}
                  
                  {!collection.has_icon && onGenerateIcon && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onGenerateIcon(collection)}
                    >
                      <Zap className="h-3 w-3 mr-1" />
                      Generate
                    </Button>
                  )}
                  
                  {syncing === collection.id ? (
                    <Button size="sm" variant="outline" disabled>
                      <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                      Syncing...
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedCollection(collection);
                        setSyncDialogOpen(true);
                      }}
                    >
                      <Upload className="h-3 w-3 mr-1" />
                      Upload
                    </Button>
                  )}
                  
                  <a
                    href={`https://admin.shopify.com/store/collections/${collection.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
      
      {/* Icon Sync Dialog */}
      {selectedCollection && (
        <IconSyncDialog
          open={syncDialogOpen}
          onOpenChange={setSyncDialogOpen}
          collectionId={selectedCollection.id}
          collectionName={selectedCollection.title}
          onSync={handleSyncIcon}
        />
      )}
    </Card>
  );
}