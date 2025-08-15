/* eslint-disable @typescript-eslint/no-explicit-any */
import { wsClient, checkWsHeartbeat } from '../src/wsClient';

test('queued messages replay after reconnect', () => {
  wsClient.connections.clear();
  (wsClient as any).queues.clear();
  const sent: string[] = [];
  (global as any).WebSocket = function() {
    const ws: any = { readyState: 3, send: (msg: string) => sent.push(msg) };
    return ws;
  } as any;
  (global as any).WebSocket.OPEN = 1;

  wsClient.connect('/test', () => {});
  wsClient.send('/test', { a: 1 });
  expect(sent).toHaveLength(0);

  wsClient.connections.set('/test', { readyState: 1, send: (msg: string) => sent.push(msg) } as any);
  checkWsHeartbeat();

  expect(sent).toEqual([JSON.stringify({ a: 1 })]);
});
