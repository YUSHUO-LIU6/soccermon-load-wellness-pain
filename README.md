# SoccerMon: load, wellness and lower-limb pain

Code and frozen analytical materials for a published secondary longitudinal
analysis of 50 players from two elite Norwegian women's football teams during
2020–2021.

**Liu Y, Li H (2026).** Within-player load-wellness monitoring and lower-limb pain
in elite female football: A reproducible secondary analysis of the SoccerMon
dataset. *PLOS ONE* **21**(11): e0362663. Published 13 November 2026.
[Article and supporting information](https://doi.org/10.1371/journal.pone.0362663).
See [CITATION.cff](CITATION.cff) for machine-readable citation metadata.

## Research question and interpretation

Are deviations from a player's usual training load and wellness associated
with subsequent self-reported lower-limb pain/injury episode onset, and how
stable are the estimates to exposure construction, sparse events and missing
monitoring?

The reference risk set contains **36,296 player-days and 42 onset-days from 15
players**. The soreness complete-case analysis uses **19,758 days and 28
onset-days from nine event players**. These are self-reported symptom episodes;
clinical diagnoses are unavailable. The analyses estimate associations and do
not establish causality, prospective prediction performance or actionable
risk thresholds.

## A central sensitivity result

![Firth estimates and profile-likelihood 95% confidence intervals for the load–soreness interaction and chronic load under full-period and prior-observations-only standardization.](reports/standardization_sensitivity.png)

The full-period interaction estimate is below one, but whole-player bootstrap
intervals include one. Backward-looking standardization attenuates the
interaction and materially changes the chronic-load estimate. Sparse events,
team separation, season imbalance and incomplete monitoring limit all models.
See [study definitions and analysis hierarchy](docs/STUDY.md).

This repository figure uses frozen structured results and model-based
profile-likelihood intervals. It is separate from the published article figures.
The [source table](reports/standardization_sensitivity_data.csv) and
[provenance](reports/figure_provenance.json) identify its inputs.

## Reproduce and inspect

```bash
uv sync --frozen
uv run python scripts/pipeline.py verify-frozen
uv run python scripts/pipeline.py rebuild
uv run python scripts/pipeline.py diagnostics
```

`rebuild` obtains only the public 705,770-byte `subjective.zip`, checks its
SHA-256 and reconstructs the analytical data. To use a verified local copy, add
`--raw-zip /path/to/subjective.zip`. Raw files, player-level derived data,
dependencies and temporary results belong in the ignored `workspace/`.

Follow [the reproduction guide](docs/REPRODUCING.md) for local R setup,
independent Firth refits, isolated R1/R2 execution and the B=2,000 bootstraps.
The R2 historical workflow explicitly uses the frozen R1 baseline; a fresh R1
run does not replace it. Some historical scripts append or resume, so full
runs require separate clean workspaces.

The [post-publication audit](reports/REPRODUCIBILITY_AUDIT.md),
[result comparison](reports/RESULT_COMPARISON.csv) and
[execution manifest](reports/EXECUTION_MANIFEST.json) distinguish actual new
execution from stored-result checks and report unresolved items. The older
[VALIDATION.md](reports/VALIDATION.md) remains a historical record.

## Repository map

| Location | Contents |
|---|---|
| `analysis/core/` | Portable reconstruction and preserved R1 analysis |
| `analysis/sensitivity/` | Frozen R2 workstream source, staged by the runner |
| `analysis/reporting/` | Historical reporting script; see audit for coverage |
| `protocol/revision_sap/` | Unchanged frozen SAP, model matrix and missing-data plan |
| `reproducibility/frozen/` | Historical outputs, never used as evidence of a new refit |
| `reproducibility/` | Source hashes and derived-data fingerprints |
| `scripts/` | Execution, model acceptance, environment and verification tools |
| `environment/` | Original environment records and current setup guidance |
| `reports/` | Audit, comparisons, manifest and historical validation |

## Source materials and reuse

SoccerMon was created by Midoglu and colleagues:
[Zenodo dataset](https://doi.org/10.5281/zenodo.10033832).
The [original preregistration](https://doi.org/10.17605/OSF.IO/UAFWQ),
frozen revision SAP, R1 reanalysis, later R2 sensitivities and post-publication
software checks are distinct layers.

The published [S2 reproducibility archive](https://doi.org/10.1371/journal.pone.0362663.s014)
and [S3 original protocol](https://doi.org/10.1371/journal.pone.0362663.s015)
remain authoritative source records. The repository is a portable subset of
S2, with documented code adaptations and additional frozen SAP materials.
The audit records the correspondence and omissions; it does not assert that
the repository and archive are identical.

Raw ZIP files, local dependencies, manuscript drafts and private reviewer
correspondence are not distributed here. Existing player-level summaries and
third-party materials require the reuse review documented in the audit.
No repository code license has been selected. The article's publication
license does not itself resolve licensing of all code or source data.
