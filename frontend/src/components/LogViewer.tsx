import React, { useState } from 'react';
import { cn } from "@/lib/utils";

interface LogEntry {
  id: string;
  timestamp: string;
  status: 'success' | 'error' | 'running';
  message: string;
  details?: string;
}

interface LogViewerProps {
  className?: string;
  logs: LogEntry[];
}

export function LogViewer({ className, logs }: LogViewerProps) {
  const [filter, setFilter] = useState<'all' | 'success' | 'error' | 'running'>('all');
  const [searchTerm, setSearchTerm] = useState('');

  const filteredLogs = logs.filter(log => {
    const matchesFilter = filter === 'all' || log.status === filter;
    const matchesSearch = searchTerm === '' || 
      log.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (log.details && log.details.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesFilter && matchesSearch;
  });
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return (
          <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'error':
        return (
          <svg className="w-4 h-4 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'running':
        return (
          <svg className="w-4 h-4 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        );
      default:
        return null;
    }
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex-1 max-w-md">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search logs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className={cn(
                "w-full rounded-md border border-input bg-background pl-10 pr-3 py-2 text-sm",
                "placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring"
              )}
            />
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground hidden sm:inline">Filter:</span>
          <div className="flex gap-1">
            {(['all', 'success', 'error', 'running'] as const).map((status) => (
              <button
                key={status}
                onClick={() => setFilter(status)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                  "hover:bg-muted/80 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                  filter === status
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>
      
      {/* Logs Table */}
      <div className="rounded-md border bg-card overflow-hidden">
        {/* Header */}
        <div className="bg-muted/50 px-4 py-3 border-b">
          <div className="grid grid-cols-12 gap-4 text-sm font-medium">
            <div className="col-span-3">Timestamp</div>
            <div className="col-span-2">Status</div>
            <div className="col-span-7">Details</div>
          </div>
        </div>
        
        {/* Content */}
        <div className="divide-y max-h-96 overflow-y-auto">
          {filteredLogs.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-muted flex items-center justify-center">
                <svg className="w-6 h-6 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <p className="text-sm font-medium text-muted-foreground">
                {logs.length === 0 ? 'No sync logs available' : 'No logs match your filter'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {logs.length === 0 ? 'Run a sync to see activity here' : 'Try adjusting your search or filter'}
              </p>
            </div>
          ) : (
            filteredLogs.map((log) => (
              <div key={log.id} className="px-4 py-3 hover:bg-muted/20 transition-colors">
                <div className="grid grid-cols-12 gap-4">
                  <div className="col-span-3 text-sm text-muted-foreground">
                    <div className="font-mono">
                      {new Date(log.timestamp).toLocaleDateString()}
                    </div>
                    <div className="font-mono text-xs">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                  <div className="col-span-2">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(log.status)}
                      <span
                        className={cn(
                          "inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset",
                          {
                            "bg-green-50 text-green-700 ring-green-600/20":
                              log.status === "success",
                            "bg-red-50 text-red-700 ring-red-600/20":
                              log.status === "error",
                            "bg-blue-50 text-blue-700 ring-blue-600/20":
                              log.status === "running",
                          }
                        )}
                      >
                        {log.status}
                      </span>
                    </div>
                  </div>
                  <div className="col-span-7">
                    <div className="text-sm font-medium">{log.message}</div>
                    {log.details && (
                      <div className="mt-1 text-xs text-muted-foreground line-clamp-2">
                        {log.details}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
      
      {/* Footer */}
      {filteredLogs.length > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>Showing {filteredLogs.length} of {logs.length} entries</span>
          <span>Updated {new Date().toLocaleTimeString()}</span>
        </div>
      )}
    </div>
  );
}