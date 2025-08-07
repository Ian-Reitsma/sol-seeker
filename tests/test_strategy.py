from solbot.engine import Strategy, RiskManager, PosteriorOutput


def test_strategy_positive_edge_trades():
    risk = RiskManager()
    strat = Strategy(risk)
    post = PosteriorOutput(rug=0.0, trend=0.6, revert=0.3, chop=0.1)
    sig = strat.evaluate(post, fee=0.01, equity=1000.0, volatility=0.1)
    assert sig is not None and sig.qty > 0


def test_strategy_fee_blocks_trade():
    risk = RiskManager()
    strat = Strategy(risk)
    post = PosteriorOutput(rug=0.0, trend=0.6, revert=0.3, chop=0.1)
    sig = strat.evaluate(post, fee=0.5, equity=1000.0, volatility=0.1)
    assert sig is None


def test_strategy_stop_loss_take_profit():
    risk = RiskManager()
    strat = Strategy(risk, stop_loss=0.1, take_profit=0.2)
    risk.add_position("SOL", 1.0, 100.0)
    strat.check_exit("SOL", 80.0)
    assert "SOL" not in risk.positions
    risk.add_position("SOL", 1.0, 100.0)
    strat.check_exit("SOL", 130.0)
    assert "SOL" not in risk.positions


def _mk_swap(ts: int, amount_in: float, amount_out: float, fee: float, volume: float):
    from solbot.schema import Event, EventKind

    return Event(ts=ts, kind=EventKind.SWAP, amount_in=amount_in, amount_out=amount_out, fee=fee, volume=volume)


def run_backtest(fee_threshold: float) -> float:
    from solbot.engine.features import PyFeatureEngine
    from solbot.engine.posterior import PosteriorEngine

    events = [
        _mk_swap(1, 100.0, 99.0, 0.5, 20.0),
        _mk_swap(2, 99.0, 101.0, 0.01, 200.0),
        _mk_swap(3, 101.0, 106.0, 0.01, 200.0),
    ]
    prices = [e.amount_out / e.amount_in for e in events]
    fe = PyFeatureEngine()
    posterior = PosteriorEngine(n_features=11)
    posterior.W_regime[0, 10] = 1.0
    pnl = 0.0
    for i, ev in enumerate(events[:-1], start=1):
        vec = fe.update(ev, slot=i)
        action = posterior.decide_action(vec, fee_thr=fee_threshold)
        price = prices[i - 1]
        next_price = prices[i]
        next_fee = events[i].fee
        if action == "enter":
            pnl += next_price - price - ev.fee - next_fee
    return pnl


def test_backtest_fee_volume_features():
    base_pnl = run_backtest(fee_threshold=100.0)
    improved_pnl = run_backtest(fee_threshold=10.0)
    assert improved_pnl > base_pnl

