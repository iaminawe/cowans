/**
 * Shopify API service for collection management
 */

import { apiClient } from './api';

export interface ShopifyCollection {
  id: string;
  graphql_id: string;
  handle: string;
  title: string;
  description: string;
  products_count: number;
  image_url: string | null;
  has_icon: boolean;
  updated_at: string;
  metafields: Record<string, unknown>;
}

export interface IconUploadRequest {
  icon_path: string;
  alt_text?: string;
  style?: string;
  color?: string;
  keywords?: string[];
}

export interface GenerateAllIconsRequest {
  options: {
    only_missing?: boolean;
    style?: string;
    color?: string;
    batch_size?: number;
  };
}

export interface SyncIconRequest {
  local_icon_id: string;
}

export interface BatchSyncRequest {
  mappings: Array<{
    icon_id: number;
    collection_id: string;
    alt_text?: string;
  }>;
}

export interface SyncStatus {
  icon_id: number;
  collection_id: string;
  status: 'pending' | 'in_progress' | 'success' | 'failed' | 'retrying';
  shopify_image_id?: string;
  shopify_image_url?: string;
  error?: string;
  retry_count: number;
  processing_time: number;
}

export interface BatchSyncResult {
  success: boolean;
  summary: {
    total_icons: number;
    successful_syncs: number;
    failed_syncs: number;
    success_rate: number;
    total_processing_time: number;
    average_processing_time: number;
    total_retries: number;
    error_summary: Record<string, number>;
  };
  results: SyncStatus[];
  progress_log?: Array<{
    completed: number;
    total: number;
    icon_id: number;
    status: string;
    timestamp: string;
  }>;
}

export interface CollectionVerificationResult {
  collection_id: string;
  has_image: boolean;
  image_url?: string;
  title?: string;
  handle?: string;
  error?: string;
}

class ShopifyAPI {
  /**
   * Get all Shopify collections
   */
  async getCollections(): Promise<{ collections: ShopifyCollection[]; total: number }> {
    const response = await apiClient.get<{ collections: ShopifyCollection[]; total: number }>('/shopify/collections');
    return response;
  }

  /**
   * Upload an icon to a specific collection
   */
  async uploadCollectionIcon(collectionId: string, data: IconUploadRequest & Record<string, unknown>): Promise<{
    success: boolean;
    message?: string;
    image_url?: string;
    error?: string;
  }> {
    const response = await apiClient.post<any>(`/shopify/collections/${collectionId}/upload-icon`, data);
    return response;
  }

  /**
   * Generate icons for all collections
   */
  async generateAllIcons(data: GenerateAllIconsRequest & Record<string, unknown>): Promise<{
    success: boolean;
    message?: string;
    generated_count?: number;
    error?: string;
  }> {
    const response = await apiClient.post<any>('/shopify/collections/generate-all', data);
    return response;
  }

  /**
   * Sync a locally generated icon with a Shopify collection
   */
  async syncCollectionIcon(collectionId: string, data: SyncIconRequest & Record<string, unknown>): Promise<{
    success: boolean;
    message?: string;
    shopify_image_id?: string;
    shopify_image_url?: string;
    error?: string;
  }> {
    const response = await apiClient.post<any>(`/shopify/collections/${collectionId}/sync`, data);
    return response;
  }

  /**
   * Get collection by handle
   */
  async getCollectionByHandle(handle: string): Promise<ShopifyCollection | null> {
    try {
      const response = await apiClient.get<ShopifyCollection>(`/shopify/collections/handle/${handle}`);
      return response;
    } catch (error) {
      console.error('Error fetching collection by handle:', error);
      return null;
    }
  }

  /**
   * Check Shopify API status
   */
  async checkStatus(): Promise<{ connected: boolean; message?: string }> {
    try {
      const response = await apiClient.get<{ connected: boolean; message?: string }>('/shopify/status');
      return response;
    } catch (error) {
      return { connected: false, message: 'Failed to connect to Shopify' };
    }
  }

  /**
   * Enhanced single icon sync with retry support
   */
  async syncIconEnhanced(iconId: number, collectionId: string): Promise<SyncStatus> {
    const response = await apiClient.post<SyncStatus>('/icons/sync/single', {
      icon_id: iconId,
      collection_id: collectionId
    });
    return response;
  }

  /**
   * Batch sync multiple icons to collections
   */
  async syncIconsBatch(mappings: BatchSyncRequest['mappings']): Promise<BatchSyncResult> {
    const response = await apiClient.post<BatchSyncResult>('/icons/sync/batch', {
      mappings
    });
    return response;
  }

  /**
   * Verify which collections have images
   */
  async verifyCollectionImages(collectionIds: string[]): Promise<{
    success: boolean;
    summary: {
      total_collections: number;
      with_images: number;
      without_images: number;
      errors: number;
      coverage_percentage: number;
    };
    results: CollectionVerificationResult[];
  }> {
    const response = await apiClient.post<{
      success: boolean;
      summary: {
        total_collections: number;
        with_images: number;
        without_images: number;
        errors: number;
        coverage_percentage: number;
      };
      results: CollectionVerificationResult[];
    }>('/icons/sync/verify', {
      collection_ids: collectionIds
    });
    return response;
  }

  /**
   * Get sync status and statistics
   */
  async getSyncStatus(): Promise<{
    success: boolean;
    statistics: {
      total_icons: number;
      synced_icons: number;
      unsynced_icons: number;
      failed_syncs: number;
      sync_percentage: number;
      categories_with_shopify: number;
    };
    recent_syncs: Array<{
      icon_id: number;
      filename: string;
      category: string;
      synced_at: string;
      shopify_image_url: string;
    }>;
  }> {
    const response = await apiClient.get<{
      success: boolean;
      statistics: {
        total_icons: number;
        synced_icons: number;
        unsynced_icons: number;
        failed_syncs: number;
        sync_percentage: number;
        categories_with_shopify: number;
      };
      recent_syncs: Array<{
        icon_id: number;
        filename: string;
        category: string;
        synced_at: string;
        shopify_image_url: string;
      }>;
    }>('/icons/sync/status');
    return response;
  }

  /**
   * Retry all failed sync operations
   */
  async retryFailedSyncs(): Promise<{
    success: boolean;
    message: string;
    summary?: any;
    total_failed?: number;
    retried?: number;
  }> {
    const response = await apiClient.post<{
      success: boolean;
      message: string;
      summary?: any;
      total_failed?: number;
      retried?: number;
    }>('/icons/sync/retry-failed', {});
    return response;
  }
}

export const shopifyApi = new ShopifyAPI();