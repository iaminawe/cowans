import { ReactNode } from 'react';
import { cn } from "@/lib/utils";
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import { Button } from '@/components/ui/button';
import { 
  Activity, 
  Clock, 
  LogOut, 
  User
} from 'lucide-react';

interface DashboardLayoutProps {
  children: ReactNode;
  className?: string;
  isLoading?: boolean;
  // Header props
  syncStatus?: 'syncing' | 'ready' | 'error';
  lastSyncTime?: string;
  onLogout?: () => void;
  user?: {
    email?: string;
    is_admin?: boolean;
  };
}

export function DashboardLayout({ 
  children, 
  className, 
  isLoading, 
  syncStatus = 'ready',
  lastSyncTime,
  onLogout,
  user 
}: DashboardLayoutProps) {
  const getLastSyncDisplay = (lastSyncTime: string) => {
    if (!lastSyncTime) return 'Never';
    const date = new Date(lastSyncTime);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className={cn("min-h-screen bg-background", className)}>
      <div className="flex flex-col">
        {/* Enhanced Header */}
        <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-sm">
          <div className="container flex h-16 items-center justify-between py-4">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center shadow-sm">
                  <svg className="w-5 h-5 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 1.79 4 4 4h8c2.21 0 4-1.79 4-4V7c0-2.21-1.79-4-4-4H8c-2.21 0-4 1.79-4 4z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m9 12 2 2 4-4" />
                  </svg>
                </div>
                <div>
                  <h1 className="text-xl font-bold tracking-tight">Product Feed Dashboard</h1>
                  <p className="text-xs text-muted-foreground hidden sm:block">Cowan's Office Products Integration</p>
                </div>
              </div>
            </div>
            
            {/* Header Actions */}
            <div className="flex items-center gap-4">
              {/* Sync Status */}
              <div className="flex items-center gap-2 text-sm">
                <Activity className="h-4 w-4 text-muted-foreground" />
                <span className="text-muted-foreground hidden sm:inline">Status:</span>
                <div className="flex items-center gap-1">
                  <div className={cn(
                    "h-2 w-2 rounded-full",
                    syncStatus === 'syncing' || isLoading ? "bg-blue-500 animate-pulse" : 
                    syncStatus === 'error' ? "bg-red-500" : "bg-green-500"
                  )} />
                  <span className="font-medium text-sm">
                    {syncStatus === 'syncing' || isLoading ? 'Syncing...' : 
                     syncStatus === 'error' ? 'Error' : 'Ready'}
                  </span>
                </div>
              </div>

              {/* Last Sync Time */}
              {lastSyncTime && (
                <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
                  <Clock className="h-4 w-4" />
                  <span>Last sync: {getLastSyncDisplay(lastSyncTime)}</span>
                </div>
              )}

              {/* User Info & Logout */}
              {user && (
                <div className="flex items-center gap-2">
                  <div className="hidden lg:flex items-center gap-2 text-sm text-muted-foreground">
                    <User className="h-4 w-4" />
                    <span>{user.email}</span>
                    {user.is_admin && (
                      <span className="px-2 py-1 text-xs bg-primary/10 text-primary rounded-md">Admin</span>
                    )}
                  </div>
                  {onLogout && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={onLogout}
                      className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <LogOut className="h-4 w-4" />
                      <span className="hidden sm:inline">Sign Out</span>
                    </Button>
                  )}
                </div>
              )}
              
              {isLoading && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Spinner size="small" />
                  <span className="hidden sm:inline">Loading...</span>
                </div>
              )}
            </div>
          </div>
        </header>
        
        {/* Main Content */}
        <main className="flex-1">
          <div className="container py-6 lg:py-8 space-y-6 lg:space-y-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

export function DashboardSection({ children, className, ...props }: DashboardLayoutProps) {
  return (
    <div className={cn(
      "rounded-xl border bg-card p-6 shadow-sm hover:shadow-md transition-all duration-200",
      "hover:border-border/80",
      className
    )} {...props}>
      {children}
    </div>
  );
}

export function DashboardGrid({ 
  children, 
  className, 
  columns = 'auto',
  ...props 
}: DashboardLayoutProps & { columns?: 'auto' | 1 | 2 | 3 | 4 }) {
  const getGridClasses = () => {
    if (columns === 'auto') return "grid-cols-1 lg:grid-cols-2 xl:grid-cols-3";
    if (columns === 1) return "grid-cols-1";
    if (columns === 2) return "grid-cols-1 lg:grid-cols-2";
    if (columns === 3) return "grid-cols-1 md:grid-cols-2 xl:grid-cols-3";
    if (columns === 4) return "grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4";
    return "grid-cols-1 lg:grid-cols-2 xl:grid-cols-3";
  };
  
  return (
    <div className={cn(
      "grid gap-6",
      getGridClasses(),
      className
    )} {...props}>
      {children}
    </div>
  );
}

export function DashboardCard({ 
  children, 
  className, 
  title, 
  description, 
  actions, 
  variant = 'default',
  size = 'default',
  loading = false,
  ...props 
}: DashboardLayoutProps & {
  title?: string;
  description?: string;
  actions?: ReactNode;
  variant?: 'default' | 'outlined' | 'ghost';
  size?: 'default' | 'sm' | 'lg';
  loading?: boolean;
}) {
  const getVariantClasses = () => {
    switch (variant) {
      case 'outlined':
        return "border-2 border-dashed border-border/50 bg-transparent";
      case 'ghost':
        return "border-0 bg-muted/50 shadow-none";
      default:
        return "border bg-card shadow-sm hover:shadow-md";
    }
  };
  
  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return "p-3";
      case 'lg':
        return "p-8";
      default:
        return "p-6";
    }
  };
  
  if (loading) {
    return (
      <div className={cn(
        "rounded-xl border bg-card shadow-sm",
        getSizeClasses(),
        className
      )} {...props}>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-2">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-64" />
            </div>
            <Skeleton className="h-8 w-20" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className={cn(
      "rounded-xl transition-all duration-200",
      getVariantClasses(),
      className
    )} {...props}>
      {(title || description || actions) && (
        <div className="flex items-start justify-between p-6 pb-4">
          <div className="space-y-1 flex-1">
            {title && (
              <h3 className="text-lg font-semibold tracking-tight leading-none">
                {title}
              </h3>
            )}
            {description && (
              <p className="text-sm text-muted-foreground leading-relaxed">
                {description}
              </p>
            )}
          </div>
          {actions && (
            <div className="flex items-center gap-2 ml-4">
              {actions}
            </div>
          )}
        </div>
      )}
      <div className={cn(
        title || description || actions ? "px-6 pb-6" : getSizeClasses()
      )}>
        {children}
      </div>
    </div>
  );
}