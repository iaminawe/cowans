import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { apiClient } from '@/lib/api';
import { shopifyApi, ShopifyCollection } from '@/lib/shopifyApi';
import { IconSyncDialog } from './IconSyncDialog';
import { 
  Layers,
  Wand2,
  Upload,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Image,
  RefreshCw,
  Play,
  Pause,
  RotateCcw
} from 'lucide-react';

interface CollectionWithSelection extends ShopifyCollection {
  selected: boolean;
}

interface BatchOperation {
  id: string;
  type: 'generate' | 'sync';
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  collections: string[];
  startedAt: Date;
  completedAt?: Date;
  errors: string[];
}

export function CollectionIconManager() {
  const [collections, setCollections] = useState<CollectionWithSelection[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCollections, setSelectedCollections] = useState<Set<string>>(new Set());
  const [batchOperation, setBatchOperation] = useState<BatchOperation | null>(null);
  const [generationStyle, setGenerationStyle] = useState('modern');
  const [generationColor, setGenerationColor] = useState('#3B82F6');
  const [syncDialogOpen, setSyncDialogOpen] = useState(false);
  const [selectedCollectionForSync, setSelectedCollectionForSync] = useState<ShopifyCollection | null>(null);

  useEffect(() => {
    loadCollections();
  }, []);

  const loadCollections = async () => {
    try {
      setLoading(true);
      const data = await shopifyApi.getCollections();
      setCollections(data.collections.map(c => ({ ...c, selected: false })));
    } catch (error) {
      console.error('Error loading collections:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const allIds = collections.map(c => c.id);
      setSelectedCollections(new Set(allIds));
      setCollections(collections.map(c => ({ ...c, selected: true })));
    } else {
      setSelectedCollections(new Set());
      setCollections(collections.map(c => ({ ...c, selected: false })));
    }
  };

  const handleSelectCollection = (collectionId: string, checked: boolean) => {
    const newSelected = new Set(selectedCollections);
    if (checked) {
      newSelected.add(collectionId);
    } else {
      newSelected.delete(collectionId);
    }
    setSelectedCollections(newSelected);
    setCollections(collections.map(c => 
      c.id === collectionId ? { ...c, selected: checked } : c
    ));
  };

  const handleBatchGenerate = async () => {
    const selected = collections.filter(c => selectedCollections.has(c.id) && !c.has_icon);
    
    if (selected.length === 0) {
      alert('No collections without icons selected');
      return;
    }

    const batchOp: BatchOperation = {
      id: Date.now().toString(),
      type: 'generate',
      status: 'running',
      progress: 0,
      collections: selected.map(c => c.id),
      startedAt: new Date(),
      errors: []
    };

    setBatchOperation(batchOp);

    try {
      // Create batch generation request
      const response = await apiClient.post<{ batch_id?: string; message?: string }>('/generate/batch', {
        categories: selected.map(c => ({
          id: c.id,
          name: c.title
        })),
        style: generationStyle,
        color: generationColor,
        use_ai: true
      });

      if (response.batch_id) {
        // Monitor batch progress
        monitorBatchProgress(response.batch_id, batchOp);
      }
    } catch (error: any) {
      batchOp.status = 'failed';
      batchOp.errors.push(error.message || 'Failed to start batch generation');
      setBatchOperation({ ...batchOp });
    }
  };

  const handleBatchSync = async () => {
    const selected = collections.filter(c => selectedCollections.has(c.id) && c.has_icon);
    
    if (selected.length === 0) {
      alert('No collections with icons selected');
      return;
    }

    const batchOp: BatchOperation = {
      id: Date.now().toString(),
      type: 'sync',
      status: 'running',
      progress: 0,
      collections: selected.map(c => c.id),
      startedAt: new Date(),
      errors: []
    };

    setBatchOperation(batchOp);

    try {
      // Prepare batch sync mappings
      const mappings = selected.map(c => ({
        icon_id: parseInt(c.id), // This should be the actual icon ID
        collection_id: c.graphql_id,
        alt_text: `${c.title} collection icon`
      }));

      const response = await shopifyApi.syncIconsBatch(mappings);
      
      if (response.success) {
        batchOp.status = 'completed';
        batchOp.progress = 100;
        batchOp.completedAt = new Date();
        setBatchOperation({ ...batchOp });
        
        // Reload collections to update status
        await loadCollections();
      } else {
        batchOp.status = 'failed';
        batchOp.errors = response.results
          .filter(r => r.status === 'failed')
          .map(r => r.error || 'Unknown error');
        setBatchOperation({ ...batchOp });
      }
    } catch (error: any) {
      batchOp.status = 'failed';
      batchOp.errors.push(error.message || 'Failed to sync icons');
      setBatchOperation({ ...batchOp });
    }
  };

  const monitorBatchProgress = async (batchId: string, operation: BatchOperation) => {
    const checkProgress = async () => {
      try {
        const response = await apiClient.get<{
          progress: number;
          status: string;
          error?: string;
        }>(`/batch/${batchId}/status`);
        
        operation.progress = response.progress;
        setBatchOperation({ ...operation });

        if (response.status === 'completed') {
          operation.status = 'completed';
          operation.completedAt = new Date();
          setBatchOperation({ ...operation });
          await loadCollections();
        } else if (response.status === 'failed') {
          operation.status = 'failed';
          operation.errors.push(response.error || 'Batch operation failed');
          setBatchOperation({ ...operation });
        } else {
          // Continue monitoring
          setTimeout(() => checkProgress(), 2000);
        }
      } catch (error) {
        operation.status = 'failed';
        operation.errors.push('Failed to check progress');
        setBatchOperation({ ...operation });
      }
    };

    checkProgress();
  };

  const collectionsWithoutIcons = collections.filter(c => !c.has_icon);
  const collectionsWithIcons = collections.filter(c => c.has_icon);
  const selectedCount = selectedCollections.size;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Collection Icon Manager</h3>
          <p className="text-sm text-muted-foreground">
            Batch generate and sync icons for multiple collections
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={loadCollections}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{collections.length}</div>
            <p className="text-xs text-muted-foreground">Total Collections</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-green-600">{collectionsWithIcons.length}</div>
            <p className="text-xs text-muted-foreground">With Icons</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-yellow-600">{collectionsWithoutIcons.length}</div>
            <p className="text-xs text-muted-foreground">Need Icons</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-blue-600">{selectedCount}</div>
            <p className="text-xs text-muted-foreground">Selected</p>
          </CardContent>
        </Card>
      </div>

      {/* Batch Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Batch Actions</CardTitle>
          <CardDescription>
            Select collections and perform batch operations
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Generation Options */}
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="text-sm font-medium">Style</label>
              <Select value={generationStyle} onValueChange={setGenerationStyle}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="modern">Modern</SelectItem>
                  <SelectItem value="classic">Classic</SelectItem>
                  <SelectItem value="minimalist">Minimalist</SelectItem>
                  <SelectItem value="detailed">Detailed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex-1">
              <label className="text-sm font-medium">Color</label>
              <input
                type="color"
                value={generationColor}
                onChange={(e) => setGenerationColor(e.target.value)}
                className="w-full h-10 rounded border"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            <Button
              onClick={handleBatchGenerate}
              disabled={selectedCount === 0 || batchOperation?.status === 'running'}
            >
              <Wand2 className="h-4 w-4 mr-2" />
              Generate Icons ({selectedCollections.size})
            </Button>
            <Button
              variant="outline"
              onClick={handleBatchSync}
              disabled={selectedCount === 0 || batchOperation?.status === 'running'}
            >
              <Upload className="h-4 w-4 mr-2" />
              Sync to Shopify ({selectedCollections.size})
            </Button>
          </div>

          {/* Progress Display */}
          {batchOperation && (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span>
                      {batchOperation.type === 'generate' ? 'Generating' : 'Syncing'} icons...
                    </span>
                    <Badge variant={
                      batchOperation.status === 'completed' ? 'default' :
                      batchOperation.status === 'failed' ? 'destructive' :
                      'secondary'
                    }>
                      {batchOperation.status}
                    </Badge>
                  </div>
                  <Progress value={batchOperation.progress} />
                  <div className="text-xs text-muted-foreground">
                    {batchOperation.progress}% complete • {batchOperation.collections.length} collections
                  </div>
                  {batchOperation.errors.length > 0 && (
                    <div className="text-xs text-red-600">
                      Errors: {batchOperation.errors.join(', ')}
                    </div>
                  )}
                </div>
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Collections List */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Collections</CardTitle>
            <div className="flex items-center gap-2">
              <Checkbox
                checked={selectedCount === collections.length && collections.length > 0}
                onCheckedChange={handleSelectAll}
              />
              <span className="text-sm">Select All</span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {loading ? (
              <div className="text-center py-8 text-muted-foreground">
                Loading collections...
              </div>
            ) : collections.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No collections found
              </div>
            ) : (
              collections.map((collection) => (
                <div
                  key={collection.id}
                  className="flex items-center gap-4 p-3 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  <Checkbox
                    checked={collection.selected}
                    onCheckedChange={(checked) => 
                      handleSelectCollection(collection.id, checked as boolean)
                    }
                  />
                  
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{collection.title}</span>
                      {collection.has_icon ? (
                        <Badge variant="secondary" className="text-xs">
                          <CheckCircle2 className="h-3 w-3 mr-1" />
                          Has Icon
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs">
                          <Image className="h-3 w-3 mr-1" />
                          No Icon
                        </Badge>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {collection.handle} • {collection.products_count} products
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {!collection.has_icon && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setSelectedCollections(new Set([collection.id]));
                          handleBatchGenerate();
                        }}
                      >
                        <Wand2 className="h-3 w-3" />
                      </Button>
                    )}
                    {collection.has_icon && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setSelectedCollectionForSync(collection);
                          setSyncDialogOpen(true);
                        }}
                      >
                        <Upload className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Sync Dialog */}
      {selectedCollectionForSync && (
        <IconSyncDialog
          open={syncDialogOpen}
          onOpenChange={setSyncDialogOpen}
          collectionId={selectedCollectionForSync.id}
          collectionName={selectedCollectionForSync.title}
          onSync={async (collectionId, iconId) => {
            await handleSyncIcon(parseInt(iconId), selectedCollectionForSync.graphql_id);
          }}
        />
      )}
    </div>
  );
}

async function handleSyncIcon(iconId: number, collectionId: string) {
  const result = await shopifyApi.syncIconEnhanced(iconId, collectionId);
  if (result.status !== 'success') {
    throw new Error(result.error || 'Sync failed');
  }
}