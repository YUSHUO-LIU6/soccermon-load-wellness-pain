#!/usr/bin/env python3
"""
run_ipw_final.py — IPW workstream, PLOS ONE R2 reproducibility freeze (sec 9.9)
PONE-D-26-31950 (SoccerMon secondary analysis). Seed 20260722 (no randomness
in IPW itself; recorded for the freeze).

Scope
-----
VARIANT 1 "onset"  (taxonomy = R1_REVISION_SAP):
    Diagnostics frozen from the EXISTING R1 run files
    (RUN_R2_REPRO/ipw_weights_<var>.csv, ipw_weight_diagnostics.csv,
    master_results.csv IPW rows, top-level observation_model_results.csv).
    Additionally the observation model is refit here WITH onset_day using the
    exact code path of 06_ANALYSIS_CODE/05_bootstrap_and_ipw.py stage `ipw`
    purely as a reproduction check of the stored weights (max |diff|).

VARIANT 2 "nooutcome" (taxonomy = R2_REVIEWER_REQUESTED):
    NEW sensitivity requested by Reviewer 2: observation model WITHOUT
    onset_day. Everything else identical to 05 stage `ipw`: same fit sample
    (36,296 at-risk days), same scoring grid (36,550), same clipping
    [1e-4, 1-1e-4], same marginal stabilization, same 1st/99th within-variable
    truncation, same previous-at-risk-row lag lookup. NOT an R1 reproduction —
    the R1 archive contains no such variant (see KNOWN GAP note in
    18_LOGS/workstream_ipw.log).

Stages
------
  python run_ipw_final.py stage1    -> weights_nooutcome csvs, diag stage1 csv,
                                       plots, reproduction check
  Rscript run_ipw_final.R           -> ipw_final_r_results.csv (weighted glms)
  python run_ipw_final.py finalize  -> IPW_FINAL_DIAGNOSTICS.csv,
                                       IPW_FINAL_RESULTS.csv, log lines

Writes ONLY under FR/13_IPW_FINAL/.
"""

import argparse
import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

FR = Path("D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE")
SB = FR / "02_R1_REPRODUCTION" / "r1_sandbox"
OUT_ALL = SB / "07_ANALYSIS_OUTPUTS"
RUN = OUT_ALL / "RUN_R2_REPRO"
OUTDIR = FR / "13_IPW_FINAL"
WORK = OUTDIR / "_work"
SEED = 20260722

PRIMARY = ["soreness", "fatigue", "readiness"]
WELL_Z = {"soreness": "soreness_burden_recent3_wp_z",
          "fatigue": "fatigue_burden_recent3_wp_z",
          "readiness": "readiness_deficit_recent3_wp_z"}
CC_VARS_EXTRA = ["onset_day", "acute_load_7d_wp_z", "chronic_load_28d_wp_z",
                 "prev_episode_ever", "calendar_time", "team", "season",
                 "player_id", "date", "prev_episode_count"]

QS = [0, .01, .05, .25, .50, .75, .90, .95, .99, 1.0]
Q_LABS = ["min", "p01", "p05", "p25", "median", "p75", "p90", "p95", "p99",
          "max"]

OBS_FORMULA_ONSET = ("obs_{v} ~ daily_load_z + C(team) + C(season) + "
                     "calendar_time_z + C(day_of_week) + obs_{v}_lag1 + "
                     "prev_episode_ever + onset_day")
OBS_FORMULA_NOOUTCOME = ("obs_{v} ~ daily_load_z + C(team) + C(season) + "
                         "calendar_time_z + C(day_of_week) + obs_{v}_lag1 + "
                         "prev_episode_ever")

# R1 reference numbers (established facts, for PASS/FAIL check)
R1_INTERACTION = {
    "soreness":  dict(OR=0.6464, lo=0.4293, hi=0.9732, p=0.0366),
    "fatigue":   dict(OR=0.8012, lo=0.6163, hi=1.0417, p=None),
    "readiness": dict(OR=0.9184, lo=0.6951, hi=1.2135, p=None),
}
R1_CC_N = {"soreness": 19758, "fatigue": 19815, "readiness": 19817}


