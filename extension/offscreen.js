const WS_URL = 'ws://localhost:8001/ws/audio/';

let audioStream = null;
let sessionId = null;
let audioContext = null;
let scriptProcessor = null;
let chunkCounter = 0;
let sampleRate = 48000;
let recordingBuffers = [];
let websocket = null;
let recordingMetadata = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'start-recording') {
    recordingMetadata = message.metadata || null;
    console.log('[Offscreen] Received metadata:', recordingMetadata);

    startRecording(message.streamId, message.sessionId)
      .then(() => sendResponse({ success: true }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }

  if (message.type === 'stop-recording') {
    stopRecording()
      .then(() => sendResponse({ success: true }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }
});

async function startRecording(streamId, sid) {
  try {
    console.log('[Offscreen] Starting WAV recording with stream ID:', streamId);
    chunkCounter = 0;
    recordingBuffers = [];

    await connectWebSocket();

    audioStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        mandatory: {
          chromeMediaSource: 'tab',
          chromeMediaSourceId: streamId
        }
      }
    });

    console.log('[Offscreen] Audio stream obtained');

    audioContext = new AudioContext();
    sampleRate = audioContext.sampleRate;

    const source = audioContext.createMediaStreamSource(audioStream);

    source.connect(audioContext.destination);

    scriptProcessor = audioContext.createScriptProcessor(4096, 2, 2);

    scriptProcessor.onaudioprocess = async (e) => {
      const left = e.inputBuffer.getChannelData(0);
      const right = e.inputBuffer.getChannelData(1);

      recordingBuffers.push({
        left: new Float32Array(left),
        right: new Float32Array(right)
      });

      const samplesPerSecond = sampleRate;
      const currentSamples = recordingBuffers.reduce((sum, buf) => sum + buf.left.length, 0);

      if (currentSamples >= samplesPerSecond) {
        await sendBuffersAsChunk();
      }
    };

    source.connect(scriptProcessor);
    scriptProcessor.connect(audioContext.destination);

    console.log('[Offscreen] WAV recording started (1s chunks, WebSocket mode)');

  } catch (error) {
    console.error('[Offscreen] Error starting recording:', error);
    cleanup();
    throw error;
  }
}

async function connectWebSocket() {
  return new Promise((resolve, reject) => {
    console.log('[Offscreen] Connecting to WebSocket:', WS_URL);

    websocket = new WebSocket(WS_URL);

    websocket.onopen = () => {
      console.log('[Offscreen] ✅ WebSocket connected');
      resolve();
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[Offscreen] WebSocket message:', data);

        if (data.type === 'session_started') {
          sessionId = data.session_id;
          console.log('[Offscreen] Session ID:', sessionId);

          // Send metadata to server after session is started
          if (recordingMetadata) {
            console.log('[Offscreen] 📤 Sending metadata to server:', recordingMetadata);
            websocket.send(JSON.stringify({
              type: 'metadata',
              metadata: recordingMetadata
            }));
          } else {
            console.warn('[Offscreen] ⚠️ No metadata to send');
          }
        } else if (data.type === 'chunk_received') {
          console.log(`[Offscreen] ✅ Chunk ${data.chunk_number} confirmed by server`);
        } else if (data.type === 'error') {
          console.error('[Offscreen] Server error:', data.message);
        }
      } catch (e) {
        console.error('[Offscreen] Error parsing WebSocket message:', e);
      }
    };

    websocket.onerror = (error) => {
      console.error('[Offscreen] ❌ WebSocket error:', error);
      reject(error);
    };

    websocket.onclose = (event) => {
      console.log('[Offscreen] WebSocket closed:', event.code, event.reason);
    };

    // Таймаут на подключение
    setTimeout(() => {
      if (websocket.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket connection timeout'));
      }
    }, 5000);
  });
}

