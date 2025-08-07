import React, { useEffect, useState } from 'react';

type Posterior = Record<string, number>;
interface Position {
  qty: number;
  px: number;
}
type Positions = Record<string, Position>;
interface Order {
  id: number;
  token: string;
  quantity: number;
  side: string;
  price: number;
  slippage: number;
  fee: number;
}
interface Risk {
  equity: number;
  unrealized: number;
  drawdown: number;
  realized: number;
  var: number;
  es: number;
  sharpe: number;
}

const Dashboard: React.FC = () => {
  const [features, setFeatures] = useState<number[]>([]);
  const [posterior, setPosterior] = useState<Posterior>({});
  const [positions, setPositions] = useState<Positions>({});
  const [orders, setOrders] = useState<Order[]>([]);
  const [risk, setRisk] = useState<Risk | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    async function init() {
      try {
        const resp = await fetch('/dashboard');
        const data = await resp.json();
        setFeatures(data.features || []);
        setPosterior(data.posterior || {});
        setPositions(data.positions || {});
        setOrders(data.orders || []);
        setRisk(data.risk || null);
      } catch (err) {
        console.error('snapshot fetch failed', err);
      }

      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      ws = new WebSocket(`${proto}://${window.location.host}/dashboard/ws`);
      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.features) setFeatures(msg.features);
          if (msg.posterior) setPosterior(msg.posterior);
          if (msg.positions) setPositions(msg.positions);
          if (msg.orders) setOrders(msg.orders);
          if (msg.risk) setRisk(msg.risk);
        } catch (err) {
          console.error('ws parse error', err);
        }
      };
    }
    init();
    return () => {
      if (ws) ws.close();
    };
  }, []);

  const renderSparkline = () => {
    if (!features.length) return null;
    const width = 200;
    const height = 50;
    const max = Math.max(...features);
    const min = Math.min(...features);
    const scaleY = (v: number) =>
      max - min === 0 ? height / 2 : height - ((v - min) / (max - min)) * height;
    const len = features.length;
    const points = features
      .map((v, i) => `${(i / (len - 1 || 1)) * width},${scaleY(v)}`)
      .join(' ');
    return (
      <svg width={width} height={height}>
        <polyline fill="none" stroke="steelblue" strokeWidth="1" points={points} />
      </svg>
    );
  };

  const renderPosteriorBars = () => {
    const entries = Object.entries(posterior);
    if (!entries.length) return null;
    return (
      <div style={{ display: 'flex', alignItems: 'flex-end', height: 100 }}>
        {entries.map(([k, v]) => (
          <div key={k} style={{ flex: 1, textAlign: 'center', margin: '0 4px' }}>
            <div style={{ background: 'teal', width: '100%', height: `${v * 100}%` }} />
            <span>
              {k} {(v * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div>
      <h1>Dashboard</h1>
      <section>
        <h2>Features</h2>
        {renderSparkline()}
      </section>
      <section>
        <h2>Posterior</h2>
        {renderPosteriorBars()}
      </section>
      <section>
        <h2>Risk</h2>
        {risk && (
          <ul>
            <li>Equity: {risk.equity}</li>
            <li>Unrealized: {risk.unrealized}</li>
            <li>Realized: {risk.realized}</li>
            <li>VaR: {risk.var}</li>
            <li>ES: {risk.es}</li>
            <li>Sharpe: {risk.sharpe}</li>
            <li>Drawdown: {risk.drawdown}</li>
          </ul>
        )}
      </section>
      <section>
        <h2>Positions</h2>
        <table>
          <thead>
            <tr>
              <th>Token</th>
              <th>Qty</th>
              <th>Px</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(positions).map(([token, p]) => (
              <tr key={token}>
                <td>{token}</td>
                <td>{p.qty}</td>
                <td>{p.px}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section>
        <h2>Orders</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Token</th>
              <th>Qty</th>
              <th>Side</th>
              <th>Price</th>
              <th>Slippage</th>
              <th>Fee</th>
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
                <td>{o.slippage}</td>
                <td>{o.fee}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
};

export default Dashboard;

