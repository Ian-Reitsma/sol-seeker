document.addEventListener('DOMContentLoaded', () => {
  function renderPositionsMap() {
    const canvas = document.getElementById('positionsMap');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let positions = [];

    function draw() {
      const barWidth = 20;
      const height = canvas.height;
      canvas.width = positions.length * (barWidth + 4);
      ctx.clearRect(0, 0, canvas.width, height);
      positions.forEach((p, idx) => {
        const x = idx * (barWidth + 4);
        ctx.fillStyle = p.qty >= 0 ? '#00e5ff' : '#ff6b35';
        ctx.fillRect(x, 0, barWidth, height);
      });
    }

    try {
      const ws = new WebSocket(apiClient.getWebSocketURL('/positions/ws'));
      ws.addEventListener('open', () => {
        setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, 5000);
      });
      ws.onmessage = evt => {
        try {
          const data = JSON.parse(evt.data);
          positions = Array.isArray(data) ? data : Object.values(data);
          draw();
        } catch (err) {
          console.error('positions ws parse failed', err);
        }
      };
    } catch (err) {
      console.error('positions ws failed', err);
    }
  }

  async function loadPositions() {
    try {
      const list = document.getElementById('positionsList');
      if (!list) return;
      const data = await fetch(`${API_BASE}/positions`).then(r => r.json());
      list.innerHTML = '';
      Object.entries(data).forEach(([token, p]) => {
        const div = document.createElement('div');
        div.className = 'flex items-center justify-between hologram-text text-sm';
        const qty = p.qty || 0;
        div.innerHTML = `<span>${token}</span><span>${qty.toFixed(2)}</span>`;
        list.appendChild(div);
      });
    } catch (e) {
      console.error('positions load failed', e);
    }
  }

  function renderHistoryEntry(order) {
    const pnl = order.pnl ?? 0;
    const entry = document.createElement('div');
    entry.className = 'bg-void-black/50 p-4 rounded border';
    entry.classList.add(pnl >= 0 ? 'border-blade-cyan/30' : 'border-blade-orange/30');
    const color = pnl >= 0 ? 'text-cyan-glow' : 'text-blade-orange';
    const time = order.timestamp ? new Date(order.timestamp * 1000).toLocaleTimeString() : '';
    entry.innerHTML = `
        <div class="flex items-center justify-between mb-2">
            <div>
                <div class="hologram-text text-white font-bold">${order.token || ''} ${order.status ? order.status.toUpperCase() : ''}</div>
                <div class="hologram-text text-xs text-blade-amber/60">${time} • ${order.strategy || ''}</div>
            </div>
            <div class="text-right">
                <div class="hologram-text ${color} font-bold">${pnl >= 0 ? '+' : ''}${pnl} SOL</div>
            </div>
        </div>`;
    return entry;
  }

  function appendHistoryEntry(order) {
    const list = document.getElementById('historyList');
    if (!list) return;
    const entry = renderHistoryEntry(order);
    list.insertBefore(entry, list.firstChild);
  }

  async function loadHistory() {
    try {
      const orders = await fetch(`${API_BASE}/orders?limit=50`).then(r => r.json());
      const list = document.getElementById('historyList');
      if (!Array.isArray(orders) || !list) return;
      list.innerHTML = '';
      orders.forEach(o => appendHistoryEntry(o));
    } catch (err) {
      console.error('history load failed', err);
    }
  }

  async function pollRisk() {
    try {
      const data = await fetch(`${API_BASE}/risk/portfolio`).then(r => r.json());
      const dd = document.getElementById('riskMaxDrawdown');
      if (dd) dd.textContent = formatPercent(-data.max_drawdown * 100);
      const lev = document.getElementById('leverageRatio');
      if (lev) lev.textContent = `${data.leverage.toFixed(2)}x`;
      const ex = document.getElementById('exposure');
      if (ex) ex.textContent = formatPercent(data.exposure * 100);
    } catch (e) {
      console.warn('risk poll failed', e);
    }
  }

  async function loadStrategyMatrix() {
    try {
      const data = await fetch(`${API_BASE}/strategy/matrix`).then(r => r.json());
      if (typeof updateStrategyMatrix === 'function') {
        updateStrategyMatrix(data);
      }
    } catch (e) {
      if (typeof updateStrategyMatrix === 'function') {
        updateStrategyMatrix(null);
      }
    }
  }

  window.loadPositions = loadPositions;
  window.loadHistory = loadHistory;
  window.appendHistoryEntry = appendHistoryEntry;

  loadPositions().then(pollRisk);
  loadStrategyMatrix();
  renderPositionsMap();
  setInterval(pollRisk, 5000);
  setInterval(loadStrategyMatrix, 10000);
});
