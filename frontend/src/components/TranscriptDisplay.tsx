import { useEffect, useRef } from 'react';
import { Message } from '../hooks/useWebSocket';

interface TranscriptDisplayProps {
  messages: Message[];
  currentPartial: string | null;
  emptyMessage?: string;
}

export function TranscriptDisplay({ messages, currentPartial, emptyMessage }: TranscriptDisplayProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages, currentPartial]);

  if (messages.length === 0 && !currentPartial) {
    return (
      <div className="transcript-container">
        <div className="transcript-empty">
          <BrainIcon />
          <p>{emptyMessage || 'Start listening to see transcriptions here'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="transcript-container" ref={containerRef}>
      {messages.map((message) => (
        <MessageCard key={message.id} message={message} />
      ))}
      {currentPartial && (
        <div className="message-card transcribing">
          <div className="message-header">
            <span className="status-badge transcribing">
              <span className="pulse-dot" />
              Listening...
            </span>
          </div>
          <div className="message-utterance">{currentPartial}</div>
        </div>
      )}
    </div>
  );
}

function MessageCard({ message }: { message: Message }) {
  const getStatusBadge = () => {
    switch (message.status) {
      case 'transcribing':
        return (
          <span className="status-badge transcribing">
            <span className="pulse-dot" />
            Listening...
          </span>
        );
      case 'processing':
        return (
          <span className="status-badge processing">
            <span className="spinner-small" />
            Processing...
          </span>
        );
      case 'complete':
        return (
          <span className="status-badge complete">
            <CheckIcon />
            Complete
          </span>
        );
      case 'error':
        return (
          <span className="status-badge error">
            <ErrorIcon />
            Error
          </span>
        );
    }
  };

  return (
    <div className={`message-card ${message.status}`}>
      <div className="message-header">
        <div className="message-header-left">
          {getStatusBadge()}
          <span className={`source-badge ${message.source}`}>
            {message.source === 'voice' ? 'Capture' : 'Recall'}
          </span>
        </div>
        <span className="timestamp">
          {message.timestamp.toLocaleTimeString()}
        </span>
      </div>
      
      <div className="message-utterance">
        <span className="utterance-label">You:</span>
        {message.text}
      </div>

      {message.status === 'complete' && message.agentResponse && (
        <div className="message-response">
          <span className="response-label">Brain:</span>
          {message.agentResponse}
        </div>
      )}

      {message.status === 'error' && message.error && (
        <div className="message-error">
          {message.error}
        </div>
      )}

      {message.toolsUsed && message.toolsUsed.length > 0 && (
        <div className="tools-used">
          {message.toolsUsed.map((tool) => (
            <span key={tool} className="tool-badge">
              {formatToolName(tool)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function formatToolName(tool: string): string {
  // Convert snake_case to Title Case
  return tool
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function BrainIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="brain-icon"
    >
      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-1.54" />
      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-1.54" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  );
}
