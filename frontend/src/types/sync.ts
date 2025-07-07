// Types for parallel batch sync system

export interface ParallelSyncConfig {
  enabled: boolean;
  minWorkers: number;
  maxWorkers: number;
  batchSize: number;
  priority: 'low' | 'normal' | 'high';
  operationType: 'create' | 'update' | 'delete' | 'all';
  strategy: 'speed' | 'cost' | 'balanced';
  retryAttempts: number;
  timeout: number;
}

export interface WorkerPoolStatus {
  active: number;
  idle: number;
  total: number;
  utilization: number;
  tasksQueued: number;
  tasksProcessing: number;
  tasksCompleted: number;
  tasksFailed: number;
}

export interface SyncMetrics {
  operationsPerSecond: number;
  successRate: number;
  errorRate: number;
  averageLatency: number;
  totalOperations: number;
  successfulOperations: number;
  failedOperations: number;
  retryCount: number;
  throughput: number;
  estimatedTimeRemaining: number;
  memoryUsage: number;
  cpuUsage: number;
}

export interface BulkOperation {
  id: string;
  type: 'create' | 'update' | 'delete' | 'mixed';
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  totalItems: number;
  processedItems: number;
  successfulItems: number;
  failedItems: number;
  progress: number;
  startTime: Date;
  endTime?: Date;
  estimatedEndTime?: Date;
  errors: BulkOperationError[];
  results?: BulkOperationResult;
  config: ParallelSyncConfig;
}

export interface BulkOperationError {
  itemId: string;
  message: string;
  code: string;
  timestamp: Date;
  retryable: boolean;
}

export interface BulkOperationResult {
  successfulIds: string[];
  failedIds: string[];
  skippedIds: string[];
  summary: {
    total: number;
    successful: number;
    failed: number;
    skipped: number;
    duration: number;
  };
}

export interface SyncAlert {
  id: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  timestamp: Date;
  source: string;
  actionRequired: boolean;
  resolved: boolean;
}

export interface PerformancePrediction {
  estimatedDuration: number;
  estimatedCost: number;
  estimatedSuccessRate: number;
  recommendedWorkers: number;
  recommendedBatchSize: number;
  bottlenecks: string[];
  optimizationSuggestions: string[];
}

export interface QueueDepth {
  total: number;
  byPriority: {
    low: number;
    normal: number;
    high: number;
  };
  byOperation: {
    create: number;
    update: number;
    delete: number;
  };
  averageWaitTime: number;
  oldestItemAge: number;
}

export interface SystemResources {
  memory: {
    used: number;
    total: number;
    percentage: number;
  };
  cpu: {
    usage: number;
    cores: number;
  };
  network: {
    latency: number;
    throughput: number;
  };
}

export interface ParallelSyncStartRequest {
  config: ParallelSyncConfig;
  productIds?: string[];
  filters?: Record<string, any>;
}

export interface ParallelSyncStatusResponse {
  operations: BulkOperation[];
  metrics: SyncMetrics;
  workerPool: WorkerPoolStatus;
  queue: QueueDepth;
  resources: SystemResources;
  alerts: SyncAlert[];
}

export interface ParallelSyncResultsDownload {
  format: 'csv' | 'json' | 'xlsx';
  includeErrors: boolean;
  includeSuccesses: boolean;
  includeSkipped: boolean;
}