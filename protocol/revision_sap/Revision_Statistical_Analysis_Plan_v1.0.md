# Revision Statistical Analysis Plan v1.0 (FROZEN)

**Manuscript:** PONE-D-26-31950 — Within-player load–wellness monitoring and lower-limb pain in elite female football (SoccerMon secondary analysis)
**Frozen:** 2026-07-22, before any revised inferential model is run. Hash recorded in `SAP_FREEZE_HASH.txt`.
**Drivers:** Academic Editor concerns E1 (variable polarity), E2 (overlapping positive days / recurrent-event dependence), E3 (protocol deviations), E4 (missingness), E5 (cross-file inconsistency). Frozen S3 protocol (OSF 10.17605/OSF.IO/UAFWQ) is the reference standard and is NOT edited.

## 1. Estimand

Primary estimand: the association between within-player deviations in lagged training load / wellness and the **odds of a new lower-limb self-reported injury/pain episode onset on day t**, expressed as odds ratios per +1 SD within-player deviation, among at-risk player-days. Explanatory, not predictive; no causal, clinical, or threshold claims.

## 2. Analysis unit and risk set

- Unit: at-risk player-day (calendar time scale).
- Outcome: `onset_day` = 1 if ≥1 new lower-limb episode onset occurs for that player on day t; same-day multi-location onsets merged into one onset-day.
- Risk set: 36,296 at-risk player-days; days during an ongoing episode (onset+1..end) excluded; recovery at end+1. Sensitivity: recovery at end+1+washout (36,019 days).
- Events: 42 onset-days from 15 of 50 players (7-day washout). Event concentration documented (highest contributor report retained as influence sensitivity).
- Body-location-specific episode counts (92) are descriptive; the old future 1–7 day risk-window outcome is demoted to exploratory descriptive analysis and will not be interpreted as independent episode risk or as prediction.

## 3. Exposures (all lagged, ending day t-1; no same-day information)

- Acute load: `acute_load_7d` = rolling mean of daily load over t-7..t-1.
- Chronic load: `chronic_load_28d` = rolling mean over t-28..t-1.
- Wellness: most recent report within t-3..t-1 (`_recent3`; implements the registered recent-window fallback; strict day t-1 lag as sensitivity).
- Canonical coding (Phase 5, VERIFIED): `fatigue_burden = 6 − fatigue`, `soreness_burden = 6 − soreness`, `readiness_deficit = 11 − readiness`; higher = worse than usual.
- Parameterisation: within-player z-scores (≥10 observations, player SD > 0) computed on burden/deficit and lagged load variables.

## 4. Model candidates and selection (technical criteria only; p-values never used for selection)

| ID | Model | Estimand/target | Dependence handling | Role |
|---|---|---|---|---|
| A | Discrete-time day-t recurrent onset model: binomial GLMM, logit, player random intercept + event-history terms | Conditional onset odds | Random intercept + event history | **Primary** |
| B | Andersen–Gill counting-process Cox model, cluster(player) robust SE | Marginal-ish onset rate ratio | Gap-independent increments + CRVE | Key sensitivity |
| C | PWP total-time Cox, cluster(player) | Rate ratio, total time | Stratum/term by event order | Sensitivity |
| D | PWP gap-time Cox, cluster(player) | Rate ratio, gap time | Stratum/term by event order | Sensitivity |
| E | Shared frailty Cox (`survival::frailty(player)` or coxme) | Conditional rate ratio | Gamma/Gaussian frailty | Sensitivity |
| F | Firth penalised logistic (logistf) + player-cluster inference | Small-sample-bias-reduced onset odds | Penalisation + CRVE/bootstrap | Small-sample sensitivity |
| G | Old risk-window GLMM | — | — | Exploratory descriptive only |

Acceptance criteria in priority order: (1) estimand correct; (2) no future information; (3) risk set definable; (4) recurrent dependence addressed; (5) identifiable/converges; (6) small-sample inference not over-optimistic; (7) protocol alignment; (8) interpretability. If A fails to converge or shows separation: apply the registered simplification order (remove interaction → remove chronic load if collinear → reduce wellness predictors in order fatigue then readiness → population-average cluster-robust model). Every fallback is reported.

## 5. Primary model (Model A)

```
onset_day ~ acute_load_7d_wp_z * soreness_burden_wp_z
          + chronic_load_28d_wp_z + prev_episode_ever + calendar_time
          + team + season + (1 | player_id)
```

- Prespecified interaction: acute load × soreness_burden (protocol §8).
- Alternative wellness models (same formula): fatigue_burden; readiness_deficit (protocol §10 wellness swap).
- Complete-case per model (reference analysis, protocol §11).
- Small sample: 42 events / 15 event players; parsimony enforced; events-per-parameter reported; Firth (Model F) reported alongside if events-per-parameter < 10 in any fitted model.

## 6. Inference

- Wald 95% CIs from fitted models; effect estimates emphasised over p-values.
- Player-cluster bootstrap (B = 2000, resampling whole players, seed 20260722) percentile CI for the primary interaction and primary acute-load term.
- Cluster-robust variance (player) for marginal/Cox models via clubSandwich/sandwich.
- Multiplicity: single prespecified primary interaction reported unadjusted; alternative wellness interactions and sensitivities labelled as secondary; no claim of confirmatory significance with 42 events.

## 7. Missing data (per frozen missing_data_plan.md)

- Reference: per-model complete-case.
- Key sensitivity: stabilised IPW (1st/99th percentile truncation) from per-variable observation models; diagnostics: weight percentiles, ESS, positivity; no "bias eliminated/corrected" wording.
- Multilevel MI: not implemented for primary inference (justification documented: 42 events, lag structure, non-random reporting); MNAR tipping-point: not quantitatively bounded from these data — qualitative limitation only.

## 8. Sensitivity analyses

1. Washout 3-day and 14-day episode definitions (same primary formula).
2. Risk-set recovery rule (end+1 vs end+1+washout).
3. ACWR (7/28 lagged) replacing acute load (protocol: sensitivity only).
4. Strict day t-1 wellness lag instead of recent3.
5. Exclusion of the highest-episode contributor.
6. Exploratory: old future 1–7 day risk-window GLMM (clearly labelled, no independent-risk interpretation).

## 9. Reporting rules

- ORs with 95% CIs; exact event counts, players, at-risk days per model; convergence/separation/frailty diagnostics; failed models and reasons reported.
- No causal language, no prediction/ML framing, no actionable thresholds, no clinician-diagnosis wording.
- All numbers in manuscript/tables/figures/response letter come from `master_results.csv/json` only.

## 10. Software

R 4.6.1: survival (AG/PWP/frailty), lme4 (GLMM), clubSandwich/sandwich/lmtest (CRVE), logistf (Firth), boot. Python 3.11.9 (embed): pandas/numpy/statsmodels for data build and observation models. Seeds fixed and recorded.
