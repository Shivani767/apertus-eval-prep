"""Adaptive evaluation (Phase 9).

Framework for choosing which experiment to run next under a budget, instead of
exhaustively running N models x N prompts x N backends x ...

    initial experiments -> estimate uncertainty -> select next -> run ->
    update -> stop when confidence sufficient or budget exhausted.

All inputs are already-measured scores (accuracy + n). `compare_strategies`
only ever uses a provided known-score table (synthetic in tests, real committed
scores when the caller supplies them). We do NOT claim the adaptive approach is
better than any baseline until compared empirically — `compare_strategies`
exists precisely to make that comparison.

Strategies (documented operationalizations):
- random: uniform draw among unmeasured candidates (baseline).
- uncertainty: candidates of models involved in the most-uncertain ranking
  pair (closest mean scores); unmeasured models are the most uncertain of all.
- max_disagreement: candidate of the model with the highest measured score
  variance (most volatile model ~ most informative next run).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from statistics import mean, median, pstdev
from typing import Any, Sequence

from apertus_eval_prep.stats import cis_overlap, wilson_interval

STRATEGIES = ("random", "uncertainty", "max_disagreement")


@dataclass
class AdaptiveState:
    """Mutable state: what has been measured and how much budget is left."""

    budget: int
    candidates: list[dict[str, Any]] = field(default_factory=list)
    measured: dict[str, float] = field(default_factory=dict)
    n: dict[str, int] = field(default_factory=dict)
    seed: int = 0
    strategy: str = "uncertainty"

    def key(self, candidate: dict[str, Any]) -> str:
        return f"{candidate['model_id']}::{candidate['config_key']}"

    def budget_left(self) -> int:
        return self.budget - len(self.measured)

    def unmeasured(self) -> list[dict[str, Any]]:
        return [c for c in self.candidates if self.key(c) not in self.measured]

    def scores_of(self, model_id: str) -> list[float]:
        return [s for cid, s in self.measured.items()
                if cid.startswith(f"{model_id}::")]

    def model_mean(self, model_id: str) -> float | None:
        s = self.scores_of(model_id)
        return mean(s) if s else None

    def model_ci(self, model_id: str) -> tuple[float, float] | None:
        """Wilson CI on the model's mean score using median n of its configs."""
        s = self.scores_of(model_id)
        if not s:
            return None
        ns = [self.n[k] for k in self.measured if k.startswith(f"{model_id}::")
              and self.n.get(k)]
        n_use = int(median(ns)) if ns else 100
        k = int(round(mean(s) * n_use))
        return wilson_interval(k, n_use)

    def most_uncertain_pair(self) -> tuple[str | None, str | None]:
        """(a, b) with the closest mean scores among MEASURED models."""
        models = sorted({c["model_id"] for c in self.candidates})
        meas = [(m, mean(self.scores_of(m))) for m in models if self.scores_of(m)]
        if len(meas) < 2:
            return None, None
        best_d, best = None, (meas[0][0], meas[1][0])
        for i in range(len(meas)):
            for j in range(i + 1, len(meas)):
                d = abs(meas[i][1] - meas[j][1])
                if best_d is None or d < best_d:
                    best_d, best = d, (meas[i][0], meas[j][0])
        return best


