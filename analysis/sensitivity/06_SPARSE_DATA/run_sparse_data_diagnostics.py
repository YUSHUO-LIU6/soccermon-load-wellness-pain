#!/usr/bin/env python3
"""
run_sparse_data_diagnostics.py — R2 freeze plan section 9.2
PONE-D-26-31950 (SoccerMon) R2 reproducibility freeze.

Sparse-data / parameter-count audit over every focal model already fitted in
RUN_R2_REPRO (r_results.csv + master_results.csv), using model_inventory.csv,
sample_size_inventory.csv and diagnostic_inventory.csv.

Coefficient counting convention (SAP formula structure, no variable
selection, EPV is NOT treated as a 10-per-parameter validity threshold):
  full interaction Model A formula:
    onset_day ~ acute*wcol + chronic + prev_episode_ever + calendar_time
                + team + season
    -> 8 non-intercept fixed coefficients (team -> 1 dummy, season -> 1
       dummy, interaction -> 1), +1 intercept = 9 fixed; glmer adds +1
       random-intercept variance = 10 total.
  no_interaction: 7 non-intercept (+1 intercept).
  no_interaction_no_chronic: 6 non-intercept (+1 intercept).
  Cox B/C/D: same RHS as full (8 non-intercept, no intercept; strata not
    counted); aliased/dropped terms subtracted from fitted count.
  Cox E: full RHS + frailty variance (+1).
  Firth F: 9 (incl. intercept). IPW: 9 (incl. intercept).
  A_boot/F_boot: bootstrap CIs for A-PA / F -> same parameter counts.

Rows for A_drop_team / F_drop_team are RESERVED placeholders (produced by the
R2 drop-team workstream) so model_ids slot in without collision.

Output: SPARSE_DATA_DIAGNOSTICS.csv — one row per
(model_id, wellness_variant, fallback_level).
Taxonomy: R2_INTERNAL_QA_ONLY. Seed 20260722 (no stochastic steps).
"""
import re
import numpy as np
import pandas as pd
from pathlib import Path

SEED = 20260722
TAXONOMY = "R2_INTERNAL_QA_ONLY"

FR = Path(r"D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE")
RUN = FR / "02_R1_REPRODUCTION" / "r1_sandbox" / "07_ANALYSIS_OUTPUTS" / "RUN_R2_REPRO"
OUTDIR = FR / "06_SPARSE_DATA"
OUTDIR.mkdir(parents=True, exist_ok=True)

rres = pd.read_csv(RUN / "r_results.csv")
master = pd.read_csv(RUN / "master_results.csv")
inv = pd.read_csv(RUN / "model_inventory.csv")
ss = pd.read_csv(RUN / "sample_size_inventory.csv")
diag = pd.read_csv(RUN / "diagnostic_inventory.csv")

results_all = pd.concat([rres, master]).drop_duplicates(
    subset=["model_id", "wellness_variant", "term", "optimizer"], keep="first")


def diag_val(model_id, variant, diagnostic):
    m = diag[(diag.model_id == model_id) &
             (diag.wellness_variant == variant) &
             (diag.diagnostic == diagnostic)]
    return None if m.empty else m.iloc[0]["value"]


def parse_rhs_counts(formula):
    """Count fixed-effect coefficients from a stored R formula string.
    Returns (n_nonintercept, has_intercept, n_random_var)."""
    if not isinstance(formula, str) or "~" not in formula:
        return None, None, None
    rhs = formula.split("~", 1)[1]
    rhs = re.sub(r"Surv\([^)]*\)", "", rhs)  # in case Surv leaked into rhs
    # drop random-effect / frailty / strata terms, count separately
    n_re = len(re.findall(r"\(\s*1\s*\|", rhs)) + len(re.findall(r"frailty\(", rhs))
    rhs = re.sub(r"\([^)]*\|[^)]*\)", " ", rhs)
    rhs = re.sub(r"frailty\([^)]*\)", " ", rhs)
    rhs = re.sub(r"strata\([^)]*\)", " ", rhs)
    terms = [t.strip() for t in re.split(r"\+", rhs) if t.strip()]
    n = 0
    for t in terms:
        if t in ("1", "0", "-1"):
            continue
        if "*" in t:
            m = len([x for x in t.split("*") if x.strip()])
            n += 2 ** m - 1  # a*b = a + b + a:b (3 coefficients for 2-way)
        else:
            n += 1  # main effect; 2-level factors (team, season) -> 1 dummy
    has_int = "- 1" not in formula and "+ 0" not in formula
    return n, has_int, n_re


