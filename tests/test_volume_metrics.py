import numpy as np

import solbot.solana.volume as volume
from solbot.engine.features import PyFeatureEngine
from solbot.engine.strategy import VolumeAwareStrategy
from solbot.engine.posterior import PosteriorEngine


def test_fetch_volume_and_fees(monkeypatch):
    class DummyClient:
        def __init__(self, url):
            self.url = url

        def get_recent_performance_samples(self, window):
            return {
                "result": [
                    {"numTransactions": 30, "samplePeriodSecs": 15},
                    {"numTransactions": 20, "samplePeriodSecs": 5},
                ]
            }

        def get_recent_prioritization_fees(self):
            return {
                "result": [
                    {"prioritizationFee": 1},
                    {"prioritizationFee": 3},
                    {"prioritizationFee": 2},
                ]
            }

    monkeypatch.setattr(volume, "Client", DummyClient)
    tps, fee = volume.fetch_volume_and_fees("http://dummy")
    assert tps == 50 / 20
    assert fee == 2.0


def test_feature_update_with_network_metrics():
    fe = PyFeatureEngine()
    fe.update_network_metrics(2.0, 5.0, slot=1)
    assert fe.curr[6] == 2.0
    assert fe.curr[7] == 5.0


def test_volume_aware_strategy():
    strat = VolumeAwareStrategy(PosteriorEngine(n_features=11))
    high = np.zeros(11, dtype=float)
    high[6] = 5.0
    high[7] = 5.0
    low = np.zeros(11, dtype=float)
    neg = np.zeros(11, dtype=float)
    neg[6] = -5.0
    neg[7] = -5.0

    assert strat.should_enter(high)
    assert not strat.should_enter(low)
    assert strat.should_exit(neg)

