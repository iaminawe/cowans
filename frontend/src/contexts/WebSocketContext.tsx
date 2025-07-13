import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { 
  WebSocketMessage, 
  WebSocketData, 
  WebSocketCallback, 
  OutgoingWebSocketMessage,
  WebSocketEventMap 
} from '@/types/websocket';

interface WebSocketContextType {
  isConnected: boolean;
  sendMessage: (message: OutgoingWebSocketMessage) => void;
  subscribe: <K extends keyof WebSocketEventMap>(type: K, callback: WebSocketCallback<WebSocketEventMap[K]>) => () => void;
  subscribeCustom: (type: string, callback: WebSocketCallback) => () => void;
  subscribeWildcard: (callback: (message: WebSocketMessage) => void) => () => void;
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
  const subscribersRef = useRef<Map<string, Set<WebSocketCallback>>>(new Map());
  const wildcardSubscribersRef = useRef<Set<(message: WebSocketMessage) => void>>(new Set());

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
        socket.on(eventType, (data: unknown) => {
          const message: WebSocketMessage = {
            type: eventType as WebSocketMessage['type'],
            data: (data && typeof data === 'object' && 'data' in data) 
              ? (data as { data: WebSocketData }).data 
              : data as WebSocketData,
            timestamp: (data && typeof data === 'object' && 'timestamp' in data) 
              ? (data as { timestamp: string }).timestamp 
              : new Date().toISOString()
          };
          
          setLastMessage(message);

          // Notify subscribers
          const subscribers = subscribersRef.current.get(eventType);
          if (subscribers) {
            subscribers.forEach(callback => callback(message.data));
          }

          // Also notify wildcard subscribers
          const wildcardSubscribers = wildcardSubscribersRef.current;
          wildcardSubscribers.forEach(callback => callback(message));
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

  const sendMessage = useCallback((message: OutgoingWebSocketMessage) => {
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

  const subscribe = useCallback(<K extends keyof WebSocketEventMap>(
    type: K, 
    callback: WebSocketCallback<WebSocketEventMap[K]>
  ) => {
    const typeString = type as string;
    if (!subscribersRef.current.has(typeString)) {
      subscribersRef.current.set(typeString, new Set());
    }
    subscribersRef.current.get(typeString)!.add(callback as WebSocketCallback);

    // Return unsubscribe function
    return () => {
      const subscribers = subscribersRef.current.get(typeString);
      if (subscribers) {
        subscribers.delete(callback as WebSocketCallback);
        if (subscribers.size === 0) {
          subscribersRef.current.delete(typeString);
        }
      }
    };
  }, []);

  const subscribeCustom = useCallback((type: string, callback: WebSocketCallback) => {
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

  const subscribeWildcard = useCallback((callback: (message: WebSocketMessage) => void) => {
    wildcardSubscribersRef.current.add(callback);

    // Return unsubscribe function
    return () => {
      wildcardSubscribersRef.current.delete(callback);
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
    subscribeCustom,
    subscribeWildcard,
    lastMessage
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}