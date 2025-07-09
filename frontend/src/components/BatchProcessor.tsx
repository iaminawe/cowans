import React, { useState, useEffect } from 'react';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';
import { 
  Play, 
  Pause, 
  Square, 
  Upload, 
  Download, 
  Settings, 
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  BarChart3,
  FileText,
  Trash2
} from 'lucide-react';

interface BatchConfig {
  batch_size: number;
  max_workers: number;
  timeout_seconds: number;
  retry_attempts: number;
  retry_delay: number;
  memory_limit_mb: number;
  enable_parallel: boolean;
  checkpoint_interval: number;
}

interface BatchProgress {
  batch_id: string;
  status: string;
  total_items: number;
  processed_items: number;
  successful_items: number;
  failed_items: number;
  skipped_items: number;
  current_batch: number;
  total_batches: number;
  progress_percentage: number;
  throughput_per_second: number;
  error_rate: number;
  elapsed_time: string;
  estimated_completion?: string;
  start_time: string;
}

interface BatchStats {
  active_batches: number;
  completed_batches: number;
  failed_batches: number;
  total_items_across_batches: number;
  total_processed_items: number;
  memory_usage_mb: number;
  config: BatchConfig;
}

export function BatchProcessor() {
  const [batches, setBatches] = useState<BatchProgress[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<string | null>(null);
  const [config, setConfig] = useState<BatchConfig | null>(null);
  const [stats, setStats] = useState<BatchStats | null>(null);
  const [activeTab, setActiveTab] = useState<'batches' | 'create' | 'config' | 'stats'>('batches');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form states
  const [newBatchItems, setNewBatchItems] = useState<string>('');
  const [processorType, setProcessorType] = useState('sample_product');
  
  const { subscribe } = useWebSocket();

  useEffect(() => {
    loadBatches();
    loadConfig();
    loadStats();
    
    // Set up refresh interval
    const interval = setInterval(() => {
      loadBatches();
      loadStats();
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Subscribe to batch-related WebSocket events
    const unsubscribeOperationStart = subscribe('operation_start', (data) => {
      if (data.type === 'batch_processing') {
        loadBatches();
      }
    });

    const unsubscribeOperationProgress = subscribe('operation_progress', (data) => {
      setBatches(prev => prev.map(batch => 
        batch.batch_id === data.operation_id 
          ? { ...batch, progress_percentage: data.progress_percentage || 0 }
          : batch
      ));
    });

    const unsubscribeOperationComplete = subscribe('operation_complete', (data) => {
      loadBatches();
      loadStats();
    });

    return () => {
      unsubscribeOperationStart();
      unsubscribeOperationProgress();
      unsubscribeOperationComplete();
    };
  }, [subscribe]);

  const loadBatches = async () => {
    try {
      const response = await apiClient.get<{batches: BatchProgress[]}>('/batch/list');
      setBatches(response.batches || []);
    } catch (error) {
      console.error('Failed to load batches:', error);
    }
  };

  const loadConfig = async () => {
    try {
      const response = await apiClient.get<BatchConfig>('/batch/config');
      setConfig(response);
    } catch (error) {
      console.error('Failed to load config:', error);
    }
  };

  const loadStats = async () => {
    try {
      const response = await apiClient.get<BatchStats>('/batch/stats');
      setStats(response);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const createBatch = async () => {
    if (!newBatchItems.trim()) {
      setError('Please provide items to process');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Parse items (expecting JSON array or CSV)
      let items;
      try {
        items = JSON.parse(newBatchItems);
      } catch {
        // Try parsing as CSV
        const lines = newBatchItems.trim().split('\n');
        const headers = lines[0].split(',').map(h => h.trim());
        items = lines.slice(1).map((line, index) => {
          const values = line.split(',').map(v => v.trim());
          const item: any = { id: `item_${index}` };
          headers.forEach((header, i) => {
            item[header] = values[i] || '';
          });
          return item;
        });
      }

      if (!Array.isArray(items) || items.length === 0) {
        throw new Error('No valid items found');
      }

      const response = await apiClient.post<{batch_id: string, message: string, total_items: number, batch_type: string}>('/batch/create', {
        items,
        type: processorType
      });

      const batchId = response.batch_id;
      
      // Start processing immediately
      await apiClient.post(`/batch/process/${batchId}`, {
        processor_type: processorType
      });

      setNewBatchItems('');
      loadBatches();
      setActiveTab('batches');
      
    } catch (error: any) {
      setError(error.message || 'Failed to create batch');
    } finally {
      setIsLoading(false);
    }
  };

  const cancelBatch = async (batchId: string) => {
    try {
      await apiClient.post(`/batch/cancel/${batchId}`);
      loadBatches();
    } catch (error: any) {
      setError(error.message || 'Failed to cancel batch');
    }
  };

  const updateConfig = async (newConfig: Partial<BatchConfig>) => {
    try {
      const response = await apiClient.put<{message: string, config: BatchConfig}>('/batch/config', newConfig);
      setConfig(response.config);
      loadStats();
    } catch (error: any) {
      setError(error.message || 'Failed to update configuration');
    }
  };

  const cleanupOldBatches = async () => {
    try {
      await apiClient.post('/batch/cleanup?max_age_hours=24');
      loadBatches();
      loadStats();
    } catch (error: any) {
      setError(error.message || 'Failed to cleanup batches');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Activity className="h-5 w-5 text-blue-500 animate-pulse" />;
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'completed_with_errors':
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'cancelled':
        return <Square className="h-5 w-5 text-gray-500" />;
      default:
        return <Clock className="h-5 w-5 text-gray-400" />;
    }
  };

  const formatDuration = (duration: string) => {
    try {
      const parts = duration.split(':');
      if (parts.length >= 3) {
        const hours = parseInt(parts[0]);
        const minutes = parseInt(parts[1]);
        const seconds = Math.round(parseFloat(parts[2]));
        
        if (hours > 0) {
          return `${hours}h ${minutes}m ${seconds}s`;
        } else if (minutes > 0) {
          return `${minutes}m ${seconds}s`;
        } else {
          return `${seconds}s`;
        }
      }
    } catch {
      return duration;
    }
    return duration;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Batch Processor</h2>
          <p className="text-muted-foreground">
            Efficiently process large datasets with parallel batch operations
          </p>
        </div>
        
        {stats && (
          <div className="flex items-center space-x-4 text-sm">
            <div className="flex items-center space-x-1">
              <Activity className="h-4 w-4" />
              <span>{stats.active_batches} active</span>
            </div>
            <div className="flex items-center space-x-1">
              <BarChart3 className="h-4 w-4" />
              <span>{stats.memory_usage_mb.toFixed(1)} MB</span>
            </div>
          </div>
        )}
      </div>

      {/* Navigation Tabs */}
      <div className="border-b">
        <nav className="-mb-px flex space-x-8">
          {[
            { id: 'batches', label: 'Active Batches', icon: FileText },
            { id: 'create', label: 'Create Batch', icon: Upload },
            { id: 'config', label: 'Configuration', icon: Settings },
            { id: 'stats', label: 'Statistics', icon: BarChart3 }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={cn(
                "flex items-center space-x-2 py-2 px-1 border-b-2 font-medium text-sm",
                activeTab === tab.id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-gray-300"
              )}
            >
              <tab.icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <XCircle className="h-5 w-5 text-red-400" />
            <div className="ml-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="ml-auto text-red-400 hover:text-red-600"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Tab Content */}
      {activeTab === 'batches' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium">Active Batches</h3>
            <button
              onClick={cleanupOldBatches}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Cleanup Old
            </button>
          </div>

          {batches.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500">No active batches</p>
            </div>
          ) : (
            <div className="grid gap-4">
              {batches.map(batch => (
                <div
                  key={batch.batch_id}
                  className="border rounded-lg p-4 hover:bg-accent/50 cursor-pointer"
                  onClick={() => setSelectedBatch(
                    selectedBatch === batch.batch_id ? null : batch.batch_id
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      {getStatusIcon(batch.status)}
                      <div>
                        <p className="font-medium">{batch.batch_id}</p>
                        <p className="text-sm text-muted-foreground">
                          {batch.total_items} items • {batch.status}
                        </p>
                      </div>
                    </div>
                    
                    <div className="text-right">
                      <div className="text-sm font-medium">
                        {batch.progress_percentage.toFixed(1)}%
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {batch.throughput_per_second.toFixed(1)}/s
                      </div>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="mt-3">
                    <div className="h-2 bg-secondary rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary transition-all duration-500"
                        style={{ width: `${batch.progress_percentage}%` }}
                      />
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {selectedBatch === batch.batch_id && (
                    <div className="mt-4 pt-4 border-t grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground">Processed:</span>
                        <p className="font-medium">{batch.processed_items}/{batch.total_items}</p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Success:</span>
                        <p className="font-medium text-green-600">{batch.successful_items}</p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Failed:</span>
                        <p className="font-medium text-red-600">{batch.failed_items}</p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Duration:</span>
                        <p className="font-medium">{formatDuration(batch.elapsed_time)}</p>
                      </div>
                      
                      {batch.status === 'running' && (
                        <div className="col-span-2 md:col-span-4 mt-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              cancelBatch(batch.batch_id);
                            }}
                            className="inline-flex items-center px-3 py-1 border border-red-300 rounded-md text-sm font-medium text-red-700 bg-white hover:bg-red-50"
                          >
                            <Square className="h-4 w-4 mr-1" />
                            Cancel
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'create' && (
        <div className="space-y-6">
          <h3 className="text-lg font-medium">Create New Batch</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Processor Type
              </label>
              <select
                value={processorType}
                onChange={(e) => setProcessorType(e.target.value)}
                className="w-full border border-input rounded-md px-3 py-2"
              >
                <option value="sample_product">Sample Product Processor</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Items (JSON Array or CSV)
              </label>
              <textarea
                value={newBatchItems}
                onChange={(e) => setNewBatchItems(e.target.value)}
                placeholder={`JSON: [{"id": "1", "title": "Product 1", "sku": "SKU001"}, ...]
                
CSV:
title,sku,price
Product 1,SKU001,29.99
Product 2,SKU002,39.99`}
                rows={10}
                className="w-full border border-input rounded-md px-3 py-2 font-mono text-sm"
              />
            </div>

            <button
              onClick={createBatch}
              disabled={isLoading || !newBatchItems.trim()}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary hover:bg-primary/90 disabled:opacity-50"
            >
              {isLoading ? (
                <Activity className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              Create & Process Batch
            </button>
          </div>
        </div>
      )}

      {activeTab === 'config' && config && (
        <div className="space-y-6">
          <h3 className="text-lg font-medium">Batch Configuration</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium mb-2">
                Batch Size
              </label>
              <input
                type="number"
                value={config.batch_size}
                onChange={(e) => updateConfig({ batch_size: parseInt(e.target.value) })}
                min="1"
                max="1000"
                className="w-full border border-input rounded-md px-3 py-2"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Number of items to process in each batch
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Max Workers
              </label>
              <input
                type="number"
                value={config.max_workers}
                onChange={(e) => updateConfig({ max_workers: parseInt(e.target.value) })}
                min="1"
                max="16"
                className="w-full border border-input rounded-md px-3 py-2"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Maximum number of parallel workers
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Timeout (seconds)
              </label>
              <input
                type="number"
                value={config.timeout_seconds}
                onChange={(e) => updateConfig({ timeout_seconds: parseFloat(e.target.value) })}
                min="10"
                max="3600"
                className="w-full border border-input rounded-md px-3 py-2"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Memory Limit (MB)
              </label>
              <input
                type="number"
                value={config.memory_limit_mb}
                onChange={(e) => updateConfig({ memory_limit_mb: parseInt(e.target.value) })}
                min="64"
                max="4096"
                className="w-full border border-input rounded-md px-3 py-2"
              />
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={config.enable_parallel}
                onChange={(e) => updateConfig({ enable_parallel: e.target.checked })}
                className="rounded border-input"
              />
              <label className="text-sm font-medium">
                Enable Parallel Processing
              </label>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'stats' && stats && (
        <div className="space-y-6">
          <h3 className="text-lg font-medium">System Statistics</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center">
                <Activity className="h-8 w-8 text-blue-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-blue-900">Active Batches</p>
                  <p className="text-2xl font-bold text-blue-600">{stats.active_batches}</p>
                </div>
              </div>
            </div>

            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center">
                <CheckCircle className="h-8 w-8 text-green-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-green-900">Completed</p>
                  <p className="text-2xl font-bold text-green-600">{stats.completed_batches}</p>
                </div>
              </div>
            </div>

            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-center">
                <XCircle className="h-8 w-8 text-red-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-red-900">Failed</p>
                  <p className="text-2xl font-bold text-red-600">{stats.failed_batches}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="border rounded-lg p-4">
              <h4 className="font-medium mb-2">Processing Statistics</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total Items:</span>
                  <span className="font-medium">{stats.total_items_across_batches.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Processed:</span>
                  <span className="font-medium">{stats.total_processed_items.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Memory Usage:</span>
                  <span className="font-medium">{stats.memory_usage_mb.toFixed(1)} MB</span>
                </div>
              </div>
            </div>

            <div className="border rounded-lg p-4">
              <h4 className="font-medium mb-2">Current Configuration</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Batch Size:</span>
                  <span className="font-medium">{stats.config.batch_size}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Max Workers:</span>
                  <span className="font-medium">{stats.config.max_workers}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Parallel:</span>
                  <span className="font-medium">{stats.config.enable_parallel ? 'Yes' : 'No'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}