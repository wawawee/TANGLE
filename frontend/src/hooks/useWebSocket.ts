import { useState, useCallback, useRef, useEffect } from 'react';
import type { AgentThought, EventLogEntry, ProgressUpdate } from '../types/websocket';

interface UseWebSocketOptions {
  onProgress: (update: ProgressUpdate) => void;
  onAgentThought: (thought: AgentThought) => void;
  onEventLog: (entry: EventLogEntry) => void;
  onTokenUsage?: (usage: any) => void;
  onComplete: (deliverables: unknown) => void;
  onError: (error: Error) => void;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const connect = useCallback((url: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    console.log(`🔌 Connecting to WebSocket at ${url}`);
    const ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('🔌 WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case 'EVENT_LOG':
            options.onEventLog(data.payload);
            break;
          case 'AGENT_THOUGHT':
            options.onAgentThought(data.payload);
            break;
          case 'PROGRESS':
            options.onProgress(data.payload);
            break;
          case 'TOKEN_USAGE':
            if (options.onTokenUsage) {
              options.onTokenUsage(data.payload);
            }
            break;
          case 'COMPLETE':
            options.onComplete(data.payload);
            break;
          case 'ERROR':
            options.onError(new Error(data.payload));
            break;
          default:
            console.warn('Unknown message type:', data.type);
        }
      } catch (err) {
        console.error('Error parsing WebSocket message:', err);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      options.onError(new Error('WebSocket connection error'));
    };

    ws.onclose = () => {
      console.log('🔌 WebSocket disconnected');
      setIsConnected(false);
      wsRef.current = null;
    };

    wsRef.current = ws;

  }, [options]);

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimeoutRef.current);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((type: string, payload: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    } else {
      console.warn('Cannot send message: WebSocket is not connected');
    }
  }, []);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    connect,
    disconnect,
    sendMessage,
    isConnected
  };
}
