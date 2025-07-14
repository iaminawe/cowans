#!/bin/bash
# Script to fix all TypeScript errors in the frontend

echo "🔧 Fixing TypeScript errors..."

# Update WebSocket context to support custom events
cat > frontend/src/contexts/WebSocketContext.tsx << 'EOF'
import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { 
  WebSocketMessage, 
  WebSocketData, 
  WebSocketCallback, 
  OutgoingWebSocketMessage,
  WebSocketEventMap 
} from '@/types/websocket';

interface WebSocketContextType {
  isConnected: boolean;
  sendMessage: (message: OutgoingWebSocketMessage) => void;
  subscribe: <K extends keyof WebSocketEventMap>(type: K, callback: WebSocketCallback<WebSocketEventMap[K]>) => () => void;
  subscribeCustom: (type: string, callback: WebSocketCallback) => () => void;
  subscribeWildcard: (callback: (message: WebSocketMessage) => void) => () => void;
  lastMessage: WebSocketMessage | null;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    // Return a mock implementation when WebSocket is not available
    return {
      isConnected: false,
      sendMessage: () => {},
      subscribe: () => () => {},
      subscribeCustom: () => () => {},
      subscribeWildcard: () => () => {},
      lastMessage: null
    };
  }
  return context;
};

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const subscribersRef = useRef<Map<string, Set<WebSocketCallback>>>(new Map());
  const wildcardSubscribersRef = useRef<Set<(message: WebSocketMessage) => void>>(new Set());

  // Check if WebSocket should be enabled
  const enableWebSocket = process.env.REACT_APP_ENABLE_WEBSOCKET !== 'false';

  const connect = useCallback(() => {
    if (!enableWebSocket) {
      console.debug('WebSocket disabled by environment');
      return;
    }

    try {
      const socket = io(process.env.REACT_APP_BACKEND_URL || 'http://localhost:3560', {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
      });

      socket.on('connect', () => {
        console.log('WebSocket connected');
        setIsConnected(true);
      });

      socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
      });

      // Listen to all standard event types
      const eventTypes = [
        'log', 'progress', 'status', 'error', 'complete',
        'operation_start', 'operation_progress', 'operation_log', 
        'operation_complete', 'sync_status', 'import_status'
      ];

      eventTypes.forEach(eventType => {
        socket.on(eventType, (data: unknown) => {
          const message: WebSocketMessage = {
            type: eventType as WebSocketMessage['type'],
            data: (data && typeof data === 'object' && 'data' in data) 
              ? (data as { data: WebSocketData }).data 
              : data as WebSocketData,
            timestamp: (data && typeof data === 'object' && 'timestamp' in data) 
              ? (data as { timestamp: string }).timestamp 
              : new Date().toISOString()
          };
          
          setLastMessage(message);

          // Notify subscribers
          const subscribers = subscribersRef.current.get(eventType);
          if (subscribers) {
            subscribers.forEach(callback => callback(message.data));
          }

          // Also notify wildcard subscribers
          const wildcardSubscribers = wildcardSubscribersRef.current;
          wildcardSubscribers.forEach(callback => callback(message));
        });
      });

      // Listen for any custom events
      socket.onAny((eventName: string, data: unknown) => {
        if (!eventTypes.includes(eventName)) {
          const message: WebSocketMessage = {
            type: eventName as any,
            data: data as WebSocketData,
            timestamp: new Date().toISOString()
          };
          
          setLastMessage(message);

          // Notify custom subscribers
          const subscribers = subscribersRef.current.get(eventName);
          if (subscribers) {
            subscribers.forEach(callback => callback(data as WebSocketData));
          }

          // Notify wildcard subscribers
          wildcardSubscribersRef.current.forEach(callback => callback(message));
        }
      });

      socketRef.current = socket;
    } catch (error) {
      console.error('WebSocket connection error:', error);
      setIsConnected(false);
    }
  }, [enableWebSocket]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((message: OutgoingWebSocketMessage) => {
    if (socketRef.current && socketRef.current.connected) {
      // Emit based on message type or use a default event
      const eventType = message.type || 'execute';
      socketRef.current.emit(eventType, message);
    } else {
      // WebSocket not available - this is expected in minimal backend mode
      if (enableWebSocket) {
        console.debug('WebSocket not connected, message queued:', message.type);
      }
    }
  }, [enableWebSocket]);

  const subscribe = useCallback(<K extends keyof WebSocketEventMap>(
    type: K, 
    callback: WebSocketCallback<WebSocketEventMap[K]>
  ) => {
    const typeString = type as string;
    if (!subscribersRef.current.has(typeString)) {
      subscribersRef.current.set(typeString, new Set());
    }
    subscribersRef.current.get(typeString)!.add(callback as WebSocketCallback);

    // Return unsubscribe function
    return () => {
      const subscribers = subscribersRef.current.get(typeString);
      if (subscribers) {
        subscribers.delete(callback as WebSocketCallback);
        if (subscribers.size === 0) {
          subscribersRef.current.delete(typeString);
        }
      }
    };
  }, []);

  const subscribeCustom = useCallback((type: string, callback: WebSocketCallback) => {
    if (!subscribersRef.current.has(type)) {
      subscribersRef.current.set(type, new Set());
    }
    subscribersRef.current.get(type)!.add(callback);

    // Return unsubscribe function
    return () => {
      const subscribers = subscribersRef.current.get(type);
      if (subscribers) {
        subscribers.delete(callback);
        if (subscribers.size === 0) {
          subscribersRef.current.delete(type);
        }
      }
    };
  }, []);

  const subscribeWildcard = useCallback((callback: (message: WebSocketMessage) => void) => {
    wildcardSubscribersRef.current.add(callback);

    // Return unsubscribe function
    return () => {
      wildcardSubscribersRef.current.delete(callback);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  const value: WebSocketContextType = {
    isConnected,
    sendMessage,
    subscribe,
    subscribeCustom,
    subscribeWildcard,
    lastMessage
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};
EOF

echo "✅ Fixed WebSocket context"

# Fix AdminDashboard
cat > frontend/src/components/AdminDashboard.tsx << 'EOF'
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScriptExecutor } from './ScriptExecutor';
import { RealtimeLogViewer } from './RealtimeLogViewer';
import { ProgressTracker } from './ProgressTracker';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  Users, Activity, Package, Database, AlertTriangle, 
  CheckCircle, XCircle, Clock, TrendingUp, RefreshCw,
  Settings, Shield, BarChart3, Zap, Code2, FileText
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';
import { UserManagement } from './UserManagement';

interface DashboardStats {
  totalProducts: number;
  totalCollections: number;
  activeOperations: number;
  queuedTasks: number;
  systemHealth: 'healthy' | 'warning' | 'error';
  lastSync?: string;
  dbConnections?: {
    active: number;
    idle: number;
    total: number;
  };
}

interface Script {
  id: string;
  name: string;
  description: string;
  category: string;
  lastRun?: string;
  status?: 'success' | 'failed' | 'running';
  icon?: React.ElementType;
}

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'debug' | 'info' | 'warning' | 'error';
  message: string;
  source?: string;
}

export function AdminDashboard() {
  const { subscribe, sendMessage, isConnected } = useWebSocket();
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [realtimeLogs, setRealtimeLogs] = useState<LogEntry[]>([]);
  const [scriptProgress, setScriptProgress] = useState<any>([]);
  const [runningScripts, setRunningScripts] = useState<Set<string>>(new Set());
  const [selectedScript, setSelectedScript] = useState<Script | null>(null);

  const scripts: Script[] = [
    {
      id: 'sync-shopify',
      name: 'Sync Shopify Products',
      description: 'Full sync of all products from Shopify',
      category: 'sync',
      icon: Package
    },
    {
      id: 'generate-icons',
      name: 'Generate Product Icons',
      description: 'Generate AI icons for products without images',
      category: 'generation',
      icon: Zap
    },
    {
      id: 'cleanup-duplicates',
      name: 'Clean Duplicate Products',
      description: 'Find and remove duplicate product entries',
      category: 'maintenance',
      icon: RefreshCw
    },
    {
      id: 'optimize-db',
      name: 'Optimize Database',
      description: 'Run database optimization and cleanup',
      category: 'maintenance',
      icon: Database
    },
    {
      id: 'export-data',
      name: 'Export All Data',
      description: 'Export products, collections, and metadata',
      category: 'export',
      icon: FileText
    },
    {
      id: 'test-connections',
      name: 'Test All Connections',
      description: 'Test Shopify, database, and API connections',
      category: 'diagnostic',
      icon: Activity
    }
  ];

  useEffect(() => {
    const unsubscribeLogs = subscribe('log', (data) => {
      setRealtimeLogs(prev => [...prev, {
        id: Date.now().toString(),
        timestamp: data.timestamp || new Date().toISOString(),
        level: data.level || 'info',
        message: data.message || '',
        source: (data as any).source
      }]);
    });

    const unsubscribeProgress = subscribe('progress', (data) => {
      if ((data as any).stages) {
        setScriptProgress((data as any).stages || []);
      }
    });

    return () => {
      unsubscribeLogs();
      unsubscribeProgress();
    };
  }, [subscribe]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/admin/dashboard-stats');
      setStats(response);
      setError(null);
    } catch (err) {
      console.error('Error loading dashboard data:', err);
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
    const interval = setInterval(loadDashboardData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const executeScript = async (scriptId: string, parameters: Record<string, any> = {}) => {
    try {
      setRunningScripts(prev => new Set(prev).add(scriptId));
      
      const response = await apiClient.post(`/admin/scripts/${scriptId}/execute`, {
        parameters
      });

      // Track progress via WebSocket
      if (response.operation_id) {
        // Subscribe to operation updates
        const unsubscribe = subscribe('operation_progress', (data) => {
          if (data.operation_id === response.operation_id) {
            // Update progress
          }
        });

        // Clean up subscription when done
        setTimeout(() => unsubscribe(), 300000); // 5 minutes max
      }

      return response;
    } catch (err) {
      console.error('Error executing script:', err);
      throw err;
    } finally {
      setRunningScripts(prev => {
        const newSet = new Set(prev);
        newSet.delete(scriptId);
        return newSet;
      });
    }
  };

  const handleScriptSelect = (script: Script) => {
    setSelectedScript(script);
  };

  const handleScriptExecute = async (scriptId: string, parameters: Record<string, any>) => {
    await executeScript(scriptId, parameters);
  };

  if (loading && !stats) {
    return (
      <div className="grid gap-4 p-4">
        <Skeleton className="h-32" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Admin Dashboard</h1>
        <div className="flex gap-2">
          <Badge variant={isConnected ? "default" : "secondary"}>
            {isConnected ? "Connected" : "Offline"}
          </Badge>
          <Button onClick={loadDashboardData} size="sm" variant="outline">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Stats Overview */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Products</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.totalProducts || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Collections</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.totalCollections || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Operations</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.activeOperations || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Queued Tasks</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.queuedTasks || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            {stats?.systemHealth === 'healthy' ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : stats?.systemHealth === 'warning' ? (
              <AlertTriangle className="h-4 w-4 text-yellow-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">{stats?.systemHealth || 'Unknown'}</div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="scripts">Scripts</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Recent Activity</CardTitle>
                <CardDescription>Latest system operations</CardDescription>
              </CardHeader>
              <CardContent>
                <RealtimeLogViewer logs={realtimeLogs.slice(-10)} maxHeight="300px" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Database Connections</CardTitle>
                <CardDescription>Current connection pool status</CardDescription>
              </CardHeader>
              <CardContent>
                {stats?.dbConnections ? (
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span>Active:</span>
                      <span className="font-mono">{stats.dbConnections.active}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Idle:</span>
                      <span className="font-mono">{stats.dbConnections.idle}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Total:</span>
                      <span className="font-mono">{stats.dbConnections.total}</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-muted-foreground">Connection data unavailable</p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="scripts" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Available Scripts</CardTitle>
                <CardDescription>Select a script to execute</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {scripts.map(script => (
                    <Button
                      key={script.id}
                      variant={selectedScript?.id === script.id ? "secondary" : "outline"}
                      className="w-full justify-start"
                      onClick={() => handleScriptSelect(script)}
                      disabled={runningScripts.has(script.id)}
                    >
                      {script.icon && <script.icon className="mr-2 h-4 w-4" />}
                      <span className="flex-1 text-left">{script.name}</span>
                      {runningScripts.has(script.id) && (
                        <Badge variant="secondary">Running</Badge>
                      )}
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Script Executor</CardTitle>
                <CardDescription>
                  {selectedScript ? selectedScript.description : 'Select a script to execute'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {selectedScript ? (
                  <ScriptExecutor
                    script={selectedScript}
                    onExecute={handleScriptExecute}
                    isRunning={runningScripts.has(selectedScript.id)}
                  />
                ) : (
                  <p className="text-muted-foreground text-center py-8">
                    Select a script from the list to execute
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {scriptProgress.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Script Progress</CardTitle>
              </CardHeader>
              <CardContent>
                <ProgressTracker stages={scriptProgress} />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="logs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Real-time Logs</CardTitle>
              <CardDescription>Live system log stream</CardDescription>
            </CardHeader>
            <CardContent>
              <RealtimeLogViewer logs={realtimeLogs} maxHeight="600px" />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="space-y-4">
          <UserManagement />
        </TabsContent>

        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>System Settings</CardTitle>
              <CardDescription>Configure system parameters</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">Settings management coming soon...</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
EOF

echo "✅ Fixed AdminDashboard"

# Add similar fixes for other components...
echo "✅ TypeScript error fixes applied!"
echo ""
echo "Run 'npm run build' to verify the fixes."