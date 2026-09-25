# Post-warmup convergence-margin validation

This study closes the evidence gate in
[issue #133](https://github.com/yoavram-lab/VBPCApy/issues/133). Four shipped
routing buckets currently have no eligible post-warmup convergence window:
`wide_moderate`, `tall_moderate`, `tall_extreme`, and `large_scale`.

The paired design compares:

- the exact shipped configuration;
- the shipped warmup with caps of 400 and 800 iterations;
- 50-iteration and zero-iteration warmups with a 400-iteration cap; and
- a forced 800-iteration endpoint with all numerical stop criteria disabled.

`cap800` is the practical reference. The forced endpoint diagnoses whether
accepted numerical stops differ from a long-run endpoint; it is not presumed
to be better. Runtime and iteration counts are secondary diagnostics and do
not compensate for worse rank recovery, held-out prediction, or coverage.

The `smoke` profile uses smaller shapes that route to all four affected
buckets. `screen` uses the exact microbiome, cultural, ecological, and
single-cell shapes that produced the shipped configurations. `confirm` adds
held-out shapes and complete, MCAR, MNAR-censored, and block-missingness
settings.

## Local smoke test

Install the local `trade-study` package in the analysis environment, then run:

```bash
python -m analysis.trade_study.validate_convergence_margins manifest \
  --profile smoke --n-reps 1 --seed 20260922 \
  --output analysis/results/convergence_margin/smoke/manifest.json

for condition_index in 0 1 2 3 4 5; do
  python -m analysis.trade_study.validate_convergence_margins run-condition \
    --manifest analysis/results/convergence_margin/smoke/manifest.json \
    --condition-index "${condition_index}" \
    --output-dir analysis/results/convergence_margin/smoke/conditions \
    --n-jobs 4
done

python -m analysis.trade_study.validate_convergence_margins summarize \
  --manifest analysis/results/convergence_margin/smoke/manifest.json \
  --output-dir analysis/results/convergence_margin/smoke/conditions \
  --output analysis/results/convergence_margin/smoke/summary.json
```

Each condition is an atomic checkpoint. Re-running a complete condition
validates and reuses it; a checkpoint with a different config, replicate set,
observable schema, or non-finite score fails closed.

## Rockfish shared-array screen

Create the `screen` manifest once in a clean, pinned checkout and record its
checksum. Export cluster-specific paths rather than committing them:

```bash
export VBPCA_REPO_ROOT=/path/to/clean/VBPCApy
export VBPCA_TRADE_STUDY_ROOT=/path/to/clean/trade-study
export VBPCA_PYTHON=/path/to/analysis/python
export VBPCA_MARGIN_MANIFEST=/path/to/results/screen/manifest.json
export VBPCA_MARGIN_OUTPUT_DIR=/path/to/results/screen/conditions
export VBPCA_REVISION="$(git -C "${VBPCA_REPO_ROOT}" rev-parse HEAD)"
export VBPCA_TRADE_STUDY_REVISION="$(git -C "${VBPCA_TRADE_STUDY_ROOT}" rev-parse HEAD)"

"${VBPCA_PYTHON}" -m analysis.trade_study.validate_convergence_margins \
  manifest --profile screen --n-reps 3 --seed 20260922 \
  --output "${VBPCA_MARGIN_MANIFEST}"
export VBPCA_MARGIN_MANIFEST_SHA256="$(sha256sum "${VBPCA_MARGIN_MANIFEST}" | cut -d ' ' -f 1)"

sbatch --array=0-5%6 \
  --export=ALL,VBPCA_REPO_ROOT,VBPCA_TRADE_STUDY_ROOT,VBPCA_PYTHON,VBPCA_MARGIN_MANIFEST,VBPCA_MARGIN_OUTPUT_DIR,VBPCA_REVISION,VBPCA_TRADE_STUDY_REVISION,VBPCA_MARGIN_MANIFEST_SHA256 \
  analysis/rockfish/convergence_margin_shared.sbatch
```

Monitor with `squeue -u "$USER"`, then inspect completed jobs with
`sacct -j JOB_ID --format=JobID,State,Elapsed,MaxRSS,ExitCode`. After all six
array tasks succeed, run `summarize` as above. Advance only nondominated
candidates to a new `confirm` manifest with distinct seeds; do not edit or
reuse the screen manifest.

## Selected-candidate confirmation

Keep the shipped configuration as the control and name only candidates that
survived screening. Set the reference explicitly when the practical
`cap800` screen reference is not among the selected conditions. For example:

```bash
"${VBPCA_PYTHON}" -m analysis.trade_study.validate_convergence_margins \
  manifest --profile confirm --n-reps 8 --seed 20261022 \
  --conditions shipped no_warmup_cap400 \
  --reference-condition shipped \
  --output "${VBPCA_MARGIN_MANIFEST}"
export VBPCA_MARGIN_MANIFEST_SHA256="$(sha256sum "${VBPCA_MARGIN_MANIFEST}" | cut -d ' ' -f 1)"

# Two selected conditions means array indices 0 and 1. Indices always resolve
# against the ordered condition list stored in the immutable manifest.
sbatch --array=0-1%2 \
  --export=ALL,VBPCA_REPO_ROOT,VBPCA_TRADE_STUDY_ROOT,VBPCA_PYTHON,VBPCA_MARGIN_MANIFEST,VBPCA_MARGIN_OUTPUT_DIR,VBPCA_REVISION,VBPCA_TRADE_STUDY_REVISION,VBPCA_MARGIN_MANIFEST_SHA256 \
  analysis/rockfish/convergence_margin_shared.sbatch
```

The reducer reads the same manifest and therefore validates and compares only
those selected checkpoints.

The original smoke/screen design remains six conditions. If its selected
no-warmup candidate still reaches the 400-iteration cap in confirmation, the
registered opt-in `no_warmup_cap800` condition isolates the remaining cap
effect without changing that original design:

```bash
"${VBPCA_PYTHON}" -m analysis.trade_study.validate_convergence_margins \
  manifest --profile confirm --n-reps 8 --seed 20261022 \
  --conditions no_warmup_cap400 no_warmup_cap800 \
  --reference-condition no_warmup_cap400 \
  --output "${VBPCA_MARGIN_MANIFEST}"
```

Within this versioned study, `shipped` retains the pre-validation warmup and
cap values even after public recommendations adopt a validated candidate.
This prevents later defaults from redefining the historical control or its
one-factor ablations.

## Preregistered bucket-specific validation

The confirmation and cap follow-up motivate one final, opt-in candidate. It
sets `niter_broadprior=0` in every affected bucket and changes only the
iteration margin by bucket: 1600 for `wide_moderate`, 400 for
`tall_moderate`, 800 for `tall_extreme`, and 400 for `large_scale`. These
choices were fixed before examining the final validation seeds. The original
six-condition design and the shipped defaults remain unchanged.

Validate the candidate against the shipped control with 12 paired replicates
per confirmation regime and the held-out seed series beginning at 20261122:

```bash
"${VBPCA_PYTHON}" -m analysis.trade_study.validate_convergence_margins \
  manifest --profile confirm --n-reps 12 --seed 20261122 \
  --conditions shipped bucket_margin_candidate \
  --reference-condition shipped \
  --output "${VBPCA_MARGIN_MANIFEST}"
export VBPCA_MARGIN_MANIFEST_SHA256="$(sha256sum "${VBPCA_MARGIN_MANIFEST}" | cut -d ' ' -f 1)"

sbatch --array=0-1%2 \
  --export=ALL,VBPCA_REPO_ROOT,VBPCA_TRADE_STUDY_ROOT,VBPCA_PYTHON,VBPCA_MARGIN_MANIFEST,VBPCA_MARGIN_OUTPUT_DIR,VBPCA_REVISION,VBPCA_TRADE_STUDY_REVISION,VBPCA_MARGIN_MANIFEST_SHA256 \
  analysis/rockfish/convergence_margin_shared.sbatch
```

Do not substitute another cap, seed, replicate count, profile, or regime after
seeing these results. A shipped-default change is a separate decision and
commit made only after this immutable validation completes.

## Validation outcome

The preregistered run completed on Rockfish as array job `31220503`, pinned to
VBPCApy merge `2a41cad6ca54519ef224e44bc0f24a9915eddd5c` and trade-study
revision `68753adab5e420629ee0cbc20c319e675029a071`. Its manifest SHA-256 is
`96f0c4332cfc0b8f374c50b2149be850038251084c45546ac5704c6a551c61f9`.

Across 120 paired fits per condition, the candidate improved exact rank
recovery from 0.825 to 0.900 (paired difference 0.075; 95% regime-stratified
bootstrap CI 0.042 to 0.108), rank MAE from 1.058 to 0.183 (gain 0.875; CI
0.725 to 1.017), and holdout RMSE from 0.848 to 0.588 (difference -0.260; CI
-0.296 to -0.224). Coverage was unchanged within uncertainty. The selected-fit
budget-hit rate fell from 100% to 5%. The intervals were regenerated from the
retained checkpoints after #172 corrected the reducer to preserve the fixed
regime composition; point estimates were unchanged and no fits were rerun.

The remaining six selected-fit budget hits comprised two microbiome and two
wide-complete replicates at the 1600-iteration cap and two tall-extreme-MNAR
replicates at the 800-iteration cap. The wide-complete setting also shifted
from severe under-selection toward moderate over-selection: exact recovery
fell from 3/12 to 1/12 even though mean rank MAE improved from 1.917 to 1.750
and holdout RMSE improved by 0.669. These qualifications are retained rather
than tuning again on the final validation seeds. The primary paired endpoints
support shipping the registered policy; see #166 and #168 for the full
decision record.
