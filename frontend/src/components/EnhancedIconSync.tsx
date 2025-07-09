import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { shopifyApi, BatchSyncRequest, BatchSyncResult, CollectionVerificationResult } from '@/lib/shopifyApi';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  RefreshCw, 
  Upload, 
  Zap, 
  CheckCircle2, 
  XCircle,
  AlertCircle,
  RotateCcw,
  BarChart,
  Search
} from 'lucide-react';

interface EnhancedIconSyncProps {
  className?: string;
}

interface RecentSync {
  icon_id: number;
  filename: string;
  category: string;
  synced_at: string;
  shopify_image_url: string;
}

export function EnhancedIconSync({ className }: EnhancedIconSyncProps) {
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncStatus, setSyncStatus] = useState<any>(null);
  const [verificationResults, setVerificationResults] = useState<CollectionVerificationResult[]>([]);
  const [batchProgress, setBatchProgress] = useState<number>(0);
  const [lastSyncResult, setLastSyncResult] = useState<BatchSyncResult | null>(null);

  useEffect(() => {
    loadSyncStatus();
  }, []);

  const loadSyncStatus = async () => {
    try {
      setLoading(true);
      const status = await shopifyApi.getSyncStatus();
      setSyncStatus(status);
    } catch (error: any) {
      console.error('Error loading sync status:', error);
      setError(error.response?.data?.message || 'Failed to load sync status');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCollections = async () => {
    try {
      setVerifying(true);
      setError(null);
      
      // Get all collections first
      const collectionsData = await shopifyApi.getCollections();
      const collectionIds = collectionsData.collections.map(c => c.graphql_id || c.id);
      
      // Verify images
      const verificationData = await shopifyApi.verifyCollectionImages(collectionIds);
      setVerificationResults(verificationData.results);
      
    } catch (error: any) {
      console.error('Error verifying collections:', error);
      setError(error.response?.data?.message || 'Failed to verify collections');
    } finally {
      setVerifying(false);
    }
  };

  const handleBatchSync = async () => {
    try {
      setSyncing(true);
      setError(null);
      setBatchProgress(0);
      
      // Get collections without images
      const collectionsToSync = verificationResults.filter(r => !r.has_image && !r.error);
      
      if (collectionsToSync.length === 0) {
        setError('No collections need icon sync');
        return;
      }
      
      // TODO: This would need to be connected to your icon selection logic
      // For now, we'll show a placeholder
      setError('Please implement icon selection logic for batch sync');
      
      // Example of how batch sync would work:
      /*
      const mappings: BatchSyncRequest['mappings'] = collectionsToSync.map(collection => ({
        icon_id: getIconForCollection(collection.collection_id), // Need to implement
        collection_id: collection.collection_id,
        alt_text: collection.title ? `${collection.title} icon` : undefined
      }));
      
      const result = await shopifyApi.syncIconsBatch(mappings);
      setLastSyncResult(result);
      
      // Refresh status
      await loadSyncStatus();
      */
      
    } catch (error: any) {
      console.error('Error in batch sync:', error);
      setError(error.response?.data?.message || 'Failed to sync icons');
    } finally {
      setSyncing(false);
    }
  };

  const handleRetryFailed = async () => {
    try {
      setRetrying(true);
      setError(null);
      
      const result = await shopifyApi.retryFailedSyncs();
      
      if (result.success) {
        await loadSyncStatus();
        setError(null);
      } else {
        setError(result.message || 'Failed to retry syncs');
      }
      
    } catch (error: any) {
      console.error('Error retrying failed syncs:', error);
      setError(error.response?.data?.message || 'Failed to retry syncs');
    } finally {
      setRetrying(false);
    }
  };

  const stats = syncStatus?.statistics;
  const recentSyncs: RecentSync[] = syncStatus?.recent_syncs || [];

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5" />
              Enhanced Icon Sync
            </CardTitle>
            <CardDescription>
              Advanced batch synchronization with retry support
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadSyncStatus}
              disabled={loading}
            >
              <RefreshCw className={cn("h-4 w-4 mr-2", loading && "animate-spin")} />
              Refresh
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Statistics Overview */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
              <div className="text-2xl font-bold">{stats.total_icons}</div>
              <div className="text-sm text-muted-foreground">Total Icons</div>
            </div>
            <div className="text-center p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
              <div className="text-2xl font-bold text-green-600">{stats.synced_icons}</div>
              <div className="text-sm text-muted-foreground">Synced</div>
            </div>
            <div className="text-center p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
              <div className="text-2xl font-bold text-orange-600">{stats.unsynced_icons}</div>
              <div className="text-sm text-muted-foreground">Unsynced</div>
            </div>
            <div className="text-center p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
              <div className="text-2xl font-bold text-red-600">{stats.failed_syncs}</div>
              <div className="text-sm text-muted-foreground">Failed</div>
            </div>
          </div>
        )}

        {/* Sync Progress */}
        {stats && stats.total_icons > 0 && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Sync Progress</span>
              <span>{stats.sync_percentage.toFixed(1)}%</span>
            </div>
            <Progress value={stats.sync_percentage} className="h-2" />
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-3">
          <Button 
            onClick={handleVerifyCollections}
            disabled={verifying}
            variant="outline"
            className="flex items-center gap-2"
          >
            {verifying ? (
              <>
                <Search className="h-4 w-4 animate-pulse" />
                Verifying...
              </>
            ) : (
              <>
                <Search className="h-4 w-4" />
                Verify Collections
              </>
            )}
          </Button>

          <Button 
            onClick={handleBatchSync}
            disabled={syncing || verificationResults.length === 0}
            className="flex items-center gap-2"
          >
            {syncing ? (
              <>
                <Upload className="h-4 w-4 animate-pulse" />
                Syncing...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                Batch Sync
              </>
            )}
          </Button>

          {stats && stats.failed_syncs > 0 && (
            <Button 
              onClick={handleRetryFailed}
              disabled={retrying}
              variant="destructive"
              className="flex items-center gap-2"
            >
              {retrying ? (
                <>
                  <RotateCcw className="h-4 w-4 animate-spin" />
                  Retrying...
                </>
              ) : (
                <>
                  <RotateCcw className="h-4 w-4" />
                  Retry Failed ({stats.failed_syncs})
                </>
              )}
            </Button>
          )}
        </div>

        {/* Verification Results */}
        {verificationResults.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium">Verification Results</h4>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 rounded bg-green-100 dark:bg-green-900/20">
                <div className="text-lg font-bold text-green-600">
                  {verificationResults.filter(r => r.has_image).length}
                </div>
                <div className="text-xs text-muted-foreground">With Images</div>
              </div>
              <div className="p-3 rounded bg-orange-100 dark:bg-orange-900/20">
                <div className="text-lg font-bold text-orange-600">
                  {verificationResults.filter(r => !r.has_image && !r.error).length}
                </div>
                <div className="text-xs text-muted-foreground">Need Images</div>
              </div>
              <div className="p-3 rounded bg-red-100 dark:bg-red-900/20">
                <div className="text-lg font-bold text-red-600">
                  {verificationResults.filter(r => r.error).length}
                </div>
                <div className="text-xs text-muted-foreground">Errors</div>
              </div>
            </div>
          </div>
        )}

        {/* Recent Syncs */}
        {recentSyncs.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium">Recent Syncs</h4>
            <ScrollArea className="h-48">
              <div className="space-y-2">
                {recentSyncs.map((sync) => (
                  <div key={sync.icon_id} className="flex items-center justify-between p-2 rounded border">
                    <div className="flex-1">
                      <div className="font-medium text-sm">{sync.filename}</div>
                      <div className="text-xs text-muted-foreground">
                        {sync.category} • {new Date(sync.synced_at).toLocaleString()}
                      </div>
                    </div>
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}

        {/* Last Sync Result Summary */}
        {lastSyncResult && (
          <Alert>
            <BarChart className="h-4 w-4" />
            <AlertDescription>
              Last batch sync: {lastSyncResult.summary.successful_syncs} successful, 
              {lastSyncResult.summary.failed_syncs} failed 
              ({lastSyncResult.summary.success_rate.toFixed(1)}% success rate)
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}