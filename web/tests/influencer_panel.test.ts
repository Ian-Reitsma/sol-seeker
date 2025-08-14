/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import { jest } from '@jest/globals';

const influencerState = new Map<string, { element: HTMLElement; timestamp: number }>();

function updateInfluencers(list: any[]) {
  const container = document.getElementById('influencerAlerts');
  if (!container) return;
  const now = Date.now();
  const ONE_HOUR = 3600000;

  if (Array.isArray(list) && list.length > 0) {
    if (container.textContent && container.textContent.includes('DATA UNAVAILABLE')) {
      container.replaceChildren();
    }
    list.forEach(a => {
      const itemTime = a.timestamp ? new Date(a.timestamp).getTime() : now;
      if (now - itemTime > ONE_HOUR) return;
      const key = `${a.handle}|${a.message}`;
      const existing = influencerState.get(key);
      if (existing) {
        existing.timestamp = itemTime;
        return;
      }
      const stanceBear = a.stance && a.stance.toUpperCase().includes('BEAR');
      const stanceClass = stanceBear ? 'text-blade-orange' : 'text-cyan-glow';
      const stanceIcon = stanceBear ? '🐻' : '🐂';
      const avatar = a.avatar || `https://unavatar.io/${encodeURIComponent(a.handle.replace(/^@/, ''))}`;
      const row = document.createElement('div');
      row.className = 'flex items-center space-x-3 cursor-pointer';
      const img = document.createElement('img');
      img.src = avatar;
      img.className = 'w-6 h-6 rounded-full';
      img.alt = '';
      row.appendChild(img);
      const center = document.createElement('div');
      center.className = 'flex-1';
      const handle = document.createElement('div');
      handle.className = 'hologram-text text-white font-bold';
      handle.textContent = a.handle;
      center.appendChild(handle);
      const msg = document.createElement('div');
      msg.className = 'hologram-text text-xs text-blade-amber/60';
      msg.textContent = a.message;
      center.appendChild(msg);
      row.appendChild(center);
      const right = document.createElement('div');
      right.className = 'text-right';
      const followers = document.createElement('div');
      followers.className = 'hologram-text text-xs text-blade-amber/60';
      followers.textContent = `${a.followers} followers`;
      right.appendChild(followers);
      const stance = document.createElement('div');
      stance.className = `hologram-text text-xs font-bold ${stanceClass}`;
      stance.textContent = `${stanceIcon} ${a.stance}`;
      right.appendChild(stance);
      row.appendChild(right);
      if (a.url) row.addEventListener('click', () => window.open(a.url, '_blank'));
      container.appendChild(row);
      influencerState.set(key, { element: row, timestamp: itemTime });
    });
  }

  for (const [key, entry] of influencerState.entries()) {
    if (now - entry.timestamp > ONE_HOUR) {
      entry.element.remove();
      influencerState.delete(key);
    }
  }

  if (container.children.length === 0) {
    const msg = document.createElement('div');
    msg.className = 'hologram-text text-blade-amber/60';
    msg.textContent = 'DATA UNAVAILABLE';
    container.appendChild(msg);
  }
}

test('renders avatar, stance icon, link and prunes stale alerts', () => {
  jest.useFakeTimers();
  jest.setSystemTime(0);
  influencerState.clear();
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  const alerts = [
    { handle: '@alice', message: 'Buy SOL', followers: 10, stance: 'bull', url: 'https://x.com/alice/1', timestamp: Date.now() },
    { handle: '@bob', message: 'Sell SOL', followers: 5, stance: 'bear', url: 'https://x.com/bob/1', timestamp: Date.now() - 3600000 - 1 }
  ];

  const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
  updateInfluencers(alerts);
  const container = document.getElementById('influencerAlerts')!;
  expect(container.children.length).toBe(1);
  const row = container.children[0] as HTMLElement;
  expect(row.querySelector('img')).not.toBeNull();
  expect(row.textContent).toContain('🐂');
  row.click();
  expect(openSpy).toHaveBeenCalledWith('https://x.com/alice/1', '_blank');

  jest.advanceTimersByTime(3600000 + 1);
  updateInfluencers([]);
  expect(container.textContent).toContain('DATA UNAVAILABLE');
  jest.useRealTimers();
});

test('sanitizes HTML in influencer alerts', () => {
  influencerState.clear();
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  const xss = '<img src=x onerror="window.__xss=true">';
  updateInfluencers([{ handle: xss, message: 'hi', followers: 1, stance: 'bull', timestamp: Date.now() }]);
  const container = document.getElementById('influencerAlerts')!;
  expect(container.textContent).toContain(xss);
  expect((globalThis as any).__xss).toBeUndefined();
});

