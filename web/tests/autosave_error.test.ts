/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import * as vm from 'vm';

test('queueSettingsSave shows toast and re-enables controls on failure', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  const match = html.match(/let settingsTimer[\s\S]*?const sliders/);
  expect(match).toBeTruthy();
  const scriptContent = match![0].replace(/const sliders[\s\S]*$/, '');

  document.body.innerHTML = `
    <input id="maxDrawdown" value="10" />
    <div id="saveIndicator" class="hidden"></div>
    <div id="toastContainer"></div>
  `;

  const apiClient = {
    post: jest.fn((_e: string, _d: any) => Promise.reject(new Error('fail')))
  };

  jest.useFakeTimers();
  const context: any = {
    document,
    apiClient,
    localStorage: { getItem: () => null, setItem: () => {} },
    setTimeout,
    clearTimeout
  };
  vm.createContext(context);
  const script = new vm.Script(scriptContent);
  script.runInContext(context);
  context.showToast = jest.fn((msg: string) => {
    const toast = document.createElement('div');
    toast.textContent = msg;
    document.getElementById('toastContainer')!.appendChild(toast);
  });
  context.collectSettings = () => ({ });

  const slider = document.getElementById('maxDrawdown') as HTMLInputElement;
  const indicator = document.getElementById('saveIndicator')!;

  context.queueSettingsSave();
  await jest.runAllTimersAsync();
  await Promise.resolve();
  expect(apiClient.post).toHaveBeenCalledWith('/state', { settings: expect.any(Object) });
  expect(context.showToast).toHaveBeenCalledWith('Failed to save settings');
  expect(document.getElementById('toastContainer')!.textContent).toContain('Failed to save settings');
  expect(indicator.classList.contains('hidden')).toBe(true);
  expect(slider.disabled).toBe(false);
});
