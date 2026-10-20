# VALIDATION REPORT — R2_FINAL_ANALYSIS_FREEZE (PONE-D-26-31950)

Date: 2026-09-02 | Generated with `20_FREEZE/build_validation.py` | Machine-readable copy: `VALIDATION_REPORT.json`
Cross-file evidence: `NUMERIC_CONSISTENCY_CHECK.csv` — **54 checks, 0 FAIL**.

## 1. Data integrity — PASS
Gate B raw rebuild of `00_INPUT_SNAPSHOT/subjective.zip`: 50 players × 731 days = 36,550 player-day grid, 0 duplicate player-dates; injury parsing reproduces all expected counts (306 body-location entries, 295 lower-limb, 230/76 minor/major, 11 body parts); episode rebuild counts validated (7d: 101/92/22 all/lower-limb/knee); all 25 compared columns EXACT MATCH vs the old derived table; `RAW_VS_DERIVED_RECONCILIATION.csv` 33/33 MATCH, max abs diff 0.0.

## 2. Temporal integrity — PASS
- Exposures are lagged: all analysis windows end at t-1 (acute t-7..t-1, chronic t-28..t-1).
- Non-overlap variant: chronic t-28..t-8 is disjoint from acute t-7..t-1 — `08_NONOVERLAP_WINDOW/NONOVERLAP_QA.txt` 4/4 PASS (brute-force max|diff| = 0; missingness pattern identical to R1 chronic; CC N identical 19,758).
- Backward standardization: baselines use only history strictly before day t, min 10 prior observations — `11_BACKWARD_STANDARDIZATION/BACKWARD_Z_QA.txt` 19/19 PASS (12 brute-force variable checks max|diff| = 0; bit-identical determinism; min-obs rule enforced per variable). No day-t leakage.

## 3. Polarity integrity — PASS
`12_POLARITY_AUDIT/`: all 7 wellness codings CONSISTENT with independent external anchors, all HIGH confidence, outcome data never used in any coding decision (NUMERIC_CONSISTENCY_CHECK POL-01 PASS). Open documentation discrepancies (soreness panel not visible in descriptor Fig. 2 — anchors via Jarmann 2023 Table 2.1; descriptor Table 1 stress-range typo; Smolarski thesis not anonymously downloadable) are recorded and non-load-bearing.

## 4. IPW integrity — PASS
With-onset variant reproduced exactly: independent obs-model refit max|diff| = 1.8e-15 on both weight columns; R weighted-glm refit reproduces frozen master rows bit-for-bit (dOR = 0.0). Weight-key uniqueness, lag-lookup identity, truncation at recomputed 1/99 percentiles (max|diff| ≤ 5.6e-17), and Python/R ESS agreement all PASS for both variants. Documented caveat (≈15.8% of CC rows reference a lag day without a raw report of that variable) is inherent to the R1 design and identical across variants.

## 5. Model integrity — PASS
- 1 failed fit recorded, not omitted: Model E readiness (coxph gamma frailty + coxme fallback: "No starting estimate was successful"). E soreness/fatigue converged with frailty variance NA.
- All separation-driven ladder rejections (teamTeamB, |β| > 10) are registered as REJECTED-level rows and retained in master results.
- Cox aliasing documented: B (calendar_time, season2021), C (+ prev_episode_ever), D (prev_episode_ever).
- 3 logistf maxit=25 warnings resolved by maxit=200 refits (max|Δlog OR| ≤ 1.25e-05; rows unchanged).

## 6. Cross-file consistency — PASS
`NUMERIC_CONSISTENCY_CHECK.csv`: 54/54 PASS. Every number cited in `R2_FINAL_ANALYSIS_REPORT.md` was verified programmatically against its source file (sample counts, correlations, VIF/κ, all interaction ORs/CIs/p across workstreams, IPW weights/ESS, event-concentration shares, LOO range, registry↔master identity, duplicate-key check).

## 7. Gate status
- Gate A (R1 reproduction): **PASS** — 0 FAIL of 217 checks (`19_VALIDATION/R1_REPRODUCTION_CHECK.csv`).
- Gate B (raw rebuild): **PASS** — 33/33 MATCH (`19_VALIDATION/RAW_VS_DERIVED_RECONCILIATION.csv`).

## 8. Prompt-vs-archive discrepancies (documented; NOT R1 defects)
1. The freeze plan's claimed R1 IPW numbers (soreness/fatigue/readiness interaction ORs 0.833/0.930/1.035; max weights 219–224; truncation 8.0–8.2; ESS 44–45%) do not exist anywhere in the locked R1 outputs. Actual locked values: 0.6464/0.8012/0.9184; max w_stab ≈ 11.24–11.26; truncated max ≈ 10.62–10.67; ESS/CC ≈ 0.36, ESS/all-rows 0.534. (GAP-01 PASS: claimed values absent.)
2. The claimed run id `RUN_20260728_FINAL` does not exist; the locked reference run is `RUN_20260722_151418`. (GAP-02 PASS.)

## 9. Known unmapped items
The R2-round decision letter is not present in the freeze workspace. Reviewer-4 points #1–#4, #9, #10 and Reviewers R1/R3 have no attributable computational output in this freeze; they are marked UNMAPPED_PENDING in `20_FREEZE/EDITOR_REVIEWER_COMPUTATIONAL_RESPONSE_MAP.csv` and must be mapped against the decision letter before the response letter is drafted.

## Overall verdict
**PASS** — all integrity domains pass; 54/54 consistency checks PASS; the backward-standardization attenuation is a substantive finding to report prominently, not a validation failure.