def log(msg=""):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# observation-model machinery (mirror of 05_bootstrap_and_ipw.py stage `ipw`)
# ---------------------------------------------------------------------------

def build_grid_and_fit(md, base, formula_template):
    """Returns (grid, phat dict, auc dict, fit_info list).
    Code path mirrors 05_bootstrap_and_ipw.py stage `ipw` line for line;
    only the formula template differs (with/without onset_day)."""
    import statsmodels.formula.api as smf
    from sklearn.metrics import roc_auc_score

    grid = base.sort_values(["player_id", "date"]).reset_index(drop=True)
    md_keys = set(zip(md["player_id"], md["date"]))
    grid["in_risk_set"] = [(p, d) in md_keys
                           for p, d in zip(grid["player_id"], grid["date"])]
    ons_keys = set(zip(md.loc[md["onset_day"] == 1, "player_id"],
                       md.loc[md["onset_day"] == 1, "date"]))
    grid["onset_day"] = [(p, d) in ons_keys
                         for p, d in zip(grid["player_id"], grid["date"])]
    grid["onset_day"] = grid["onset_day"].astype(int)
    grid["prev_episode_ever"] = (
        grid.groupby("player_id")["onset_day"].cumsum()
        - grid["onset_day"]).clip(upper=1).astype(int)
    grid["season"] = grid["date"].dt.year
    grid["calendar_time"] = (grid["date"] - pd.Timestamp("2020-01-01")).dt.days

    fit_df = grid.loc[grid["in_risk_set"] == 1].copy()
    for c, cz in [("daily_load", "daily_load_z"),
                  ("calendar_time", "calendar_time_z")]:
        mu, sd = fit_df[c].mean(), fit_df[c].std(ddof=1)
        fit_df[cz] = (fit_df[c] - mu) / sd
        grid[cz] = (grid[c] - mu) / sd

    phat, auc, info = {}, {}, []
    for v in PRIMARY:
        grid[f"obs_{v}"] = grid[v].notna().astype(int)
        fit_df[f"obs_{v}"] = fit_df[v].notna().astype(int)
        grid[f"obs_{v}_lag1"] = (grid.groupby("player_id")[f"obs_{v}"]
                                 .shift(1).fillna(0).astype(int))
        fit_df[f"obs_{v}_lag1"] = (fit_df.groupby("player_id")[f"obs_{v}"]
                                   .shift(1).fillna(0).astype(int))
        f = formula_template.format(v=v)
        res = smf.logit(f, data=fit_df).fit(disp=0, maxiter=200)
        conv = bool(res.mle_retvals.get("converged", True))
        a = float(roc_auc_score(fit_df[f"obs_{v}"].values,
                                res.predict(fit_df)))
        auc[v] = a
        info.append(dict(variable=v, formula=f, n_fit=len(fit_df),
                         obs_rate=float(fit_df[f"obs_{v}"].mean()),
                         auc=a, converged=conv))
        log(f"  obs model [{v}] N={len(fit_df)}, obs rate="
            f"{fit_df[f'obs_{v}'].mean():.3f}, AUC={a:.4f}, converged={conv}")
        phat[v] = res.predict(grid).clip(1e-4, 1 - 1e-4)
        grid[f"phat_{v}"] = phat[v].values
    return grid, phat, auc, info


def compute_weights(md, grid, phat):
    """Mirror of 05 stage `ipw` weight block. Returns dict v -> weight df
    (all 36,296 at-risk rows) plus per-variable scalar diagnostics."""
    md2 = md.sort_values(["player_id", "date"]).reset_index(drop=True)
    md2["lag_date"] = md2.groupby("player_id")["date"].shift(1)
    lk = grid.set_index(["player_id", "date"])
    out = {}
    for v in PRIMARY:
        p_marg = grid.loc[grid["in_risk_set"] == 1, f"obs_{v}"].mean()
        cc = md2.copy()
        cc = cc.join(lk[[f"phat_{v}"]], on=["player_id", "lag_date"])
        n_na = int(cc[f"phat_{v}"].isna().sum())
        cc["w_stab"] = p_marg / cc[f"phat_{v}"]
        lo, hi = cc["w_stab"].quantile([0.01, 0.99])
        cc["w_stab_trunc"] = cc["w_stab"].clip(lo, hi)
        cc["p_marg"] = p_marg
        out[v] = dict(df=cc, p_marg=float(p_marg), n_na_lag=n_na,
                      lo=float(lo), hi=float(hi))
    return out


