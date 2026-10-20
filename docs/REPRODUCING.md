# Reproducing the analysis

## Verification levels

Commands intentionally separate checking stored results, rebuilding data and
refitting models. A passing stored-results audit does not mean a model or a
2,000-replicate bootstrap has been rerun.

| Command | What it does | Inputs |
|---|---|---|
| `verify-frozen` | Verify imported-file and frozen-SAP hashes; reexecute 54 consistency checks on frozen structured results | Tracked frozen reference files |
| `rebuild` | Verify the raw ZIP hash; rebuild player-days, episodes, risk sets, exposures and missingness models; compare six derived files against frozen column fingerprints | Public `subjective.zip` |
| `diagnostics` | Recompute event/sample audit, sparse-data diagnostics, collinearity, non-overlap exposures and historical standardization | Rebuilt data and explicitly frozen R1 reference results |
| `refit-focus` | Independently refit the full-period and backward-looking soreness Firth models; compare focal ORs and profile-likelihood CIs | Rebuilt data, `logistf` |
| `r1-full` | Run the preserved R1 model suite and full B=2,000 bootstrap procedures, then finalize fresh results | Rebuilt data and R packages |
| `r2-full` | Run preserved R2 sensitivity workstreams, including their bootstraps, with the frozen R1 baseline | Rebuilt data and R packages |
| `plot` | Render the two focal parameters from frozen results, with source CSV and provenance | Tracked frozen results |

## Python

Install [uv](https://docs.astral.sh/uv/), then run from the repository root:

```bash
uv sync --frozen
uv run python scripts/pipeline.py verify-frozen
uv run python scripts/pipeline.py plot
uv run python scripts/pipeline.py rebuild
uv run python scripts/pipeline.py diagnostics
```

`rebuild` downloads only the 705,770-byte subjective archive from the documented
Zenodo record, not the approximately 99 GB objective/GPS files. Alternatively:

```bash
uv run python scripts/pipeline.py rebuild --raw-zip /path/to/subjective.zip
```

The SHA-256 must match `data/subjective.zip.sha256` before extraction.
Raw files, player-level derived data, temporary scripts and execution logs stay
under the ignored `workspace/` directory. Do not commit that directory.

The six derived-file checks hash every column in row order, with explicit
missingness and numerical values rounded to eight decimal places. This is a
strict reproducibility fingerprint, not an element-wise tolerance test. A
mismatch should be inspected, not bypassed or made to pass by changing inputs.

The two old historical comparisons in the portable core scripts are optional.
They do not enter the revised estimand. Their paths can be supplied using
`SOCCERMON_OLD_DERIVED` and `SOCCERMON_FROZEN_EPISODES`. Without them the scripts
explicitly record skipped historical comparisons. The six-file fingerprint
check remains required.

## R

The original freeze used Windows, Python 3.11.9 and R 4.6.1. Their recorded
package versions are in `environment/`. The Python lock specifies the exact
environment resolved for this portable repository; it is separate from the
original environment record.

Install dependencies in a local library, without changing the system library:

```bash
Rscript --vanilla scripts/setup_r.R
SOCCERMON_R_LIBRARY="$PWD/workspace/R/library" R_LIBS_USER="$PWD/workspace/R/library" \
  uv run python scripts/pipeline.py refit-focus
```

Use the same environment variables for `r1-full` and `r2-full`. Their
B=2,000 procedures can take substantially longer than the data rebuild.
The focal-refit comparison uses a prespecified absolute tolerance of 0.001
for the displayed OR and each profile-likelihood CI endpoint. Record actual
R/package versions with every verification; cross-platform agreement is not
assumed.

## Workspace and provenance

Frozen R2 scripts are retained verbatim in `analysis/sensitivity/`.
The runner stages working copies and relocates the original `FR`/`WS` roots.
Model specifications, transformations, fallback rules and random seed 20260722
are unchanged. `analysis/core/` retains the repository's existing portability
layer; original and portable hashes are recorded in `source_manifest.csv`.

R2 scripts read the copied frozen `RUN_R2_REPRO` baseline. `r1-full` writes
fresh results to `RUN_PORTABLE`; it does not silently replace that baseline.
Use a separate clean checkout/workspace for a new full run: some original R2
scripts append or resume. Do not combine outputs from different runs.

The manual wellness-polarity audit preserves its evidence note and source
identifiers. It is not rerun as an automated empirical validation.
Source manuscript packages, reviewer correspondence, raw ZIP files, software
caches and installed Windows libraries are not tracked in this repository.
