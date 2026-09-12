#!/usr/bin/env python3
"""
03_missingness_ipw.py
=====================
Phase 8 of the PLOS ONE R1 revision (SoccerMon): missing-data audit of the
seven wellness variables, observation (missingness) models for the three
primary wellness exposures, and inverse-probability-of-observation (IPW)
weights with diagnostics.

Inputs (read-only)
------------------
02_RAW_DATA/rebuilt_player_day_base.csv     (36,550 player-day grid, raw wellness + load)
07_ANALYSIS_OUTPUTS/modeling_dataset.csv    (36,296 at-risk player-days, lagged exposures, onsets)

Outputs
-------
07_ANALYSIS_OUTPUTS/missingness_by_variable.csv
07_ANALYSIS_OUTPUTS/missingness_by_player.csv
07_ANALYSIS_OUTPUTS/observation_model_results.csv
07_ANALYSIS_OUTPUTS/ipw_diagnostics.csv
07_ANALYSIS_OUTPUTS/ipw_effective_sample_size.csv
07_ANALYSIS_OUTPUTS/ipw_extreme_weights.csv
05_REVISION_SAP/missing_data_plan.md
logs/03_missingness.log

Design decisions (documented in missing_data_plan.md)
-----------------------------------------------------
- The observation model is FIT on the 36,296 at-risk player-days (the risk set
  of the injury analysis), outcome = wellness variable recorded on that day.
- Predicted probabilities p_hat are then scored on the FULL 36,550-day grid,
  because the weight for injury-model row t must reference the day the lag-1
  exposure was actually recorded, i.e. day t-1, which can fall outside the
  risk set (post-onset washout days).
- IPW weight for row t and variable v:  w_t = 1 / p_hat_v(player, t-1).
  Stabilized: sw_t = P_marginal(observed) / p_hat_v(player, t-1), with the
  marginal probability taken from the fit sample.
- Complete case for variable v = modeling row with v_lag1 non-missing.
- Stabilized weights are truncated at their 1st/99th within-variable
  percentiles for the primary IPW diagnostic (ESS).
- prev_episode_ever / onset_day are reconstructed on the full grid from the
  42 onset days so that scoring outside the risk set is possible.
"""

import os
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.metrics import roc_auc_score

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
WS = Path(os.environ.get("SOCCERMON_WORKSPACE", REPO_ROOT / "workspace")).resolve()
OUT = WS / "07_ANALYSIS_OUTPUTS"
LOG = WS / "logs" / "03_missingness.log"
LOG.parent.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

WELLNESS = ["fatigue", "readiness", "soreness", "mood", "stress",
            "sleep_quality", "sleep_duration"]
PRIMARY = ["fatigue", "readiness", "soreness"]
BURDEN_Z = {"fatigue": "fatigue_burden_wp_z",
            "readiness": "readiness_deficit_wp_z",
            "soreness": "soreness_burden_wp_z"}

_log_fh = open(LOG, "w", encoding="utf-8")


def log(msg=""):
    print(msg)
    _log_fh.write(str(msg) + "\n")
    _log_fh.flush()


