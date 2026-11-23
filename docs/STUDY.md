# Study definitions and interpretation

**Published article:** Liu Y, Li H (2026). Within-player load-wellness monitoring
and lower-limb pain in elite female football: A reproducible secondary analysis
of the SoccerMon dataset. *PLOS ONE* 21(11): e0362663.
[DOI 10.1371/journal.pone.0362663](https://doi.org/10.1371/journal.pone.0362663).
Published 13 November 2026.

## Data and outcome

The public source contains 50 anonymized players from two elite Norwegian
women's football teams during 2020–2021. A common calendar grid contains
50 × 731 = 36,550 player-days. Under the 7-day episode rule, 92 lower-limb
body-location episodes collapse into 52 unique onset-days. Removing onset-days
during another ongoing episode leaves 42 onset-days from 15 event players
in 36,296 at-risk player-days. These are validation targets rather than
hard-coded reconstruction inputs.

The outcome is onset on index day t of a **self-reported lower-limb pain/injury
episode**, with exposures ending before t. It is not a clinician-confirmed
injury. Reports at the same exact body location no more than seven days apart
are merged; left/right locations are separate. Multiple locations starting on
the same player-day count as one onset-day. Ongoing episode days after onset
are excluded, with reference re-entry after the last report. A stricter
end-plus-washout re-entry rule is a sensitivity analysis.

## Exposure definitions

- Acute load: mean daily load over t−7 through t−1.
- Reference chronic load: mean over t−28 through t−1. The post-SAP non-overlap
  sensitivity uses t−28 through t−8.
- Wellness: most recent available report in t−3 through t−1; strict t−1 is a
  sensitivity analysis.
- Canonical burden coding: `fatigue_burden = 6 − fatigue`,
  `soreness_burden = 6 − soreness`, `readiness_deficit = 11 − readiness`.
  Instrument polarity was assessed independently of outcome associations.
- Reference within-player z-scores use the full retrospective observation
  period, at least ten observations and non-zero SD. Backward-looking z-scores
  use only observations strictly before t, with at least ten prior
  observations and non-zero sample SD.

The source daily-load field supplies a value on every calendar day. Zero load
cannot reliably distinguish a rest day from an unreported training day; this
uncertainty is retained.

## Analysis hierarchy

| Layer | Definition and distinction |
|---|---|
| Original OSF protocol, 29 May 2026 | Player-specific first/last observation windows; joint wellness main-effects model with player random intercept; acute load × soreness focal interaction; fallback and sensitivity rules. [Published unchanged protocol](https://doi.org/10.1371/journal.pone.0362663.s015). |
| Frozen revision SAP, 22 July 2026 | Separate wellness model families; intended primary player-random-intercept logistic model A, Firth companion F, explicit recurrent-onset risk sets. The historical files and hashes remain unchanged in `protocol/revision_sap/`. |
| R1 reference reanalysis | Implemented common calendar grid, model-specific complete cases and full-period within-player standardization. Sparse events and separation led final interpretation to emphasize Firth and separate whole-player bootstrap uncertainty. |
| Later R2 analyses | Post-SAP non-overlap window, team/season removal, backward-looking scaling, no-outcome IPW observation model, influence/event concentration and multiplicity census. These are not presented as original preregistered analyses. |
| Post-publication audit | Software portability, integrity checks and fresh-versus-frozen numerical verification. These checks do not modify the scientific estimand or plan. |

The [published S10 reconciliation table](https://doi.org/10.1371/journal.pone.0362663.s012)
discloses the common-grid deviation, separate wellness variants, estimator
prioritization and the non-executable zero-versus-missing load sensitivity.
Neither the original protocol nor the SAP was rewritten to match the results.

The registered PDF and published S3 are byte-identical. The OSF structured
answers contain additional qualifications: interaction analyses are described
as secondary/exploratory unless event information permits stable estimation;
the attached protocol retains main effects as primary if the interaction model
is unstable. The structured answers and attachment also differ in fallback
detail and sensitivity coverage. See the [source audit](../reports/PUBLICATION_SOURCE_AUDIT.md).
The final focal interaction emphasis must not be read as an unqualified
original preregistered primary interaction claim.

## Statistical scope and limitations

The soreness reference complete-case sample contains 19,758 days from 49
players and 28 onset-days from nine event players. Backward-looking scaling
retains 19,216 days and 27 onsets. The same Firth specification includes acute
load × soreness, chronic load, previous episode history, calendar time, team
and season. Model-based profile-likelihood confidence intervals contain no
player random effect or cluster adjustment; whole-player B=2,000 bootstrap
percentile intervals are a separate uncertainty assessment.

The full-period focal Firth interaction is approximately OR 0.63
(profile-likelihood 95% CI 0.45–0.97); bootstrap intervals include one.
Backward-looking scaling yields approximately OR 0.97 (0.73–1.25), while the
chronic-load estimate changes to about OR 1.96 (1.21–3.06). The change in
parameterization also changes the complete-case sample. These results do
not establish a protective interaction or a causal chronic-load effect.

Team B has no complete-case onset, and events are concentrated by player and
season. Failed/non-estimable fits, fallback levels, aliased coefficients and
uncertain frailty estimates remain in the frozen registries. More overlapping
models do not increase independent event information.

IPW is a sensitivity analysis. Strong observation-model assumptions,
positivity/weight tails, reduced effective sample size and a retained
lag-alignment mismatch prevent interpreting it as removal of missing-data or
selection bias. A recent-3-day exposure may originate on t−2 or t−3 while the
weight's reporting indicator refers to t−1.

These are associational analyses of self-reported monitoring data, without
causal identification, validated prospective prediction performance or a
clinical decision threshold. Full-period standardization uses future
observations and cannot be deployed in real time as specified. Findings are
limited by two teams, two seasons and absent demographic/clinical metadata.

## Reproduction records

[Published S2](https://doi.org/10.1371/journal.pone.0362663.s014) contains
historical source, derived inputs, results and logs. This repository preserves
a portable subset with source hashes and intentionally omits raw archives and
local environments. A new run is only considered verified when the relevant
acceptance checks pass; stored-result validation is not evidence that models
or bootstrap samples were newly calculated. See
[REPRODUCING.md](REPRODUCING.md) and the
[current audit](../reports/REPRODUCIBILITY_AUDIT.md).
