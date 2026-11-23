# Reproducing the published analysis

Run commands from the repository root. Frozen results and protocol files are
read-only references. The dated audit in `reports/REPRODUCIBILITY_AUDIT.md`
reports what actually ran; `reports/VALIDATION.md` documents the earlier
2026-10-21 portability pass.

## Install the recorded portable environment

```bash
uv sync --frozen
Rscript --vanilla scripts/setup_r.R
export SOCCERMON_R_LIBRARY="$PWD/workspace/R/library"
export R_LIBS_USER="$SOCCERMON_R_LIBRARY"
```

Do not update `uv.lock` to force agreement. The R setup script installs only
missing packages into the selected local library; installed packages can also
be loaded from the existing R installation. It records versions, library
origins and session information, and never installs into the system library.
It is a dependency bootstrap, **not an R lockfile**. The original Windows R
4.6.1 records and portable macOS R 4.5.2 records are distinct. Consult
`environment/REPRODUCIBILITY.md` for the current differences.

## Integrity, raw rebuild, diagnostics and focused refits

```bash
uv run python scripts/pipeline.py verify-frozen --workspace workspace/checks
uv run python scripts/pipeline.py rebuild --workspace workspace/checks
uv run python scripts/pipeline.py diagnostics --workspace workspace/checks
uv run python scripts/pipeline.py refit-focus --workspace workspace/checks
```

