// Note: Import toast from your actual toast implementation
// import { toast } from '@/components/ui/toast';

export interface ErrorWithCode extends Error {
  code?: string;
  status?: number;
  details?: Record<string, any>;
}

export interface ErrorHandlerOptions {
  fallbackMessage?: string;
  showToast?: boolean;
  logToConsole?: boolean;
  reportToService?: boolean;
}

class ErrorHandler {
  private errorReports: ErrorReport[] = [];
  private maxReports = 100;

  /**
   * Handle various types of errors with appropriate user feedback
   */
  handle(
    error: unknown, 
    context?: string, 
    options: ErrorHandlerOptions = {}
  ): ErrorWithCode {
    const {
      fallbackMessage = 'An unexpected error occurred',
      showToast = true,
      logToConsole = true,
      reportToService = true
    } = options;

    const processedError = this.processError(error);
    const userMessage = this.getUserMessage(processedError, fallbackMessage);

    // Log to console if enabled
    if (logToConsole) {
      console.error(`[ErrorHandler] ${context || 'Unknown context'}:`, processedError);
    }

    // Show user notification
    if (showToast) {
      this.showErrorToast(userMessage, processedError);
    }

    // Report to error tracking service
    if (reportToService) {
      this.reportError(processedError, context);
    }

    return processedError;
  }

  /**
   * Process raw error into standardized format
   */
  private processError(error: unknown): ErrorWithCode {
    if (error instanceof Error) {
      return error as ErrorWithCode;
    }

    if (typeof error === 'string') {
      return new Error(error) as ErrorWithCode;
    }

    if (typeof error === 'object' && error !== null) {
      const obj = error as Record<string, any>;
      const err = new Error(obj.message || 'Unknown error') as ErrorWithCode;
      err.code = obj.code;
      err.status = obj.status;
      err.details = obj.details;
      return err;
    }

    return new Error('Unknown error occurred') as ErrorWithCode;
  }

  /**
   * Generate user-friendly error message
   */
  private getUserMessage(error: ErrorWithCode, fallback: string): string {
    // Network errors
    if (error.status === 0 || error.message.includes('fetch')) {
      return 'Network connection error. Please check your internet connection.';
    }

    // Authentication errors
    if (error.status === 401) {
      return 'Authentication failed. Please log in again.';
    }

    if (error.status === 403) {
      return 'You do not have permission to perform this action.';
    }

    // Server errors
    if (error.status && error.status >= 500) {
      return 'Server error occurred. Please try again later.';
    }

    // Client errors
    if (error.status === 400) {
      return error.message || 'Invalid request. Please check your input.';
    }

    if (error.status === 404) {
      return 'The requested resource was not found.';
    }

    if (error.status === 429) {
      return 'Too many requests. Please wait a moment before trying again.';
    }

    // Shopify-specific errors
    if (error.code === 'SHOPIFY_API_ERROR') {
      return 'Shopify API error. Please check your store configuration.';
    }

    if (error.code === 'RATE_LIMIT_EXCEEDED') {
      return 'API rate limit exceeded. Please wait before making more requests.';
    }

    // Supabase auth errors
    if (error.code === 'SUPABASE_AUTH_ERROR') {
      return 'Authentication service error. Please try logging in again.';
    }

    // Use the original error message if it's user-friendly
    if (error.message && this.isUserFriendlyMessage(error.message)) {
      return error.message;
    }

    return fallback;
  }

  /**
   * Check if error message is suitable for users
   */
  private isUserFriendlyMessage(message: string): boolean {
    // Avoid technical jargon and stack traces
    const technicalPatterns = [
      /at \w+\./,           // Stack trace patterns
      /TypeError:/,         // JavaScript errors
      /ReferenceError:/,    // JavaScript errors
      /SyntaxError:/,       // JavaScript errors
      /fetch\(\)/,          // Fetch API references
      /XMLHttpRequest/,     // XMLHttpRequest references
      /\b[0-9a-f]{8,}\b/,   // Long hex strings (likely IDs)
    ];

    return !technicalPatterns.some(pattern => pattern.test(message));
  }

