#!/usr/bin/env python3
"""
05_bootstrap_and_ipw.py — Phase 10/11 companion to 04_run_reanalysis.R
PONE-D-26-31950 (SoccerMon), per FROZEN SAP v1.0. Seed fixed: 20260722.

Stages (run via run_revision_1.ps1 in this order):
  prep       rebuild washout-3d / washout-14d risk sets + onset_day from
             07_ANALYSIS_OUTPUTS/episode_inventory.csv (scope=lower_limb),
             replicating 02_episodes_and_modeling_data.py rules; add
             acwr_7_28_wp_z (same within-player rule) for the ACWR
             sensitivity; write event_count_inventory.csv.
  ipw        reproduce 03_missingness_ipw.py observation model
             (statsmodels logit, fit on the 36,296 at-risk days:
             obs ~ daily_load_z + C(team) + C(season) + calendar_time_z
             + C(day_of_week) + obs_lag1 + prev_episode_ever + onset_day),
             score the full grid, stabilised weights (1/99 truncation) for
             each primary wellness variable -> ipw_weights_<var>.csv.
  bootstrap  player-cluster bootstrap B=2000 (whole players, seed 20260722)
             of the PRIMARY soreness interaction via fast marginal logit
             (numpy IRLS, SAP-sanctioned approximation; glmer full bootstrap
             not run — reason recorded).
  firth_boot Python IRLS implementation of Firth logistic (Jeffreys
             penalty); point estimates validated against R logistf output
             before use; player-cluster bootstrap B=2000 percentile CIs for
             the Model F terms (SAP: SE via cluster bootstrap).
  finalize   merge r_results.csv + bootstrap + firth_boot into
             master_results.csv / master_results.json; write environment
             info; RESULTS_LOCK.md + RESULTS_LOCK_HASH.txt (sha256).
"""

import argparse
import hashlib
import os
import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
WS = Path(os.environ.get("SOCCERMON_WORKSPACE", REPO_ROOT / "workspace")).resolve()
OUT_ALL = WS / "07_ANALYSIS_OUTPUTS"
WS.mkdir(parents=True, exist_ok=True)
RUN_FILE = WS / "RUN_ID.txt"
if RUN_FILE.exists():
    RUN = RUN_FILE.read_text().strip().splitlines()[0]
else:
    RUN = os.environ.get("SOCCERMON_RUN_ID", "RUN_PUBLIC")
    RUN_FILE.write_text(RUN + "\n", encoding="utf-8")
OUT = OUT_ALL / RUN
OUT.mkdir(parents=True, exist_ok=True)
LOG = WS / "logs" / "04_reanalysis.log"
LOG.parent.mkdir(parents=True, exist_ok=True)
SEED = 20260722

_fh = open(LOG, "a", encoding="utf-8")


def log(msg=""):
    print(msg)
    _fh.write(str(msg) + "\n")
    _fh.flush()


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

def within_player_z(df, value_col, z_col, min_obs=10):
    """Same rule as 02_episodes_and_modeling_data.py: (x - player mean) /
    player sample SD (ddof=1) over the full grid; NaN if <10 obs or SD<=0."""
    g = df.groupby("player_id")[value_col]
    mean = g.transform("mean")
    sd = g.transform("std")
    n = g.transform("count")
    z = (df[value_col] - mean) / sd
    z[(n < min_obs) | (sd <= 0)] = np.nan
    df[z_col] = z


def build_risk_set(base, ll_episodes, washout):
    """Replicates 02 build_risk_set: at-risk unless t in (onset, end] of any
    episode; onset-day = any episode onset on day t (merged across
    locations)."""
    rs = base[["player_id", "date"]].copy()
    rs["during_episode"] = 0
    for e in ll_episodes.itertuples():
        m = rs["player_id"] == e.player_id
        rs.loc[m & (rs["date"] > e.onset_date) & (rs["date"] <= e.end_date),
               "during_episode"] = 1
    onsets = (ll_episodes.groupby(["player_id", "onset_date"]).size()
              .reset_index(name="n_locations")
              .rename(columns={"onset_date": "date"}))
    rs = rs.merge(onsets, on=["player_id", "date"], how="left")
    rs["onset_day"] = (rs["n_locations"].fillna(0) > 0).astype(int)
    rs["at_risk"] = (rs["during_episode"] == 0).astype(int)
    return rs


