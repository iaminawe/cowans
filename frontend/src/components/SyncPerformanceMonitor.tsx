import React, { useEffect, useState, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Activity,
  Cpu,
  HardDrive,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Zap,
  Users,
  Package,
  BarChart3,
  Info,
  AlertOctagon
} from 'lucide-react';
import {
  SyncMetrics,
  WorkerPoolStatus,
  QueueDepth,
  SystemResources,
  SyncAlert,
  PerformancePrediction
} from '@/types/sync';

interface SyncPerformanceMonitorProps {
  metrics: SyncMetrics;
  workerPool: WorkerPoolStatus;
  queue: QueueDepth;
  resources: SystemResources;
  alerts: SyncAlert[];
  prediction?: PerformancePrediction;
  className?: string;
}

export function SyncPerformanceMonitor({
  metrics,
  workerPool,
  queue,
  resources,
  alerts,
  prediction,
  className
}: SyncPerformanceMonitorProps) {
  const [selectedTab, setSelectedTab] = useState('overview');
  const [realtimeMetrics, setRealtimeMetrics] = useState(metrics);

  // Update metrics with smooth transitions
  useEffect(() => {
    setRealtimeMetrics(metrics);
  }, [metrics]);

  const formatNumber = (num: number): string => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toFixed(0);
  };

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`;
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const getHealthStatus = () => {
    if (metrics.errorRate > 10) return { status: 'critical', color: 'text-red-600' };
    if (metrics.errorRate > 5) return { status: 'warning', color: 'text-yellow-600' };
    if (metrics.successRate > 95) return { status: 'healthy', color: 'text-green-600' };
    return { status: 'normal', color: 'text-blue-600' };
  };

  const health = getHealthStatus();

  const activeAlerts = useMemo(
    () => alerts.filter(alert => !alert.resolved),
    [alerts]
  );

  const criticalAlerts = activeAlerts.filter(a => a.severity === 'critical');
  const warningAlerts = activeAlerts.filter(a => a.severity === 'warning');

  return (
    <div className={className}>
      <Tabs value={selectedTab} onValueChange={setSelectedTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="workers">Workers</TabsTrigger>
          <TabsTrigger value="resources">Resources</TabsTrigger>
          <TabsTrigger value="alerts">
            Alerts {activeAlerts.length > 0 && (
              <Badge variant="destructive" className="ml-2 h-5 w-5 p-0 justify-center">
                {activeAlerts.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {/* Key Metrics Grid */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Operations/sec</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{metrics.operationsPerSecond.toFixed(1)}</div>
                <p className="text-xs text-muted-foreground">
                  {metrics.throughput > 0 ? (
                    <span className="flex items-center gap-1">
                      <TrendingUp className="h-3 w-3 text-green-600" />
                      {(metrics.throughput * 100).toFixed(1)}% throughput
                    </span>
                  ) : (
                    'Calculating...'
                  )}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
                <CheckCircle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${health.color}`}>
                  {metrics.successRate.toFixed(1)}%
                </div>
                <p className="text-xs text-muted-foreground">
                  {formatNumber(metrics.successfulOperations)} successful
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Error Rate</CardTitle>
                <XCircle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${metrics.errorRate > 5 ? 'text-red-600' : ''}`}>
                  {metrics.errorRate.toFixed(1)}%
                </div>
                <p className="text-xs text-muted-foreground">
                  {formatNumber(metrics.failedOperations)} failed
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">ETA</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {metrics.estimatedTimeRemaining > 0 
                    ? formatDuration(metrics.estimatedTimeRemaining)
                    : 'Calculating...'}
                </div>
                <p className="text-xs text-muted-foreground">
                  Avg latency: {metrics.averageLatency.toFixed(0)}ms
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Performance Prediction */}
          {prediction && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-5 w-5" />
                  Performance Predictions
                </CardTitle>
                <CardDescription>
                  AI-powered analysis and optimization suggestions
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-3">
                  <div>
                    <p className="text-sm font-medium">Estimated Duration</p>
                    <p className="text-2xl font-bold">{formatDuration(prediction.estimatedDuration)}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Estimated Cost</p>
                    <p className="text-2xl font-bold">${prediction.estimatedCost.toFixed(2)}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Predicted Success Rate</p>
                    <p className="text-2xl font-bold">{prediction.estimatedSuccessRate.toFixed(1)}%</p>
                  </div>
                </div>

                {prediction.bottlenecks.length > 0 && (
                  <Alert>
                    <AlertTriangle className="h-4 w-4" />
                    <AlertTitle>Detected Bottlenecks</AlertTitle>
                    <AlertDescription>
                      <ul className="list-disc list-inside mt-2">
                        {prediction.bottlenecks.map((bottleneck, index) => (
                          <li key={index} className="text-sm">{bottleneck}</li>
                        ))}
                      </ul>
                    </AlertDescription>
                  </Alert>
                )}

                {prediction.optimizationSuggestions.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium mb-2">Optimization Suggestions</h4>
                    <div className="space-y-2">
                      {prediction.optimizationSuggestions.map((suggestion, index) => (
                        <div key={index} className="flex items-start gap-2">
                          <Info className="h-4 w-4 text-blue-600 mt-0.5" />
                          <p className="text-sm text-muted-foreground">{suggestion}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Live Progress */}
          <Card>
            <CardHeader>
              <CardTitle>Operation Progress</CardTitle>
              <CardDescription>
                {formatNumber(metrics.totalOperations)} total operations
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Overall Progress</span>
                  <span className="text-sm text-muted-foreground">
                    {((metrics.successfulOperations + metrics.failedOperations) / metrics.totalOperations * 100).toFixed(1)}%
                  </span>
                </div>
                <Progress 
                  value={(metrics.successfulOperations + metrics.failedOperations) / metrics.totalOperations * 100} 
                />
              </div>

              <div className="grid grid-cols-3 gap-4 text-sm">
                <div className="text-center">
                  <CheckCircle className="h-5 w-5 text-green-600 mx-auto mb-1" />
                  <p className="font-medium">{formatNumber(metrics.successfulOperations)}</p>
                  <p className="text-xs text-muted-foreground">Successful</p>
                </div>
                <div className="text-center">
                  <XCircle className="h-5 w-5 text-red-600 mx-auto mb-1" />
                  <p className="font-medium">{formatNumber(metrics.failedOperations)}</p>
                  <p className="text-xs text-muted-foreground">Failed</p>
                </div>
                <div className="text-center">
                  <Clock className="h-5 w-5 text-yellow-600 mx-auto mb-1" />
                  <p className="font-medium">{formatNumber(metrics.totalOperations - metrics.successfulOperations - metrics.failedOperations)}</p>
                  <p className="text-xs text-muted-foreground">Pending</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="workers" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Worker Pool Status
              </CardTitle>
              <CardDescription>
                Real-time worker utilization and task distribution
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Worker Pool Overview */}
              <div className="grid gap-4 md:grid-cols-4">
                <div>
                  <p className="text-sm font-medium">Active Workers</p>
                  <p className="text-2xl font-bold text-green-600">{workerPool.active}</p>
                </div>
                <div>
                  <p className="text-sm font-medium">Idle Workers</p>
                  <p className="text-2xl font-bold text-yellow-600">{workerPool.idle}</p>
                </div>
                <div>
                  <p className="text-sm font-medium">Total Workers</p>
                  <p className="text-2xl font-bold">{workerPool.total}</p>
                </div>
                <div>
                  <p className="text-sm font-medium">Utilization</p>
                  <p className="text-2xl font-bold">{(workerPool.utilization * 100).toFixed(1)}%</p>
                </div>
              </div>

              {/* Worker Utilization Bar */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Worker Utilization</span>
                  <span className="text-sm text-muted-foreground">
                    {workerPool.active}/{workerPool.total} workers active
                  </span>
                </div>
                <Progress value={workerPool.utilization * 100} />
              </div>

              {/* Task Distribution */}
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Task Distribution</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center p-4 border rounded-lg">
                    <Package className="h-5 w-5 text-blue-600 mx-auto mb-2" />
                    <p className="text-2xl font-bold">{workerPool.tasksQueued}</p>
                    <p className="text-xs text-muted-foreground">Queued</p>
                  </div>
                  <div className="text-center p-4 border rounded-lg">
                    <Activity className="h-5 w-5 text-yellow-600 mx-auto mb-2" />
                    <p className="text-2xl font-bold">{workerPool.tasksProcessing}</p>
                    <p className="text-xs text-muted-foreground">Processing</p>
                  </div>
                  <div className="text-center p-4 border rounded-lg">
                    <CheckCircle className="h-5 w-5 text-green-600 mx-auto mb-2" />
                    <p className="text-2xl font-bold">{workerPool.tasksCompleted}</p>
                    <p className="text-xs text-muted-foreground">Completed</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Queue Depth Visualization */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Queue Depth Analysis
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <h4 className="text-sm font-medium mb-2">By Priority</h4>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm">High Priority</span>
                      <Badge variant="destructive">{queue.byPriority.high}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Normal Priority</span>
                      <Badge variant="default">{queue.byPriority.normal}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Low Priority</span>
                      <Badge variant="secondary">{queue.byPriority.low}</Badge>
                    </div>
                  </div>
                </div>
                <div>
                  <h4 className="text-sm font-medium mb-2">By Operation</h4>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Create</span>
                      <Badge variant="outline">{queue.byOperation.create}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Update</span>
                      <Badge variant="outline">{queue.byOperation.update}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Delete</span>
                      <Badge variant="outline">{queue.byOperation.delete}</Badge>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Average Wait Time:</span>
                    <span className="ml-2 font-medium">{formatDuration(queue.averageWaitTime)}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Oldest Item Age:</span>
                    <span className="ml-2 font-medium">{formatDuration(queue.oldestItemAge)}</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="resources" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Memory Usage */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <HardDrive className="h-5 w-5" />
                  Memory Usage
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">System Memory</span>
                    <span className="text-sm text-muted-foreground">
                      {(resources.memory.used / 1024 / 1024 / 1024).toFixed(1)}GB / {(resources.memory.total / 1024 / 1024 / 1024).toFixed(1)}GB
                    </span>
                  </div>
                  <Progress value={resources.memory.percentage} />
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <p className="text-3xl font-bold">{resources.memory.percentage.toFixed(1)}%</p>
                  <p className="text-sm text-muted-foreground">Memory Utilization</p>
                </div>
              </CardContent>
            </Card>

            {/* CPU Usage */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Cpu className="h-5 w-5" />
                  CPU Usage
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">CPU Load</span>
                    <span className="text-sm text-muted-foreground">
                      {resources.cpu.cores} cores available
                    </span>
                  </div>
                  <Progress value={resources.cpu.usage} />
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <p className="text-3xl font-bold">{resources.cpu.usage.toFixed(1)}%</p>
                  <p className="text-sm text-muted-foreground">CPU Utilization</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Network Performance */}
          <Card>
            <CardHeader>
              <CardTitle>Network Performance</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-4 border rounded-lg">
                  <Activity className="h-5 w-5 text-blue-600 mx-auto mb-2" />
                  <p className="text-2xl font-bold">{resources.network.latency.toFixed(0)}ms</p>
                  <p className="text-xs text-muted-foreground">Network Latency</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <Zap className="h-5 w-5 text-green-600 mx-auto mb-2" />
                  <p className="text-2xl font-bold">{(resources.network.throughput / 1024 / 1024).toFixed(1)} MB/s</p>
                  <p className="text-xs text-muted-foreground">Throughput</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="alerts" className="space-y-4">
          {activeAlerts.length === 0 ? (
            <Card>
              <CardContent className="flex items-center justify-center py-8">
                <div className="text-center">
                  <CheckCircle className="h-8 w-8 text-green-600 mx-auto mb-2" />
                  <p className="text-muted-foreground">No active alerts</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <>
              {criticalAlerts.length > 0 && (
                <Alert variant="destructive">
                  <AlertOctagon className="h-4 w-4" />
                  <AlertTitle>Critical Alerts ({criticalAlerts.length})</AlertTitle>
                  <AlertDescription>
                    <div className="mt-2 space-y-2">
                      {criticalAlerts.map((alert) => (
                        <div key={alert.id} className="text-sm">
                          <p className="font-medium">{alert.message}</p>
                          <p className="text-xs opacity-75">
                            {alert.source} • {new Date(alert.timestamp).toLocaleTimeString()}
                          </p>
                        </div>
                      ))}
                    </div>
                  </AlertDescription>
                </Alert>
              )}

              {warningAlerts.length > 0 && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Warnings ({warningAlerts.length})</AlertTitle>
                  <AlertDescription>
                    <div className="mt-2 space-y-2">
                      {warningAlerts.map((alert) => (
                        <div key={alert.id} className="text-sm">
                          <p className="font-medium">{alert.message}</p>
                          <p className="text-xs opacity-75">
                            {alert.source} • {new Date(alert.timestamp).toLocaleTimeString()}
                          </p>
                        </div>
                      ))}
                    </div>
                  </AlertDescription>
                </Alert>
              )}

              <Card>
                <CardHeader>
                  <CardTitle>All Alerts</CardTitle>
                  <CardDescription>
                    Complete list of system alerts and notifications
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {activeAlerts.map((alert) => (
                      <div 
                        key={alert.id} 
                        className="flex items-start gap-3 p-3 border rounded-lg"
                      >
                        <div className="mt-0.5">
                          {alert.severity === 'critical' && <AlertOctagon className="h-4 w-4 text-red-600" />}
                          {alert.severity === 'error' && <XCircle className="h-4 w-4 text-red-500" />}
                          {alert.severity === 'warning' && <AlertTriangle className="h-4 w-4 text-yellow-600" />}
                          {alert.severity === 'info' && <Info className="h-4 w-4 text-blue-600" />}
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-medium">{alert.message}</p>
                          <p className="text-xs text-muted-foreground">
                            {alert.source} • {new Date(alert.timestamp).toLocaleString()}
                          </p>
                          {alert.actionRequired && (
                            <Badge variant="outline" className="mt-1">
                              Action Required
                            </Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}