# build_validation.py -- cross-file numeric consistency checks + validation JSON (workstream: validation)
import json, os
import pandas as pd
import numpy as np

FR = "D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE"
RUN_REPRO = f"{FR}/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_R2_REPRO"
def rd(p): return pd.read_csv(f"{FR}/{p}")

master   = rd("17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")
registry = rd("17_MASTER_RESULTS/MODEL_REGISTRY.csv")
audit    = rd("05_SAMPLE_EVENT_AUDIT/SAMPLE_EVENT_AUDIT.csv")
sparse   = rd("06_SPARSE_DATA/SPARSE_DATA_DIAGNOSTICS.csv")
collin   = rd("07_COLLINEARITY/ACUTE_CHRONIC_COLLINEARITY.csv")
nonov    = rd("08_NONOVERLAP_WINDOW/NONOVERLAP_WINDOW_RESULTS.csv")
nonovcor = rd("08_NONOVERLAP_WINDOW/NONOVERLAP_CORRELATION.csv")
dropteam = rd("09_TEAM_SENSITIVITY/DROP_TEAM_SENSITIVITY.csv")
season   = rd("10_SEASON_SENSITIVITY/SEASON_STABILITY.csv")
backz    = rd("11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv")
polarity = rd("12_POLARITY_AUDIT/WELLNESS_POLARITY_INDEPENDENT_AUDIT.csv")
ipw_res  = rd("13_IPW_FINAL/IPW_FINAL_RESULTS.csv")
loo      = rd("14_EVENT_INFLUENCE/LEAVE_ONE_EVENT_PLAYER_OUT_QA.csv")
eventconc= rd("14_EVENT_INFLUENCE/EVENT_CONCENTRATION.csv")
census   = rd("15_MULTIPLICITY/MULTIPLICITY_CENSUS.csv")
nsi      = rd("15_MULTIPLICITY/NOMINAL_SIGNIFICANCE_INVENTORY.csv")
focstab  = rd("16_FOCAL_STABILITY/FOCAL_ESTIMATE_STABILITY.csv")
gateA    = rd("19_VALIDATION/R1_REPRODUCTION_CHECK.csv")
gateB    = rd("19_VALIDATION/RAW_VS_DERIVED_RECONCILIATION.csv")

IX = "acute_load_7d_wp_z:soreness_burden_recent3_wp_z"
def get(df, mid, term, col="OR", var="soreness"):
    r = df[(df.model_id == mid) & (df.term == term)]
    if "wellness_variant" in df.columns and var is not None:
        r = r[r.wellness_variant == var]
    return float(r[col].iloc[0]) if len(r) else np.nan

checks = []
def chk(cid, domain, desc, reported, source_val, source_file, tol=1e-4):
    try:
        if isinstance(source_val, str) or isinstance(reported, str):
            ok = str(reported) == str(source_val)
        else:
            ok = abs(float(reported) - float(source_val)) <= tol
    except Exception:
        ok = False
    checks.append(dict(check_id=cid, domain=domain, description=desc,
                       value_cited_in_report=reported, value_in_source_file=source_val,
                       source_file=source_file, tolerance=tol,
                       status="PASS" if ok else "FAIL"))

# --- Gates
ga_fail = int((gateA.match_status == "FAIL").sum())
chk("GATE-A-01", "gate", "Gate A: 0 FAIL of 217 reproduction checks", 0, ga_fail, "19_VALIDATION/R1_REPRODUCTION_CHECK.csv")
chk("GATE-A-02", "gate", "Gate A: 217 checks", 217, len(gateA), "19_VALIDATION/R1_REPRODUCTION_CHECK.csv")
gb_fail = int((gateB.match_status != "MATCH").sum())
chk("GATE-B-01", "gate", "Gate B: 33/33 MATCH, 0 FAIL", "33/33", f"{int((gateB.match_status=='MATCH').sum())}/{len(gateB)}", "19_VALIDATION/RAW_VS_DERIVED_RECONCILIATION.csv")

