import { ReactNode } from 'react';
import { cn } from "@/lib/utils";

interface DashboardLayoutProps {
  children: ReactNode;
  className?: string;
}

export function DashboardLayout({ children, className }: DashboardLayoutProps) {
  return (
    <div className={cn("min-h-screen bg-background", className)}>
      <div className="flex flex-col">
        <header className="sticky top-0 z-40 w-full border-b bg-background">
          <div className="container flex h-16 items-center justify-between py-4">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold">Product Feed Dashboard</h2>
            </div>
          </div>
        </header>
        <main className="flex-1">
          <div className="container py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

export function DashboardSection({ children, className, ...props }: DashboardLayoutProps) {
  return (
    <div className={cn("rounded-lg border bg-card p-6 shadow-sm", className)} {...props}>
      {children}
    </div>
  );
}