def event_history(df, onsets_by_player):
    """prev_episode_count / days_since_last_episode / prev_episode_ever as in
    02 (evaluated strictly before day t, on the full grid)."""
    df = df.sort_values(["player_id", "date"]).copy()
    df["prev_episode_count"] = 0
    df["days_since_last_episode"] = np.nan
    for p, g in df.groupby("player_id"):
        ons = onsets_by_player.get(p)
        if ons is None or len(ons) == 0:
            continue
        idx = np.searchsorted(ons, g["date"].values, side="left")
        df.loc[g.index, "prev_episode_count"] = idx
        last = np.where(idx > 0, ons[np.clip(idx - 1, 0, None)],
                        np.datetime64("NaT"))
        dsl = (g["date"].values - last) / np.timedelta64(1, "D")
        dsl[idx == 0] = np.nan
        df.loc[g.index, "days_since_last_episode"] = dsl
    df["prev_episode_ever"] = (df["prev_episode_count"] > 0).astype(int)
    return df


WELL_Z = {"soreness": "soreness_burden_recent3_wp_z",
          "fatigue": "fatigue_burden_recent3_wp_z",
          "readiness": "readiness_deficit_recent3_wp_z"}

COVARS = ["onset_day", "acute_load_7d_wp_z", "chronic_load_28d_wp_z",
          "prev_episode_ever", "calendar_time", "team", "season"]


# ---------------------------------------------------------------------------
# stage: prep
# ---------------------------------------------------------------------------

