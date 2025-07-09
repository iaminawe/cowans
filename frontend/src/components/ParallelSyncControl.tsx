import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { 
  Play,
  Pause,
  Settings,
  Zap,
  DollarSign,
  BarChart2,
  Users,
  Package,
  AlertTriangle,
  Info
} from 'lucide-react';
import { ParallelSyncConfig, ParallelSyncStartRequest } from '@/types/sync';
import { apiClient } from '@/lib/api';

interface ParallelSyncControlProps {
  onSyncStart: (config: ParallelSyncConfig) => void;
  onSyncStop: () => void;
  isRunning: boolean;
  className?: string;
}

export function ParallelSyncControl({ 
  onSyncStart, 
  onSyncStop, 
  isRunning,
  className 
}: ParallelSyncControlProps) {
  const [config, setConfig] = useState<ParallelSyncConfig>({
    enabled: true,
    minWorkers: 1,
    maxWorkers: 4,
    batchSize: 50,
    priority: 'normal',
    operationType: 'all',
    strategy: 'balanced',
    retryAttempts: 3,
    timeout: 300000 // 5 minutes
  });

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleConfigChange = (key: keyof ParallelSyncConfig, value: any) => {
    setConfig(prev => ({
      ...prev,
      [key]: value
    }));
    setValidationError(null);
  };

  const validateConfig = (): boolean => {
    if (config.minWorkers > config.maxWorkers) {
      setValidationError('Minimum workers cannot exceed maximum workers');
      return false;
    }
    if (config.batchSize < 1 || config.batchSize > 1000) {
      setValidationError('Batch size must be between 1 and 1000');
      return false;
    }
    if (config.timeout < 10000) {
      setValidationError('Timeout must be at least 10 seconds');
      return false;
    }
    return true;
  };

  const handleStart = () => {
    if (validateConfig()) {
      onSyncStart(config);
    }
  };

  const getStrategyIcon = (strategy: string) => {
    switch (strategy) {
      case 'speed':
        return <Zap className="h-4 w-4" />;
      case 'cost':
        return <DollarSign className="h-4 w-4" />;
      case 'balanced':
        return <BarChart2 className="h-4 w-4" />;
      default:
        return null;
    }
  };

  const getStrategyDescription = (strategy: string) => {
    switch (strategy) {
      case 'speed':
        return 'Maximize throughput with more parallel workers';
      case 'cost':
        return 'Minimize API calls and resource usage';
      case 'balanced':
        return 'Optimize for both speed and cost efficiency';
      default:
        return '';
    }
  };

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Parallel Sync Control
          </span>
          {isRunning && (
            <Badge variant="default" className="bg-green-500">
              <span className="flex h-2 w-2 rounded-full bg-white animate-pulse mr-2" />
              Running
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          Configure and control the parallel batch synchronization system
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {validationError && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{validationError}</AlertDescription>
          </Alert>
        )}

        {/* Basic Configuration */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="enabled">Enable Parallel Processing</Label>
              <p className="text-sm text-muted-foreground">
                Use multiple workers for faster synchronization
              </p>
            </div>
            <Switch
              id="enabled"
              checked={config.enabled}
              onCheckedChange={(checked: boolean) => handleConfigChange('enabled', checked)}
              disabled={isRunning}
            />
          </div>

          {/* Worker Pool Configuration */}
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Users className="h-4 w-4" />
              Worker Pool Size: {config.minWorkers} - {config.maxWorkers}
            </Label>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="minWorkers" className="text-xs">Minimum Workers</Label>
                <Slider
                  id="minWorkers"
                  min={1}
                  max={10}
                  step={1}
                  value={[config.minWorkers]}
                  onValueChange={(value: number[]) => handleConfigChange('minWorkers', value[0])}
                  disabled={isRunning || !config.enabled}
                  className="mt-2"
                />
              </div>
              <div>
                <Label htmlFor="maxWorkers" className="text-xs">Maximum Workers</Label>
                <Slider
                  id="maxWorkers"
                  min={1}
                  max={10}
                  step={1}
                  value={[config.maxWorkers]}
                  onValueChange={(value: number[]) => handleConfigChange('maxWorkers', value[0])}
                  disabled={isRunning || !config.enabled}
                  className="mt-2"
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Workers automatically scale based on queue depth and system resources
            </p>
          </div>

          {/* Batch Size */}
          <div className="space-y-2">
            <Label htmlFor="batchSize" className="flex items-center gap-2">
              <Package className="h-4 w-4" />
              Batch Size
            </Label>
            <Input
              id="batchSize"
              type="number"
              min={1}
              max={1000}
              value={config.batchSize}
              onChange={(e) => handleConfigChange('batchSize', parseInt(e.target.value) || 1)}
              disabled={isRunning}
            />
            <p className="text-xs text-muted-foreground">
              Number of items to process in each batch
            </p>
          </div>

          {/* Priority Selection */}
          <div className="space-y-2">
            <Label htmlFor="priority">Processing Priority</Label>
            <Select 
              value={config.priority} 
              onValueChange={(value: 'low' | 'normal' | 'high') => handleConfigChange('priority', value)}
              disabled={isRunning}
            >
              <SelectTrigger id="priority">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="low">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">Low</Badge>
                    <span className="text-sm">Background processing</span>
                  </div>
                </SelectItem>
                <SelectItem value="normal">
                  <div className="flex items-center gap-2">
                    <Badge variant="default">Normal</Badge>
                    <span className="text-sm">Standard processing</span>
                  </div>
                </SelectItem>
                <SelectItem value="high">
                  <div className="flex items-center gap-2">
                    <Badge variant="destructive">High</Badge>
                    <span className="text-sm">Priority processing</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Operation Type */}
          <div className="space-y-2">
            <Label htmlFor="operationType">Operation Type</Label>
            <Select 
              value={config.operationType} 
              onValueChange={(value: 'create' | 'update' | 'delete' | 'all') => handleConfigChange('operationType', value)}
              disabled={isRunning}
            >
              <SelectTrigger id="operationType">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="create">Create New Products</SelectItem>
                <SelectItem value="update">Update Existing Products</SelectItem>
                <SelectItem value="delete">Delete Products</SelectItem>
                <SelectItem value="all">All Operations</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Sync Strategy */}
          <div className="space-y-2">
            <Label htmlFor="strategy">Sync Strategy</Label>
            <Select 
              value={config.strategy} 
              onValueChange={(value: 'speed' | 'cost' | 'balanced') => handleConfigChange('strategy', value)}
              disabled={isRunning}
            >
              <SelectTrigger id="strategy">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="speed">
                  <div className="flex items-center gap-2">
                    <Zap className="h-4 w-4" />
                    <span>Speed Priority</span>
                  </div>
                </SelectItem>
                <SelectItem value="cost">
                  <div className="flex items-center gap-2">
                    <DollarSign className="h-4 w-4" />
                    <span>Cost Optimized</span>
                  </div>
                </SelectItem>
                <SelectItem value="balanced">
                  <div className="flex items-center gap-2">
                    <BarChart2 className="h-4 w-4" />
                    <span>Balanced</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
            {config.strategy && (
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  {getStrategyDescription(config.strategy)}
                </AlertDescription>
              </Alert>
            )}
          </div>
        </div>

        {/* Advanced Settings */}
        <div className="space-y-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full"
          >
            {showAdvanced ? 'Hide' : 'Show'} Advanced Settings
          </Button>

          {showAdvanced && (
            <div className="space-y-4 pt-4 border-t">
              <div className="space-y-2">
                <Label htmlFor="retryAttempts">Retry Attempts</Label>
                <Input
                  id="retryAttempts"
                  type="number"
                  min={0}
                  max={10}
                  value={config.retryAttempts}
                  onChange={(e) => handleConfigChange('retryAttempts', parseInt(e.target.value) || 0)}
                  disabled={isRunning}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="timeout">Timeout (ms)</Label>
                <Input
                  id="timeout"
                  type="number"
                  min={10000}
                  max={3600000}
                  step={1000}
                  value={config.timeout}
                  onChange={(e) => handleConfigChange('timeout', parseInt(e.target.value) || 10000)}
                  disabled={isRunning}
                />
                <p className="text-xs text-muted-foreground">
                  Maximum time per batch operation ({config.timeout / 1000} seconds)
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Control Buttons */}
        <div className="flex gap-2">
          {!isRunning ? (
            <Button 
              onClick={handleStart}
              className="flex-1"
              disabled={!config.enabled}
            >
              <Play className="h-4 w-4 mr-2" />
              Start Parallel Sync
            </Button>
          ) : (
            <Button 
              onClick={onSyncStop}
              variant="destructive"
              className="flex-1"
            >
              <Pause className="h-4 w-4 mr-2" />
              Stop Sync
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}