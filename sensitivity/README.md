# Sensitivity and Robustness Analyses

This directory contains the sensitivity, robustness, and internal QA analyses used alongside the core SoccerMon analysis.

The public-facing scripts are derived from the frozen manuscript-revision workflow. Workstation-specific absolute paths are replaced with project-relative workspace paths while preserving the intended study definitions and statistical logic.

## Included workstreams

The sensitivity workflow includes:

- sample and event audit
- sparse-data diagnostics
- acute–chronic load collinearity assessment
- non-overlapping exposure-window analysis
- drop-team sensitivity
- season stability analysis
- backward-looking within-player standardization
- inverse-probability-weighting analyses
- event concentration analysis
- leave-one-event-player-out analysis

## Default workspace

Scripts stored in `analysis/sensitivity/` use the repository workspace by default:

```text
<repository>/workspace/
