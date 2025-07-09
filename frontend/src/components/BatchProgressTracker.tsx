import React from 'react';
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Clock, 
  CheckCircle2, 
  XCircle, 
  Loader2, 
  AlertTriangle,
  Pause,
  Play,
  Square,
  BarChart3,
  Zap,
  Timer
} from 'lucide-react';

export interface BatchStage {
  id: string;
  name: string;
  description?: string;
  status: 'pending' | 'running' | 'completed' | 'error' | 'paused';
  progress: number; // 0-100
  currentItem?: string;
  totalItems?: number;
  completedItems?: number;
  startTime?: string;
  endTime?: string;
  duration?: number; // in seconds
  error?: string;
  estimatedTimeRemaining?: number; // in seconds
}

export interface BatchOperation {
  id: string;
  name: string;
  description?: string;
  status: 'idle' | 'running' | 'paused' | 'completed' | 'error' | 'cancelled';
  stages: BatchStage[];
  totalProgress: number; // 0-100
  startTime?: string;
  endTime?: string;
  estimatedTimeRemaining?: number;
  itemsProcessed: number;
  totalItems: number;
  successfulItems: number;
  failedItems: number;
  canPause?: boolean;
  canCancel?: boolean;
}

interface BatchProgressTrackerProps {
  operation: BatchOperation;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
  onRetry?: () => void;
  showDetails?: boolean;
  orientation?: 'horizontal' | 'vertical';
  compact?: boolean;
  className?: string;
}

