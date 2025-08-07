import { useEffect, useState } from 'react';
import { getPositions, positionsWs } from '../api/client';
import type { PositionsResponse } from '../api/client';

export function usePositions(apiKey: string) {
  const [data, setData] = useState<PositionsResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    getPositions(apiKey).then(setData).catch(setError);
    ws = positionsWs();
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
