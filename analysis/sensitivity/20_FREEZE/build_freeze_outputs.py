# build_freeze_outputs.py -- R2 freeze final assembly (workstream 9.11/9.12 + master + validation)
# Reads ONLY from FR inputs; writes ONLY under FR/15,16,17,19.
# Run: C:/Users/15776/python_temp/python_embed/python.exe build_freeze_outputs.py
import json, os, sys
import pandas as pd
import numpy as np

FR = "D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE"
RUN = f"{FR}/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_R2_REPRO"

def rd(p): return pd.read_csv(f"{FR}/{p}")

r1_master = rd("02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_R2_REPRO/master_results.csv")
r1_inv    = rd("02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_R2_REPRO/model_inventory.csv")
sparse    = rd("06_SPARSE_DATA/SPARSE_DATA_DIAGNOSTICS.csv")
audit     = rd("05_SAMPLE_EVENT_AUDIT/SAMPLE_EVENT_AUDIT.csv")
collin    = rd("07_COLLINEARITY/ACUTE_CHRONIC_COLLINEARITY.csv")
nonov     = rd("08_NONOVERLAP_WINDOW/NONOVERLAP_WINDOW_RESULTS.csv")
nonovcor  = rd("08_NONOVERLAP_WINDOW/NONOVERLAP_CORRELATION.csv")
dropteam  = rd("09_TEAM_SENSITIVITY/DROP_TEAM_SENSITIVITY.csv")
season    = rd("10_SEASON_SENSITIVITY/SEASON_STABILITY.csv")
backz     = rd("11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv")
polarity  = rd("12_POLARITY_AUDIT/WELLNESS_POLARITY_INDEPENDENT_AUDIT.csv")
ipw_res   = rd("13_IPW_FINAL/IPW_FINAL_RESULTS.csv")
ipw_r     = rd("13_IPW_FINAL/ipw_final_r_results.csv")
loo       = rd("14_EVENT_INFLUENCE/LEAVE_ONE_EVENT_PLAYER_OUT_QA.csv")
eventconc = rd("14_EVENT_INFLUENCE/EVENT_CONCENTRATION.csv")
gateA     = rd("19_VALIDATION/R1_REPRODUCTION_CHECK.csv")
gateB     = rd("19_VALIDATION/RAW_VS_DERIVED_RECONCILIATION.csv")

# ---------------------------------------------------------------- focal terms
FOCAL_GROUPS = {
    "acute_load":              lambda t: ("acute_load_7d" in t or "acwr_7_28" in t) and ":" not in t,
    "chronic_load":            lambda t: ("chronic_load_28d" in t or "chronic_load_28to8" in t) and ":" not in t,
    "acute_x_soreness":        lambda t: "soreness_burden" in t and ":" in t,
    "acute_x_fatigue":         lambda t: "fatigue_burden" in t and ":" in t,
    "acute_x_readiness":       lambda t: "readiness_deficit" in t and ":" in t,
    "prev_episode_ever":       lambda t: t == "prev_episode_ever",
}
def focal_group(term):
    for g, f in FOCAL_GROUPS.items():
        if f(str(term)): return g
    return None

EST_FAMILY = [
    ("boot",     "player-cluster bootstrap (marginal logit IRLS)"),
    ("IPW",      "stabilised-IPW glm + clubSandwich CR2"),
    ("logistf",  "logistf (Firth penalised)"),
    ("glmer",    "glmer nAGQ=1 bobyqa"),
    ("glm",      "glm binomial + clubSandwich CR2 (population-average)"),
    ("coxph",    "coxph"),
    ("frailty",  "coxph gamma frailty"),
]
def est_family(est, optimizer=""):
    s = f"{est} {optimizer}".lower()
    for k, v in EST_FAMILY:
        if k.lower() in s: return v
    return est

# ---------------------------------------------------------------- MODEL REGISTRY
reg = []