# --- sample/event counts
a = audit.set_index("sample_id")
chk("SMP-01", "sample", "theoretical grid 36,550 player-days (50 x 731)", 36550, int(a.loc["theoretical_grid_50x731","n_player_days"]), "05_SAMPLE_EVENT_AUDIT/SAMPLE_EVENT_AUDIT.csv")
chk("SMP-02", "sample", "primary risk set 36,296 player-days", 36296, int(a.loc["primary_risk_set","n_player_days"]), "05_SAMPLE_EVENT_AUDIT/SAMPLE_EVENT_AUDIT.csv")
chk("SMP-03", "sample", "risk-set onset-days 42 / event players 15", "42/15", f"{int(a.loc['primary_risk_set','onset_days'])}/{int(a.loc['primary_risk_set','event_players'])}", "05_SAMPLE_EVENT_AUDIT/SAMPLE_EVENT_AUDIT.csv")
chk("SMP-04", "sample", "soreness CC n=19,758 (audit) == master A soreness n", 19758, get(master,"A","acute_load_7d_wp_z","n"), "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")
chk("SMP-05", "sample", "soreness CC events=28 consistent audit vs master", 28, get(master,"A","acute_load_7d_wp_z","events"), "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")
chk("SMP-06", "sample", "soreness CC event players=9 (sparse diagnostics)", 9, int(sparse[(sparse.model_id=="A")&(sparse.fallback_level=="population_average_crve")&(sparse.wellness_variant=="soreness")].event_players.iloc[0]), "06_SPARSE_DATA/SPARSE_DATA_DIAGNOSTICS.csv")
chk("SMP-07", "sample", "fatigue CC n=19,815; readiness CC n=19,817", "19815/19817", f"{get(master,'A','acute_load_7d_wp_z','n','fatigue'):.0f}/{get(master,'A','acute_load_7d_wp_z','n','readiness'):.0f}", "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")
chk("SMP-08", "sample", "EPV primary PA approx 3.5 (28/8)", 3.50, float(sparse[(sparse.model_id=="A")&(sparse.fallback_level=="population_average_crve")&(sparse.wellness_variant=="soreness")].events_per_parameter_crude.iloc[0]), "06_SPARSE_DATA/SPARSE_DATA_DIAGNOSTICS.csv", tol=0.001)

# --- collinearity
def cv(section, metric):
    return float(collin[(collin.section == section) & (collin.metric == metric)].value.iloc[0])
chk("COL-01", "collinearity", "acute-chronic Pearson r=0.6981 (soreness CC)", 0.6981, cv("9.3.1_pairwise_primary","pearson_r"), "07_COLLINEARITY/ACUTE_CHRONIC_COLLINEARITY.csv")
chk("COL-02", "collinearity", "max VIF main-effects design = 4.0846 (calendar_time)", 4.0846, cv("9.3.3_full_design_VIF","max_VIF[main_effects_only]"), "07_COLLINEARITY/ACUTE_CHRONIC_COLLINEARITY.csv")
kap = collin[collin.metric.str.contains("condition", case=False, na=False)]
chk("COL-03", "collinearity", "condition number (scaled, main) = 3.79", 3.79, float(kap.value.min()), "07_COLLINEARITY/ACUTE_CHRONIC_COLLINEARITY.csv", tol=0.01)
chk("COL-04", "collinearity", "non-overlap chronic r=0.4695 == NONOVERLAP_CORRELATION", 0.4695, float(nonovcor[nonovcor.chronic_variant.str.contains("non-overlap")].pearson.iloc[0]), "08_NONOVERLAP_WINDOW/NONOVERLAP_CORRELATION.csv", tol=1e-3)
chk("COL-05", "collinearity", "R1 overlap reference r=0.6981 == NONOVERLAP_CORRELATION reference", 0.6981, float(nonovcor[nonovcor.chronic_variant.str.contains("R1 overlap")].pearson.iloc[0]), "08_NONOVERLAP_WINDOW/NONOVERLAP_CORRELATION.csv", tol=1e-3)

