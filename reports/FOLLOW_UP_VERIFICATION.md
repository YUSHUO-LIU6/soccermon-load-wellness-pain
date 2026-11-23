# Follow-up verification and scientific impact assessment

2026-11-23. Baseline scientific archive: `3ddde51`. No frozen data, SAP,
model formula, historical estimate or numerical acceptance tolerance changed.
The initial audit evidence was integrated into the GitHub-connected work branch
once; completed raw rebuilds and full R1/R2 runs were reused.

## Retained strict differences

The 95 strict FAIL gates remain FAIL. They are classified individually in
`FAIL_IMPACT_CLASSIFICATION.csv`: A (protected main contrast), 0; B (estimation
state/optimizer sensitivity), 68; C (small numerical drift), 16; D (ordering or
duplicate structure), 8; E (annotation), 3. `ESTIMATE_IMPACT.csv` checks 145
changed matched estimates rather than assuming every numeric difference is
harmless. These classifications do not convert exact comparison failures to
PASS or alter the pre-existing Gate A tolerances.

Core Firth, non-overlap/drop-team/backward-looking Firth and all six bootstrap
summaries retain their numerical agreement. No protected scientific contrast
has a recorded strict discrepancy. Inferences remain associational and apply
to self-reported symptom onsets, with no clinical-diagnosis, causal or validated
prediction claim.

## Frailty and internal QA

Gamma frailty Model E emitted inner-loop convergence warnings in the frozen
soreness/fatigue fits and the current fits. Readiness failed in the freeze but
returns warning-bearing coefficients on this machine. The archived
`converged=TRUE`/OK labels do not certify convergence. The current soreness
acute-load frailty interval changes from 0.244–1.117 to 0.218–0.999; interpreting
this borderline ancillary result as new evidence would be unjustified.
All Model E variants remain unverified for interpretation. Original failure
records and both sets of returned coefficients are retained.

A controlled survival-version probe did not isolate the Windows/macOS failure
cause: survival 3.8-3 and 3.8-6 returned identical warning-bearing estimates on
macOS/R 4.5.2. No scientifically preferred alternative was selected.

The joint team/season-removal GLMM is internal QA, excluded from the published
scientific model-space denominator. Its previous-event OR changes from 1.595
to 0.670 while both wide intervals include one. The same fixed formula was
refitted only for post-publication diagnostics. Default initialization returned
log likelihood −175.41085; initialization from the frozen fixed effects returned
−176.30942 and a previous-event OR of 1.825. Neither replaces a published result.
The local lme4 2.0-1 control has `calc.derivs=NULL` and a 10,000-observation
convergence-check limit; stored derivative diagnostics were absent at N=19,758.
Thus optimizer code 0 and absent warnings cannot establish stationarity.
Richardson finite differences reproduced each stored deviance but returned an
indefinite Hessian and non-small gradients. These checks support numerical
instability, not a global-optimum certificate: finite-difference derivatives
can themselves be unreliable, as discussed in the [lme4 convergence guidance](https://lme4.github.io/lme4/reference/convergence.html).

`MODEL_DIAGNOSTIC_ASSESSMENT.csv` is a conservative overlay: historical failure
stays failure; warning-bearing returns remain unverified; missing derivatives
and optimizer code 0 are not automatically certified. Its regression tests
cover precisely these cases. The raw historical status fields are unchanged.

## Replicate-level Firth evidence

Only the three Firth bootstrap streams were replayed to fill the missing
replicate-trace evidence. The other three B=2,000 procedures and full model
suites were not rerun. The replay is explicitly POST_PUBLICATION_VALIDATION.
It extracts the preserved numerical functions and adds observation-only return
callbacks. Unit tests verify bit-identical coefficient returns and the honest
recording of singular and iteration-limit termination. RNG seed 20260723 runs
continuously through soreness, fatigue and readiness, as in the archived code.

`FIRTH_REPLICATE_DIAGNOSTICS.csv` contains 6,000 unique variant/replicate records,
iteration counts, terminal steps, original acceptance/rejection, termination
reasons and all nine coefficients. It contains no sampled player identifiers.
All 6,000 attempts met the original 1e−9 step criterion. The original acceptance
rule retained 2,000 soreness, 2,000 fatigue and 1,999 readiness fits; the remaining
readiness fit was rejected by the unchanged coefficient-magnitude limit.
No accepted fit exhausted the iteration limit or had nonfinite coefficients.
The latent historical success-flag bug was therefore not triggered among this
run's accepted replicates, but remains documented in the preserved code.

All 27 term summaries agree with the previous fresh results. The verifier also
independently reconstructs medians, percentile endpoints and SDs from the saved
individual coefficients. The previous fresh-trace BLOCKED gate is resolved;
this does not recover or relabel unrecorded historical traces.

The updated strict comparison has **821 gates: 709 PASS, 95 FAIL, 17 NOT RUN,
0 BLOCKED**. The 17 exclusions concern historical/manual evidence and prose,
session or lock-byte comparisons, not omitted requested statistical procedures.

## Rights, privacy and delivery

The rights holders authorized MIT for project-owned code with the approved
copyright attribution. Data and published materials retain their own terms.
The author reviewed the initial private commit's automatic local-account
identity and confirmed it contains no credentials and may be disclosed.
Subsequent commits use the verified GitHub identity. Existing history is
preserved without force push. Runtime data, model objects, libraries and logs
remain ignored; only diagnostic summaries and non-identifying replicate
coefficients are included. Remote Linux CI passed 39 tests, including reconstruction of frozen summaries
from the exported traces without raw inputs. RELEASE_GATE.json records
READY WITH DOCUMENTED LIMITATIONS; strict numerical differences remain
visible in the release.
