import React, { useEffect, useState } from 'react';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { cn } from '@/lib/utils';
import { CheckCircle, XCircle, Loader2, Info, AlertCircle } from 'lucide-react';

interface Operation {
  id: string;
  type: string;
  description: string;
  status: 'running' | 'success' | 'error' | 'cancelled';
  progress?: number;
  currentStep?: number;
  totalSteps?: number;
  message?: string;
  logs: LogEntry[];
  startTime: string;
  endTime?: string;
}

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
  source?: string;
}

interface OperationStatusProps {
  operationId?: string;
  className?: string;
  showLogs?: boolean;
  compact?: boolean;
}

export function OperationStatus({ 
  operationId, 
  className, 
  showLogs = true,
  compact = false 
}: OperationStatusProps) {
  const { subscribe } = useWebSocket();
  const [operations, setOperations] = useState<Map<string, Operation>>(new Map());
  const [activeOperationId, setActiveOperationId] = useState<string | null>(operationId || null);

  useEffect(() => {
    // Subscribe to operation events
    const unsubscribeStart = subscribe('operation_start', (data) => {
      const operation: Operation = {
        id: data.operation_id,
        type: data.type,
        description: data.description,
        status: 'running',
        totalSteps: data.total_steps,
        currentStep: 0,
        logs: [],
        startTime: new Date().toISOString()
      };
      
      setOperations(prev => {
        const updated = new Map(prev);
        updated.set(data.operation_id, operation);
        return updated;
      });
      
      if (!activeOperationId) {
        setActiveOperationId(data.operation_id);
      }
    });

    const unsubscribeProgress = subscribe('operation_progress', (data) => {
      setOperations(prev => {
        const updated = new Map(prev);
        const operation = updated.get(data.operation_id);
        
        if (operation) {
          operation.currentStep = data.current_step;
          operation.message = data.message;
          if (data.progress_percentage !== undefined) {
            operation.progress = data.progress_percentage;
          }
        }
        
        return updated;
      });
    });

    const unsubscribeLog = subscribe('operation_log', (data) => {
      setOperations(prev => {
        const updated = new Map(prev);
        const operation = updated.get(data.operation_id);
        
        if (operation) {
          operation.logs.push({
            timestamp: new Date().toISOString(),
            level: data.level,
            message: data.message,
            source: data.source
          });
        }
        
        return updated;
      });
    });

    const unsubscribeComplete = subscribe('operation_complete', (data) => {
      setOperations(prev => {
        const updated = new Map(prev);
        const operation = updated.get(data.operation_id);
        
        if (operation) {
          operation.status = data.status;
          operation.endTime = new Date().toISOString();
          operation.progress = 100;
        }
        
        return updated;
      });
    });

    return () => {
      unsubscribeStart();
      unsubscribeProgress();
      unsubscribeLog();
      unsubscribeComplete();
    };
  }, [subscribe, activeOperationId]);

  const activeOperation = activeOperationId ? operations.get(activeOperationId) : null;

  if (!activeOperation && compact) {
    return null;
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
      case 'success':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'error':
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <Info className="h-5 w-5 text-gray-500" />;
    }
  };

  const getLogIcon = (level: string) => {
    switch (level) {
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'warning':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      default:
        return <Info className="h-4 w-4 text-blue-500" />;
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  if (compact && activeOperation) {
    return (
      <div className={cn("flex items-center space-x-2", className)}>
        {getStatusIcon(activeOperation.status)}
        <span className="text-sm">
          {activeOperation.message || activeOperation.description}
        </span>
        {activeOperation.progress !== undefined && (
          <span className="text-sm text-muted-foreground">
            {Math.round(activeOperation.progress)}%
          </span>
        )}
      </div>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Operation List */}
      {operations.size > 0 && (
        <div className="space-y-2">
          {Array.from(operations.values()).map(operation => (
            <div
              key={operation.id}
              className={cn(
                "rounded-lg border p-4 cursor-pointer transition-colors",
                activeOperationId === operation.id
                  ? "border-primary bg-accent"
                  : "border-border hover:bg-accent/50"
              )}
              onClick={() => setActiveOperationId(operation.id)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3">
                  {getStatusIcon(operation.status)}
                  <div>
                    <h4 className="font-medium">{operation.description}</h4>
                    <p className="text-sm text-muted-foreground">
                      {operation.type} • Started {formatTime(operation.startTime)}
                    </p>
                  </div>
                </div>
                
                {operation.progress !== undefined && (
                  <div className="text-right">
                    <div className="text-sm font-medium">
                      {Math.round(operation.progress)}%
                    </div>
                    {operation.totalSteps && (
                      <div className="text-xs text-muted-foreground">
                        Step {operation.currentStep} of {operation.totalSteps}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {operation.message && (
                <p className="mt-2 text-sm text-muted-foreground">
                  {operation.message}
                </p>
              )}

              {/* Progress Bar */}
              {operation.status === 'running' && operation.progress !== undefined && (
                <div className="mt-3">
                  <div className="h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all duration-500"
                      style={{ width: `${operation.progress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Logs Panel */}
      {showLogs && activeOperation && activeOperation.logs.length > 0 && (
        <div className="rounded-lg border p-4">
          <h4 className="font-medium mb-3">Operation Logs</h4>
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {activeOperation.logs.map((log, index) => (
              <div
                key={index}
                className="flex items-start space-x-2 text-sm"
              >
                {getLogIcon(log.level)}
                <span className="text-muted-foreground">
                  {formatTime(log.timestamp)}
                </span>
                <span className="flex-1">
                  {log.message}
                  {log.source && (
                    <span className="text-muted-foreground ml-1">
                      [{log.source}]
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {operations.size === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          <Info className="h-8 w-8 mx-auto mb-2" />
          <p>No active operations</p>
        </div>
      )}
    </div>
  );
}