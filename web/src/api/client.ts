import type { paths } from './schema';
import API_BASE_URL from '../api';

const API_BASE = API_BASE_URL;

export type LicenseResponse = paths['/license']['get']['responses']['200']['content']['application/json'];
export type DashboardResponse = paths['/dashboard']['get']['responses']['200']['content']['application/json'];
export type PositionsResponse = paths['/positions']['get']['responses']['200']['content']['application/json'];

async function handleResponse<T>(res: Response): Promise<T> {
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

function httpToWs(url: string): string {
  return url.replace(/^http/, 'ws');
}

export function dashboardWs(): WebSocket {
  return new WebSocket(`${httpToWs(API_BASE)}/dashboard/ws`);
}

export function positionsWs(): WebSocket {
  return new WebSocket(`${httpToWs(API_BASE)}/positions/ws`);
}
