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

STRATEGIES = ("random", "uncertainty", "max_disagreement", "apertus_r", "ofat", "lhs")


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
        if strat == "apertus_r":
            return self._apertus_r(unmeas)
        if strat == "ofat":
            return self._ofat(unmeas)
        if strat == "lhs":
            return self._lhs(unmeas)
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

    # -- Apertus-R ----------------------------------------------------
    def _model_decision_uncertainty(self, model_id: str) -> float:
        """Sum of pairwise decision uncertainties involving `model_id`.

        For each other MEASURED model o: uncertainty = 1 - |mean_m - mean_o|
        (closest pairs are the most decision-relevant). Pairs whose Wilson CIs
        overlap contribute a bonus of +0.5. Zero when no other model measured.
        """
        models = sorted({c["model_id"] for c in self.state.candidates})
        total = 0.0
        for o in models:
            if o == model_id:
                continue
            m_m = self.state.model_mean(model_id)
            m_o = self.state.model_mean(o)
            if m_m is None or m_o is None:
                continue
            d = abs(m_m - m_o)
            total += (1.0 - d)
            ci_m = self.state.model_ci(model_id)
            ci_o = self.state.model_ci(o)
            if ci_m and ci_o and cis_overlap(ci_m, ci_o) is True:
                total += 0.5
        return total

    def _apertus_r(self, unmeas: list[dict[str, Any]]) -> dict[str, Any]:
        """Reliability-aware acquisition (documented heuristic).

        Utility(c) = decision_relevance(model(c)) / cost(c):
          - decision_relevance: models with NO measurement yet get the maximum
            relevance (most unknown); otherwise the model's summed pairwise
            decision uncertainty (see _model_decision_uncertainty).
          - cost(c): candidate['estimated_cost'] when present (measured/DERIVED
            latency), else 1.0 — documented as the cost proxy until metered
            cost exists.
        Tie-breaks are seeded. This is a heuristic, NOT a proven optimum.
        """
        models = sorted({c["model_id"] for c in self.state.candidates})
        measured_models = {m for m in models if self.state.scores_of(m)}
        best, best_u = None, -1.0
        for cand in unmeas:
            m = cand["model_id"]
            if m not in measured_models:
                relevance = 1_000_000.0 + len(models)  # unmeasured models first
            else:
                relevance = self._model_decision_uncertainty(m)
            cost = float(cand.get("estimated_cost") or 1.0)
            if cost <= 0:
                cost = 1.0  # never divide by zero; 1.0 = unknown cost
            u = relevance / cost
            if u > best_u + 1e-12:
                best, best_u = cand, u
            elif abs(u - best_u) <= 1e-12 and best is not None:
                if self._rng.random() < 0.5:
                    best = cand
        if best is None:
            best = self._rng.choice(unmeas)
        return best

    # -- OFAT / LHS baselines -----------------------------------------
    def _ofat(self, unmeas: list[dict[str, Any]]) -> dict[str, Any]:
        """OFAT baseline: follow the factor-swap order of the candidate list.

        Candidates may carry an explicit ``order`` int (deterministic OFAT
        expansion order); otherwise the candidate list order is used. Returns
        the first unmeasured candidate in that order.
        """
        ordered = sorted(
            unmeas,
            key=lambda c: (int(c.get("order", 0)), self.state.key(c)),
        )
        return ordered[0]

    def _lhs(self, unmeas: list[dict[str, Any]]) -> dict[str, Any]:
        """Latin-hypercube-style stratification over the (model x config) grid.

        Round-robins across models; within a model, configs are consumed in a
        seeded rotation (offset by the model index). Documented as a stratified
        sampling baseline, not an optimal design.
        """
        models = sorted({c["model_id"] for c in unmeas})
        if not models:
            return self._rng.choice(unmeas)
        best = None
        for offset in range(len(models)):
            m = models[offset % len(models)]
            pool = [c for c in unmeas if c["model_id"] == m]
            if not pool:
                continue
            keyed = sorted(pool, key=lambda c: self.state.key(c))
            k = (self.state.seed + offset) % len(keyed)
            best = keyed[k]
            break
        return best if best is not None else self._rng.choice(unmeas)

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


# ---------------------------------------------------------------------------
# Budget curves (research Phase 8)
# ---------------------------------------------------------------------------


