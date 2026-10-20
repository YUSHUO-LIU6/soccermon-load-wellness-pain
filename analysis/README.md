# Analysis

`core/` contains the repository's portable versions of the five R1 analytical
scripts. Optional historical-reference comparisons are logged as skipped if
the old files are not supplied. The current six-file rebuild verification is
separate and required.

`sensitivity/` contains original frozen R2 scripts. They retain original path
constants to preserve source identity. Use `scripts/pipeline.py`, which stages
working copies and relocates those roots. Do not run the archived scripts
directly on another machine.

`reporting/06b_make_figures.py` preserves earlier submitted-figure code for
provenance. Use `scripts/pipeline.py plot` for the current portfolio figure.

See [reproduction steps](../docs/REPRODUCING.md) and
[study definitions](../docs/STUDY.md). Model formulas, estimands, inference
units and original seed 20260722 are retained.
