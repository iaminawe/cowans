// Comprehensive API Response Types for Cowans Office Products

// Base API Response Types
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
  errors?: string[];
}

export interface PaginatedResponse<T = unknown> {
  data: T[];
  total: number;
  offset: number;
  limit: number;
  page?: number;
  total_pages?: number;
}

export interface OperationResponse {
  success: boolean;
  message: string;
  operation_id?: string;
  timestamp?: string;
}

// Auth Response Types
export interface AuthUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_admin: boolean;
  created_at?: string;
  last_login?: string;
}

// Legacy compatibility
export type User = AuthUser;

export interface LoginResponse {
  access_token: string;
  refresh_token?: string;
  user: AuthUser;
  expires_in?: number;
}

export interface RegisterResponse {
  access_token: string;
  refresh_token?: string;
  user: AuthUser;
  message: string;
}

export interface UserProfileResponse {
  user: AuthUser;
}

// Import Types
export interface ImportStatus {
  import_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  stage: string;
  total_records: number;
  processed_records: number;
  imported_records: number;
  failed_records: number;
  progress_percentage: number;
  current_operation: string;
  errors: string[];
  warnings?: string[];
  started_at?: string;
  completed_at?: string;
}

export interface ImportValidationResult {
  valid: boolean;
  total_records?: number;
  sample_records?: Record<string, unknown>[];
  available_columns?: string[];
  message?: string;
  error?: string;
  warnings?: string[];
}

export interface ImportHistoryItem {
  import_id: string;
  success: boolean;
  total_records: number;
  imported_records: number;
  failed_records: number;
  duration_seconds: number;
  batch_id: number;
  errors: string[];
  created_at?: string;
  completed_at?: string;
}

export interface ImportBatch {
  id: number;
  filename: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  total_records: number;
  product_count: number;
  created_at?: string;
  completed_at?: string;
}

// Shopify Sync Types
export interface ShopifySyncStatus {
  sync_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'queued';
  mode: string;
  total_products: number;
  successful_uploads: number;
  failed_uploads: number;
  skipped_uploads: number;
  progress_percentage: number;
  current_operation: string;
  errors: string[];
  warnings: string[];
  created_at?: string;
  started_at?: string;
  completed_at?: string;
}

export interface ShopifySyncHistoryItem {
  sync_id: string;
  status: string;
  mode: string;
  total_products: number;
  successful_uploads: number;
  failed_uploads: number;
  duration_seconds?: number;
  created_at?: string;
  completed_at?: string;
}

export interface ShopifySyncConfiguration {
  mode: string;
  flags: string[];
  batch_size?: number;
  max_workers?: number;
  shop_url?: string;
  access_token?: string;
  data_source?: string;
  limit?: number;
  start_from?: number;
  filters?: Record<string, unknown>;
  import_batch_id?: number;
}

export interface SyncMode {
  value: string;
  label: string;
  description: string;
}

export interface SyncFlag {
  value: string;
  label: string;
  description: string;
}

// Product Types
export interface SyncableProduct {
  id: number;
  sku: string;
  title: string;
  category: string;
  status: 'draft' | 'active' | 'inactive';
  shopify_id?: string;
  shopify_status: string;
  last_synced?: string;
  has_conflicts: boolean;
  primary_source: string;
  price?: number;
}

export interface ProductType {
  value: string;
  label: string;
  category?: string;
  count?: number;
}

// Collection Types
export interface Collection {
  id: number;
  name: string;
  handle: string;
  description?: string;
  rules_type?: 'manual' | 'automatic';
  rules_conditions?: Record<string, unknown>[];
  disjunctive?: boolean;
  status: 'draft' | 'active' | 'archived';  // Fixed: Made non-optional with specific union type
  sort_order?: string;
  seo_title?: string;
  seo_description?: string;
  product_count?: number;
  products_count?: number; // Alternative name for compatibility
  created_at?: string;
  updated_at?: string;
  // Shopify-specific properties
  shopify_collection_id?: string;
  shopify_synced_at?: string;
  shopify_sync_status?: string;
}

