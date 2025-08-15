/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import * as vm from 'vm';

test('disables save on unknown demo asset', () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  const fnMatch = html.match(/function validateDemoAssets\(\)[\s\S]*?}\n/);
  expect(fnMatch).toBeTruthy();

  document.body.innerHTML = '<select id="demoAssets" multiple><option selected value="FAKE">FAKE</option></select><button id="saveSettings"></button>';
  const context: any = { document, dashboardState: { assets: ['BTC'] } };
  vm.createContext(context);
  const script = new vm.Script(fnMatch![0]);
  script.runInContext(context);
  const valid = context.validateDemoAssets();
  expect(valid).toBe(false);
  expect((document.getElementById('saveSettings') as HTMLButtonElement).disabled).toBe(true);
});