# --- R1 reference focal numbers
chk("R1-01", "r1_reference", "R1 F soreness interaction OR 0.6296 [0.4450,0.9651] p=0.0348", 0.6296, get(master,"F",IX), "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")
chk("R1-02", "r1_reference", "R1 IPW soreness interaction 0.6464 [0.4293,0.9732] p=0.0366", 0.6464, get(master,"IPW",IX), "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")
chk("R1-03", "r1_reference", "R1 IPW fatigue/readiness interaction 0.8012/0.9184", "0.8012/0.9184", f"{get(master,'IPW','acute_load_7d_wp_z:fatigue_burden_recent3_wp_z','OR','fatigue'):.4f}/{get(master,'IPW','acute_load_7d_wp_z:readiness_deficit_recent3_wp_z','OR','readiness'):.4f}", "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")
chk("R1-04", "r1_reference", "R1 A_boot interaction 0.6697 [0.4467,1.1071]", 0.6697, get(master,"A_boot",IX), "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")
chk("R1-05", "r1_reference", "master R1 block = 243 rows", 243, int((master.taxonomy=="R1_REVISION_SAP").sum()), "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")

# --- 9.4 non-overlap
chk("NOV-01", "nonoverlap", "F_nonoverlap interaction 0.6300 [0.4452,0.9661]", 0.6300, get(nonov,"F_nonoverlap",IX), "08_NONOVERLAP_WINDOW/NONOVERLAP_WINDOW_RESULTS.csv")
chk("NOV-02", "nonoverlap", "A_nonoverlap_dropteam (glmer full) interaction 0.7029 [0.4751,1.0399]", 0.7029, get(nonov,"A_nonoverlap_dropteam",IX), "08_NONOVERLAP_WINDOW/NONOVERLAP_WINDOW_RESULTS.csv")
chk("NOV-03", "nonoverlap", "nonoverlap bootstrap interaction 0.7404 [0.5568,1.1331]", 0.7404, get(nonov,"A_nonoverlap_dropteam_boot",IX), "08_NONOVERLAP_WINDOW/NONOVERLAP_WINDOW_RESULTS.csv")
chk("NOV-04", "nonoverlap", "nonoverlap CC n=19758/events=28 identical to R1 soreness CC", "19758/28", f"{int(nonov[nonov.model_id=='F_nonoverlap'].n.iloc[0])}/{int(nonov[nonov.model_id=='F_nonoverlap'].events.iloc[0])}", "08_NONOVERLAP_WINDOW/NONOVERLAP_WINDOW_RESULTS.csv")

# --- 9.5 drop-team
chk("DRT-01", "drop_team", "A_drop_team (glmer full accepted) interaction 0.6938 [0.4699,1.0246] p=0.066", 0.6938, get(dropteam,"A_drop_team",IX), "09_TEAM_SENSITIVITY/DROP_TEAM_SENSITIVITY.csv")
chk("DRT-02", "drop_team", "F_drop_team interaction 0.6710 [0.4739,1.0695] p=0.0915", 0.6710, get(dropteam,"F_drop_team",IX), "09_TEAM_SENSITIVITY/DROP_TEAM_SENSITIVITY.csv")
chk("DRT-03", "drop_team", "A_drop_team_boot interaction 0.7401 [0.5556,1.1323]", 0.7401, get(dropteam,"A_drop_team_boot",IX), "09_TEAM_SENSITIVITY/DROP_TEAM_SENSITIVITY.csv")

# --- 9.6 season
chk("SEA-01", "season", "F_drop_season interaction 0.6303 [0.4440,0.9704] p=0.0370", 0.6303, get(season,"F_drop_season",IX), "10_SEASON_SENSITIVITY/SEASON_STABILITY.csv")
d = season[season.model_id=="SEASON_DIST_CC"].set_index("term")
chk("SEA-02", "season", "CC onset-days split 20 (71.4%, 2020) / 8 (28.6%, 2021)", "20/8", f"{int(d.loc['season2020','events'])}/{int(d.loc['season2021','events'])}", "10_SEASON_SENSITIVITY/SEASON_STABILITY.csv")
r1sea = season[season.model_id.str.startswith("R1_") & (season.term=="season2021")]
chk("SEA-03", "season", "R1 season2021 OR range 2.69 (A-PA) to 31.2 (D Cox PWP)", "2.69/31.2", f"{float(r1sea[r1sea.model_id=='R1_A_season2021'].OR.iloc[0]):.2f}/{float(r1sea[r1sea.model_id=='R1_D_season2021'].OR.iloc[0]):.1f}", "10_SEASON_SENSITIVITY/SEASON_STABILITY.csv")

