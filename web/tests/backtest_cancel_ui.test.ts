/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import * as vm from 'vm';

test('backtest cancellation resets UI', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  const match = html.match(/let backtestEndpoint = null;\n\s*async function runBacktest\(\)[\s\S]*?document.getElementById\('runBacktest'\)\.addEventListener\('click', runBacktest\);/);
  expect(match).toBeTruthy();

  document.body.innerHTML = `
    <input id="btPeriod" value="1D"/>
    <input id="btCapital" value="1000"/>
    <input id="btStrategyMix" value="mix"/>
    <button id="runBacktest">RUN BACKTEST</button>
    <button id="cancelBacktest" class="hidden"></button>
    <div id="btProgress" class="hidden"><div id="btProgressBar"></div></div>
    <div id="backtestPnL"></div>
    <div id="backtestStats"></div>
  `;

  let sent: any = null;
  let disconnected: string | null = null;
  const callbacks: Record<string, (msg: any) => void> = {};

  const context: any = {
    document,
    localStorage: { getItem: () => null, setItem: () => {} },
    showToast: () => {},
    apiClient: {
      runBacktest: () => Promise.resolve({ id: 'job1' })
    },
    wsClient: {
      connect: (endpoint: string, cb: (msg: any) => void) => {
        callbacks[endpoint] = cb;
      },
      send: (_endpoint: string, msg: any) => { sent = msg; },
      disconnect: (endpoint: string) => { disconnected = endpoint; }
    },
    backtestEndpoint: null
  };

  vm.createContext(context);
  const scriptContent = match![0].replace(/document.getElementById\('runBacktest'\).*$/, '');
  const script = new vm.Script(scriptContent);
  script.runInContext(context);

  await context.runBacktest();
  const btn = document.getElementById('runBacktest') as HTMLButtonElement;
  const cancelBtn = document.getElementById('cancelBacktest') as HTMLButtonElement;
  const progress = document.getElementById('btProgress')!;
  const bar = document.getElementById('btProgressBar')!;

  expect(btn.disabled).toBe(true);
  expect(cancelBtn.classList.contains('hidden')).toBe(false);
  expect(progress.classList.contains('hidden')).toBe(false);

  cancelBtn.click();
  expect(sent).toEqual({ action: 'cancel' });

  callbacks['/backtest/ws/job1']({ progress: 100, cancelled: true });

  expect(disconnected).toBe('/backtest/ws/job1');
  expect(btn.disabled).toBe(false);
  expect(btn.textContent).toBe('RUN BACKTEST');
  expect(cancelBtn.classList.contains('hidden')).toBe(true);
  expect(progress.classList.contains('hidden')).toBe(true);
  expect(bar.style.width).toBe('0px');
});