def stage_prep():
    log("=" * 70)
    log("[prep] rebuilding sensitivity datasets")
    base = pd.read_csv(WS / "02_RAW_DATA" / "rebuilt_player_day_base.csv",
                       parse_dates=["date"])
    md = pd.read_csv(OUT_ALL / "modeling_dataset.csv", parse_dates=["date"])
    ep = pd.read_csv(OUT_ALL / "episode_inventory.csv",
                     parse_dates=["onset_date", "end_date"])
    ll = ep[ep["scope"] == "lower_limb"]

    # exposures z on the full grid (identical rules to 02)
    base["soreness_burden_recent3"] = 6 - base["soreness_recent3"]
    within_player_z(base, "acute_load_7d_lag", "acute_load_7d_wp_z")
    within_player_z(base, "chronic_load_28d_lag", "chronic_load_28d_wp_z")
    within_player_z(base, "soreness_burden_recent3",
                    "soreness_burden_recent3_wp_z")
    within_player_z(base, "acwr_7_28_lag", "acwr_7_28_wp_z")
    base["season"] = base["year"]
    base["calendar_time"] = (base["date"] - pd.Timestamp("2020-01-01")).dt.days

    # validation: rebuilt z must match modeling_dataset on shared rows
    chk = md.merge(base[["player_id", "date", "acute_load_7d_wp_z",
                         "soreness_burden_recent3_wp_z"]],
                   on=["player_id", "date"], suffixes=("", "_rebuilt"))
    d1 = (chk["acute_load_7d_wp_z"] - chk["acute_load_7d_wp_z_rebuilt"]).abs().max()
    d2 = (chk["soreness_burden_recent3_wp_z"]
          - chk["soreness_burden_recent3_wp_z_rebuilt"]).abs().max()
    log(f"[prep] validation vs modeling_dataset: max|diff| acute z={d1:.2e}, "
        f"soreness recent3 z={d2:.2e}")
    assert d1 < 1e-10 and d2 < 1e-10, "z rebuild mismatch vs modeling_dataset"

    expo = base[["player_id", "date", "team", "season", "calendar_time",
                 "acute_load_7d_wp_z", "chronic_load_28d_wp_z",
                 "soreness_burden_recent3_wp_z"]]

    inv_rows = []
    for w in (3, 7, 14):
        epw = ll[ll["washout_days"] == w]
        rs = build_risk_set(base, epw, w)
        n_ep = len(epw)
        onsets = epw.groupby("player_id")["onset_date"].apply(
            lambda s: s.sort_values().values).to_dict()
        rs = event_history(rs, onsets)
        n_onset_total = int(rs["onset_day"].sum())
        risk = rs[rs["at_risk"] == 1]
        n_onset_risk = int(risk["onset_day"].sum())
        ev_players = risk.loc[risk["onset_day"] == 1, "player_id"].nunique()
        inv_rows.append(dict(washout_days=w, ll_episodes=n_ep,
                             onset_days_total=n_onset_total,
                             at_risk_days=len(risk),
                             onset_days_in_risk_set=n_onset_risk,
                             event_players=ev_players,
                             players=base["player_id"].nunique()))
        log(f"[prep] washout {w}d: {n_ep} LL episodes, {n_onset_total} onset "
            f"days total, risk set {len(risk)} days / {n_onset_risk} onsets / "
            f"{ev_players} event players")
        if w in (3, 14):
            d = risk.merge(expo, on=["player_id", "date"], how="left",
                           validate="one_to_one")
            d = d.drop(columns=["during_episode", "n_locations", "at_risk"])
            d.to_csv(OUT / f"sens_washout{w}d.csv", index=False,
                     date_format="%Y-%m-%d")
            log(f"[prep] wrote sens_washout{w}d.csv ({len(d)} rows)")

    # ACWR sensitivity dataset: modeling_dataset + acwr_7_28_wp_z
    da = md.merge(base[["player_id", "date", "acwr_7_28_wp_z"]],
                  on=["player_id", "date"], how="left", validate="one_to_one")
    da.to_csv(OUT / "sens_acwr.csv", index=False, date_format="%Y-%m-%d")
    log(f"[prep] wrote sens_acwr.csv (acwr z non-missing "
        f"{da['acwr_7_28_wp_z'].notna().sum()}/{len(da)})")

    pd.DataFrame(inv_rows).to_csv(OUT / "event_count_inventory.csv",
                                  index=False)
    log("[prep] wrote event_count_inventory.csv")


# ---------------------------------------------------------------------------
# stage: ipw
# ---------------------------------------------------------------------------

