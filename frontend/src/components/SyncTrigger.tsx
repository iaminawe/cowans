import React from 'react';
import { cn } from "@/lib/utils";

interface SyncTriggerProps {
  className?: string;
  onSync: () => void;
  isLoading?: boolean;
}

export function SyncTrigger({ className, onSync, isLoading = false }: SyncTriggerProps) {
  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Manual Sync</h3>
          <p className="text-sm text-muted-foreground">
            Trigger a manual sync to update products from Etilize
          </p>
        </div>
        <button
          onClick={onSync}
          disabled={isLoading}
          className={cn(
            "inline-flex items-center justify-center rounded-md px-4 py-2",
            "bg-primary text-primary-foreground hover:bg-primary/90",
            "disabled:pointer-events-none disabled:opacity-50"
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
            'Run Sync'
          )}
        </button>
      </div>
    </div>
  );
}