def add_reg(model_id, taxonomy, variant, estimator, exposure, standardization,
            team, season_, interaction, n, events, event_players, focal_terms,
            fit_status, role):
    reg.append(dict(model_id=model_id, taxonomy=taxonomy, wellness_variant=variant,
                    estimator=estimator, exposure_definition=exposure,
                    standardization=standardization, team_included=team,
                    season_included=season_, interaction_included=interaction,
                    n=n, events=events, event_players=event_players,
                    focal_terms=focal_terms, fit_status=fit_status, role=role))

R1_EXPO = "acute 7d (t-7..t-1) + chronic 28d (t-28..t-1, overlapping) + wellness burden/deficit recent3"
R1_Z    = "within-player full-period z"
R1_EST = {
    "A":  "glm binomial + clubSandwich CR2 (population-average fallback; glmer separated at all 3 ladder levels)",
    "B":  "coxph counting-process (Andersen-Gill)",
    "C":  "coxph counting-process + strata(enum)",
    "D":  "coxph PWP gap-time + strata(enum)",
    "E":  "coxph gamma frailty (player_id)",
    "F":  "logistf (Firth penalised); bootstrap CI",
    "IPW":"stabilised-IPW glm + clubSandwich CR2 (obs model incl. onset_day; 1/99 truncation)",
    "S1_washout3d":  "glmer nAGQ=1 bobyqa (full interaction level accepted; only accepted glmer in R1)",
    "S1_washout14d": "glm binomial + clubSandwich CR2 (population-average fallback; separation)",
    "S2_end_plus_washout": "glm binomial + clubSandwich CR2 (population-average fallback; separation)",
    "S3_ACWR_replaces_acute": "glm binomial + clubSandwich CR2 (population-average fallback; separation)",
    "S4_strict_lag1_wellness": "glm binomial + clubSandwich CR2 (population-average fallback; separation)",
    "S5_exclude_high_contributor": "glm binomial + clubSandwich CR2 (population-average fallback; separation)",
    "A_boot": "player-cluster bootstrap B=2000 of marginal logit (numpy IRLS; SAP-sanctioned fast approximation)",
    "F_boot": "logistf (Firth) + player-cluster bootstrap B=2000 CI",
}
R1_ROLE = {"PRIMARY":"primary", "PRIMARY_BOOTSTRAP":"key_sensitivity",
           "KEY_SENSITIVITY":"key_sensitivity", "SMALL_SAMPLE_SENSITIVITY":"key_sensitivity",
           "SENSITIVITY":"secondary", "SENSITIVITY_IPW":"secondary",
           "SECONDARY_wellness_variant":"secondary"}
role_by_model = {}
for (mid, var), g in r1_master.groupby(["model_id", "wellness_variant"]):
    role_by_model[(mid, var)] = R1_ROLE.get(g.analysis_role.iloc[0], "secondary")

for _, r in r1_inv.iterrows():
    mid, var = r["model_id"], r["wellness_variant"]
    mm = r1_master[(r1_master.model_id == mid) & (r1_master.wellness_variant == var)]
    n = int(mm.n.iloc[0]) if len(mm) and pd.notna(mm.n.iloc[0]) else ""
    ev = int(mm.events.iloc[0]) if len(mm) and pd.notna(mm.events.iloc[0]) else ""
    terms = sorted(mm.term.unique()) if len(mm) else []
    fg = sorted({focal_group(t) for t in terms if focal_group(t)})
    interaction = any(":" in str(t) for t in terms)
    expo = R1_EXPO
    if mid == "S3_ACWR_replaces_acute": expo = "ACWR (7d/28d) replaces acute load; chronic 28d; soreness burden recent3"
    if mid == "S4_strict_lag1_wellness": expo = "acute 7d + chronic 28d + soreness burden lag1 (strict, no recent3)"
    if mid.startswith("S1"): expo = R1_EXPO + f"; episode definition washout {'3d' if '3d' in mid else '14d'}"
    if mid == "S2_end_plus_washout": expo = R1_EXPO + "; risk set ends episode at end+1+washout"
    if mid == "S5_exclude_high_contributor": expo = R1_EXPO + "; excludes TeamA-4051bba7 (highest contributor by 7d LL episode count, 45)"
    ep = {("A","soreness"):9,("F","soreness"):9}.get((mid,var), "")
    if mid in ("A","B","C","D","E","F","IPW"):
        ep = 9 if len(mm) else ""
    add_reg(mid, "R1_REVISION_SAP", var, R1_EST.get(mid, ""), expo, R1_Z,
            True, True, interaction, n, ev, ep, ";".join(fg),
            r["status"], role_by_model.get((mid, var), "secondary"))