def res_stats(model_id, variant):
    """Estimate-derived flags from results rows."""
    m = results_all[(results_all.model_id == model_id) &
                    (results_all.wellness_variant == variant)]
    if m.empty:
        return {}
    beta = np.log(m["OR"].astype(float))
    boundary = bool((beta.abs() > 10).any())
    with np.errstate(all="ignore"):
        w = np.log(m["CI_high"].astype(float)) - np.log(m["CI_low"].astype(float))
    wide = bool((w > 5).any())
    maxw = float(np.nanmax(w)) if w.notna().any() else np.nan
    bterms = ";".join(m.loc[beta.abs() > 10, "term"].tolist())
    return {"boundary_beta_abs_gt10": boundary, "boundary_terms": bterms,
            "wide_ci_logwidth_gt5": wide, "max_ci_log_width": round(maxw, 2)}


WELL_DESCRIBE = {
    ("full", True): "onset_day ~ acute*wcol + chronic + prev_episode_ever + calendar_time + team + season + (1|player_id)",
}

GLMER_LEVELS = [("full", 8, 9, 10), ("no_interaction", 7, 8, 9),
                ("no_interaction_no_chronic", 6, 7, 8)]

SAFEGUARD = ("28 CC onset-days / 9 event players = severe information limit; "
             "multiple estimators share the same events; TeamB contributes 0 CC "
             "events so the team coefficient is degenerate (separation); "
             "nominal p<0.05 must never be called robust. EPV is reported as a "
             "descriptive sparsity metric only — 10 EPV is NOT a validity "
             "threshold and no variable selection was performed.")

rows = []


def add_row(**kw):
    base = dict(taxonomy=TAXONOMY, model_id=None, wellness_variant=None,
                fallback_level=None, estimator=None, formula=None,
                status=None, n=None, players=None, events=None,
                event_players=None, n_fixed_nonintercept=None,
                n_total_fitted=None, events_per_parameter_crude=None,
                r_inventory_n_parameters=None, r_inventory_epv=None,
                converged=None, singular=None, separation_flag=None,
                separated_terms=None, boundary_beta_abs_gt10=None,
                boundary_terms=None, wide_ci_logwidth_gt5=None,
                max_ci_log_width=None, aliased_dropped_terms=None,
                extra_diagnostics=None, notes=None)
    base.update(kw)
    if base["events"] is not None and base["n_total_fitted"]:
        base["events_per_parameter_crude"] = round(
            base["events"] / base["n_total_fitted"], 2)
    rows.append(base)


def ss_row(model_id, variant):
    m = ss[(ss.model_id == model_id) & (ss.wellness_variant == variant)]
    return None if m.empty else m.iloc[0]


def inv_row(model_id, variant):
    m = inv[(inv.model_id == model_id) & (inv.wellness_variant == variant)]
    return None if m.empty else m.iloc[0]


VARIANTS = ["soreness", "fatigue", "readiness"]