export interface CollectionSuggestion {
  name: string;
  handle: string;
  description: string;
  product_types: string[];
  estimated_products: number;
  confidence_score: number;
}

// Sync History Types
export interface SyncHistoryItem {
  id: string;
  timestamp: string;
  status: 'success' | 'error' | 'running';
  message: string;
  details?: string;
  operation_type?: string;
  duration_seconds?: number;
}

// Staged Changes Types
export interface StagedChange {
  id: string;
  product_id: string;
  change_type: 'create' | 'update' | 'delete';
  field_changes: Record<string, {
    old_value: unknown;
    new_value: unknown;
  }>;
  source: string;
  status: 'pending' | 'approved' | 'rejected' | 'conflict';
  has_conflicts: boolean;
  created_at: string;
  updated_at?: string;
}

// Parallel Sync Types
export interface ParallelSyncOperation {
  operation_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  total_items: number;
  processed_items: number;
  failed_items: number;
  success_rate: number;
  started_at: string;
  completed_at?: string;
  error_summary?: Record<string, number>;
}

export interface BulkOperationResult {
  operation_id: string;
  success: boolean;
  total_processed: number;
  successful_operations: number;
  failed_operations: number;
  results: Array<{
    item_id: string;
    status: 'success' | 'failed';
    error?: string;
  }>;
}

// FTP and External Service Types
export interface FTPConnectionStatus {
  connected: boolean;
  last_connection?: string;
  lastChecked?: string; // For UI compatibility
  server_info?: {
    host: string;
    port: number;
    username: string;
  };
  error?: string;
}

export interface FTPFile {
  name: string;
  size: number;
  modified: string;
  type: 'file' | 'directory';
  permissions?: string;
  isNew?: boolean; // For UI state
}

export interface ExternalServiceConfig {
  service_name: string;
  enabled: boolean;
  connection_string?: string;
  api_key?: string;
  last_sync?: string;
  settings: Record<string, unknown>;
}

// Metrics and Analytics Types
export interface SyncMetrics {
  total_syncs: number;
  successful_syncs: number;
  failed_syncs: number;
  success_rate: number;
  average_duration: number;
  total_products_synced: number;
  last_sync_time?: string;
  sync_frequency: {
    hourly: number;
    daily: number;
    weekly: number;
  };
}

export interface DashboardStats {
  total_products: number;
  synced_products: number;
  pending_products: number;
  failed_products: number;
  last_sync: string;
  sync_status: 'idle' | 'running' | 'error';
  active_operations: number;
}

// Error Types
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  timestamp: string;
  request_id?: string;
}

export interface ValidationError {
  field: string;
  message: string;
  code?: string;
  value?: unknown;
}

// WebSocket Types
export interface WebSocketMessage<T = unknown> {
  type: string;
  data: T;
  timestamp: string;
  id?: string;
}

export interface ProgressUpdate {
  operation_id: string;
  progress_percentage: number;
  current_item: number;
  total_items: number;
  current_operation: string;
  eta_seconds?: number;
}

// Xorosoft Sync Types
export interface XorosoftConfig {
  apiUrl: string;
  apiKey: string;
  syncMode: 'full' | 'incremental' | 'changes-only';
  syncSchedule: 'manual' | 'hourly' | 'daily' | 'realtime';
  inventoryThreshold: number;
  priceUpdateEnabled: boolean;
  stockUpdateEnabled: boolean;
  locationMapping: Record<string, string>;
}

export interface InventoryItem {
  sku: string;
  productTitle: string;
  currentStock: number;
  xorosoftStock: number;
  difference: number;
  lastUpdated: string;
  location: string;
  status: 'in-sync' | 'needs-update' | 'low-stock' | 'out-of-stock';
}

export interface SyncResult {
  totalItems: number;
  updatedItems: number;
  failedItems: number;
  skippedItems: number;
  duration: number;
  timestamp: string;
}

