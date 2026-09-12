# Reproducibility

This directory documents the reproducibility and validation framework used for the SoccerMon secondary analysis.

The project was developed as a structured reproducibility workflow rather than as a single analysis script. The frozen analysis package includes explicit model specifications, validation checks, numerical consistency checks, and records of the final analytical state.

## Reproducibility framework

The workflow includes:

- reconstruction of the analytical player-day dataset from the public source data
- predefined exposure and outcome construction
- structured model specifications
- sparse-event diagnostics
- whole-player resampling procedures
- sensitivity analyses
- numerical consistency checks
- software and execution records
- file-integrity checks for the frozen analytical package

## Validation

The frozen revision package contains multiple layers of validation designed to check that:

1. the analytical dataset can be reconstructed from the documented source data;
2. derived variables and model inputs are consistent with the frozen reference analysis;
3. reported numerical results correspond to the final analysis outputs;
4. the analysis package remains internally consistent after manuscript revision.

Detailed validation outputs and machine-readable records will be added to this directory as the repository is finalized.

## Analysis provenance

The repository separates:

- raw public source data
- reconstructed analytical data
- analysis scripts
- model outputs
- manuscript-facing results

This separation is intended to make each stage of the workflow traceable.

## Frozen analysis

The current repository is being prepared from the reproducibility package associated with the revised manuscript.

The frozen submission archive will be preserved separately from the GitHub-facing research repository so that the original analytical record remains unchanged.

## Planned contents

This directory will include:

- analysis taxonomy
- model registry
- validation summaries
- numerical consistency records
- file-integrity manifests
- final freeze information
