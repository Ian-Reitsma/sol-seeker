/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import * as vm from 'vm';

test('heartbeat indicator shows DISCONNECTED after timeout', () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  const match = html.match(/function checkWsHeartbeat\(\)[\s\S]*?\n\s*}\n/);
  expect(match).toBeTruthy();
  document.body.innerHTML = '<span id="wsStatus"></span>';
  const context: any = { document, wsHeartbeatTs: Date.now() - 11000 };
  vm.createContext(context);
  const script = new vm.Script(`${match![0]}; checkWsHeartbeat();`);
  script.runInContext(context);
  const el = document.getElementById('wsStatus');
  expect(el?.textContent).toBe('DISCONNECTED');
});
