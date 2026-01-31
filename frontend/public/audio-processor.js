/**
 * AudioWorklet processor for capturing and converting audio to 16kHz mono PCM.
 * This runs in a separate audio thread for low-latency processing.
 */
class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 4096; // Samples to accumulate before sending
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
    this.inputSampleRate = 48000; // Will be set from main thread
    this.targetSampleRate = 16000;
    
    this.port.onmessage = (event) => {
      if (event.data.type === 'init') {
        this.inputSampleRate = event.data.sampleRate || 48000;
      }
    };
  }

  /**
   * Downsample audio from input sample rate to 16kHz.
   */
  downsample(inputBuffer, inputSampleRate, outputSampleRate) {
    if (inputSampleRate === outputSampleRate) {
      return inputBuffer;
    }
    
    const ratio = inputSampleRate / outputSampleRate;
    const outputLength = Math.floor(inputBuffer.length / ratio);
    const output = new Float32Array(outputLength);
    
    for (let i = 0; i < outputLength; i++) {
      const srcIndex = i * ratio;
      const srcIndexFloor = Math.floor(srcIndex);
      const srcIndexCeil = Math.min(srcIndexFloor + 1, inputBuffer.length - 1);
      const frac = srcIndex - srcIndexFloor;
      
      // Linear interpolation
      output[i] = inputBuffer[srcIndexFloor] * (1 - frac) + inputBuffer[srcIndexCeil] * frac;
    }
    
    return output;
  }

  /**
   * Convert Float32 samples to Int16 PCM bytes.
   */
  float32ToInt16(float32Array) {
    const int16Array = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      // Clamp to [-1, 1] and convert to Int16 range
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16Array;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) {
      return true;
    }

    // Get first channel (mono)
    const channelData = input[0];
    
    // Add samples to buffer
    for (let i = 0; i < channelData.length; i++) {
      this.buffer[this.bufferIndex++] = channelData[i];
      
      // When buffer is full, process and send
      if (this.bufferIndex >= this.bufferSize) {
        // Downsample to 16kHz
        const downsampled = this.downsample(
          this.buffer,
          this.inputSampleRate,
          this.targetSampleRate
        );
        
        // Convert to Int16 PCM
        const pcmData = this.float32ToInt16(downsampled);
        
        // Send to main thread
        this.port.postMessage({
          type: 'audio',
          data: pcmData.buffer
        }, [pcmData.buffer]);
        
        // Reset buffer
        this.buffer = new Float32Array(this.bufferSize);
        this.bufferIndex = 0;
      }
    }

    return true;
  }
}

registerProcessor('audio-processor', AudioProcessor);
