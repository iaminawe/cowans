import { io, Socket } from 'socket.io-client';
import { supabase } from './supabase';
import { errorHandler } from './errorHandler';

export interface WebSocketConfig {
  url: string;
  reconnectionAttempts?: number;
  reconnectionDelay?: number;
  timeout?: number;
  enableHeartbeat?: boolean;
  heartbeatInterval?: number;
}

export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: number;
  id: string;
}

export interface ConnectionState {
  status: 'disconnected' | 'connecting' | 'connected' | 'authenticated' | 'error';
  lastConnected?: Date;
  reconnectAttempts: number;
  latency?: number;
}

class SecureWebSocketService {
  private socket: Socket | null = null;
  private config: WebSocketConfig;
  private state: ConnectionState = {
    status: 'disconnected',
    reconnectAttempts: 0,
  };
  private messageQueue: WebSocketMessage[] = [];
  private eventListeners = new Map<string, Set<Function>>();
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private latencyCheckInterval: NodeJS.Timeout | null = null;

  constructor(config: WebSocketConfig) {
    this.config = {
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      timeout: 10000,
      enableHeartbeat: true,
      heartbeatInterval: 30000,
      ...config,
    };
  }

  /**
   * Connect to WebSocket server with Supabase authentication
   */
  async connect(): Promise<void> {
    try {
      this.updateState({ status: 'connecting' });

      // Get current Supabase session
      const { data: { session }, error } = await supabase.auth.getSession();
      
      if (error || !session) {
        throw new Error('No valid authentication session');
      }

      // Create socket connection with auth token
      this.socket = io(this.config.url, {
        auth: {
          token: session.access_token,
          user_id: session.user.id,
        },
        timeout: this.config.timeout,
        reconnection: true,
        reconnectionAttempts: this.config.reconnectionAttempts,
        reconnectionDelay: this.config.reconnectionDelay,
        transports: ['websocket', 'polling'],
      });

      await this.setupEventHandlers();
      
      // Wait for successful connection and authentication
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Connection timeout'));
        }, this.config.timeout);

        this.socket!.on('connect', () => {
          clearTimeout(timeout);
          this.updateState({ 
            status: 'connected',
            lastConnected: new Date(),
            reconnectAttempts: 0,
          });
        });

        this.socket!.on('authenticated', () => {
          this.updateState({ status: 'authenticated' });
          this.processPendingMessages();
          this.startHeartbeat();
          this.startLatencyCheck();
          resolve();
        });

        this.socket!.on('connect_error', (error) => {
          clearTimeout(timeout);
          reject(error);
        });

