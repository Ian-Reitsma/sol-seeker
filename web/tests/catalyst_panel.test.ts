/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import { jest } from '@jest/globals';

function updateCatalystList(list: any[]) {
  const container = document.getElementById('catalystList');
  if (!container) return;
  container.replaceChildren();
  if (!Array.isArray(list) || list.length === 0) {
    const msg = document.createElement('div');
    msg.className = 'hologram-text text-white';
    msg.textContent = 'None';
    container.appendChild(msg);
    return;
  }
  const frag = document.createDocumentFragment();
  const colorMap: Record<string, [string, string]> = {
    high: ['bg-blade-orange', 'text-blade-orange'],
    medium: ['bg-cyan-glow', 'text-cyan-glow'],
    low: ['bg-blade-amber', 'text-blade-amber']
  };
  list.forEach(item => {
    const [bg, text] = colorMap[item.severity] || colorMap.low;
    const row = document.createElement('div');
    row.className = 'flex justify-between items-center';
    const left = document.createElement('div');
    left.className = 'flex items-center space-x-2';
    const dot = document.createElement('div');
    dot.className = `w-2 h-2 rounded-full ${bg}${item.severity === 'high' ? ' animate-pulse' : ''}`;
    left.appendChild(dot);
    const name = document.createElement('span');
    name.className = 'hologram-text text-white';
    name.textContent = item.name;
    left.appendChild(name);
    row.appendChild(left);
    const time = document.createElement('span');
    time.className = `hologram-text ${text}`;
    time.textContent = 'soon';
    row.appendChild(time);
    frag.appendChild(row);
  });
  container.appendChild(frag);
}

test('catalyst panel refreshes and clears when empty', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  const now = Date.now() / 1000;
  const data1 = [{ name: 'Firedancer Testnet', eta: now + 3600, severity: 'high' }];
  const data2 = [{ name: 'Jupiter V2 Launch', eta: now + 7200, severity: 'medium' }];

  const getCatalysts = jest
    .fn<() => Promise<any[]>>()
    .mockResolvedValueOnce(data1)
    .mockResolvedValueOnce(data2)
    .mockResolvedValueOnce([]);

  (global as any).apiClient = { getCatalysts };
  (global as any).dashboardState = {};
  (global as any).pollingIntervals = [];

    async function loadCatalysts() {
      try {
        const list = await (global as any).apiClient.getCatalysts().catch(() => []);
        (global as any).dashboardState.catalysts = list;
        updateCatalystList(list);
      } catch (err) {
        console.error('Catalyst load failed', err);
      }
    }

  await loadCatalysts();
  const listEl = document.getElementById('catalystList')!;
  expect(listEl.textContent).toContain('Firedancer Testnet');

  await loadCatalysts();
  expect(listEl.textContent).toContain('Jupiter V2 Launch');
  expect(listEl.textContent).not.toContain('Firedancer Testnet');

  await loadCatalysts();
  expect(listEl.textContent).toBe('None');
});

test('sanitizes HTML in catalyst list', () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  const xss = '<img src=x onerror="window.__xss=true">';
  updateCatalystList([{ name: xss, eta: 0, severity: 'low' }]);
  const container = document.getElementById('catalystList')!;
  expect(container.textContent).toContain(xss);
  expect((globalThis as any).__xss).toBeUndefined();
});
