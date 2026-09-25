#!/usr/bin/env bash
#SBATCH --job-name=vbpca-convergence-margin
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=36:00:00
#SBATCH --output=slurm-%x-%A_%a.out

set -Eeuo pipefail

: "${VBPCA_REPO_ROOT:?export the pinned VBPCApy checkout}"
: "${VBPCA_TRADE_STUDY_ROOT:?export the pinned trade-study checkout}"
: "${VBPCA_PYTHON:?export the analysis Python executable}"
: "${VBPCA_MARGIN_MANIFEST:?export the immutable manifest path}"
: "${VBPCA_MARGIN_OUTPUT_DIR:?export the condition-results directory}"
: "${VBPCA_REVISION:?export the pinned VBPCApy revision}"
: "${VBPCA_TRADE_STUDY_REVISION:?export the pinned trade-study revision}"
: "${VBPCA_MARGIN_MANIFEST_SHA256:?export the pinned manifest SHA-256}"
: "${SLURM_ARRAY_TASK_ID:?submit this worker with --array=0-5}"

if [[ ! -x "${VBPCA_PYTHON}" ]]; then
    printf 'Python executable not found: %s\n' "${VBPCA_PYTHON}" >&2
    exit 2
fi
if [[ "$(git -C "${VBPCA_REPO_ROOT}" rev-parse HEAD)" != "${VBPCA_REVISION}" ]]; then
    printf 'VBPCApy revision differs from pinned revision %s\n' \
        "${VBPCA_REVISION}" >&2
    exit 2
fi
if [[ -n "$(git -C "${VBPCA_REPO_ROOT}" status --porcelain --untracked-files=no)" ]]; then
    printf 'VBPCApy checkout has tracked changes.\n' >&2
    exit 2
fi
if [[ "$(git -C "${VBPCA_TRADE_STUDY_ROOT}" rev-parse HEAD)" != "${VBPCA_TRADE_STUDY_REVISION}" ]]; then
    printf 'trade-study revision differs from pinned revision %s\n' \
        "${VBPCA_TRADE_STUDY_REVISION}" >&2
    exit 2
fi
if [[ -n "$(git -C "${VBPCA_TRADE_STUDY_ROOT}" status --porcelain --untracked-files=no)" ]]; then
    printf 'trade-study checkout has tracked changes.\n' >&2
    exit 2
fi
actual_manifest_sha256="$(sha256sum "${VBPCA_MARGIN_MANIFEST}" | cut -d ' ' -f 1)"
if [[ "${actual_manifest_sha256}" != "${VBPCA_MARGIN_MANIFEST_SHA256}" ]]; then
    printf 'Manifest checksum differs from pinned SHA-256 %s\n' \
        "${VBPCA_MARGIN_MANIFEST_SHA256}" >&2
    exit 2
fi

export PYTHONPATH="${VBPCA_REPO_ROOT}/src:${VBPCA_TRADE_STUDY_ROOT}/src:${VBPCA_REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONUNBUFFERED="1"
# run_grid parallelizes independent replicates with one process per allocated
# CPU. Keep numerical kernels single-threaded inside each worker to avoid
# multiplying the allocation by the number of joblib processes.
export OMP_NUM_THREADS="1"
export OPENBLAS_NUM_THREADS="1"
export MKL_NUM_THREADS="1"
export BLIS_NUM_THREADS="1"
export NUMEXPR_NUM_THREADS="1"
export VBPCA_NUM_THREADS="1"

cd -- "${VBPCA_REPO_ROOT}"
vbpca_import="$("${VBPCA_PYTHON}" -c 'from pathlib import Path; import vbpca_py; print(Path(vbpca_py.__file__).resolve())')"
case "${vbpca_import}" in
    "${VBPCA_REPO_ROOT}/src"/*) ;;
    *)
        printf 'VBPCApy imported from %s, expected below %s/src\n' \
            "${vbpca_import}" "${VBPCA_REPO_ROOT}" >&2
        exit 2
        ;;
esac
trade_study_import="$("${VBPCA_PYTHON}" -c 'from pathlib import Path; import trade_study; print(Path(trade_study.__file__).resolve())')"
case "${trade_study_import}" in
    "${VBPCA_TRADE_STUDY_ROOT}/src"/*) ;;
    *)
        printf 'trade-study imported from %s, expected below %s/src\n' \
            "${trade_study_import}" "${VBPCA_TRADE_STUDY_ROOT}" >&2
        exit 2
        ;;
esac

printf 'VBPCApy revision: %s\ntrade-study revision: %s\n' \
    "${VBPCA_REVISION}" "${VBPCA_TRADE_STUDY_REVISION}"
"${VBPCA_PYTHON}" -c 'import platform, numpy, scipy; print(f"Python: {platform.python_version()}"); print(f"NumPy: {numpy.__version__}"); print(f"SciPy: {scipy.__version__}")'

"${VBPCA_PYTHON}" -m analysis.trade_study.validate_convergence_margins \
    run-condition \
    --manifest "${VBPCA_MARGIN_MANIFEST}" \
    --condition-index "${SLURM_ARRAY_TASK_ID}" \
    --output-dir "${VBPCA_MARGIN_OUTPUT_DIR}" \
    --n-jobs "${SLURM_CPUS_PER_TASK:-1}"
