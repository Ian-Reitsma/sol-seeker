document.addEventListener('DOMContentLoaded', () => {
  const consoleEl = document.getElementById('debugConsole');
  const generateBtn = document.getElementById('generateLogs');
  const clearBtn = document.getElementById('clearLogs');
  const filterButtons = document.querySelectorAll('.log-filter');
  const buffer = [];
  const MAX = 500;
  let level = 'ALL';

  function render() {
    if (!consoleEl) return;
    consoleEl.innerHTML = '';
    for (const entry of buffer) {
      if (level !== 'ALL' && entry.level !== level) continue;
      const div = document.createElement('div');
      div.textContent = `[${new Date(entry.timestamp).toLocaleTimeString()}] ${entry.level}: ${entry.message}`;
      consoleEl.appendChild(div);
    }
    consoleEl.scrollTop = consoleEl.scrollHeight;
  }

  function onLog(entry) {
    buffer.push(entry);
    if (buffer.length > MAX) buffer.shift();
    render();
  }

  if (generateBtn) {
    generateBtn.addEventListener('click', () => {
      fetch(`${API_BASE}/logs/generate`, { method: 'POST' }).catch(() => {});
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      buffer.length = 0;
      render();
    });
  }

  filterButtons.forEach(btn => btn.addEventListener('click', () => {
    level = btn.dataset.level;
    render();
  }));

  try {
    const ws = new WebSocket(apiClient.getWebSocketURL('/logs/ws'));
    ws.onmessage = ev => {
      try {
        const msg = JSON.parse(ev.data);
        onLog(msg);
      } catch {}
    };
  } catch (e) {
    console.warn('log ws failed', e);
  }
});