# A_boot / F_boot (not in model_inventory)
mm = r1_master[r1_master.model_id == "A_boot"]
add_reg("A_boot", "R1_REVISION_SAP", "soreness", R1_EST["A_boot"], R1_EXPO, R1_Z,
        True, True, True, 19758, 28, 9,
        "acute_x_soreness", "OK (B=2000, 0/2000 failures)", "key_sensitivity")
for var in ["soreness","fatigue","readiness"]:
    mm = r1_master[(r1_master.model_id=="F_boot") & (r1_master.wellness_variant==var)]
    terms = sorted(mm.term.unique())
    fg = sorted({focal_group(t) for t in terms if focal_group(t)})
    add_reg("F_boot", "R1_REVISION_SAP", var, R1_EST["F_boot"], R1_EXPO, R1_Z,
            True, True, True, int(mm.n.iloc[0]), int(mm.events.iloc[0]), 9,
            ";".join(fg), "OK (B=2000, 0 failures soreness/fatigue; 1/2000 readiness)", "key_sensitivity")

# ---- R2 fits: helper to register from a workstream fit dataframe
def register_fits(df, id_filter, expo, stand, team_fn, season_fn, role_map, est_fn,
                  event_players_map, status_fn):
    d = df[id_filter(df)].copy()
    for (mid, var), g in d.groupby(["model_id", "wellness_variant"]):
        terms = sorted(g.term.astype(str).unique())
        fg = sorted({focal_group(t) for t in terms if focal_group(t)})
        interaction = any(":" in t for t in terms) or ("interaction" in str(g.formula.iloc[0]).lower() if "formula" in g else False)
        add_reg(mid, g.taxonomy.iloc[0] if "taxonomy" in g else "R2_REVIEWER_REQUESTED",
                var, est_fn(mid, g), expo, stand, team_fn(mid), season_fn(mid),
                interaction, int(g.n.iloc[0]), int(g.events.iloc[0]),
                event_players_map(mid), ";".join(fg), status_fn(mid, g), role_map(mid))

is_fit = lambda df: (~df.model_id.str.startswith(("CMP_", "SUMMARY"))) & df.OR.notna()

NOV_EXPO = "acute 7d (t-7..t-1) + NON-OVERLAPPING chronic t-28..t-8 + soreness burden recent3"
def est_from_notes(mid, g):
    txt = " ".join(str(x) for x in list(g.get("optimizer", pd.Series([""])).unique()) + list(g.notes.astype(str).unique()[:1])) if "optimizer" in g else str(g.notes.iloc[0])
    if "boot" in mid: return "player-cluster bootstrap B=2000 marginal logit (numpy IRLS), design minus team"
    if mid.startswith("F_"): return "logistf (Firth penalised)"
    if "REJECTED" in mid: return "glmer nAGQ=1 bobyqa (rejected ladder level; separation present)"
    if "dropteam" in mid or "drop_team" in mid:
        return "glmer nAGQ=1 bobyqa maxfun2e5 (full level accepted; team removed)"
    return "glm binomial + clubSandwich CR2 (population-average fallback; separation)"
