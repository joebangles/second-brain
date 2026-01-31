import { useCallback, useRef, useState } from 'react';

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';
export type RecordingStatus = 'idle' | 'recording';

export type MessageStatus = 'transcribing' | 'processing' | 'complete' | 'error';
export type MessageSource = 'voice' | 'chat';

export interface Message {
  id: string;
  text: string;  // The utterance text
  status: MessageStatus;
  source: MessageSource;
  agentResponse?: string;
  toolsUsed?: string[];
  agentsUsed?: string[];
  error?: string;
  timestamp: Date;
}

export interface WebSocketState {
  connectionStatus: ConnectionStatus;
  recordingStatus: RecordingStatus;
  error: string | null;
  messages: Message[];
  currentPartial: string | null;
}

export interface UseWebSocketResult {
  state: WebSocketState;
  connect: () => Promise<void>;
  disconnect: () => void;
  start: () => Promise<void>;
  stop: () => void;
  sendAudio: (data: ArrayBuffer) => void;
  sendChat: (text: string) => void;
  clearMessages: () => void;
}

/**
 * Hook for managing WebSocket connection to the backend.
 * Supports stop/start cycles without disconnecting.
 */
export function useWebSocket(): UseWebSocketResult {
  const [state, setState] = useState<WebSocketState>({
    connectionStatus: 'disconnected',
    recordingStatus: 'idle',
    error: null,
    messages: [],
    currentPartial: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const messageIdRef = useRef(0);
  const startResolveRef = useRef<(() => void) | null>(null);
  const startRejectRef = useRef<((err: Error) => void) | null>(null);

  // Find message by utterance text (for matching agent responses)
  const findMessageByText = useCallback((text: string, messages: Message[]): number => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].text === text && messages[i].status === 'processing') {
        return i;
      }
    }
    return -1;
  }, []);

  const connect = useCallback(async () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    const wsUrl = import.meta.env.VITE_BACKEND_WS_URL || 'ws://localhost:8000/ws/transcribe';

    setState((prev) => ({ ...prev, connectionStatus: 'connecting', error: null }));

    return new Promise<void>((resolve, reject) => {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setState((prev) => ({ ...prev, connectionStatus: 'connected' }));
          resolve();
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            switch (data.type) {
              case 'started':
                setState((prev) => ({ ...prev, recordingStatus: 'recording' }));
                if (startResolveRef.current) {
                  startResolveRef.current();
                  startResolveRef.current = null;
                  startRejectRef.current = null;
                }
                break;

              case 'stopped':
                // Server confirms stop - state already updated locally
                setState((prev) => ({ 
                  ...prev, 
                  recordingStatus: 'idle',
                  currentPartial: null 
                }));
                break;

              case 'recording_state':
                setState((prev) => ({
                  ...prev,
                  recordingStatus: data.state as RecordingStatus,
                }));
                break;

              case 'partial':
                setState((prev) => ({ ...prev, currentPartial: data.text }));
                break;

              case 'final':
                setState((prev) => ({
                  ...prev,
                  currentPartial: (prev.currentPartial || '') + data.text,
                }));
                break;

              case 'end_of_utterance':
                setState((prev) => {
                  const newMessage: Message = {
                    id: `msg-${++messageIdRef.current}`,
                    text: data.text,
                    status: 'processing',
                    source: 'voice',
                    timestamp: new Date(),
                  };
                  return {
                    ...prev,
                    messages: [...prev.messages, newMessage],
                    currentPartial: null,
                  };
                });
                break;

              case 'agent_response':
                setState((prev) => {
                  const idx = findMessageByText(data.prompt, prev.messages);
                  if (idx === -1) {
                    const newMessage: Message = {
                      id: `msg-${++messageIdRef.current}`,
                      text: data.prompt,
                      status: 'complete',
                      source: 'voice',
                      agentResponse: data.text,
                      toolsUsed: data.tools_used,
                      agentsUsed: data.agents_used,
                      timestamp: new Date(),
                    };
                    return { ...prev, messages: [...prev.messages, newMessage] };
                  }
                  
                  const updated = [...prev.messages];
                  updated[idx] = {
                    ...updated[idx],
                    status: 'complete',
                    source: updated[idx].source || 'voice',
                    agentResponse: data.text,
                    toolsUsed: data.tools_used,
                    agentsUsed: data.agents_used,
                  };
                  return { ...prev, messages: updated };
                });
                break;

              case 'agent_error':
                setState((prev) => {
                  const idx = findMessageByText(data.prompt, prev.messages);
                  if (idx === -1) return prev;
                  
                  const updated = [...prev.messages];
                  updated[idx] = {
                    ...updated[idx],
                    status: 'error',
                    source: updated[idx].source || 'voice',
                    error: data.message,
                  };
                  return { ...prev, messages: updated };
                });
                break;

              case 'error':
                setState((prev) => ({ ...prev, error: data.message }));
                if (startRejectRef.current) {
                  startRejectRef.current(new Error(data.message));
                  startResolveRef.current = null;
                  startRejectRef.current = null;
                }
                break;
            }
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err);
          }
        };

        ws.onerror = () => {
          setState((prev) => ({
            ...prev,
            connectionStatus: 'error',
            error: 'WebSocket connection error',
          }));
          reject(new Error('WebSocket connection error'));
        };

        ws.onclose = () => {
          setState((prev) => ({
            ...prev,
            connectionStatus: 'disconnected',
            recordingStatus: 'idle',
            currentPartial: null,
          }));
          wsRef.current = null;
        };
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to connect';
        setState((prev) => ({ ...prev, connectionStatus: 'error', error: message }));
        reject(err);
      }
    });
  }, [findMessageByText]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setState((prev) => ({ 
      ...prev, 
      connectionStatus: 'disconnected',
      recordingStatus: 'idle',
      currentPartial: null 
    }));
  }, []);

  const start = useCallback(async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected');
    }

    return new Promise<void>((resolve, reject) => {
      startResolveRef.current = resolve;
      startRejectRef.current = reject;
      
      wsRef.current!.send(JSON.stringify({
        type: 'start',
        sampleRate: 16000,
        language: 'en',
      }));

      // Timeout after 10 seconds
      setTimeout(() => {
        if (startResolveRef.current) {
          startRejectRef.current?.(new Error('Start timeout'));
          startResolveRef.current = null;
          startRejectRef.current = null;
        }
      }, 10000);
    });
  }, []);

  const stop = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setState((prev) => ({ ...prev, recordingStatus: 'idle' }));
      return;
    }

    // Send stop and immediately update state - don't wait for response
    wsRef.current.send(JSON.stringify({ type: 'stop' }));
    setState((prev) => ({ ...prev, recordingStatus: 'idle', currentPartial: null }));
  }, []);

  const sendAudio = useCallback((data: ArrayBuffer) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  const sendChat = useCallback((text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected');
    }

    const trimmed = text.trim();
    if (!trimmed) {
      return;
    }

    setState((prev) => {
      const newMessage: Message = {
        id: `msg-${++messageIdRef.current}`,
        text: trimmed,
        status: 'processing',
        source: 'chat',
        timestamp: new Date(),
      };
      return {
        ...prev,
        messages: [...prev.messages, newMessage],
        currentPartial: null,
      };
    });

    wsRef.current.send(JSON.stringify({ type: 'chat', text: trimmed }));
  }, []);

  const clearMessages = useCallback(() => {
    setState((prev) => ({ ...prev, messages: [], currentPartial: null }));
  }, []);

  return { state, connect, disconnect, start, stop, sendAudio, sendChat, clearMessages };
}