export interface StockMovement {
  sku: string;
  type: 'increase' | 'decrease' | 'adjustment';
  quantity: number;
  previousStock: number;
  newStock: number;
  reason: string;
  timestamp: string;
}

export interface XorosoftSyncHistory {
  results: SyncResult[];
  movements: StockMovement[];
}

export interface XorosoftInventoryComparison {
  items: InventoryItem[];
}

export interface XorosoftConnectionStatus {
  connected: boolean;
  lastSync?: string;
}

// Etilize Sync Types
export interface EtilizeConfig {
  ftpHost: string;
  ftpUsername: string;
  ftpPassword: string;
  ftpDirectory: string;
  autoArchive: boolean;
  filePattern: string;
  processingMode: 'validate' | 'import' | 'validate-and-import';
}

export interface EtilizeImportJob {
  job_id: string;
  filename: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  total_records: number;
  processed_records: number;
  imported_records: number;
  failed_records: number;
  created_at: string;
  completed_at?: string;
  error_message?: string;
}

export interface EtilizeImportHistory {
  jobs: EtilizeImportJob[];
}

export interface EtilizeFTPScanResult {
  files: FTPFile[];
}

// Enhanced Sync Types
export interface EnhancedSyncMetrics {
  productsToSync: number;
  productsWithChanges: number;
  stagedChanges: number;
  approvedChanges: number;
  pendingApprovals: number;
  failedSyncs: number;
  successRate: number;
  lastSyncTime?: string;
}

export interface EnhancedSyncStatus {
  isRunning: boolean;
  currentStage: string;
  progress: number;
  eta?: string;
  errors: string[];
  warnings: string[];
}

export interface SyncBatch {
  batch_id: string;
  type: 'pull' | 'push';
  status: 'pending' | 'running' | 'completed' | 'failed';
  total_items: number;
  processed_items: number;
  failed_items: number;
  created_at: string;
  completed_at?: string;
}

export interface SyncBatchesResponse {
  batches: SyncBatch[];
}

export interface StagedChangesResponse {
  changes: StagedChange[];
}

// Shopify Sync Manager Types
export interface WorkerPoolStatus {
  totalWorkers: number;
  activeWorkers: number;
  idleWorkers: number;
  queuedTasks: number;
  completedTasks: number;
  failedTasks: number;
}

export interface QueueDepth {
  pending: number;
  processing: number;
  completed: number;
  failed: number;
}

export interface SystemResources {
  cpuUsage: number;
  memoryUsage: number;
  diskUsage: number;
  networkIO: number;
}

export interface SyncAlert {
  id: string;
  level: 'info' | 'warning' | 'error';
  message: string;
  timestamp: string;
  operation?: string;
}

export interface BulkOperation {
  operation_id: string;
  type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  total_items: number;
  processed_items: number;
  failed_items: number;
  created_at: string;
  completed_at?: string;
}

export interface ShopifySyncManagerStatus {
  isRunning: boolean;
  currentOperation: string;
  totalOperations: number;
  completedOperations: number;
  failedOperations: number;
  progress: number;
  eta?: string;
  operations: BulkOperation[];
  metrics?: EnhancedSyncMetrics;
  workerPool?: WorkerPoolStatus;
  queue?: QueueDepth;
  resources?: SystemResources;
  alerts?: SyncAlert[];
}

// Utility Types
export type ApiResponseWithData<T> = ApiResponse<T> & { data: T };
export type ApiResponseWithPagination<T> = ApiResponse<PaginatedResponse<T>>;

// Type Guards
export function isApiError(obj: unknown): obj is ApiError {
  return typeof obj === 'object' && obj !== null && 'code' in obj && 'message' in obj;
}

export function isApiResponse<T>(obj: unknown): obj is ApiResponse<T> {
  return typeof obj === 'object' && obj !== null && 'success' in obj;
}

export function isPaginatedResponse<T>(obj: unknown): obj is PaginatedResponse<T> {
  return typeof obj === 'object' && obj !== null && 'data' in obj && 'total' in obj;
}