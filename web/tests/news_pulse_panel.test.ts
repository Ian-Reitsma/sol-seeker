/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import { jest } from '@jest/globals';

function updateNews(list: any[]) {
  const container = document.getElementById('newsFeed');
  if (!container) return;
  if (!Array.isArray(list) || list.length === 0) {
    if (container.children.length === 0) {
      const msg = document.createElement('div');
      msg.className = 'hologram-text text-blade-amber/60';
      msg.textContent = 'NO NEWS';
      container.appendChild(msg);
    }
    return;
  }
  if (container.textContent && container.textContent.includes('NO NEWS')) {
    container.replaceChildren();
  }
  let lastId = parseInt(localStorage.getItem('last_news_id') || '0', 10);
  const fresh = list
    .filter(item => item.id && item.id > lastId)
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  fresh.forEach(item => {
    const row = document.createElement('div');
    row.className = 'flex items-start space-x-2';
    row.dataset.timestamp = item.timestamp;
    const ts = new Date(item.timestamp).toLocaleString();
    const meta = `Source: ${item.source}${item.confidence !== undefined ? ` • Confidence: ${item.confidence}%` : ''} • ${ts}`;
    const dot = document.createElement('div');
    dot.className = 'w-2 h-2 bg-blade-orange rounded-full mt-1';
    row.appendChild(dot);
    const wrap = document.createElement('div');
    const title = document.createElement('div');
    title.className = 'hologram-text text-white';
    title.textContent = item.title;
    wrap.appendChild(title);
    const metaDiv = document.createElement('div');
    metaDiv.className = 'hologram-text text-blade-amber/60';
    metaDiv.textContent = meta;
    wrap.appendChild(metaDiv);
    row.appendChild(wrap);
    container.insertBefore(row, container.firstChild);
    if (item.id > lastId) lastId = item.id;
  });
  if (fresh.length > 0) {
    localStorage.setItem('last_news_id', String(lastId));
  } else if (container.children.length === 0) {
    const msg = document.createElement('div');
    msg.className = 'hologram-text text-blade-amber/60';
    msg.textContent = 'NO NEWS';
    container.appendChild(msg);
  }
}

function updatePulse(p: any) {
  const fgBar = document.getElementById('fearGreedBar');
  if (fgBar && p.fear_greed_pct !== undefined) fgBar.style.width = `${p.fear_greed_pct}%`;
  const svBar = document.getElementById('socialVolumeBar');
  if (svBar && p.social_volume_pct !== undefined) svBar.style.width = `${p.social_volume_pct}%`;
  const fomoBar = document.getElementById('fomoBar');
  if (fomoBar && p.fomo_pct !== undefined) fomoBar.style.width = `${p.fomo_pct}%`;
}

test('news items sorted by time and pulse bars match percentages', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  const newsData = [
    { id: 1, timestamp: '2023-01-01T00:00:00Z', title: 'Older', source: 'A', confidence: 60 },
    { id: 2, timestamp: '2023-01-01T01:00:00Z', title: 'Newer', source: 'B', confidence: 80 }
  ];

  const pulseData = {
    fear_greed: 42,
    fear_greed_pct: 80,
    social_volume: 100,
    social_volume_pct: 40,
    fomo: 7,
    fomo_pct: 25,
    timestamp: '2023-01-01T02:00:00Z'
  };

  (global as any).apiClient = {
    get: jest.fn((url: string) => {
      if (url === '/news') return Promise.resolve(newsData);
      if (url === '/sentiment/pulse') return Promise.resolve(pulseData);
      return Promise.resolve(null);
    })
  };
  (global as any).pollingIntervals = [];

  async function loadFeeds() {
    const [pulse, news] = await Promise.all([
      (global as any).apiClient.get('/sentiment/pulse').catch(() => null),
      (global as any).apiClient.get('/news').catch(() => null)
    ]);
    if (pulse) updatePulse(pulse);
    if (news) updateNews(news);
  }

  await loadFeeds();

  const newsContainer = document.getElementById('newsFeed')!;
  expect(newsContainer.children.length).toBe(2);
  const timestamps = Array.from(newsContainer.children).map(c => (c as HTMLElement).dataset.timestamp);
  expect(timestamps).toEqual(['2023-01-01T01:00:00Z', '2023-01-01T00:00:00Z']);

  expect((document.getElementById('fearGreedBar') as HTMLElement).style.width).toBe('80%');
  expect((document.getElementById('socialVolumeBar') as HTMLElement).style.width).toBe('40%');
  expect((document.getElementById('fomoBar') as HTMLElement).style.width).toBe('25%');
});

test('sanitizes HTML in news feed', () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;
  localStorage.clear();
  const xss = '<img src=x onerror="window.__xss=true">';
  updateNews([{ id: 1, timestamp: '2023-01-01T00:00:00Z', title: xss, source: 'X', confidence: 50 }]);
  const container = document.getElementById('newsFeed')!;
  expect(container.textContent).toContain(xss);
  expect((globalThis as any).__xss).toBeUndefined();
});

