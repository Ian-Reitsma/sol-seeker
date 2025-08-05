"""Posterior probability engine stubs."""

"""Lightweight online posterior models for rug and regime probabilities."""

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
    """Online logistic/softmax regression for posterior predictions.

    The engine keeps separate weight matrices for rug probability (binary
    logistic) and regime probabilities (3-class softmax).  Both models share the
    first ``n_features`` elements of the input feature vector.
    """

    def __init__(self, n_features: int = 10) -> None:
        self.n_features = n_features
        self.w_rug = np.zeros(n_features, dtype=np.float64)
        self.W_regime = np.zeros((3, n_features), dtype=np.float64)

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def predict(self, x: Sequence[float]) -> PosteriorOutput:
        """Return posterior probabilities for rug and market regimes."""

        feat = np.asarray(x[: self.n_features], dtype=np.float64)

        # Rug probability via logistic regression
        rug_logit = float(self.w_rug @ feat)
        rug = 1.0 / (1.0 + np.exp(-rug_logit))

        # Regime probabilities via multinomial logistic (softmax)
        logits = self.W_regime @ feat
        logits -= logits.max()  # numerical stability
        exps = np.exp(logits)
        probs = exps / exps.sum()

        return PosteriorOutput(rug=rug, trend=float(probs[0]), revert=float(probs[1]), chop=float(probs[2]))

    # ------------------------------------------------------------------
    # Online update
    # ------------------------------------------------------------------
    def update(self, x: Sequence[float], rug: int, regime: int, lr: float = 0.01) -> None:
        """Online gradient step for logistic and softmax regressions.

        Parameters
        ----------
        x:
            Feature vector.
        rug:
            Observed rug outcome (1 if rug pull occurred else 0).
        regime:
            Index of realised regime: 0=trend, 1=revert, 2=chop.
        lr:
            Learning rate for gradient descent.
        """

        feat = np.asarray(x[: self.n_features], dtype=np.float64)

        # Update rug logistic regression
        rug_pred = 1.0 / (1.0 + np.exp(-(self.w_rug @ feat)))
        rug_error = rug - rug_pred
        self.w_rug += lr * rug_error * feat

        # Update regime softmax regression
        logits = self.W_regime @ feat
        logits -= logits.max()
        exps = np.exp(logits)
        probs = exps / exps.sum()
        y = np.zeros(3)
        y[regime] = 1.0
        error = y - probs
        self.W_regime += lr * error[:, None] @ feat[None, :]