def _replay_metrics(
    score_table: dict[str, dict[str, float]],
    candidates: Sequence[dict[str, Any]],
    budget: int,
    strategy: str,
    seed: int,
    *,
    n: int = 100,
) -> dict[str, Any]:
    """One strategy trajectory -> per-metric values (measured on known table)."""
    from apertus_eval_prep.ranking import (
        spearman_rank_correlation,
    )

    full_by_model = {m: mean(list(v.values())) for m, v in score_table.items() if v}
    ev = AdaptiveEvaluator(candidates, budget=budget, strategy=strategy, seed=seed)
    while (cand := ev.select_next()) is not None:
        sc = score_table[cand["model_id"]].get(cand["config_key"])
        ev.observe(cand, sc, n=n)
    measured_models = sorted({k.split("::")[0] for k in ev.state.measured})
    if not measured_models:
        return {}
    meas_acc = [mean(ev.state.scores_of(m)) for m in measured_models]
    full_acc = [full_by_model[m] for m in measured_models]
    tau = spearman_rank_correlation(meas_acc, full_acc)
    ranking_recovery = 1.0 if tau is None else tau

    # pairwise decision accuracy vs full table ranking (ties are not wins)
    correct = total = 0
    for i in range(len(measured_models)):
        for j in range(i + 1, len(measured_models)):
            if meas_acc[i] == meas_acc[j] or full_acc[i] == full_acc[j]:
                continue  # ties are not decisions
            total += 1
            measured_winner = i if meas_acc[i] > meas_acc[j] else j
            full_winner = i if full_acc[i] > full_acc[j] else j
            correct += 1 if measured_winner == full_winner else 0
    pairwise_acc = correct / total if total else None

    score_err = mean(abs(a - b) for a, b in zip(meas_acc, full_acc))
    full_stds = {
        m: pstdev(list(v.values())) if len(v) > 1 else 0.0
        for m, v in score_table.items() if v
    }
    rel_err = mean(
        abs(pstdev(ev.state.scores_of(m)) - full_stds.get(m, 0.0))
        for m in measured_models
    )
    cost = sum(
        float(c.get("estimated_cost") or 1.0)
        for c in candidates
        if f"{c['model_id']}::{c['config_key']}" in ev.state.measured
    )
    return {
        "ranking_recovery": round(ranking_recovery, 6),
        "pairwise_decision_accuracy": round(pairwise_acc, 6) if pairwise_acc is not None else None,
        "score_error_mae": round(score_err, 6),
        "reliability_error_mae": round(rel_err, 6),
        "kendall_tau": tau,
        "evaluation_cost": round(cost, 6),
        "n_measured": len(ev.state.measured),
    }


def _ci(vals: list[float]) -> tuple[float | None, float | None]:
    if not vals:
        return None, None
    vals.sort()
    return vals[max(0, int(0.025 * len(vals)))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]


def budget_curves(
    score_table: dict[str, dict[str, float]],
    candidates: Sequence[dict[str, Any]],
    budgets: Sequence[int],
    strategies: Sequence[str] = ("random", "ofat", "apertus_r"),
    *,
    n_rep: int = 5,
    seed: int = 0,
) -> dict[str, Any]:
    """Empirical budget-vs-reliability curves (research Phase 8).

    Every strategy receives the SAME budget at each point, replayed ``n_rep``
    times with deterministic per-rep seeds. Metrics per (strategy, budget):
    mean + 95% percentile CI across reps for ranking recovery, pairwise
    decision accuracy, score error, reliability error, Kendall tau, and
    evaluation cost. No superiority claim is made by this harness; it only
    reports what the KNOWN score table shows.
    """
    budgets = sorted(budgets)
    out: dict[str, Any] = {}
    for strat in strategies:
        if strat not in STRATEGIES:
            raise ValueError(f"strategy {strat!r} not in {list(STRATEGIES)}")
        curves: dict[str, Any] = {}
        for b in budgets:
            metrics_by_key: dict[str, list[float]] = {}
            for rep in range(n_rep):
                m = _replay_metrics(
                    score_table, candidates, b, strat, seed=seed + rep
                )
                for k, v in m.items():
                    if isinstance(v, (int, float)):
                        metrics_by_key.setdefault(k, []).append(float(v))
            point: dict[str, Any] = {"n_rep": n_rep, "values": {}}
            for k, vals in metrics_by_key.items():
                lo, hi = _ci(list(vals))
                point["values"][k] = {
                    "mean": round(mean(vals), 6),
                    "ci_lo": lo,
                    "ci_hi": hi,
                }
            curves[b] = point
        out[strat] = curves
    return {
        "curves": out,
        "budgets": list(budgets),
        "strategies": list(strategies),
        "n_rep": n_rep,
        "base_seed": seed,
        "note": "known score table replay; all strategies get the same budget per point",
    }