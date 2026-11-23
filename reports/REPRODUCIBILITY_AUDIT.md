# Post-publication computational reproducibility audit

Audit date: 2026-11-23 (Asia/Shanghai). Baseline commit:
`3ddde51a62559787261accf4e20e143e616b0b73`.
Audit branch: `reproducibility/post-publication-audit-20261123`.

**Follow-up scientific assessment: READY WITH DOCUMENTED LIMITATIONS.**
Core scientific contrasts and all accepted Firth replicates have been verified.
Strict ancillary/QA discrepancies remain visible and are not converted to PASS.
The 39-test remote CI suite passed on the final code revision. The release
profile is recorded in [RELEASE_GATE.json](RELEASE_GATE.json); final branch
checks are verified again before merge. See
[FOLLOW_UP_VERIFICATION.md](FOLLOW_UP_VERIFICATION.md) for the current evidence.

## Research and publication information

Liu Y and Li H. *Within-player load-wellness monitoring and lower-limb pain in
elite female football: A reproducible secondary analysis of the SoccerMon
dataset*. PLOS ONE 21(11): e0362663, published 2026-11-13.
[Publication](https://doi.org/10.1371/journal.pone.0362663).
Source dataset: [SoccerMon](https://doi.org/10.5281/zenodo.10033832).
Registration: [OSF UAFWQ](https://doi.org/10.17605/OSF.IO/UAFWQ).
This audit concerns numerical reproducibility and release preparation. It
neither reselects models nor changes scientific results, the original
preregistration, frozen revision SAP or historical reference outputs.

## Reproducibility objectives and protected scope

The initial audit used an isolated clone of the clean baseline checkout.
Its 10 reachable commits, scientific inputs and original main branch were
preserved. The verified changes were subsequently integrated into the
GitHub-connected repository on the audit branch. Private branch/PR delivery
is separate from authorization for a public Release.

The baseline inventory contains 137 tracked files; the final proposed-file
scan covers 157 paths, including 20 new files. All 137 unique reachable
file blobs were scanned for publication risks; analytical source, runner,
protocol, dependency records, result structures and documentation were
reviewed by function. This inventory-wide scan is distinct from an assertion
that every line received a separate human-style review. The 101 imported
source/SAP hash records and frozen results remain unchanged. New calculations
reside only in isolated ignored execution roots.

## Source data and integrity

Only the cached public `subjective.zip` was supplied to the rebuild, after
verification of its expected 705,770 bytes and SHA-256
`338e9878fbed1f941cfc37b3f012cb356f97cc0f726e80a79aa5c8e67cc2a87c`.
The approximately 99 GB GPS release was not downloaded. The 50-player raw
structure produced 36,550 theoretical player-days and 36,296 at-risk days,
with 42 primary onset-days. The 7-day location-specific episode rule yields
92 lower-limb episodes and 52 unique onset-days before excluding onsets during
another ongoing episode. The soreness complete-case model has 19,758 days,
49 players and 28 onsets in nine event players.

Six reconstructed datasets match all frozen column fingerprints, preserving
column/row order and missingness with numeric hashing at eight decimals.
The non-overlap and backward-looking exposure datasets also match both frozen
fingerprints. These numerical targets were not used to overwrite records.
Exposure windows end before outcome day: acute t−7:t−1; chronic t−28:t−1;
non-overlap chronic t−28:t−8. Canonical burden coding uses 6−fatigue,
6−soreness and 11−readiness. Backward-looking standardization excludes day t
and future observations and requires ten prior observations. The source
polarity evidence is preserved manual evidence, not a newly validated
empirical polarity experiment.

## Computational environment

Python 3.11.15, R 4.5.2 and uv 0.11.31 ran on macOS 15.7.9, arm64. Python
packages came from unchanged `uv.lock` via `uv sync --frozen`. R setup installed
missing dependencies into `workspace/R/library` and reused existing packages
with their origins recorded. No system R installation was changed. Original
Windows/Python 3.11.9/R 4.6.1 records remain separate. lme4 and sandwich versions
in particular differ from the original freeze; their numerical impact is
assessed rather than concealed. See `environment/REPRODUCIBILITY.md` and the
machine-readable manifest for package versions and hashes.

Base seed is 20260722. Firth bootstrap initializes a continuous stream at
20260723 across the three wellness variants. Internal QA uses 20260902.
Unique timestamped logs and per-command UTC times, argv and exit statuses are
retained. `EXECUTION_MANIFEST.json` records artifact/input hashes and redacts
local account paths in public metadata.

## Analysis execution manifest

| Newly executed operation | Execution result | Numerical acceptance |
|---|---|---|
| Frozen source/SAP integrity | Completed, exit 0 | 101 source files; 54 stored-result checks PASS |
| Raw rebuild, independently in R1/R2 roots | Completed, exit 0 | Six fingerprints PASS in each root |
| Diagnostics/exposure sensitivity data | Completed, exit 0 | Both extra dataset fingerprints PASS in each root |
| Focused F / F_hist refits | Completed, exit 0 | Exact samples/events and all OR/CI endpoints PASS |
| Full R1 model/bootstraps/finalization | Completed, exit 0, 40 min 59 s | Partial agreement; E/readiness state mismatch and other strict differences |
| Full R2 sensitivity/final assembly | Completed, exit 0, 24 min 9 s | 678 master rows / 86 registry rows; strict differences retained |
| Manuscript figure script, portable execution copy | Completed, exit 0 | Five count gates PASS; four images visually inspected |
| Separate survival-version probe | Two completed fixed-formula fits | Same warning-bearing estimate; Windows failure not explained by survival alone |

The producer records are `workspace/audit/execution.jsonl`,
`workspace/r1_20261123/execution.jsonl` and `workspace/r2_20261123/execution.jsonl`.
R1 produced 251 master rows versus 243 frozen because E/readiness returned
eight additional coefficients; it did not overwrite the frozen 243-row result.
The manifest records all commands, statuses, selected versions and artifact
hashes. A completed process is not itself numerical acceptance.

## R1/R2 workflow verification

R1 full execution writes `RUN_PORTABLE` in its own root. R2 full execution uses
a separate independently rebuilt root and explicitly copied frozen R1
`RUN_R2_REPRO` baseline; only observation-weight input files are reconstructed
for its IPW stages. This is the original-baseline R2 rerun, not an end-to-end
fresh-R1 baseline substitution. Taxonomy/manual evidence are copied references.
The preserved reporting script also checked the obsolete `washout` field;
its actual input schema has `washout_days`. Unadapted, it would plot all
three washout definitions as a seven-day timeline. The portable execution copy
now selects the actual seven-day field, with independent 52-onset/15-player/
92-episode/45-maximum figure-data gates. The original reporting source remains
unchanged, and the transformation is explicitly recorded.

Original append/resume behavior is protected by one-use full-run claims;
existing full-run roots are refused rather than implicitly resumed or erased.

The staged R2 assembly omits two unused reads of historical validation CSVs
and creates missing output directories. This changes orchestration, not
analysis. Each staged source and transformation has recorded hashes. The
full original model specifications, failure/fallback logic, seeds, core
analytical source and frozen SAP are unchanged.

## Bootstrap verification

All six B=2,000 procedures actually ran: 12,000 attempts, 11,999 accepted under
the original operational rules and one failure. Summary estimates, percentile
CI endpoints and available replicate values agree with frozen references
under the unchanged Gate A policy. Marginal replicate tables each have exactly
2,000 unique IDs 0–1999; counts were checked against the saved summaries.

| Procedure | Requested / completed | Accepted / failed | Interaction median ratio (95% percentile CI) |
|---|---|---|---|
| R1 marginal soreness | 2,000 / 2,000 | 2,000 / 0 | 0.669743 (0.446747–1.107105) |
| R1 Firth soreness | 2,000 / 2,000 per execution loop/log | 2,000 / 0 | 0.655092 (0.439754–1.158569) |
| R1 Firth fatigue | 2,000 / 2,000 per execution loop/log | 2,000 / 0 | 0.867377 (0.618437–1.249460) |
| R1 Firth readiness | 2,000 / 2,000 per execution loop/log | 1,999 / 1 | 0.885021 (0.621235–1.251517) |
| R2 non-overlap, drop team | 2,000 / 2,000 | 2,000 / 0 | 0.740413 (0.556757–1.133109) |
| R2 drop team | 2,000 / 2,000 | 2,000 / 0 | 0.740098 (0.555581–1.132304) |

The Firth completion/acceptance evidence comes from actual loop completion,
execution logs and term-wise summaries, not independently retained individual
replicate estimates/IDs. The subsequent post-publication replay now supplies
6,000 saved traces and verifies convergence of all accepted replicates; it does
not recover the historical unsaved traces.
Original marginal-logit bootstraps are whole-player fixed-formula fits, not
2,000 mixed-effect refits.
The historical scripts explicitly did not run 2,000 glmer fits; this audit
does not relabel them. Firth summary acceptance counts do not prove every
replicate converged: the original IRLS returns success after exhausting its
iteration limit and the Firth acceptance loop does not check its convergence
flag. It also saves no per-replicate Firth estimates/IDs. These are retained
implementation limitations, not repaired silently to alter published results.
A separate corrected-algorithm sensitivity would require an explicitly
identified post-publication estimand/implementation record.

## Fresh-versus-frozen comparisons

Focused Firth refits pass exact N/events and the pre-existing absolute 0.001
criterion for all four ORs and eight profile-likelihood CI endpoints:

| Model / parameter | Fresh OR | Profile-likelihood 95% CI | N / events |
|---|---:|---|---|
| F / load × soreness | 0.629552 | 0.445024–0.965067 | 19,758 / 28 |
| F / chronic load | 0.947220 | 0.533212–1.718810 | 19,758 / 28 |
| F_hist / load × soreness | 0.974084 | 0.727652–1.252043 | 19,216 / 27 |
| F_hist / chronic load | 1.955454 | 1.208291–3.058183 | 19,216 / 27 |

Maximum absolute difference across these focused values/endpoints is
8.89e−15. This is evidence for those two models, not all models or bootstrap
intervals. Broader tables use the historical Gate A criterion,
`abs(a-b) <= max(1e-8, 1e-6*max(abs(a),abs(b)))`; counts, keys, missingness and
states remain exact. `RESULT_COMPARISON.csv` contains field-level PASS, FAIL,
BLOCKED and NOT RUN outcomes. Optional `NUMERICAL_DISCREPANCIES.csv` records
each differing cell. No frozen value or acceptance threshold was altered.

## Numerical discrepancies

The initial verifier recorded 791 gates (678 PASS, 95 FAIL, 1 BLOCKED,
17 NOT RUN). With the separate Firth replay evidence, the current verifier
records **821 gates: 709 PASS, 95 FAIL, 0 BLOCKED, 17 NOT RUN** (exit status 1). These are gates, not counts
of independent models or failed fits. A 2,411-cell discrepancy ledger and
grouped summary preserve all compared-cell differences. Final checks identify tie-dependent player ranks and
cumulative event shares, plus platform/version-sensitive mixed-model fits.
The event-rank code sorts equal counts without a stable secondary key; ranks
and intermediate cumulative shares can differ while keyed event counts
remain equal. Such rows are retained as FAIL under exact comparison rather
than ignored. Optimizer-dependent rejected fits and warning text also remain
in scope; they are not evidence that all primary estimates changed.

The frozen non-overlap diagnostic table contains four duplicated DATA records
(29 rows versus 25 in the clean rerun), and the frozen backward-looking table
contains three duplicated DATA records (55 versus 52). Their duplicated values
are identical to the single clean-run values. This is consistent with the
original append/resume behavior; exact duplicate multiplicities remain FAIL
rather than being silently deduplicated or described as missing analysis.
All distinct diagnostic keys are present in both completed R2 tables.

A material R1 estimation-state discrepancy remains: frozen Model E/readiness
failed ("No starting estimate was successful"), whereas the macOS execution
returned eight coefficient rows and the historical script marked it OK.
It also issued "Inner loop failed to coverge for iterations 1"; returned
coefficients and the script's unconditional `converged=TRUE` field do not
establish convergence. Thus new R results have 223 rows versus 215 frozen,
and sample inventory 27 versus 26. A separately labeled dependency probe
loaded the exact frozen survival 3.8-6 in another project library and refitted
the identical formula/data: both survival 3.8-3 and 3.8-6 returned the same
coefficients/warning under macOS/R 4.5.2. Changing this dependency alone did
not reproduce the Windows failure. The remaining platform/R/numerical cause
is not isolated. Neither the historical failure nor the new warning-bearing
estimates were overwritten. See `FRAILTY_VERSION_PROBE.json` and its reusable
`scripts/probe_frailty_version.R`; this diagnostic is not a new selected
scientific model or a replacement for the completed reference workflow.

## Sensitivity analyses and published-source comparison

The R2 process completed in 24 minutes 9 seconds with exit status 0. All
original sensitivity stages executed, including 153 leave-one-event-player-out
rows, event concentration, final IPW and multiplicity/registry assembly. Its
678-row main table and 86-row registry include explicitly copied frozen R1
reference rows; they are not 678 newly fitted models. Numerical acceptance
remains separate: R2 Firth coefficients and bootstrap summaries match within
the existing tolerance, while optimizer-dependent results/diagnostics and
tie-dependent event ranks retain FAIL outcomes. Source comparison is independently complete:
623 selected published numeric displays agree with frozen structured values
at printed precision. The corrected local/S2 mapping finds 91 exact files,
five documented portable core adaptations and five additional local records.
The authenticated GitHub CLI verifies the private remote main commit and
all 137 file-blob hashes equal the inspected local baseline. The connector's
404 was resolved through this authenticated read-only fallback.

The registered OSF PDF is byte-identical to published S3. OSF structured
answers and that attachment nevertheless contain different qualifications of
interaction primacy, fallback detail and sensitivity coverage. The audit
retains both; final Firth emphasis and R2 sensitivities must not be described
as original preregistered primary inference. See `PUBLICATION_SOURCE_AUDIT.md`,
`S2_REPOSITORY_COMPARISON.json` and `PUBLISHED_FROZEN_COMPARISON.csv` for scope.

## Figure verification and software validation

The four generated figures (timeline, episode concentration, conditional Firth
curves and estimator forest) were visually inspected. Timeline source data
contain 52 unique player-dates; episode bars contain 15 event players, total
92 and maximum 45 episodes. `FIGURE_DATA_CHECKS.json` records all five PASS
count gates. The timeline uses different anonymous player ordering and layout
from the publisher; exact label/layout reproduction is not claimed. The
conditional curves match the published Fig 3's scientific shape and parameter
scale. Their 363 grid-by-soreness values are now retained in `Fig3_curves.csv`
alongside the fitted coefficients and fixed calendar-time offset. Logistic OR
and Cox HR are explicitly distinguished in the staged mixed-estimator forest
axis label; no numerical estimate is changed by this presentation correction.

The acceptance-tool JSON Path-label defect found against the full R2 master
was repaired and covered by a nested-result regression test. **39 local unit
tests passed**; Python compilation and `git diff --check` passed. CFF 1.2.0
schema validation passed after using the supported electronic-page field.
The data-free GitHub Actions workflow ran successfully on Linux, including
the 39 tests, frozen-source checks, exported replicate reconstruction and
Python compilation. It downloads no raw monitoring data and refits no models. Tests certify software gates and source integrity;
they do not establish statistical model validity or clinical performance.

## Known limitations

These are self-reported symptom episodes, not clinician-confirmed injuries.
Models estimate associations; they do not establish causality, prospective
prediction performance or actionable thresholds. Full-period scaling uses
future observations. The backward-looking sensitivity materially changes the
interaction and chronic-load estimates and also changes the eligible sample.
Team separation, nine complete-case event players, concentration of events,
season imbalance, missing wellness data and IPW lag/alignment/model assumptions
remain limitations. IPW does not establish removal of selection bias.

Historical Gate A/B checks of 217/33 rows were not newly rerun merely because
their stored reports were copied into the frozen integrity test. The six/two
fingerprint tests are separate newly executed checks. Publisher page layout,
all submission tables and all figure pixels are not certified by this audit.
PNG/SVG byte equality is inappropriate across platforms; figure evaluation
must use source data, model coefficients, content and visual inspection.

## Remaining blockers and public-release safety

All requested historical workflows completed. The follow-up replays only the
three Firth streams whose individual records were missing. A separate
fresh-R1-baseline substitution into R2 was not executed and is not claimed.

The previous fresh-replicate BLOCKED finding is resolved: all 6,000 recorded
Firth attempts meet the original step tolerance, and all 5,999 accepted fits
reproduce the prior 27 term summaries. The readiness rejection remains intact.
The historical iteration-limit flag bug remains in preserved source, but it
did not affect accepted replicates in this replay.

The 95 strict FAIL gates are individually classified: 68 estimation/optimizer,
16 small numerical drift, 8 ordering/duplicate structure, 3 annotations, and
zero protected-contrast discrepancies. No tolerance was relaxed. Gamma-frailty
and joint team/season-removal QA fits remain unverified and must not support
new scientific inference. The additional diagnostics explain their numerical
instability without selecting a more favorable model. Independent finite
numerical derivatives are themselves imperfect; global optimality is not
claimed. These are documented limits on ancillary interpretation rather than
an unexplained change to the primary Firth/bootstrap findings.

The author authorized MIT for project-owned code and confirmed that the first
private commit's local-account identity contains no credentials and may be
public. Existing history is preserved; subsequent commits use the verified
GitHub identity. Remote CI passed; the final release profile records the remaining scientific
limitations and the verified rights/privacy decisions.

No credential candidate, raw archive,
installed environment or large output was detected among the inspected
reachable Git blobs. Existing frozen player-linked health summaries, source
UUIDs, one historical account-path comment and Git identity metadata are
explicitly disclosed in `PUBLICATION_SAFETY.md`. DataCite supplies the source
CC BY 4.0 rights metadata; `docs/DATA_REUSE.md` adds attribution and change
notices. MIT was added after explicit rights-holder authorization; third-party terms
remain separate.
Private branch and PR delivery occurred after the initial audit. No raw or
frozen scientific record or historical commit was altered; no force push was
used. Public release is governed by the recorded final release gate.

## Final reproducibility verdict

**READY WITH DOCUMENTED LIMITATIONS** is the final release assessment. Remote
CI passed, and licensing/privacy decisions are resolved. The raw rebuild, protected
Firth contrasts, all six original bootstrap procedures and the added Firth
replicate replay are verified. Exact universal cross-platform equality and
ancillary-model convergence are not claimed. The retained strict failures,
original failures, new warning-bearing returns and provenance remain available
for inspection. No result or threshold was changed to manufacture PASS.

## Proposed changes and author decisions

The initial audit changed nine tracked files and proposed twenty new files.
The follow-up adds replicate evidence, scientific-impact and model-status
assessment, numerical diagnostic tools, approved licensing and tested CI. Documentation
now cites the published article and separates registered/SAP/R1/R2/audit layers;
the runner isolates full executions and records commands, libraries and source
adaptations; fresh acceptance tests, a frailty dependency probe, data-free CI,
source/data attribution, citation metadata and audit evidence were added.
`reports/VALIDATION.md`, all frozen outputs, original analytical source, SAP,
`pyproject.toml` and `uv.lock` remain unchanged. The original audit patch was checked before being applied once to the clean
GitHub-connected checkout. Execution evidence was copied locally without
rerunning the completed workflows; workspace data, environments and logs
remain excluded from Git. Main-branch scientific history was preserved.

The author explicitly authorized the MIT license and the historical identity
disclosure. The follow-up scientific diagnostics are documented separately
from the original registered/SAP analyses. The current instruction authorizes
normal GitHub delivery, merge, Release and public visibility only after the
release gate passes; no additional authorization is inferred from data access.