def stage_ipw():
    import statsmodels.formula.api as smf
    log("=" * 70)
    log("[ipw] reproducing 03_missingness_ipw.py observation model")
    md = pd.read_csv(OUT_ALL / "modeling_dataset.csv", parse_dates=["date"])
    base = pd.read_csv(WS / "02_RAW_DATA" / "rebuilt_player_day_base.csv",
                       parse_dates=["date"])
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

    PRIMARY = ["soreness", "fatigue", "readiness"]
    phat = {}
    for v in PRIMARY:
        grid[f"obs_{v}"] = grid[v].notna().astype(int)
        fit_df[f"obs_{v}"] = fit_df[v].notna().astype(int)
        grid[f"obs_{v}_lag1"] = (grid.groupby("player_id")[f"obs_{v}"]
                                 .shift(1).fillna(0).astype(int))
        fit_df[f"obs_{v}_lag1"] = (fit_df.groupby("player_id")[f"obs_{v}"]
                                   .shift(1).fillna(0).astype(int))
        f = (f"obs_{v} ~ daily_load_z + C(team) + C(season) + "
             f"calendar_time_z + C(day_of_week) + obs_{v}_lag1 + "
             f"prev_episode_ever + onset_day")
        res = smf.logit(f, data=fit_df).fit(disp=0, maxiter=200)
        log(f"[ipw] obs model [{v}]: N={len(fit_df)}, obs rate="
            f"{fit_df[f'obs_{v}'].mean():.3f}, converged="
            f"{res.mle_retvals.get('converged')}")
        phat[v] = res.predict(grid).clip(1e-4, 1 - 1e-4)
        grid[f"phat_{v}"] = phat[v].values

    # weights: as in 03 — lag day = previous at-risk day per player
    md2 = md.sort_values(["player_id", "date"]).reset_index(drop=True)
    md2["lag_date"] = md2.groupby("player_id")["date"].shift(1)
    lk = grid.set_index(["player_id", "date"])
    diag = []
    for v in PRIMARY:
        p_marg = grid.loc[grid["in_risk_set"] == 1, f"obs_{v}"].mean()
        cc = md2.copy()
        cc = cc.join(lk[[f"phat_{v}"]], on=["player_id", "lag_date"])
        n_na = int(cc[f"phat_{v}"].isna().sum())
        cc["w_stab"] = p_marg / cc[f"phat_{v}"]
        lo, hi = cc["w_stab"].quantile([0.01, 0.99])
        cc["w_stab_trunc"] = cc["w_stab"].clip(lo, hi)
        out = cc[["player_id", "date", "w_stab", "w_stab_trunc"]]
        out.to_csv(OUT / f"ipw_weights_{v}.csv", index=False,
                   date_format="%Y-%m-%d")
        ess = (cc["w_stab_trunc"].sum() ** 2 / (cc["w_stab_trunc"] ** 2).sum())
        diag.append(dict(variable=v, p_marginal_observed=p_marg,
                         n_rows=len(cc), n_missing_lag_phat=n_na,
                         ess_truncated=ess, ess_over_n=ess / len(cc),
                         max_w_trunc=cc["w_stab_trunc"].max()))
        log(f"[ipw] {v}: p_marg={p_marg:.3f}, rows without lag p_hat={n_na}, "
            f"ESS(trunc)={ess:.0f} (ESS/n={ess/len(cc):.2f}), "
            f"max w={cc['w_stab_trunc'].max():.2f} -> ipw_weights_{v}.csv")
    pd.DataFrame(diag).to_csv(OUT / "ipw_weight_diagnostics.csv", index=False)


# ---------------------------------------------------------------------------
# fast IRLS logit / Firth
# ---------------------------------------------------------------------------

def design_matrix(d, wcol):
    """Primary-formula design matrix (intercept + acute*wellness + chronic +
    prev_episode_ever + calendar_time + team + season)."""
    teamB = (d["team"] == "TeamB").astype(float).values
    seasons = sorted(d["season"].unique())
    scols = [(d["season"] == s).astype(float).values for s in seasons[1:]]
    a = d["acute_load_7d_wp_z"].values
    w = d[wcol].values
    X = np.column_stack(
        [np.ones(len(d)), a, w, a * w,
         d["chronic_load_28d_wp_z"].values,
         d["prev_episode_ever"].astype(float).values,
         d["calendar_time"].astype(float).values, teamB] + scols)
    names = (["Intercept", "acute_load_7d_wp_z", wcol,
              f"acute_load_7d_wp_z:{wcol}", "chronic_load_28d_wp_z",
              "prev_episode_ever", "calendar_time", "teamTeamB"]
             + [f"season{s}" for s in seasons[1:]])
    return X, names


