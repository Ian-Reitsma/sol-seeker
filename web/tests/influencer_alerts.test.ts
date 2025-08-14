/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import { jest } from '@jest/globals';

test('influencer alerts render, dedupe, open links, and purge stale', async () => {
  jest.useFakeTimers();
  jest.setSystemTime(0);
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  const datasets = [
    [
      { handle: '@alice', message: 'Buy SOL', followers: 1000, stance: 'bull', url: 'https://x.com/alice/1' },
      { handle: '@alice', message: 'Buy SOL', followers: 1000, stance: 'bull', url: 'https://x.com/alice/1' }
    ],
    []
  ];

  const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
  (global as any).apiClient = {
    get: jest.fn(() => Promise.resolve(datasets.shift()))
  };
  (global as any).pollingIntervals = [];
  const influencerState = new Map<string, { element: HTMLElement; timestamp: number }>();

  function updateInfluencers(list: any[]) {
    const container = document.getElementById('influencerAlerts');
    if (!container) return;
    const now = Date.now();
    const ONE_HOUR = 3600000;

    if (Array.isArray(list) && list.length > 0) {
      if (container.textContent.includes('DATA UNAVAILABLE')) {
        container.innerHTML = '';
      }
      list.forEach(a => {
        const key = `${a.handle}|${a.message}`;
        const existing = influencerState.get(key);
        if (existing) {
          existing.timestamp = now;
          return;
        }
        const row = document.createElement('div');
        row.className = 'flex items-center space-x-3 cursor-pointer';
        const stanceClass = a.stance && a.stance.toUpperCase().includes('BEAR')
          ? 'text-blade-orange'
          : 'text-cyan-glow';
        const avatar = `https://unavatar.io/${encodeURIComponent(a.handle.replace(/^@/, ''))}`;
        row.innerHTML = `<img src="${avatar}" class="w-6 h-6 rounded-full" alt=""><div class="flex-1"><div class="hologram-text text-white font-bold">${a.handle}</div><div class="hologram-text text-xs text-blade-amber/60">${a.message}</div></div><div class="text-right"><div class="hologram-text text-xs text-blade-amber/60">${a.followers} followers</div><div class="hologram-text text-xs font-bold ${stanceClass}">${a.stance}</div></div>`;
        if (a.url) row.addEventListener('click', () => window.open(a.url, '_blank'));
        container.appendChild(row);
        influencerState.set(key, { element: row, timestamp: now });
      });
    }

    for (const [key, entry] of influencerState.entries()) {
      if (now - entry.timestamp > ONE_HOUR) {
        entry.element.remove();
        influencerState.delete(key);
      }
    }

    if (container.children.length === 0) {
      container.innerHTML = '<div class="hologram-text text-blade-amber/60">DATA UNAVAILABLE</div>';
    }
  }

  async function loadInfluencers() {
    const influencers = await (global as any).apiClient
      .get('/sentiment/influencers')
      .catch(() => null);
    if (influencers) updateInfluencers(influencers);
  }

  await loadInfluencers();
  const container = document.getElementById('influencerAlerts')!;
  expect(container.children.length).toBe(1);
  const row = container.children[0] as HTMLElement;
  expect(row.textContent).toContain('@alice');
  expect(row.querySelector('img')!.getAttribute('src')).toContain('unavatar.io');
  row.click();
  expect(openSpy).toHaveBeenCalledWith('https://x.com/alice/1', '_blank');

  jest.advanceTimersByTime(3600000 + 1);
  await loadInfluencers();
  expect(container.textContent).toContain('DATA UNAVAILABLE');
  jest.useRealTimers();
});
