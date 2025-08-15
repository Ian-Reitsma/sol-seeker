/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import * as vm from 'vm';

test('renders license diagnostics panel', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  const licMatch = html.match(/async function loadLicense\(\)[\s\S]*?}\n\s*}/);
  const infoMatch = html.match(/function updateLicenseInfo\(\)[\s\S]*?}\n\s*}/);
  expect(licMatch).toBeTruthy();
  expect(infoMatch).toBeTruthy();

  document.body.innerHTML = '<div id="licenseInfo"><div>WALLET: <span id="licenseWallet"></span></div><div>MODE: <span id="licenseMode"></span></div><div>ISSUED: <span id="licenseIssued"></span></div></div>';
  const mockLicense = { wallet: 'demoWallet', mode: 'demo', issued_at: 1234567890 };
  const context: any = {
    document,
    dashboardState: { assets: null, license: null, licenseError: false, isDemo: false },
    apiClient: {
      getLicense: () => Promise.resolve(mockLicense)
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
  expect(document.getElementById('licenseWallet')?.textContent).toBe(mockLicense.wallet);
  expect(document.getElementById('licenseMode')?.textContent).toBe(mockLicense.mode);
  const issuedText = new Date(mockLicense.issued_at * 1000).toLocaleString();
  expect(document.getElementById('licenseIssued')?.textContent).toBe(issuedText);
});

