import React, { useState, useEffect } from 'react';
import { DashboardLayout, DashboardSection, DashboardGrid, DashboardCard } from './components/DashboardLayout';
import { SyncTrigger } from './components/SyncTrigger';
import { LogViewer } from './components/LogViewer';
import { AuthPage } from './components/AuthPage';
import { ProtectedRoute } from './components/ProtectedRoute';
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
import { EnhancedCategoriesPanel } from './components/EnhancedCategoriesPanel';
import { AdminDashboard } from './components/AdminDashboard';
import { IconGenerationDashboard } from './components/IconGenerationDashboard';
import { EnhancedSyncDashboard } from './components/EnhancedSyncDashboard';
import { ProductAnalyticsLive } from './components/ProductAnalyticsLive';

function AppContent() {
  const [logs, setLogs] = useState<SyncHistoryItem[]>([]);
  const [syncLoading, setSyncLoading] = useState(false);
  const [activeView, setActiveView] = useState<'sync' | 'scripts' | 'logs' | 'products' | 'analytics' | 'collections' | 'categories' | 'icons' | 'admin'>('sync');
  const { subscribe, sendMessage, isConnected } = useWebSocket();
  const { isAuthenticated, user, logout } = useAuth();

  useEffect(() => {
    if (isAuthenticated) {
      loadSyncHistory();
    }
  }, [isAuthenticated]);


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
    }
  };


  const handleLogout = async () => {
    await logout();
    setLogs([]);
  };

  if (!isAuthenticated) {
    return <AuthPage />;
  }


  return (
    <DashboardLayout
      syncStatus={syncLoading ? 'syncing' : 'ready'}
      lastSyncTime={logs.find(log => log.status === 'success')?.timestamp}
      onLogout={handleLogout}
      user={user || undefined}
      isLoading={syncLoading}
    >
      {/* Navigation using NavigationTabs component */}
      <NavigationTabs
        activeView={activeView}
        onViewChange={setActiveView}
        isLoading={syncLoading}
        realtimeLogsCount={0}
        currentScript={undefined}
        productsCount={0} // TODO: Add actual products count
        isAdmin={user?.is_admin || false}
      />
      
      {/* Content Area */}
      <div className="space-y-6">
        {activeView === 'sync' && (
          <EnhancedSyncDashboard />
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
            <EnhancedCategoriesPanel />
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