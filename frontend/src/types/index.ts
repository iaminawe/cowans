// Central type exports for the Cowans Office Products frontend

// Product types
export * from './product';

// API response types
export * from './api';

// Re-export commonly used types for convenience
export type {
  ShopifyProduct,
  ShopifyProductVariant,
  ShopifyProductImage,
  ShopifyProductOption,
  ShopifyProductSEO,
  ShopifyMetafield,
  ProductFormData,
  ProductFormErrors,
  ProductValidationResult,
  ProductCreationResponse,
  ProductUpdateResponse,
  ProductDeletionResponse,
  ProductTypeOption,
  VendorOption
} from './product';

export type {
  ApiResponse,
  PaginatedResponse,
  OperationResponse,
  AuthUser,
  User,
  LoginResponse,
  RegisterResponse,
  UserProfileResponse,
  ImportStatus,
  ImportValidationResult,
  ImportHistoryItem,
  ImportBatch,
  ShopifySyncStatus,
  ShopifySyncHistoryItem,
  ShopifySyncConfiguration,
  SyncMode,
  SyncFlag,
  SyncableProduct,
  ProductType,
  Collection,
  CollectionSuggestion,
  SyncHistoryItem,
  StagedChange,
  ParallelSyncOperation,
  BulkOperationResult,
  FTPConnectionStatus,
  FTPFile,
  ExternalServiceConfig,
  SyncMetrics,
  DashboardStats,
  ApiError,
  ValidationError,
  WebSocketMessage,
  ProgressUpdate
} from './api';

// Type utility functions
export {
  isApiError,
  isApiResponse,
  isPaginatedResponse
} from './api';

// Product utility functions
export {
  createDefaultVariant,
  createDefaultProduct,
  validateSKU,
  validatePrice,
  validateHandle,
  generateHandle,
  validateProductForm,
  DEFAULT_PRODUCT_TYPES,
  DEFAULT_VENDORS
} from './product';