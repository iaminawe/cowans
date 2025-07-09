import React, { useState, useEffect, useRef } from 'react';
import { cn } from "@/lib/utils";

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug' | 'success';
  message: string;
  details?: string;
  source?: string;
  metadata?: Record<string, any>;
}

interface RealtimeLogViewerProps {
  className?: string;
  logs: LogEntry[];
  maxLogs?: number;
  autoScroll?: boolean;
  showTimestamp?: boolean;
  showLevel?: boolean;
  showSource?: boolean;
  onClear?: () => void;
}

const LOG_LEVEL_COLORS = {
  info: 'text-blue-600',
  warning: 'text-yellow-600',
  error: 'text-red-600',
  debug: 'text-gray-600',
  success: 'text-green-600'
};

const LOG_LEVEL_BG = {
  info: 'bg-blue-50',
  warning: 'bg-yellow-50',
  error: 'bg-red-50',
  debug: 'bg-gray-50',
  success: 'bg-green-50'
};

export function RealtimeLogViewer({
  className,
  logs,
  maxLogs = 1000,
  autoScroll = true,
  showTimestamp = true,
  showLevel = true,
  showSource = true,
  onClear
}: RealtimeLogViewerProps) {
  const [filter, setFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(autoScroll);
  const [expandedLogs, setExpandedLogs] = useState<Set<string>>(new Set());
  const logContainerRef = useRef<HTMLDivElement>(null);
  const wasAtBottomRef = useRef(true);

  // Auto-scroll effect
  useEffect(() => {
    if (isAutoScrollEnabled && logContainerRef.current) {
      const container = logContainerRef.current;
      const isAtBottom = container.scrollHeight - container.scrollTop === container.clientHeight;
      
      if (wasAtBottomRef.current || isAtBottom) {
        container.scrollTop = container.scrollHeight;
      }
    }
  }, [logs, isAutoScrollEnabled]);

  // Track scroll position
  const handleScroll = () => {
    if (logContainerRef.current) {
      const container = logContainerRef.current;
      const isAtBottom = Math.abs(container.scrollHeight - container.scrollTop - container.clientHeight) < 5;
      wasAtBottomRef.current = isAtBottom;
      
      // Disable auto-scroll if user scrolls up
      if (!isAtBottom && isAutoScrollEnabled) {
        setIsAutoScrollEnabled(false);
      }
    }
  };

  const toggleLogExpansion = (logId: string) => {
    setExpandedLogs(prev => {
      const newSet = new Set(prev);
      if (newSet.has(logId)) {
        newSet.delete(logId);
      } else {
        newSet.add(logId);
      }
      return newSet;
    });
  };

  const filteredLogs = logs.slice(-maxLogs).filter(log => {
    const matchesFilter = filter === 'all' || log.level === filter;
    const matchesSearch = searchTerm === '' || 
      log.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (log.details && log.details.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (log.source && log.source.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesFilter && matchesSearch;
  });

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      fractionalSecondDigits: 3
    });
  };

  const exportLogs = () => {
    const logData = filteredLogs.map(log => ({
      timestamp: log.timestamp,
      level: log.level,
      source: log.source,
      message: log.message,
      details: log.details,
      metadata: log.metadata
    }));
    
    const blob = new Blob([JSON.stringify(logData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs-${new Date().toISOString()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={cn("flex flex-col h-full", className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold">Real-time Logs</h3>
          <p className="text-sm text-muted-foreground">
            Live output from script execution
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsAutoScrollEnabled(!isAutoScrollEnabled)}
            className={cn(
              "px-3 py-1 rounded-md text-xs font-medium transition-colors",
              isAutoScrollEnabled
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {isAutoScrollEnabled ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
          </button>
          <button
            onClick={exportLogs}
            className="px-3 py-1 rounded-md text-xs font-medium bg-muted text-muted-foreground hover:bg-muted/80"
          >
            Export
          </button>
          {onClear && (
            <button
              onClick={onClear}
              className="px-3 py-1 rounded-md text-xs font-medium bg-muted text-muted-foreground hover:bg-muted/80"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Filters and Search */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center mb-4">
        <div className="flex-1">
          <input
            type="text"
            placeholder="Search logs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className={cn(
              "w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
              "placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring"
            )}
          />
        </div>
        
        <div className="flex gap-2">
          {(['all', 'info', 'warning', 'error', 'debug', 'success'] as const).map((level) => (
            <button
              key={level}
              onClick={() => setFilter(level)}
              className={cn(
                "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                filter === level
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              )}
            >
              {level.charAt(0).toUpperCase() + level.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Log Container */}
      <div className="flex-1 rounded-md border bg-black/95 overflow-hidden">
        <div 
          ref={logContainerRef}
          onScroll={handleScroll}
          className="h-full overflow-y-auto p-4 font-mono text-xs"
        >
          {filteredLogs.length === 0 ? (
            <div className="text-gray-500 text-center py-8">
              {logs.length === 0 ? 'No logs yet...' : 'No logs match your filter'}
            </div>
          ) : (
            <div className="space-y-1">
              {filteredLogs.map((log) => {
                const isExpanded = expandedLogs.has(log.id);
                return (
                  <div 
                    key={log.id} 
                    className={cn(
                      "rounded px-2 py-1 hover:bg-gray-900/50 cursor-pointer transition-colors",
                      LOG_LEVEL_BG[log.level]
                    )}
                    onClick={() => toggleLogExpansion(log.id)}
                  >
                    <div className="flex items-start gap-2">
                      {showTimestamp && (
                        <span className="text-gray-500 whitespace-nowrap">
                          {formatTimestamp(log.timestamp)}
                        </span>
                      )}
                      
                      {showLevel && (
                        <span className={cn(
                          "font-medium uppercase",
                          LOG_LEVEL_COLORS[log.level]
                        )}>
                          [{log.level}]
                        </span>
                      )}
                      
                      {showSource && log.source && (
                        <span className="text-purple-500">
                          {log.source}:
                        </span>
                      )}
                      
                      <span className="text-gray-100 flex-1 break-all">
                        {log.message}
                      </span>
                    </div>
                    
                    {(log.details || log.metadata) && (
                      <div className={cn(
                        "mt-2 ml-4 overflow-hidden transition-all duration-200",
                        isExpanded ? "max-h-96" : "max-h-0"
                      )}>
                        {log.details && (
                          <div className="text-gray-400 text-xs whitespace-pre-wrap">
                            {log.details}
                          </div>
                        )}
                        
                        {log.metadata && (
                          <div className="mt-2 text-gray-500 text-xs">
                            <pre>{JSON.stringify(log.metadata, null, 2)}</pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Status Bar */}
      <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
        <span>
          Showing {filteredLogs.length} of {logs.length} logs
        </span>
        <span>
          {logs.length > maxLogs && `(Limited to last ${maxLogs} logs)`}
        </span>
      </div>
    </div>
  );
}