def stat_fn(mid, g):
    if "REJECTED" in mid: return "fitted_rejected_ladder_level (separation; recorded for transparency)"
    if "boot" in mid: return "OK (B=2000, 0/2000 failures)"
    return "OK"
role_r2 = lambda mid: ("internal_QA" if ("r90" in mid or "drop_team_season" in mid) else "key_sensitivity")
team_fn = lambda mid: not ("dropteam" in mid or "drop_team" in mid)
season_fn = lambda mid: ("drop_season" not in mid) and ("drop_team_season" not in mid)
nov_ep = lambda mid: 9

register_fits(nonov, is_fit, NOV_EXPO, R1_Z, team_fn, season_fn, role_r2, est_from_notes, nov_ep, stat_fn)
register_fits(dropteam, is_fit, R1_EXPO + "; team covariate removed", R1_Z, team_fn, season_fn,
              role_r2, est_from_notes, nov_ep, stat_fn)
register_fits(season, lambda df: is_fit(df) & ~df.model_id.str.startswith(("R1_", "SEASON_DIST", "COLLINEARITY", "COX_")),
              R1_EXPO + "; season covariate removed (drop_season) or team+season removed (drop_team_season)",
              R1_Z, team_fn, season_fn, role_r2, est_from_notes, nov_ep, stat_fn)
BZ_EXPO = "acute 7d + chronic 28d + wellness burden/deficit recent3; exposures re-standardized backward-looking"
register_fits(backz, is_fit, BZ_EXPO,
              "within-player EXPANDING-HISTORY z (baseline < t, min 10 prior obs; leakage-free)" ,
              team_fn, season_fn, role_r2, est_from_notes, nov_ep, stat_fn)

# IPW_nooutcome (from ipw_final_r_results, obs_model_variant=nooutcome)
ipw_no = ipw_r[ipw_r.obs_model_variant == "nooutcome"]
for var, g in ipw_no.groupby("wellness_variant"):
    terms = sorted(g.term.astype(str).unique())
    fg = sorted({focal_group(t) for t in terms if focal_group(t)})
    add_reg("IPW_nooutcome", "R2_REVIEWER_REQUESTED", var,
            "stabilised-IPW glm + clubSandwich CR2 (observation model WITHOUT onset_day; 1/99 truncation)",
            R1_EXPO, R1_Z, True, True, True, int(g.n.iloc[0]), int(g.events.iloc[0]), 9,
            ";".join(fg), "OK (observation-model sensitivity; NEW in R2)", "key_sensitivity")

# LOO QA fits
for (excl, model), g in loo.groupby(["excluded_player", "model"]):
    short = "-".join(excl.split("-")[:2])
    mid = f"LOO_{'FIRTH' if model=='firth_full' else 'PA_CR2'}_excl_{short}"
    terms = sorted(g.term.astype(str).unique())
    fg = sorted({focal_group(t) for t in terms if focal_group(t)})
    est = ("logistf (Firth, full interaction formula)" if model == "firth_full"
           else "glm binomial + clubSandwich CR2 (PA no-interaction fallback formula)")
    add_reg(mid, "R2_INTERNAL_QA_ONLY", "soreness", est,
            R1_EXPO + f"; excludes event player {short}", R1_Z, True, True,
            model == "firth_full", int(g.n.iloc[0]), int(g.events.iloc[0]),
            int(g.event_players.iloc[0]), ";".join(fg),
            "OK (all 18 LOO fits succeeded; PA separation on teamTeamB expected)", "internal_QA")

registry = pd.DataFrame(reg)
registry.insert(0, "registry_row", range(1, len(registry) + 1))
os.makedirs(f"{FR}/17_MASTER_RESULTS", exist_ok=True)
os.makedirs(f"{FR}/15_MULTIPLICITY", exist_ok=True)
registry.to_csv(f"{FR}/17_MASTER_RESULTS/MODEL_REGISTRY.csv", index=False)
registry.to_csv(f"{FR}/15_MULTIPLICITY/MODEL_REGISTRY.csv", index=False)
print(f"REGISTRY: {len(registry)} rows | failed fits: {(registry.fit_status.str.upper().str.startswith('FAILED')).sum()}")
print(registry.groupby('role').size().to_dict())

