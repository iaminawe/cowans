import React, { useState } from 'react';
import { cn } from "@/lib/utils";

interface LoginFormProps {
  className?: string;
  onLogin: (email: string, password: string) => Promise<void>;
  onSwitchToRegister?: () => void;
  isLoading?: boolean;
  error?: string | null;
}

export function LoginForm({ className, onLogin, onSwitchToRegister, isLoading = false, error: externalError }: LoginFormProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }

    try {
      await onLogin(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    }
  };

  return (
    <div className={cn("flex min-h-screen items-center justify-center bg-background", className)}>
      <div className="mx-auto w-full max-w-md space-y-6">
        <div className="text-center">
          <h2 className="text-3xl font-bold tracking-tight">Cowans Office Supplies Dashboard</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Sign in to manage your product synchronization
          </p>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={cn(
                "mt-1 block w-full rounded-md border border-input bg-background px-3 py-2",
                "placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring"
              )}
              placeholder="Enter your email"
              disabled={isLoading}
            />
          </div>
          
          <div>
            <label htmlFor="password" className="block text-sm font-medium">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={cn(
                "mt-1 block w-full rounded-md border border-input bg-background px-3 py-2",
                "placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring"
              )}
              placeholder="Enter your password"
              disabled={isLoading}
            />
          </div>
          
          {(error || externalError) && (
            <div className="text-sm text-red-600">
              {error || externalError}
            </div>
          )}
          
          <button
            type="submit"
            disabled={isLoading}
            className={cn(
              "w-full rounded-md bg-primary px-4 py-2 text-primary-foreground",
              "hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring",
              "disabled:pointer-events-none disabled:opacity-50"
            )}
          >
            {isLoading ? (
              <>
                <svg
                  className="mr-2 inline h-4 w-4 animate-spin"
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
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Signing in...
              </>
            ) : (
              'Sign In'
            )}
          </button>
          
          {onSwitchToRegister && (
            <div className="text-center text-sm">
              <span className="text-muted-foreground">Don't have an account? </span>
              <button
                type="button"
                onClick={onSwitchToRegister}
                className="text-primary hover:underline"
                disabled={isLoading}
              >
                Create account
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}