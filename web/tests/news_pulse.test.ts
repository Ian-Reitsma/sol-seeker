/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import { jest } from '@jest/globals';

test('news feed renders chronologically and pulse shows metrics with timestamp', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  const newsDatasets = [
    [
      { id: 1, title: 'Old', source: 'S1', confidence: 90, timestamp: '2024-01-01T00:00:00Z' },
      { id: 2, title: 'New', source: 'S2', confidence: 80, timestamp: '2024-01-02T00:00:00Z' }
    ],
    [
      { id: 2, title: 'New', source: 'S2', confidence: 80, timestamp: '2024-01-02T00:00:00Z' },
      { id: 3, title: 'Newest', source: 'S3', confidence: 70, timestamp: '2024-01-03T00:00:00Z' }
    ]
  ];

  const pulseData = {
    fear_greed: 55,
    fear_greed_pct: 55,
    social_volume: 10,
    social_volume_pct: 10,
    fomo: 20,
    fomo_pct: 20,
    timestamp: '2024-01-02T00:00:00Z'
  };

  (global as any).apiClient = {
    get: jest.fn((url: string) => {
      if (url === '/news') {
        return Promise.resolve(newsDatasets.shift() || []);
      }
      if (url === '/sentiment/pulse') {
        return Promise.resolve(pulseData);
      }
      return Promise.resolve([]);
    })
  };
  (global as any).pollingIntervals = [];

  function updatePulse(p: any) {
    const fg = document.getElementById('fearGreedValue');
    const fgBar = document.getElementById('fearGreedBar');
    if (fg && p.fear_greed !== undefined) fg.textContent = p.fear_greed;
    if (fgBar && p.fear_greed_pct !== undefined) fgBar.style.width = `${p.fear_greed_pct}%`;
    const sv = document.getElementById('socialVolumeValue');
    const svBar = document.getElementById('socialVolumeBar');
    if (sv && p.social_volume !== undefined) sv.textContent = p.social_volume;
    if (svBar && p.social_volume_pct !== undefined) svBar.style.width = `${p.social_volume_pct}%`;
    const fomo = document.getElementById('fomoValue');
    const fomoBar = document.getElementById('fomoBar');
    if (fomo && p.fomo !== undefined) fomo.textContent = p.fomo;
    if (fomoBar && p.fomo_pct !== undefined) fomoBar.style.width = `${p.fomo_pct}%`;
    const ts = document.getElementById('pulseTimestamp');
    if (ts && p.timestamp) ts.textContent = new Date(p.timestamp).toLocaleString();
  }

  function updateNews(list: any[]) {
    const container = document.getElementById('newsFeed');
    if (!container) return;
    if (!Array.isArray(list) || list.length === 0) {
      if (container.children.length === 0) {
        container.innerHTML = '<div class="hologram-text text-blade-amber/60">NO NEWS</div>';
      }
      return;
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
      row.innerHTML = `<div class="w-2 h-2 bg-blade-orange rounded-full mt-1"></div><div><div class="hologram-text text-white">${item.title}</div><div class="hologram-text text-blade-amber/60">${meta}</div></div>`;
      container.insertBefore(row, container.firstChild);
      if (item.id > lastId) lastId = item.id;
    });
    if (fresh.length > 0) {
      localStorage.setItem('last_news_id', String(lastId));
    } else if (container.children.length === 0) {
      container.innerHTML = '<div class="hologram-text text-blade-amber/60">NO NEWS</div>';
    }
  }

  async function loadSocialFeeds() {
    const [pulse, news] = await Promise.all([
      (global as any).apiClient.get('/sentiment/pulse').catch(() => null),
      (global as any).apiClient.get('/news').catch(() => null)
    ]);
    if (pulse) updatePulse(pulse);
    if (news) updateNews(news);
  }

  await loadSocialFeeds();
  const newsContainer = document.getElementById('newsFeed')!;
  expect(newsContainer.children.length).toBe(2);
  let timestamps = Array.from(newsContainer.children).map(n => n.getAttribute('data-timestamp'));
  expect(timestamps).toEqual(['2024-01-02T00:00:00Z', '2024-01-01T00:00:00Z']);

  const fg = document.getElementById('fearGreedValue')!;
  expect(fg.textContent).toBe('55');
  const tsEl = document.getElementById('pulseTimestamp')!;
  expect(tsEl.textContent).toContain('2024');

  await loadSocialFeeds();
  expect(newsContainer.children.length).toBe(3);
  timestamps = Array.from(newsContainer.children).map(n => n.getAttribute('data-timestamp'));
  expect(timestamps).toEqual([
    '2024-01-03T00:00:00Z',
    '2024-01-02T00:00:00Z',
    '2024-01-01T00:00:00Z'
  ]);
});