def main():
    log("=" * 72)
    log("03_missingness_ipw.py — Phase 8 missing-data audit + IPW")
    log("=" * 72)

    md = pd.read_csv(OUT / "modeling_dataset.csv", parse_dates=["date"])
    base = pd.read_csv(WS / "02_RAW_DATA" / "rebuilt_player_day_base.csv",
                       parse_dates=["date"])
    log(f"modeling_dataset: {md.shape[0]} rows x {md.shape[1]} cols")
    log(f"player-day grid : {base.shape[0]} rows x {base.shape[1]} cols")

    # ------------------------------------------------------------------ #
    # Enrich the full grid: risk-set flag, onset info, observation flags  #
    # ------------------------------------------------------------------ #
    grid = base.copy()
    md_keys = set(zip(md["player_id"], md["date"]))
    grid["in_risk_set"] = [(p, d) in md_keys
                           for p, d in zip(grid["player_id"], grid["date"])]
    log(f"risk-set days on grid: {grid['in_risk_set'].sum()} "
        f"(excluded: {(~grid['in_risk_set']).sum()})")

    onsets = md.loc[md["onset_day"] == 1, ["player_id", "date"]].copy()
    log(f"onset days: {len(onsets)} across {onsets['player_id'].nunique()} players")

    grid = grid.sort_values(["player_id", "date"]).reset_index(drop=True)
    grid["onset_day"] = 0
    ons_keys = set(zip(onsets["player_id"], onsets["date"]))
    grid.loc[[(p, d) in ons_keys for p, d in zip(grid["player_id"], grid["date"])],
             "onset_day"] = 1
    # prev_episode_ever: >=1 onset strictly before day t
    grid["prev_episode_ever"] = (
        grid.groupby("player_id")["onset_day"].cumsum() - grid["onset_day"]
    ).clip(upper=1).astype(int)

    # observation indicators per wellness variable + lagged (t-1) versions
    for v in WELLNESS:
        grid[f"obs_{v}"] = grid[v].notna().astype(int)
        grid[f"obs_{v}_lag1"] = (
            grid.groupby("player_id")[f"obs_{v}"].shift(1)
        )
    grid["any_report_lag1"] = grid.groupby("player_id")["wellness_any_record"].shift(1)

    # onset in previous 7 days [t-7, t-1] / next 7 days [t+1, t+7]
    def roll_onset(s, win, past=True):
        if past:
            return s.shift(1).rolling(win, min_periods=1).max()
        return s.shift(-1)[::-1].rolling(win, min_periods=1).max()[::-1]

    grid["onset_prev7"] = grid.groupby("player_id")["onset_day"].transform(
        lambda s: roll_onset(s, 7, past=True)).fillna(0).astype(int)
    grid["onset_next7"] = grid.groupby("player_id")["onset_day"].transform(
        lambda s: roll_onset(s, 7, past=False)).fillna(0).astype(int)

    # monitoring window: first-to-last day with any wellness record, per player
    rec = grid.loc[grid["wellness_any_record"] == 1]
    win = rec.groupby("player_id")["date"].agg(["min", "max"])
    grid["win_min"] = grid["player_id"].map(win["min"])
    grid["win_max"] = grid["player_id"].map(win["max"])
    grid["in_window"] = ((grid["date"] >= grid["win_min"]) &
                         (grid["date"] <= grid["win_max"])).astype(int)
    log(f"monitoring-window player-days: {grid['in_window'].sum()} "
        f"(expected 25,003)")

    # season == calendar year (verified), calendar_time = days since 2020-01-01
    grid["season"] = grid["date"].dt.year

    # ================================================================== #
    # PART A — per-variable missingness audit                             #
    # ================================================================== #
    log("\n--- Part A: missingness audit ---")
    rows_a = []
    for v in WELLNESS:
        n_grid = len(grid)
        n_obs = int(grid[f"obs_{v}"].sum())
        gw = grid.loc[grid["in_window"] == 1]
        n_win = len(gw)
        n_obs_win = int(gw[f"obs_{v}"].sum())
        rows_a.append(dict(variable=v, scope="overall_grid", stratum_type="ALL",
                           stratum="ALL", n_days=n_grid, n_observed=n_obs,
                           missing_rate=1 - n_obs / n_grid))
        rows_a.append(dict(variable=v, scope="monitoring_window", stratum_type="ALL",
                           stratum="ALL", n_days=n_win, n_observed=n_obs_win,
                           missing_rate=1 - n_obs_win / n_win))
        log(f"{v:15s} grid missing {1-n_obs/n_grid:.3f} "
            f"({n_grid-n_obs}/{n_grid}); in-window missing "
            f"{1-n_obs_win/n_win:.3f} ({n_win-n_obs_win}/{n_win})")

    # stratification variables on the full grid
    grid["daily_load_q"] = pd.qcut(grid["daily_load"], 4, duplicates="drop")
    grid["ctl28_q"] = pd.qcut(grid["ctl28"], 4, duplicates="drop")
    grid["prev_day_report"] = grid["any_report_lag1"].fillna(0).astype(int)
    strata = {
        "team": grid["team"].astype(str),
        "season": grid["season"].astype(str),
        "month": grid["month"].astype(str),
        "day_of_week": grid["day_of_week"].astype(str),
        "daily_load_quantile": grid["daily_load_q"].astype(str),
        "ctl28_quantile": grid["ctl28_q"].astype(str),
        "prev_day_report": grid["prev_day_report"].astype(str),
        "onset_prev_7d": grid["onset_prev7"].astype(str),
        "onset_next_7d": grid["onset_next7"].astype(str),
    }
    for v in WELLNESS:
        for sname, scol in strata.items():
            for lev, idx in scol.groupby(scol).groups.items():
                sub = grid.loc[idx]
                n = len(sub)
                no = int(sub[f"obs_{v}"].sum())
                rows_a.append(dict(variable=v, scope="overall_grid",
                                   stratum_type=sname, stratum=str(lev),
                                   n_days=n, n_observed=no,
                                   missing_rate=1 - no / n))
    miss_var = pd.DataFrame(rows_a)
    miss_var.to_csv(OUT / "missingness_by_variable.csv", index=False)
    log(f"wrote missingness_by_variable.csv ({len(miss_var)} rows)")

    # per-player file
    rows_p = []
    for pid, g in grid.groupby("player_id"):
        team = g["team"].iloc[0]
        gw = g.loc[g["in_window"] == 1]
        for v in WELLNESS:
            rows_p.append(dict(
                player_id=pid, team=team, variable=v,
                n_grid_days=len(g), n_observed_grid=int(g[f"obs_{v}"].sum()),
                missing_rate_grid=1 - g[f"obs_{v}"].mean(),
                n_window_days=len(gw),
                n_observed_window=int(gw[f"obs_{v}"].sum()),
                missing_rate_window=(1 - gw[f"obs_{v}"].mean()
                                     if len(gw) else np.nan)))
    miss_pl = pd.DataFrame(rows_p)
    miss_pl.to_csv(OUT / "missingness_by_player.csv", index=False)
    log(f"wrote missingness_by_player.csv ({len(miss_pl)} rows); "
        f"per-player in-window missing rate range "
        f"[{miss_pl['missing_rate_window'].min():.3f}, "
        f"{miss_pl['missing_rate_window'].max():.3f}]")

    # ================================================================== #
    # PART B — observation models (fit on at-risk days, score full grid)  #
    # ================================================================== #
    log("\n--- Part B: observation models ---")
    fit_df = grid.loc[grid["in_risk_set"] == 1].copy()
    for v in PRIMARY:
        fit_df[f"obs_{v}_lag1"] = fit_df[f"obs_{v}_lag1"].fillna(0).astype(int)
        grid[f"obs_{v}_lag1"] = grid[f"obs_{v}_lag1"].fillna(0).astype(int)
    # standardized continuous predictors (scaling from the fit sample)
    for c, cz in [("daily_load", "daily_load_z"),
                  ("calendar_time", "calendar_time_z")]:
        if c == "calendar_time":
            fit_df[c] = (fit_df["date"] - pd.Timestamp("2020-01-01")).dt.days
            grid[c] = (grid["date"] - pd.Timestamp("2020-01-01")).dt.days
        mu, sd = fit_df[c].mean(), fit_df[c].std(ddof=1)
        fit_df[cz] = (fit_df[c] - mu) / sd
        grid[cz] = (grid[c] - mu) / sd
        log(f"standardized {c}: mean={mu:.2f} sd={sd:.2f}")

    obs_rows = []
    phat = {}  # variable -> Series indexed like grid
    for v in PRIMARY:
        formula_full = (f"obs_{v} ~ daily_load_z + C(team) + C(season) + "
                        f"calendar_time_z + C(day_of_week) + obs_{v}_lag1 + "
                        f"prev_episode_ever + onset_day")
        dropped = []
        res = None
        for drop in [[], ["onset_day"], ["onset_day", "prev_episode_ever"]]:
            f = formula_full
            for d in drop:
                f = f.replace(f" + {d}", "")
            try:
                m = smf.logit(f, data=fit_df)
                res = m.fit(disp=0, maxiter=200, cov_type="cluster",
                            cov_kwds={"groups": fit_df["player_id"]})
                dropped = drop
                if not res.mle_retvals.get("converged", True):
                    log(f"WARNING: {v} model did not converge with formula "
                        f"[{f}]; trying simpler model")
                    continue
                break
            except Exception as e:
                log(f"WARNING: {v} model failed with formula [{f}]: "
                    f"{type(e).__name__}: {e}; trying simpler model")
                continue
        if res is None:
            raise RuntimeError(f"observation model for {v} failed in all forms")
        if dropped:
            log(f"NOTE: {v} model fitted after dropping {dropped}")

        y = fit_df[f"obs_{v}"].values
        p_fit = res.predict(fit_df)
        auc = roc_auc_score(y, p_fit)
        log(f"\n[{v}] N={len(fit_df)}, observed={y.sum()} "
            f"({y.mean():.3f}), AUC={auc:.3f}")
        obs_rows.append(dict(variable=v, row_type="metric", term="n_days",
                             coef=len(fit_df)))
        obs_rows.append(dict(variable=v, row_type="metric", term="n_observed",
                             coef=int(y.sum())))
        obs_rows.append(dict(variable=v, row_type="metric", term="event_rate",
                             coef=y.mean()))
        obs_rows.append(dict(variable=v, row_type="metric", term="auc", coef=auc))
        pq = np.percentile(p_fit, [0, 1, 25, 50, 75, 99, 100])
        for lab, val in zip(["pred_p_min", "pred_p_p1", "pred_p_p25",
                             "pred_p_p50", "pred_p_p75", "pred_p_p99",
                             "pred_p_max"], pq):
            obs_rows.append(dict(variable=v, row_type="metric", term=lab,
                                 coef=val))
        params = res.params
        for term in params.index:
            ci = res.conf_int().loc[term]
            orow = dict(variable=v, row_type="term", term=term,
                        coef=params[term], std_err=res.bse[term],
                        z=res.tvalues[term], p_value=res.pvalues[term],
                        odds_ratio=np.exp(params[term]),
                        ci_lo=np.exp(ci[0]), ci_hi=np.exp(ci[1]))
            obs_rows.append(orow)
            sig = "*" if res.pvalues[term] < 0.05 else " "
            log(f"  {term:35s} OR={orow['odds_ratio']:7.3f} "
                f"[{orow['ci_lo']:.3f},{orow['ci_hi']:.3f}] {sig}")
        phat[v] = res.predict(grid).clip(1e-4, 1 - 1e-4)

    obs_res = pd.DataFrame(obs_rows)
    obs_res.to_csv(OUT / "observation_model_results.csv", index=False)
    log(f"\nwrote observation_model_results.csv ({len(obs_res)} rows)")

    for v in PRIMARY:
        grid[f"phat_{v}"] = phat[v].values

    # ================================================================== #
    # PART C — IPW weights and diagnostics                                #
    # ================================================================== #
    log("\n--- Part C: IPW diagnostics ---")
    md2 = md.sort_values(["player_id", "date"]).reset_index(drop=True)
    md2["lag_date"] = md2.groupby("player_id")["date"].shift(1)
    p_lookup = grid.set_index(["player_id", "date"])

    diag_rows, ess_rows, ext_rows = [], [], []
    qs = [0, .01, .05, .25, .50, .75, .95, .99, 1.0]
    q_labs = ["min", "p1", "p5", "p25", "p50", "p75", "p95", "p99", "max"]

    for v in PRIMARY:
        cc = md2.loc[md2[f"{v}_lag1"].notna()].copy()
        lk = p_lookup[[f"phat_{v}", "team", "season", "daily_load"]]
        cc = cc.join(lk, on=["player_id", "lag_date"], rsuffix="_lag")
        n_drop = int(cc[f"phat_{v}"].isna().sum())
        cc = cc.dropna(subset=[f"phat_{v}"])
        p_marg = grid.loc[grid["in_risk_set"] == 1, f"obs_{v}"].mean()
        cc["w_unstab"] = 1.0 / cc[f"phat_{v}"]
        cc["w_stab"] = p_marg / cc[f"phat_{v}"]
        lo, hi = cc["w_stab"].quantile([0.01, 0.99])
        cc["w_stab_trunc"] = cc["w_stab"].clip(lo, hi)

        n_cc = len(cc)
        ess_un = cc["w_stab"].sum() ** 2 / (cc["w_stab"] ** 2).sum()
        ess_tr = cc["w_stab_trunc"].sum() ** 2 / (cc["w_stab_trunc"] ** 2).sum()
        ess_rows.append(dict(
            variable=v, n_at_risk=len(md2), n_complete_case=n_cc,
            complete_case_rate=n_cc / len(md2),
            n_cc_dropped_no_lag_phat=n_drop,
            p_marginal_observed=p_marg,
            ess_untruncated=ess_un, ess_truncated_1_99=ess_tr,
            ess_n_ratio_truncated=ess_tr / n_cc,
            max_sw_untruncated=cc["w_stab"].max(),
            max_sw_truncated=cc["w_stab_trunc"].max()))
        log(f"\n[{v}] complete cases {n_cc}/{len(md2)} "
            f"({n_cc/len(md2):.3f}); lag-day p_hat missing for {n_drop} rows")
        log(f"  marginal P(observed)={p_marg:.3f}")
        log(f"  max stabilized weight: {cc['w_stab'].max():.2f} "
            f"(truncated {cc['w_stab_trunc'].max():.2f})")
        log(f"  ESS: {ess_un:.0f} untruncated, {ess_tr:.0f} truncated "
            f"(ESS/N = {ess_tr/n_cc:.3f})")

        for wcol, wlab in [("w_unstab", "unstabilized"),
                           ("w_stab", "stabilized"),
                           ("w_stab_trunc", "stabilized_trunc_1_99")]:
            vals = np.quantile(cc[wcol], qs)
            for lab, val in zip(q_labs, vals):
                diag_rows.append(dict(variable=v, section="weight_quantile",
                                      stratum=wlab, metric=lab, value=val,
                                      note=""))
            diag_rows.append(dict(variable=v, section="weight_quantile",
                                  stratum=wlab, metric="frac_gt10",
                                  value=(cc[wcol] > 10).mean(), note=""))
            diag_rows.append(dict(variable=v, section="weight_quantile",
                                  stratum=wlab, metric="frac_gt20",
                                  value=(cc[wcol] > 20).mean(), note=""))

        # positivity: p_hat range on the lag days actually used, by team x season
        for (tm, se), g in cc.groupby(["team_lag", "season_lag"]):
            diag_rows.append(dict(variable=v, section="positivity",
                                  stratum=f"{tm} x {se}", metric="n",
                                  value=len(g), note=""))
            diag_rows.append(dict(variable=v, section="positivity",
                                  stratum=f"{tm} x {se}", metric="p_hat_min",
                                  value=g[f"phat_{v}"].min(), note=""))
            diag_rows.append(dict(variable=v, section="positivity",
                                  stratum=f"{tm} x {se}", metric="p_hat_max",
                                  value=g[f"phat_{v}"].max(), note=""))

        # extreme weights (top 10 truncated-basis stabilized)
        top = cc.nlargest(10, "w_stab")
        for rank, (_, r) in enumerate(top.iterrows(), 1):
            ext_rows.append(dict(
                variable=v, rank=rank, player_id=r["player_id"],
                lag_date=r["lag_date"].date(), team=r["team_lag"],
                season=r["season_lag"], daily_load_lag=r["daily_load"],
                p_hat=r[f"phat_{v}"], w_stab=r["w_stab"],
                onset_day=r["onset_day"], prev_episode_ever=r["prev_episode_ever"]))

        # exposure distribution: all at-risk vs complete-case vs IPW-weighted CC
        for xcol in ["acute_load_7d_wp_z", BURDEN_Z[v]]:
            allx = md2[xcol].dropna()
            sub = cc.dropna(subset=[xcol])
            m_all = allx.mean()
            m_cc = sub[xcol].mean()
            m_w = np.average(sub[xcol], weights=sub["w_stab_trunc"])
            for met, val in [("mean_all_at_risk", m_all),
                             ("mean_cc_unweighted", m_cc),
                             ("mean_cc_weighted", m_w),
                             ("diff_cc_minus_all", m_cc - m_all),
                             ("diff_weighted_minus_all", m_w - m_all)]:
                diag_rows.append(dict(variable=v, section="exposure_contrast",
                                      stratum=xcol, metric=met, value=val,
                                      note=""))
            log(f"  {xcol}: mean all={m_all:.3f}, CC={m_cc:.3f}, "
                f"weighted={m_w:.3f}")

    diag = pd.DataFrame(diag_rows)
    diag.to_csv(OUT / "ipw_diagnostics.csv", index=False)
    ess = pd.DataFrame(ess_rows)
    ess.to_csv(OUT / "ipw_effective_sample_size.csv", index=False)
    ext = pd.DataFrame(ext_rows)
    ext.to_csv(OUT / "ipw_extreme_weights.csv", index=False)
    log(f"\nwrote ipw_diagnostics.csv ({len(diag)} rows), "
        f"ipw_effective_sample_size.csv, ipw_extreme_weights.csv")

    # ================================================================== #
    # PART D — missing data plan (markdown)                               #
    # ================================================================== #
    log("\n--- Part D: writing 05_REVISION_SAP/missing_data_plan.md ---")
    write_plan(grid, miss_var, obs_res, ess, ext)
    log("done.")


