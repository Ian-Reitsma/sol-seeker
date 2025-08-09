/* eslint-disable @typescript-eslint/no-explicit-any */
process.env.VITE_API_URL = 'http://api.test';
import {
  getLicense,
  getDashboard,
  getPositions,
  getOrders,
  placeOrder,
  dashboardWs,
  positionsWs,
  ordersWs,
} from '../src/api/client';

describe('api client', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  test('getLicense fetches license', async () => {
    (fetch as jest.Mock).mockResolvedValue({ ok: true, json: () => Promise.resolve({ wallet: 'w', mode: 'full' }) });
    const data = await getLicense();
    expect(fetch).toHaveBeenCalledWith('http://api.test/license');
    expect(data.wallet).toBe('w');
  });

  test('getDashboard fetches dashboard', async () => {
    (fetch as jest.Mock).mockResolvedValue({ ok: true, json: () => Promise.resolve({ features: [], posterior: null, positions: {}, orders: [{ id: 1, token: 'SOL', quantity: 1, side: 'buy', price: 10, slippage: 0.1, fee: 0.01, timestamp: 0, status: 'closed' }], risk: { equity: 0, unrealized: 0, drawdown: 0, realized: 0, var: 0, es: 0, sharpe: 0 }, timestamp: 0 }) });
    const data = await getDashboard();
    expect(fetch).toHaveBeenCalledWith('http://api.test/dashboard');
    expect(data.risk.es).toBe(0);
    expect(data.orders[0].slippage).toBe(0.1);
  });

  test('getPositions includes api key', async () => {
    (fetch as jest.Mock).mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    await getPositions('secret');
    expect(fetch).toHaveBeenCalledWith('http://api.test/positions', { headers: { 'X-API-Key': 'secret' } });
  });

  test('getOrders includes api key', async () => {
    (fetch as jest.Mock).mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    await getOrders('k');
    expect(fetch).toHaveBeenCalledWith('http://api.test/orders', { headers: { 'X-API-Key': 'k' } });
  });

  test('placeOrder posts with api key', async () => {
    (fetch as jest.Mock).mockResolvedValue({ ok: true, json: () => Promise.resolve({ id: 1, token: 'SOL', quantity: 1, side: 'buy', price: 10, slippage: 0.1, fee: 0.01, timestamp: 0, status: 'closed' }) });
    const resp = await placeOrder('k', { token: 'SOL', qty: 1, side: 'buy' });
    expect(fetch).toHaveBeenCalledWith('http://api.test/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': 'k' },
      body: JSON.stringify({ token: 'SOL', qty: 1, side: 'buy' }),
    });
    expect(resp.slippage).toBe(0.1);
    expect(resp.status).toBe('closed');
  });

  test('dashboardWs connects to websocket with api key', () => {
    const mockWs = {} as any;
    (global as any).WebSocket = jest.fn().mockReturnValue(mockWs);
    const ws = dashboardWs('secret');
    expect((global as any).WebSocket).toHaveBeenCalledWith('ws://api.test/dashboard/ws?key=secret');
    expect(ws).toBe(mockWs);
  });

  test('positionsWs connects to websocket with api key', () => {
    const mockWs = {} as any;
    (global as any).WebSocket = jest.fn().mockReturnValue(mockWs);
    const ws = positionsWs('secret');
    expect((global as any).WebSocket).toHaveBeenCalledWith('ws://api.test/positions/ws?key=secret');
    expect(ws).toBe(mockWs);
  });

  test('ordersWs connects to websocket with api key', () => {
    const mockWs = {} as any;
    (global as any).WebSocket = jest.fn().mockReturnValue(mockWs);
    const ws = ordersWs('secret');
    expect((global as any).WebSocket).toHaveBeenCalledWith('ws://api.test/ws?key=secret');
    expect(ws).toBe(mockWs);
  });
});
