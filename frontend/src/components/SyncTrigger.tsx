import React from 'react';
import { cn } from "@/lib/utils";
import { StatusIndicator } from './StatusIndicator';

interface SyncTriggerProps {
  className?: string;
  onSync: () => void;
  isLoading?: boolean;
  lastSyncTime?: string;
  syncStatus?: 'idle' | 'running' | 'success' | 'error';
}

export function SyncTrigger({ 
  className, 
  onSync, 
  isLoading = false, 
  lastSyncTime,
  syncStatus = 'idle'
}: SyncTriggerProps) {
  const formatTimeAgo = (timestamp: string) => {
    const now = new Date().getTime();
    const then = new Date(timestamp).getTime();
    const diffInMinutes = Math.floor((now - then) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`;
    return `${Math.floor(diffInMinutes / 1440)}d ago`;
  };

  return (
    <div className={cn("space-y-6", className)}>
      {/* Sync Controls */}
      <div className="flex flex-col sm:flex-row gap-4 sm:items-center sm:justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <div className={cn(
              "w-3 h-3 rounded-full transition-colors",
              isLoading ? "bg-blue-500 animate-pulse" :
              syncStatus === 'success' ? "bg-green-500" :
              syncStatus === 'error' ? "bg-red-500" : "bg-gray-400"
            )} />
            <span className="text-sm font-medium">
              {isLoading ? 'Synchronizing...' :
               syncStatus === 'success' ? 'Ready for sync' :
               syncStatus === 'error' ? 'Last sync failed' : 'Waiting for sync'
              }
            </span>
          </div>
          {lastSyncTime && (
            <p className="text-sm text-muted-foreground">
              Last successful sync: {formatTimeAgo(lastSyncTime)}
            </p>
          )}
        </div>
        
        <div className="flex items-center gap-3">
          <button
            onClick={onSync}
            disabled={isLoading}
            className={cn(
              "inline-flex items-center justify-center rounded-md px-6 py-3",
              "bg-primary text-primary-foreground hover:bg-primary/90",
              "disabled:pointer-events-none disabled:opacity-50",
              "transition-all duration-200 font-medium",
              "shadow-sm hover:shadow-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
              isLoading && "cursor-not-allowed"
            )}
          >
            {isLoading ? (
              <>
                <svg
                  className="mr-2 h-4 w-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Syncing...
              </>
            ) : (
              <>
                <svg className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Start Sync
              </>
            )}
          </button>
        </div>
      </div>
      
      {/* Status Information */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
            <svg className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium">Source</p>
            <p className="text-xs text-muted-foreground">Etilize FTP</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
          <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
            <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium">Status</p>
            <p className="text-xs text-muted-foreground">
              {isLoading ? 'Processing...' : 
               syncStatus === 'success' ? 'Ready' :
               syncStatus === 'error' ? 'Failed' : 'Idle'
              }
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
          <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center">
            <svg className="w-4 h-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium">Target</p>
            <p className="text-xs text-muted-foreground">Shopify Store</p>
          </div>
        </div>
      </div>
      
      <StatusIndicator 
        status={isLoading ? 'running' : syncStatus} 
        lastSync={lastSyncTime}
      />
    </div>
  );
}