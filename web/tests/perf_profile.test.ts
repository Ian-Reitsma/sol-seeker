/**
 * @jest-environment jsdom
 */
import { performance } from 'perf_hooks';
import { jest } from '@jest/globals';

// minimal DOM diffing routine copied from dashboard for profiling
const positionRows = new Map<string, HTMLElement>();
function updatePositionsDisplay(map: Record<string, any>): void {
  const entries = Object.entries(map);
  const list = document.getElementById('positionsList');
  if (!list) return;
  const fragment = document.createDocumentFragment();
  const seen = new Set<string>();
  entries.forEach(([token, p]) => {
    let row = positionRows.get(token);
    if (!row) {
      row = document.createElement('div');
      row.className = 'position-row';
      positionRows.set(token, row);
    }
    const pnl = p.unrealized ?? p.pnl ?? 0;
    const color = pnl >= 0 ? 'text-cyan-glow' : 'text-blade-orange';
    row.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="token-icon">${token[0] || '?'}</div>
          <div>
            <div class="hologram-text text-white font-bold">$${token}</div>
            <div class="hologram-text text-xs text-blade-amber/60">${p.quantity ?? p.qty ?? 0}</div>
          </div>
        </div>
        <div class="text-right">
          <div class="hologram-text ${color} font-bold">${pnl >= 0 ? '+' : ''}${pnl}</div>
        </div>
      </div>`;
    fragment.appendChild(row);
    seen.add(token);
  });
  for (const [token, row] of Array.from(positionRows.entries())) {
    if (!seen.has(token)) {
      row.remove();
      positionRows.delete(token);
    }
  }
  list.appendChild(fragment);
}

// simple websocket client mirroring dashboard reconnection logic
let showToast: (msg: string) => void;
class SolSeekerWebSocket {
  connections = new Map<string, any>();
  reconnectAttempts = new Map<string, number>();
  maxReconnectAttempts = 5;
  connect(endpoint: string, onMessage: (d: any) => void, onError: ((e: any) => void) | null = null): void {
    try {
      const ws: any = new WebSocket(endpoint);
      ws.onopen = () => {
        this.reconnectAttempts.set(endpoint, 0);
      };
      ws.onmessage = (ev: any) => {
        try {
          onMessage(JSON.parse(ev.data));
        } catch {
          // ignore parse errors
        }
      };
      ws.onclose = () => {
        this.handleReconnect(endpoint, onMessage, onError);
      };
      ws.onerror = (err: any) => {
        if (onError) onError(err);
      };
      this.connections.set(endpoint, ws);
    } catch (err) {
      if (onError) onError(err);
    }
  }
  handleReconnect(endpoint: string, onMessage: (d: any) => void, onError: ((e: any) => void) | null): void {
    const attempts = this.reconnectAttempts.get(endpoint) || 0;
    if (attempts < this.maxReconnectAttempts) {
      const next = attempts + 1;
      this.reconnectAttempts.set(endpoint, next);
      const delay = Math.pow(2, next) * 1000;
      setTimeout(() => this.connect(endpoint, onMessage, onError), delay);
    } else {
      showToast(`Unable to reconnect to ${endpoint}`);
      if (onError) onError(new Error('max reconnect attempts reached'));
    }
  }
}

test('profile DOM diffing for large position updates', () => {
  document.body.innerHTML = '<div id="positionsList"></div>';
  const positions: Record<string, any> = {};
  for (let i = 0; i < 1000; i++) {
    positions['T' + i] = { quantity: i, unrealized: i };
  }
  const start = performance.now();
  for (let i = 0; i < 10; i++) {
    updatePositionsDisplay(positions);
  }
  const duration = performance.now() - start;
  console.log('DOM diffing 10x1000 positions took', duration.toFixed(2), 'ms');
  expect(duration).toBeGreaterThan(0);
});

test('profile websocket reconnection loop', () => {
  jest.useFakeTimers();
  (global as any).showToast = jest.fn();
  showToast = (global as any).showToast;

  class MockSocket {
    onopen?: () => void;
    onmessage?: (ev: any) => void;
    onclose?: (ev: any) => void;
    onerror?: (err: any) => void;
    constructor() {
      setTimeout(() => {
        this.onclose && this.onclose({});
      }, 0);
    }
    close() {}
  }
  (global as any).WebSocket = MockSocket as any;

  const client = new SolSeekerWebSocket();
  const start = performance.now();
  client.connect('/test', () => {});
  jest.runAllTimers();
  const duration = performance.now() - start;
  console.log('Reconnection loop for', client.maxReconnectAttempts, 'attempts took', duration.toFixed(2), 'ms');
  expect(duration).toBeGreaterThan(0);
});
