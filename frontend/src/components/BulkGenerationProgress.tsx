import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { CheckCircle2, XCircle, Loader2, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface GenerationResult {
  collection_id: string;
  collection_name: string;
  status: 'pending' | 'generating' | 'completed' | 'failed';
  error?: string;
  icon_url?: string;
}

interface BulkGenerationProgressProps {
  isGenerating: boolean;
  progress: {
    current: number;
    total: number;
  };
  results: GenerationResult[];
  onCancel?: () => void;
  className?: string;
}

export function BulkGenerationProgress({
  isGenerating,
  progress,
  results,
  onCancel,
  className
}: BulkGenerationProgressProps) {
  const completedCount = results.filter(r => r.status === 'completed').length;
  const failedCount = results.filter(r => r.status === 'failed').length;
  const progressPercentage = progress.total > 0 ? (progress.current / progress.total) * 100 : 0;

  if (!isGenerating && results.length === 0) {
    return null;
  }

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Bulk Generation Progress</CardTitle>
          {isGenerating && onCancel && (
            <Button size="sm" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Overall Progress */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Overall Progress</span>
            <span className="text-muted-foreground">
              {progress.current} / {progress.total}
            </span>
          </div>
          <Progress value={progressPercentage} className="h-2" />
          <div className="flex gap-4 text-sm">
            <div className="flex items-center gap-1">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              <span>{completedCount} completed</span>
            </div>
            {failedCount > 0 && (
              <div className="flex items-center gap-1">
                <XCircle className="w-4 h-4 text-red-500" />
                <span>{failedCount} failed</span>
              </div>
            )}
          </div>
        </div>

        {/* Individual Results */}
        <div className="space-y-2 max-h-[300px] overflow-y-auto">
          {results.map((result) => (
            <div
              key={result.collection_id}
              className="flex items-center gap-3 p-2 rounded-lg border bg-card"
            >
              <div className="flex-shrink-0">
                {result.status === 'pending' && (
                  <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                    <div className="w-4 h-4 rounded-full bg-muted-foreground/20" />
                  </div>
                )}
                {result.status === 'generating' && (
                  <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                )}
                {result.status === 'completed' && (
                  <CheckCircle2 className="w-8 h-8 text-green-500" />
                )}
                {result.status === 'failed' && (
                  <XCircle className="w-8 h-8 text-red-500" />
                )}
              </div>
              
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{result.collection_name}</p>
                {result.error && (
                  <p className="text-sm text-red-500 truncate">{result.error}</p>
                )}
              </div>
              
              <Badge
                variant={
                  result.status === 'completed' ? 'default' :
                  result.status === 'failed' ? 'destructive' :
                  result.status === 'generating' ? 'secondary' :
                  'outline'
                }
                className="flex-shrink-0"
              >
                {result.status}
              </Badge>
            </div>
          ))}
        </div>

        {!isGenerating && results.length > 0 && (
          <div className="pt-2 border-t">
            <div className="flex items-center gap-2 text-sm">
              <AlertTriangle className="w-4 h-4 text-yellow-500" />
              <span>Generation complete. {failedCount > 0 ? 'Some icons failed to generate.' : 'All icons generated successfully!'}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}