let miniEquityChart;

document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelectorAll('.chart-tab');
  const panels = document.querySelectorAll('.chart-panel');

  function activate(tab) {
    tabs.forEach(btn => {
      btn.classList.remove('bg-blade-amber/20', 'text-blade-amber');
      btn.classList.add('bg-void-black/50', 'text-blade-amber/60');
      btn.setAttribute('aria-selected', 'false');
    });
    tab.classList.add('bg-blade-amber/20', 'text-blade-amber');
    tab.classList.remove('bg-void-black/50', 'text-blade-amber/60');
    tab.setAttribute('aria-selected', 'true');
    panels.forEach(p => (p.hidden = true));
    const target = document.getElementById(`${tab.dataset.chart}Chart`);
    if (target) target.hidden = false;
    switch (tab.dataset.chart) {
      case 'equity':
        loadEquityCurve();
        break;
      case 'pnl':
        loadPnLBreakdown();
        break;
      case 'market':
        loadMarketData();
        break;
      case 'regime':
        loadRegimeAnalysis();
        break;
    }
  }

  tabs.forEach(btn => btn.addEventListener('click', () => activate(btn)));
  loadMiniEquity();
  loadPerformanceMatrix();
  pollRpcLatency();
  setInterval(pollRpcLatency, 5000);
  const p7 = document.getElementById('perf7d');
  const p30 = document.getElementById('perf30d');
  if (p7 && p30) {
    p7.addEventListener('click', () => { strategyMatrixPeriod = '7d'; p7.classList.add('bg-blade-amber/20','text-blade-amber'); p30.classList.remove('bg-blade-amber/20','text-blade-amber'); p30.classList.add('bg-void-black/50','text-blade-amber/60'); loadPerformanceMatrix(); });
    p30.addEventListener('click', () => { strategyMatrixPeriod = '30d'; p30.classList.add('bg-blade-amber/20','text-blade-amber'); p7.classList.remove('bg-blade-amber/20','text-blade-amber'); p7.classList.add('bg-void-black/50','text-blade-amber/60'); loadPerformanceMatrix(); });
  }
  initBacktestLab();
});

async function loadMiniEquity() {
  try {
    const ctx = document.getElementById('sparkline')?.getContext('2d');
    if (!ctx || !window.Chart) return;
    const data = await fetch(`${API_BASE}/chart/portfolio?limit=48`).then(r => r.json());
    const series = data.series || [];
    const labels = [];
    const values = [];
    for (let i = 0; i < series.length; i++) {
      labels.push(i);
      values.push(series[i][1]);
    }
    if (miniEquityChart) miniEquityChart.destroy();
    miniEquityChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{ data: values, borderColor: '#ff8c00', borderWidth: 1, fill: false, tension: 0.1, pointRadius: 0 }],
      },
      options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } },
    });
  } catch (e) {
    console.warn('mini equity load failed', e);
  }
}
setInterval(loadMiniEquity, 30000);

const root = typeof window !== 'undefined' ? window : globalThis;
root.loadMiniEquity = loadMiniEquity;
root.loadPerformanceMatrix = loadPerformanceMatrix;

let strategyMatrixPeriod = '7d';

async function loadPerformanceMatrix() {
  try {
    const data = await fetch(`${API_BASE}/strategy/performance_matrix?period=${strategyMatrixPeriod}`).then(r => r.json());
    const grid = document.getElementById('perfMatrixGrid');
    if (grid) {
      grid.innerHTML = '';
      data.days.forEach(v => {
        const cell = document.createElement('div');
        const color = v >= 0 ? 'bg-cyan-glow/70' : 'bg-blade-orange/60';
        cell.className = `w-8 h-8 ${color} rounded`;
        cell.title = `${v.toFixed(2)} SOL`;
        grid.appendChild(cell);
      });
    }
    const stratBox = document.getElementById('perfStrategyBreakdown');
    if (stratBox) {
      stratBox.innerHTML = '';
      data.strategies.forEach(s => {
        const box = document.createElement('div');
        box.className = 'bg-void-black/50 p-3 rounded border border-blade-cyan/30';
        box.innerHTML = `<div class="hologram-text text-cyan-glow font-bold text-sm">${s.name}</div>`+
          `<div class="hologram-text text-white text-lg">${formatSol(s.pnl, solPrice)}</div>`+
          `<div class="hologram-text text-cyan-glow text-xs">${formatPercent(s.win_rate)}</div>`;
        stratBox.appendChild(box);
      });
    }
    const sharpe = document.getElementById('perfSharpe');
    const draw = document.getElementById('perfDrawdown');
    const vol = document.getElementById('perfVol');
    const calmar = document.getElementById('perfCalmar');
    if (sharpe) sharpe.textContent = data.risk.sharpe.toFixed(2);
    if (draw) draw.textContent = formatPercent(-data.risk.max_drawdown);
    if (vol) vol.textContent = formatPercent(data.risk.volatility);
    if (calmar) calmar.textContent = data.risk.calmar.toFixed(2);
  } catch (e) {
    console.warn('perf matrix load failed', e);
  }
}
setInterval(loadPerformanceMatrix, 60000);

