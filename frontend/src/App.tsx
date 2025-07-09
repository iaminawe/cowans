import React, { useState, useEffect } from 'react';
import { DashboardLayout, DashboardSection, DashboardGrid, DashboardCard } from './components/DashboardLayout';
import { SyncTrigger } from './components/SyncTrigger';
import { LogViewer } from './components/LogViewer';
import { AuthPage } from './components/AuthPage';
import { ProtectedRoute } from './components/ProtectedRoute';
import { ScriptExecutor } from './components/ScriptExecutor';
import { RealtimeLogViewer } from './components/RealtimeLogViewer';
import { ProgressTracker } from './components/ProgressTracker';
import { SwarmExecutionDashboard } from './components/SwarmExecutionDashboard';
import { ImportManager } from './components/ImportManager';
import { ShopifySyncManager } from './components/ShopifySyncManager';
import { OperationStatus } from './components/OperationStatus';
import { BatchProcessor } from './components/BatchProcessor';
import { CollectionsDashboard } from './components/CollectionsDashboard';
import { ProductsDashboard as ProductsDashboardEnhanced } from './components/ProductsDashboardEnhanced';
import { NavigationTabs } from './components/NavigationTabs';
import { WebSocketProvider, useWebSocket } from './contexts/WebSocketContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { NotificationProvider } from './components/NotificationSystem';
import { apiClient, type SyncHistoryItem } from './lib/api';
import { cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { RotateCcw, Code2, FileText, LogOut, Image, Upload, Store, User, Activity, Zap, Layers, Package, Settings, FolderTree, Users, Shield } from 'lucide-react';
import { CategoryManagementPanel } from './components/CategoryManagementPanel';
import { AdminDashboard } from './components/AdminDashboard';
import { IconGenerationDashboard } from './components/IconGenerationDashboard';
import { EnhancedSyncDashboard } from './components/EnhancedSyncDashboard';
import { ProductAnalyticsLive } from './components/ProductAnalyticsLive';

function AppContent() {
  const [logs, setLogs] = useState<SyncHistoryItem[]>([]);
  const [syncLoading, setSyncLoading] = useState(false);
  const [activeView, setActiveView] = useState<'sync' | 'scripts' | 'logs' | 'products' | 'analytics' | 'collections' | 'categories' | 'icons' | 'admin'>('sync');
  const [realtimeLogs, setRealtimeLogs] = useState<any[]>([]);
  const [scriptProgress, setScriptProgress] = useState<any[]>([]);
  const [currentScript, setCurrentScript] = useState<string | null>(null);
  const { subscribe, sendMessage, isConnected } = useWebSocket();
  const { isAuthenticated, user, logout } = useAuth();

  useEffect(() => {
    if (isAuthenticated) {
      loadSyncHistory();
    }
  }, [isAuthenticated]);

  // Subscribe to WebSocket events
  useEffect(() => {
    const unsubscribeLogs = subscribe('log', (data) => {
      setRealtimeLogs(prev => [...prev, {
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
        ...data
      }]);
    });

    const unsubscribeProgress = subscribe('progress', (data) => {
      setScriptProgress(data.stages || []);
    });

    return () => {
      unsubscribeLogs();
      unsubscribeProgress();
    };
  }, [subscribe]);

  const loadSyncHistory = async () => {
    try {
      const history = await apiClient.getSyncHistory();
      setLogs(history);
    } catch (error) {
      console.error('Failed to load sync history:', error);
    }
  };


  const handleSync = async () => {
    setSyncLoading(true);
    setCurrentScript('full_import');
    try {
      await apiClient.triggerSync();
      // Add optimistic update
      const newLog: SyncHistoryItem = {
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
        status: 'running',
        message: 'Sync in progress...'
      };
      setLogs(prev => [newLog, ...prev]);
      
      // Reload history after a delay to get actual results
      setTimeout(loadSyncHistory, 2000);
    } catch (error) {
      console.error('Sync failed:', error);
      const errorLog: SyncHistoryItem = {
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
        status: 'error',
        message: 'Sync failed',
        details: error instanceof Error ? error.message : 'Unknown error'
      };
      setLogs(prev => [errorLog, ...prev]);
    } finally {
      setSyncLoading(false);
      setCurrentScript(null);
    }
  };

  const handleScriptExecute = async (scriptId: string, parameters: Record<string, any>) => {
    setCurrentScript(scriptId);
    try {
      // Send script execution request via WebSocket
      sendMessage({
        type: 'execute',
        scriptId,
        parameters
      });
    } catch (error) {
      console.error('Script execution failed:', error);
      setCurrentScript(null);
    }
  };

  const handleLogout = async () => {
    await logout();
    setLogs([]);
  };

  if (!isAuthenticated) {
    return <AuthPage />;
  }

  const getViewIcon = (view: string) => {
    switch (view) {
      case 'sync':
        return <RotateCcw className="w-4 h-4" />;
      case 'scripts':
        return <Code2 className="w-4 h-4" />;
      case 'logs':
        return <FileText className="w-4 h-4" />;
      default:
        return null;
    }
  };

  return (
    <DashboardLayout>
      {/* Navigation using NavigationTabs component */}
      <NavigationTabs
        activeView={activeView}
        onViewChange={setActiveView}
        onLogout={handleLogout}
        lastSyncTime={logs.find(log => log.status === 'success')?.timestamp}
        isLoading={syncLoading}
        realtimeLogsCount={realtimeLogs.length}
        currentScript={currentScript || undefined}
        productsCount={0} // TODO: Add actual products count
        isAdmin={user?.is_admin || false}
      />
      
      {/* Content Area */}
      <div className="space-y-6">
        {activeView === 'sync' && (
          <EnhancedSyncDashboard />
        )}
        
        {activeView === 'scripts' && (
          <>
            {/* Script Execution */}
            <DashboardCard
              title="Script Execution"
              description="Execute individual scripts and monitor their progress"
              actions={
                currentScript && (
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                    <span className="text-xs text-muted-foreground">
                      Running: {currentScript}
                    </span>
                  </div>
                )
              }
            >
              <ScriptExecutor
                onExecute={handleScriptExecute}
                isExecuting={currentScript !== null}
                currentScript={currentScript || undefined}
                progress={scriptProgress[0]?.progress}
                logs={realtimeLogs.slice(-5).map(log => log.message)}
              />
            </DashboardCard>
            
            {/* Script Progress */}
            {scriptProgress.length > 0 && (
              <DashboardCard title="Execution Progress" description="Monitor script execution stages">
                <ProgressTracker stages={scriptProgress} orientation="horizontal" />
              </DashboardCard>
            )}
          </>
        )}
        
        {activeView === 'logs' && (
          <DashboardCard 
            title="Real-time Logs"
            description="Live monitoring of system activity and script execution"
            className="h-[600px]"
            actions={
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span className="text-xs text-muted-foreground">
                  Live ({realtimeLogs.length} entries)
                </span>
              </div>
            }
          >
            <RealtimeLogViewer
              logs={realtimeLogs}
              onClear={() => setRealtimeLogs([])}
            />
          </DashboardCard>
        )}
        
        {activeView === 'products' && (
          <ProductsDashboardEnhanced />
        )}
        
        {activeView === 'analytics' && (
          <DashboardCard
            title="Product Analytics"
            description="Comprehensive analytics and insights for your product catalog"
          >
            <ProductAnalyticsLive />
          </DashboardCard>
        )}
        
        {activeView === 'collections' && user?.is_admin && (
          <ProtectedRoute adminOnly>
            <CollectionsDashboard />
          </ProtectedRoute>
        )}
        
        {activeView === 'categories' && user?.is_admin && (
          <ProtectedRoute adminOnly>
            <DashboardCard
              title="Category Management"
              description="Manage product categories, hierarchy, and icon assignments"
              className="min-h-[600px]"
            >
              <CategoryManagementPanel
                categories={[]} // TODO: Load from API
                availableIcons={[]} // TODO: Load from API
                onCategoryCreate={(parentId, name, description) => {
                  console.log('Create category:', { parentId, name, description });
                  // TODO: Implement API call
                }}
                onCategoryUpdate={(categoryId, updates) => {
                  console.log('Update category:', { categoryId, updates });
                  // TODO: Implement API call
                }}
                onCategoryDelete={(categoryId) => {
                  console.log('Delete category:', categoryId);
                  // TODO: Implement API call
                }}
                onIconAssign={(categoryId, iconId) => {
                  console.log('Assign icon:', { categoryId, iconId });
                  // TODO: Implement API call
                }}
              />
            </DashboardCard>
          </ProtectedRoute>
        )}
        
        {activeView === 'icons' && user?.is_admin && (
          <ProtectedRoute adminOnly>
            <DashboardCard
              title="Icon Generation"
              description="Generate AI-powered category icons using OpenAI"
              className="min-h-[600px]"
            >
              <IconGenerationDashboard />
            </DashboardCard>
          </ProtectedRoute>
        )}
        
        {activeView === 'admin' && user?.is_admin && (
          <ProtectedRoute adminOnly>
            <AdminDashboard />
          </ProtectedRoute>
        )}
      </div>
    </DashboardLayout>
  );
}

function App() {
  return (
    <AuthProvider>
      <WebSocketProvider enableWebSocket={false}>
        <NotificationProvider>
          <AppContent />
        </NotificationProvider>
      </WebSocketProvider>
    </AuthProvider>
  );
}

export default App;