# ---------------------------------------------------------------- MASTER RESULTS
cols15 = ["analysis_role","model_id","wellness_variant","term","OR","CI_low","CI_high",
          "p","se","converged","optimizer","n","players","events","notes"]
r1m = r1_master.copy()
r1m["taxonomy"] = "R1_REVISION_SAP"

def to_master(df, id_filter, role_lookup, optimizer_fn, notes_prefix=""):
    d = df[id_filter(df)].copy()
    out = pd.DataFrame()
    out["analysis_role"] = d.model_id.map(lambda m: {"primary":"PRIMARY","key_sensitivity":"KEY_SENSITIVITY",
        "secondary":"SECONDARY","internal_QA":"INTERNAL_QA"}[role_lookup(m)])
    out["model_id"] = d.model_id
    out["wellness_variant"] = d.wellness_variant
    out["term"] = d.term
    for c in ["OR","CI_low","CI_high","p","se","converged","n","players","events"]:
        out[c] = d[c] if c in d else np.nan
    out["optimizer"] = [optimizer_fn(m, g) for m, g in zip(d.model_id, d.notes.astype(str))]
    out["notes"] = notes_prefix + d.notes.astype(str) if "notes" in d else notes_prefix
    out["taxonomy"] = d.taxonomy if "taxonomy" in d else "R2_REVIEWER_REQUESTED"
    return out[cols15 + ["taxonomy"]]

role_lookup = dict(zip(registry.model_id, registry.role))
def rl(mid): return role_lookup.get(mid, "key_sensitivity")
opt_fn = lambda mid, note: est_from_notes(mid, pd.DataFrame({"notes":[note],"optimizer":[""]}))

parts = [r1m[cols15 + ["taxonomy"]]]
parts.append(to_master(nonov, is_fit, rl, opt_fn))
parts.append(to_master(dropteam, is_fit, rl, opt_fn))
parts.append(to_master(season, lambda df: is_fit(df) & ~df.model_id.str.startswith(("R1_","SEASON_DIST","COLLINEARITY","COX_")), rl, opt_fn))
parts.append(to_master(backz, is_fit, rl, opt_fn))
# IPW_nooutcome from ipw_final_r_results
ipw_out = ipw_no.copy()
ipw_out["model_id"] = "IPW_nooutcome"
ipw_out["taxonomy"] = "R2_REVIEWER_REQUESTED"
ipw_out["notes"] = ("NEW R2 reviewer-requested sensitivity: observation model WITHOUT onset_day; "
                    "stabilised IPW 1/99 trunc; ESS/CC=" + ipw_out.ess_over_n_cc_sample.round(3).astype(str))
parts.append(to_master(ipw_out, lambda df: df.OR.notna(), lambda m: "key_sensitivity",
                       lambda m, n: "glm binomial weighted + clubSandwich CR2 cluster(player)"))
# LOO
loo_m = loo.copy()
loo_m["wellness_variant"] = "soreness"
loo_m["model_id"] = ["LOO_%s_excl_%s" % (("FIRTH" if m == "firth_full" else "PA_CR2"),
                     "-".join(e.split("-")[:2])) for e, m in zip(loo_m.excluded_player, loo_m.model)]
loo_m["taxonomy"] = "R2_INTERNAL_QA_ONLY"
parts.append(to_master(loo_m, lambda df: df.OR.notna(), lambda m: "internal_QA",
                       lambda m, n: ("logistf" if "FIRTH" in m else "glm binomial + clubSandwich CR2")))

