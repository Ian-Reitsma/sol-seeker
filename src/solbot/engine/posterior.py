"""Posterior probability engine stubs."""

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass
class PosteriorOutput:
    rug: float
    trend: float
    revert: float
    chop: float


class PosteriorEngine:
    """Minimal posterior engine with mock predictions."""

    def __init__(self, n_features: int = 10) -> None:
        self.n_features = n_features
        self.coefs = np.zeros(n_features)

    def predict(self, x: Sequence[float]) -> PosteriorOutput:
        """Return dummy probabilities based on a linear score."""
        score = float(np.dot(self.coefs, x[: self.n_features]))
        # simple softmax over three regimes
        logits = np.array([score, -score, 0.0])
        exps = np.exp(logits)
        probs = exps / exps.sum()
        return PosteriorOutput(rug=0.01, trend=probs[0], revert=probs[1], chop=probs[2])

    def update(self, x: Sequence[float], y: float, lr: float = 0.01) -> None:
        """Perform a simple gradient step on the logistic regression stub."""
        pred = self.predict(x)
        error = y - pred.trend
        self.coefs += lr * error * np.array(x[: self.n_features])
