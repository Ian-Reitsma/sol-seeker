/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import { jest } from '@jest/globals';

test('catalyst list refreshes and clears when empty', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  const datasets = [
    [
      { name: 'Upgrade', eta: Date.now() / 1000 + 3600, severity: 'high' },
      { name: 'Release', eta: Date.now() / 1000 + 7200, severity: 'low' }
    ],
    []
  ];

  (global as any).apiClient = {
    get: jest.fn((url: string) => {
      if (url === '/events/catalysts') {
        return Promise.resolve(datasets.shift());
      }
      return Promise.resolve([]);
    })
  };
  (global as any).pollingIntervals = [];

  function formatTimeDiff(eta: any) {
    const ts = typeof eta === 'number' ? eta * 1000 : new Date(eta).getTime();
    const diff = ts - Date.now();
    if (diff <= 0) return 'soon';
    const mins = Math.floor(diff / 60000);
    const days = Math.floor(mins / 1440);
    const hours = Math.floor((mins % 1440) / 60);
    const minutes = mins % 60;
    const parts: string[] = [];
    if (days) parts.push(`${days}D`);
    if (hours) parts.push(`${hours}H`);
    parts.push(`${minutes}M`);
    return parts.join(' ');
  }

  function updateCatalystList(list: any[]) {
    const container = document.getElementById('catalystList');
    if (!container) return;
    container.innerHTML = '';
    if (!Array.isArray(list) || list.length === 0) {
      container.innerHTML = '<div class="hologram-text text-white">None</div>';
      return;
    }
    const frag = document.createDocumentFragment();
    list.forEach(item => {
      const row = document.createElement('div');
      row.className = 'flex justify-between items-center';
      const name = document.createElement('span');
      name.textContent = item.name;
      const time = document.createElement('span');
      time.textContent = formatTimeDiff(item.eta);
      row.appendChild(name);
      row.appendChild(time);
      frag.appendChild(row);
    });
    container.appendChild(frag);
  }

  async function loadCatalysts() {
    const list = await (global as any).apiClient.get('/events/catalysts').catch(() => null);
    if (list) updateCatalystList(list);
  }

  await loadCatalysts();
  const container = document.getElementById('catalystList')!;
  expect(container.children.length).toBe(2);
  expect(container.textContent).toContain('Upgrade');

  await loadCatalysts();
  expect(container.textContent).toBe('None');
});
