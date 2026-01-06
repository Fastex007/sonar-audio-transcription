const API_BASE_URL = 'http://localhost:8000/api';

let sessionId = null;
let isRecording = false;
let recordingTabId = null;
let offscreenDocumentCreated = false;
let startedAt = null;
let chunksCount = 0;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'startRecording') {
    startRecording(message.tabId)
      .then(() => sendResponse({ success: true, sessionId }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true; // Keep channel open for async response
  }

  if (message.action === 'stopRecording') {
    stopRecording()
      .then(() => sendResponse({ success: true }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }

  if (message.action === 'getStatus') {
    sendResponse({
      isRecording,
      sessionId,
      recordingTabId,
      startedAt,
      chunksCount,
      status: isRecording ? 'recording' : 'idle'
    });
    return true;
  }

  if (message.type === 'chunk-uploaded') {
    chunksCount++;
    console.log(`[Background] Chunk uploaded, total: ${chunksCount}`);
    sendResponse({ success: true, chunksCount });
    return true;
  }
});

async function setupOffscreenDocument() {
  if (offscreenDocumentCreated) {
    return;
  }

  try {
    await chrome.offscreen.createDocument({
      url: 'offscreen.html',
      reasons: ['USER_MEDIA'],
      justification: 'Recording audio from tab'
    });
    offscreenDocumentCreated = true;
    console.log('[Background] Offscreen document created');
  } catch (error) {
    if (error.message.includes('Only a single offscreen')) {
      offscreenDocumentCreated = true;
      console.log('[Background] Offscreen document already exists');
    } else {
      throw error;
    }
  }
}

async function startRecording(tabId) {
  try {
    console.log('[Background] Starting recording for tab:', tabId);

    chunksCount = 0;
    startedAt = Date.now();

    await setupOffscreenDocument();

    const tab = await chrome.tabs.get(tabId);
    console.log('[Background] Tab info:', {
      url: tab.url,
      title: tab.title,
      favIconUrl: tab.favIconUrl
    });

    const browserInfo = {
      userAgent: navigator.userAgent,
      platform: navigator.platform,
      language: navigator.language,
      vendor: navigator.vendor
    };
    console.log('[Background] Browser info:', browserInfo);

    const metadata = {
      tab_url: tab.url,
      tab_title: tab.title,
      tab_favicon: tab.favIconUrl,
      user_agent: navigator.userAgent,
      browser_info: browserInfo
    };

    const streamId = await new Promise((resolve, reject) => {
      chrome.tabCapture.getMediaStreamId({ targetTabId: tabId }, (id) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(id);
        }
      });
    });

    console.log('[Background] Got stream ID:', streamId);

    const response = await chrome.runtime.sendMessage({
      type: 'start-recording',
      streamId: streamId,
      metadata: metadata
    });

    if (!response.success) {
      throw new Error(response.error);
    }

    isRecording = true;
    recordingTabId = tabId;
    console.log('[Background] Recording started successfully on tab:', tabId);

  } catch (error) {
    console.error('[Background] Error starting recording:', error);
    sessionId = null;
    isRecording = false;
    recordingTabId = null;
    startedAt = null;
    chunksCount = 0;
    throw error;
  }
}

async function stopRecording() {
  try{
    console.log('[Background] Stopping recording...');

    if (offscreenDocumentCreated) {
      await chrome.runtime.sendMessage({
        type: 'stop-recording'
      });
    }

    console.log(`[Background] Recording stopped. Total chunks: ${chunksCount}`);

    sessionId = null;
    isRecording = false;
    recordingTabId = null;
    startedAt = null;
    chunksCount = 0;

  } catch (error) {
    console.error('[Background] Error stopping recording:', error);
    sessionId = null;
    isRecording = false;
    recordingTabId = null;
    startedAt = null;
    chunksCount = 0;
    throw error;
  }
}

chrome.runtime.onSuspend.addListener(() => {
  if (isRecording) {
    stopRecording();
  }
});
