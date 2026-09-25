"""Tests for the immutable convergence-margin study design."""

from __future__ import annotations

from pathlib import Path
from runpy import run_path

import pytest

MODULE = run_path(
    str(
        Path(__file__).parents[1]
        / "analysis"
        / "trade_study"
        / "_convergence_margin_design.py"
    )
)
CONDITIONS = MODULE["CONDITIONS"]
DEFAULT_CONDITIONS = MODULE["DEFAULT_CONDITIONS"]
build_manifest = MODULE["build_manifest"]
condition_config = MODULE["condition_config"]
validate_manifest = MODULE["validate_manifest"]


@pytest.mark.parametrize("profile", ["smoke", "screen", "confirm"])
def test_profiles_route_only_to_affected_buckets(profile: str) -> None:
    manifest = build_manifest(profile, n_reps=2, seed=100)

    assert {regime["bucket"] for regime in manifest["regimes"]} == {
        "wide_moderate",
        "tall_moderate",
        "tall_extreme",
        "large_scale",
    }
    assert [regime["seed"] for regime in manifest["regimes"]] == list(
        range(100, 100 + len(manifest["regimes"]))
    )
    validate_manifest(manifest)
    assert manifest["conditions"] == list(DEFAULT_CONDITIONS)


def test_conditions_isolate_cap_and_warmup_changes() -> None:
    with pytest.warns(UserWarning, match="wide_moderate"):
        configs = {name: condition_config(50, 300, name) for name in CONDITIONS}

    assert configs["shipped"]["maxiters"] == 200
    assert configs["shipped"]["niter_broadprior"] == 200
    assert configs["cap400"]["maxiters"] == 400
    assert configs["cap400"]["niter_broadprior"] == 200
    assert configs["cap800"]["maxiters"] == 800
    assert configs["warmup50_cap400"]["niter_broadprior"] == 50
    assert configs["warmup50_cap400"]["maxiters"] == 400
    assert configs["no_warmup_cap400"]["niter_broadprior"] == 0
    assert configs["no_warmup_cap400"]["maxiters"] == 400
    assert configs["no_warmup_cap800"]["niter_broadprior"] == 0
    assert configs["no_warmup_cap800"]["maxiters"] == 800
    assert configs["bucket_margin_candidate"]["niter_broadprior"] == 0
    assert configs["bucket_margin_candidate"]["maxiters"] == 1600
    assert configs["forced800"]["maxiters"] == 800
    assert not any(configs["forced800"]["convergence_criteria"].values())


@pytest.mark.parametrize(
    ("n", "p", "bucket", "niter_broadprior", "maxiters"),
    [
        (50, 300, "wide_moderate", 200, 200),
        (1000, 50, "tall_moderate", 200, 200),
        (3000, 30, "tall_extreme", 200, 100),
        (250, 250, "large_scale", 200, 200),
    ],
)
def test_shipped_condition_preserves_prevalidation_control(
    n: int, p: int, bucket: str, niter_broadprior: int, maxiters: int
) -> None:
    with pytest.warns(UserWarning, match=bucket):
        config = condition_config(n, p, "shipped")

    assert config["niter_broadprior"] == niter_broadprior
    assert config["maxiters"] == maxiters


@pytest.mark.parametrize(
    ("n", "p", "bucket", "maxiters"),
    [
        (50, 300, "wide_moderate", 1600),
        (1000, 50, "tall_moderate", 400),
        (3000, 30, "tall_extreme", 800),
        (250, 250, "large_scale", 400),
    ],
)
def test_bucket_margin_candidate_uses_preregistered_cap(
    n: int, p: int, bucket: str, maxiters: int
) -> None:
    with pytest.warns(UserWarning, match=bucket):
        config = condition_config(n, p, "bucket_margin_candidate")

    assert config["niter_broadprior"] == 0
    assert config["maxiters"] == maxiters


def test_bucket_margin_candidate_rejects_unaffected_bucket() -> None:
    with pytest.raises(ValueError, match="applies only"):
        condition_config(100, 20, "bucket_margin_candidate")


def test_condition_configs_do_not_share_mutable_values() -> None:
    with pytest.warns(UserWarning, match="tall_moderate"):
        first = condition_config(1000, 50, "cap400")
    first["rmsstop"].append(999)
    first["convergence_criteria"]["angle"] = False

    with pytest.warns(UserWarning, match="tall_moderate"):
        second = condition_config(1000, 50, "cap400")

    assert 999 not in second["rmsstop"]
    assert second["convergence_criteria"]["angle"] is True


def test_manifest_allows_selected_conditions_and_reference() -> None:
    manifest = build_manifest(
        "confirm",
        n_reps=8,
        seed=20,
        conditions=("shipped", "no_warmup_cap400"),
        reference_condition="shipped",
    )

    assert manifest["conditions"] == ["shipped", "no_warmup_cap400"]
    assert manifest["reference_condition"] == "shipped"
    validate_manifest(manifest)


def test_manifest_allows_bucket_margin_confirmation() -> None:
    manifest = build_manifest(
        "confirm",
        n_reps=12,
        seed=20261122,
        conditions=("shipped", "bucket_margin_candidate"),
        reference_condition="shipped",
    )

    assert manifest["conditions"] == ["shipped", "bucket_margin_candidate"]
    assert manifest["reference_condition"] == "shipped"
    assert manifest["n_reps"] == 12
    assert manifest["seed"] == 20261122
    validate_manifest(manifest)


@pytest.mark.parametrize(
    ("conditions", "reference", "match"),
    [
        ((), "shipped", "at least one"),
        (("shipped", "shipped"), "shipped", "duplicates"),
        (("unknown",), "unknown", "unknown convergence-margin"),
        (("shipped",), "cap800", "absent from conditions"),
    ],
)
def test_build_manifest_rejects_invalid_condition_selection(
    conditions: tuple[str, ...], reference: str, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        build_manifest(
            "confirm",
            n_reps=1,
            seed=10,
            conditions=conditions,
            reference_condition=reference,
        )


@pytest.mark.parametrize(
    ("conditions", "reference", "match"),
    [
        ([], "shipped", "non-empty"),
        (["shipped", "shipped"], "shipped", "duplicates"),
        (["shipped", "unknown"], "shipped", "unknown conditions"),
        (["shipped"], "cap800", "absent from conditions"),
    ],
)
def test_manifest_validation_rejects_invalid_condition_selection(
    conditions: list[str], reference: str, match: str
) -> None:
    manifest = build_manifest("screen", n_reps=1, seed=10)
    manifest["conditions"] = conditions
    manifest["reference_condition"] = reference

    with pytest.raises(ValueError, match=match):
        validate_manifest(manifest)


def test_invalid_profile_condition_and_replicates_fail() -> None:
    with pytest.raises(ValueError, match="unknown profile"):
        build_manifest("unknown", n_reps=1, seed=1)
    with pytest.raises(ValueError, match="positive"):
        build_manifest("screen", n_reps=0, seed=1)
    with pytest.raises(ValueError, match="unknown convergence-margin condition"):
        condition_config(50, 300, "unknown")