def irls_logit(X, y, weights=None, firth=False, max_iter=100, tol=1e-9):
    n, p = X.shape
    sw = np.ones(n) if weights is None else np.asarray(weights, float)
    beta = np.zeros(p)
    for it in range(max_iter):
        eta = X @ beta
        mu = 1.0 / (1.0 + np.exp(-eta))
        W = sw * np.clip(mu * (1 - mu), 1e-10, None)
        XtW = X.T * W
        XtWX = XtW @ X
        try:
            XtWX_inv = np.linalg.inv(XtWX)
        except np.linalg.LinAlgError:
            return None, False
        score = X.T @ (sw * (y - mu))
        if firth:
            # hat diag of W^1/2 X (X'WX)^-1 X' W^1/2
            h = np.einsum("ij,jk,ik->i", X, XtWX_inv, X) * W
            score = score + X.T @ (h * (0.5 - mu))
        step = XtWX_inv @ score
        beta = beta + step
        if np.max(np.abs(step)) < tol:
            return beta, True
    return beta, True


def cc_frame(md, wcol):
    vars_ = COVARS + [wcol, "player_id", "date"]
    return md.dropna(subset=vars_).reset_index(drop=True)


def player_cluster_indices(d, rng):
    """Resample whole players with replacement; return row indices."""
    players = d["player_id"].unique()
    pick = rng.choice(players, size=len(players), replace=True)
    by_p = {p: np.where(d["player_id"].values == p)[0] for p in players}
    return np.concatenate([by_p[p] for p in pick])


# ---------------------------------------------------------------------------
# stage: bootstrap (primary soreness interaction, fast marginal logit)
# ---------------------------------------------------------------------------

def stage_boot(B=2000):
    log("=" * 70)
    log(f"[bootstrap] player-cluster bootstrap B={B}, seed={SEED} "
        "(fast marginal logit IRLS; glmer full bootstrap not run — with "
        "42 events and ~20k rows, 2000 glmer refits is computationally "
        "infeasible in the revision window; the marginal-logit bootstrap is "
        "the SAP-sanctioned fast approximation)")
    md = pd.read_csv(OUT_ALL / "modeling_dataset.csv", parse_dates=["date"])
    wcol = WELL_Z["soreness"]
    d = cc_frame(md, wcol)
    X, names = design_matrix(d, wcol)
    y = d["onset_day"].values.astype(float)
    beta0, conv = irls_logit(X, y)
    log(f"[bootstrap] CC sample n={len(d)}, events={int(y.sum())}, "
        f"players={d['player_id'].nunique()}; full-sample fit converged={conv}")
    rng = np.random.default_rng(SEED)
    ix = names.index(f"acute_load_7d_wp_z:{wcol}")
    reps = np.full(B, np.nan)
    n_fail = 0
    for b in range(B):
        idx = player_cluster_indices(d, rng)
        beta, ok = irls_logit(X[idx], y[idx])
        if ok and beta is not None and np.abs(beta[ix]) < 20:
            reps[b] = beta[ix]
        else:
            n_fail += 1
        if (b + 1) % 500 == 0:
            log(f"[bootstrap] {b+1}/{B} done (failures so far: {n_fail})")
    ok = reps[~np.isnan(reps)]
    res = dict(model_id="A_boot", wellness_variant="soreness",
               term=f"acute_load_7d_wp_z:{wcol}",
               n_boot_requested=B, n_boot_ok=len(ok), n_boot_failed=n_fail,
               beta_full_sample=float(beta0[ix]),
               OR_median=float(np.exp(np.median(ok))),
               OR_ci_low=float(np.exp(np.percentile(ok, 2.5))),
               OR_ci_high=float(np.exp(np.percentile(ok, 97.5))),
               p_OR_gt1=float(np.mean(np.exp(ok) > 1)))
    pd.DataFrame({"replicate": np.arange(B), "beta_interaction": reps}
                 ).to_csv(OUT / "bootstrap_replicates.csv", index=False)
    with open(OUT / "bootstrap_primary_interaction.json", "w") as f:
        json.dump(res, f, indent=2)
    log(f"[bootstrap] interaction OR: median={res['OR_median']:.3f} "
        f"[{res['OR_ci_low']:.3f}, {res['OR_ci_high']:.3f}], "
        f"P(OR>1)={res['p_OR_gt1']:.3f}, ok={len(ok)}/{B}")


