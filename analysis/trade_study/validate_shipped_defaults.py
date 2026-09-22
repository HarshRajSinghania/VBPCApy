#!/usr/bin/env python
"""Replicated validation of the exact bucket configs shipped in defaults.py.

Targeted follow-up to the Option A trade study (#111): rather than
re-running the full Sobol collection, this compares the library's raw
default configuration against the *exact* configs ``recommend_config()``
returns today — the values ``v3_compare.py``'s replicated comparison never
actually validated, since it reads from older per-family JSON artifacts
instead of the shipped module.

Each regime (training + held-out validation) is evaluated ``--n-reps``
times per condition, with both the data draw and the VBPCA ``random_state``
varied per replicate (via ``VBPCASimulator.generate(..., rep=...)``), using
trade-study's replicated-trials support (jcm-sci/trade-study#112). Both
conditions share the same base seed per regime, so a given (regime, rep)
pair draws identical synthetic data and VBPCA init noise in both
conditions -- a paired (common-random-numbers) design that isolates the
effect of the config choice itself from other randomness sources.

Usage
-----
    python -m analysis.trade_study.validate_shipped_defaults --n-reps 8
    python -m analysis.trade_study.validate_shipped_defaults --regime-set routing --n-reps 8

The default ``all`` regime set includes the original training/validation grid
and the five shape-routing regimes from ``option_a_aspect_ratio``. Use
``routing`` for the smaller Rockfish job that revalidates only the coarse
wide, tall, and large-scale buckets after routing changes.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any

from trade_study import Direction, Observable, run_grid

from vbpca_py import defaults as vbpca_defaults
from vbpca_py import recommend_config

from ._common import VALIDATION_REGIMES
from ._world import VBPCAScorer, VBPCASimulator
from .option_a_aspect_ratio import ALL_REGIMES as ROUTING_REGIMES
from .option_a_pipeline import TRAINING_REGIMES

RESULTS_DIR = pathlib.Path("analysis/results/optionA")

OBSERVABLES: list[Observable] = [
    Observable("rank_mae", Direction.MINIMIZE),
    Observable("rank_under", Direction.MINIMIZE),
    Observable("rank_over", Direction.MINIMIZE),
    Observable("holdout_rmse", Direction.MINIMIZE),
    Observable("coverage_95", Direction.MAXIMIZE),
]

CONDITIONS = ("default", "shipped")

REGIME_SETS: dict[str, list[dict[str, Any]]] = {
    "original": TRAINING_REGIMES + VALIDATION_REGIMES,
    "routing": list(ROUTING_REGIMES.values()),
    "all": TRAINING_REGIMES + VALIDATION_REGIMES + list(ROUTING_REGIMES.values()),
}


def _grid_for_condition(
    regimes: list[dict[str, Any]], condition: str, seed: int
) -> list[dict[str, Any]]:
    """Build a run_grid grid: one row per regime, tagged with its bucket.

    The "default" condition supplies only regime keys, so VBPCASimulator
    falls back to the library's own untuned defaults. The "shipped"
    condition merges in whatever ``recommend_config(n, p)`` returns today.
    Each row gets a distinct base ``seed`` (offset by its index) so
    different regimes don't share a replicate seed sequence.

    Returns:
        List of config dicts suitable for run_grid.
    """
    grid: list[dict[str, Any]] = []
    for idx, regime in enumerate(regimes):
        cfg = dict(regime)
        n, p = int(regime["n"]), int(regime["p"])
        cfg["_bucket"] = vbpca_defaults._bucket(n, p)  # noqa: SLF001
        cfg["seed"] = seed + idx
        if condition == "shipped":
            cfg.update(recommend_config(n=n, p=p))
        grid.append(cfg)
    return grid


def run_validation(
    n_reps: int = 8,
    seed: int = 42,
    n_jobs: int = -1,
    regime_set: str = "all",
) -> dict[str, Any]:
    """Run the replicated default-vs-shipped comparison.

    Returns:
        Dict with per-condition, per-bucket aggregated results, saved
        alongside the return value at
        ``analysis/results/optionA/shipped_defaults_validation.json``.
    """
    regimes = REGIME_SETS[regime_set]
    world = VBPCASimulator()
    scorer = VBPCAScorer()

    per_condition: dict[str, list[dict[str, Any]]] = {}
    for condition in CONDITIONS:
        grid = _grid_for_condition(regimes, condition, seed)
        # run_grid doesn't know about "_bucket"; VBPCASimulator.generate
        # ignores unrecognised keys, so it's safe to carry through the
        # grid purely for post-hoc grouping below.
        table = run_grid(
            world,
            scorer,
            grid,
            OBSERVABLES,
            n_jobs=n_jobs,
            n_reps=n_reps,
        )
        agg = table.aggregate_replicates()

        rows: list[dict[str, Any]] = []
        for i, cfg in enumerate(agg.configs):
            row = {
                "condition": condition,
                "bucket": cfg["_bucket"],
                "n": cfg["n"],
                "p": cfg["p"],
                "true_rank": cfg["true_rank"],
                "missingness": cfg["missingness"],
                "n_reps": agg.metadata[i]["n_reps"],
            }
            for j, name in enumerate(agg.observable_names):
                row[name] = float(agg.scores[i, j])
                row[f"{name}_std"] = float(agg.metadata[i]["score_std"][name])
            rows.append(row)
        per_condition[condition] = rows

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "" if regime_set == "all" else f"_{regime_set}"
    out = RESULTS_DIR / f"shipped_defaults_validation{suffix}.json"
    out.write_text(json.dumps(per_condition, indent=2))

    _print_summary(per_condition)
    print(f"\nSaved -> {out}")
    return per_condition


def _print_summary(per_condition: dict[str, list[dict[str, Any]]]) -> None:
    buckets = sorted({row["bucket"] for row in per_condition["default"]})
    print(f"\n{'bucket':10s} {'condition':10s} {'rank_mae':>10s} {'rmse':>8s}")
    print("-" * 42)
    for bucket in buckets:
        for condition in CONDITIONS:
            rows = [r for r in per_condition[condition] if r["bucket"] == bucket]
            if not rows:
                continue
            mae = sum(r["rank_mae"] for r in rows) / len(rows)
            rmse = sum(r["holdout_rmse"] for r in rows) / len(rows)
            print(f"{bucket:10s} {condition:10s} {mae:10.3f} {rmse:8.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-reps", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--regime-set", choices=sorted(REGIME_SETS), default="all")
    args = parser.parse_args()
    run_validation(
        n_reps=args.n_reps,
        seed=args.seed,
        n_jobs=args.n_jobs,
        regime_set=args.regime_set,
    )


if __name__ == "__main__":
    main()
