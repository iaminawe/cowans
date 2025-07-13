import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { apiClient } from '@/lib/api';
import { AuthUser } from '@/types/api';

type User = AuthUser;

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, firstName: string, lastName: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  const setLoading = useCallback((loading: boolean) => {
    setState(prev => ({ ...prev, isLoading: loading }));
  }, []);

  const setError = useCallback((error: string) => {
    setState(prev => ({ ...prev, error, isLoading: false }));
  }, []);

  const setUser = useCallback((user: User | null) => {
    setState(prev => ({
      ...prev,
      user,
      isAuthenticated: !!user,
      isLoading: false,
      error: null,
    }));
  }, []);

  // Get current user profile
  const refreshUser = useCallback(async () => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        setUser(null);
        return;
      }

      const response = await apiClient.getCurrentUser();
      setUser(response.user);
    } catch (error: unknown) {
      console.error('Failed to refresh user:', error);
      
      const errorMessage = error instanceof Error ? error.message : String(error);
      
      // Clear any invalid tokens for various error types
      if (errorMessage.includes('401') || 
          errorMessage.includes('Unauthorized') || 
          errorMessage.includes('Authentication required') ||
          errorMessage.includes('SyntaxError') ||
          errorMessage.includes('string did not match') ||
          error instanceof SyntaxError) {
        console.log('Clearing invalid auth token due to error:', errorMessage);
        localStorage.removeItem('auth_token');
        apiClient.setAuthToken(null);
        setUser(null);
        clearError(); // Clear any existing errors
      } else {
        // For other errors, don't clear the token immediately
        setError(errorMessage || 'Failed to refresh user');
      }
    } finally {
      setLoading(false);
    }
  }, [setUser, setError, clearError, setLoading]);

  // Login function
  const login = useCallback(async (email: string, password: string) => {
    setLoading(true);
    clearError();

    try {
      const response = await apiClient.login(email, password);
      setUser(response.user);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Login failed');
      throw error;
    }
  }, [setLoading, clearError, setUser, setError]);

  // Register function
  const register = useCallback(async (email: string, password: string, firstName: string, lastName: string) => {
    setLoading(true);
    clearError();

    try {
      const response = await apiClient.register(email, password, firstName, lastName);
      setUser(response.user);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Registration failed');
      throw error;
    }
  }, [setLoading, clearError, setUser, setError]);

  // Logout function
  const logout = useCallback(async () => {
    setLoading(true);
    
    try {
      await apiClient.logout();
    } catch (error) {
      console.error('Logout error:', error);
      // Continue with logout even if API call fails
    } finally {
      setUser(null);
    }
  }, [setLoading, setUser]);

  // Initialize authentication state on mount
  useEffect(() => {
    const initializeAuth = async () => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        try {
          // Validate token format before attempting to use it
          if (token === 'dev-token' || token.includes('undefined') || token.length < 10) {
            console.log('Clearing invalid/dev token');
            localStorage.removeItem('auth_token');
            apiClient.setAuthToken(null);
            setLoading(false);
            return;
          }
          
          await refreshUser();
        } catch (error) {
          console.error('Auth initialization error:', error);
          // Clear problematic token
          localStorage.removeItem('auth_token');
          apiClient.setAuthToken(null);
          setLoading(false);
        }
      } else {
        setLoading(false);
      }
    };

    initializeAuth();
  }, [refreshUser, setLoading]);

  const contextValue: AuthContextType = {
    ...state,
    login,
    register,
    logout,
    clearError,
    refreshUser,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export type { User, AuthState, AuthContextType };