import React, { useEffect, useState } from 'react';
import {
  getOrders,
  getPositions,
  placeOrder,
  dashboardWs,
  positionsWs,
} from '../api/client';

interface Order {
  id: number;
  token: string;
  quantity: number;
  side: string;
  price: number;
}

interface Position {
  token: string;
  qty: number;
  cost: number;
}

const Trading: React.FC = () => {
  const [apiKey, setApiKey] = useState<string>(() => localStorage.getItem('apiKey') || '');
  const [token, setToken] = useState('');
  const [qty, setQty] = useState<number>(0);
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [orders, setOrders] = useState<Order[]>([]);
  const [positions, setPositions] = useState<Record<string, Position>>({});

  useEffect(() => {
    localStorage.setItem('apiKey', apiKey);
  }, [apiKey]);

  useEffect(() => {
    if (!apiKey) return;
    getOrders(apiKey)
      .then((o) => setOrders(o as unknown as Order[]))
      .catch(() => setOrders([]));
    getPositions(apiKey)
      .then(setPositions)
      .catch(() => setPositions({}));

    const posWs = positionsWs(apiKey);
    posWs.onmessage = (ev) => setPositions(JSON.parse(ev.data));

    const dashWs = dashboardWs(apiKey);
    dashWs.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.orders) setOrders(msg.orders);
      } catch {
        // ignore parse errors
      }
    };

    return () => {
      posWs.close();
      dashWs.close();
    };
  }, [apiKey]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey) return;
    try {
      await placeOrder(apiKey, { token, qty, side });
      setToken('');
      setQty(0);
    } catch {
      // ignore errors
    }
  };

  return (
    <div>
      <h1>Trading</h1>
      <label>
        API Key:
        <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
      </label>
      <form onSubmit={submit}>
        <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="Token" />
        <input
          type="number"
          value={qty}
          onChange={(e) => setQty(parseFloat(e.target.value))}
          placeholder="Quantity"
        />
        <select value={side} onChange={(e) => setSide(e.target.value as 'buy' | 'sell')}>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
        <button type="submit">Place Order</button>
      </form>
      <h2>Orders</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Token</th>
            <th>Qty</th>
            <th>Side</th>
            <th>Price</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id}>
              <td>{o.id}</td>
              <td>{o.token}</td>
              <td>{o.quantity}</td>
              <td>{o.side}</td>
              <td>{o.price}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2>Positions</h2>
      <table>
        <thead>
          <tr>
            <th>Token</th>
            <th>Qty</th>
            <th>Cost</th>
          </tr>
        </thead>
        <tbody>
          {Object.values(positions).map((p) => (
            <tr key={p.token}>
              <td>{p.token}</td>
              <td>{p.qty}</td>
              <td>{p.cost}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Trading;

