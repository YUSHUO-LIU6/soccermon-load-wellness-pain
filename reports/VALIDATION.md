# Verification report

Verified 2026-10-21 (Asia/Shanghai). This report distinguishes fresh data/model
calculations from fresh checks of stored results.

## Completed

| Verification | Result |
|---|---|
| Imported source-file hashes | 101 verified |
| Recovered revision SAP | Original content hashes verified |
| Frozen structured results | 54 numerical consistency checks reexecuted; all PASS |
| Public raw ZIP | SHA-256 matches frozen source; supplied local copy used |
| Raw-to-analytical rebuild | Six derived files match frozen column fingerprints |
| R2 exposure reconstruction | Both non-overlap and historical-standardization datasets match frozen fingerprints |
| Diagnostic workstreams | Sample/event audit, sparse-data diagnostics, collinearity and exposure construction executed |
| Independent Firth refits | Two models; four focal OR/CI comparisons PASS |
| Portfolio figure | Source table/provenance included; PNG visually inspected |

The numerical fingerprints preserve row/column order and missingness; numeric
values are rounded to eight decimal places. They cover every column in the
eight checked datasets, not just the headline counts.

## Fresh focal model comparisons

| Model | Parameter | Refit OR | Profile-likelihood 95% CI | Result |
|---|---|---:|---|---|
| F | Interaction | 0.629552 | 0.445024–0.965067 | PASS |
| F | Chronic load | 0.947220 | 0.533212–1.718810 | PASS |
| F_hist | Interaction | 0.974084 | 0.727652–1.252043 | PASS |
| F_hist | Chronic load | 1.955454 | 1.208291–3.058183 | PASS |

`F` uses retrospective full-period standardization. `F_hist` uses only prior
observations. The maximum absolute discrepancy across these four ORs and all
eight CI endpoints was 8.88e-15; the predefined comparison tolerance was
0.001. This is numerical agreement for these two models, not validation of
every estimator or bootstrap interval.

## Environment

Fresh verification used Python 3.11.15 on Darwin arm64.
The focal R fits used R 4.5.2 and logistf 1.26.1; see
[`portable_R_session.txt`](../environment/portable_R_session.txt). The original
freeze records R 4.6.1 on Windows. `uv.lock` and the original session records
are retained separately. Version differences were not concealed.

## Remaining verification scope

The full R1/R2 model suite and all B=2,000 bootstrap procedures have **not**
been rerun in this portability pass. Their source scripts and frozen outputs
are included with explicit reproduction commands. Submitted DOCX tables and
binary TIFF figures have not been regenerated or compared pixel by pixel.
The earlier figure-generation script is retained, but this report does not
claim complete reconstruction of the final submission layout. The manual
wellness-polarity source audit was retained rather than repeated.

Historical raw/derived comparison gates are optional in the portable core
scripts and were not rerun using their old directory layout. The current
six-file reconstruction verification is a separate completed check.

Machine-readable evidence: [`validation_details.json`](validation_details.json)
and [`focal_refits.csv`](focal_refits.csv).
