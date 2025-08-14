/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest } from '@jest/globals';

let showToast: (msg: string) => void;

class SolSeekerWebSocket {
  connections = new Map<string, any>();
  reconnectAttempts = new Map<string, number>();
  maxReconnectAttempts = 2;

  connect(
    endpoint: string,
    onMessage: (data: any) => void,
    onError: ((err: any) => void) | null = null
  ): void {
    try {
      const ws: any = new WebSocket(endpoint);
      ws.onopen = () => {
        this.reconnectAttempts.set(endpoint, 0);
      };
      ws.onmessage = (event: any) => {
        try {
          const data = JSON.parse(event.data);
          onMessage(data);
        } catch {
          // ignore parse errors in tests
        }
      };
      ws.onclose = () => {
        this.handleReconnect(endpoint, onMessage, onError);
      };
      ws.onerror = (err: any) => {
        if (onError) onError(err);
      };
      this.connections.set(endpoint, ws);
    } catch (err) {
      if (onError) onError(err);
    }
  }

  handleReconnect(
    endpoint: string,
    onMessage: (d: any) => void,
    onError: ((err: any) => void) | null
  ): void {
    const attempts = this.reconnectAttempts.get(endpoint) || 0;
    if (attempts < this.maxReconnectAttempts) {
      const next = attempts + 1;
      this.reconnectAttempts.set(endpoint, next);
      const delay = Math.pow(2, next) * 1000;
      setTimeout(() => this.connect(endpoint, onMessage, onError), delay);
    } else {
      showToast(`Unable to reconnect to ${endpoint}`);
      if (onError) onError(new Error('max reconnect attempts reached'));
    }
  }
}

test('reconnection failure surfaces toast after max attempts', () => {
  jest.useFakeTimers();
  const client = new SolSeekerWebSocket();
  (global as any).showToast = jest.fn();
  showToast = (global as any).showToast;

  // always fail to connect and trigger another reconnect attempt
  client.connect = jest.fn((endpoint: string, onMsg: any, onErr: any) => {
    if (onErr) onErr(new Error('connect failed'));
    client.handleReconnect(endpoint, onMsg, onErr);
  });

  client.connect('/test', () => {}, () => {});
  jest.runAllTimers();

  expect((global as any).showToast).toHaveBeenCalledWith(
    'Unable to reconnect to /test'
  );
  expect((client.connect as jest.Mock).mock.calls.length).toBe(
    client.maxReconnectAttempts + 1
  );
});