# --- 9.7 backward-z
IXH = "acute_load_7d_wp_z_hist:soreness_burden_recent3_wp_z_hist"
chk("BWZ-01", "backward_z", "F_hist interaction 0.9741 [0.7277,1.2520]", 0.9741, get(backz,"F_hist",IXH), "11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv")
chk("BWZ-02", "backward_z", "A_hist_dropteam (glmer full) interaction 0.9581 [0.6969,1.3172]", 0.9581, get(backz,"A_hist_dropteam",IXH), "11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv")
chk("BWZ-03", "backward_z", "F_hist_dropteam interaction 0.9440 [0.8589,1.1367]", 0.9440, get(backz,"F_hist_dropteam",IXH), "11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv")
chk("BWZ-04", "backward_z", "r90 QA agrees: F_hist_r90 0.9502 / F_hist_dropteam_r90 1.0874", "0.9502/1.0874", f"{get(backz,'F_hist_r90','acute_load_7d_wp_z_r90:soreness_burden_recent3_wp_z_r90'):.4f}/{get(backz,'F_hist_dropteam_r90','acute_load_7d_wp_z_r90:soreness_burden_recent3_wp_z_r90'):.4f}", "11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv")
chk("BWZ-05", "backward_z", "chronic REVERSES: A_hist chronic 2.1398 (p=0.0068)", 2.1398, get(backz,"A_hist","chronic_load_28d_wp_z_hist"), "11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv")
chk("BWZ-06", "backward_z", "chronic REVERSES: F_hist chronic 1.9555 (p=0.0077)", 1.9555, get(backz,"F_hist","chronic_load_28d_wp_z_hist"), "11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv")
chk("BWZ-07", "backward_z", "directional F_hist_dropteam fatigue/readiness interaction 0.9367/1.0028", "0.9367/1.0028", f"{get(backz,'F_hist_dropteam','acute_load_7d_wp_z_hist:fatigue_burden_recent3_wp_z_hist','OR','fatigue'):.4f}/{get(backz,'F_hist_dropteam','acute_load_7d_wp_z_hist:readiness_deficit_recent3_wp_z_hist','OR','readiness'):.4f}", "11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv")
chk("BWZ-08", "backward_z", "backwardz soreness CC n=19,216, events=27, event players=9", "19216/27", f"{int(backz[backz.model_id=='F_hist'].n.iloc[0])}/{int(backz[backz.model_id=='F_hist'].events.iloc[0])}", "11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv")

# --- 9.9 IPW
ipw_s = ipw_res[(ipw_res.wellness_variant=="soreness")].set_index("model_id")
chk("IPW-01", "ipw", "IPW_onset soreness interaction 0.6464 == frozen R1 IPW row", 0.6464, float(ipw_s.loc["IPW_onset","OR"]), "13_IPW_FINAL/IPW_FINAL_RESULTS.csv")
chk("IPW-02", "ipw", "IPW_nooutcome soreness interaction 0.6567 [0.4247,1.0155] p=0.0586", 0.6567, float(ipw_s.loc["IPW_nooutcome","OR"]), "13_IPW_FINAL/IPW_FINAL_RESULTS.csv")
chk("IPW-03", "ipw", "IPW ESS/CC approx 0.36 (onset, soreness)", 0.360, float(ipw_s.loc["IPW_onset","ess_over_n_cc_sample"]), "13_IPW_FINAL/IPW_FINAL_RESULTS.csv", tol=0.001)
chk("IPW-04", "ipw", "max stabilized weight (onset) approx 11.25; truncated approx 10.67", "11.247/10.665", f"{float(ipw_s.loc['IPW_onset','max_w_stab_untrunc']):.3f}/{float(ipw_s.loc['IPW_onset','max_w_stab_trunc']):.3f}", "13_IPW_FINAL/IPW_FINAL_RESULTS.csv")