function initBacktestLab() {
  const btn = document.getElementById('runLab');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const start = document.getElementById('labStart').value;
    const end = document.getElementById('labEnd').value;
    const sniper = parseFloat(document.getElementById('labSniper').value) || 0;
    const arb = parseFloat(document.getElementById('labArb').value) || 0;
    const mm = parseFloat(document.getElementById('labMM').value) || 0;
    const params = { period: `${start}:${end}`, capital: 100, strategy_mix: `sniper:${sniper},arb:${arb},mm:${mm}` };
    try {
      const res = await apiClient.runBacktest(params);
      const ws = new WebSocket(apiClient.getWebSocketURL(`/backtest/ws/${res.id}`));
      ws.onmessage = ev => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.pnl !== undefined) {
            document.getElementById('labFinal').textContent = formatSol(msg.pnl, solPrice);
            document.getElementById('labReturn').textContent = formatPercent(msg.pnl / params.capital);
            document.getElementById('labTrades').textContent = msg.trades ?? '-';
            document.getElementById('labWin').textContent = formatPercent(msg.win_rate ?? 0);
            document.getElementById('labAvg').textContent = formatSol(msg.avg_trade ?? 0, solPrice);
          }
        } catch {}
      };
      ws.onclose = () => {};
    } catch (e) {
      console.error('backtest lab failed', e);
    }
  });
}

async function loadEquityCurve() {
  try {
    const data = await fetch(`${API_BASE}/chart/portfolio?limit=50`).then(r => r.json());
    const series = data.series || [];
    const ctx = document.getElementById('equityCanvas')?.getContext('2d');
    if (!ctx || !window.Chart) return;
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: series.map(p => new Date(p[0] * 1000).toLocaleTimeString()),
        datasets: [{ data: series.map(p => p[1]), borderColor: '#00e5ff', fill: false }],
      },
      options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } },
    });
  } catch (e) {
    console.warn('equity curve load failed', e);
  }
}

async function loadPnLBreakdown() {
  try {
    const daily = await fetch(`${API_BASE}/pnl/daily?days=14`).then(r => r.json());
    const barCtx = document.getElementById('pnlBarChart')?.getContext('2d');
    if (barCtx && window.Chart) {
      const labels = daily.map(d => d.date);
      const values = daily.map(d => d.pnl);
      new Chart(barCtx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{ data: values, backgroundColor: values.map(v => (v >= 0 ? '#00e5ff' : '#ff6b35')) }],
        },
        options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } },
      });
    }
    const strat = await fetch(`${API_BASE}/strategy/breakdown`).then(r => r.json());
    const donutCtx = document.getElementById('strategyDonutChart')?.getContext('2d');
    if (donutCtx && window.Chart) {
      const labels = strat.map(s => s.name);
      const values = strat.map(s => s.pnl);
      const colors = ['#00e5ff', '#ff6b35', '#ffab00', '#2ecc71', '#9b59b6'];
      new Chart(donutCtx, {
        type: 'doughnut',
        data: { labels, datasets: [{ data: values, backgroundColor: colors.slice(0, labels.length) }] },
        options: { plugins: { legend: { position: 'bottom' } }, cutout: '60%' },
      });
    }
  } catch (e) {
    console.warn('pnl load failed', e);
  }
}

