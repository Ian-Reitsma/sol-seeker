/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import * as vm from 'vm';

test('shows license error when fetch fails', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  const licMatch = html.match(/async function loadLicense\(\)[\s\S]*?}\n\s*}/);
  const infoMatch = html.match(/function updateLicenseInfo\(\)[\s\S]*?}\n\s*}/);
  expect(licMatch).toBeTruthy();
  expect(infoMatch).toBeTruthy();
  document.body.innerHTML = '<div id="licenseInfo"><div>WALLET: <span id="licenseWallet"></span></div><div>MODE: <span id="licenseMode"></span></div><div>ISSUED: <span id="licenseIssued"></span></div></div>';
  const context: any = {
    document,
    dashboardState: { assets: null, license: null, licenseError: false, isDemo: false },
    apiClient: {
      getLicense: () => Promise.reject(new Error('fail'))
    },
    updateLicenseMode: () => {},
    updateLicenseExpiryBanner: () => {},
    licenseInfoTemplate: document.getElementById('licenseInfo')!.innerHTML,
    requestAnimationFrame: (cb: any) => cb()
  };
  vm.createContext(context);
  const script = new vm.Script(`${licMatch![0]} ${infoMatch![0]}`);
  script.runInContext(context);
  await context.loadLicense();
  const panel = document.getElementById('licenseInfo');
  expect(panel?.textContent).toBe('License data unavailable');
  expect(panel?.classList.contains('text-blade-orange')).toBe(true);
});
