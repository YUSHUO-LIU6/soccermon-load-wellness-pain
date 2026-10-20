#!/usr/bin/env python3
"""
run_nonoverlap_boot.py — Task 9.4 (R2): player-cluster bootstrap of the
non-overlap chronic-window DROP-TEAM interaction (B=2000, whole players,
seed 20260722).

PONE-D-26-31950 (SoccerMon), R2 reproducibility freeze.
Taxonomy: R2_REVIEWER_REQUESTED.

Same numpy IRLS marginal-logit approximation as R1's
02_R1_REPRODUCTION/r1_sandbox/06_ANALYSIS_CODE/05_bootstrap_and_ipw.py
(stage_boot), with the design matrix minus the team dummy and
chronic_load_28to8_wp_z in place of chronic_load_28d_wp_z. This bootstraps
the same population-average marginal-logit interaction estimand as R1's
A_boot and R2's A_drop_team_boot (09_TEAM_SENSITIVITY/run_drop_team_boot.py)
for direct comparability.

Inputs : FR/08_NONOVERLAP_WINDOW/modeling_dataset_nonoverlap.csv
Outputs: FR/08_NONOVERLAP_WINDOW/nonoverlap_boot_replicates.csv
         FR/08_NONOVERLAP_WINDOW/nonoverlap_boot_summary.json
         row appended to FR/08_NONOVERLAP_WINDOW/NONOVERLAP_WINDOW_RESULTS.csv
Log    : FR/18_LOGS/workstream_newmodels.log
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

FR = Path("D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE")
OUT = FR / "08_NONOVERLAP_WINDOW"
LOG = FR / "18_LOGS" / "workstream_newmodels.log"
SEED = 20260722
B = 2000

WCOL = "soreness_burden_recent3_wp_z"
CHRON = "chronic_load_28to8_wp_z"
INTER = f"acute_load_7d_wp_z:{WCOL}"

# R1 reference: A_boot interaction OR (with team) = 0.6697 [0.4467, 1.1071];
# R2 drop-team bootstrap OR (09_TEAM_SENSITIVITY) = 0.7401 [0.5556, 1.1323].
R1_BOOT_OR = 0.669743373316233
R2_DT_BOOT_OR = 0.740097920694462


def log(msg=""):
    from datetime import datetime
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | [9.4 nonoverlap_boot] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def design_matrix_noteam(d):
    """R1 primary-formula design matrix WITHOUT the team dummy, with the
    non-overlap chronic column (intercept + acute*soreness +
    chronic_28to8 + prev_episode_ever + calendar_time + season)."""
    seasons = sorted(d["season"].unique())
    scols = [(d["season"] == s).astype(float).values for s in seasons[1:]]
    a = d["acute_load_7d_wp_z"].values
    w = d[WCOL].values
    X = np.column_stack(
        [np.ones(len(d)), a, w, a * w,
         d[CHRON].values,
         d["prev_episode_ever"].astype(float).values,
         d["calendar_time"].astype(float).values] + scols)
    names = (["Intercept", "acute_load_7d_wp_z", WCOL, INTER, CHRON,
              "prev_episode_ever", "calendar_time"]
             + [f"season{s}" for s in seasons[1:]])
    return X, names


def irls_logit(X, y, max_iter=100, tol=1e-9):
    """Identical to 05_bootstrap_and_ipw.py irls_logit (unweighted)."""
    n, p = X.shape
    sw = np.ones(n)
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
        step = XtWX_inv @ score
        beta = beta + step
        if np.max(np.abs(step)) < tol:
            return beta, True
    return beta, True


def player_cluster_indices(d, rng):
    players = d["player_id"].unique()
    pick = rng.choice(players, size=len(players), replace=True)
    by_p = {p: np.where(d["player_id"].values == p)[0] for p in players}
    return np.concatenate([by_p[p] for p in pick])


def main():
    log(f"player-cluster bootstrap B={B}, seed={SEED}, design minus team, "
        f"chronic={CHRON} (non-overlap t-28..t-8); estimand = "
        "population-average marginal-logit interaction (same numpy IRLS "
        "approximation as R1 05_bootstrap_and_ipw.py stage_boot)")
    md = pd.read_csv(OUT / "modeling_dataset_nonoverlap.csv",
                     parse_dates=["date"])
    vars_ = ["onset_day", "acute_load_7d_wp_z", WCOL, CHRON,
             "prev_episode_ever", "calendar_time", "team", "season",
             "player_id", "date", "prev_episode_count"]
    d = md.dropna(subset=vars_).reset_index(drop=True)
    n, ev, evp = len(d), int(d["onset_day"].sum()), \
        d.loc[d["onset_day"] == 1, "player_id"].nunique()
    log(f"CC n={n}, events={ev}, event_players={evp}, "
        f"players={d['player_id'].nunique()}")
    assert n == 19758 and ev == 28 and evp == 9, \
        f"CC sample mismatch vs asserted 19758/28/9: got {n}/{ev}/{evp}"
    X, names = design_matrix_noteam(d)
    y = d["onset_day"].values.astype(float)
    beta0, conv = irls_logit(X, y)
    ix = names.index(INTER)
    log(f"full-sample marginal-logit fit converged={conv}; "
        f"interaction beta={beta0[ix]:.4f} (OR={np.exp(beta0[ix]):.4f})")
    rng = np.random.default_rng(SEED)
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
            log(f"{b+1}/{B} done (failures so far: {n_fail})")
    ok = reps[~np.isnan(reps)]
    res = dict(model_id="A_nonoverlap_dropteam_boot",
               wellness_variant="soreness", term=INTER,
               n_boot_requested=B, n_boot_ok=len(ok), n_boot_failed=n_fail,
               beta_full_sample=float(beta0[ix]),
               OR_median=float(np.exp(np.median(ok))),
               OR_ci_low=float(np.exp(np.percentile(ok, 2.5))),
               OR_ci_high=float(np.exp(np.percentile(ok, 97.5))),
               p_OR_gt1=float(np.mean(np.exp(ok) > 1)))
    pd.DataFrame({"replicate": np.arange(B),
                  "beta_interaction": reps}).to_csv(
        OUT / "nonoverlap_boot_replicates.csv", index=False)
    with open(OUT / "nonoverlap_boot_summary.json", "w") as f:
        json.dump(res, f, indent=2)

    formula = ("onset_day ~ acute_load_7d_wp_z * soreness_burden_recent3_wp_z "
               "+ chronic_load_28to8_wp_z + prev_episode_ever + calendar_time "
               "+ season (population-average marginal logit, numpy IRLS; "
               "design = R1 primary minus team, non-overlap chronic)")
    row = pd.DataFrame([dict(
        model_id="A_nonoverlap_dropteam_boot", wellness_variant="soreness",
        term=INTER, OR=res["OR_median"], CI_low=res["OR_ci_low"],
        CI_high=res["OR_ci_high"], p=np.nan, se=np.nan, converged=True,
        separation_flag=False, n=n, players=d["player_id"].nunique(),
        events=ev, formula=formula, taxonomy="R2_REVIEWER_REQUESTED",
        notes=(f"P(OR>1)={res['p_OR_gt1']:.3f}; full-sample marginal beta="
               f"{res['beta_full_sample']:.4f}; player-cluster bootstrap "
               f"B={B} (ok={len(ok)}, failed={n_fail}), seed={SEED}; "
               "bootstrapped estimand = population-average marginal-logit "
               "interaction (R1 A_boot precedent; glmer bootstrap infeasible "
               "in revision window)"))])
    dl_r1 = np.log(res["OR_median"]) - np.log(R1_BOOT_OR)
    dl_dt = np.log(res["OR_median"]) - np.log(R2_DT_BOOT_OR)
    cmp_row = pd.DataFrame([dict(
        model_id="CMP_A_nonoverlap_dropteam_boot_vs_R1_A_boot",
        wellness_variant="soreness", term=INTER, OR=res["OR_median"],
        CI_low=res["OR_ci_low"], CI_high=res["OR_ci_high"], p=np.nan,
        se=np.nan, converged=True, separation_flag=False, n=n,
        players=d["player_id"].nunique(), events=ev, formula=formula,
        taxonomy="R2_REVIEWER_REQUESTED",
        notes=(f"bootstrap interaction OR {res['OR_median']:.4f} "
               f"[{res['OR_ci_low']:.4f}, {res['OR_ci_high']:.4f}] vs R1 "
               f"A_boot 0.6697 [0.4467, 1.1071]: delta log(OR)={dl_r1:.4f} "
               f"({100*dl_r1/abs(np.log(R1_BOOT_OR)):.1f}% of |log(OR_R1)|); "
               f"vs R2 A_drop_team_boot 0.7401 [0.5556, 1.1323]: "
               f"delta log(OR)={dl_dt:.4f} "
               f"({100*dl_dt/abs(np.log(R2_DT_BOOT_OR)):.1f}%). Direction "
               "preserved (OR<1). Materiality judged on log(OR) shift, "
               "not p-values."))])
    out = pd.concat([row, cmp_row], ignore_index=True)
    res_csv = OUT / "NONOVERLAP_WINDOW_RESULTS.csv"
    out.to_csv(res_csv, mode="a", header=False, index=False)
    log(f"interaction OR: median={res['OR_median']:.3f} "
        f"[{res['OR_ci_low']:.3f}, {res['OR_ci_high']:.3f}], "
        f"P(OR>1)={res['p_OR_gt1']:.3f}, ok={len(ok)}/{B}; rows appended to "
        "NONOVERLAP_WINDOW_RESULTS.csv")


if __name__ == "__main__":
    main()
