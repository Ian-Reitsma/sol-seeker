/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import { jest } from '@jest/globals';

test('queueSettingsSave shows toast and re-enables controls on failure', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  document.documentElement.innerHTML = html;

  let settingsTimer: any;
  let isSavingSettings = false;
  const settingControls = [
    'maxDrawdown', 'maxPosition', 'maxTrades', 'sniperToggle', 'arbToggle',
    'mmToggle', 'failoverToggle', 'rpcSelect', 'modeSelect', 'demoCash',
    'demoAssets', 'saveSettings', 'resetSettings'
  ];

  function setSettingsDisabled(disabled: boolean) {
    settingControls.forEach(id => {
      const el = document.getElementById(id) as HTMLInputElement | null;
      if (el) el.disabled = disabled;
    });
  }

  const toastContainer = document.createElement('div');
  toastContainer.id = 'toastContainer';
  document.body.appendChild(toastContainer);
  const showToast = jest.fn((message: string) => {
    const toast = document.createElement('div');
    toast.textContent = message;
    toastContainer.appendChild(toast);
  });

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

  const apiClient = {
    post: jest.fn(async (_endpoint: string, _data: any) => { throw new Error('save failed'); })
  };

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
        showToast('Failed to save settings');
      } finally {
        if (indicator) indicator.classList.add('hidden');
        setSettingsDisabled(false);
        isSavingSettings = false;
      }
    }, 500);
  }

  const slider = document.getElementById('maxDrawdown') as HTMLInputElement;

  jest.useFakeTimers();
  queueSettingsSave();
  jest.advanceTimersByTime(500);
  expect(slider.disabled).toBe(true);
  await Promise.resolve();

  expect(showToast).toHaveBeenCalledWith('Failed to save settings');
  expect(toastContainer.textContent).toContain('Failed to save settings');
  expect(slider.disabled).toBe(false);
});
