/**
 * @jest-environment jsdom
 */
import { readFileSync } from 'fs';
import * as path from 'path';
import * as vm from 'vm';

test('backtest cancellation resets UI', async () => {
  const html = readFileSync(path.join(__dirname, '../public/dashboard.html'), 'utf8');
  const match = html.match(/async function runBacktest\(\)[\s\S]*?cancelBtn\.onclick = \(\) => ws\.send\(JSON\.stringify\({ action: 'cancel' }\)\);[\s\S]*?document.getElementById\('runBacktest'\)\.addEventListener\('click', runBacktest\);/);
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
  let wsInstance: any = null;

    const context: any = {
      document,
      localStorage: { getItem: () => null, setItem: () => {} },
      showToast: () => {},
      apiClient: {
        runBacktest: () => Promise.resolve({ id: 'job1' }),
        getWebSocketURL: (ep: string) => ep,
      },
      WebSocket: class {
        url: string;
        onmessage: ((ev: any) => void) | null = null;
        onclose: (() => void) | null = null;
        constructor(url: string) { this.url = url; wsInstance = this; }
        send(msg: string) { sent = JSON.parse(msg); }
        close() { if (this.onclose) this.onclose(); }
      },
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

  wsInstance.onmessage!({ data: JSON.stringify({ progress: 100, cancelled: true }) });
  expect(btn.disabled).toBe(false);
  expect(btn.textContent).toBe('RUN BACKTEST');
  expect(cancelBtn.classList.contains('hidden')).toBe(true);
  expect(progress.classList.contains('hidden')).toBe(true);
  expect(bar.style.width).toBe('0px');
});