export function BatchProgressTracker({
  operation,
  onPause,
  onResume,
  onCancel,
  onRetry,
  showDetails = true,
  orientation = 'horizontal',
  compact = false,
  className
}: BatchProgressTrackerProps) {
  const getStatusIcon = (status: BatchOperation['status']) => {
    switch (status) {
      case 'running':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-600" />;
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-600" />;
      case 'paused':
        return <Pause className="h-4 w-4 text-yellow-600" />;
      case 'cancelled':
        return <Square className="h-4 w-4 text-gray-600" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusBadge = (status: BatchOperation['status']) => {
    switch (status) {
      case 'running':
        return <Badge className="bg-blue-100 text-blue-800 border-blue-200">Running</Badge>;
      case 'completed':
        return <Badge className="bg-green-100 text-green-800 border-green-200">Completed</Badge>;
      case 'error':
        return <Badge variant="destructive">Error</Badge>;
      case 'paused':
        return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">Paused</Badge>;
      case 'cancelled':
        return <Badge variant="outline">Cancelled</Badge>;
      default:
        return <Badge variant="outline">Idle</Badge>;
    }
  };

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`;
    return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
  };

  const getElapsedTime = () => {
    if (!operation.startTime) return 0;
    const start = new Date(operation.startTime).getTime();
    const end = operation.endTime ? new Date(operation.endTime).getTime() : Date.now();
    return Math.floor((end - start) / 1000);
  };

  const currentStage = operation.stages.find(stage => stage.status === 'running');
  const completedStages = operation.stages.filter(stage => stage.status === 'completed').length;
  const elapsedTime = getElapsedTime();

  if (compact) {
    return (
      <div className={cn("flex items-center gap-4 p-3 border rounded-lg", className)}>
        <div className="flex items-center gap-2">
          {getStatusIcon(operation.status)}
          <span className="font-medium text-sm">{operation.name}</span>
        </div>
        <div className="flex-1">
          <Progress value={operation.totalProgress} className="h-2" />
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>{operation.itemsProcessed}/{operation.totalItems}</span>
          {operation.estimatedTimeRemaining && (
            <span>~{formatTime(operation.estimatedTimeRemaining)}</span>
          )}
        </div>
        {operation.status === 'running' && operation.canPause && onPause && (
          <Button variant="ghost" size="sm" onClick={onPause}>
            <Pause className="h-3 w-3" />
          </Button>
        )}
      </div>
    );
  }

  return (
    <Card className={cn("", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              {getStatusIcon(operation.status)}
              <CardTitle className="text-lg">{operation.name}</CardTitle>
            </div>
            {getStatusBadge(operation.status)}
          </div>
          
          <div className="flex items-center gap-2">
            {operation.status === 'running' && operation.canPause && onPause && (
              <Button variant="outline" size="sm" onClick={onPause}>
                <Pause className="h-4 w-4 mr-1" />
                Pause
              </Button>
            )}
            {operation.status === 'paused' && onResume && (
              <Button variant="outline" size="sm" onClick={onResume}>
                <Play className="h-4 w-4 mr-1" />
                Resume
              </Button>
            )}
            {operation.status === 'error' && onRetry && (
              <Button variant="outline" size="sm" onClick={onRetry}>
                <Loader2 className="h-4 w-4 mr-1" />
                Retry
              </Button>
            )}
            {(operation.status === 'running' || operation.status === 'paused') && operation.canCancel && onCancel && (
              <Button variant="outline" size="sm" onClick={onCancel} className="text-red-600">
                <Square className="h-4 w-4 mr-1" />
                Cancel
              </Button>
            )}
          </div>
        </div>
        
        {operation.description && (
          <p className="text-sm text-muted-foreground mt-1">{operation.description}</p>
        )}
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Overall Progress */}
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Overall Progress</span>
            <span className="text-muted-foreground">
              {operation.itemsProcessed}/{operation.totalItems} items
            </span>
          </div>
          <Progress 
            value={operation.totalProgress} 
            className="h-3"
            variant={operation.status === 'error' ? 'error' : 'default'}
          />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{Math.round(operation.totalProgress)}% complete</span>
            {operation.estimatedTimeRemaining && (
              <span className="flex items-center gap-1">
                <Timer className="h-3 w-3" />
                {formatTime(operation.estimatedTimeRemaining)} remaining
              </span>
            )}
          </div>
        </div>

        {/* Statistics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center p-3 rounded-lg bg-gray-100 dark:bg-gray-800">
            <div className="text-lg font-semibold text-green-600">{operation.successfulItems}</div>
            <div className="text-xs text-muted-foreground">Successful</div>
          </div>
          <div className="text-center p-3 rounded-lg bg-gray-100 dark:bg-gray-800">
            <div className="text-lg font-semibold text-red-600">{operation.failedItems}</div>
            <div className="text-xs text-muted-foreground">Failed</div>
          </div>
          <div className="text-center p-3 rounded-lg bg-gray-100 dark:bg-gray-800">
            <div className="text-lg font-semibold">{completedStages}/{operation.stages.length}</div>
            <div className="text-xs text-muted-foreground">Stages</div>
          </div>
          <div className="text-center p-3 rounded-lg bg-gray-100 dark:bg-gray-800">
            <div className="text-lg font-semibold">{formatTime(elapsedTime)}</div>
            <div className="text-xs text-muted-foreground">Elapsed</div>
          </div>
        </div>

        {/* Current Stage */}
        {currentStage && (
          <Alert>
            <Zap className="h-4 w-4" />
            <AlertDescription>
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">{currentStage.name}</div>
                  {currentStage.currentItem && (
                    <div className="text-sm text-muted-foreground mt-1">
                      Processing: {currentStage.currentItem}
                    </div>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium">{Math.round(currentStage.progress)}%</div>
                  {currentStage.completedItems !== undefined && currentStage.totalItems && (
                    <div className="text-xs text-muted-foreground">
                      {currentStage.completedItems}/{currentStage.totalItems}
                    </div>
                  )}
                </div>
              </div>
              <Progress value={currentStage.progress} className="mt-2" />
            </AlertDescription>
          </Alert>
        )}

        {/* Stage Details */}
        {showDetails && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              <span className="font-medium text-sm">Stages</span>
            </div>
            
            <div className={cn(
              "space-y-3",
              orientation === 'horizontal' && "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3"
            )}>
              {operation.stages.map((stage, index) => (
                <StageCard
                  key={stage.id}
                  stage={stage}
                  index={index + 1}
                  orientation={orientation}
                />
              ))}
            </div>
          </div>
        )}

        {/* Error Display */}
        {operation.status === 'error' && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <div className="font-medium mb-1">Operation Failed</div>
              {operation.stages.find(s => s.status === 'error')?.error || 'An unknown error occurred'}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}

interface StageCardProps {
  stage: BatchStage;
  index: number;
  orientation: 'horizontal' | 'vertical';
}

function StageCard({ stage, index, orientation }: StageCardProps) {
  const getStageIcon = (status: BatchStage['status']) => {
    switch (status) {
      case 'running':
        return <Loader2 className="h-3 w-3 animate-spin text-blue-600" />;
      case 'completed':
        return <CheckCircle2 className="h-3 w-3 text-green-600" />;
      case 'error':
        return <XCircle className="h-3 w-3 text-red-600" />;
      case 'paused':
        return <Pause className="h-3 w-3 text-yellow-600" />;
      default:
        return <Clock className="h-3 w-3 text-gray-400" />;
    }
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  };

  return (
    <div className={cn(
      "p-3 border rounded-lg transition-colors",
      stage.status === 'running' && "border-blue-200 bg-blue-50/50",
      stage.status === 'completed' && "border-green-200 bg-green-50/50",
      stage.status === 'error' && "border-red-200 bg-red-50/50",
      stage.status === 'paused' && "border-yellow-200 bg-yellow-50/50"
    )}>
      <div className="flex items-start gap-3">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded">
            {index.toString().padStart(2, '0')}
          </span>
          {getStageIcon(stage.status)}
          <div className="min-w-0 flex-1">
            <div className="font-medium text-sm truncate">{stage.name}</div>
            {stage.description && (
              <div className="text-xs text-muted-foreground truncate">
                {stage.description}
              </div>
            )}
          </div>
        </div>
      </div>

      {stage.status !== 'pending' && (
        <div className="mt-2 space-y-2">
          {stage.status === 'running' && (
            <>
              <Progress value={stage.progress} className="h-1.5" />
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{Math.round(stage.progress)}%</span>
                {stage.completedItems !== undefined && stage.totalItems && (
                  <span>{stage.completedItems}/{stage.totalItems}</span>
                )}
              </div>
              {stage.currentItem && (
                <div className="text-xs text-muted-foreground truncate">
                  {stage.currentItem}
                </div>
              )}
            </>
          )}

          {stage.status === 'completed' && stage.duration && (
            <div className="text-xs text-muted-foreground">
              Completed in {formatDuration(stage.duration)}
            </div>
          )}

          {stage.status === 'error' && stage.error && (
            <div className="text-xs text-red-600 truncate" title={stage.error}>
              {stage.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}