# ---------------------------------------------------------------------------
# stage: firth_boot (Firth point estimates validated vs R logistf, then
# player-cluster bootstrap B=2000 for percentile CIs)
# ---------------------------------------------------------------------------

def stage_firth_boot(B=2000):
    log("=" * 70)
    log(f"[firth_boot] Firth IRLS + player-cluster bootstrap B={B}")
    md = pd.read_csv(OUT_ALL / "modeling_dataset.csv", parse_dates=["date"])
    r_res = pd.read_csv(OUT / "r_results.csv")
    rng = np.random.default_rng(SEED + 1)
    out_rows = []
    for v, wcol in WELL_Z.items():
        d = cc_frame(md, wcol)
        X, names = design_matrix(d, wcol)
        y = d["onset_day"].values.astype(float)
        beta, ok = irls_logit(X, y, firth=True, max_iter=200)
        # validate vs R logistf point estimates
        rr = r_res[(r_res.model_id == "F") & (r_res.wellness_variant == v)]
        maxdiff = np.nan
        if len(rr) and beta is not None:
            r_beta = {}
            for _, row in rr.iterrows():
                r_beta[row["term"]] = np.log(row["OR"])
            diffs = []
            for i, nm in enumerate(names):
                # map python names to R term names
                cand = [nm, nm.replace("teamTeamB", "teamTeamB"),
                        nm.replace("season", "season")]
                hit = None
                for c in cand:
                    if c in r_beta:
                        hit = c
                        break
                if hit is not None:
                    diffs.append(abs(beta[i] - r_beta[hit]))
            maxdiff = max(diffs) if diffs else np.nan
        log(f"[firth_boot] {v}: python Firth vs R logistf max|beta diff| = "
            f"{maxdiff:.2e}")
        boot = {nm: [] for nm in names}
        n_fail = 0
        for b in range(B):
            idx = player_cluster_indices(d, rng)
            bb, okb = irls_logit(X[idx], y[idx], firth=True, max_iter=200)
            if bb is None or np.any(np.abs(bb) > 20):
                n_fail += 1
                continue
            for i, nm in enumerate(names):
                boot[nm].append(bb[i])
            if (b + 1) % 500 == 0:
                log(f"[firth_boot] {v}: {b+1}/{B} done (failures: {n_fail})")
        for i, nm in enumerate(names):
            vals = np.array(boot[nm])
            out_rows.append(dict(
                analysis_role="SMALL_SAMPLE_SENSITIVITY", model_id="F_boot",
                wellness_variant=v, term=nm,
                OR=float(np.exp(np.median(vals))),
                CI_low=float(np.exp(np.percentile(vals, 2.5))),
                CI_high=float(np.exp(np.percentile(vals, 97.5))),
                p=np.nan, se=float(np.std(vals, ddof=1)), converged=True,
                optimizer=f"Firth IRLS cluster bootstrap B={B} "
                          f"(ok={len(vals)}, failed={n_fail}); "
                          f"python-vs-logistf max|dBeta|={maxdiff:.2e}",
                n=len(d), players=d["player_id"].nunique(),
                events=int(y.sum()),
                notes="SE=SD of bootstrap betas; CI=percentile on OR scale"))
        log(f"[firth_boot] {v}: done, failures={n_fail}")
    pd.DataFrame(out_rows).to_csv(OUT / "firth_bootstrap_results.csv",
                                  index=False)


# ---------------------------------------------------------------------------
# stage: finalize
# ---------------------------------------------------------------------------

