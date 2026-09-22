# Convergence Criteria

Each fit run (including every candidate $k$ tried in `select_n_components`)
iterates the EM loop until one of the following criteria triggers or `maxiters`
is reached.

## Criteria (evaluated in priority order)

### 1. Subspace angle — `minangle`

Stops when the principal angle between successive loading matrices falls below
the threshold.

| Option | Default | Description |
|--------|---------|-------------|
| `minangle` | `1e-8` | Angle threshold in radians |

### 2. Early stopping on probe RMS — `earlystop`

When a probe set is provided (via `xprobe` or `xprobe_fraction`), stops if the
probe RMS starts increasing (overfitting signal).

| Option | Default | Description |
|--------|---------|-------------|
| `earlystop` | `False` | Enable probe-based early stopping |

### 3. RMS plateau — `rmsstop`

Compares the current RMS to the value `window` iterations ago. Stops if the
absolute change is below `abs_tol` or the relative change is below `rel_tol`.

| Option | Default | Description |
|--------|---------|-------------|
| `rmsstop` | `[100, 1e-4, 1e-3]` | `[window, abs_tol, rel_tol]` |

### 4. Cost / ELBO plateau — `cfstop`

Same interpretation as `rmsstop` but applied to the variational cost (negative
ELBO).

| Option | Default | Description |
|--------|---------|-------------|
| `cfstop` | `[]` (disabled) | `[window, abs_tol, rel_tol]` |

### 5. Relative ELBO decrease — `cfstop_rel`

Stops when the fractional ELBO improvement drops below a threshold.

| Option | Default | Description |
|--------|---------|-------------|
| `cfstop_rel` | disabled | Relative improvement threshold |

### 6. ELBO curvature — `cfstop_curv`

Stops when the second difference of the ELBO stabilises.

| Option | Default | Description |
|--------|---------|-------------|
| `cfstop_curv` | disabled | Curvature threshold |

### 7. Composite criteria — `composite_stop`

Require multiple criteria to trigger simultaneously. Pass a dict specifying
which criteria must all be satisfied:

```python
model = VBPCA(
    n_components=5,
    composite_stop={"rmsstop": [50, 1e-4, 1e-3], "cfstop": [50, 1e-3, 1e-2]},
)
```

## Patience

All criteria support a **criterion-specific patience window**: the same
criterion must be satisfied for $N$ consecutive eligible iterations before
convergence is declared. Alternating hits from different criteria are tracked
separately and cannot jointly satisfy patience.

| Option | Default | Description |
|--------|---------|-------------|
| `patience` | `1` | Consecutive iterations required |

## Other stopping conditions

- **Slowing-down guard:** internal backtracking hits 40 steps.
- **Hard cap:** `maxiters` (default 1000).
- **Broad-prior warmup:** during the first `niter_broadprior` iterations (default
  100), stopping messages are suppressed when `use_prior` is active, allowing the
  model to settle before ARD engages.

A fit that reaches `maxiters` without accepting a criterion reports
`convergence_reason_ == "maxiters"` and `converged_ == False`. Probe-based early
stopping and the slowing-down guard also set `converged_ == False` because they
terminate for validation or stability reasons rather than numerical
convergence. VBPCA warns whenever the resolved options have
`maxiters <= niter_broadprior`: that configuration leaves no eligible
post-warmup iteration in which a convergence criterion can stop the fit.

## Criterion ordering — `criterion_order`

Individual criteria have **OR semantics** by default. Criteria are evaluated in
a fixed priority order (angle first, slowing-down last), and the first eligible
criterion whose own patience streak is complete wins. Reordering determines
the winner when multiple criteria are ready on the same iteration; it does not
require an earlier criterion to converge before a later one may stop the fit.
Use `composite_stop` and disable its individual constituents when AND semantics
are required.

| Option | Default | Description |
|--------|---------|-------------|
| `criterion_order` | `None` (use default) | List of criterion names in priority order |

Valid criterion names: `angle`, `earlystop`, `rms_plateau`, `cost`,
`composite`, `slowing_down`.

The learning curve records a numeric `criterion_satisfied_<name>` trace for
every criterion, including disabled or nonwinning criteria. These traces allow
counterfactual stopping policies to be compared after a long-running fit.

## Per-criterion enable/disable — `convergence_criteria`

Selectively disable individual criteria without zeroing their thresholds.
Disabled criteria are still evaluated for diagnostics but excluded from the
stop decision.

| Option | Default | Description |
|--------|---------|-------------|
| `convergence_criteria` | `None` (all enabled) | Dict mapping criterion names to booleans |