# ---------------------------------------------------------------------------
# diagnostics helpers
# ---------------------------------------------------------------------------

def pct_rows(s, prefix):
    vals = np.quantile(s.dropna().values, QS)
    return {f"{prefix}_{lab}": float(x) for lab, x in zip(Q_LABS, vals)}


def variant_diagnostics(v, variant, md, wdf, p_marg, lo, hi, n_na_lag,
                        formula, auc):
    """Diagnostics dict for one (wellness, obs-model variant).
    wdf: at-risk-row frame with w_stab / w_stab_trunc / lag_date / phat."""
    wcol = WELL_Z[v]
    cc_vars = CC_VARS_EXTRA + [wcol]
    cc = md.dropna(subset=cc_vars).copy()
    n_target = len(md)
    n_cc_pre = len(cc)
    # attach weights by player-date (same join as the R outcome model)
    key_w = wdf.set_index(["player_id", "date"])
    cc = cc.join(key_w[["w_stab", "w_stab_trunc", "lag_date", f"phat_{v}"]],
                 on=["player_id", "date"])
    n_cc_no_weight = int(cc["w_stab"].isna().sum())
    cc = cc.dropna(subset=["w_stab"])

    w_all = wdf.dropna(subset=["w_stab"])
    ess_all = float(w_all["w_stab_trunc"].sum() ** 2
                    / (w_all["w_stab_trunc"] ** 2).sum())
    ess_cc = float(cc["w_stab_trunc"].sum() ** 2
                   / (cc["w_stab_trunc"] ** 2).sum())

    d = dict(
        wellness_variant=v, obs_model_variant=variant,
        obs_model_formula=formula.format(v=v), obs_model_auc=auc,
        n_target_rows=n_target,
        n_players_target=int(md["player_id"].nunique()),
        n_complete_case_pre_weight_drop=n_cc_pre,
        n_cc_dropped_no_weight=n_cc_no_weight,
        n_complete_case=len(cc),
        complete_case_fraction=len(cc) / n_target,
        n_players_cc=int(cc["player_id"].nunique()),
        n_onset_days_cc=int(cc["onset_day"].sum()),
        n_event_players_cc=int(cc.loc[cc["onset_day"] == 1, "player_id"]
                               .nunique()),
        n_weighted_atrisk_rows=len(w_all),
        n_atrisk_rows_missing_lag_phat=n_na_lag,
        p_marginal_observed=p_marg,
        trunc_p01_threshold=lo, trunc_p99_threshold=hi,
        n_truncated_low=int((w_all["w_stab"] < lo).sum()),
        n_truncated_high=int((w_all["w_stab"] > hi).sum()),
        n_truncated_total=int((w_all["w_stab"] != w_all["w_stab_trunc"])
                              .sum()),
        prop_truncated=float((w_all["w_stab"] != w_all["w_stab_trunc"])
                             .mean()),
        max_w_stab_untrunc=float(w_all["w_stab"].max()),
        max_w_stab_trunc=float(w_all["w_stab_trunc"].max()),
        ess_trunc_all_atrisk_rows=ess_all,
        ess_over_n_all_atrisk_rows=ess_all / len(w_all),
        ess_trunc_cc_sample=ess_cc,
        ess_over_n_cc_sample=ess_cc / len(cc),
    )
    # predicted observation probability actually used (lag-day lookup):
    # p_hat = p_marg / w_stab (exact algebraic inverse of stabilization)
    phat_used = p_marg / w_all["w_stab"]
    d.update(pct_rows(phat_used, "pred_p"))
    d.update(pct_rows(w_all["w_stab"], "w_stab"))
    d.update(pct_rows(w_all["w_stab_trunc"], "w_stab_trunc"))
    return d, cc