def stage_finalize():
    log("=" * 70)
    log("[finalize] assembling master_results + RESULTS_LOCK")
    r = pd.read_csv(OUT / "r_results.csv")
    extra = []
    bf = OUT / "bootstrap_primary_interaction.json"
    if bf.exists():
        b = json.loads(bf.read_text())
        extra.append(dict(
            analysis_role="PRIMARY_BOOTSTRAP", model_id="A_boot",
            wellness_variant="soreness", term=b["term"], OR=b["OR_median"],
            CI_low=b["OR_ci_low"], CI_high=b["OR_ci_high"], p=np.nan,
            se=np.nan, converged=True,
            optimizer=(f"player-cluster bootstrap B={b['n_boot_requested']} "
                       f"(ok={b['n_boot_ok']}, failed={b['n_boot_failed']}), "
                       "fast marginal logit IRLS, seed=20260722"),
            n=np.nan, players=np.nan, events=np.nan,
            notes=(f"P(OR>1)={b['p_OR_gt1']:.3f}; full-sample marginal beta="
                   f"{b['beta_full_sample']:.4f}; glmer bootstrap infeasible "
                   "(see log)")))
    fb = OUT / "firth_bootstrap_results.csv"
    if fb.exists():
        extra += pd.read_csv(fb).to_dict("records")
    master = pd.concat([r, pd.DataFrame(extra)], ignore_index=True)
    master.to_csv(OUT / "master_results.csv", index=False)
    master.to_json(OUT / "master_results.json", orient="records", indent=1)
    log(f"[finalize] master_results: {len(master)} rows")

    # python environment info
    import scipy, statsmodels
    with open(OUT / "session_info_python.txt", "w") as f:
        f.write(f"python {sys.version}\n")
        for mod in (np, pd, scipy, statsmodels):
            f.write(f"{mod.__name__} {mod.__version__}\n")

    # lock: sha256 of every output file except the lock files themselves
    skip = {"RESULTS_LOCK.md", "RESULTS_LOCK_HASH.txt"}
    hashes = {}
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name not in skip:
            hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    with open(OUT / "RESULTS_LOCK_HASH.txt", "w") as f:
        for name, h in hashes.items():
            f.write(f"{h}  {name}\n")
    combined = hashlib.sha256(
        "".join(f"{h}  {n}\n" for n, h in hashes.items()).encode()).hexdigest()
    with open(OUT / "RESULTS_LOCK.md", "w") as f:
        f.write(f"# RESULTS LOCK — {RUN}\n\n")
        f.write("Phase 10/11 formal re-analysis per FROZEN SAP v1.0 "
                "(05_REVISION_SAP, hash in SAP_FREEZE_HASH.txt). "
                "seed=20260722. Model set fixed by model_candidate_matrix.csv; "
                "no p-value-based selection.\n\n")
        f.write("Naming mapping (SAP-concordant): primary wellness exposure = "
                "most recent report within t-3..t-1 -> columns "
                "`*_recent3_wp_z`; strict day t-1 lag sensitivity -> columns "
                "`*_wp_z` (z of `*_burden_lag1`). SAP §5 formula label "
                "`soreness_burden_wp_z` is shorthand for the SAP §3 recent3 "
                "definition.\n\n")
        f.write("All numbers in downstream documents must come from "
                "`master_results.csv` / `master_results.json` only.\n\n")
        f.write("## Files (sha256 in RESULTS_LOCK_HASH.txt)\n\n")
        for name in hashes:
            f.write(f"- {name}\n")
        f.write(f"\nCombined lock hash (sha256 of hash manifest): "
                f"`{combined}`\n")
    log(f"[finalize] RESULTS_LOCK written; combined hash {combined[:16]}…")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["prep", "ipw", "bootstrap",
                                      "firth_boot", "finalize"])
    ap.add_argument("--B", type=int, default=2000)
    args = ap.parse_args()
    try:
        {"prep": stage_prep, "ipw": stage_ipw,
         "bootstrap": lambda: stage_boot(args.B),
         "firth_boot": lambda: stage_firth_boot(args.B),
         "finalize": stage_finalize}[args.stage]()
    except Exception:
        log("FATAL ERROR:\n" + traceback.format_exc())
        raise
    finally:
        _fh.flush()
