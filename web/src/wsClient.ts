export class SolSeekerWebSocket {
  connections: Map<string, WebSocket> = new Map();
  reconnectAttempts: Map<string, number> = new Map();
  maxReconnectAttempts = 5;
  queues: Map<string, any[]> = new Map();

  connect(endpoint: string, onMessage: (data: any) => void, onError: ((err: any) => void) | null = null): void {
    try {
      const ws = new WebSocket(endpoint);
      ws.onopen = () => {
        this.reconnectAttempts.set(endpoint, 0);
      };
      ws.onmessage = (ev: any) => {
        try {
          onMessage(JSON.parse(ev.data));
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

  handleReconnect(endpoint: string, onMessage: (d: any) => void, onError: ((err: any) => void) | null): void {
    const attempts = this.reconnectAttempts.get(endpoint) || 0;
    if (attempts < this.maxReconnectAttempts) {
      const next = attempts + 1;
      this.reconnectAttempts.set(endpoint, next);
      const delay = Math.pow(2, next) * 1000;
      setTimeout(() => this.connect(endpoint, onMessage, onError), delay);
    } else {
      if (onError) onError(new Error('max reconnect attempts reached'));
    }
  }

  send(endpoint: string, data: any): void {
    const ws = this.connections.get(endpoint);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    } else {
      const q = this.queues.get(endpoint) || [];
      q.push(data);
      this.queues.set(endpoint, q);
    }
  }

  flush(endpoint: string): void {
    const ws = this.connections.get(endpoint);
    const q = this.queues.get(endpoint);
    if (ws && ws.readyState === WebSocket.OPEN && q && q.length) {
      while (q.length) {
        ws.send(JSON.stringify(q.shift()));
      }
    }
  }

  hasPending(): boolean {
    for (const q of this.queues.values()) {
      if (q.length) return true;
    }
    return false;
  }
}

export const wsClient = new SolSeekerWebSocket();
export let wsHeartbeatTs = 0;

export function checkWsHeartbeat(): void {
  wsClient.connections.forEach((_, ep) => wsClient.flush(ep));
}
