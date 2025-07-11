import type {
  AuthUser,
  LoginResponse,
  RegisterResponse,
  UserProfileResponse,
  SyncHistoryItem,
  ImportHistoryItem,
  ImportStatus,
  ImportValidationResult,
  ShopifySyncConfiguration,
  ShopifySyncStatus,
  ShopifySyncHistoryItem,
  SyncMode,
  SyncFlag,
  ImportBatch,
  SyncableProduct,
  Collection,
  XorosoftConnectionStatus,
  XorosoftInventoryComparison,
  XorosoftSyncHistory,
  FTPConnectionStatus,
  EtilizeFTPScanResult,
  EtilizeImportHistory,
  EnhancedSyncMetrics,
  StagedChangesResponse,
  SyncBatchesResponse,
  ShopifySyncManagerStatus,
  WorkerPoolStatus,
  QueueDepth,
  SystemResources,
  SyncAlert,
  BulkOperation
} from '../types/api';

// Type alias for backwards compatibility
type User = AuthUser;

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string = process.env.REACT_APP_API_URL || '/api') {
    this.baseUrl = baseUrl;
    this.token = localStorage.getItem('auth_token');
    
    // Development fallback if no token
    if (!this.token && process.env.NODE_ENV === 'development') {
      this.token = 'dev-token';
    }
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      credentials: 'include', // Include credentials for CORS
      ...options,
    };

    if (this.token) {
      config.headers = {
        ...config.headers,
        Authorization: `Bearer ${this.token}`,
      };
    }

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        // Special handling for auth errors
        if (response.status === 401) {
          // Clear invalid token
          this.token = null;
          localStorage.removeItem('auth_token');
          throw new Error('Authentication required. Please log in again.');
        }
        
        const error = await response.json().catch(() => ({ message: 'Network error' }));
        throw new Error(error.message || `HTTP ${response.status}`);
      }

      return response.json();
    } catch (error) {
      // Handle network errors more gracefully
      if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
        throw new Error('Network error: Unable to connect to server. Please check if the backend is running.');
      }
      throw error;
    }
  }

  async login(email: string, password: string): Promise<LoginResponse> {
    const response = await this.request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    
    this.token = response.access_token;
    localStorage.setItem('auth_token', response.access_token);
    
    return response;
  }

  async register(email: string, password: string, firstName: string, lastName: string): Promise<RegisterResponse> {
    const response = await this.request<RegisterResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ 
        email, 
        password, 
        first_name: firstName, 
        last_name: lastName 
      }),
    });
    
    this.token = response.access_token;
    localStorage.setItem('auth_token', response.access_token);
    
    return response;
  }

  async getCurrentUser(): Promise<UserProfileResponse> {
    return this.request<UserProfileResponse>('/auth/me');
  }

  async logout(): Promise<void> {
    if (this.token) {
      try {
        await this.request<{ message: string }>('/auth/logout', {
          method: 'POST',
        });
      } catch (error) {
        console.error('Logout API call failed:', error);
      }
    }
    
    this.token = null;
    localStorage.removeItem('auth_token');
  }

  async triggerSync(): Promise<{ message: string }> {
    return this.request<{ message: string }>('/sync/trigger', {
      method: 'POST',
    });
  }

  async getSyncHistory(): Promise<SyncHistoryItem[]> {
    return this.request<SyncHistoryItem[]>('/sync/history');
  }

  isAuthenticated(): boolean {
    return this.token !== null;
  }

  // Generic HTTP methods for other services
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  // Import-specific methods
  async uploadImportFile(file: File): Promise<{file_path: string}> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${this.baseUrl}/import/upload`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.token}`,
      },
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Upload failed' }));
      throw new Error(error.error || 'Upload failed');
    }
    
    return response.json();
  }

  async validateImport(filePath: string, config?: unknown): Promise<ImportValidationResult> {
    return this.request<ImportValidationResult>('/import/validate', {
      method: 'POST',
      body: JSON.stringify({ file_path: filePath, config }),
    });
  }

  async executeImport(filePath: string, config?: unknown): Promise<{import_id: string}> {
    return this.request<{import_id: string}>('/import/execute', {
      method: 'POST',
      body: JSON.stringify({ file_path: filePath, config }),
    });
  }

  async getImportStatus(importId: string): Promise<ImportStatus> {
    return this.request<ImportStatus>(`/import/status/${importId}`);
  }

  async getImportHistory(): Promise<{history: ImportHistoryItem[]}> {
    return this.request<{history: ImportHistoryItem[]}>('/import/history');
  }

  async cancelImport(importId: string): Promise<{success: boolean}> {
    return this.request<{success: boolean}>(`/import/cancel/${importId}`, {
      method: 'POST',
    });
  }

  // Shopify sync methods
  async createShopifySync(config: ShopifySyncConfiguration): Promise<{sync_id: string}> {
    return this.request<{sync_id: string}>('/shopify/sync/create', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async executeShopifySync(config: ShopifySyncConfiguration): Promise<{sync_id: string}> {
    return this.request<{sync_id: string}>('/shopify/sync/execute', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async getShopifySyncStatus(syncId: string): Promise<ShopifySyncStatus> {
    return this.request<ShopifySyncStatus>(`/shopify/sync/status/${syncId}`);
  }

  async getShopifySyncHistory(): Promise<{history: ShopifySyncHistoryItem[]}> {
    return this.request<{history: ShopifySyncHistoryItem[]}>('/shopify/sync/history');
  }

  async cancelShopifySync(syncId: string): Promise<{success: boolean}> {
    return this.request<{success: boolean}>(`/shopify/sync/cancel/${syncId}`, {
      method: 'POST',
    });
  }

  async getShopifySyncModes(): Promise<{modes: SyncMode[], flags: SyncFlag[]}> {
    return this.request<{modes: SyncMode[], flags: SyncFlag[]}>('/shopify/sync/modes');
  }

  async getSyncableProducts(params?: {
    import_batch_id?: number;
    category?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{products: SyncableProduct[], total: number, offset: number, limit: number}> {
    const queryParams = new URLSearchParams();
    if (params?.import_batch_id) queryParams.append('import_batch_id', params.import_batch_id.toString());
    if (params?.category) queryParams.append('category', params.category);
    if (params?.status) queryParams.append('status', params.status);
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.offset) queryParams.append('offset', params.offset.toString());
    
    const url = `/shopify/products/syncable${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    return this.request<{products: SyncableProduct[], total: number, offset: number, limit: number}>(url);
  }

  async getImportBatches(): Promise<{batches: ImportBatch[]}> {
    return this.request<{batches: ImportBatch[]}>('/shopify/batches');
  }

  async validateShopifyConfig(config: unknown): Promise<{valid: boolean, errors?: string[]}> {
    return this.request<{valid: boolean, errors?: string[]}>('/shopify/validate', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  // Collections API
  async getCollections(params?: {
    status?: string;
    include_archived?: boolean;
  }): Promise<{collections: Collection[], total: number}> {
    const queryParams = new URLSearchParams();
    if (params?.status) queryParams.append('status', params.status);
    if (params?.include_archived) queryParams.append('include_archived', params.include_archived.toString());
    
    const url = `/collections${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    return this.request<{collections: Collection[], total: number}>(url);
  }

  async getCollection(collectionId: number): Promise<Collection> {
    return this.request<Collection>(`/collections/${collectionId}`);
  }

  async createCollection(data: {
    name: string;
    handle: string;
    description?: string;
    rules_type?: 'manual' | 'automatic';
    rules_conditions?: unknown[];
    disjunctive?: boolean;
    status?: string;
    sort_order?: string;
    seo_title?: string;
    seo_description?: string;
  }): Promise<{message: string, collection: Collection}> {
    return this.request<{message: string, collection: Collection}>('/collections/create', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateCollection(collectionId: number, data: unknown): Promise<{message: string, collection: Collection}> {
    return this.request<{message: string, collection: Collection}>(`/collections/${collectionId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async addProductsToCollection(collectionId: number, productIds: number[]): Promise<{message: string, added_count: number}> {
    return this.request<{message: string, added_count: number}>(`/collections/${collectionId}/products`, {
      method: 'POST',
      body: JSON.stringify({ product_ids: productIds }),
    });
  }

  async removeProductsFromCollection(collectionId: number, productIds: number[]): Promise<{message: string, removed_count: number}> {
    return this.request<{message: string, removed_count: number}>(`/collections/${collectionId}/products`, {
      method: 'DELETE',
      body: JSON.stringify({ product_ids: productIds }),
    });
  }

  async syncCollectionToShopify(collectionId: number): Promise<{message: string, shopify_collection_id: string}> {
    return this.request<{message: string, shopify_collection_id: string}>(`/collections/${collectionId}/sync-to-shopify`, {
      method: 'POST',
    });
  }

  async getProductTypesSummary(): Promise<{product_types: Array<{value: string, label: string, count: number}>, total: number}> {
    return this.request<{product_types: Array<{value: string, label: string, count: number}>, total: number}>('/collections/product-types-summary');
  }

  async getAICollectionSuggestions(productTypes: string[]): Promise<{suggestions: Array<{name: string, handle: string, description: string, product_types: string[], estimated_products: number, confidence_score: number}>}> {
    return this.request<{suggestions: Array<{name: string, handle: string, description: string, product_types: string[], estimated_products: number, confidence_score: number}>}>('/collections/ai-suggestions', {
      method: 'POST',
      body: JSON.stringify({ product_types: productTypes }),
    });
  }

  async getManagedCollections(): Promise<{collections: Collection[]}> {
    return this.request<{collections: Collection[]}>('/collections/managed');
  }

  // Parallel Sync Methods
  async startParallelSync(request: unknown): Promise<{operation_id: string}> {
    return this.request<{operation_id: string}>('/shopify/sync/parallel/start', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async stopParallelSync(operationId: string): Promise<{success: boolean}> {
    return this.request<{success: boolean}>(`/shopify/sync/parallel/stop/${operationId}`, {
      method: 'POST',
    });
  }

  async getParallelSyncStatus(): Promise<ShopifySyncManagerStatus> {
    return this.request<ShopifySyncManagerStatus>('/shopify/sync/parallel/status');
  }

  async cancelBulkOperation(operationId: string): Promise<{success: boolean}> {
    return this.request<{success: boolean}>(`/shopify/sync/bulk/cancel/${operationId}`, {
      method: 'POST',
    });
  }

  async retryBulkOperation(operationId: string): Promise<{operation_id: string}> {
    return this.request<{operation_id: string}>(`/shopify/sync/bulk/retry/${operationId}`, {
      method: 'POST',
    });
  }

  async downloadBulkOperationResults(operationId: string, config: unknown): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/shopify/sync/bulk/download/${operationId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.token}`,
      },
      body: JSON.stringify(config),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Download failed' }));
      throw new Error(error.message || 'Download failed');
    }

    return response.blob();
  }

  // Enhanced Sync API Methods
  async pullFromShopify(config: unknown): Promise<{batch_id: string}> {
    return this.request<{batch_id: string}>('/sync/shopify/pull', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async getStagedChanges(filters?: unknown): Promise<StagedChangesResponse> {
    const params = filters ? '?' + new URLSearchParams(filters as Record<string, string>).toString() : '';
    return this.request<StagedChangesResponse>(`/sync/staged${params}`);
  }

  async approveStaged(changeId: string): Promise<{success: boolean}> {
    return this.request<{success: boolean}>(`/sync/staged/${changeId}/approve`, {
      method: 'POST',
    });
  }

  async rejectStaged(changeId: string): Promise<{success: boolean}> {
    return this.request<{success: boolean}>(`/sync/staged/${changeId}/reject`, {
      method: 'POST',
    });
  }

  async bulkApproveStaged(changeIds: string[]): Promise<{success: boolean}> {
    return this.request<{success: boolean}>('/sync/staged/bulk-approve', {
      method: 'POST',
      body: JSON.stringify({ change_ids: changeIds }),
    });
  }

  async pushToShopify(config: unknown): Promise<{batch_id: string}> {
    return this.request<{batch_id: string}>('/sync/shopify/push', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async getSyncBatches(): Promise<SyncBatchesResponse> {
    return this.request<SyncBatchesResponse>('/sync/batches');
  }

  async rollbackSync(batchId: string): Promise<{success: boolean}> {
    return this.request<{success: boolean}>(`/sync/rollback/${batchId}`, {
      method: 'POST',
    });
  }

  // FTP and Etilize Methods
  async checkFTPConnection(): Promise<FTPConnectionStatus> {
    return this.request<FTPConnectionStatus>('/import/etilize/ftp/check');
  }

  async downloadFromFTP(config: unknown): Promise<{download_id: string}> {
    return this.request<{download_id: string}>('/import/etilize/ftp/download', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async getFTPDownloadStatus(downloadId: string): Promise<{status: string}> {
    return this.request<{status: string}>(`/import/etilize/ftp/download/${downloadId}/status`);
  }


  // Xorosoft Sync Methods
  async syncWithXorosoft(config: unknown): Promise<{sync_id: string}> {
    return this.request<{sync_id: string}>('/sync/xorosoft', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async getXorosoftSyncStatus(syncId: string): Promise<{status: string}> {
    return this.request<{status: string}>(`/sync/xorosoft/${syncId}/status`);
  }

  // Enhanced Sync API Methods - removed duplicates, using implementations with error handling at end of file

  // Shopify Sync Down Methods
  async startShopifySyncDown(options: unknown): Promise<{sync_id: string; batch_id?: string}> {
    try {
      const response = await this.request<any>('/shopify/sync-down/start', {
        method: 'POST',
        body: JSON.stringify(options),
      });
      // Handle both sync_id and batch_id responses
      return {
        sync_id: response.batch_id || response.sync_id,
        batch_id: response.batch_id
      };
    } catch (error) {
      console.error('Failed to start Shopify sync down:', error);
      throw error;
    }
  }

  async getShopifyCollections(): Promise<{collections: Array<{id: string, handle: string, title: string, products_count: number}>}> {
    return this.request<{collections: Array<{id: string, handle: string, title: string, products_count: number}>}>('/shopify/collections');
  }

  async getProductTypes(): Promise<{types: string[]}> {
    return this.request<{types: string[]}>('/shopify/product-types');
  }

  // Staged Changes Methods

  async stageProductChanges(data: {productIds: string[], source: string}): Promise<{success: boolean}> {
    return this.request<{success: boolean}>('/staged-changes/stage', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async approveChanges(changeIds: string[]): Promise<{success: boolean}> {
    return this.request<{success: boolean}>('/staged-changes/approve', {
      method: 'POST',
      body: JSON.stringify({ change_ids: changeIds }),
    });
  }

  async rejectChanges(changeIds: string[]): Promise<{success: boolean}> {
    return this.request<{success: boolean}>('/staged-changes/reject', {
      method: 'POST',
      body: JSON.stringify({ change_ids: changeIds }),
    });
  }

  async resolveConflict(changeId: string, resolution: unknown): Promise<{success: boolean}> {
    return this.request<{success: boolean}>(`/staged-changes/${changeId}/resolve`, {
      method: 'POST',
      body: JSON.stringify(resolution),
    });
  }

  // Shopify Sync Up Methods
  async getApprovedProducts(): Promise<{products: SyncableProduct[]}> {
    return this.request<{products: SyncableProduct[]}>('/shopify/approved-products');
  }

  async startShopifySyncUp(data: {productIds: string[], options: unknown}): Promise<{sync_id: string}> {
    return this.request<{sync_id: string}>('/shopify/sync-up/start', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async retryFailedUploads(productIds: string[]): Promise<{success: boolean}> {
    return this.request<{success: boolean}>('/shopify/sync-up/retry', {
      method: 'POST',
      body: JSON.stringify({ product_ids: productIds }),
    });
  }

  // Etilize Sync Methods
  async checkEtilizeFTPConnection(): Promise<FTPConnectionStatus> {
    return this.request<FTPConnectionStatus>('/etilize/ftp/check');
  }

  async scanEtilizeFTP(directory: string): Promise<EtilizeFTPScanResult> {
    return this.request<EtilizeFTPScanResult>('/etilize/ftp/scan', {
      method: 'POST',
      body: JSON.stringify({ directory }),
    });
  }

  async getEtilizeImportHistory(): Promise<EtilizeImportHistory> {
    return this.request<EtilizeImportHistory>('/etilize/import/history');
  }

  async startEtilizeImport(data: {filename: string, validate: boolean, archive: boolean}): Promise<{job_id: string}> {
    return this.request<{job_id: string}>('/etilize/import/start', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async saveEtilizeConfig(config: unknown): Promise<{success: boolean}> {
    return this.request<{success: boolean}>('/etilize/config', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  // Xorosoft Sync Methods
  async checkXorosoftConnection(): Promise<XorosoftConnectionStatus> {
    return this.request<XorosoftConnectionStatus>('/xorosoft/connection/check');
  }

  async getXorosoftInventoryComparison(): Promise<XorosoftInventoryComparison> {
    return this.request<XorosoftInventoryComparison>('/xorosoft/inventory/comparison');
  }

  async getXorosoftSyncHistory(): Promise<XorosoftSyncHistory> {
    return this.request<XorosoftSyncHistory>('/xorosoft/sync/history');
  }

  async startXorosoftSync(data: {mode: string, skus?: string[], updateStock: boolean, updatePrice: boolean}): Promise<{sync_id: string}> {
    return this.request<{sync_id: string}>('/xorosoft/sync/start', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async saveXorosoftConfig(config: unknown): Promise<{success: boolean}> {
    return this.request<{success: boolean}>('/xorosoft/config', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  // Enhanced Sync Methods
  async getSyncMetrics(): Promise<any> {
    try {
      return await this.request<any>('/sync/metrics');
    } catch (error) {
      console.warn('Failed to get sync metrics, using fallback:', error);
      // Return fallback metrics when backend is not ready
      return {
        productsToSync: 0,
        productsWithChanges: 0,
        stagedChanges: 0,
        approvedChanges: 0,
        lastSyncTime: null,
        nextScheduledSync: null
      };
    }
  }

  async getRecentSyncActivity(): Promise<any[]> {
    try {
      return await this.request<any[]>('/sync/recent-activity');
    } catch (error) {
      console.warn('Failed to get recent activity, using fallback:', error);
      // Return empty activity when backend is not ready
      return [];
    }
  }
}

export const apiClient = new ApiClient();
// Re-export types for compatibility
export type { 
  User,
  AuthUser,
  LoginResponse,
  RegisterResponse,
  UserProfileResponse,
  SyncHistoryItem, 
  ImportHistoryItem, 
  ImportStatus, 
  ImportValidationResult,
  ShopifySyncConfiguration,
  ShopifySyncStatus,
  ShopifySyncHistoryItem,
  SyncMode,
  SyncFlag,
  ImportBatch,
  SyncableProduct,
  Collection
} from '../types/api';