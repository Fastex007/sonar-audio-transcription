const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const viewRecordingsBtn = document.getElementById('viewRecordingsBtn');
const statusDiv = document.getElementById('status');
const sessionInfoDiv = document.getElementById('sessionInfo');
const sessionIdSpan = document.getElementById('sessionId');
const recordingTimeSpan = document.getElementById('recordingTime');
const chunksCountSpan = document.getElementById('chunksCount');

let recordingStartTime = null;
let statsInterval = null;

async function updateStatus() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getStatus' });

    const [currentTab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (response.isRecording) {
      const isCurrentTab = currentTab && currentTab.id === response.recordingTabId;

      if (isCurrentTab) {
        statusDiv.textContent = '🔴 Идёт запись этой вкладки...';
      } else {
        statusDiv.textContent = '🔴 Идёт запись другой вкладки...';
      }

      statusDiv.className = 'status recording';
      startBtn.disabled = true;
      stopBtn.disabled = false;  // Allow stopping from any tab

      if (response.sessionId) {
        sessionIdSpan.textContent = response.sessionId.substring(0, 8) + '...';
        sessionInfoDiv.style.display = 'block';

        // Start recording time if not already started
        if (!recordingStartTime && response.startedAt) {
          recordingStartTime = response.startedAt;
          startStatsUpdate();
        }

        // Update stats
        updateRecordingStats(response);
      }
    } else {
      statusDiv.textContent = 'Готов к записи';
      statusDiv.className = 'status idle';
      startBtn.disabled = false;
      stopBtn.disabled = true;
      sessionInfoDiv.style.display = 'none';

      if (statsInterval) {
        clearInterval(statsInterval);
        statsInterval = null;
      }
      recordingStartTime = null;
    }
  } catch (error) {
    console.error('Error updating status:', error);
  }
}

function updateRecordingStats(response) {
  if (response.chunksCount !== undefined) {
    chunksCountSpan.textContent = response.chunksCount;
  }

  if (recordingStartTime) {
    const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    recordingTimeSpan.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
}

function startStatsUpdate() {
  if (statsInterval) {
    clearInterval(statsInterval);
  }

  statsInterval = setInterval(async () => {
    try {
      const response = await chrome.runtime.sendMessage({ action: 'getStatus' });
      if (response.isRecording) {
        updateRecordingStats(response);
      }
    } catch (error) {
      console.error('Error updating stats:', error);
    }
  }, 500); // Update every 500ms for smooth time display
}

// Start recording
startBtn.addEventListener('click', async () => {
  try {
    // Get current tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab) {
      alert('Активная вкладка не найдена');
      return;
    }

    // Check if tab has audio
    if (!tab.audible && !confirm('Эта вкладка может не воспроизводить аудио. Продолжить?')) {
      return;
    }

    statusDiv.textContent = 'Запуск записи...';
    startBtn.disabled = true;

    const response = await chrome.runtime.sendMessage({
      action: 'startRecording',
      tabId: tab.id
    });

    if (response.success) {
      console.log('Recording started:', response.sessionId);
      recordingStartTime = Date.now();
      await updateStatus();
    } else {
      alert('Не удалось начать запись: ' + response.error);
      startBtn.disabled = false;
      statusDiv.textContent = 'Ошибка: ' + response.error;
      statusDiv.className = 'status idle';
    }
  } catch (error) {
    console.error('Error starting recording:', error);
    alert('Ошибка: ' + error.message);
    startBtn.disabled = false;
    statusDiv.textContent = 'Ошибка';
    statusDiv.className = 'status idle';
  }
});

stopBtn.addEventListener('click', async () => {
  try {
    statusDiv.textContent = 'Остановка записи...';
    stopBtn.disabled = true;

    const response = await chrome.runtime.sendMessage({ action: 'stopRecording' });

    if (response.success) {
      console.log('Recording stopped');
      if (statsInterval) {
        clearInterval(statsInterval);
        statsInterval = null;
      }
      recordingStartTime = null;
      await updateStatus();
    } else {
      alert('Не удалось остановить запись: ' + response.error);
      await updateStatus();
    }
  } catch (error) {
    console.error('Error stopping recording:', error);
    alert('Ошибка: ' + error.message);
    await updateStatus();
  }
});

viewRecordingsBtn.addEventListener('click', () => {
  chrome.tabs.create({
    url: 'http://localhost:8000/'
  });
});

updateStatus();
setInterval(updateStatus, 2000);
