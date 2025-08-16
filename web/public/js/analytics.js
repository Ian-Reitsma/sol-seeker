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
});

async function loadMiniEquity() {
  try {
    const ctx = document.getElementById('portfolioSpark')?.getContext('2d');
    if (!ctx || !window.Chart) return;
    const data = await fetch(`${API_BASE}/chart/portfolio?limit=48`).then(r => r.json());
    const series = data.series || [];
    if (miniEquityChart) miniEquityChart.destroy();
    miniEquityChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: series.map((p, i) => i),
        datasets: [{ data: series.map(p => p[1]), borderColor: '#ff8c00', borderWidth: 1, fill: false, tension: 0.1, pointRadius: 0 }],
      },
      options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } },
    });
  } catch (e) {
    console.warn('mini equity load failed', e);
  }
}
setInterval(loadMiniEquity, 30000);

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
      tr.innerHTML = `<td class="px-2 py-1 cursor-pointer">${m.symbol}</td>` +
        `<td class="px-2 py-1">${m.volume}</td>` +
        `<td class="px-2 py-1">${m.volatility}</td>` +
        `<td class="px-2 py-1">${m.liquidity}</td>` +
        `<td class="px-2 py-1">${m.spread}</td>`;
      tr.addEventListener('click', () => window.open(`${API_BASE}/chart/${m.symbol}`, '_blank'));
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
      ws.onerror = () => {
        ws.close();
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
    } catch (e) {
      console.warn('regime analysis load failed', e);
      const panel = document.getElementById('regimeChart');
      if (panel) panel.hidden = true;
    }
  }
  connect(0);
}
