import React from 'react';
import { cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  RotateCcw, 
  Code2, 
  FileText, 
  Package,
  FolderTree,
  Image,
  Shield,
  Layers,
  BarChart3
} from 'lucide-react';

interface NavigationTabsProps {
  activeView: 'sync' | 'scripts' | 'logs' | 'products' | 'analytics' | 'collections' | 'categories' | 'icons' | 'admin';
  onViewChange: (view: 'sync' | 'scripts' | 'logs' | 'products' | 'analytics' | 'collections' | 'categories' | 'icons' | 'admin') => void;
  isLoading?: boolean;
  realtimeLogsCount?: number;
  currentScript?: string;
  productsCount?: number;
  isAdmin?: boolean;
  className?: string;
}

export function NavigationTabs({
  activeView,
  onViewChange,
  isLoading,
  realtimeLogsCount = 0,
  currentScript,
  productsCount = 0,
  isAdmin = false,
  className
}: NavigationTabsProps) {
  return (
    <div className={cn("mb-8", className)}>
      <div className="flex flex-col space-y-4 lg:flex-row lg:items-center lg:justify-between lg:space-y-0">
        {/* Main Navigation */}
        <div className="flex-1">
          <Tabs 
            value={activeView} 
            onValueChange={(value) => onViewChange(value as any)}
            className="w-full"
          >
            <TabsList className={cn(
              "grid w-full h-12",
              isAdmin ? "grid-cols-9 lg:w-[1260px]" : "grid-cols-5 lg:w-[800px]"
            )}>
              <TabsTrigger 
                value="sync" 
                className="flex items-center gap-2 transition-all duration-200 data-[state=active]:shadow-md"
              >
                <RotateCcw className={cn(
                  "h-4 w-4 transition-transform",
                  isLoading && activeView === 'sync' ? "animate-spin" : ""
                )} />
                <span className="font-medium">Sync</span>
                {isLoading && activeView === 'sync' && (
                  <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                    Running
                  </Badge>
                )}
              </TabsTrigger>

              <TabsTrigger 
                value="products" 
                className="flex items-center gap-2 transition-all duration-200 data-[state=active]:shadow-md"
              >
                <Package className="h-4 w-4" />
                <span className="font-medium">Products</span>
                {productsCount > 0 && (
                  <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                    {productsCount}
                  </Badge>
                )}
              </TabsTrigger>

              <TabsTrigger 
                value="analytics" 
                className="flex items-center gap-2 transition-all duration-200 data-[state=active]:shadow-md"
              >
                <BarChart3 className="h-4 w-4" />
                <span className="font-medium">Analytics</span>
              </TabsTrigger>
              
              {isAdmin && (
                <>
                  <TabsTrigger 
                    value="collections" 
                    className="flex items-center gap-2 transition-all duration-200 data-[state=active]:shadow-md"
                  >
                    <Layers className="h-4 w-4" />
                    <span className="font-medium">Collections</span>
                  </TabsTrigger>
                  
                  <TabsTrigger 
                    value="categories" 
                    className="flex items-center gap-2 transition-all duration-200 data-[state=active]:shadow-md"
                  >
                    <FolderTree className="h-4 w-4" />
                    <span className="font-medium">Categories</span>
                  </TabsTrigger>
                  
                  <TabsTrigger 
                    value="icons" 
                    className="flex items-center gap-2 transition-all duration-200 data-[state=active]:shadow-md"
                  >
                    <Image className="h-4 w-4" />
                    <span className="font-medium">Icons</span>
                  </TabsTrigger>
                  
                  <TabsTrigger 
                    value="admin" 
                    className="flex items-center gap-2 transition-all duration-200 data-[state=active]:shadow-md"
                  >
                    <Shield className="h-4 w-4" />
                    <span className="font-medium">Admin</span>
                  </TabsTrigger>
                </>
              )}
            </TabsList>
          </Tabs>
        </div>
      </div>
    </div>
  );
}