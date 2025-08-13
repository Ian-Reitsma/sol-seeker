/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import * as vm from 'vm';

test('order form disabled in demo mode', () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  const match = html.match(/function updateOrderTicket\(\)[\s\S]*?\n\s*}\n\s*}/);
  expect(match).toBeTruthy();
  document.body.innerHTML = '<button id="submitOrder"></button>';
  const context: any = { document, dashboardState: { isDemo: true } };
  vm.createContext(context);
  const script = new vm.Script(`${match![0]}; updateOrderTicket();`);
  script.runInContext(context);
  const btn = document.getElementById('submitOrder') as HTMLButtonElement;
  expect(btn.disabled).toBe(true);
});
