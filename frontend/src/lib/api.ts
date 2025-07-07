interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_admin: boolean;
  created_at?: string;
  last_login?: string;
}

interface LoginResponse {
  access_token: string;
  user: User;
}

interface RegisterResponse {
  access_token: string;
  user: User;
  message: string;
}

interface UserProfileResponse {
  user: User;
}

interface SyncHistoryItem {
  id: string;
  timestamp: string;
  status: 'success' | 'error' | 'running';
  message: string;
  details?: string;
}

interface ImportHistoryItem {
  import_id: string;
  success: boolean;
  total_records: number;
  imported_records: number;
  failed_records: number;
  duration_seconds: number;
  batch_id: number;
  errors: string[];
}

interface ImportStatus {
  import_id: string;
  status: string;
  stage: string;
  total_records: number;
  processed_records: number;
  imported_records: number;
  failed_records: number;
  progress_percentage: number;
  current_operation: string;
  errors: string[];
}

interface ImportValidationResult {
  valid: boolean;
  total_records?: number;
  sample_records?: any[];
  available_columns?: string[];
  message?: string;
  error?: string;
}

interface ShopifySyncConfiguration {
  mode: string;
  flags: string[];
  batch_size?: number;
  max_workers?: number;
  shop_url?: string;
  access_token?: string;
  data_source?: string;
  limit?: number;
  start_from?: number;
  filters?: Record<string, any>;
  import_batch_id?: number;
}

interface ShopifySyncStatus {
  sync_id: string;
  status: string;
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

interface ShopifySyncHistoryItem {
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

interface SyncMode {
  value: string;
  label: string;
  description: string;
}

interface SyncFlag {
  value: string;
  label: string;
  description: string;
}

interface ImportBatch {
  id: number;
  filename: string;
  status: string;
  total_records: number;
  product_count: number;
  created_at?: string;
  completed_at?: string;
}

interface SyncableProduct {
  id: number;
  sku: string;
  title: string;
  category: string;
  status: string;
  shopify_id?: string;
  shopify_status: string;
  last_synced?: string;
  has_conflicts: boolean;
  primary_source: string;
  price?: number;
}

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string = 'http://localhost:3560/api') {
    this.baseUrl = baseUrl;
    this.token = localStorage.getItem('auth_token');
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    if (this.token) {
      config.headers = {
        ...config.headers,
        Authorization: `Bearer ${this.token}`,
      };
    }

    const response = await fetch(url, config);
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Network error' }));
      throw new Error(error.message || `HTTP ${response.status}`);
    }

    return response.json();
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

  async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: any): Promise<T> {
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

  async validateImport(filePath: string, config?: any): Promise<ImportValidationResult> {
    return this.request<ImportValidationResult>('/import/validate', {
      method: 'POST',
      body: JSON.stringify({ file_path: filePath, config }),
    });
  }

  async executeImport(filePath: string, config?: any): Promise<{import_id: string}> {
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

  async validateShopifyConfig(config: Partial<ShopifySyncConfiguration>): Promise<{valid: boolean, errors?: string[]}> {
    return this.request<{valid: boolean, errors?: string[]}>('/shopify/validate', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  // Collections API
  async getCollections(params?: {
    status?: string;
    include_archived?: boolean;
  }): Promise<{collections: any[], total: number}> {
    const queryParams = new URLSearchParams();
    if (params?.status) queryParams.append('status', params.status);
    if (params?.include_archived) queryParams.append('include_archived', params.include_archived.toString());
    
    const url = `/collections${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    return this.request<{collections: any[], total: number}>(url);
  }

  async getCollection(collectionId: number): Promise<any> {
    return this.request<any>(`/collections/${collectionId}`);
  }

  async createCollection(data: {
    name: string;
    handle: string;
    description?: string;
    rules_type?: 'manual' | 'automatic';
    rules_conditions?: any[];
    disjunctive?: boolean;
    status?: string;
    sort_order?: string;
    seo_title?: string;
    seo_description?: string;
  }): Promise<{message: string, collection: any}> {
    return this.request<{message: string, collection: any}>('/collections/create', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateCollection(collectionId: number, data: any): Promise<{message: string, collection: any}> {
    return this.request<{message: string, collection: any}>(`/collections/${collectionId}`, {
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

  async getProductTypesSummary(): Promise<{product_types: any[], total: number}> {
    return this.request<{product_types: any[], total: number}>('/collections/product-types-summary');
  }

  async getAICollectionSuggestions(productTypes: string[]): Promise<{suggestions: any[]}> {
    return this.request<{suggestions: any[]}>('/collections/ai-suggestions', {
      method: 'POST',
      body: JSON.stringify({ product_types: productTypes }),
    });
  }

  async getManagedCollections(): Promise<{collections: any[]}> {
    return this.request<{collections: any[]}>('/collections/managed');
  }

  // Parallel Sync Methods
  async startParallelSync(request: any): Promise<{operation_id: string}> {
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

  async getParallelSyncStatus(): Promise<any> {
    return this.request<any>('/shopify/sync/parallel/status');
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

  async downloadBulkOperationResults(operationId: string, config: any): Promise<Blob> {
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
}

export const apiClient = new ApiClient();
export type { 
  User,
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
  SyncableProduct
};