def integrity_checks(v, variant, md, grid, wdf, cc):
    """Integrity checks requested in sec 9.9 task 2 (also applied to the
    onset variant for symmetry). Returns dict of check -> value/pass."""
    chk = {}
    # 1. observation indicator == raw wellness availability on same grid row
    obs = grid.set_index(["player_id", "date"])[f"obs_{v}"]
    base = grid.set_index(["player_id", "date"])[v]
    chk["ic_obs_indicator_eq_raw_notna"] = bool(
        (obs == base.notna().astype(int)).all())
    # 2. weight keys unique and attach to same player-date as outcome row
    wk = wdf[["player_id", "date"]]
    chk["ic_weight_key_unique"] = not bool(wk.duplicated().any())
    chk["ic_n_cc_rows_total"] = int(len(cc) + 0)  # post weight-drop frame
    # 3. lag lookup = previous at-risk row of same player (shift(1))
    md2 = md.sort_values(["player_id", "date"]).reset_index(drop=True)
    lag = md2.groupby("player_id")["date"].shift(1)
    lag2 = (wdf.sort_values(["player_id", "date"])
            .reset_index(drop=True)["lag_date"])
    eq = ((lag == lag2) | (lag.isna() & lag2.isna()))
    chk["ic_lag_eq_prev_atrisk_row"] = bool(eq.all())
    chk["ic_n_rows_lag_na_first_atrisk"] = int(lag.isna().sum())
    # 4. truncation exactly at 1st/99th percentile of untruncated w_stab
    w = wdf["w_stab"].dropna()
    lo, hi = w.quantile([0.01, 0.99])
    recomputed = w.clip(lo, hi).values
    stored = wdf["w_stab_trunc"].dropna().values
    chk["ic_trunc_max_abs_diff"] = float(np.max(np.abs(recomputed - stored)))
    chk["ic_trunc_exact_1_99"] = bool(chk["ic_trunc_max_abs_diff"] < 1e-12)
    # 5. ESS recomputed independently (numpy direct, over CC sample)
    wtr = cc["w_stab_trunc"].values
    ess_cc = float(wtr.sum() ** 2 / (wtr ** 2).sum())
    chk["ic_ess_cc_sample_independent"] = ess_cc
    # 6. exposure/weight reference-day alignment: share of CC rows where the
    #    raw variable was actually observed on the lag_date the weight
    #    references (the analyzed recent3 exposure may originate from t-2/t-3)
    lk = grid.set_index(["player_id", "date"])[f"obs_{v}"]
    lag_keys = list(zip(cc["player_id"], cc["lag_date"]))
    obs_on_lag = np.array([lk.get(k, np.nan) for k in lag_keys], dtype=float)
    chk["ic_cc_frac_lagday_raw_observed"] = float(np.nanmean(obs_on_lag))
    chk["ic_cc_n_lagday_raw_missing"] = int(np.nansum(obs_on_lag == 0))
    return chk


# ---------------------------------------------------------------------------
# plots
# ---------------------------------------------------------------------------