async function loadMarketData() {
  try {
    const tbody = document.querySelector('#marketDataTable tbody');
    if (!tbody) return;
    const markets = await fetch(`${API_BASE}/market/active`).then(r => r.json());
    tbody.innerHTML = '';
    markets.forEach(m => {
      const tr = document.createElement('tr');
      tr.className = 'cursor-pointer hover:bg-void-black/30';
      tr.innerHTML = `<td class="px-2 py-1">${m.symbol}</td>` +
        `<td class="px-2 py-1">${m.volume.toLocaleString()}</td>` +
        `<td class="px-2 py-1">${formatPercent(m.volatility * 100)}</td>` +
        `<td class="px-2 py-1">${m.liquidity.toLocaleString()}</td>` +
        `<td class="px-2 py-1">${formatPercent(m.spread * 100)}</td>`;
      tr.addEventListener('click', () => {
        const sym = m.symbol.replace('/', '');
        window.open(`https://www.tradingview.com/chart/?symbol=${sym}`, '_blank');
      });
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.warn('market data load failed', e);
  }
}

setInterval(loadMarketData, 10000);

async function loadRegimeAnalysis(retries = 5, delay = 1000) {
  const canvas = document.getElementById('regimeCanvas');
  if (!canvas || !window.Chart) return;
  const ctx = canvas.getContext('2d');
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'Trend', borderColor: '#00e5ff', data: [], fill: false },
        { label: 'Revert', borderColor: '#ff8c00', data: [], fill: false },
        { label: 'Chop', borderColor: '#ffab00', data: [], fill: false },
        { label: 'Rug', borderColor: '#ff6b35', data: [], fill: false },
      ],
    },
    options: { animation: false, scales: { x: { display: false }, y: { min: 0, max: 1 } } },
  });
  function connect(attempt) {
    try {
      const ws = new WebSocket(apiClient.getWebSocketURL('/posterior/ws'));
      ws.onopen = () => {
        const panel = document.getElementById('regimeChart');
        if (panel) panel.hidden = false;
      };
      ws.onmessage = evt => {
        try {
          const msg = JSON.parse(evt.data);
          const t = new Date().toLocaleTimeString();
          chart.data.labels.push(t);
          chart.data.datasets[0].data.push(msg.trend);
          chart.data.datasets[1].data.push(msg.revert);
          chart.data.datasets[2].data.push(msg.chop);
          chart.data.datasets[3].data.push(msg.rug);
          chart.update();
        } catch (err) {
          console.error('posterior ws parse failed', err);
        }
      };
      const handleClose = () => {
        const panel = document.getElementById('regimeChart');
        if (attempt < retries) {
          const wait = delay * Math.pow(2, attempt);
          console.warn(`posterior ws retry ${attempt + 1}`);
          setTimeout(() => connect(attempt + 1), wait);
        } else if (panel) {
          panel.hidden = true;
          const msg = document.createElement('div');
          msg.className = 'hologram-text text-blade-amber/60';
          msg.textContent = 'Regime feed unavailable';
          panel.parentNode?.insertBefore(msg, panel);
        }
      };
      ws.onerror = handleClose;
      ws.onclose = handleClose;
    } catch (e) {
      console.warn('regime analysis load failed', e);
      const panel = document.getElementById('regimeChart');
      if (panel) panel.hidden = true;
    }
  }
  connect(0);
}

async function pollMevAlpha() {
  const panel = document.getElementById('mevAlphaPanel');
  if (!panel) return;
  try {
    const [mevRes, alphaRes, priceRes] = await Promise.all([
      fetch(`${API_BASE}/mev/status`),
      fetch(`${API_BASE}/alpha/signals`),
      fetch(`${API_BASE}/price/sol`),
    ]);
    if (mevRes.status === 503 || alphaRes.status === 503) {
      panel.classList.add('hidden');
      return;
    }
    const [mev, alpha, priceData] = await Promise.all([
      mevRes.json(),
      alphaRes.json(),
      priceRes.json(),
    ]);
    const price = priceData.price ?? priceData;
    const savedEl = document.getElementById('mevSaved');
    if (savedEl) savedEl.textContent = formatSol(mev.saved_today, price);
    const blockedEl = document.getElementById('mevBlocked');
    if (blockedEl) blockedEl.textContent = mev.attacks_blocked;
    const successEl = document.getElementById('mevSuccess');
    if (successEl) successEl.textContent = formatPercent(mev.success_rate);
    const latencyEl = document.getElementById('mevLatency');
    if (latencyEl) latencyEl.textContent = `${mev.latency_ms}ms`;
    const strengthEl = document.getElementById('alphaStrength');
    if (strengthEl) strengthEl.textContent = alpha.strength;
    const sentEl = document.getElementById('alphaSentiment');
    if (sentEl) sentEl.textContent = `${alpha.social_sentiment.toFixed(1)}/10`;
    const momEl = document.getElementById('alphaMomentum');
    if (momEl) momEl.textContent = `${alpha.onchain_momentum.toFixed(1)}/10`;
    const whaleEl = document.getElementById('alphaWhales');
    if (whaleEl) whaleEl.textContent = `${alpha.whale_activity.toFixed(1)}/10`;
    panel.classList.remove('hidden');
  } catch (e) {
    console.warn('mev/alpha load failed', e);
    panel.classList.add('hidden');
  }
}

document.addEventListener('DOMContentLoaded', pollMevAlpha);
setInterval(pollMevAlpha, 15000);

const latencySamples = [];
async function pollRpcLatency() {
  try {
    const res = await fetch(`${API_BASE}/health`).then(r => r.json());
    const latency = res.rpc_latency_ms;
    if (typeof latency === 'number') {
      latencySamples.push(latency);
      if (latencySamples.length > 5) latencySamples.shift();
      const avg = latencySamples.reduce((a, b) => a + b, 0) / latencySamples.length;
      const el = document.getElementById('rpcLatency');
      if (el) {
        el.textContent = `${avg.toFixed(0)}ms`;
        el.classList.add('text-blade-amber');
        setTimeout(() => el.classList.remove('text-blade-amber'), 500);
      }
      try {
        localStorage.setItem('metricRpcLatency', String(avg));
        const metric = document.getElementById('metricRpc');
        if (metric) metric.textContent = `${avg.toFixed(0)}ms`;
      } catch {}
    }
  } catch (e) {
    console.error('rpc latency poll failed', e);
    const el = document.getElementById('rpcLatency');
    if (el) el.textContent = '--';
  }
}
