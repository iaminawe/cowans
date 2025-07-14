import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { 
  Download,
  Upload,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Database,
  FileText,
  Server,
  Truck,
  Settings,
  Activity,
  GitCompare,
  GitCommit,
  ChevronRight
} from 'lucide-react';
import { ShopifySyncDown } from './ShopifySyncDown';
import { StagedChangesReview } from './StagedChangesReview';
import { ShopifySyncUp } from './ShopifySyncUp';
import { EtilizeSyncTool } from './EtilizeSyncTool';
import { XorosoftSync } from './XorosoftSync';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { apiClient } from '@/lib/api';

interface EnhancedSyncDashboardProps {
  className?: string;
}

interface SyncStatus {
  shopifyDown: 'idle' | 'running' | 'completed' | 'error';
  shopifyUp: 'idle' | 'running' | 'completed' | 'error';
  etilize: 'idle' | 'running' | 'completed' | 'error';
  xorosoft: 'idle' | 'running' | 'completed' | 'error';
}

interface SyncMetrics {
  productsToSync: number;
  productsWithChanges: number;
  stagedChanges: number;
  approvedChanges: number;
  lastSyncTime?: string;
  nextScheduledSync?: string;
}

export function EnhancedSyncDashboard({ className }: EnhancedSyncDashboardProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'shopify-down' | 'staged-changes' | 'shopify-up' | 'etilize' | 'xorosoft'>('overview');
  const [syncStatus, setSyncStatus] = useState<SyncStatus>({
    shopifyDown: 'idle',
    shopifyUp: 'idle',
    etilize: 'idle',
    xorosoft: 'idle'
  });
  const [syncMetrics, setSyncMetrics] = useState<SyncMetrics>({
    productsToSync: 0,
    productsWithChanges: 0,
    stagedChanges: 0,
    approvedChanges: 0
  });
  const [recentActivity, setRecentActivity] = useState<any[]>([]);
  const { subscribeCustom, isConnected } = useWebSocket();

  useEffect(() => {
    loadSyncMetrics();
    loadRecentActivity();
  }, []);

  useEffect(() => {
    if (!isConnected) return;

    const unsubscribeSyncUpdate = subscribeCustom('sync-update', (data) => {
      // Type assertion for custom sync-update event data
      const syncData = data as { source?: keyof SyncStatus; status?: SyncStatus[keyof SyncStatus] };
      if (syncData.source && syncData.status) {
        setSyncStatus(prev => ({
          ...prev,
          [syncData.source as keyof SyncStatus]: syncData.status as SyncStatus[keyof SyncStatus]
        }));
      }
    });

    const unsubscribeMetricsUpdate = subscribeCustom('metrics-update', (data) => {
      // Type assertion for custom metrics-update event data
      const metricsData = data as Partial<SyncMetrics>;
      setSyncMetrics(prev => ({
        ...prev,
        ...metricsData
      }));
    });

    return () => {
      unsubscribeSyncUpdate();
      unsubscribeMetricsUpdate();
    };
  }, [subscribeCustom, isConnected]);

  const loadSyncMetrics = async () => {
    try {
      const metrics = await apiClient.getSyncMetrics();
      setSyncMetrics(metrics);
    } catch (error) {
      console.error('Failed to load sync metrics:', error);
    }
  };

  const loadRecentActivity = async () => {
    try {
      const activity = await apiClient.getRecentSyncActivity();
      setRecentActivity(activity);
    } catch (error) {
      console.error('Failed to load recent activity:', error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'idle':
        return <Clock className="h-4 w-4 text-gray-500" />;
      case 'running':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      idle: 'secondary',
      running: 'default',
      completed: 'outline',
      error: 'destructive'
    };
    return <Badge variant={variants[status] || 'secondary'}>{status}</Badge>;
  };

  return (
    <div className={cn("space-y-6", className)}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Enhanced Sync Management</h2>
          <p className="text-muted-foreground">
            Manage product synchronization across all platforms with change detection and staging
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-2 h-2 rounded-full",
            isConnected ? "bg-green-500" : "bg-red-500"
          )} />
          <span className="text-xs text-muted-foreground">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="shopify-down" className="flex items-center gap-2">
            <Download className="h-4 w-4" />
            Shopify Down
          </TabsTrigger>
          <TabsTrigger value="staged-changes" className="flex items-center gap-2">
            <GitCompare className="h-4 w-4" />
            Staged Changes
          </TabsTrigger>
          <TabsTrigger value="shopify-up" className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            Shopify Up
          </TabsTrigger>
          <TabsTrigger value="etilize" className="flex items-center gap-2">
            <Database className="h-4 w-4" />
            Etilize
          </TabsTrigger>
          <TabsTrigger value="xorosoft" className="flex items-center gap-2">
            <Truck className="h-4 w-4" />
            Xorosoft
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Sync Status Cards */}
          <div className="grid grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Shopify Sync Down</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(syncStatus.shopifyDown)}
                    <span className="text-2xl font-bold">{syncMetrics.productsWithChanges}</span>
                  </div>
                  {getStatusBadge(syncStatus.shopifyDown)}
                </div>
                <p className="text-xs text-muted-foreground mt-2">Products with changes</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Staged Changes</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <GitCompare className="h-4 w-4 text-orange-500" />
                    <span className="text-2xl font-bold">{syncMetrics.stagedChanges}</span>
                  </div>
                  <Badge variant="outline">Review</Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-2">Awaiting approval</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Shopify Sync Up</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(syncStatus.shopifyUp)}
                    <span className="text-2xl font-bold">{syncMetrics.approvedChanges}</span>
                  </div>
                  {getStatusBadge(syncStatus.shopifyUp)}
                </div>
                <p className="text-xs text-muted-foreground mt-2">Approved for upload</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">External Sources</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Etilize</span>
                    {getStatusIcon(syncStatus.etilize)}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Xorosoft</span>
                    {getStatusIcon(syncStatus.xorosoft)}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Sync Workflow */}
          <Card>
            <CardHeader>
              <CardTitle>Sync Workflow</CardTitle>
              <CardDescription>
                Follow the enhanced sync process for accurate product management
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="flex flex-col items-center">
                  <Button
                    variant={activeTab === 'shopify-down' ? 'default' : 'outline'}
                    size="lg"
                    className="w-32"
                    onClick={() => setActiveTab('shopify-down')}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Pull Data
                  </Button>
                  <p className="text-xs text-muted-foreground mt-2">From Shopify</p>
                </div>
                
                <ChevronRight className="h-6 w-6 text-muted-foreground" />
                
                <div className="flex flex-col items-center">
                  <Button
                    variant={activeTab === 'staged-changes' ? 'default' : 'outline'}
                    size="lg"
                    className="w-32"
                    onClick={() => setActiveTab('staged-changes')}
                  >
                    <GitCompare className="h-4 w-4 mr-2" />
                    Review
                  </Button>
                  <p className="text-xs text-muted-foreground mt-2">Staged Changes</p>
                </div>
                
                <ChevronRight className="h-6 w-6 text-muted-foreground" />
                
                <div className="flex flex-col items-center">
                  <Button
                    variant={activeTab === 'shopify-up' ? 'default' : 'outline'}
                    size="lg"
                    className="w-32"
                    onClick={() => setActiveTab('shopify-up')}
                  >
                    <Upload className="h-4 w-4 mr-2" />
                    Push Data
                  </Button>
                  <p className="text-xs text-muted-foreground mt-2">To Shopify</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Recent Activity */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Sync Activity</CardTitle>
              <CardDescription>
                Latest synchronization operations across all platforms
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recentActivity.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No recent activity
                  </div>
                ) : (
                  recentActivity.map((activity, index) => (
                    <div key={index} className="flex items-center justify-between border-b pb-2 last:border-0">
                      <div className="flex items-center gap-3">
                        {activity.type === 'success' ? (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        ) : activity.type === 'error' ? (
                          <XCircle className="h-4 w-4 text-red-500" />
                        ) : (
                          <AlertTriangle className="h-4 w-4 text-yellow-500" />
                        )}
                        <div>
                          <p className="text-sm font-medium">{activity.message}</p>
                          <p className="text-xs text-muted-foreground">{activity.source}</p>
                        </div>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {new Date(activity.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Shopify Sync Down Tab */}
        <TabsContent value="shopify-down" className="space-y-6">
          <ShopifySyncDown 
            onSyncComplete={() => {
              loadSyncMetrics();
              setActiveTab('staged-changes');
            }}
          />
        </TabsContent>

        {/* Staged Changes Review Tab */}
        <TabsContent value="staged-changes" className="space-y-6">
          <StagedChangesReview 
            onChangesApproved={() => {
              loadSyncMetrics();
              setActiveTab('shopify-up');
            }}
          />
        </TabsContent>

        {/* Shopify Sync Up Tab */}
        <TabsContent value="shopify-up" className="space-y-6">
          <ShopifySyncUp 
            onSyncComplete={() => {
              loadSyncMetrics();
              setActiveTab('overview');
            }}
          />
        </TabsContent>

        {/* Etilize Sync Tab */}
        <TabsContent value="etilize" className="space-y-6">
          <EtilizeSyncTool />
        </TabsContent>

        {/* Xorosoft Sync Tab */}
        <TabsContent value="xorosoft" className="space-y-6">
          <XorosoftSync />
        </TabsContent>
      </Tabs>
    </div>
  );
}