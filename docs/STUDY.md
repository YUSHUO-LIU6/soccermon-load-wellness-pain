# Study definitions and interpretation

**Associated manuscript:** Within-player load–wellness monitoring and lower-limb
pain in elite female football: a reproducible secondary analysis of the
SoccerMon dataset. PLOS ONE manuscript PONE-D-26-31950; revised manuscript under
review according to the supplied submission package. This repository does not
claim acceptance or publication.

## Data and outcome

The source contains two elite Norwegian women's football teams across
2020–2021. The theoretical calendar grid is 50 players × 731 days = 36,550
player-days. Under the 7-day washout, 92 lower-limb body-location episodes
collapse into 52 onset-days. Excluding onset-days during an ongoing episode
leaves 42 onset-days from 15 event players in 36,296 at-risk player-days.

The outcome is next-day onset of a **self-reported lower-limb pain/injury
episode**, not a clinically diagnosed injury. Body-location episodes and
player-day onsets are different quantities and must not be interchanged.

## Exposures

- Acute load: mean daily load over t−7 through t−1.
- Reference chronic load: mean daily load over t−28 through t−1, overlapping
  the acute window. The non-overlap sensitivity uses t−28 through t−8.
- Wellness: the most recent report in t−3 through t−1. Higher fatigue and
  soreness burden are `6 − score`; readiness deficit is `11 − score`.
- The reference within-player standardization uses the full retrospective
  observation period. The expanding-history sensitivity uses observations
  strictly before day t, with at least 10 prior observations and nonzero SD.

## Statistical scope

The analysis estimates associations, not prospective predictive accuracy or
causal effects. The frozen revision SAP and later R2 taxonomy remain separate.
They were not rewritten to match the portfolio presentation.

The soreness reference complete-case sample contains 19,758 days and 28
onset-days from nine event players. After backward-looking standardization,
it contains 19,216 days and 27 onset-days. The focal interaction attenuates
toward one under backward-looking standardization, while the chronic-load
estimate changes materially. This sensitivity and the sparse event set are
central to interpretation.

Team B has no complete-case onset event. Separation, failed/non-estimable
models, fallback levels and uncertain frailty estimates remain documented in
the frozen inventories. IPW is a sensitivity analysis: its effective sample
size and the retained lag-alignment limitation preclude claiming that it
eliminates selection bias. Multiple fits do not add independent event
information.

The portfolio figure shows the same Firth estimator and covariates for two
standardization schemes. Its profile-likelihood CIs are **not** player-cluster
bootstrap intervals. The schemes also differ in complete-case sample size.
Both the interaction and chronic-load parameter are shown to avoid presenting
only the attenuated interaction.
