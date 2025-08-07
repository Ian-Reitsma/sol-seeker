import { useEffect, useState } from 'react';
import { getDashboard, dashboardWs } from '../api/client';
import type { DashboardResponse } from '../api/client';

export function useDashboard(apiKey: string) {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    getDashboard().then(setData).catch(setError);
    ws = dashboardWs(apiKey);
    ws.onmessage = (ev) => {
      try {
        setData(JSON.parse(ev.data));
      } catch {
        // ignore parse errors
      }
    };
    ws.onerror = () => setError(new Error('WebSocket error'));
    return () => {
      ws?.close();
    };
  }, [apiKey]);

  return { data, error };
}
