import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { getAccessToken } from '../services/supabase';

interface WebSocketMessage {
  type: 'log' | 'progress' | 'status' | 'error' | 'complete' | 
        'operation_start' | 'operation_progress' | 'operation_log' | 
        'operation_complete' | 'sync_status' | 'import_status';
  data: any;
  timestamp: string;
}

interface WebSocketContextType {
  isConnected: boolean;
  sendMessage: (message: any) => void;
  subscribe: (type: string, callback: (data: any) => void) => () => void;
  lastMessage: WebSocketMessage | null;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

interface WebSocketProviderProps {
  children: React.ReactNode;
  url?: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  enableWebSocket?: boolean;
}

export function SupabaseWebSocketProvider({ 
  children, 
  url = process.env.REACT_APP_WEBSOCKET_URL || '',
  reconnectInterval = 5000,
  maxReconnectAttempts = 5,
  enableWebSocket = true  // Enabled by default with Supabase auth
}: WebSocketProviderProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const subscribersRef = useRef<Map<string, Set<(data: any) => void>>>(new Map());
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(async () => {
    // Skip WebSocket connection if disabled
    if (!enableWebSocket) {
      console.log('WebSocket disabled');
      return;
    }

    // Get Supabase access token
    const token = await getAccessToken();
    if (!token) {
      console.log('No auth token available, skipping WebSocket connection');
      // Try to reconnect after interval
      reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);
      return;
    }
    
    try {
      const socket = io(url, {
        reconnection: true,
        reconnectionDelay: reconnectInterval,
        reconnectionAttempts: maxReconnectAttempts,
        transports: ['websocket', 'polling'],
        auth: {
          token: token  // Send Supabase token for authentication
        }
      });
      
      socketRef.current = socket;

      socket.on('connect', () => {
        console.log('Socket.IO connected with Supabase auth');
        setIsConnected(true);
        // Clear any reconnect timeout
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
      });

      socket.on('disconnect', () => {
        console.log('Socket.IO disconnected');
        setIsConnected(false);
      });

      socket.on('connect_error', async (error: any) => {
        console.error('Socket.IO connection error:', error);
        
        // If auth error, try to refresh token
        if (error.message?.includes('401') || error.message?.includes('Unauthorized')) {
          console.log('Auth error, attempting to refresh token...');
          const newToken = await getAccessToken();
          if (newToken && socket.auth && typeof socket.auth !== 'function') {
            socket.auth.token = newToken;
            socket.connect();
          }
        }
      });

      // Listen for all message types
      const eventTypes = [
        'log', 'progress', 'status', 'error', 'complete',
        'operation_start', 'operation_progress', 'operation_log', 
        'operation_complete', 'sync_status', 'import_status'
      ];
      
      eventTypes.forEach(eventType => {
        socket.on(eventType, (data) => {
          const message: WebSocketMessage = {
            type: eventType as any,
            data: data.data || data,
            timestamp: data.timestamp || new Date().toISOString()
          };
          
          setLastMessage(message);

          // Notify subscribers
          const subscribers = subscribersRef.current.get(eventType);
          if (subscribers) {
            subscribers.forEach(callback => callback(message.data));
          }

          // Also notify wildcard subscribers
          const wildcardSubscribers = subscribersRef.current.get('*');
          if (wildcardSubscribers) {
            wildcardSubscribers.forEach(callback => callback(message));
          }
        });
      });

      // Handle authentication errors
      socket.on('error', (error: any) => {
        if (error.type === 'auth' || error.message?.includes('Authentication')) {
          console.error('WebSocket authentication error:', error);
          // Disconnect and try to reconnect with fresh token
          socket.disconnect();
          setTimeout(connect, reconnectInterval);
        }
      });

    } catch (error) {
      console.error('Failed to create Socket.IO connection:', error);
      // Try to reconnect after interval
      reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);
    }
  }, [url, reconnectInterval, maxReconnectAttempts, enableWebSocket]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (socketRef.current && socketRef.current.connected) {
      // Emit based on message type or use a default event
      const eventType = message.type || 'execute';
      socketRef.current.emit(eventType, message);
    } else {
      console.log('WebSocket not connected, message queued:', message);
      // Optionally, queue messages to send when connected
    }
  }, []);

  const subscribe = useCallback((type: string, callback: (data: any) => void) => {
    if (!subscribersRef.current.has(type)) {
      subscribersRef.current.set(type, new Set());
    }
    subscribersRef.current.get(type)!.add(callback);

    // Return unsubscribe function
    return () => {
      const subscribers = subscribersRef.current.get(type);
      if (subscribers) {
        subscribers.delete(callback);
        if (subscribers.size === 0) {
          subscribersRef.current.delete(type);
        }
      }
    };
  }, []);

  // Reconnect when auth state changes
  useEffect(() => {
    const checkAuthAndConnect = async () => {
      try {
        const token = await getAccessToken();
        if (token && !socketRef.current?.connected) {
          connect();
        } else if (!token && socketRef.current?.connected) {
          disconnect();
        }
      } catch (error) {
        console.error('Error checking auth state:', error);
        // If we can't get token, disconnect
        if (socketRef.current?.connected) {
          disconnect();
        }
      }
    };

    // Check auth state periodically
    const interval = setInterval(checkAuthAndConnect, 30000); // Every 30 seconds

    // Initial connection
    checkAuthAndConnect();

    return () => {
      clearInterval(interval);
      disconnect();
    };
  }, [connect, disconnect]);

  const value: WebSocketContextType = {
    isConnected,
    sendMessage,
    subscribe,
    lastMessage
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

// Export for backward compatibility
export const WebSocketProvider = SupabaseWebSocketProvider;