# ---------------------------------------------------------------- Model A ----
for v in VARIANTS:
    s = ss_row("A", v)
    i = inv_row("A", v)
    # glmer attempt levels (diagnostics only; none accepted for A)
    for tag, n_ni, n_fix, n_tot in GLMER_LEVELS:
        conv = diag_val("A", v, f"converged_{tag}")
        sing = diag_val("A", v, f"singular_{tag}")
        trig = diag_val("A", v, "fallback_trigger")
        sep = None
        if isinstance(trig, str) and trig.startswith(f"{tag}:"):
            sep = "separation=TRUE" in trig
        add_row(model_id="A", wellness_variant=v,
                fallback_level=f"glmer_attempt_{tag}",
                estimator="glmer nAGQ=1 bobyqa (attempt)",
                formula=WELL_DESCRIBE[("full", True)] if tag == "full" else
                f"glmer attempt level '{tag}' (see 04_run_reanalysis.R mk_formula)",
                status="attempted_not_accepted" if sep or conv == "TRUE" else "attempted",
                n=s["n"], players=s["players"], events=s["onset_days"],
                event_players=s["event_players"],
                n_fixed_nonintercept=n_ni, n_total_fitted=n_tot,
                converged=conv, singular=sing, separation_flag=sep,
                notes=("glmer attempt level; fell back because separation "
                       "(|beta|>10) present" if sep else "glmer attempt level"))
    # final PA row
    st = res_stats("A", v)
    add_row(model_id="A", wellness_variant=v,
            fallback_level="population_average_crve",
            estimator="glm binomial + clubSandwich CR2 cluster(player)",
            formula=i["formula"], status=i["status"],
            n=s["n"], players=s["players"], events=s["onset_days"],
            event_players=s["event_players"],
            n_fixed_nonintercept=7, n_total_fitted=8,
            r_inventory_n_parameters=s["n_parameters"],
            r_inventory_epv=s["events_per_parameter"],
            converged=True, singular=pd.NA,
            separation_flag=diag_val("A", v, "separation_population_average"),
            separated_terms=diag_val("A", v, "separated_terms"),
            **st,
            notes=("R1 primary Model A final estimator after registered "
                   "fallback (all 3 glmer levels separated). " + SAFEGUARD))

# ------------------------------------------------------- Cox B / C / D / E ---
for mid in ["B", "C", "D", "E"]:
    for v in VARIANTS:
        s = ss_row(mid, v)
        i = inv_row(mid, v)
        if i is None:
            continue
        if str(i["status"]).startswith("FAILED"):
            # failed fit: report the attempted CC sample size from a sibling
            # model on the same variant (identical CC sample)
            sib = ss_row("F", v)
            add_row(model_id=mid, wellness_variant=v, fallback_level="final",
                    estimator="coxph gamma frailty", formula=i["formula"],
                    status=i["status"],
                    n=sib["n"], players=sib["players"],
                    events=sib["onset_days"], event_players=sib["event_players"],
                    notes=(f"FAILED: {i['fail_reason']} (frailty and coxme "
                           f"fallback both failed); attempted on the same CC "
                           f"sample as model F. " + SAFEGUARD))
            continue
        n_ni, has_int, n_re = parse_rhs_counts(i["formula"])
        aliased = diag_val(mid, v, "cox_terms_dropped_aliased")
        n_drop = len(str(aliased).split(" || ")) if isinstance(aliased, str) else 0
        n_tot = (n_ni or 0) + (n_re or 0) - n_drop
        warn = diag_val(mid, v, "cox_warnings") or diag_val(mid, v, "frailty_warnings")
        add_row(model_id=mid, wellness_variant=v, fallback_level="final",
                estimator=str(i["status"]), formula=i["formula"],
                status=i["status"],
                n=s["n"], players=s["players"], events=s["onset_days"],
                event_players=s["event_players"],
                n_fixed_nonintercept=(n_ni - n_drop) if n_ni is not None else None,
                n_total_fitted=n_tot if n_ni is not None else None,
                r_inventory_n_parameters=s["n_parameters"],
                r_inventory_epv=s["events_per_parameter"],
                converged=diag_val(mid, v, "cox_converged"),
                separation_flag=diag_val(mid, v, "possible_separation"),
                aliased_dropped_terms=aliased,
                extra_diagnostics=(f"warnings: {warn}" if warn else None),
                **res_stats(mid, v),
                notes=("Cox counting-process variant; aliased terms dropped by "
                       "coxph reduce the fitted coefficient count. " + SAFEGUARD))