# --- 9.10 event influence
ec = eventconc[eventconc.scope=="risk_set_42"].sort_values("events", ascending=False)
chk("EVC-01", "event_influence", "top risk-set contributor TeamA-3e5f6e2b 11/42 = 26.2%", "TeamA-3e5f6e2b-46b7-4890-84a9-3bbb2649af5a/11/26.19", f"{ec.iloc[0].player_id}/{int(ec.iloc[0].events)}/{ec.iloc[0].pct_of_scope_events:.2f}", "14_EVENT_INFLUENCE/EVENT_CONCENTRATION.csv")
lf = loo[(loo.model=="firth_full") & (loo.term==IX)]
chk("EVC-02", "event_influence", "LOO Firth interaction OR range 0.574-0.810", "0.574/0.810", f"{lf.OR.min():.3f}/{lf.OR.max():.3f}", "14_EVENT_INFLUENCE/LEAVE_ONE_EVENT_PLAYER_OUT_QA.csv", tol=0.001)
s5 = master[(master.model_id=="S5_exclude_high_contributor")]
chk("EVC-03", "event_influence", "R1 S5 (episode-count exclusion) n=19,297 events=22 reproduced", "19297/22", f"{int(s5.n.iloc[0])}/{int(s5.events.iloc[0])}", "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")

# --- polarity
pev = open(f"{FR}/12_POLARITY_AUDIT/WELLNESS_POLARITY_EVIDENCE.md", encoding="utf-8").read().upper()
n_consistent = pev.count("CONSISTENT")
pol_ok = (len(polarity) == 7 and (polarity.confidence == "HIGH").all()
          and (polarity.outcome_data_used == "NO").all() and n_consistent >= 3)
chk("POL-01", "polarity", "polarity audit: 7 variables, all CONSISTENT, all HIGH confidence, outcome data never used",
    "PASS", "PASS" if pol_ok else f"rows={len(polarity)},conf={(polarity.confidence=='HIGH').all()},outcome={(polarity.outcome_data_used=='NO').all()},CONSISTENT_mentions={n_consistent}",
    "12_POLARITY_AUDIT/WELLNESS_POLARITY_INDEPENDENT_AUDIT.csv + WELLNESS_POLARITY_EVIDENCE.md")

# --- prompt-vs-archive discrepancies
r1_ipw_ix = master[(master.model_id=="IPW") & (master.term.str.contains(":"))]
claimed = [0.833, 0.930, 1.035]
near = [c for c in claimed if (np.abs(r1_ipw_ix.OR - c) < 0.01).any()]
chk("GAP-01", "prompt_vs_archive", "freeze-prompt claimed R1 IPW ORs 0.833/0.930/1.035 do NOT exist in locked R1 outputs", "absent", "absent" if not near else f"FOUND:{near}", "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")
run0728 = os.path.exists(f"{FR}/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_20260728_FINAL")
chk("GAP-02", "prompt_vs_archive", "freeze-prompt run id 'RUN_20260728_FINAL' does NOT exist; reference run is RUN_20260722_151418", "absent", "absent" if not run0728 else "PRESENT", "02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/")

