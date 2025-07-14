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
  users: {
    total: number;
    active: number;
    admins: number;
    new_this_week: number;
    new_this_month: number;
  };
  products: {
    total: number;
    active: number;
    with_shopify_sync: number;
    pending_sync: number;
    new_this_week: number;
    new_this_month: number;
  };
  categories: {
    total: number;
    active: number;
    with_products: number;
    empty: number;
    max_depth: number;
  };
  jobs: {
    total: number;
    running: number;
    pending: number;
    completed: number;
    failed: number;
    today: number;
  };
  sync_history: {
    total_syncs: number;
    successful_syncs: number;
    failed_syncs: number;
    this_week: number;
    avg_products_per_sync: number;
  };
  system: {
    error_rate: number;
    avg_response_time: number;
    uptime_percentage: number;
    database_size: number;
    last_backup: string | null;
  };
  recent_activity: Array<{
    id: string;
    script_name: string;
    status: string;
    created_at: string;
    user_email: string;
  }>;
  performance: {
    avg_job_duration: number;
    jobs_per_hour: number;
    success_rate: number;
  };
  generated_at: string;
}


interface Job {
  id: string;
  type: string;
  status: string;
  user_email: string;
  created_at: string;
  completed_at?: string;
  error?: string;
}

export function AdminDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [error, setError] = useState<string | null>(null);
  const [realtimeLogs, setRealtimeLogs] = useState<any[]>([]);
  const [scriptProgress, setScriptProgress] = useState<any[]>([]);
  const [currentScript, setCurrentScript] = useState<string | null>(null);
  const { subscribe, sendMessage } = useWebSocket();

  useEffect(() => {
    loadDashboardData();
  }, []);

  // Subscribe to WebSocket events for scripts and logs
  useEffect(() => {
    const unsubscribeLogs = subscribe('log', (data) => {
      setRealtimeLogs(prev => [...prev, {
        id: Date.now().toString(),
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

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Load dashboard overview
      const dashboardData = await apiClient.get<DashboardStats>('/admin/dashboard');
      console.log('Dashboard data received:', dashboardData);
      setStats(dashboardData);
      
      // Load recent jobs
      const jobsResponse = await apiClient.get<{jobs: Job[], pagination?: any}>('/admin/jobs?limit=10');
      setJobs(jobsResponse.jobs || []);
      
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
      setError('Failed to load dashboard data. Please check your permissions.');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadDashboardData();
    setRefreshing(false);
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
      case 'success':
        return 'text-green-600';
      case 'failed':
      case 'error':
        return 'text-red-600';
      case 'running':
      case 'pending':
        return 'text-blue-600';
      default:
        return 'text-gray-600';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
      case 'success':
        return <CheckCircle className="w-4 h-4" />;
      case 'failed':
      case 'error':
        return <XCircle className="w-4 h-4" />;
      case 'running':
      case 'pending':
        return <Clock className="w-4 h-4" />;
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Admin Dashboard</h2>
          <p className="text-muted-foreground">System overview and management</p>
        </div>
        <Button 
          onClick={handleRefresh} 
          disabled={refreshing}
          variant="outline"
          size="sm"
        >
          <RefreshCw className={cn("h-4 w-4 mr-2", refreshing && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Users</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.users.total}</div>
              <p className="text-xs text-muted-foreground">
                {stats.users.active} active, {stats.users.admins} admins
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Jobs</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.jobs.running}</div>
              <p className="text-xs text-muted-foreground">
                {stats.jobs.today} created today
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">API Performance</CardTitle>
              <Zap className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.system.avg_response_time}ms</div>
              <p className="text-xs text-muted-foreground">
                Avg response time
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">System Health</CardTitle>
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.system.uptime_percentage}%</div>
              <p className="text-xs text-muted-foreground">
                Uptime last 30 days
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="jobs">Jobs</TabsTrigger>
          <TabsTrigger value="system">System</TabsTrigger>
          <TabsTrigger value="scripts" className="flex items-center gap-2">
            <Code2 className="h-4 w-4" />
            Scripts
          </TabsTrigger>
          <TabsTrigger value="logs" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Logs
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>Latest system events and user actions</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {(stats?.recent_activity || []).slice(0, 5).map((activity) => (
                  <div key={activity.id} className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className={cn("flex items-center", getStatusColor(activity.status))}>
                        {getStatusIcon(activity.status)}
                      </div>
                      <div>
                        <p className="text-sm font-medium">{activity.script_name}</p>
                        <p className="text-xs text-muted-foreground">
                          by {activity.user_email} • {new Date(activity.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <Badge variant={activity.status === 'completed' ? 'default' : 'secondary'}>
                      {activity.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="space-y-4">
          <UserManagement />
        </TabsContent>

        <TabsContent value="jobs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Job History</CardTitle>
              <CardDescription>Recent background jobs and their status</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job ID</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Duration</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(jobs || []).map((job) => (
                    <TableRow key={job.id}>
                      <TableCell className="font-mono text-xs">{job.id}</TableCell>
                      <TableCell>{job.type}</TableCell>
                      <TableCell>{job.user_email}</TableCell>
                      <TableCell>
                        <div className={cn("flex items-center gap-1", getStatusColor(job.status))}>
                          {getStatusIcon(job.status)}
                          <span>{job.status}</span>
                        </div>
                      </TableCell>
                      <TableCell>{new Date(job.created_at).toLocaleString()}</TableCell>
                      <TableCell>
                        {job.completed_at 
                          ? `${Math.round((new Date(job.completed_at).getTime() - new Date(job.created_at).getTime()) / 1000)}s`
                          : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="system" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Database Statistics</CardTitle>
                <CardDescription>Storage and performance metrics</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm">Database Size</span>
                    <span className="text-sm font-medium">{stats?.system.database_size ? `${stats.system.database_size} MB` : '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm">Error Rate</span>
                    <span className="text-sm font-medium">{typeof stats?.system.error_rate === 'number' ? stats.system.error_rate.toFixed(2) : '0'}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm">Avg Response Time</span>
                    <span className="text-sm font-medium">{stats?.system.avg_response_time}ms</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>API Performance</CardTitle>
                <CardDescription>Request metrics and error rates</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm">Jobs Per Hour</span>
                    <span className="text-sm font-medium">{typeof stats?.performance.jobs_per_hour === 'number' ? stats.performance.jobs_per_hour.toFixed(1) : '0'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm">Success Rate</span>
                    <span className="text-sm font-medium">{typeof stats?.performance.success_rate === 'number' ? stats.performance.success_rate.toFixed(1) : '0'}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm">Avg Job Duration</span>
                    <span className="text-sm font-medium">{typeof stats?.performance.avg_job_duration === 'number' ? stats.performance.avg_job_duration.toFixed(1) : '0'}s</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="scripts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Code2 className="h-5 w-5" />
                Script Management
              </CardTitle>
              <CardDescription>
                Execute and monitor system scripts
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScriptExecutor
                onExecute={handleScriptExecute}
                isExecuting={currentScript !== null}
                currentScript={currentScript || undefined}
                progress={scriptProgress[0]?.progress}
                logs={realtimeLogs.slice(-5).map(log => log.message)}
              />
            </CardContent>
          </Card>
          
          {scriptProgress.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Execution Progress</CardTitle>
                <CardDescription>Monitor script execution stages</CardDescription>
              </CardHeader>
              <CardContent>
                <ProgressTracker stages={scriptProgress} orientation="horizontal" />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="logs" className="space-y-4">
          <Card className="h-[700px]">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                System Logs
              </CardTitle>
              <CardDescription>
                Real-time system logs and activity monitoring
              </CardDescription>
              <div className="flex items-center gap-2 text-sm">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span className="text-muted-foreground">
                  Live ({realtimeLogs.length} entries)
                </span>
              </div>
            </CardHeader>
            <CardContent className="h-full pb-6">
              <RealtimeLogViewer
                logs={realtimeLogs}
                onClear={() => setRealtimeLogs([])}
                className="h-full"
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}