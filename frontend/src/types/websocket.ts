// WebSocket Message Types

export interface BaseWebSocketData {
  timestamp: string;
  operation_id?: string;
}

export interface LogData extends BaseWebSocketData {
  message: string;
  level: 'debug' | 'info' | 'warning' | 'error';
  source?: string;
}

export interface ProgressData extends BaseWebSocketData {
  percentage?: number;
  current?: number;
  total?: number;
  message?: string;
  progress_percentage?: number;
  current_step?: number;
  stages?: Array<{
    name: string;
    status: 'pending' | 'in_progress' | 'completed' | 'failed';
  }>;
}

export interface StatusData extends BaseWebSocketData {
  status: 'idle' | 'running' | 'completed' | 'failed' | 'paused';
  message?: string;
}

export interface ErrorData extends BaseWebSocketData {
  error: string;
  stack?: string;
  code?: string;
}

export interface OperationStartData extends BaseWebSocketData {
  operation_type: string;
  operation_name: string;
  estimated_duration?: number;
  type?: string;
  description?: string;
  total_steps?: number;
}

export interface OperationCompleteData extends BaseWebSocketData {
  operation_type: string;
  operation_name: string;
  duration: number;
  success: boolean;
  result?: unknown;
  status?: string;
}

export interface SyncStatusData extends BaseWebSocketData {
  sync_type: 'shopify' | 'etilize' | 'xorosoft';
  status: 'syncing' | 'completed' | 'failed';
  progress?: number;
  items_processed?: number;
  items_total?: number;
}

export interface ImportStatusData extends BaseWebSocketData {
  import_type: string;
  filename: string;
  status: 'processing' | 'completed' | 'failed';
  progress?: number;
  records_processed?: number;
  records_total?: number;
  errors?: string[];
}

// Union type for all possible data types
export type WebSocketData = 
  | LogData 
  | ProgressData 
  | StatusData 
  | ErrorData 
  | OperationStartData 
  | OperationCompleteData 
  | SyncStatusData 
  | ImportStatusData;

// Message types with specific data
export interface WebSocketMessage<T extends WebSocketData = WebSocketData> {
  type: 'log' | 'progress' | 'status' | 'error' | 'complete' | 
        'operation_start' | 'operation_progress' | 'operation_log' | 
        'operation_complete' | 'sync_status' | 'import_status';
  data: T;
  timestamp: string;
}

// Typed message interfaces for specific message types
export interface LogMessage extends WebSocketMessage<LogData> {
  type: 'log' | 'operation_log';
}

export interface ProgressMessage extends WebSocketMessage<ProgressData> {
  type: 'progress' | 'operation_progress';
}

export interface StatusMessage extends WebSocketMessage<StatusData> {
  type: 'status';
}

export interface ErrorMessage extends WebSocketMessage<ErrorData> {
  type: 'error';
}

export interface OperationStartMessage extends WebSocketMessage<OperationStartData> {
  type: 'operation_start';
}

export interface OperationCompleteMessage extends WebSocketMessage<OperationCompleteData> {
  type: 'operation_complete' | 'complete';
}

export interface SyncStatusMessage extends WebSocketMessage<SyncStatusData> {
  type: 'sync_status';
}

export interface ImportStatusMessage extends WebSocketMessage<ImportStatusData> {
  type: 'import_status';
}

// Generic outgoing message interface
export interface OutgoingWebSocketMessage {
  type: string;
  data?: Record<string, unknown>;
  room?: string;
  operation_id?: string;
  // Allow additional properties for flexibility
  [key: string]: unknown;
}

// Subscription callback type
export type WebSocketCallback<T extends WebSocketData = WebSocketData> = (data: T) => void;

// Event map for type-safe subscriptions
export interface WebSocketEventMap {
  'log': LogData;
  'progress': ProgressData;
  'status': StatusData;
  'error': ErrorData;
  'complete': OperationCompleteData;
  'operation_start': OperationStartData;
  'operation_progress': ProgressData;
  'operation_log': LogData;
  'operation_complete': OperationCompleteData;
  'sync_status': SyncStatusData;
  'import_status': ImportStatusData;
  // Additional custom events
  [key: string]: BaseWebSocketData;
}