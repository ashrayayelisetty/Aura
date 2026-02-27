/**
 * WebSocket Service for AURA-VIP Orchestration System
 * 
 * This service manages WebSocket connection to the backend with automatic
 * reconnection using exponential backoff strategy.
 * 
 * Validates Requirements: 16.1, 16.2, 16.3, 16.4, 16.5
 */

// WebSocket message types from backend
export type MessageType = 
  | 'vip_update' 
  | 'escort_update' 
  | 'buggy_update' 
  | 'lounge_update' 
  | 'flight_update';

// WebSocket message structure from backend
export interface WebSocketMessage {
  type: MessageType;
  payload: {
    event_type: string;
    vip_id?: string;
    source_agent: string;
    [key: string]: any;
  };
  timestamp: string;
}

// Event listener callback type
export type MessageListener = (message: WebSocketMessage) => void;

// Connection state
export enum ConnectionState {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  RECONNECTING = 'reconnecting',
}

/**
 * WebSocket Service with automatic reconnection
 * 
 * Features:
 * - Automatic connection establishment
 * - Message parsing and event dispatching
 * - Exponential backoff reconnection (1s to 30s max)
 * - Event listener management for React components
 */
class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private listeners: Map<MessageType, Set<MessageListener>> = new Map();
  private reconnectAttempts: number = 0;
  private reconnectTimeout: number | null = null;
  private maxReconnectDelay: number = 30000; // 30 seconds max
  private initialReconnectDelay: number = 1000; // 1 second initial
  private connectionState: ConnectionState = ConnectionState.DISCONNECTED;
  private stateListeners: Set<(state: ConnectionState) => void> = new Set();

  constructor(url?: string) {
    // Default to localhost:8000 if not provided
    this.url = url || this.getDefaultWebSocketUrl();
  }

  /**
   * Get default WebSocket URL based on current location
   */
  private getDefaultWebSocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port = import.meta.env.VITE_WS_PORT || '8000';
    return `${protocol}//${host}:${port}/ws`;
  }

  /**
   * Connect to WebSocket server
   * Validates: Requirement 16.1
   */
  public connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log('[WebSocket] Already connected');
      return;
    }

    if (this.ws?.readyState === WebSocket.CONNECTING) {
      console.log('[WebSocket] Connection already in progress');
      return;
    }

    this.setConnectionState(ConnectionState.CONNECTING);
    console.log(`[WebSocket] Connecting to ${this.url}`);

    try {
      this.ws = new WebSocket(this.url);
      this.setupEventHandlers();
    } catch (error) {
      console.error('[WebSocket] Connection error:', error);
      this.handleConnectionError();
    }
  }

  /**
   * Setup WebSocket event handlers
   */
  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('[WebSocket] Connected successfully');
      this.setConnectionState(ConnectionState.CONNECTED);
      this.reconnectAttempts = 0; // Reset reconnect attempts on successful connection
      
      // Clear any pending reconnect timeout
      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout);
        this.reconnectTimeout = null;
      }
    };

    this.ws.onmessage = (event: MessageEvent) => {
      this.handleMessage(event);
    };

    this.ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
    };

    this.ws.onclose = (event) => {
      console.log(`[WebSocket] Connection closed (code: ${event.code}, reason: ${event.reason})`);
      this.setConnectionState(ConnectionState.DISCONNECTED);
      this.handleConnectionError();
    };
  }

  /**
   * Handle incoming WebSocket message
   * Validates: Requirement 16.2, 16.3, 16.5
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      
      console.log(`[WebSocket] Received ${message.type}:`, message);

      // Dispatch to registered listeners for this message type
      const listeners = this.listeners.get(message.type);
      if (listeners) {
        listeners.forEach(listener => {
          try {
            listener(message);
          } catch (error) {
            console.error(`[WebSocket] Error in listener for ${message.type}:`, error);
          }
        });
      }
    } catch (error) {
      console.error('[WebSocket] Error parsing message:', error);
    }
  }

  /**
   * Handle connection error and trigger reconnection
   * Validates: Requirement 16.4
   */
  private handleConnectionError(): void {
    // Don't reconnect if we're already trying to reconnect
    if (this.reconnectTimeout) {
      return;
    }

    this.setConnectionState(ConnectionState.RECONNECTING);

    // Calculate exponential backoff delay
    const delay = Math.min(
      this.initialReconnectDelay * Math.pow(2, this.reconnectAttempts),
      this.maxReconnectDelay
    );

    this.reconnectAttempts++;
    
    console.log(
      `[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})...`
    );

    this.reconnectTimeout = setTimeout(() => {
      this.reconnectTimeout = null;
      this.connect();
    }, delay);
  }

  /**
   * Subscribe to specific message type
   * 
   * @param type - Message type to listen for
   * @param listener - Callback function to handle messages
   * @returns Unsubscribe function
   */
  public subscribe(type: MessageType, listener: MessageListener): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    
    this.listeners.get(type)!.add(listener);
    console.log(`[WebSocket] Subscribed to ${type} (${this.listeners.get(type)!.size} listeners)`);

    // Return unsubscribe function
    return () => {
      const listeners = this.listeners.get(type);
      if (listeners) {
        listeners.delete(listener);
        console.log(`[WebSocket] Unsubscribed from ${type} (${listeners.size} listeners remaining)`);
      }
    };
  }

  /**
   * Subscribe to connection state changes
   * 
   * @param listener - Callback function to handle state changes
   * @returns Unsubscribe function
   */
  public onStateChange(listener: (state: ConnectionState) => void): () => void {
    this.stateListeners.add(listener);
    
    // Immediately call with current state
    listener(this.connectionState);

    // Return unsubscribe function
    return () => {
      this.stateListeners.delete(listener);
    };
  }

  /**
   * Update connection state and notify listeners
   */
  private setConnectionState(state: ConnectionState): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.stateListeners.forEach(listener => {
        try {
          listener(state);
        } catch (error) {
          console.error('[WebSocket] Error in state listener:', error);
        }
      });
    }
  }

  /**
   * Get current connection state
   */
  public getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  /**
   * Check if WebSocket is connected
   */
  public isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Disconnect from WebSocket server
   */
  public disconnect(): void {
    console.log('[WebSocket] Disconnecting...');
    
    // Clear reconnect timeout
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    // Close WebSocket connection
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.setConnectionState(ConnectionState.DISCONNECTED);
  }

  /**
   * Clear all listeners
   */
  public clearListeners(): void {
    this.listeners.clear();
    this.stateListeners.clear();
    console.log('[WebSocket] All listeners cleared');
  }
}

// Export singleton instance
export const websocketService = new WebSocketService();

// Export class for testing
export { WebSocketService };
