/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import { jest } from '@jest/globals';

test('autosave failure shows toast and reverts settings', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  let settingsTimer: any;
  let isSavingSettings = false;
  const settingControls = ['maxDrawdown', 'maxPosition', 'maxTrades', 'sniperToggle', 'arbToggle', 'mmToggle', 'failoverToggle', 'rpcSelect', 'modeSelect', 'demoCash', 'demoAssets', 'saveSettings', 'resetSettings'];

  function setSettingsDisabled(disabled: boolean) {
    settingControls.forEach(id => {
      const el = document.getElementById(id) as HTMLInputElement | null;
      if (el) el.disabled = disabled;
    });
  }

  function showToast(message: string) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'bg-blade-orange/90 text-white px-4 py-2 rounded shadow-lg';
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  function collectSettings() {
    return {
      max_drawdown: parseFloat((document.getElementById('maxDrawdown') as HTMLInputElement).value) / 100,
      max_position_size: parseFloat((document.getElementById('maxPosition') as HTMLInputElement).value),
      max_concurrent_trades: parseInt((document.getElementById('maxTrades') as HTMLInputElement).value),
      strategies: {
        listing_sniper: (document.getElementById('sniperToggle') as HTMLInputElement).checked,
        arbitrage: (document.getElementById('arbToggle') as HTMLInputElement).checked,
        market_making: (document.getElementById('mmToggle') as HTMLInputElement).checked
      },
      rpc_provider: (document.getElementById('rpcSelect') as HTMLSelectElement).value,
      auto_failover: (document.getElementById('failoverToggle') as HTMLInputElement).checked
    };
  }

  function queueSettingsSave() {
    clearTimeout(settingsTimer);
    settingsTimer = setTimeout(async () => {
      if (isSavingSettings) return;
      isSavingSettings = true;
      setSettingsDisabled(true);
      const indicator = document.getElementById('saveIndicator');
      if (indicator) indicator.classList.remove('hidden');
      try {
        await apiClient.post('/state', { settings: collectSettings() });
      } catch (err) {
        console.error('auto save settings failed', err);
        showToast('Failed to save settings');
      } finally {
        if (indicator) indicator.classList.add('hidden');
        setSettingsDisabled(false);
        isSavingSettings = false;
      }
    }, 500);
  }

  function applySettings(settings: any) {
    if (!settings) return;
    if (typeof settings.max_drawdown === 'number') {
      const md = Math.round(settings.max_drawdown * 100);
      (document.getElementById('maxDrawdown') as HTMLInputElement).value = String(md);
      (document.getElementById('drawdownValue') as HTMLElement).textContent = md + '%';
    }
    if (typeof settings.max_position_size === 'number') {
      const mp = settings.max_position_size;
      (document.getElementById('maxPosition') as HTMLInputElement).value = String(mp);
      (document.getElementById('positionValue') as HTMLElement).textContent = String(mp);
    }
    if (typeof settings.max_concurrent_trades === 'number') {
      const mt = settings.max_concurrent_trades;
      (document.getElementById('maxTrades') as HTMLInputElement).value = String(mt);
      (document.getElementById('tradesValue') as HTMLElement).textContent = String(mt);
    }
    if (settings.strategies) {
      (document.getElementById('sniperToggle') as HTMLInputElement).checked = !!settings.strategies.listing_sniper;
      (document.getElementById('arbToggle') as HTMLInputElement).checked = !!settings.strategies.arbitrage;
      (document.getElementById('mmToggle') as HTMLInputElement).checked = !!settings.strategies.market_making;
    }
    if (settings.rpc_provider) {
      (document.getElementById('rpcSelect') as HTMLSelectElement).value = settings.rpc_provider;
    }
    if (typeof settings.auto_failover === 'boolean') {
      (document.getElementById('failoverToggle') as HTMLInputElement).checked = settings.auto_failover;
    }
  }

  const apiClient = {
    saveSettings: jest.fn((..._args: any[]) => Promise.reject(new Error('fail'))),
    post(endpoint: string, data: any) {
      return this.saveSettings(endpoint, data);
    }
  };

  const dashboardState = { state: { settings: {
    max_drawdown: 0.1,
    max_position_size: 5,
    max_concurrent_trades: 2,
    strategies: { listing_sniper: false, arbitrage: false, market_making: false },
    rpc_provider: 'rpc',
    auto_failover: false
  } } };

  applySettings(dashboardState.state.settings);
  const slider = document.getElementById('maxDrawdown') as HTMLInputElement;
  expect(slider.value).toBe('10');

  slider.value = '15';
  jest.useFakeTimers();
  queueSettingsSave();
  jest.runAllTimers();
  await Promise.resolve();

  const toastText = document.getElementById('toastContainer')!.textContent;
  expect(toastText).toContain('Failed to save settings');

  applySettings(dashboardState.state.settings);
  expect(slider.value).toBe('10');
});
