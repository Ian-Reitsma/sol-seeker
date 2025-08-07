import React, { useEffect, useState } from 'react';

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

const wsBase = () => {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}`;
};

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
    fetch('/orders', { headers: { 'X-API-Key': apiKey } })
      .then((r) => r.json())
      .then(setOrders)
      .catch(() => setOrders([]));

    const posWs = new WebSocket(`${wsBase()}/positions/ws`);
    posWs.onmessage = (ev) => setPositions(JSON.parse(ev.data));

    const orderWs = new WebSocket(`${wsBase()}/ws`);
    orderWs.onmessage = (ev) => {
      const order: Order = JSON.parse(ev.data);
      setOrders((o) => [...o, order]);
    };

    return () => {
      posWs.close();
      orderWs.close();
    };
  }, [apiKey]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey) return;
    const resp = await fetch('/orders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: JSON.stringify({ token, qty, side }),
    });
    if (resp.ok) {
      setToken('');
      setQty(0);
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

