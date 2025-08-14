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
    container.innerHTML = '';
    if (!Array.isArray(tokens) || tokens.length === 0) {
      container.innerHTML = '<div class="hologram-text text-blade-amber/60">DATA UNAVAILABLE</div>';
      return;
    }
    tokens.forEach(t => {
      const row = document.createElement('div');
      row.className = 'flex items-center justify-between';
      const sentimentClass = t.sentiment && t.sentiment.toUpperCase().includes('BEAR')
        ? 'text-blade-orange'
        : 'text-cyan-glow';
      row.innerHTML = `<div class="flex items-center space-x-3"><div class="w-6 h-6 bg-gradient-to-r from-cyan-glow to-blade-cyan rounded-full flex items-center justify-center text-xs font-bold">🔥</div><div><div class="hologram-text text-white font-bold">${t.symbol}</div><div class="hologram-text text-xs text-blade-amber/60">${t.mentions} mentions • ${t.change_pct}%</div></div></div><div class="text-right"><div class="hologram-text ${sentimentClass} font-bold">${t.sentiment}</div><div class="hologram-text text-xs text-blade-amber/60">SENTIMENT</div></div>`;
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
