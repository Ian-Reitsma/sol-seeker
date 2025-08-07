/* eslint-disable @typescript-eslint/no-explicit-any */
process.env.VITE_API_URL = 'http://api.test';
import { getLicense, getDashboard, getPositions, dashboardWs, positionsWs } from '../src/api/client';

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
    (fetch as jest.Mock).mockResolvedValue({ ok: true, json: () => Promise.resolve({ features: [], posterior: null, positions: {}, orders: [], risk: { equity: 0, unrealized: 0, drawdown: 0 }, timestamp: 0 }) });
    const data = await getDashboard();
    expect(fetch).toHaveBeenCalledWith('http://api.test/dashboard');
    expect(data.risk).toBeDefined();
  });

  test('getPositions includes api key', async () => {
    (fetch as jest.Mock).mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    await getPositions('secret');
    expect(fetch).toHaveBeenCalledWith('http://api.test/positions', { headers: { 'X-API-Key': 'secret' } });
  });

  test('dashboardWs connects to websocket', () => {
    const mockWs = {} as any;
    (global as any).WebSocket = jest.fn().mockReturnValue(mockWs);
    const ws = dashboardWs();
    expect((global as any).WebSocket).toHaveBeenCalledWith('ws://api.test/dashboard/ws');
    expect(ws).toBe(mockWs);
  });

  test('positionsWs connects to websocket', () => {
    const mockWs = {} as any;
    (global as any).WebSocket = jest.fn().mockReturnValue(mockWs);
    const ws = positionsWs();
    expect((global as any).WebSocket).toHaveBeenCalledWith('ws://api.test/positions/ws');
    expect(ws).toBe(mockWs);
  });
});