def write_plan(grid, miss_var, obs_res, ess, ext):
    lines = []
    a = lines.append
    a("# Missing-Data Plan — Wellness Exposures (SoccerMon, PLOS ONE R1)")
    a("")
    a("Generated by `06_ANALYSIS_CODE/03_missingness_ipw.py` "
      "(log: `logs/03_missingness.log`). All numbers are computed, not assumed.")
    a("")
    a("## 1. Extent and pattern of missingness")
    a("")
    a("| Variable | Grid missing (n=36,550) | In-window missing (n=25,003) |")
    a("|---|---|---|")
    for v in WELLNESS:
        g = miss_var[(miss_var.variable == v) & (miss_var.scope == "overall_grid")]
        w = miss_var[(miss_var.variable == v) & (miss_var.scope == "monitoring_window")]
        a(f"| {v} | {g.missing_rate.iloc[0]:.3f} | {w.missing_rate.iloc[0]:.3f} |")
    a("")
    a("Stratified missingness (team, season, month, day of week, daily-load and "
      "CTL28 quantiles, previous-day report, onset within previous/next 7 days) "
      "is tabulated in `07_ANALYSIS_OUTPUTS/missingness_by_variable.csv`; "
      "per-player rates in `missingness_by_player.csv`. Reporting is clearly "
      "non-random: it depends on team, calendar period, training load and on "
      "whether the player reported the previous day (see observation models). "
      "The mechanism is therefore at best MAR, and plausibly MNAR (a player who "
      "feels unwell may be more or less likely to file a report).")
    a("")
    a("## 2. Observation models")
    a("")
    a("For each primary variable, Pr(recorded on day t) was modelled by logistic "
      "regression on the 36,296 at-risk player-days with player-clustered "
      "standard errors: `obs ~ daily_load(z) + team + season + calendar_time(z) "
      "+ day_of_week + obs_lag1 + prev_episode_ever + onset_day`. "
      "Full coefficient tables, AUCs and predicted-probability distributions are "
      "in `07_ANALYSIS_OUTPUTS/observation_model_results.csv`.")
    a("")
    a("| Variable | AUC | Key predictors of being observed (OR, 95% CI) |")
    a("|---|---|---|")
    for v in PRIMARY:
        sub = obs_res[(obs_res.variable == v) & (obs_res.row_type == "term")]
        auc = obs_res[(obs_res.variable == v) &
                      (obs_res.term == "auc")].coef.iloc[0]
        keys = []
        for t in ["obs_" + v + "_lag1", "C(team)[T.TeamB]", "daily_load_z",
                  "calendar_time_z", "prev_episode_ever", "onset_day"]:
            r = sub[sub.term == t]
            if len(r):
                r = r.iloc[0]
                keys.append(f"{t}: {r.odds_ratio:.2f} "
                            f"({r.ci_lo:.2f}–{r.ci_hi:.2f})")
        a(f"| {v} | {auc:.3f} | " + "; ".join(keys) + " |")
    a("")
    a("## 3. Pre-specified analysis strategy")
    a("")
    a("- **Primary analysis: complete-case.** The main onset-day models use "
      "player-days with the relevant lagged wellness exposure observed. This is "
      "the transparent reference analysis; the complete-case fraction and the "
      "factors predicting observation (Section 2) are reported alongside it.")
    a("- **Key sensitivity analysis: IPW.** Observation models from Section 2 "
      "provide p_hat for the day each lag-1 exposure was recorded; stabilized "
      "weights sw = P_marginal(observed)/p_hat, truncated at the within-variable "
      "1st/99th percentiles, are applied to the complete-case sample. "
      "Diagnostics in `ipw_diagnostics.csv` / `ipw_effective_sample_size.csv`:")
    a("")
    a("| Variable | CC n | Max sw (trunc) | ESS (trunc) | ESS/n |")
    a("|---|---|---|---|---|")
    for _, r in ess.iterrows():
        a(f"| {r.variable} | {r.n_complete_case} | "
          f"{r.max_sw_untruncated:.1f} ({r.max_sw_truncated:.1f}) | "
          f"{r.ess_truncated_1_99:.0f} | {r.ess_n_ratio_truncated:.2f} |")
    a("")
    a("- **Multilevel multiple imputation: not the primary analysis.** "
      "Feasibility assessment: (i) only 42 onset events and 15 event players — "
      "an imputation model would have to preserve the exposure–event "
      "relationship with extremely sparse outcome information; (ii) exposures "
      "enter as lag-1 and rolling 3-day summaries, so imputation must respect "
      "the longitudinal lag structure (a joint multilevel model of 7 correlated "
      "wellness scales x ~730 days x 50 players, with within-player "
      "standardization), which is computationally and methodologically fragile "
      "in standard MI software; (iii) reporting is demonstrably non-random and "
      "plausibly MNAR, so MAR-based MI offers no clear advantage over the "
      "transparent complete-case + IPW combination while adding substantial "
      "modelling assumptions. Multilevel MI is therefore judged **not "
      "reasonable** as the primary approach for this revision.")
    a("- **MNAR tipping-point sensitivity: not pursued quantitatively.** A "
      "formal delta-adjustment tipping-point analysis would require specifying "
      "a sensitivity parameter for the unobservable contrast between reporters "
      "and non-reporters on 1–5/1–10 ordinal scales, mapped through lag-1 and "
      "3-day averaged exposures into a survival model with 42 events; the "
      "resulting parameter space cannot be credibly bounded from these data. "
      "Instead we (a) report exactly which observed factors predict reporting "
      "(Section 2), and (b) present the IPW sensitivity analysis, and state "
      "the residual MNAR risk as a limitation.")
    a("")
    a("## 4. Required wording")
    a("")
    a("Manuscript and response letter must **not** claim that missing-data bias "
      "was \"eliminated\", \"corrected\", or \"removed\". Approved phrasing: "
      "\"IPW sensitivity analyses assess the robustness of the complete-case "
      "estimates to non-random observation; residual bias due to "
      "missing-not-at-random reporting cannot be excluded.\"")
    a("")
    (WS / "05_REVISION_SAP").mkdir(exist_ok=True)
    (WS / "05_REVISION_SAP" / "missing_data_plan.md").write_text(
        "\n".join(lines), encoding="utf-8")
    log("wrote 05_REVISION_SAP/missing_data_plan.md")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL ERROR:\n" + traceback.format_exc())
        raise
    finally:
        _log_fh.close()
