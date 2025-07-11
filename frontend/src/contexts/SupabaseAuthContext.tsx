import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { User, Session, AuthError } from '@supabase/supabase-js';
import { supabase } from '../services/supabase';
import { apiClient } from '@/lib/api';

interface LocalUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_admin: boolean;
  created_at?: string;
  last_login?: string;
}

interface AuthState {
  user: User | null;
  localUser: LocalUser | null;
  session: Session | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

interface AuthContextType extends AuthState {
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, firstName: string, lastName: string) => Promise<void>;
  signOut: () => Promise<void>;
  clearError: () => void;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function SupabaseAuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    user: null,
    localUser: null,
    session: null,
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

  const setAuthState = useCallback((user: User | null, session: Session | null, localUser: LocalUser | null) => {
    setState(prev => ({
      ...prev,
      user,
      session,
      localUser,
      isAuthenticated: !!user && !!session,
      isLoading: false,
      error: null,
    }));
  }, []);

  // Sync local user data after Supabase auth
  const syncLocalUser = useCallback(async (session: Session) => {
    try {
      // Store tokens for API client
      if (session.access_token) {
        localStorage.setItem('auth_token', session.access_token);
        localStorage.setItem('refresh_token', session.refresh_token || '');
      }

      // Get user profile from backend
      const response: any = await apiClient.getCurrentUser();
      return response.user;
    } catch (error) {
      console.error('Failed to sync local user:', error);
      return null;
    }
  }, []);

  // Sign in function
  const signIn = useCallback(async (email: string, password: string) => {
    setLoading(true);
    clearError();

    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) throw error;

      if (data.user && data.session) {
        // Sync with backend
        const localUser = await syncLocalUser(data.session);
        setAuthState(data.user, data.session, localUser);
      }
    } catch (error) {
      const message = error instanceof AuthError ? error.message : 'Sign in failed';
      setError(message);
      throw error;
    }
  }, [setLoading, clearError, setAuthState, setError, syncLocalUser]);

  // Sign up function
  const signUp = useCallback(async (email: string, password: string, firstName: string, lastName: string) => {
    setLoading(true);
    clearError();

    try {
      // Use our backend API for signup
      const response: any = await apiClient.post('/auth/signup', {
        email,
        password,
        first_name: firstName,
        last_name: lastName,
      });
      
      // If we get tokens back, we can sign in immediately
      if (response.access_token && response.refresh_token) {
        // Set the auth token for future API calls
        apiClient.setAuthToken(response.access_token);
        
        // Get the session from Supabase using the tokens
        const { data: { session }, error: sessionError } = await supabase.auth.setSession({
          access_token: response.access_token,
          refresh_token: response.refresh_token,
        });
        
        if (sessionError) throw sessionError;
        if (!session) throw new Error('Failed to establish session');
        
        // Sync with local user - we already have localUser from response
        if (response.user) {
          const localUser: LocalUser = {
            id: response.user.id,
            email: response.user.email,
            first_name: response.user.first_name || '',
            last_name: response.user.last_name || '',
            is_admin: response.user.is_admin || false,
          };
          setAuthState(session.user, session, localUser);
        } else {
          // Fallback to sync if user not in response
          const localUser = await syncLocalUser(session);
          setAuthState(session.user, session, localUser);
        }
      } else {
        // Registration successful but no auto-login (might need email confirmation)
        setError('Registration successful! Please check your email to confirm your account.');
        setLoading(false);
        return;
      }
    } catch (error: any) {
      const message = error.response?.data?.message || error.message || 'Sign up failed';
      setError(message);
      throw error;
    }
  }, [setLoading, clearError, setAuthState, setError, syncLocalUser]);

  // Sign out function
  const signOut = useCallback(async () => {
    setLoading(true);
    
    try {
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
    } catch (error) {
      console.error('Sign out error:', error);
      // Continue with sign out even if Supabase call fails
    } finally {
      // Clear all auth data
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      setAuthState(null, null, null);
    }
  }, [setLoading, setAuthState]);

  // Refresh session
  const refreshSession = useCallback(async () => {
    try {
      const { data: { session }, error } = await supabase.auth.refreshSession();
      
      if (error) throw error;

      if (session) {
        const localUser = await syncLocalUser(session);
        setAuthState(session.user, session, localUser);
      } else {
        setAuthState(null, null, null);
      }
    } catch (error) {
      console.error('Session refresh error:', error);
      setAuthState(null, null, null);
    }
  }, [setAuthState, syncLocalUser]);

  // Initialize authentication state
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        // Get initial session
        const { data: { session } } = await supabase.auth.getSession();
        
        if (session) {
          const localUser = await syncLocalUser(session);
          setAuthState(session.user, session, localUser);
        } else {
          setLoading(false);
        }
      } catch (error) {
        console.error('Auth initialization error:', error);
        setLoading(false);
      }
    };

    initializeAuth();

    // Subscribe to auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      console.log('Auth state changed:', event);
      
      if (session) {
        const localUser = await syncLocalUser(session);
        setAuthState(session.user, session, localUser);
      } else {
        setAuthState(null, null, null);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [setLoading, setAuthState, syncLocalUser]);

  const contextValue: AuthContextType = {
    ...state,
    signIn,
    signUp,
    signOut,
    clearError,
    refreshSession,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

export function useSupabaseAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useSupabaseAuth must be used within a SupabaseAuthProvider');
  }
  return context;
}

// Export a compatible interface for existing components
export function useAuth() {
  const { user, localUser, isAuthenticated, isLoading, error, signIn, signUp, signOut, clearError } = useSupabaseAuth();
  
  return {
    user: localUser,
    isAuthenticated,
    isLoading,
    error,
    login: signIn,
    register: signUp,
    logout: signOut,
    clearError,
    refreshUser: async () => {
      const { refreshSession } = useSupabaseAuth();
      await refreshSession();
    },
  };
}

export type { LocalUser as User, AuthState, AuthContextType };