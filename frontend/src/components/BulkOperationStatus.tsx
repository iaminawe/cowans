import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  PlayCircle,
  PauseCircle,
  StopCircle,
  Download,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  FileDown,
  FileJson,
  FileSpreadsheet,
  Eye,
  RotateCcw,
  Trash2,
  ChevronRight
} from 'lucide-react';
import { BulkOperation, BulkOperationError, ParallelSyncResultsDownload } from '@/types/sync';
import { apiClient } from '@/lib/api';

interface BulkOperationStatusProps {
  operations: BulkOperation[];
  onCancelOperation: (operationId: string) => void;
  onRetryOperation: (operationId: string) => void;
  onRefresh: () => void;
  className?: string;
}

export function BulkOperationStatus({
  operations,
  onCancelOperation,
  onRetryOperation,
  onRefresh,
  className
}: BulkOperationStatusProps) {
  const [selectedOperation, setSelectedOperation] = useState<BulkOperation | null>(null);
  const [showErrorDetails, setShowErrorDetails] = useState(false);
  const [downloadFormat, setDownloadFormat] = useState<'csv' | 'json' | 'xlsx'>('csv');

  const activeOperations = useMemo(
    () => operations.filter(op => op.status === 'processing' || op.status === 'queued'),
    [operations]
  );

  const completedOperations = useMemo(
    () => operations.filter(op => op.status === 'completed' || op.status === 'failed' || op.status === 'cancelled'),
    [operations]
  );

  const formatDuration = (start: Date, end?: Date): string => {
    const endTime = end || new Date();
    const duration = (endTime.getTime() - start.getTime()) / 1000;
    
    if (duration < 60) return `${duration.toFixed(0)}s`;
    if (duration < 3600) return `${Math.floor(duration / 60)}m ${(duration % 60).toFixed(0)}s`;
    const hours = Math.floor(duration / 3600);
    const minutes = Math.floor((duration % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'queued':
        return <Clock className="h-4 w-4" />;
      case 'processing':
        return <RefreshCw className="h-4 w-4 animate-spin" />;
      case 'completed':
        return <CheckCircle className="h-4 w-4" />;
      case 'failed':
        return <XCircle className="h-4 w-4" />;
      case 'cancelled':
        return <StopCircle className="h-4 w-4" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'queued':
        return 'bg-gray-500';
      case 'processing':
        return 'bg-blue-500';
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'cancelled':
        return 'bg-yellow-500';
      default:
        return 'bg-gray-500';
    }
  };

  const handleDownloadResults = async (operation: BulkOperation) => {
    try {
      const downloadConfig: ParallelSyncResultsDownload = {
        format: downloadFormat,
        includeErrors: true,
        includeSuccesses: true,
        includeSkipped: true
      };

      // This would call your API to download results
      await apiClient.downloadBulkOperationResults(operation.id, downloadConfig);
    } catch (error) {
      console.error('Failed to download results:', error);
    }
  };

  const renderOperationCard = (operation: BulkOperation) => {
    const isActive = operation.status === 'processing' || operation.status === 'queued';
    const hasErrors = operation.failedItems > 0;

    return (
      <Card key={operation.id} className="overflow-hidden">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Badge variant="outline" className={`${getStatusColor(operation.status)} text-white`}>
                <span className="flex items-center gap-1">
                  {getStatusIcon(operation.status)}
                  {operation.status}
                </span>
              </Badge>
              <CardTitle className="text-base">
                {operation.type.charAt(0).toUpperCase() + operation.type.slice(1)} Operation
              </CardTitle>
            </div>
            <div className="flex items-center gap-2">
              {operation.status === 'completed' && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleDownloadResults(operation)}
                >
                  <Download className="h-4 w-4" />
                </Button>
              )}
              {operation.status === 'failed' && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onRetryOperation(operation.id)}
                >
                  <RotateCcw className="h-4 w-4" />
                </Button>
              )}
              {isActive && (
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => onCancelOperation(operation.id)}
                >
                  <StopCircle className="h-4 w-4" />
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelectedOperation(operation)}
              >
                <Eye className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Progress Bar */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">
                {operation.processedItems} / {operation.totalItems} items
              </span>
              <span className="text-sm text-muted-foreground">
                {operation.progress.toFixed(1)}%
              </span>
            </div>
            <Progress value={operation.progress} />
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div className="text-center">
              <CheckCircle className="h-5 w-5 text-green-600 mx-auto mb-1" />
              <p className="font-medium">{operation.successfulItems}</p>
              <p className="text-xs text-muted-foreground">Successful</p>
            </div>
            <div className="text-center">
              <XCircle className="h-5 w-5 text-red-600 mx-auto mb-1" />
              <p className="font-medium">{operation.failedItems}</p>
              <p className="text-xs text-muted-foreground">Failed</p>
            </div>
            <div className="text-center">
              <Clock className="h-5 w-5 text-yellow-600 mx-auto mb-1" />
              <p className="font-medium">{formatDuration(operation.startTime, operation.endTime)}</p>
              <p className="text-xs text-muted-foreground">Duration</p>
            </div>
          </div>

          {/* Error Summary */}
          {hasErrors && operation.errors.length > 0 && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <p className="font-medium mb-1">
                  {operation.errors.length} errors occurred
                </p>
                <p className="text-sm">
                  {operation.errors[0].message}
                </p>
                {operation.errors.length > 1 && (
                  <Button
                    variant="link"
                    size="sm"
                    className="p-0 h-auto mt-1"
                    onClick={() => {
                      setSelectedOperation(operation);
                      setShowErrorDetails(true);
                    }}
                  >
                    View all errors →
                  </Button>
                )}
              </AlertDescription>
            </Alert>
          )}

          {/* ETA for active operations */}
          {isActive && operation.estimatedEndTime && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Estimated completion:</span>
              <span className="font-medium">
                {new Date(operation.estimatedEndTime).toLocaleTimeString()}
              </span>
            </div>
          )}

          {/* Operation Configuration */}
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">
              {operation.config.strategy} strategy
            </Badge>
            <Badge variant="secondary">
              {operation.config.priority} priority
            </Badge>
            <Badge variant="secondary">
              Batch size: {operation.config.batchSize}
            </Badge>
            <Badge variant="secondary">
              {operation.config.minWorkers}-{operation.config.maxWorkers} workers
            </Badge>
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold">Bulk Operations</h3>
          <p className="text-sm text-muted-foreground">
            {activeOperations.length} active, {completedOperations.length} completed
          </p>
        </div>
        <Button onClick={onRefresh} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <Tabs defaultValue="active" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="active">
            Active ({activeOperations.length})
          </TabsTrigger>
          <TabsTrigger value="history">
            History ({completedOperations.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="active" className="space-y-4">
          {activeOperations.length === 0 ? (
            <Card>
              <CardContent className="flex items-center justify-center py-8">
                <div className="text-center">
                  <PlayCircle className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                  <p className="text-muted-foreground">No active operations</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            activeOperations.map(renderOperationCard)
          )}
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          {completedOperations.length === 0 ? (
            <Card>
              <CardContent className="flex items-center justify-center py-8">
                <div className="text-center">
                  <Clock className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                  <p className="text-muted-foreground">No completed operations</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            completedOperations.map(renderOperationCard)
          )}
        </TabsContent>
      </Tabs>

      {/* Operation Details Dialog */}
      <Dialog open={!!selectedOperation} onOpenChange={() => setSelectedOperation(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>Operation Details</DialogTitle>
            <DialogDescription>
              {selectedOperation?.id}
            </DialogDescription>
          </DialogHeader>
          
          {selectedOperation && (
            <Tabs defaultValue="summary" className="mt-4">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="summary">Summary</TabsTrigger>
                <TabsTrigger value="errors">
                  Errors ({selectedOperation.errors.length})
                </TabsTrigger>
                <TabsTrigger value="results">Results</TabsTrigger>
              </TabsList>

              <TabsContent value="summary" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm font-medium">Type</p>
                    <p className="text-lg">{selectedOperation.type}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Status</p>
                    <Badge variant="outline" className={`${getStatusColor(selectedOperation.status)} text-white`}>
                      {selectedOperation.status}
                    </Badge>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Started</p>
                    <p className="text-lg">{selectedOperation.startTime.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Duration</p>
                    <p className="text-lg">
                      {formatDuration(selectedOperation.startTime, selectedOperation.endTime)}
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium">Progress</p>
                  <Progress value={selectedOperation.progress} />
                  <div className="grid grid-cols-4 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Total</p>
                      <p className="font-medium">{selectedOperation.totalItems}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Processed</p>
                      <p className="font-medium">{selectedOperation.processedItems}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Successful</p>
                      <p className="font-medium text-green-600">{selectedOperation.successfulItems}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Failed</p>
                      <p className="font-medium text-red-600">{selectedOperation.failedItems}</p>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium">Configuration</p>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Strategy:</span>
                      <span>{selectedOperation.config.strategy}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Priority:</span>
                      <span>{selectedOperation.config.priority}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Batch Size:</span>
                      <span>{selectedOperation.config.batchSize}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Workers:</span>
                      <span>{selectedOperation.config.minWorkers}-{selectedOperation.config.maxWorkers}</span>
                    </div>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="errors" className="space-y-4">
                <ScrollArea className="h-[400px] w-full rounded-md border p-4">
                  {selectedOperation.errors.length === 0 ? (
                    <div className="text-center py-8">
                      <CheckCircle className="h-8 w-8 text-green-600 mx-auto mb-2" />
                      <p className="text-muted-foreground">No errors occurred</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {selectedOperation.errors.map((error, index) => (
                        <div key={index} className="p-3 border rounded-lg space-y-2">
                          <div className="flex items-start justify-between">
                            <div className="space-y-1">
                              <p className="text-sm font-medium">Item ID: {error.itemId}</p>
                              <p className="text-sm">{error.message}</p>
                              <p className="text-xs text-muted-foreground">
                                Code: {error.code} • {new Date(error.timestamp).toLocaleString()}
                              </p>
                            </div>
                            {error.retryable && (
                              <Badge variant="outline" className="text-xs">
                                Retryable
                              </Badge>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              <TabsContent value="results" className="space-y-4">
                {selectedOperation.results ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-2xl font-bold text-green-600">
                            {selectedOperation.results.summary.successful}
                          </div>
                          <p className="text-xs text-muted-foreground">Successful</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-2xl font-bold text-red-600">
                            {selectedOperation.results.summary.failed}
                          </div>
                          <p className="text-xs text-muted-foreground">Failed</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-2xl font-bold text-yellow-600">
                            {selectedOperation.results.summary.skipped}
                          </div>
                          <p className="text-xs text-muted-foreground">Skipped</p>
                        </CardContent>
                      </Card>
                    </div>

                    <div className="space-y-2">
                      <p className="text-sm font-medium">Download Results</p>
                      <div className="flex items-center gap-2">
                        <Select value={downloadFormat} onValueChange={(value: any) => setDownloadFormat(value)}>
                          <SelectTrigger className="w-32">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="csv">
                              <div className="flex items-center gap-2">
                                <FileSpreadsheet className="h-4 w-4" />
                                CSV
                              </div>
                            </SelectItem>
                            <SelectItem value="json">
                              <div className="flex items-center gap-2">
                                <FileJson className="h-4 w-4" />
                                JSON
                              </div>
                            </SelectItem>
                            <SelectItem value="xlsx">
                              <div className="flex items-center gap-2">
                                <FileSpreadsheet className="h-4 w-4" />
                                Excel
                              </div>
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <Button onClick={() => handleDownloadResults(selectedOperation)}>
                          <Download className="h-4 w-4 mr-2" />
                          Download
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <Clock className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                    <p className="text-muted-foreground">
                      Results will be available when the operation completes
                    </p>
                  </div>
                )}
              </TabsContent>
            </Tabs>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}