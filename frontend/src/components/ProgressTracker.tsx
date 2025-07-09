import React from 'react';
import { cn } from "@/lib/utils";

interface Stage {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error' | 'skipped';
  progress?: number;
  startTime?: string;
  endTime?: string;
  estimatedTime?: number; // in seconds
  message?: string;
  error?: string;
}

interface ProgressTrackerProps {
  stages: Stage[];
  className?: string;
  orientation?: 'horizontal' | 'vertical';
  showDetails?: boolean;
}

const STATUS_COLORS = {
  pending: 'bg-gray-200',
  running: 'bg-blue-500',
  completed: 'bg-green-500',
  error: 'bg-red-500',
  skipped: 'bg-gray-400'
};

const STATUS_ICONS = {
  pending: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <circle cx="12" cy="12" r="10" strokeWidth="2" />
    </svg>
  ),
  running: (
    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  ),
  completed: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
    </svg>
  ),
  error: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
    </svg>
  ),
  skipped: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
    </svg>
  )
};

export function ProgressTracker({
  stages,
  className,
  orientation = 'vertical',
  showDetails = true
}: ProgressTrackerProps) {
  const calculateElapsedTime = (startTime: string, endTime?: string) => {
    const start = new Date(startTime).getTime();
    const end = endTime ? new Date(endTime).getTime() : Date.now();
    const elapsed = Math.floor((end - start) / 1000);
    const mins = Math.floor(elapsed / 60);
    const secs = elapsed % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const formatEstimatedTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const overallProgress = stages.reduce((acc, stage) => {
    if (stage.status === 'completed') return acc + 1;
    if (stage.status === 'running' && stage.progress) return acc + (stage.progress / 100);
    return acc;
  }, 0) / stages.length * 100;

  if (orientation === 'horizontal') {
    return (
      <div className={cn("w-full", className)}>
        {/* Overall Progress Bar */}
        <div className="mb-4">
          <div className="flex justify-between text-sm mb-1">
            <span className="font-medium">Overall Progress</span>
            <span>{Math.round(overallProgress)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-primary h-2 rounded-full transition-all duration-300"
              style={{ width: `${overallProgress}%` }}
            />
          </div>
        </div>

        {/* Horizontal Stage Display */}
        <div className="relative">
          <div className="flex items-center justify-between">
            {stages.map((stage, index) => (
              <div key={stage.id} className="flex-1 relative">
                {/* Connection Line */}
                {index < stages.length - 1 && (
                  <div 
                    className={cn(
                      "absolute top-5 left-1/2 w-full h-0.5",
                      stage.status === 'completed' ? 'bg-green-500' : 'bg-gray-300'
                    )}
                  />
                )}
                
                {/* Stage Indicator */}
                <div className="relative z-10 flex flex-col items-center">
                  <div className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center text-white",
                    STATUS_COLORS[stage.status]
                  )}>
                    {STATUS_ICONS[stage.status]}
                  </div>
                  <div className="mt-2 text-center">
                    <div className="text-sm font-medium">{stage.name}</div>
                    {showDetails && stage.status === 'running' && stage.startTime && (
                      <div className="text-xs text-muted-foreground">
                        {calculateElapsedTime(stage.startTime)}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Vertical orientation
  return (
    <div className={cn("space-y-4", className)}>
      {/* Overall Progress */}
      <div className="rounded-lg border bg-card p-4">
        <div className="flex justify-between text-sm mb-2">
          <span className="font-medium">Overall Progress</span>
          <span>{Math.round(overallProgress)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div 
            className="bg-primary h-2 rounded-full transition-all duration-300"
            style={{ width: `${overallProgress}%` }}
          />
        </div>
      </div>

      {/* Stage List */}
      <div className="space-y-3">
        {stages.map((stage, index) => (
          <div 
            key={stage.id} 
            className={cn(
              "rounded-lg border p-4 transition-all",
              stage.status === 'running' && "border-primary bg-primary/5",
              stage.status === 'error' && "border-red-500 bg-red-50",
              stage.status === 'completed' && "bg-green-50",
              stage.status === 'skipped' && "opacity-60"
            )}
          >
            <div className="flex items-start gap-3">
              {/* Status Icon */}
              <div className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center text-white flex-shrink-0",
                STATUS_COLORS[stage.status]
              )}>
                {STATUS_ICONS[stage.status]}
              </div>

              {/* Stage Details */}
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <h4 className="font-medium">{stage.name}</h4>
                  {stage.estimatedTime && stage.status === 'pending' && (
                    <span className="text-xs text-muted-foreground">
                      Est. {formatEstimatedTime(stage.estimatedTime)}
                    </span>
                  )}
                </div>

                {/* Progress Bar for Running Stage */}
                {stage.status === 'running' && stage.progress !== undefined && (
                  <div className="mb-2">
                    <div className="w-full bg-gray-200 rounded-full h-1.5">
                      <div 
                        className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${stage.progress}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Status Message */}
                {stage.message && (
                  <p className="text-sm text-muted-foreground">{stage.message}</p>
                )}

                {/* Error Message */}
                {stage.error && (
                  <p className="text-sm text-red-600 mt-1">{stage.error}</p>
                )}

                {/* Timing Information */}
                {showDetails && (
                  <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                    {stage.startTime && (
                      <span>
                        Started: {new Date(stage.startTime).toLocaleTimeString()}
                      </span>
                    )}
                    {stage.endTime && (
                      <span>
                        Completed: {new Date(stage.endTime).toLocaleTimeString()}
                      </span>
                    )}
                    {stage.status === 'running' && stage.startTime && (
                      <span>
                        Elapsed: {calculateElapsedTime(stage.startTime)}
                      </span>
                    )}
                    {stage.status === 'completed' && stage.startTime && stage.endTime && (
                      <span>
                        Duration: {calculateElapsedTime(stage.startTime, stage.endTime)}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}