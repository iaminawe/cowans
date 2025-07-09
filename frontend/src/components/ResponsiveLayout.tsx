import React from 'react';
import { cn } from "@/lib/utils";

interface ResponsiveLayoutProps {
  children: React.ReactNode;
  className?: string;
}

// Responsive Container with proper breakpoints
export function ResponsiveContainer({ children, className }: ResponsiveLayoutProps) {
  return (
    <div className={cn(
      "w-full mx-auto",
      "px-4 sm:px-6 lg:px-8",
      "max-w-7xl",
      className
    )}>
      {children}
    </div>
  );
}

// Stack layout for mobile-first design
export function ResponsiveStack({ 
  children, 
  className,
  spacing = 'default',
  align = 'stretch'
}: ResponsiveLayoutProps & {
  spacing?: 'tight' | 'default' | 'loose';
  align?: 'start' | 'center' | 'end' | 'stretch';
}) {
  const getSpacingClasses = () => {
    switch (spacing) {
      case 'tight':
        return 'space-y-2 lg:space-y-4';
      case 'loose':
        return 'space-y-8 lg:space-y-12';
      default:
        return 'space-y-4 lg:space-y-6';
    }
  };

  const getAlignClasses = () => {
    switch (align) {
      case 'start':
        return 'items-start';
      case 'center':
        return 'items-center';
      case 'end':
        return 'items-end';
      default:
        return 'items-stretch';
    }
  };

  return (
    <div className={cn(
      "flex flex-col",
      getSpacingClasses(),
      getAlignClasses(),
      className
    )}>
      {children}
    </div>
  );
}

// Responsive grid with breakpoint control
export function ResponsiveGrid({ 
  children, 
  className,
  columns = { base: 1, md: 2, lg: 3 },
  gap = 'default'
}: ResponsiveLayoutProps & {
  columns?: { base?: number; sm?: number; md?: number; lg?: number; xl?: number };
  gap?: 'tight' | 'default' | 'loose';
}) {
  const getGridClasses = () => {
    const classes = ['grid'];
    
    if (columns.base) classes.push(`grid-cols-${columns.base}`);
    if (columns.sm) classes.push(`sm:grid-cols-${columns.sm}`);
    if (columns.md) classes.push(`md:grid-cols-${columns.md}`);
    if (columns.lg) classes.push(`lg:grid-cols-${columns.lg}`);
    if (columns.xl) classes.push(`xl:grid-cols-${columns.xl}`);
    
    return classes.join(' ');
  };

  const getGapClasses = () => {
    switch (gap) {
      case 'tight':
        return 'gap-2 lg:gap-4';
      case 'loose':
        return 'gap-8 lg:gap-12';
      default:
        return 'gap-4 lg:gap-6';
    }
  };

  return (
    <div className={cn(
      getGridClasses(),
      getGapClasses(),
      className
    )}>
      {children}
    </div>
  );
}

// Responsive flexbox layout
export function ResponsiveFlex({ 
  children, 
  className,
  direction = 'col',
  wrap = false,
  justify = 'start',
  align = 'start',
  gap = 'default'
}: ResponsiveLayoutProps & {
  direction?: 'row' | 'col' | 'row-reverse' | 'col-reverse';
  wrap?: boolean;
  justify?: 'start' | 'center' | 'end' | 'between' | 'around' | 'evenly';
  align?: 'start' | 'center' | 'end' | 'stretch' | 'baseline';
  gap?: 'tight' | 'default' | 'loose';
}) {
  const getDirectionClasses = () => {
    switch (direction) {
      case 'row':
        return 'flex-col sm:flex-row';
      case 'col':
        return 'flex-col';
      case 'row-reverse':
        return 'flex-col-reverse sm:flex-row-reverse';
      case 'col-reverse':
        return 'flex-col-reverse';
      default:
        return 'flex-col sm:flex-row';
    }
  };

  const getJustifyClasses = () => {
    switch (justify) {
      case 'center':
        return 'justify-center';
      case 'end':
        return 'justify-end';
      case 'between':
        return 'justify-between';
      case 'around':
        return 'justify-around';
      case 'evenly':
        return 'justify-evenly';
      default:
        return 'justify-start';
    }
  };

  const getAlignClasses = () => {
    switch (align) {
      case 'center':
        return 'items-center';
      case 'end':
        return 'items-end';
      case 'stretch':
        return 'items-stretch';
      case 'baseline':
        return 'items-baseline';
      default:
        return 'items-start';
    }
  };

  const getGapClasses = () => {
    switch (gap) {
      case 'tight':
        return 'gap-2 sm:gap-3';
      case 'loose':
        return 'gap-6 sm:gap-8';
      default:
        return 'gap-4 sm:gap-6';
    }
  };

  return (
    <div className={cn(
      "flex",
      getDirectionClasses(),
      wrap ? 'flex-wrap' : '',
      getJustifyClasses(),
      getAlignClasses(),
      getGapClasses(),
      className
    )}>
      {children}
    </div>
  );
}

