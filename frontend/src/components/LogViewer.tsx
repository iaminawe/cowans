import React from 'react';
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
  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Sync History</h3>
          <p className="text-sm text-muted-foreground">
            View recent product sync activity and results
          </p>
        </div>
      </div>
      
      <div className="relative">
        <div className="rounded-md border">
          <div className="bg-muted px-4 py-3 border-b">
            <div className="grid grid-cols-12 gap-4">
              <div className="col-span-3">Timestamp</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-7">Details</div>
            </div>
          </div>
          <div className="divide-y">
            {logs.length === 0 ? (
              <div className="px-4 py-3 text-sm text-muted-foreground">
                No sync logs available
              </div>
            ) : (
              logs.map((log) => (
                <div key={log.id} className="px-4 py-3">
                  <div className="grid grid-cols-12 gap-4">
                    <div className="col-span-3 text-sm">
                      {log.timestamp}
                    </div>
                    <div className="col-span-2">
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
                    <div className="col-span-7">
                      <div className="text-sm">{log.message}</div>
                      {log.details && (
                        <div className="mt-1 text-xs text-muted-foreground">
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
      </div>
    </div>
  );
}