def make_plots(store):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for variant in ["onset", "nooutcome"]:
        # predicted observation probability
        fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=False)
        for ax, v in zip(axes, PRIMARY):
            p = store[(v, variant)]["p_marg"] / \
                store[(v, variant)]["w_all"]["w_stab"]
            ax.hist(p, bins=60, color="steelblue", edgecolor="white",
                    linewidth=0.3)
            ax.set_title(v)
            ax.set_xlabel("predicted P(observed) on referenced lag day")
        axes[0].set_ylabel("count")
        tag = ("with onset_day (R1_REVISION_SAP)" if variant == "onset"
               else "without onset_day (R2_REVIEWER_REQUESTED)")
        fig.suptitle(f"Predicted observation probability — obs model {tag}")
        fig.tight_layout()
        fig.savefig(OUTDIR / f"fig_predprob_{variant}.png", dpi=150)
        plt.close(fig)

        for kind, col in [("untrunc", "w_stab"), ("trunc", "w_stab_trunc")]:
            fig, axes = plt.subplots(1, 3, figsize=(13, 4))
            for ax, v in zip(axes, PRIMARY):
                w = store[(v, variant)]["w_all"][col]
                ax.hist(w, bins=60, color="darkorange", edgecolor="white",
                        linewidth=0.3)
                ax.set_title(v)
                ax.set_xlabel(f"stabilized weight ({col})")
            axes[0].set_ylabel("count")
            ttl = ("Untruncated" if kind == "untrunc"
                   else "Truncated at 1st/99th percentile")
            fig.suptitle(f"{ttl} stabilized IPW weights — obs model {tag}")
            fig.tight_layout()
            fig.savefig(OUTDIR / f"fig_weights_{kind}_{variant}.png", dpi=150)
            plt.close(fig)
    log("plots written (6 figures)")


# ---------------------------------------------------------------------------
# stage 1
# ---------------------------------------------------------------------------