master = pd.concat(parts, ignore_index=True)
# validations
dup = master.duplicated(subset=["model_id","wellness_variant","term"]).sum()
reg_models = set(zip(registry.model_id, registry.wellness_variant)) - {("E","readiness")}
mast_models = set(zip(master[master.taxonomy != "R1_REVISION_SAP"].model_id,
                      master[master.taxonomy != "R1_REVISION_SAP"].wellness_variant))
reg_r2 = set(zip(registry[registry.taxonomy != "R1_REVISION_SAP"].model_id,
                 registry[registry.taxonomy != "R1_REVISION_SAP"].wellness_variant))
missing_in_master = reg_r2 - mast_models
extra_in_master = mast_models - reg_r2
print(f"MASTER: {len(master)} rows (R1 {len(r1m)} + R2 {len(master)-len(r1m)}) | dup keys: {dup}")
print(f"registry-vs-master R2: missing={missing_in_master} extra={extra_in_master}")
assert dup == 0 and not missing_in_master and not extra_in_master, "MASTER/REGISTRY INCONSISTENT"

master.to_csv(f"{FR}/17_MASTER_RESULTS/MASTER_RESULTS_R2.csv", index=False)
with open(f"{FR}/17_MASTER_RESULTS/MASTER_RESULTS_R2.json", "w", encoding="utf-8") as f:
    json.dump({
        "schema_version": "R1 master_results 15-column schema + 1 added column 'taxonomy' "
                          "(R1_REVISION_SAP | R2_REVIEWER_REQUESTED | R2_INTERNAL_QA_ONLY). "
                          "analysis_role extended with INTERNAL_QA for R2 internal-QA fits. "
                          "All other columns identical in meaning to RUN_R2_REPRO/master_results.csv.",
        "n_rows": len(master), "n_rows_R1": len(r1m), "n_rows_R2": len(master) - len(r1m),
        "duplicate_keys": int(dup),
        "rows": master.where(pd.notna(master), None).to_dict(orient="records"),
    }, f, indent=1)
audit.to_csv(f"{FR}/17_MASTER_RESULTS/SAMPLE_EVENT_AUDIT.csv", index=False)
print("master + json + audit copy written")

# ---------------------------------------------------------------- MULTIPLICITY CENSUS
m = master.copy()
m["focal_group"] = m.term.map(focal_group)
m["is_interaction"] = m.term.astype(str).str.contains(":")
m["has_test"] = m.p.notna()
m["p05"] = m.p < 0.05
role_map2 = dict(zip(zip(registry.model_id, registry.wellness_variant), registry.role))
m["role"] = [role_map2.get((a, b), "secondary") for a, b in zip(m.model_id, m.wellness_variant)]

n_specs = len(registry)
n_failed = int((registry.fit_status.str.upper().str.startswith("FAILED")).sum())
n_fitted = n_specs - n_failed
tests = m[m.has_test]
focal = m[m.focal_group.notna() & m.has_test]
inter = m[m.is_interaction & m.has_test]
focal_sec = focal[focal.role != "primary"]
focal_p05 = focal[focal.p05]
inter_p05 = inter[inter.p05]

# estimator family keyed on the registry estimator string (NOT the model_id)
fam_of = dict(zip(zip(registry.model_id, registry.wellness_variant),
                  [est_family(e) for e in registry.estimator]))
def fam_lookup(mid, var=""):
    return fam_of.get((mid, var), fam_of.get((mid, "soreness"), "other"))

# replication across estimator families for interaction focal groups
rep_rows = []
for (g_, var), gg in inter[inter.p05.notna() & inter.focal_group.notna()].groupby(["focal_group","wellness_variant"]):
    fam = gg.apply(lambda r: fam_lookup(r.model_id, r.wellness_variant), axis=1).nunique()
    fam05 = gg[gg.p05].apply(lambda r: fam_lookup(r.model_id, r.wellness_variant), axis=1).nunique()
    rep_rows.append(dict(focal_group=g_, wellness_variant=var, n_tests=len(gg),
                         n_nominal_p05=int(gg.p05.sum()),
                         estimator_families_tested=int(fam), estimator_families_nominal_p05=int(fam05),
                         classification=("replicates_across_independent_estimators" if fam05 >= 2
                                         else ("isolated_nominal_signal" if fam05 == 1 else "no_nominal_signal"))))
