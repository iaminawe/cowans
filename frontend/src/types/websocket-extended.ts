// Extended WebSocket Types for all application-specific events

import { BaseWebSocketData, WebSocketData } from './websocket';

// Extended Progress Data with all properties
export interface ExtendedProgressData extends BaseWebSocketData {
  message?: string;
  percentage?: number;
  current?: number;
  total?: number;
  operation_id?: string;
  progress_percentage?: number;
  current_step?: number;
  stages?: Array<{
    name: string;
    status: 'pending' | 'in_progress' | 'completed' | 'failed';
  }>;
}

// Extended Operation Start Data
export interface ExtendedOperationStartData extends BaseWebSocketData {
  operation_type: string;
  operation_name: string;
  estimated_duration?: number;
  type?: string;
  description?: string;
  total_steps?: number;
}

// Extended Operation Complete Data
export interface ExtendedOperationCompleteData extends BaseWebSocketData {
  operation_type: string;
  operation_name: string;
  duration: number;
  success: boolean;
  result?: unknown;
  status?: string;
}

// Extended Log Data
export interface ExtendedLogData extends BaseWebSocketData {
  message: string;
  level: 'debug' | 'info' | 'warning' | 'error';
  source?: string;
}

// Sync Update Data
export interface SyncUpdateData extends BaseWebSocketData {
  source: string;
  status: string;
  progress?: number;
  message?: string;
}

// Metrics Update Data
export interface MetricsUpdateData extends BaseWebSocketData {
  metrics: Record<string, unknown>;
}

// Icon Generation Data
export interface BatchProgressData extends BaseWebSocketData {
  batch_id: string;
  completed: number;
  total: number;
  status: string;
  results?: Array<{
    product_id: string;
    success: boolean;
    error?: string;
  }>;
}

// Bulk Generation Progress Data
export interface BulkGenerationProgressData extends BaseWebSocketData {
  completed: number;
  total: number;
  status: string;
  results?: unknown[];
}

// Shopify Sync Data
export interface ShopifySyncProgressData extends BaseWebSocketData {
  progress: number;
  processed: number;
  total: number;
  errors: number;
  currentBatch: number;
  totalBatches: number;
  currentProduct?: string;
  rate?: number;
  estimatedTimeRemaining?: number;
}

// Shopify Sync Error Data
export interface ShopifySyncErrorData extends BaseWebSocketData {
  message: string;
  error?: unknown;
}

// Etilize FTP Data
export interface EtilizeFTPStatusData extends BaseWebSocketData {
  connected: boolean;
  lastChecked?: string;
  error?: string;
}

// Etilize New File Data
export interface EtilizeNewFileData extends BaseWebSocketData {
  filename: string;
  size?: number;
  modified?: string;
}

// Etilize Import Progress Data
export interface EtilizeImportProgressData extends BaseWebSocketData {
  job: {
    id: string;
    filename: string;
    status: string;
    progress: number;
    fileSize?: number;
    downloadedSize?: number;
    recordsProcessed?: number;
    recordsTotal?: number;
    startTime?: string;
    endTime?: string;
    error?: string;
  };
}

// Xorosoft Data Types
export interface XorosoftInventoryUpdateData extends BaseWebSocketData {
  sku: string;
  productTitle: string;
  currentStock: number;
  xorosoftStock: number;
  difference: number;
  lastUpdated: string;
  location: string;
  status: 'in-sync' | 'needs-update' | 'low-stock' | 'out-of-stock';
}

export interface XorosoftSyncProgressData extends BaseWebSocketData {
  completed: number;
  total: number;
  result?: {
    synced: number;
    failed: number;
    skipped: number;
  };
}

export interface XorosoftStockMovementData extends BaseWebSocketData {
  sku: string;
  type: 'adjustment' | 'sale' | 'return' | 'transfer';
  quantity: number;
  previousStock: number;
  newStock: number;
  reason?: string;
  timestamp: string;
}

// Shopify Sync Up Data
export interface ShopifySyncUpProgressData extends BaseWebSocketData {
  updatedCount: number;
  totalCount: number;
  errors: number;
  currentSku?: string;
  phase: string;
  detailedProgress?: Record<string, unknown>;
  isLastBatch?: boolean;
}

// Extended Event Map
export interface ExtendedWebSocketEventMap {
  // Standard events
  'log': ExtendedLogData;
  'progress': ExtendedProgressData;
  'status': BaseWebSocketData & { status: string; message?: string };
  'error': BaseWebSocketData & { error: string; message?: string };
  'complete': ExtendedOperationCompleteData;
  'operation_start': ExtendedOperationStartData;
  'operation_progress': ExtendedProgressData;
  'operation_log': ExtendedLogData;
  'operation_complete': ExtendedOperationCompleteData;
  
  // Custom events
  'sync-update': SyncUpdateData;
  'metrics-update': MetricsUpdateData;
  'batch_progress': BatchProgressData;
  'bulk_generation_progress': BulkGenerationProgressData;
  'shopify-sync-progress': ShopifySyncProgressData;
  'shopify-sync-up-progress': ShopifySyncUpProgressData;
  'shopify-sync-up-error': ShopifySyncErrorData;
  'etilize-ftp-status': EtilizeFTPStatusData;
  'etilize-new-file': EtilizeNewFileData;
  'etilize-import-progress': EtilizeImportProgressData;
  'xorosoft-inventory-update': XorosoftInventoryUpdateData;
  'xorosoft-sync-progress': XorosoftSyncProgressData;
  'xorosoft-stock-movement': XorosoftStockMovementData;
}

// Union type for all extended data
export type ExtendedWebSocketData = 
  | ExtendedLogData
  | ExtendedProgressData
  | ExtendedOperationStartData
  | ExtendedOperationCompleteData
  | SyncUpdateData
  | MetricsUpdateData
  | BatchProgressData
  | BulkGenerationProgressData
  | ShopifySyncProgressData
  | ShopifySyncUpProgressData
  | ShopifySyncErrorData
  | EtilizeFTPStatusData
  | EtilizeNewFileData
  | EtilizeImportProgressData
  | XorosoftInventoryUpdateData
  | XorosoftSyncProgressData
  | XorosoftStockMovementData;

// Helper type for custom event callbacks
export type CustomWebSocketCallback<T = unknown> = (data: T) => void;