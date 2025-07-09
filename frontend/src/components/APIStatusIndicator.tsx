import React from 'react';
import { cn } from "@/lib/utils";
import { Badge } from '@/components/ui/badge';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Clock, 
  Wifi, 
  WifiOff, 
  Zap,
  Settings,
  RefreshCw
} from 'lucide-react';

export interface APIEndpoint {
  id: string;
  name: string;
  url: string;
  status: 'connected' | 'disconnected' | 'error' | 'checking';
  lastChecked?: string;
  responseTime?: number;
  errorMessage?: string;
  rateLimitRemaining?: number;
  rateLimitReset?: string;
}

interface APIStatusIndicatorProps {
  endpoints: APIEndpoint[];
  onRefresh?: (endpointId?: string) => void;
  onConfigure?: (endpointId: string) => void;
  className?: string;
  compact?: boolean;
  showDetails?: boolean;
}

export function APIStatusIndicator({ 
  endpoints, 
  onRefresh, 
  onConfigure,
  className,
  compact = false,
  showDetails = true
}: APIStatusIndicatorProps) {
  const getStatusIcon = (status: APIEndpoint['status']) => {
    switch (status) {
      case 'connected':
        return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      case 'disconnected':
        return <WifiOff className="h-4 w-4 text-gray-400" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-600" />;
      case 'checking':
        return <RefreshCw className="h-4 w-4 text-blue-600 animate-spin" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusBadge = (status: APIEndpoint['status']) => {
    switch (status) {
      case 'connected':
        return <Badge variant="secondary" className="bg-green-100 text-green-800 border-green-200">Connected</Badge>;
      case 'disconnected':
        return <Badge variant="outline" className="text-gray-600">Disconnected</Badge>;
      case 'error':
        return <Badge variant="destructive">Error</Badge>;
      case 'checking':
        return <Badge variant="secondary" className="bg-blue-100 text-blue-800 border-blue-200">Checking...</Badge>;
      default:
        return <Badge variant="outline">Unknown</Badge>;
    }
  };

  const getOverallStatus = () => {
    const connected = endpoints.filter(e => e.status === 'connected').length;
    const total = endpoints.length;
    const hasErrors = endpoints.some(e => e.status === 'error');
    
    if (hasErrors) return 'error';
    if (connected === total) return 'connected';
    if (connected > 0) return 'partial';
    return 'disconnected';
  };

  const overallStatus = getOverallStatus();

  if (compact) {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <div className="flex items-center gap-1">
          {overallStatus === 'connected' && <Wifi className="h-4 w-4 text-green-600" />}
          {overallStatus === 'partial' && <AlertTriangle className="h-4 w-4 text-yellow-600" />}
          {overallStatus === 'error' && <XCircle className="h-4 w-4 text-red-600" />}
          {overallStatus === 'disconnected' && <WifiOff className="h-4 w-4 text-gray-400" />}
        </div>
        <span className="text-sm font-medium">
          {endpoints.filter(e => e.status === 'connected').length}/{endpoints.length} APIs
        </span>
        {onRefresh && (
          <Button variant="ghost" size="sm" onClick={() => onRefresh()}>
            <RefreshCw className="h-3 w-3" />
          </Button>
        )}
      </div>
    );
  }

  return (
    <Card className={cn("", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold">API Status</CardTitle>
          <div className="flex items-center gap-2">
            {getStatusIcon(overallStatus as APIEndpoint['status'])}
            <span className="text-sm font-medium">
              {endpoints.filter(e => e.status === 'connected').length}/{endpoints.length} Connected
            </span>
            {onRefresh && (
              <Button variant="ghost" size="sm" onClick={() => onRefresh()}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {endpoints.map((endpoint) => (
          <div key={endpoint.id} className="flex items-start justify-between p-3 rounded-lg border bg-gray-100 dark:bg-gray-800">
            <div className="flex items-start gap-3 flex-1">
              <div className="mt-0.5">
                {getStatusIcon(endpoint.status)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="font-medium text-sm">{endpoint.name}</h4>
                  {getStatusBadge(endpoint.status)}
                </div>
                <p className="text-xs text-muted-foreground mb-2 truncate">{endpoint.url}</p>
                
                {showDetails && (
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    {endpoint.lastChecked && (
                      <span>Last checked: {new Date(endpoint.lastChecked).toLocaleTimeString()}</span>
                    )}
                    {endpoint.responseTime && (
                      <span>Response: {endpoint.responseTime}ms</span>
                    )}
                    {endpoint.rateLimitRemaining !== undefined && (
                      <span>Rate limit: {endpoint.rateLimitRemaining} remaining</span>
                    )}
                  </div>
                )}
                
                {endpoint.status === 'error' && endpoint.errorMessage && (
                  <Alert variant="destructive" className="mt-2">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription className="text-xs">
                      {endpoint.errorMessage}
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            </div>
            
            <div className="flex items-center gap-1 ml-2">
              {onRefresh && (
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => onRefresh(endpoint.id)}
                  disabled={endpoint.status === 'checking'}
                >
                  <RefreshCw className={cn("h-3 w-3", endpoint.status === 'checking' && "animate-spin")} />
                </Button>
              )}
              {onConfigure && (
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => onConfigure(endpoint.id)}
                >
                  <Settings className="h-3 w-3" />
                </Button>
              )}
            </div>
          </div>
        ))}
        
        {/* Rate Limit Summary */}
        {endpoints.some(e => e.rateLimitRemaining !== undefined) && (
          <div className="pt-3 border-t">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="h-4 w-4 text-yellow-600" />
              <span className="text-sm font-medium">Rate Limits</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {endpoints
                .filter(e => e.rateLimitRemaining !== undefined)
                .map((endpoint) => (
                  <div key={endpoint.id} className="flex justify-between text-xs p-2 bg-background rounded border">
                    <span className="truncate mr-2">{endpoint.name}</span>
                    <span className={cn(
                      "font-mono",
                      endpoint.rateLimitRemaining! < 100 ? "text-red-600" :
                      endpoint.rateLimitRemaining! < 500 ? "text-yellow-600" : "text-green-600"
                    )}>
                      {endpoint.rateLimitRemaining}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function APIStatusSummary({ endpoints, className }: { endpoints: APIEndpoint[], className?: string }) {
  const connected = endpoints.filter(e => e.status === 'connected').length;
  const total = endpoints.length;
  const hasErrors = endpoints.some(e => e.status === 'error');
  
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className={cn(
        "h-2 w-2 rounded-full",
        hasErrors ? "bg-red-500" :
        connected === total ? "bg-green-500" :
        connected > 0 ? "bg-yellow-500" : "bg-gray-400"
      )} />
      <span className="text-sm text-muted-foreground">
        APIs: {connected}/{total}
      </span>
    </div>
  );
}