def stage1():
    import statsmodels.formula.api as smf  # noqa: F401 (availability check)
    WORK.mkdir(parents=True, exist_ok=True)
    md = pd.read_csv(OUT_ALL / "modeling_dataset.csv", parse_dates=["date"])
    base = pd.read_csv(SB / "02_RAW_DATA" / "rebuilt_player_day_base.csv",
                       parse_dates=["date"])
    log(f"modeling_dataset: {md.shape}; grid: {base.shape}")

    # ---- refit WITH onset_day (reproduction check of stored weights) ------
    log("\n[stage1] refit obs model WITH onset_day (reproduction check only)")
    grid_o, phat_o, auc_o, info_o = build_grid_and_fit(
        md, base, OBS_FORMULA_ONSET)
    w_onset_refit = compute_weights(md, grid_o, phat_o)

    repro = {}
    for v in PRIMARY:
        stored = pd.read_csv(RUN / f"ipw_weights_{v}.csv",
                             parse_dates=["date"])
        refit = w_onset_refit[v]["df"][["player_id", "date", "w_stab",
                                        "w_stab_trunc"]]
        m = stored.merge(refit, on=["player_id", "date"],
                         suffixes=("_stored", "_refit"))
        d_stab = (m["w_stab_stored"] - m["w_stab_refit"]).abs().max()
        d_tr = (m["w_stab_trunc_stored"]
                - m["w_stab_trunc_refit"]).abs().max()
        repro[v] = dict(max_abs_diff_w_stab=float(d_stab),
                        max_abs_diff_w_stab_trunc=float(d_tr),
                        n_rows=int(len(m)))
        log(f"  repro [{v}]: max|diff| w_stab={d_stab:.3e}, "
            f"w_stab_trunc={d_tr:.3e} over {len(m)} rows")
    (WORK / "repro_check_onset_refit.json").write_text(json.dumps(repro,
                                                                  indent=2))

    # ---- refit WITHOUT onset_day (NEW R2_REVIEWER_REQUESTED variant) ------
    log("\n[stage1] fit obs model WITHOUT onset_day (R2_REVIEWER_REQUESTED)")
    grid_n, phat_n, auc_n, info_n = build_grid_and_fit(
        md, base, OBS_FORMULA_NOOUTCOME)
    w_noout = compute_weights(md, grid_n, phat_n)
    for v in PRIMARY:
        o = w_noout[v]["df"][["player_id", "date", "w_stab", "w_stab_trunc"]]
        o.to_csv(OUTDIR / f"ipw_weights_nooutcome_{v}.csv", index=False,
                 date_format="%Y-%m-%d")
        log(f"  wrote ipw_weights_nooutcome_{v}.csv ({len(o)} rows)")
    pd.DataFrame(info_n).to_csv(WORK / "obs_model_nooutcome_fit_info.csv",
                                index=False)

    # ---- diagnostics for both variants ------------------------------------
    # onset variant: weights + p_marg taken from the EXISTING run files
    log("\n[stage1] diagnostics (both variants)")
    diag_w = pd.read_csv(RUN / "ipw_weight_diagnostics.csv")
    obs_res = pd.read_csv(OUT_ALL / "observation_model_results.csv")
    auc_r1 = {r["variable"]: float(r["coef"]) for _, r in
              obs_res[(obs_res.row_type == "metric")
                      & (obs_res.term == "auc")].iterrows()}

    store, diag_rows, ic_rows = {}, [], {}
    for v in PRIMARY:
        stored = pd.read_csv(RUN / f"ipw_weights_{v}.csv",
                             parse_dates=["date"])
        md2 = md.sort_values(["player_id", "date"]).reset_index(drop=True)
        md2["lag_date"] = md2.groupby("player_id")["date"].shift(1)
        wdf = md2.merge(stored, on=["player_id", "date"], how="left")
        # attach stored phat implied by stored weights
        p_marg = float(diag_w.loc[diag_w.variable == v,
                                  "p_marginal_observed"].iloc[0])
        wdf[f"phat_{v}"] = p_marg / wdf["w_stab"]
        lo, hi = wdf["w_stab"].quantile([0.01, 0.99])
        n_na = int(wdf["w_stab"].isna().sum())
        d, cc = variant_diagnostics(
            v, "onset", md, wdf, p_marg, lo, hi, n_na,
            OBS_FORMULA_ONSET, auc_r1[v])
        diag_rows.append(d)
        ic_rows[(v, "onset")] = integrity_checks(v, "onset", md, grid_o,
                                                 wdf, cc)
        store[(v, "onset")] = dict(w_all=wdf.dropna(subset=["w_stab"]),
                                   p_marg=p_marg)

    for v in PRIMARY:
        wdf = w_noout[v]["df"]
        d, cc = variant_diagnostics(
            v, "nooutcome", md, wdf, w_noout[v]["p_marg"],
            w_noout[v]["lo"], w_noout[v]["hi"], w_noout[v]["n_na_lag"],
            OBS_FORMULA_NOOUTCOME, auc_n[v])
        diag_rows.append(d)
        ic_rows[(v, "nooutcome")] = integrity_checks(v, "nooutcome", md,
                                                     grid_n, wdf, cc)
        store[(v, "nooutcome")] = dict(
            w_all=wdf.dropna(subset=["w_stab"]), p_marg=w_noout[v]["p_marg"])

    diag = pd.DataFrame(diag_rows)
    diag.to_csv(WORK / "diagnostics_stage1.csv", index=False)
    ic = pd.DataFrame([dict(wellness_variant=v, obs_model_variant=vv, **c)
                       for (v, vv), c in ic_rows.items()])
    ic.to_csv(WORK / "integrity_checks_stage1.csv", index=False)
    log(f"\n[stage1] diagnostics rows: {len(diag)}; integrity checks written")
    log(diag[["wellness_variant", "obs_model_variant", "n_complete_case",
              "n_onset_days_cc", "n_event_players_cc", "max_w_stab_untrunc",
              "max_w_stab_trunc", "ess_trunc_cc_sample",
              "ess_over_n_cc_sample"]].to_string(index=False))

    make_plots(store)
    log("[stage1] done")


# ---------------------------------------------------------------------------
# finalize (after R)
# ---------------------------------------------------------------------------

