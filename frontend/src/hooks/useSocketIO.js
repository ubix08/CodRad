/**
 * Socket.IO Client for OpenHands SDK Protocol
 * 
 * Connects to the agent server using the official SDK WebSocket protocol:
 * - Endpoint: /socket.io/
 * - Events: oh_user_action (send), oh_event (receive)
 * 
 * Reference: https://docs.openhands.dev/openhands/usage/developers/websocket-connection
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { io } from 'socket.io-client';

const SOCKET_URL = '';  // Same origin (proxied by Vite)

/**
 * Hook to connect to the agent server using Socket.IO
 * 
 * @param {string} sessionId - The conversation/session ID
 * @param {function} onMessage - Callback for message events
 * @param {function} onAction - Callback for action events
 * @param {function} onError - Callback for error events
 * @param {function} onComplete - Callback when agent finishes
 */
export function useSocketIO(sessionId, options = {}) {
  const {
    onMessage,
    onAction,
    onError,
    onComplete,
    latestEventId = -1,
  } = options;

  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const socketRef = useRef(null);

  // Connect to the server
  useEffect(() => {
    if (!sessionId) return;

    // Create Socket.IO connection with SDK parameters
    const socket = io(SOCKET_URL, {
      transports: ['websocket'],
      query: {
        conversation_id: sessionId,
        latest_event_id: latestEventId,
      },
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    socketRef.current = socket;

    // Connection events
    socket.on('connect', () => {
      console.log('[SocketIO] Connected:', sessionId);
      setConnected(true);
    });

    socket.on('disconnect', (reason) => {
      console.log('[SocketIO] Disconnected:', reason);
      setConnected(false);
    });

    socket.on('connect_error', (error) => {
      console.error('[SocketIO] Connection error:', error.message);
    });

    // SDK protocol events
    socket.on('oh_event', (event) => {
      console.log('[SocketIO] Event:', event.type, event);
      
      const eventType = event.type || event.source;
      
      switch (eventType) {
        case 'message':
          if (onMessage) {
            onMessage({
              content: event.message || '',
              source: event.source,
            });
          }
          break;
          
        case 'action':
          if (onAction) {
            onAction({
              action: event.action,
              args: event.args,
              toolName: event.tool_name,
              id: event.id,
            });
          }
          break;
          
        case 'error':
          if (onError) {
            onError(event.error || event.message);
          }
          setLoading(false);
          break;
          
        case 'completed':
        case 'finished':
          if (onComplete) {
            onComplete(event);
          }
          setLoading(false);
          break;
          
        default:
          console.log('[SocketIO] Unknown event type:', eventType);
      }
    });

    // Cleanup
    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [sessionId]);

  /**
   * Send a user message to the agent
   */
  const sendMessage = useCallback((message) => {
    if (!socketRef.current || !connected) {
      console.error('[SocketIO] Not connected');
      return false;
    }

    setLoading(true);
    socketRef.current.emit('oh_user_action', {
      type: 'message',
      source: 'user',
      message: message,
    });
    
    return true;
  }, [connected]);

  /**
   * Send observation (result of tool execution)
   */
  const sendObservation = useCallback((observation, actionId) => {
    if (!socketRef.current || !connected) {
      console.error('[SocketIO] Not connected');
      return false;
    }

    socketRef.current.emit('oh_user_action', {
      type: 'observation',
      source: 'environment',
      observation: observation,
      action_id: actionId,
    });
    
    return true;
  }, [connected]);

  /**
   * Disconnect from the server
   */
  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
  }, []);

  return {
    connected,
    loading,
    sendMessage,
    sendObservation,
    disconnect,
  };
}

export default useSocketIO;