# WELLNESS_POLARITY_EVIDENCE.md — Independent polarity audit of SoccerMon/PmSys wellness variables

Workstream: polarity-provenance, PLOS ONE R2 reproducibility freeze (Reviewer 4, comment #8).
Date of evidence access: 2026-09-02 (UTC). Note: the workstream brief stated "today: 2026-09-01";
the actual system date at access time was 2026-09-02 (verified via shell `date`); 2026-09-02 is used
throughout for honesty. Companion table: `WELLNESS_POLARITY_INDEPENDENT_AUDIT.csv`.

**Decision rule (Reviewer 4 #8):** polarity of each wellness variable must be justified by
evidence INDEPENDENT of the study outcome. No injury/pain-onset data, model coefficients,
p-values, or exposure–outcome correlations were used in any coding decision
(`outcome_data_used = NO` for every row of the CSV). Empirical inter-correlations among
SoccerMon variables were NOT used as decision evidence; they appear only in the clearly
labelled post-hoc QA section at the bottom.

---

## 1. Provenance check — what the R1 pipeline actually does

Verified in code (read-only inspection of the R1 tree; no files modified there):

- `PONE-D-26-31950_PLOS_R1/06_ANALYSIS_CODE/02_episodes_and_modeling_data.py`
  - Lines 28–30 (module docstring, frozen Phase-5 conventions):
    `fatigue_burden = 6 - fatigue (1-5 scale)`; `soreness_burden = 6 - soreness (1-5 scale)`;
    `readiness_deficit = 11 - readiness (1-10 scale)`.
  - Lines 341–346 (`part_c`): literal implementation on the already-lagged exposure columns:
    `df["fatigue_burden_lag1"] = 6 - df["fatigue_lag1"]`,
    `df["fatigue_burden_recent3"] = 6 - df["fatigue_recent3"]`,
    `df["soreness_burden_lag1"] = 6 - df["soreness_lag1"]`,
    `df["soreness_burden_recent3"] = 6 - df["soreness_recent3"]`,
    `df["readiness_deficit_lag1"] = 11 - df["readiness_lag1"]`,
    `df["readiness_deficit_recent3"] = 11 - df["readiness_recent3"]`.
  - Lines 352–358: within-player z-scores computed on the BURDEN/DEFICIT variables
    (`(x - player mean)/player SD`, ddof=1, >=10 non-missing obs, SD>0).
  - Lines 607–608 (generated `risk_set_definition.md`): "Canonical direction:
    `fatigue_burden = 6 - fatigue`, `soreness_burden = 6 - soreness`,
    `readiness_deficit = 11 - readiness` (higher = worse)."
- `PONE-D-26-31950_PLOS_R1/03_VARIABLE_AUDIT/variable_transformations.md` lines 13–15: same three
  formulas; line 7 states "All PmSys 1-5 items are scored so that HIGHER = BETTER state"; lines 8–9
  record that the original submission had interpreted fatigue in the wrong direction.
- `PONE-D-26-31950_PLOS_R1/03_VARIABLE_AUDIT/canonical_variable_dictionary.csv` rows 2–4:
  anchors and reverse-coding flags for fatigue / readiness / soreness (status VERIFIED).
- `PONE-D-26-31950_PLOS_R1/06_ANALYSIS_CODE/phase5_variable_polarity_audit.py` lines 14–22:
  the hard-coded anchor table used to generate the dictionary (fatigue 1=Very tired/5=Very fresh;
  readiness 1=Not ready at all/10=Can't wait!; soreness 1=very sore/5=feeling great "(prototype)").
- `PONE-D-26-31950_PLOS_R1/01_DECISION_MATRIX/decision_to_action_matrix.csv` row E1: the Academic
  Editor's direction complaint and the mandated fix (`fatigue_burden=6-fatigue;
  soreness_burden=6-soreness; readiness_deficit=11-readiness`).

**Scale-bound QA on raw data (provenance only — not outcome association):** observed min/max in the
read-only raw wellness files
(`PONE-D-26-31950_PLOS_R1/02_RAW_DATA/subjective_readonly_work/subjective/wellness/*.csv`):
fatigue 1–5 (n=16,992), soreness 1–5 (n=16,999), readiness 1–10 (n=16,997), mood 1–5 (n=16,999),
stress 1–5 (n=16,997), sleep_quality 1–5 (n=16,994), sleep_duration 1–12 h (n=16,981).
These confirm the recorded scale maxima used in the 6-x / 11-x transforms.

---

## 2. Independent evidence used for the coding decision

### Source register (all accessed 2026-09-02)

- **S1 — SoccerMon Scientific Data descriptor.** Midoglu et al. 2024, "A large-scale multivariate
  soccer athlete health, performance, and position monitoring dataset", Scientific Data,
  DOI 10.1038/s41597-024-03386-x. Full text: https://pmc.ncbi.nlm.nih.gov/articles/PMC11139986/
  (PubMed PMID 38816403). Fig. 2 ("Reporting of wellness in PmSys") is a verbatim screenshot
  carousel of the actual PmSys questionnaire; the image was downloaded and read directly
  (cached at `12_POLARITY_AUDIT/_evidence_cache/fig2_kimi.jpg`).
  Methods text: "Wellness parameters include fatigue, mood, readiness to train, sleep duration,
  sleep quality, muscle soreness, stress, and optionally menstruation. Readiness is reported on a
  scale from 1 to 10, sleep duration in hours and minutes, and menstruation with a checkbox.
  The remaining metrics are reported on a scale from 1 to 5. All scales in the questionnaire have
  supporting textual explanations for a more consistent interpretation of the numbers."
- **S2 — Official Zenodo record.** DOI 10.5281/zenodo.10033832,
  https://zenodo.org/records/10033832 (API JSON cached). Files: `subjective.zip` (706 KB) and four
  objective zips; **no README or codebook** is present in the record. The record description
  reproduces the descriptor abstract and contains no scale-anchor wording. It confirms dataset
  identity ("collected from two different elite women's soccer teams over two years") but is not
  itself anchor evidence.
- **S3 — Jarmann 2023, MSc thesis, University of Oslo** (supervised at Simula; cited as ref. 43 in
  the descriptor). https://home.simula.no/~paalh/students/AnnaLJarmann-UiO-2023.pdf (PDF + text
  extraction cached). Contains the most complete verbatim anchor table found (Table 2.1, p. 9),
  reproducing the PmSys wellness instrument, plus the readiness anchors in the running text (p. 8).
- **S4 — PMData OSF wiki (official documentation of the same PmSys app).**
  https://osf.io/vx4bk/wiki/home/ (PMData: A Sports Logging Dataset; same PmSys Reporter App used in
  PMData, cf. Ljøsne et al. 2020). Verbatim: "Fatigue, sleep quality, soreness, stress, and mood all
  have a 1-5 scale. The score 3 is normal, and 1-2 are scores below normal and 4-5 are scores above
  normal. Sleep length is just a measure of how long the sleep was in hours, and readiness
  (scale 0-10) is an overall subjective measure of how ready are you to exercise, i.e., 0 means not
  ready at all and 10 indicates that you cannot feel any better and are ready for anything!"
- **S5 — Hoel 2023, MSc thesis, University of Oslo** (Simula-hosted).
  https://home.simula.no/~paalh/students/LarsHoel-UiO.2023.pdf. Corroborates scale ranges only:
  "Readiness rates on a scale of 1 to 10, sleep length reports in hours ... while the remaining
  parameters use a balanced Likert-scale from 1 to 5."
- **S6 — simula/soccermon GitHub README** (https://raw.githubusercontent.com/simula/soccermon/main/README.md):
  data-restructuring tooling only; no anchor wording. Not used as evidence.
- **S7 — Smolarski 2022, MSc thesis, UiT (munin.uit.no/handle/10037/27843), "Match load affects
  perceived wellness significantly in elite women's football during a competitive season".** Located
  in the new NVA registry (identifier 0198f411bfc4-e7ed5e4b-098c-4ad3-b16d-4b2af7ed322b,
  `thesis.pdf`, OpenFile, CC BY-NC-SA 4.0) but the file download endpoints returned HTTP 403 for
  anonymous access, so its content could **not** be verified in this audit. The R1 dictionary cites a
  "Smolarski 2022 UiT thesis quote" for fatigue; that citation is treated as unverified here and is
  NOT load-bearing: fatigue anchors are independently covered by S1 Fig. 2 and S3 Table 2.1.

### 2.1 fatigue (raw 1–5) — CONSISTENT

- S1 Fig. 2, panel "How fatigued do you feel?": "1 - Very tired / 2 - More tired than normal /
  3 - Normal / 4 - Fresh / 5 - Very fresh" (read directly from the figure image; red-to-green
  gradient with red at 1).
- S3 Table 2.1 fatigue column: "1 Very tired / 2 More tired than normal / 3 Normal / 4 Fresh /
  5 Very fresh".
- S4: fatigue is 1–5 with "score 3 is normal, 1-2 below normal, 4-5 above normal".
- Reasoning: higher raw = fresher = LESS fatigued, so `fatigue_burden = 6 - fatigue` correctly
  yields higher = more fatigued. R1 coding **CONSISTENT**. Confidence: HIGH.

### 2.2 soreness (raw 1–5) — CONSISTENT

- S3 Table 2.1 soreness column (verbatim anchors): "1 Very sore / 2 A bit sore / 3 Normal /
  4 Feeling good / 5 Feeling great".
- S4: soreness is 1–5 with 3 = normal, 1–2 below normal, 4–5 above normal (state-quality semantics;
  below normal = worse state).
- S1 Fig. 2 does NOT show the soreness panel (the screenshot carousel hides it behind "..."), but the
  same figure's red-to-green gradient (red = low values, green = high values) applies uniformly to
  all items in the carousel, and S1 Methods states all scales carry "supporting textual
  explanations". Soreness anchors therefore rest primarily on S3, corroborated by S4.
- Reasoning: higher raw = feeling great = LESS sore, so `soreness_burden = 6 - soreness` correctly
  yields higher = sorer. R1 coding **CONSISTENT**. Confidence: HIGH (verbatim anchors from an
  independent thesis reproducing the identical instrument; two corroborating sources).
- Residual note: no public screenshot of the soreness panel itself was found; if Reviewer 4 requires
  a photographic anchor for soreness specifically, none is known to be public. The verbatim anchor
  table in S3 is treated as equivalent documentation of the same instrument.

### 2.3 readiness (raw 1–10) — CONSISTENT

- S1 Fig. 2, panel "How ready are you to train?": "1 - Not ready at all / 2 - Not ready /
  3 - Not quite ready / 4 - Almost ready / 5 - Almost ready / 6 - Ready / 7 - Ready /
  8 - Definitely ready / 9 - Definitely ready / 10 - Can't wait!" (read from the figure image).
- S1 Methods: "Readiness is reported on a scale from 1 to 10".
- S3: "Readiness is reported on a scale of 1-10, with 1 indicating 'not ready at all' and 10
  indicating 'can't wait!'".
- S4 (PMData variant): "readiness (scale 0-10) ... 0 means not ready at all and 10 indicates that
  you cannot feel any better and are ready for anything!" — note the 0–10 offset in the earlier
  PmSys version vs 1–10 in SoccerMon (observed data min=1, max=10, S1 Methods, S3); direction is
  identical, and the R1 transform `11 - x` matches the 1–10 range.
- Reasoning: higher raw = more ready = better state, so `readiness_deficit = 11 - readiness`
  correctly yields higher = less ready. R1 coding **CONSISTENT**. Confidence: HIGH.

### 2.4 Secondary variables (no R1 burden/deficit transform applied; polarity documented)

- **mood (1–5):** S3 Table 2.1: "1 Very bad mood / 2 Bad mood / 3 Normal / 4 Good mood /
  5 Very good mood"; S4 1–5 semantics. Higher raw = better mood. No reversal in R1 (kept raw) —
  direction documented; no transform to audit. Confidence HIGH.
- **stress (1–5):** S3 Table 2.1: "1 Highly stressed / 2 Somewhat stressed / 3 Normal / 4 Relaxed /
  5 Very relaxed"; S4 1–5. Higher raw = more relaxed = LESS stressed. Confidence HIGH for direction.
  **Discrepancy:** S1 Table 1 lists "Stress (1–10)" while S1 Methods text ("The remaining metrics
  are reported on a scale from 1 to 5"), S3, S4 and the observed data (max=5) all say 1–5. The
  descriptor Table 1 entry is an internal inconsistency of the descriptor; the scale maximum does
  not affect direction, and no transform depends on the stress maximum in R1 (no stress burden
  variable is modelled).
- **sleep_quality (1–5):** S1 Fig. 2 panel "How well did you sleep?": "1 - Insomnia /
  2 - Restless Sleep / 3 - Normal sleep / 4 - Good sleep / 5 - Excellent sleep"; S3 Table 2.1:
  "1 Insomnia / 2 Restless sleep / 3 Normal / 4 Good / 5 Very restful". Minor wording differences at
  points 3–5 between the two renderings; direction consistent (higher = better sleep). HIGH.
- **sleep_duration (hours, observed 1–12):** S1 Methods "sleep duration in hours and minutes"; S4
  "Sleep length is just a measure of how long the sleep was in hours". Continuous; no Likert
  polarity; higher = more sleep. HIGH.

---

## 3. Post-hoc QA notes — NOT decision-driving

The following are recorded for transparency only. None of them influenced any coding decision above.

1. **Descriptor's own empirical correlation narrative (S1, Technical Validation):** "The less sore a
   player is, the fresher she feels." and "A lower stress level indicates lower fatigue and
   soreness" — these are the dataset providers' interpretations of their correlation matrix
   (S1 Fig. 13). They agree with the anchor-based coding but are empirical associations published in
   the descriptor, hence corroboration only, not decision evidence.
2. **R1 internal correlation check** (documented in
   `03_VARIABLE_AUDIT/variable_transformations.md` lines 4–5 and `canonical_variable_dictionary.csv`
   row 4): all 1–5 wellness items are positively inter-correlated on the raw data
   (r = +0.28 … +0.49; mood–stress r = +0.62 per `phase5_variable_polarity_audit.py` line 24).
   This is consistent with uniform "higher = better state" scoring but was NOT used to set polarity.
3. **Jarmann 2023 (S3) lines 1200/1720** contain that author's own outcome-model interpretation of
   the fatigue scale ("1 indicating 'very tired' and 5 indicating 'very fresh', increasing the score
   would mean reducing fatigue"). Only the scale-anchor statement (instrument documentation) is used
   as evidence here; the author's model coefficients were ignored per the hard rule.

## 4. Verdict

| variable | R1 coding | consistent with independent anchors? | confidence |
|---|---|---|---|
| fatigue | 6 - x | YES | HIGH |
| soreness | 6 - x | YES | HIGH |
| readiness | 11 - x | YES | HIGH |
| mood | raw kept | n/a (direction documented: higher = better) | HIGH |
| stress | raw kept | n/a (direction documented: higher = less stressed) | HIGH |
| sleep_quality | raw kept | n/a (direction documented: higher = better) | HIGH |
| sleep_duration | raw kept | n/a (continuous hours) | HIGH |

No variable required a LOW-confidence rating: for all three primary variables, verbatim instrument
anchors were found in at least one independent source (S1 Fig. 2 and/or S3 Table 2.1), with
corroboration from S4. Open items: (a) no public screenshot of the soreness panel (anchors via S3);
(b) Smolarski 2022 thesis (S7) not anonymously downloadable from NVA — citation unverified but not
load-bearing; (c) descriptor Table 1 "Stress (1–10)" internal inconsistency (resolved to 1–5 by four
independent concordant sources incl. observed data).
