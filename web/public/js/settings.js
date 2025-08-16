const { protocol, hostname, port } = window.location;
let apiBase = localStorage.getItem('sol_seeker_api_base');
if (!apiBase) {
    apiBase = port === '5173'
        ? `${protocol}//${hostname}:8000`
        : `${protocol}//${hostname}${port ? ':' + port : ''}`;
    localStorage.setItem('sol_seeker_api_base', apiBase);
}
const API_BASE = apiBase;
let apiKey = localStorage.getItem('sol_seeker_api_key') || '';

const fields = {
    theme: document.getElementById('theme'),
    timeZone: document.getElementById('timeZone'),
    tradingMode: document.getElementById('tradingMode'),
    startingCapital: document.getElementById('startingCapital'),
    rpcEndpoint: document.getElementById('rpcEndpoint'),
    apiKey: document.getElementById('apiKey'),
    advancedToggle: document.getElementById('advancedToggle'),
    enableSniper: document.getElementById('enableSniper'),
    enableArbitrage: document.getElementById('enableArbitrage'),
    enableMarketMaking: document.getElementById('enableMarketMaking'),
    disableAnimation: document.getElementById('disableAnimation'),
    primaryAsset: document.getElementById('primaryAsset'),
};

if (fields.timeZone) {
    try {
        Intl.supportedValuesOf('timeZone').forEach(tz => {
            const opt = document.createElement('option');
            opt.value = tz;
            opt.textContent = tz;
            fields.timeZone.appendChild(opt);
        });
    } catch {}
}

function updateAdvancedVisibility() {
    const show = fields.advancedToggle.checked;
    document.querySelectorAll('.advanced').forEach(el => {
        el.classList.toggle('hidden', !show);
    });
}

function persist(key, value) {
    localStorage.setItem(`setting_${key}`, typeof value === 'boolean' ? String(value) : value);
    const headers = { 'Content-Type': 'application/json' };
    if (apiKey) headers['X-API-Key'] = apiKey;
    fetch(`${API_BASE}/state`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ [key]: value })
    }).catch(() => {});
}

function loadSettings() {
    for (const [key, el] of Object.entries(fields)) {
        const stored = localStorage.getItem(`setting_${key}`);
        if (stored !== null) {
            if (el.type === 'checkbox') {
                el.checked = stored === 'true';
            } else {
                el.value = stored;
            }
        } else if (key === 'timeZone') {
            el.value = Intl.DateTimeFormat().resolvedOptions().timeZone;
        } else if (key === 'primaryAsset') {
            el.value = 'SOL';
        } else if (key === 'theme') {
            el.value = 'seeker';
        }
    }
    updateAdvancedVisibility();
    updateCurrentTime();
    if (fields.disableAnimation && fields.disableAnimation.checked) {
        document.documentElement.classList.add('no-anim');
    }
    if (fields.theme) setTheme(fields.theme.value);
    if (fields.advancedToggle && !fields.advancedToggle.checked && localStorage.getItem('basic_walkthrough_done') !== 'true') {
        localStorage.setItem('basic_walkthrough_pending', 'true');
    }
}

function updateCurrentTime() {
    const tz = fields.timeZone.value || 'UTC';
    const now = new Date().toLocaleTimeString('en-US', { timeZone: tz });
    const el = document.getElementById('currentTime');
    if (el) el.textContent = now;
}

for (const [key, el] of Object.entries(fields)) {
    el.addEventListener('change', () => {
        const value = el.type === 'checkbox' ? el.checked : el.value;
        if (key === 'apiKey') {
            apiKey = value;
            localStorage.setItem('sol_seeker_api_key', value);
        }
        if (key === 'rpcEndpoint') {
            localStorage.setItem('sol_seeker_api_base', value);
        }
        persist(key, value);
        if (key === 'advancedToggle') {
            updateAdvancedVisibility();
            if (!el.checked && localStorage.getItem('basic_walkthrough_done') !== 'true') {
                localStorage.setItem('basic_walkthrough_pending', 'true');
                alert('Basic mode enabled. A quick walkthrough will start on the dashboard.');
            }
        }
        if (key === 'theme') setTheme(value);
        if (key === 'disableAnimation') document.documentElement.classList.toggle('no-anim', el.checked || fields.theme.value !== 'seeker');
        if (key === 'timeZone') updateCurrentTime();
    });
}

async function loadMetrics() {
    try {
        const m = await fetch(`${API_BASE}/metrics`).then(r => r.json());
        if (m.cpu !== undefined) document.getElementById('metricCpu').textContent = `${m.cpu.toFixed(1)}%`;
        if (m.memory !== undefined) document.getElementById('metricMem').textContent = `${m.memory.toFixed(1)}%`;
    } catch {}
    try {
        const h = await fetch(`${API_BASE}/health`).then(r => r.json());
        if (h && typeof h.rpc_latency_ms !== 'undefined') {
            document.getElementById('metricRpc').textContent = `${h.rpc_latency_ms}ms`;
        }
    } catch {}
}

loadSettings();
loadMetrics();
setInterval(updateCurrentTime, 1000);
setInterval(loadMetrics, 5000);
