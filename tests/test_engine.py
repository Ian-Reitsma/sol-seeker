from solbot.engine import PosteriorEngine


def test_posterior_predict_shape():
    engine = PosteriorEngine(n_features=3)
    x = [1.0, 2.0, 3.0]
    out = engine.predict(x)
    assert 0 <= out.trend <= 1
    assert 0 <= out.revert <= 1
    assert 0 <= out.chop <= 1
    assert abs(out.trend + out.revert + out.chop - 1) < 1e-6
    assert 0 <= out.rug <= 1


def test_posterior_update_learning():
    eng = PosteriorEngine(n_features=2)
    x = [1.0, 0.0]
    before = eng.predict(x).rug
    eng.update(x, rug=1, regime=0)
    after = eng.predict(x).rug
    assert after > before

from solbot.engine import RiskManager


def test_risk_manager_drawdown():
    rm = RiskManager()
    rm.update_equity(100)
    rm.update_equity(80)
    assert rm.drawdown == 0.2
