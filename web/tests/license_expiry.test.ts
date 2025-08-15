/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import * as vm from 'vm';

test('shows expiry banner when license near expiry', () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  const fnMatch = html.match(/function updateLicenseExpiryBanner\(\)[\s\S]*}\n/);
  expect(fnMatch).toBeTruthy();

  document.body.innerHTML = '<div id="licenseExpiryBanner" class="hidden"></div>';
  const context: any = { document, dashboardState: { licenseExpiry: Math.floor(Date.now() / 1000) + 3 * 86400 } };
  vm.createContext(context);
  const script = new vm.Script(fnMatch![0]);
  script.runInContext(context);
  context.updateLicenseExpiryBanner();
  expect(document.getElementById('licenseExpiryBanner')?.classList.contains('hidden')).toBe(false);
});
