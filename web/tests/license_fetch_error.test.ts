/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import * as vm from 'vm';

test('shows license error when fetch fails', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  const dashMatch = html.match(/async function updateDashboardData\(\)[\s\S]*?}\n\s*}/);
  const licMatch = html.match(/function updateLicenseInfo\(\)[\s\S]*?}\n\s*}/);
  expect(dashMatch).toBeTruthy();
  expect(licMatch).toBeTruthy();
  document.body.innerHTML = '<div id="licenseInfo"><div>WALLET: <span id="licenseWallet"></span></div><div>MODE: <span id="licenseMode"></span></div><div>ISSUED: <span id="licenseIssued"></span></div></div>';
  const context: any = {
    document,
    dashboardState: { assets: null, license: null, licenseError: false, isDemo: false },
    apiClient: {
      getDashboard: () => Promise.resolve(null),
      getPositions: () => Promise.resolve(null),
      getOrders: () => Promise.resolve(null),
      getFeatures: () => Promise.resolve({ features: [] }),
      getPosterior: () => Promise.resolve(null),
      getState: () => Promise.resolve(null),
      getRiskSecurity: () => Promise.resolve(null),
      getLicense: () => Promise.reject(new Error('fail')),
      getCatalysts: () => Promise.resolve(null),
      getAssets: () => Promise.resolve(null),
      getFeaturesSchema: () => Promise.resolve(null)
    },
    updateFeatureStream: () => {},
    renderFeatureSnapshot: () => {},
    updateLicenseMode: () => {},
    updateTradingButton: () => {},
    populateAssetSelect: () => {},
    applySettings: () => {},
    updateModePanel: () => {},
    renderFeatureSchema: () => {},
    updatePortfolioMetrics: () => {},
    updateRiskMetrics: () => {},
    updateSecurityPanel: () => {},
    updatePositionsDisplay: () => Promise.resolve(),
    updateSystemHealth: () => {},
    updateRegimeAnalysis: () => {},
    updateMarketStats: () => {},
    updateCatalystList: () => {},
    tradingActive: false,
    licenseInfoTemplate: document.getElementById('licenseInfo')!.innerHTML
  };
  vm.createContext(context);
  const script = new vm.Script(`${dashMatch![0]} ${licMatch![0]}`);
  script.runInContext(context);
  await context.updateDashboardData();
  context.updateLicenseInfo();
  const panel = document.getElementById('licenseInfo');
  expect(panel?.textContent).toBe('License data unavailable');
  expect(panel?.classList.contains('text-blade-orange')).toBe(true);
});