Only `subjective.zip` (705,770 bytes) is required. The runner downloads it from
[Zenodo](https://doi.org/10.5281/zenodo.10033832), checks
`data/subjective.zip.sha256` before extraction, and rejects unsafe ZIP paths.
The approximately 99 GB GPS archives are irrelevant to this analysis. With
an existing input, use:

```bash
uv run python scripts/pipeline.py rebuild --workspace workspace/checks \
  --raw-zip /path/to/subjective.zip
```

The six reconstructed files and two exposure-sensitivity files must match
`reproducibility/data_fingerprints.json` and `sensitivity_fingerprints.json`.
Their checks preserve row/column order and missingness, hashing numeric values
rounded to eight decimals. Counts are independently inspected; they are not
permitted input corrections. Canonical burden coding and lagged rolling
windows are defined in `docs/STUDY.md`.

Focused refits compare the F and F_hist interaction and chronic-load ORs,
all eight profile-likelihood CI endpoints, and exact N/events. The existing
absolute 0.001 tolerance applies only to those displayed estimates. Full
result comparisons use the stricter historical Gate A criterion below.

## Independent full R1 and R2 runs

Use **two new execution roots**. Do not run R1 and R2 in a shared directory.
The following names are examples; choose unused names for another run.

```bash
uv run python scripts/pipeline.py rebuild --workspace workspace/r1-new
uv run python scripts/pipeline.py r1-full --workspace workspace/r1-new
uv run python scripts/pipeline.py figures --workspace workspace/r1-new

uv run python scripts/pipeline.py rebuild --workspace workspace/r2-new
uv run python scripts/pipeline.py r2-full --workspace workspace/r2-new
```

`--workspace` and `SOCCERMON_EXECUTION_ROOT` select execution roots confined
to ignored `workspace/`. Full runs claim `full_run.json`; repeated/mixed full
runs or existing model outputs are refused. If interrupted, preserve that
root as evidence and rebuild in a new root. Do not delete the marker or enable
implicit resume to manufacture a clean execution history.

R1 writes newly fitted results into
`r2/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_PORTABLE` within
its execution root. R2 explicitly copies the frozen R1 baseline into
`RUN_R2_REPRO`; only its required observation-weight inputs are reconstructed.
This reproduces the historical R2 workflow. It is not an end-to-end sensitivity
run substituting the new R1 results. Any such additional comparison must have
a separate root and an explicit baseline-change record.

The preserved R2 sources are staged with documented Windows-root relocation.
Two unused historical validation reads in the assembly script are omitted in
the staged copy; their old results are not inserted as new evidence. Original
analytical sources, model formulas and frozen SAP remain unchanged. Every
staged source and transformation has a SHA-256 provenance record.

## Bootstrap evidence and limitations

The full workflows request B=2,000. R1 includes a marginal-logit whole-player
bootstrap and separate Firth bootstraps for soreness, fatigue and readiness;
R2 includes non-overlap/drop-team marginal-logit bootstraps. The original
marginal bootstrap is not 2,000 `glmer` refits. Base seed is 20260722; R1 Firth
uses one continuous RNG stream initialized at 20260723; internal QA sampling
uses 20260902. These distinctions matter for exact reproduction.

Inspect requested, completed, accepted and failed counts, replicate IDs where
saved, execution logs and summary intervals. Historical Firth code saves
summaries but no individual replicate estimates. Its IRLS iteration-limit
handling and acceptance rule do not certify convergence of every accepted
fit. Preserve this limitation and failed/unstable results; a corrected-algorithm
sensitivity would be a distinct post-publication analysis.

## Automated acceptance and tests

```bash
uv run python scripts/verify_results.py \
  --r1-workspace workspace/r1-new --r2-workspace workspace/r2-new \
  --output reports/RESULT_COMPARISON.csv \
  --details-output reports/NUMERICAL_DISCREPANCIES.csv
uv run python -m unittest discover -s tests -v
```

The verifier uses the existing Gate A numeric policy:
`abs(a-b) <= max(1e-8, 1e-6*max(abs(a),abs(b)))`. Counts, row-key occurrence
counts, missingness and estimation states are exact. It checks structures,
registries, bootstrap counts and execution provenance. Exit status 0 means all
included checks pass, 1 means at least one failure, and 2 means incomplete or
blocked checks without a numerical failure. Copied/manual historical evidence
is labeled NOT RUN rather than treated as a newly computed result. An exit 0
from the analysis runner itself is not numerical acceptance.

Differences in rejected mixed-model fits, ties in event ranks, software
warning text and floating-point output must be explained without changing
reference values or relaxing tolerances. PNG/SVG byte equality is not a
cross-platform acceptance criterion: inspect underlying data, coefficients
and scientific content. The preserved figure script is distinct from the
repository's frozen portfolio illustration and does not recreate final
publisher page layout.

Timestamped logs, `execution.jsonl`, `full_run.json`, raw hashes, staged-source
hashes and validation outputs are under each ignored execution root. Public
summary reports record hashes and commands with local account paths redacted.
Never commit raw/player-day datasets, installed libraries, caches or private
correspondence. Source-data attribution and code-license decisions are
recorded separately in `docs/DATA_REUSE.md` and `reports/PUBLICATION_SAFETY.md`.

## Separate frailty dependency probe

The audit's Model E/readiness diagnostic reused `cc_sample`, `mk_cp` and
`cox_rhs` directly from the unchanged core source. With the desired survival
version already installed in an isolated project library:

```bash
Rscript --vanilla scripts/probe_frailty_version.R workspace/R/library \
  workspace/r1-new/r2/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/modeling_dataset.csv \
  workspace/probe-current.json
Rscript --vanilla scripts/probe_frailty_version.R workspace/R/frozen-survival \
  workspace/r1-new/r2/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/modeling_dataset.csv \
  workspace/probe-frozen-survival.json
```

The audit installed survival 3.8-6 from the CRAN archive solely into
`workspace/R/frozen-survival`; the main full run continued with its original
selected library. Both versions returned the same warning-bearing estimate
on macOS/R 4.5.2. This is an explanatory dependency diagnostic, not a replacement
analysis or evidence that the fit converged. Recreating the original Windows
R 4.6.1 environment remains necessary to isolate the residual failure-state
difference. The original failure, warnings and current results stay separate.

## Independent Firth replicate diagnostics

The archived Firth summaries did not retain individual replicates. To fill
that evidence gap without changing the numerical algorithm or acceptance rule:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/audit_firth_replicates.py \
  --dataset workspace/r1-new/r2/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/modeling_dataset.csv \
  --reference workspace/r1-new/r2/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_PORTABLE/firth_bootstrap_results.csv \
  --output workspace/firth-trace-new
uv run python scripts/verify_results.py \
  --r1-workspace workspace/r1-new --r2-workspace workspace/r2-new \
  --firth-audit workspace/firth-trace-new --output reports/RESULT_COMPARISON.csv
```

This replays only three Firth B=2,000 streams, retains the original seed stream,
and records termination/acceptance plus every coefficient without saving player
identities. It refuses an existing output root. It is post-publication
verification, not an original preregistered analysis. The original marginal
bootstraps do not need repeating solely to add these Firth traces.

Strict FAIL outcomes are not waived by the release decision. The accompanying
scientific-impact assessment distinguishes protected contrasts from unstable
ancillary fits, rejected fallback levels, small numeric differences, tied ranks
and repeated historical records. Model E and the joint team/season-removal QA
GLMM remain unverified for interpretation; see `reports/FOLLOW_UP_VERIFICATION.md`.
