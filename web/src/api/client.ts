import type { paths } from './schema';
import API_BASE_URL from '../api';

const API_BASE = API_BASE_URL;

function promptApiKey(): void {
  const key = window.prompt('API key required. Please enter your API key:');
  if (key) {
    localStorage.setItem('apiKey', key);
    window.dispatchEvent(new CustomEvent('apiKey', { detail: key }));
  }
}

export type LicenseResponse = paths['/license']['get']['responses']['200']['content']['application/json'];
export type PositionsResponse = paths['/positions']['get']['responses']['200']['content']['application/json'];
export type OrderRequest = paths['/orders']['post']['requestBody']['content']['application/json'];

export interface OrderResponse {
  id: number;
  token: string;
  quantity: number;
  side: string;
  price: number;
  slippage: number;
  fee: number;
  timestamp: number;
  status: string;
}

export type OrdersResponse = OrderResponse[];

export interface RiskMetrics {
  equity: number;
  unrealized: number;
  drawdown: number;
  realized: number;
  var: number;
  es: number;
  sharpe: number;
}

export interface DashboardResponse {
  features: number[] | null;
  posterior: Record<string, number> | null;
  positions: Record<string, unknown>;
  orders: OrderResponse[];
  risk: RiskMetrics;
  timestamp: number;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    promptApiKey();
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function getLicense(): Promise<LicenseResponse> {
  const res = await fetch(`${API_BASE}/license`);
  return handleResponse<LicenseResponse>(res);
}

export async function getDashboard(): Promise<DashboardResponse> {
  const res = await fetch(`${API_BASE}/dashboard`);
  return handleResponse<DashboardResponse>(res);
}

export async function getPositions(apiKey: string): Promise<PositionsResponse> {
  const res = await fetch(`${API_BASE}/positions`, {
    headers: { 'X-API-Key': apiKey }
  });
  return handleResponse<PositionsResponse>(res);
}

export async function getOrders(apiKey: string, status?: string): Promise<OrdersResponse> {
  const url = status ? `${API_BASE}/orders?status=${encodeURIComponent(status)}` : `${API_BASE}/orders`;
  const res = await fetch(url, {
    headers: { 'X-API-Key': apiKey }
  });
  return handleResponse<OrdersResponse>(res);
}

export async function placeOrder(apiKey: string, order: OrderRequest): Promise<OrderResponse> {
  const res = await fetch(`${API_BASE}/orders`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey
    },
    body: JSON.stringify(order)
  });
  return handleResponse<OrderResponse>(res);
}

function httpToWs(url: string): string {
  return url.replace(/^http/, 'ws');
}

function createWs(path: string, apiKey: string): WebSocket {
  const ws = new WebSocket(
    `${httpToWs(API_BASE)}${path}?key=${encodeURIComponent(apiKey)}`
  );
  ws.onclose = (ev) => {
    if (ev.code === 1008) {
      promptApiKey();
    }
  };
  return ws;
}

export function dashboardWs(apiKey: string): WebSocket {
  return createWs('/dashboard/ws', apiKey);
}

export function positionsWs(apiKey: string): WebSocket {
  return createWs('/positions/ws', apiKey);
}

export function ordersWs(apiKey: string): WebSocket {
  return createWs('/orders/ws', apiKey);
}