# ---------------------------------------------------------------- Model F ----
for v in VARIANTS:
    s, i = ss_row("F", v), inv_row("F", v)
    add_row(model_id="F", wellness_variant=v, fallback_level="final",
            estimator="logistf (Firth penalised)",
            formula=i["formula"], status=i["status"],
            n=s["n"], players=s["players"], events=s["onset_days"],
            event_players=s["event_players"],
            n_fixed_nonintercept=8, n_total_fitted=9,
            r_inventory_n_parameters=s["n_parameters"],
            r_inventory_epv=s["events_per_parameter"],
            converged=True, singular=pd.NA, separation_flag=False,
            **res_stats("F", v),
            notes=("Full R1 Firth model — reference estimator under "
                   "separation; penalisation removes boundary estimates. "
                   "Profile-likelihood CIs; cluster-bootstrap CIs in F_boot. "
                   + SAFEGUARD))

# -------------------------------------------------------------------- IPW ----
for v in VARIANTS:
    s, i = ss_row("IPW", v), inv_row("IPW", v)
    ess = diag_val("IPW", v, "ESS_truncated")
    add_row(model_id="IPW", wellness_variant=v, fallback_level="final",
            estimator="stabilised-IPW glm + clubSandwich CR2",
            formula=i["formula"], status=i["status"],
            n=s["n"], players=s["players"], events=s["onset_days"],
            event_players=s["event_players"],
            n_fixed_nonintercept=8, n_total_fitted=9,
            r_inventory_n_parameters=s["n_parameters"],
            r_inventory_epv=s["events_per_parameter"],
            converged=True, singular=pd.NA,
            extra_diagnostics=(f"ESS_truncated={ess}; "
                               f"ESS_over_n={diag_val('IPW', v, 'ESS_over_n')}; "
                               f"max_weight={diag_val('IPW', v, 'max_weight')}"),
            **res_stats("IPW", v),
            notes=("Weighted marginal logit; effective sample size ~36% of n "
                   "after 1/99 truncation. " + SAFEGUARD))

# ------------------------------------------------- S1-S5 sensitivities -------
SENS = {
    "S1_washout3d": ("glmer", "full", 8, 10,
                     "accepted at glmer full level (no separation: 48 events "
                     "after 3d washout risk-set rebuild)"),
    "S1_washout14d": ("glm_crve", "population_average_crve", 7, 8, None),
    "S2_end_plus_washout": ("glm_crve", "population_average_crve", 7, 8, None),
    "S3_ACWR_replaces_acute": ("glm_crve", "population_average_crve", 7, 8, None),
    "S4_strict_lag1_wellness": ("glm_crve", "population_average_crve", 7, 8, None),
    "S5_exclude_high_contributor": ("glm_crve", "population_average_crve", 7, 8,
                                    "excludes TeamA-4051bba7-1170-4c43-b912-"
                                    "8c38815a7625 (45 lower-limb episodes)"),
}
for mid, (kind, lvl, n_ni, n_tot, note) in SENS.items():
    s, i = ss_row(mid, "soreness"), inv_row(mid, "soreness")
    add_row(model_id=mid, wellness_variant="soreness",
            fallback_level=lvl,
            estimator=str(i["status"]), formula=i["formula"],
            status=i["status"],
            n=s["n"], players=s["players"], events=s["onset_days"],
            event_players=s["event_players"],
            n_fixed_nonintercept=n_ni, n_total_fitted=n_tot,
            r_inventory_n_parameters=s["n_parameters"],
            r_inventory_epv=s["events_per_parameter"],
            converged=diag_val(mid, "soreness", f"converged_{lvl.split('_crve')[0] if lvl=='population_average_crve' else 'full'}")
            or diag_val(mid, "soreness", "converged_full"),
            singular=diag_val(mid, "soreness", "singular_full"),
            separation_flag=diag_val(mid, "soreness", "separation_population_average"),
            separated_terms=diag_val(mid, "soreness", "separated_terms"),
            **res_stats(mid, "soreness"),
            notes=((note + ". ") if note else "") + SAFEGUARD)