async function sendBuffersAsChunk() {
  if (recordingBuffers.length === 0) return;
  if (!websocket || websocket.readyState !== WebSocket.OPEN) {
    console.warn('[Offscreen] WebSocket not ready, skipping chunk');
    return;
  }

  chunkCounter++;
  console.log(`[Offscreen] Creating WAV chunk #${chunkCounter}...`);

  try {
    // Convert buffers to WAV
    const wavBlob = bufferToWav(recordingBuffers, sampleRate);
    console.log(`[Offscreen] Chunk #${chunkCounter} created, size: ${wavBlob.size} bytes`);

    // Clear buffers
    recordingBuffers = [];

    // Send to server via WebSocket
    await sendChunkViaWebSocket(wavBlob, chunkCounter);
    console.log(`[Offscreen] ✅ Chunk #${chunkCounter} sent via WebSocket`);

  } catch (error) {
    console.error(`[Offscreen] ❌ Failed to send chunk #${chunkCounter}:`, error);
    recordingBuffers = []; // Clear anyway to prevent memory leak
  }
}

function bufferToWav(buffers, sampleRate) {
  // Calculate total length
  const totalLength = buffers.reduce((sum, buf) => sum + buf.left.length, 0);

  // Interleave left and right channels
  const interleaved = new Float32Array(totalLength * 2);
  let offset = 0;

  for (const buffer of buffers) {
    for (let i = 0; i < buffer.left.length; i++) {
      interleaved[offset++] = buffer.left[i];
      interleaved[offset++] = buffer.right[i];
    }
  }

  // Convert float to 16-bit PCM
  const pcmData = new Int16Array(interleaved.length);
  for (let i = 0; i < interleaved.length; i++) {
    const s = Math.max(-1, Math.min(1, interleaved[i]));
    pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }

  // Create WAV file
  const wavBuffer = new ArrayBuffer(44 + pcmData.length * 2);
  const view = new DataView(wavBuffer);

  // WAV header
  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + pcmData.length * 2, true);
  writeString(view, 8, 'WAVE');
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true); // fmt chunk size
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 2, true); // 2 channels (stereo)
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 4, true); // byte rate
  view.setUint16(32, 4, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeString(view, 36, 'data');
  view.setUint32(40, pcmData.length * 2, true);

  // Write PCM data
  const pcmView = new Int16Array(wavBuffer, 44);
  pcmView.set(pcmData);

  return new Blob([wavBuffer], { type: 'audio/wav' });
}

function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

async function sendChunkViaWebSocket(chunkData, chunkNumber) {
  // Конвертируем Blob в ArrayBuffer
  const arrayBuffer = await chunkData.arrayBuffer();

  // Отправляем как JSON с base64 (для совместимости)
  // Можно также отправлять напрямую бинарные данные через websocket.send(arrayBuffer)
  const base64Data = arrayBufferToBase64(arrayBuffer);

  const message = {
    type: 'audio_chunk',
    chunk_number: chunkNumber,
    audio_data: base64Data
  };

  websocket.send(JSON.stringify(message));

  // Notify background script about new chunk
  try {
    await chrome.runtime.sendMessage({
      type: 'chunk-uploaded',
      chunkNumber: chunkNumber
    });
  } catch (error) {
    console.warn('[Offscreen] Could not notify background about chunk:', error);
  }
}

function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

async function stopRecording() {
  try {
    console.log('[Offscreen] Stopping recording...');

    // Send any remaining buffered audio
    if (recordingBuffers.length > 0) {
      console.log('[Offscreen] Sending final chunk with remaining buffers...');
      await sendBuffersAsChunk();
    }

    console.log(`[Offscreen] Recording stopped, total chunks sent: ${chunkCounter}`);

    // Close WebSocket gracefully
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.close(1000, 'Recording completed');
      console.log('[Offscreen] WebSocket closed');
    }

    cleanup();
  } catch (error) {
    console.error('[Offscreen] Error stopping recording:', error);
    cleanup();
    throw error;
  }
}

function cleanup() {
  if (scriptProcessor) {
    scriptProcessor.disconnect();
    scriptProcessor = null;
  }

  if (audioStream) {
    audioStream.getTracks().forEach(track => track.stop());
    audioStream = null;
  }

  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }

  if (websocket) {
    if (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING) {
      websocket.close();
    }
    websocket = null;
  }

  sessionId = null;
  chunkCounter = 0;
  recordingBuffers = [];
}
