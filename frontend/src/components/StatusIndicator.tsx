import React from 'react';
import { cn } from "@/lib/utils";

interface StatusIndicatorProps {
  className?: string;
  status: 'idle' | 'running' | 'success' | 'error';
  lastSync?: string;
}

export function StatusIndicator({ className, status, lastSync }: StatusIndicatorProps) {
  const getStatusConfig = () => {
    switch (status) {
      case 'running':
        return {
          color: 'bg-blue-500',
          text: 'Sync in Progress',
          icon: (
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          )
        };
      case 'success':
        return {
          color: 'bg-green-500',
          text: 'Last Sync Successful',
          icon: (
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          )
        };
      case 'error':
        return {
          color: 'bg-red-500',
          text: 'Last Sync Failed',
          icon: (
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          )
        };
      default:
        return {
          color: 'bg-gray-400',
          text: 'Ready to Sync',
          icon: (
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v8m4-4H8" />
            </svg>
          )
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div className={cn("flex items-center gap-4", className)}>
      <div className="flex items-center gap-2">
        <div className={cn("h-3 w-3 rounded-full", config.color)} />
        <span className="text-sm font-medium">{config.text}</span>
        {config.icon}
      </div>
      
      {lastSync && status !== 'running' && (
        <div className="text-xs text-muted-foreground">
          Last sync: {new Date(lastSync).toLocaleString()}
        </div>
      )}
    </div>
  );
}