        this.socket!.on('auth_error', (error) => {
          clearTimeout(timeout);
          reject(new Error(`Authentication failed: ${error.message}`));
        });
      });

    } catch (error) {
      this.updateState({ status: 'error' });
      errorHandler.handle(error, 'WebSocket Connection', {
        fallbackMessage: 'Failed to connect to real-time service',
      });
      throw error;
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    if (this.socket) {
      this.stopHeartbeat();
      this.stopLatencyCheck();
      this.socket.disconnect();
      this.socket = null;
    }
    this.updateState({ status: 'disconnected' });
  }

  /**
   * Send message to server
   */
  send(type: string, data: any): void {
    const message: WebSocketMessage = {
      type,
      data,
      timestamp: Date.now(),
      id: crypto.randomUUID(),
    };

    if (this.state.status === 'authenticated' && this.socket?.connected) {
      this.socket.emit(type, data);
    } else {
      // Queue message for when connection is restored
      this.messageQueue.push(message);
      
      // Attempt to reconnect if not already connecting
      if (this.state.status === 'disconnected') {
        this.connect().catch(error => {
          errorHandler.handle(error, 'WebSocket Reconnect');
        });
      }
    }
  }

  /**
   * Subscribe to server events
   */
  on(event: string, callback: Function): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }
    this.eventListeners.get(event)!.add(callback);

    // If socket is already connected, register the listener immediately
    if (this.socket) {
      this.socket.on(event, callback as any);
    }
  }

  /**
   * Unsubscribe from server events
   */
  off(event: string, callback?: Function): void {
    if (callback) {
      this.eventListeners.get(event)?.delete(callback);
      if (this.socket) {
        this.socket.off(event, callback as any);
      }
    } else {
      this.eventListeners.delete(event);
      if (this.socket) {
        this.socket.off(event);
      }
    }
  }

  /**
   * Get current connection state
   */
  getState(): ConnectionState {
    return { ...this.state };
  }

  /**
   * Check if connected and authenticated
   */
  isConnected(): boolean {
    return this.state.status === 'authenticated' && this.socket?.connected === true;
  }

  /**
   * Setup socket event handlers
   */
  private async setupEventHandlers(): Promise<void> {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.updateState({ status: 'connected' });
    });

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      this.updateState({ status: 'disconnected' });
      this.stopHeartbeat();
      this.stopLatencyCheck();
    });

    this.socket.on('reconnect', (attemptNumber) => {
      console.log('WebSocket reconnected after', attemptNumber, 'attempts');
      this.updateState({ 
        status: 'connected',
        reconnectAttempts: attemptNumber,
        lastConnected: new Date(),
      });
    });

    this.socket.on('reconnect_attempt', (attemptNumber) => {
      console.log('WebSocket reconnect attempt:', attemptNumber);
      this.updateState({ 
        status: 'connecting',
        reconnectAttempts: attemptNumber,
      });
    });

    this.socket.on('reconnect_error', (error) => {
      console.error('WebSocket reconnect error:', error);
      errorHandler.handle(error, 'WebSocket Reconnect', {
        showToast: false, // Avoid spam during reconnection attempts
      });
    });

    this.socket.on('reconnect_failed', () => {
      console.error('WebSocket reconnection failed');
      this.updateState({ status: 'error' });
      errorHandler.handle(
        new Error('Failed to reconnect to real-time service'),
        'WebSocket Reconnect',
        { fallbackMessage: 'Lost connection to real-time service' }
      );
    });

    this.socket.on('auth_error', (error) => {
      console.error('WebSocket auth error:', error);
      this.updateState({ status: 'error' });
      errorHandler.handle(error, 'WebSocket Authentication');
    });

    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error);
      errorHandler.handle(error, 'WebSocket Error');
    });

    // Handle token refresh
    this.socket.on('token_expired', async () => {
      try {
        const { data: { session }, error } = await supabase.auth.getSession();
        if (error || !session) {
          throw new Error('Failed to refresh authentication');
        }
        
        // Send new token to server
        this.socket!.emit('refresh_token', {
          token: session.access_token,
        });
      } catch (error) {
        errorHandler.handle(error, 'Token Refresh');
        this.disconnect();
      }
    });

    // Register existing event listeners
    this.eventListeners.forEach((callbacks, event) => {
      callbacks.forEach(callback => {
        this.socket!.on(event, callback as any);
      });
    });
  }

  /**
   * Process queued messages when connection is restored
   */
  private processPendingMessages(): void {
    if (this.messageQueue.length === 0) return;

    console.log(`Processing ${this.messageQueue.length} queued messages`);
    
    for (const message of this.messageQueue) {
      if (this.socket?.connected) {
        this.socket.emit(message.type, message.data);
      }
    }
    
    this.messageQueue = [];
  }

  /**
   * Start heartbeat to maintain connection
   */
  private startHeartbeat(): void {
    if (!this.config.enableHeartbeat) return;

    this.heartbeatInterval = setInterval(() => {
      if (this.socket?.connected) {
        this.socket.emit('ping', { timestamp: Date.now() });
      }
    }, this.config.heartbeatInterval);
  }

  /**
   * Stop heartbeat
   */
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /**
   * Start latency monitoring
   */
  private startLatencyCheck(): void {
    this.latencyCheckInterval = setInterval(() => {
      if (this.socket?.connected) {
        const start = Date.now();
        this.socket.emit('ping', { timestamp: start }, () => {
          const latency = Date.now() - start;
          this.updateState({ latency });
        });
      }
    }, 10000); // Check every 10 seconds
  }

  /**
   * Stop latency monitoring
   */
  private stopLatencyCheck(): void {
    if (this.latencyCheckInterval) {
      clearInterval(this.latencyCheckInterval);
      this.latencyCheckInterval = null;
    }
  }

  /**
   * Update connection state
   */
  private updateState(updates: Partial<ConnectionState>): void {
    this.state = { ...this.state, ...updates };
    
    // Emit state change event for UI updates
    if (this.eventListeners.has('state_change')) {
      this.eventListeners.get('state_change')!.forEach(callback => {
        callback(this.state);
      });
    }
  }
}

// Create singleton instance
export const secureWebSocket = new SecureWebSocketService({
  url: process.env.REACT_APP_WEBSOCKET_URL || '',
});

export default secureWebSocket;