  /**
   * Show appropriate toast notification
   */
  private showErrorToast(message: string, error: ErrorWithCode) {
    const isWarning = error.status === 401 || error.status === 403;
    const isCritical = error.status && error.status >= 500;

    // Use console.log for now - replace with actual toast implementation
    if (isCritical) {
      console.error(`Critical Error: ${message}`);
    } else if (isWarning) {
      console.warn(`Warning: ${message}`);
    } else {
      console.error(`Error: ${message}`);
    }
    
    // TODO: Implement actual toast notifications
    // toast({
    //   title: isCritical ? 'Critical Error' : isWarning ? 'Warning' : 'Error',
    //   description: message,
    //   variant: isCritical ? 'destructive' : isWarning ? 'warning' : 'destructive',
    //   duration: isCritical ? 10000 : isWarning ? 7000 : 5000,
    // });
  }

  /**
   * Report error to monitoring service
   */
  private reportError(error: ErrorWithCode, context?: string) {
    const report: ErrorReport = {
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      message: error.message,
      code: error.code,
      status: error.status,
      stack: error.stack,
      context,
      userAgent: navigator.userAgent,
      url: window.location.href,
      details: error.details,
    };

    // Store locally (implement remote reporting as needed)
    this.errorReports.unshift(report);
    if (this.errorReports.length > this.maxReports) {
      this.errorReports.pop();
    }

    // TODO: Send to error tracking service (Sentry, LogRocket, etc.)
    this.sendToRemoteService(report);
  }

  /**
   * Send error report to remote monitoring service
   */
  private async sendToRemoteService(report: ErrorReport) {
    try {
      // Example implementation - replace with your error tracking service
      if (process.env.NODE_ENV === 'production') {
        await fetch('/api/errors', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(report),
        });
      }
    } catch (err) {
      console.warn('Failed to report error to remote service:', err);
    }
  }

  /**
   * Get recent error reports for debugging
   */
  getRecentReports(limit: number = 10): ErrorReport[] {
    return this.errorReports.slice(0, limit);
  }

  /**
   * Clear stored error reports
   */
  clearReports() {
    this.errorReports = [];
  }

  /**
   * Retry mechanism for failed operations
   */
  async retry<T>(
    operation: () => Promise<T>,
    maxRetries: number = 3,
    delay: number = 1000,
    backoff: number = 2
  ): Promise<T> {
    let lastError: Error;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = this.processError(error);
        
        if (attempt === maxRetries) {
          break;
        }

        // Don't retry on authentication errors or client errors
        const errorWithCode = lastError as ErrorWithCode;
        if (errorWithCode.status && (errorWithCode.status === 401 || errorWithCode.status === 403 || errorWithCode.status === 400)) {
          break;
        }

        // Wait before retrying with exponential backoff
        await new Promise(resolve => setTimeout(resolve, delay * Math.pow(backoff, attempt - 1)));
      }
    }

    throw lastError!;
  }
}

interface ErrorReport {
  id: string;
  timestamp: string;
  message: string;
  code?: string;
  status?: number;
  stack?: string;
  context?: string;
  userAgent: string;
  url: string;
  details?: Record<string, any>;
}

// Create singleton instance
export const errorHandler = new ErrorHandler();

// Convenience functions
export const handleError = (error: unknown, context?: string, options?: ErrorHandlerOptions) => 
  errorHandler.handle(error, context, options);

export const retryOperation = <T>(
  operation: () => Promise<T>,
  maxRetries?: number,
  delay?: number,
  backoff?: number
) => errorHandler.retry(operation, maxRetries, delay, backoff);

// Global error handlers
window.addEventListener('error', (event) => {
  errorHandler.handle(event.error, 'Global Error Handler', {
    showToast: false, // Avoid spam for global errors
    logToConsole: true,
    reportToService: true,
  });
});

window.addEventListener('unhandledrejection', (event) => {
  errorHandler.handle(event.reason, 'Unhandled Promise Rejection', {
    showToast: false,
    logToConsole: true,
    reportToService: true,
  });
});

export default errorHandler;