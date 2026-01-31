import { ConnectionStatus } from '../hooks/useWebSocket';

interface StatusIndicatorProps {
  connectionStatus: ConnectionStatus;
  isRecording: boolean;
  error: string | null;
}

export function StatusIndicator({ 
  connectionStatus, 
  isRecording,
  error 
}: StatusIndicatorProps) {
  const getStatusColor = () => {
    if (error) return '#ef4444'; // red
    if (isRecording) return '#22c55e'; // green
    if (connectionStatus === 'connecting') return '#f59e0b'; // amber
    if (connectionStatus === 'connected') return '#3b82f6'; // blue
    return '#6b7280'; // gray
  };

  const getStatusText = () => {
    if (error) return `Error: ${error}`;
    if (connectionStatus === 'connecting') return 'Connecting...';
    if (isRecording) return 'Listening...';
    if (connectionStatus === 'connected') return 'Ready';
    return 'Disconnected';
  };

  return (
    <div className="status-indicator">
      <div
        className="status-dot"
        style={{ backgroundColor: getStatusColor() }}
      />
      <span className="status-text">{getStatusText()}</span>
    </div>
  );
}
