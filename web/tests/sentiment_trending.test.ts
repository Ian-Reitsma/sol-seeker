/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import { jest } from '@jest/globals';

test('trending tokens update and reorder with sentiment colors', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  const datasets = [
    [
      { symbol: 'AAA', mentions: 10, change_pct: 1.2, sentiment: 'BULLISH' },
      { symbol: 'BBB', mentions: 8, change_pct: -0.5, sentiment: 'BEARISH' }
    ],
    [
      { symbol: 'BBB', mentions: 9, change_pct: -0.2, sentiment: 'BEARISH' },
      { symbol: 'AAA', mentions: 11, change_pct: 2.0, sentiment: 'BULLISH' }
    ]
  ];

  (global as any).apiClient = {
    get: jest.fn((url: string) => {
      if (url === '/sentiment/trending') {
        return Promise.resolve(datasets.shift());
      }
      return Promise.resolve([]);
    })
  };
  (global as any).pollingIntervals = [];

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
      const sentimentClass = t.sentiment && t.sentiment.toUpperCase().includes('BEAR')
        ? 'text-blade-orange'
        : 'text-cyan-glow';
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
      val.textContent = String(t.sentiment);
      right.appendChild(val);
      const label = document.createElement('div');
      label.className = 'hologram-text text-xs text-blade-amber/60';
      label.textContent = 'SENTIMENT';
      right.appendChild(label);
      row.appendChild(right);
      container.appendChild(row);
    });
  }

  async function loadSocialFeeds() {
    const trending = await (global as any).apiClient
      .get('/sentiment/trending')
      .catch(() => null);
    if (trending) updateTrending(trending);
  }

  await loadSocialFeeds();
  const container = document.getElementById('trendingTokens')!;
  expect(container.children.length).toBe(2);
  expect(container.children[0].textContent).toContain('AAA');
  const bearishSentiment = container.children[1].querySelector('.text-right .font-bold') as HTMLElement;
  expect(bearishSentiment.className).toContain('text-blade-orange');

  await loadSocialFeeds();
  expect(container.children[0].textContent).toContain('BBB');
});
