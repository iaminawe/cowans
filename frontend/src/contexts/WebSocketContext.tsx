import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';

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

export function WebSocketProvider({ 
  children, 
  url = process.env.REACT_APP_WEBSOCKET_URL || '',
  reconnectInterval = 5000,
  maxReconnectAttempts = 5,
  enableWebSocket = false
}: WebSocketProviderProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const subscribersRef = useRef<Map<string, Set<(data: any) => void>>>(new Map());

  const connect = useCallback(() => {
    // Skip WebSocket connection if disabled
    if (!enableWebSocket) {
      console.log('WebSocket disabled');
      return;
    }
    
    try {
      // Get auth token for WebSocket authentication
      const authToken = localStorage.getItem('auth_token');
      
      const socket = io(url, {
        reconnection: true,
        reconnectionDelay: reconnectInterval,
        reconnectionAttempts: maxReconnectAttempts,
        transports: ['polling', 'websocket'], // Start with polling for better compatibility
        auth: authToken ? { token: authToken } : undefined,
        withCredentials: true,
        autoConnect: true
      });
      
      socketRef.current = socket;

      socket.on('connect', () => {
        console.log('Socket.IO connected');
        setIsConnected(true);
      });

      socket.on('disconnect', () => {
        console.log('Socket.IO disconnected');
        setIsConnected(false);
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

      socket.on('connect_error', (error) => {
        console.warn('Socket.IO connection error:', error.message || error);
        // Don't log full error object to avoid console spam
        // Connection will retry automatically based on settings
      });
    } catch (error) {
      console.error('Failed to create Socket.IO connection:', error);
    }
  }, [url, reconnectInterval, maxReconnectAttempts, enableWebSocket]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (socketRef.current && socketRef.current.connected) {
      // Emit based on message type or use a default event
      const eventType = message.type || 'execute';
      socketRef.current.emit(eventType, message);
    } else {
      // WebSocket not available - this is expected in minimal backend mode
      if (enableWebSocket) {
        console.debug('WebSocket not connected, message queued:', message.type);
      }
    }
  }, [enableWebSocket]);

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

  useEffect(() => {
    connect();
    return () => {
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