// Responsive sidebar layout
export function ResponsiveSidebar({ 
  children, 
  sidebar,
  className,
  sidebarWidth = 'default',
  sidebarPosition = 'left',
  collapsible = false
}: ResponsiveLayoutProps & {
  sidebar: React.ReactNode;
  sidebarWidth?: 'narrow' | 'default' | 'wide';
  sidebarPosition?: 'left' | 'right';
  collapsible?: boolean;
}) {
  const getSidebarWidthClasses = () => {
    switch (sidebarWidth) {
      case 'narrow':
        return 'w-64';
      case 'wide':
        return 'w-80';
      default:
        return 'w-72';
    }
  };

  return (
    <div className={cn("flex flex-col lg:flex-row min-h-screen", className)}>
      {/* Sidebar */}
      <aside className={cn(
        "shrink-0 border-r bg-muted/50",
        getSidebarWidthClasses(),
        sidebarPosition === 'right' ? 'lg:order-2' : 'lg:order-1',
        collapsible ? 'hidden lg:block' : ''
      )}>
        {sidebar}
      </aside>

      {/* Main content */}
      <main className={cn(
        "flex-1 overflow-hidden",
        sidebarPosition === 'right' ? 'lg:order-1' : 'lg:order-2'
      )}>
        {children}
      </main>
    </div>
  );
}

// Responsive card layout
export function ResponsiveCardLayout({ 
  children, 
  className,
  size = 'default'
}: ResponsiveLayoutProps & {
  size?: 'compact' | 'default' | 'spacious';
}) {
  const getSizeClasses = () => {
    switch (size) {
      case 'compact':
        return 'p-4 space-y-4';
      case 'spacious':
        return 'p-8 space-y-8';
      default:
        return 'p-6 space-y-6';
    }
  };

  return (
    <div className={cn(
      "rounded-xl border bg-card shadow-sm",
      getSizeClasses(),
      className
    )}>
      {children}
    </div>
  );
}

// Responsive breakpoint visibility
export function ResponsiveShow({ 
  children, 
  breakpoint,
  className 
}: ResponsiveLayoutProps & {
  breakpoint: 'sm' | 'md' | 'lg' | 'xl';
}) {
  const getBreakpointClasses = () => {
    switch (breakpoint) {
      case 'sm':
        return 'hidden sm:block';
      case 'md':
        return 'hidden md:block';
      case 'lg':
        return 'hidden lg:block';
      case 'xl':
        return 'hidden xl:block';
      default:
        return 'hidden';
    }
  };

  return (
    <div className={cn(getBreakpointClasses(), className)}>
      {children}
    </div>
  );
}

export function ResponsiveHide({ 
  children, 
  breakpoint,
  className 
}: ResponsiveLayoutProps & {
  breakpoint: 'sm' | 'md' | 'lg' | 'xl';
}) {
  const getBreakpointClasses = () => {
    switch (breakpoint) {
      case 'sm':
        return 'sm:hidden';
      case 'md':
        return 'md:hidden';
      case 'lg':
        return 'lg:hidden';
      case 'xl':
        return 'xl:hidden';
      default:
        return 'hidden';
    }
  };

  return (
    <div className={cn(getBreakpointClasses(), className)}>
      {children}
    </div>
  );
}