rep = pd.DataFrame(rep_rows)

census = pd.DataFrame([
    ("total_distinct_fitted_specifications_registered", n_fitted, "MODEL_REGISTRY rows excl. FAILED (incl. rejected ladder levels and internal-QA LOO fits)"),
    ("total_fit_attempts_failed", n_failed, "E readiness (coxph gamma frailty + coxme fallback): 'No starting estimate was successful'"),
    ("total_fitted_coefficient_tests", len(tests), "term rows with a Wald/p value across MASTER_RESULTS_R2 (intercepts and nuisance terms included; bootstrap-CI-only rows have no p and are excluded)"),
    ("total_focal_exposure_or_interaction_tests", len(focal), "terms in focal set: acute_load, chronic_load, acute x soreness/fatigue/readiness, prev_episode_ever"),
    ("total_load_x_wellness_interaction_tests", len(inter), "terms containing ':' (all are acute_load x wellness burden/deficit)"),
    ("total_secondary_or_sensitivity_focal_tests", len(focal_sec), "focal tests in models whose role is not primary"),
    ("nominal_p<0.05_focal_tests", int(focal_p05.shape[0]), "nominal, unadjusted; census only - no Bonferroni/FDR primary inference"),
    ("nominal_p<0.05_interaction_tests", int(inter_p05.shape[0]), "subset of focal; see NOMINAL_SIGNIFICANCE_INVENTORY.csv"),
    ("interaction_signals_replicating_across_independent_estimator_families",
     int((rep.classification == "replicates_across_independent_estimators").sum()),
     "acute_x_soreness (R1 Firth + R1 IPW); see replication detail rows"),
    ("interaction_signals_isolated_to_one_estimator_family",
     int((rep.classification == "isolated_nominal_signal").sum()), ""),
    ("binding_information_limit", "28 CC onset-days / 9 event players",
     "multiple model fits do NOT create more outcome information than the sparse event set"),
], columns=["metric", "value", "definition_notes"])
census.to_csv(f"{FR}/15_MULTIPLICITY/MULTIPLICITY_CENSUS.csv", index=False)

inv = focal_p05[["taxonomy","model_id","wellness_variant","term","focal_group","OR","CI_low","CI_high","p","role","n","events","notes"]].copy()
inv["is_interaction"] = inv.term.astype(str).str.contains(":")
inv["replication_class"] = inv.apply(lambda r: rep[(rep.focal_group == r.focal_group) & (rep.wellness_variant == r.wellness_variant)].classification.iloc[0]
                                     if r.is_interaction and len(rep[(rep.focal_group == r.focal_group) & (rep.wellness_variant == r.wellness_variant)]) else "non_interaction_focal", axis=1)
inv["multiplicity_caveat"] = ("Nominal p<0.05 in a census of %d focal tests on 28 shared CC onset-days / 9 event players; "
                              "not robustness evidence; no multiplicity-adjusted primary inference." % len(focal))
inv.sort_values(["focal_group","p"]).to_csv(f"{FR}/15_MULTIPLICITY/NOMINAL_SIGNIFICANCE_INVENTORY.csv", index=False)
rep.to_csv(f"{FR}/15_MULTIPLICITY/INTERACTION_REPLICATION_DETAIL.csv", index=False)
print(census.to_string())
print(rep.to_string())

# ---------------------------------------------------------------- FOCAL STABILITY
fs = m[m.focal_group.notna()].copy()
# reference per (focal_group, variant): R1 F if present else R1 A
ref = {}
for (g_, var), gg in fs[fs.model_id == "F"].groupby(["focal_group","wellness_variant"]):
    ref[(g_, var)] = np.sign(np.log(gg.OR.iloc[0]))