def finalize():
    WORK.mkdir(parents=True, exist_ok=True)
    diag = pd.read_csv(WORK / "diagnostics_stage1.csv")
    ic = pd.read_csv(WORK / "integrity_checks_stage1.csv")
    r_res = pd.read_csv(OUTDIR / "ipw_final_r_results.csv")
    master = pd.read_csv(RUN / "master_results.csv")

    tax = {"onset": "R1_REVISION_SAP", "nooutcome": "R2_REVIEWER_REQUESTED"}
    model_id = {"onset": "IPW_onset", "nooutcome": "IPW_nooutcome"}

    # ---------------- IPW_FINAL_RESULTS.csv -------------------------------
    rows = []
    repro_check = {}
    for v in PRIMARY:
        it_term = f"acute_load_7d_wp_z:{WELL_Z[v]}"
        for variant in ["onset", "nooutcome"]:
            dd = diag[(diag.wellness_variant == v)
                      & (diag.obs_model_variant == variant)].iloc[0]
            rr = r_res[(r_res.wellness_variant == v)
                       & (r_res.obs_model_variant == variant)
                       & (r_res.term == it_term)].iloc[0]
            if variant == "onset":
                # frozen R1 numbers from master_results.csv (authoritative)
                mr = master[(master.analysis_role == "SENSITIVITY_IPW")
                            & (master.model_id == "IPW")
                            & (master.wellness_variant == v)
                            & (master.term == it_term)].iloc[0]
                or_f, lo_f, hi_f, p_f, se_f = (float(mr.OR),
                                               float(mr.CI_low),
                                               float(mr.CI_high),
                                               float(mr.p), float(mr.se))
                # refit agreement (R refit from stored weights vs master)
                repro_check[v] = dict(
                    OR_master=or_f, OR_refit=float(rr.OR),
                    abs_diff_OR=abs(or_f - float(rr.OR)),
                    p_master=p_f, p_refit=float(rr.p))
                notes = ("frozen from RUN_R2_REPRO/master_results.csv "
                         f"(R refit agreement dOR={abs(or_f - float(rr.OR)):.2e}); "
                         "stabilised IPW, 1/99 trunc; observation model "
                         "includes onset_day")
            else:
                or_f, lo_f, hi_f, p_f, se_f = (float(rr.OR), float(rr.CI_low),
                                               float(rr.CI_high),
                                               float(rr.p), float(rr.se))
                notes = ("NEW R2 reviewer-requested sensitivity: observation "
                         "model WITHOUT onset_day (no R1 counterpart exists); "
                         "stabilised IPW, 1/99 trunc")
            rows.append(dict(
                analysis_role="SENSITIVITY_IPW",
                model_id=model_id[variant], wellness_variant=v,
                term=it_term, OR=or_f, CI_low=lo_f, CI_high=hi_f, p=p_f,
                se=se_f, converged=True,
                optimizer="glm binomial weighted + clubSandwich CR2 "
                          "cluster(player)",
                n=int(dd.n_complete_case),
                players=int(dd.n_players_cc),
                events=int(dd.n_onset_days_cc),
                ess_trunc_cc_sample=float(dd.ess_trunc_cc_sample),
                ess_over_n_cc_sample=float(dd.ess_over_n_cc_sample),
                ess_trunc_all_atrisk_rows=float(dd.ess_trunc_all_atrisk_rows),
                max_w_stab_untrunc=float(dd.max_w_stab_untrunc),
                max_w_stab_trunc=float(dd.max_w_stab_trunc),
                notes=notes, taxonomy=tax[variant]))
    res = pd.DataFrame(rows)
    res.to_csv(OUTDIR / "IPW_FINAL_RESULTS.csv", index=False)
    log(f"[finalize] wrote IPW_FINAL_RESULTS.csv ({len(res)} rows)")
    (WORK / "repro_check_onset_outcome_refit.json").write_text(
        json.dumps(repro_check, indent=2))

    # ---------------- IPW_FINAL_DIAGNOSTICS.csv ---------------------------
    long_rows = []
    for _, r in diag.iterrows():
        v, variant = r["wellness_variant"], r["obs_model_variant"]
        for col in diag.columns:
            if col in ("wellness_variant", "obs_model_variant"):
                continue
            long_rows.append(dict(
                wellness_variant=v, obs_model_variant=variant,
                model_id=model_id[variant], metric=col, value=r[col],
                taxonomy=tax[variant]))
    for _, r in ic.iterrows():
        v, variant = r["wellness_variant"], r["obs_model_variant"]
        for col in ic.columns:
            if col in ("wellness_variant", "obs_model_variant"):
                continue
            long_rows.append(dict(
                wellness_variant=v, obs_model_variant=variant,
                model_id=model_id[variant], metric=col, value=r[col],
                taxonomy=tax[variant]))
    # outcome-model interaction rows as metrics
    for _, r in res.iterrows():
        variant = ("onset" if r["model_id"] == "IPW_onset" else "nooutcome")
        for m, val in [("interaction_OR", r.OR), ("interaction_CI_low",
                                                  r.CI_low),
                       ("interaction_CI_high", r.CI_high),
                       ("interaction_p", r.p), ("interaction_se", r.se)]:
            long_rows.append(dict(
                wellness_variant=r.wellness_variant,
                obs_model_variant=variant, model_id=r.model_id,
                metric=m, value=val, taxonomy=r.taxonomy))
    longd = pd.DataFrame(long_rows)
    longd.to_csv(OUTDIR / "IPW_FINAL_DIAGNOSTICS.csv", index=False)
    log(f"[finalize] wrote IPW_FINAL_DIAGNOSTICS.csv ({len(longd)} rows)")

    # ---------------- PASS/FAIL vs established R1 numbers ------------------
    pf = []
    for v in PRIMARY:
        dd = diag[(diag.wellness_variant == v)
                  & (diag.obs_model_variant == "onset")].iloc[0]
        ref = R1_INTERACTION[v]
        got = res[(res.wellness_variant == v)
                  & (res.model_id == "IPW_onset")].iloc[0]
        ok_n = int(dd.n_complete_case) == R1_CC_N[v]
        ok_or = abs(got.OR - ref["OR"]) < 5e-5
        ok_ci = (abs(got.CI_low - ref["lo"]) < 5e-5
                 and abs(got.CI_high - ref["hi"]) < 5e-5)
        ok_p = True if ref["p"] is None else abs(got.p - ref["p"]) < 5e-5
        ok_w = repro[v]["max_abs_diff_w_stab"] < 1e-8 \
            if (repro := json.loads(
                (WORK / "repro_check_onset_refit.json").read_text())) else False
        status = "PASS" if all([ok_n, ok_or, ok_ci, ok_p, ok_w]) else "FAIL"
        pf.append(dict(wellness_variant=v, n_cc_ok=ok_n, OR_ok=ok_or,
                       CI_ok=ok_ci, p_ok=ok_p, weights_refit_ok=bool(ok_w),
                       status=status))
        log(f"[finalize] R1 reproduction check [{v}]: {status} "
            f"(n={int(dd.n_complete_case)} vs {R1_CC_N[v]}, "
            f"OR={got.OR:.4f} vs {ref['OR']}, "
            f"weights max|diff|={repro[v]['max_abs_diff_w_stab']:.2e})")
    pd.DataFrame(pf).to_csv(WORK / "r1_reproduction_passfail.csv",
                            index=False)

    # ---------------- comparison onset vs nooutcome (log scale) ------------
    cmp_rows = []
    for v in PRIMARY:
        a = res[(res.wellness_variant == v)
                & (res.model_id == "IPW_onset")].iloc[0]
        b = res[(res.wellness_variant == v)
                & (res.model_id == "IPW_nooutcome")].iloc[0]
        d_log = abs(np.log(b.OR) - np.log(a.OR))
        pct = 100 * d_log / abs(np.log(a.OR))
        cmp_rows.append(dict(wellness_variant=v,
                             OR_onset=a.OR, OR_nooutcome=b.OR,
                             abs_diff_log_scale=d_log,
                             pct_change_log_scale=pct))
        log(f"[finalize] {v}: OR onset={a.OR:.4f} -> nooutcome={b.OR:.4f}; "
            f"|d(logOR)|={d_log:.4f} ({pct:.1f}% of |logOR_onset|)")
    pd.DataFrame(cmp_rows).to_csv(WORK / "onset_vs_nooutcome_comparison.csv",
                                  index=False)
    log("[finalize] done")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["stage1", "finalize"])
    args = ap.parse_args()
    try:
        {"stage1": stage1, "finalize": finalize}[args.stage]()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
