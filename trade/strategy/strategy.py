from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

Signal = Literal["SELL", "HOLD", "BUY"]


class Strategy:
    """
    Window-based dummy strategy that gives random signals. This is just for making sure the code runs in the beginning. 
    You may need to replace this entire Strategy class for actual strategies.
    
    Contract:
      - Backtester supplies a window DataFrame each step.
      - Strategy returns ONE signal for the last timestep of that window.
    """

    _FIXED_SEED = 1234  # internal, invisible to main

    def __init__(self, args) -> None:
        self.num_past_timesteps = int(args.num_past_timesteps)

        self.prob_sell = 0.10
        self.prob_hold = 0.80
        self.prob_buy = 0.10

        probs = np.array(
            [self.prob_sell, self.prob_hold, self.prob_buy],
            dtype=float,
        )
        if (probs < 0).any() or probs.sum() <= 0:
            raise ValueError("probabilities must be non-negative and sum to > 0")

        self.probs = probs / probs.sum()

        # Internal, deterministic RNG
        self.rng = np.random.default_rng(self._FIXED_SEED)

    def per_step(self, window: pd.DataFrame) -> Signal:
        """
        Return a signal for the *last* row of `window`.
        """
        if len(window) < self.num_past_timesteps:
            raise ValueError(
                f"window must have at least {self.num_past_timesteps} rows; got {len(window)}"
            )

        return self.rng.choice(["SELL", "HOLD", "BUY"], p=self.probs)
