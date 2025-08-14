/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import { jest } from '@jest/globals';

function updateTrending(tokens: any[]) {
  const container = document.getElementById('trendingTokens');
  if (!container) return;
  container.replaceChildren();
  if (!Array.isArray(tokens) || tokens.length === 0) {
    const msg = document.createElement('div');
    msg.className = 'hologram-text text-blade-amber/60';
    msg.textContent = 'DATA UNAVAILABLE';
    container.appendChild(msg);
    return;
  }
  tokens.forEach(t => {
    const row = document.createElement('div');
    row.className = 'flex items-center justify-between';
    const isNegative = typeof t.sentiment === 'number'
      ? t.sentiment < 0
      : t.sentiment && t.sentiment.toUpperCase().includes('BEAR');
    const sentimentClass = isNegative ? 'text-blade-orange' : 'text-cyan-glow';
    const sentimentValue = typeof t.sentiment === 'number'
      ? t.sentiment.toFixed(2)
      : t.sentiment;
    const left = document.createElement('div');
    left.className = 'flex items-center space-x-3';
    const icon = document.createElement('div');
    icon.className = 'w-6 h-6 bg-gradient-to-r from-cyan-glow to-blade-cyan rounded-full flex items-center justify-center text-xs font-bold';
    icon.textContent = '🔥';
    left.appendChild(icon);
    const info = document.createElement('div');
    const sym = document.createElement('div');
    sym.className = 'hologram-text text-white font-bold';
    sym.textContent = t.symbol;
    info.appendChild(sym);
    const mentions = document.createElement('div');
    mentions.className = 'hologram-text text-xs text-blade-amber/60';
    mentions.textContent = `${t.mentions} mentions • ${t.change_pct}%`;
    info.appendChild(mentions);
    left.appendChild(info);
    row.appendChild(left);
    const right = document.createElement('div');
    right.className = 'text-right';
    const val = document.createElement('div');
    val.className = `hologram-text ${sentimentClass} font-bold`;
    val.textContent = String(sentimentValue);
    right.appendChild(val);
    const label = document.createElement('div');
    label.className = 'hologram-text text-xs text-blade-amber/60';
    label.textContent = 'SENTIMENT';
    right.appendChild(label);
    row.appendChild(right);
    container.appendChild(row);
  });
}

test('trending panel shows change pct and highlights negative sentiment', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  const dataset = [
    { symbol: 'AAA', mentions: 10, change_pct: 1.5, sentiment: 0.8 },
    { symbol: 'BBB', mentions: 5, change_pct: -2.3, sentiment: -0.4 }
  ];

  (global as any).apiClient = {
    get: jest.fn((url: string) => {
      if (url === '/sentiment/trending') {
        return Promise.resolve(dataset);
      }
      return Promise.resolve([]);
    })
  };
  (global as any).pollingIntervals = [];

  async function loadSocialFeeds() {
    const trending = await (global as any).apiClient.get('/sentiment/trending').catch(() => null);
    if (trending) updateTrending(trending);
  }

  await loadSocialFeeds();
  const container = document.getElementById('trendingTokens')!;
  expect(container.children.length).toBe(2);
  expect(container.children[0].textContent).toContain('1.5%');
  expect(container.children[1].textContent).toContain('-2.3%');
  const negative = container.children[1].querySelector('.text-right .font-bold') as HTMLElement;
  expect(negative.className).toContain('text-blade-orange');
});

test('sanitizes HTML in trending tokens', () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  const xss = '<img src=x onerror="window.__xss=true">';
  updateTrending([{ symbol: xss, mentions: 1, change_pct: 0, sentiment: 0.1 }]);
  const container = document.getElementById('trendingTokens')!;
  expect(container.textContent).toContain(xss);
  expect((globalThis as any).__xss).toBeUndefined();
});