class AdaptiveEvaluator:
    """Select-and-observe loop owner.

    ev = AdaptiveEvaluator(candidates, budget=8, strategy="uncertainty", seed=0)
    while (cand := ev.select_next()) is not None:
        score = run(cand)          # real harness; tests use a known table
        ev.observe(cand, score, n=800)
    """

    def __init__(
        self,
        candidates: Sequence[dict[str, Any]],
        budget: int,
        strategy: str = "uncertainty",
        seed: int = 0,
    ):
        if budget < 1:
            raise ValueError("budget must be >= 1")
        if strategy not in STRATEGIES:
            raise ValueError(f"strategy {strategy!r} not in {list(STRATEGIES)}")
        if budget > len(candidates):
            raise ValueError("budget must be <= number of candidates")
        self.state = AdaptiveState(
            budget=budget, candidates=[dict(c) for c in candidates],
            seed=seed, strategy=strategy,
        )
        self._rng = random.Random(seed)

    def select_next(self) -> dict[str, Any] | None:
        """Next candidate per strategy, or None when budget exhausted / all done."""
        unmeas = self.state.unmeasured()
        if not unmeas or self.state.budget_left() <= 0:
            return None
        strat = self.state.strategy
        if strat == "random":
            return self._rng.choice(unmeas)
        if strat == "uncertainty":
            return self._uncertainty(unmeas)
        if strat == "max_disagreement":
            return self._max_disagreement(unmeas)
        raise AssertionError(strat)

    def _uncertainty(self, unmeas: list[dict[str, Any]]) -> dict[str, Any]:
        unchosen = sorted({c["model_id"] for c in self.state.candidates
                           if not self.state.scores_of(c["model_id"])})
        if unchosen and any(c["model_id"] in unchosen for c in unmeas):
            return self._rng.choice(
                [c for c in unmeas if c["model_id"] in unchosen])
        pair = self.state.most_uncertain_pair()
        pool = unmeas
        if pair[0] is not None:
            pool = [c for c in unmeas if c["model_id"] in pair]
        return self._rng.choice(pool)

    def _max_disagreement(self, unmeas: list[dict[str, Any]]) -> dict[str, Any]:
        best_model, best_var = None, -1.0
        for m in sorted({c["model_id"] for c in self.state.candidates}):
            scores = self.state.scores_of(m)
            if len(scores) > 1:
                var = pstdev(scores)
                if var > best_var:
                    best_var, best_model = var, m
        pool = unmeas
        if best_model is not None:
            pool = [c for c in unmeas if c["model_id"] == best_model]
        if pool:
            return self._rng.choice(pool)
        return self._rng.choice(unmeas)

    def observe(self, candidate: dict[str, Any], score: float, n: int = 100) -> None:
        """Record a measurement (idempotent). Score must be in [0, 1]."""
        if not (0.0 <= float(score) <= 1.0):
            raise ValueError("score must be in [0, 1]")
        cid = self.state.key(candidate)
        self.state.measured[cid] = float(score)
        self.state.n[cid] = int(n)

    def selecting_confidence(self) -> float | None:
        """Fraction of measured model pairs with NON-overlapping Wilson CIs.

        Heuristic in [0, 1]; None when fewer than two models are measured.
        Documented as a heuristic, not a calibrated probability.
        """
        models = sorted({c["model_id"] for c in self.state.candidates})
        meas = [m for m in models if self.state.scores_of(m)]
        if len(meas) < 2:
            return None
        pairs = overlap = 0
        for i in range(len(meas)):
            for j in range(i + 1, len(meas)):
                ci_a = self.state.model_ci(meas[i])
                ci_b = self.state.model_ci(meas[j])
                pairs += 1
                if ci_a and ci_b and cis_overlap(ci_a, ci_b) is True:
                    overlap += 1
        return round(1.0 - overlap / pairs, 4)

    def stopped(self, *, at_least_models: int = 2, threshold: float = 0.95) -> bool:
        """Budget exhausted OR enough models measured AND confidence reached."""
        if self.state.budget_left() <= 0:
            return True
        measured = {k.split("::")[0] for k in self.state.measured}
        if len(measured) < at_least_models:
            return False
        conf = self.selecting_confidence()
        return conf is not None and conf >= threshold

    def confidence_report(self) -> dict[str, Any]:
        return {
            "strategy": self.state.strategy,
            "budget_left": self.state.budget_left(),
            "n_measured": len(self.state.measured),
            "per_model": {
                m: {"n_measured": len(self.state.scores_of(m)),
                    "mean": self.state.model_mean(m)}
                for m in sorted({c["model_id"] for c in self.state.candidates})
            },
            "confidence": self.selecting_confidence(),
        }


def compare_strategies(
    score_table: dict[str, dict[str, float]],
    candidates: Sequence[dict[str, Any]],
    budget: int,
    strategies: Sequence[str] = ("random", "uncertainty", "max_disagreement"),
    *,
    n_rep: int = 5,
    seed: int = 0,
) -> dict[str, Any]:
    """Empirical strategy comparison on a KNOWN score table (synthetic in tests).

    For each strategy, replays `budget` selections with `n_rep` seeds and
    records mean Spearman agreement between the ranking from measured configs
    and the full-table ranking (fraction of budget spent). No claim of
    superiority: this harness merely reports what the comparison shows.
    """
    from apertus_eval_prep.ranking import spearman_rank_correlation

    full_by_model: dict[str, float] = {
        m: mean(list(v.values())) for m, v in score_table.items() if v
    }
    result: dict[str, Any] = {}
    for strat in strategies:
        agreements = []
        for rep in range(n_rep):
            ev = AdaptiveEvaluator(candidates, budget=budget, strategy=strat,
                                   seed=seed + rep)
            while (cand := ev.select_next()) is not None:
                sc = score_table[cand["model_id"]][cand["config_key"]]
                ev.observe(cand, sc, n=100)
            measured_models = sorted({k.split("::")[0] for k in ev.state.measured})
            measured_acc = [mean(ev.state.scores_of(m)) for m in measured_models]
            full_acc = [full_by_model[m] for m in measured_models]
            tau = spearman_rank_correlation(measured_acc, full_acc)
            agreements.append(1.0 if tau is None else tau)
        result[strat] = {
            "mean_agreement": round(mean(agreements), 4),
            "n_rep": n_rep,
            "budget": budget,
            "n_models": len([m for m in score_table if score_table[m]]),
        }
    return result