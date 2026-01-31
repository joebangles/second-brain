import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAudioCapture } from './hooks/useAudioCapture';
import { useWebSocket } from './hooks/useWebSocket';
import { Controls } from './components/Controls';
import { StatusIndicator } from './components/StatusIndicator';
import { TranscriptDisplay } from './components/TranscriptDisplay';
import './App.css';

function App() {
  const audioCapture = useAudioCapture();
  const webSocket = useWebSocket();
  const [mode, setMode] = useState<'voice' | 'chat'>('voice');
  const [chatInput, setChatInput] = useState('');

  const isConnected = webSocket.state.connectionStatus === 'connected';
  const isRecording = webSocket.state.recordingStatus === 'recording';
  const isChatMode = mode === 'chat';

  // Stop audio capture if recording stops (e.g., due to error or disconnect)
  useEffect(() => {
    if (!isRecording && audioCapture.state.isCapturing) {
      audioCapture.stopCapture();
    }
  }, [isRecording, audioCapture]);

  // Ensure recording is stopped when switching to chat mode
  useEffect(() => {
    if (isChatMode) {
      audioCapture.stopCapture();
      webSocket.stop();
    }
  }, [isChatMode, audioCapture, webSocket]);

  const handleStart = useCallback(async () => {
    try {
      // Connect if not already connected
      if (!isConnected) {
        await webSocket.connect();
      }

      // Start recording on server
      await webSocket.start();

      // Start audio capture
      await audioCapture.startCapture((audioData) => {
        webSocket.sendAudio(audioData);
      });
    } catch (err) {
      console.error('Failed to start:', err);
      audioCapture.stopCapture();
    }
  }, [webSocket, audioCapture, isConnected]);

  const handleStop = useCallback(() => {
    // Stop audio capture immediately
    audioCapture.stopCapture();
    
    // Tell server to stop - returns instantly, processing continues in background
    webSocket.stop();
  }, [audioCapture, webSocket]);

  const handleClear = useCallback(() => {
    webSocket.clearMessages();
  }, [webSocket]);

  const handleChatSend = useCallback(async () => {
    const trimmed = chatInput.trim();
    if (!trimmed) {
      return;
    }

    try {
      if (!isConnected) {
        await webSocket.connect();
      }
      webSocket.sendChat(trimmed);
      setChatInput('');
    } catch (err) {
      console.error('Failed to send chat:', err);
    }
  }, [chatInput, isConnected, webSocket]);

  const isChatSendDisabled = useMemo(() => chatInput.trim().length === 0, [chatInput]);

  const error = audioCapture.state.error || webSocket.state.error;

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <h1>
            <BrainIcon />
            Second Brain
          </h1>
          <div className="mode-toggle">
            <button
              className={`mode-btn ${!isChatMode ? 'active' : ''}`}
              onClick={() => setMode('voice')}
              type="button"
            >
              Voice
            </button>
            <button
              className={`mode-btn ${isChatMode ? 'active' : ''}`}
              onClick={() => setMode('chat')}
              type="button"
            >
              Chat
            </button>
          </div>
          <StatusIndicator
            connectionStatus={webSocket.state.connectionStatus}
            isRecording={isRecording && audioCapture.state.isCapturing}
            error={error}
          />
        </div>
      </header>

      <main className="main">
        <TranscriptDisplay 
          messages={webSocket.state.messages} 
          currentPartial={webSocket.state.currentPartial}
          emptyMessage={isChatMode ? 'Ask a question to start chatting' : undefined}
        />
      </main>

      <footer className="footer">
        {isChatMode ? (
          <form
            className="chat-controls"
            onSubmit={(event) => {
              event.preventDefault();
              handleChatSend();
            }}
          >
            <input
              className="chat-input"
              type="text"
              placeholder="Ask your second brain..."
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
            />
            <div className="chat-actions">
              <button
                className="btn btn-secondary"
                type="button"
                onClick={handleClear}
              >
                Clear
              </button>
              <button
                className="btn btn-primary"
                type="submit"
                disabled={isChatSendDisabled}
              >
                Send
              </button>
            </div>
          </form>
        ) : (
          <Controls
            isRecording={isRecording}
            isConnecting={webSocket.state.connectionStatus === 'connecting'}
            onStart={handleStart}
            onStop={handleStop}
            onClear={handleClear}
          />
        )}
      </footer>
    </div>
  );
}

function BrainIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="28"
      height="28"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-1.54" />
      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-1.54" />
    </svg>
  );
}

export default App;