# ------------------------------------------------- bootstrap rows ------------
for mid, base_mid, n_ni, n_tot in [("A_boot", "A", 7, 8), ("F_boot", "F", 8, 9)]:
    s = ss_row(base_mid, "soreness")
    m = master[(master.model_id == mid) & (master.wellness_variant == "soreness")]
    if m.empty:
        continue
    add_row(model_id=mid, wellness_variant="soreness",
            fallback_level="bootstrap_ci",
            estimator=("player-cluster bootstrap B=2000, seed 20260722 "
                       f"(CI layer for model {base_mid})"),
            formula=f"as {base_mid}", status="OK",
            n=int(s["n"]), players=int(s["players"]),
            events=int(s["onset_days"]), event_players=int(s["event_players"]),
            n_fixed_nonintercept=n_ni, n_total_fitted=n_tot,
            converged=True,
            **res_stats(mid, "soreness"),
            notes=("Bootstrap CI layer, not an independent estimator — shares "
                   f"the same 28 events as {base_mid}. " + SAFEGUARD))

# ------------------------------------------------- reserved drop-team rows ---
for mid in ["A_drop_team", "F_drop_team"]:
    add_row(model_id=mid, wellness_variant="soreness",
            fallback_level="reserved",
            estimator=("PA glm+CR2 (team dropped)" if mid.startswith("A_")
                       else "logistf full (team dropped)"),
            formula="onset_day ~ ... (Model A/F formula minus team)",
            status="RESERVED — produced by the R2 drop-team workstream; "
                   "model_id pre-registered here to avoid collisions",
            notes=("R2_REVIEWER_REQUESTED drop-team full models slot in here. "
                   "Rationale: TeamB has 0 CC events so the team coefficient "
                   "is degenerate in every R1 fit. " + SAFEGUARD))

out = pd.DataFrame(rows)
out.to_csv(OUTDIR / "SPARSE_DATA_DIAGNOSTICS.csv", index=False)

# ---- explicit primary-soreness comparison: Model A PA vs full Firth F -------
a = master[(master.model_id == "A") & (master.wellness_variant == "soreness")].set_index("term")
f = master[(master.model_id == "F") & (master.wellness_variant == "soreness")].set_index("term")
comp_lines = ["PRIMARY soreness comparison — R1 Model A population-average "
              "fallback vs full R1 Firth (Model F):"]
for t in ["acute_load_7d_wp_z", "soreness_burden_recent3_wp_z",
          "acute_load_7d_wp_z:soreness_burden_recent3_wp_z", "teamTeamB"]:
    la = (f"  {t}: A-PA OR={a.loc[t,'OR']:.3f} [{a.loc[t,'CI_low']:.3f},"
          f"{a.loc[t,'CI_high']:.3f}] p={a.loc[t,'p']:.3g}") if t in a.index else f"  {t}: not in A-PA"
    lf = (f" | F OR={f.loc[t,'OR']:.3f} [{f.loc[t,'CI_low']:.3f},"
          f"{f.loc[t,'CI_high']:.3f}] p={f.loc[t,'p']:.3g}") if t in f.index else ""
    comp_lines.append(la + lf)
comp = "\n".join(comp_lines)
print(comp)
with open(OUTDIR / "PRIMARY_SORENESS_COMPARISON.txt", "w") as fh:
    fh.write(comp + "\n\nReserved slots: A_drop_team, F_drop_team "
             "(R2 drop-team workstream).\n\n" + SAFEGUARD + "\n")

print(f"\nwrote {len(out)} rows -> {OUTDIR/'SPARSE_DATA_DIAGNOSTICS.csv'}")
print(out[["model_id", "wellness_variant", "fallback_level", "events",
           "n_total_fitted", "events_per_parameter_crude"]].to_string(index=False))