for (g_, var), gg in fs[fs.model_id == "A"].groupby(["focal_group","wellness_variant"]):
    ref.setdefault((g_, var), np.sign(np.log(gg.OR.iloc[0])))

def flags(r):
    fl = []
    key = (r.focal_group, r.wellness_variant)
    rsign = ref.get(key, np.nan)
    sgn = np.sign(np.log(r.OR)) if pd.notna(r.OR) and r.OR > 0 else np.nan
    ci_cross = pd.notna(r.CI_low) and pd.notna(r.CI_high) and r.CI_low <= 1 <= r.CI_high
    if pd.notna(rsign) and pd.notna(sgn):
        if sgn != rsign: fl.append("direction_changes")
        elif ci_cross: fl.append("direction_consistent_but_imprecise")
    mid = r.model_id
    if "nooutcome" in mid: fl.append("sensitivity_to_missingness_model")
    if "dropteam" in mid or "drop_team" in mid: fl.append("sensitivity_to_team_removal")
    if "nonoverlap" in mid: fl.append("sensitivity_to_window_definition")
    if "_hist" in mid or "r90" in mid: fl.append("sensitivity_to_standardization")
    return ";".join(fl) if fl else "none"

fs["direction"] = np.where(fs.OR > 1, "OR>1", np.where(fs.OR < 1, "OR<1", "OR=1"))
fs["ci_crosses_1"] = (fs.CI_low <= 1) & (fs.CI_high >= 1)
fs["language_flags"] = fs.apply(flags, axis=1)
# isolated_nominal_signal: p<0.05 where <2 estimator families reach p<0.05 for that group+variant
fam05 = {}
for (g_, var), gg in fs[fs.has_test].groupby(["focal_group","wellness_variant"]):
    fam05[(g_, var)] = gg[gg.p05].apply(lambda r: fam_lookup(r.model_id, r.wellness_variant), axis=1).nunique()
mask = fs.apply(lambda r: bool(r.has_test and r.p05 and fam05.get((r.focal_group, r.wellness_variant), 0) < 2), axis=1)
fs.loc[mask, "language_flags"] = fs.loc[mask, "language_flags"].map(lambda s: ("isolated_nominal_signal;" + s).replace(";none","").replace("none;","isolated_nominal_signal;") if s != "none" else "isolated_nominal_signal")
fs["estimator_family"] = fs.apply(lambda r: fam_lookup(r.model_id, r.wellness_variant), axis=1)
fs["interpretation_note"] = ("CI crossing 1 is NOT proof of no effect; estimates are descriptive given 28 CC onset-days / 9 event players.")
fsout = fs[["taxonomy","focal_group","model_id","wellness_variant","estimator_family","term","OR","CI_low","CI_high","p",
            "direction","ci_crosses_1","n","events","role","language_flags","interpretation_note"]].sort_values(
            ["focal_group","wellness_variant","model_id"])
# add event_players from registry
ep_map = dict(zip(zip(registry.model_id, registry.wellness_variant), registry.event_players))
fsout.insert(12, "event_players", [ep_map.get((a, b), "") for a, b in zip(fsout.model_id, fsout.wellness_variant)])
fsout.to_csv(f"{FR}/16_FOCAL_STABILITY/FOCAL_ESTIMATE_STABILITY.csv", index=False)
fsout.to_csv(f"{FR}/17_MASTER_RESULTS/FOCAL_ESTIMATE_STABILITY.csv", index=False)
print(f"FOCAL STABILITY: {len(fsout)} rows; direction_changes rows: {(fsout.language_flags.str.contains('direction_changes')).sum()}")

master.to_pickle(f"{FR}/20_FREEZE/_master.pkl")
registry.to_pickle(f"{FR}/20_FREEZE/_registry.pkl")
print("BUILD PART 1 OK")