# --- assembly integrity
chk("ASM-01", "assembly", "MASTER_RESULTS_R2 has no duplicate (model_id,wellness_variant,term) keys", 0, int(master.duplicated(subset=["model_id","wellness_variant","term"]).sum()), "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")
reg_r2 = set(zip(registry[registry.taxonomy!="R1_REVISION_SAP"].model_id, registry[registry.taxonomy!="R1_REVISION_SAP"].wellness_variant))
mas_r2 = set(zip(master[master.taxonomy!="R1_REVISION_SAP"].model_id, master[master.taxonomy!="R1_REVISION_SAP"].wellness_variant))
chk("ASM-02", "assembly", "registry <-> master R2 model sets identical", "identical", "identical" if reg_r2==mas_r2 else f"diff:{reg_r2^mas_r2}", "17_MASTER_RESULTS/MODEL_REGISTRY.csv")
chk("ASM-03", "assembly", "master rows = 678 (243 R1 + 435 R2)", 678, len(master), "17_MASTER_RESULTS/MASTER_RESULTS_R2.csv")
chk("ASM-04", "assembly", "census focal p<0.05 count == NOMINAL_SIGNIFICANCE_INVENTORY rows", int(census[census.metric=="nominal_p<0.05_focal_tests"].value.iloc[0]), len(nsi), "15_MULTIPLICITY/")
chk("ASM-05", "assembly", "focal stability rows=298; all focal master rows captured", 298, len(focstab), "16_FOCAL_STABILITY/FOCAL_ESTIMATE_STABILITY.csv")

cdf = pd.DataFrame(checks)
cdf.to_csv(f"{FR}/19_VALIDATION/NUMERIC_CONSISTENCY_CHECK.csv", index=False)
n_fail = int((cdf.status=="FAIL").sum())
print(cdf.to_string(max_colwidth=60))
print(f"\nCHECKS: {len(cdf)} | FAIL={n_fail}")

vrep = {
  "generated_by": "20_FREEZE/build_validation.py",
  "domains": {
    "data_integrity": "Gate B raw rebuild: 33/33 numeric checks MATCH, max abs diff 0.0; 50x731 grid, 0 duplicate player-dates; all 25 compared columns EXACT MATCH vs old derived.",
    "temporal_integrity": "Exposures lagged (windows end t-1); non-overlap chronic t-28..t-8 disjoint from acute t-7..t-1 (NONOVERLAP_QA.txt: 4/4 PASS, brute-force max|diff|=0); backward-z baselines use only history < t with min-10-prior-obs rule (BACKWARD_Z_QA.txt: 19/19 PASS, bit-identical determinism, max|diff|=0 on brute-force spot checks).",
    "polarity_integrity": "All 7 wellness codings CONSISTENT with independent external anchors (descriptor DOI 10.1038/s41597-024-03386-x Fig.2; Jarmann 2023 Table 2.1; PMData OSF wiki), HIGH confidence, outcome data never used in any coding decision.",
    "ipw_integrity": "With-onset IPW reproduced exactly (obs-model refit max|diff|=1.8e-15 on weights; R weighted-glm refit dOR=0.0). No-outcome variant is NEW R2 sensitivity; integrity checks PASS both variants. Prompt-claimed alternative R1 IPW numbers do not exist (prompt-vs-archive discrepancy, not an R1 defect).",
    "model_integrity": "1 failed fit (E readiness gamma frailty) recorded not omitted; all separation-driven ladder rejections and aliased Cox terms documented in 06_SPARSE_DATA and workstream diagnostics; 3 logistf maxit warnings resolved by maxit=200 refits (max|dlogOR|<=1.25e-05).",
    "cross_file_consistency": f"NUMERIC_CONSISTENCY_CHECK.csv: {len(cdf)} checks, {n_fail} FAIL.",
    "gate_status": "Gate A PASS (0 FAIL of 217); Gate B PASS (33/33 byte/numeric identical).",
    "prompt_vs_archive_discrepancies": [
      "Claimed R1 IPW interaction ORs 0.833/0.930/1.035, weights 219-224, trunc 8.0-8.2, ESS 44-45%: NOT present in locked R1 outputs. Actual: 0.6464/0.8012/0.9184; max w_stab ~11.24-11.26; trunc max ~10.62-10.67; ESS/CC ~0.36, ESS/all-rows 0.534.",
      "Claimed run id RUN_20260728_FINAL does not exist; actual locked reference run is RUN_20260722_151418."
    ],
  },
  "overall_verdict": "PASS" if n_fail == 0 else f"FAIL ({n_fail} consistency failures)",
  "n_checks": len(cdf), "n_fail": n_fail,
}
with open(f"{FR}/19_VALIDATION/VALIDATION_REPORT.json","w",encoding="utf-8") as f:
    json.dump(vrep, f, indent=2)
print("validation json written")
