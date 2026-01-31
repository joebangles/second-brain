import { useCallback, useRef, useState } from 'react';

export interface AudioCaptureState {
  isCapturing: boolean;
  error: string | null;
}

export interface UseAudioCaptureResult {
  state: AudioCaptureState;
  startCapture: (onAudioData: (data: ArrayBuffer) => void) => Promise<void>;
  stopCapture: () => void;
}

/**
 * Hook for capturing microphone audio and converting to 16kHz mono PCM.
 * Uses AudioWorklet for low-latency processing.
 */
export function useAudioCapture(): UseAudioCaptureResult {
  const [state, setState] = useState<AudioCaptureState>({
    isCapturing: false,
    error: null,
  });

  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const onAudioDataRef = useRef<((data: ArrayBuffer) => void) | null>(null);

  const startCapture = useCallback(async (onAudioData: (data: ArrayBuffer) => void) => {
    try {
      setState({ isCapturing: false, error: null });
      onAudioDataRef.current = onAudioData;

      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 48000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      // Create audio context
      const audioContext = new AudioContext({ sampleRate: 48000 });
      audioContextRef.current = audioContext;

      // Load AudioWorklet processor
      await audioContext.audioWorklet.addModule('/audio-processor.js');

      // Create worklet node
      const workletNode = new AudioWorkletNode(audioContext, 'audio-processor');
      workletNodeRef.current = workletNode;

      // Initialize with actual sample rate
      workletNode.port.postMessage({
        type: 'init',
        sampleRate: audioContext.sampleRate,
      });

      // Handle audio data from worklet
      workletNode.port.onmessage = (event) => {
        if (event.data.type === 'audio' && onAudioDataRef.current) {
          onAudioDataRef.current(event.data.data);
        }
      };

      // Connect microphone to worklet
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(workletNode);
      // Don't connect to destination (we don't want to hear ourselves)

      setState({ isCapturing: true, error: null });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to capture audio';
      setState({ isCapturing: false, error: message });
      throw err;
    }
  }, []);

  const stopCapture = useCallback(() => {
    // Stop the media stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    // Disconnect and close worklet
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }

    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    onAudioDataRef.current = null;
    setState({ isCapturing: false, error: null });
  }, []);

  return { state, startCapture, stopCapture };
}
