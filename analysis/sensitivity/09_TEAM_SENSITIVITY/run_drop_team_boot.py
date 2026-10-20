#!/usr/bin/env python3
"""
run_drop_team_boot.py — Task 9.5 (R2): player-cluster bootstrap of the
A_drop_team interaction (B=2000, whole players, seed 20260722).

PONE-D-26-31950 (SoccerMon), R2 reproducibility freeze.
Taxonomy: R2_REVIEWER_REQUESTED (Reviewer 4 #7).

Same numpy IRLS marginal-logit approximation as R1's
02_R1_REPRODUCTION/r1_sandbox/06_ANALYSIS_CODE/05_bootstrap_and_ipw.py
(stage_boot), with the design matrix minus the team dummy. This bootstraps
the SAME population-average marginal-logit estimand as R1's A_boot for
direct comparability; whether the full glmer is estimable without team is
assessed in run_drop_team.R and recorded in the notes.

Inputs : FR/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/modeling_dataset.csv
Outputs: FR/09_TEAM_SENSITIVITY/drop_team_boot_row.csv
         FR/09_TEAM_SENSITIVITY/drop_team_boot_replicates.csv
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

FR = Path("D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE")
SAN = FR / "02_R1_REPRODUCTION" / "r1_sandbox"
OUT = FR / "09_TEAM_SENSITIVITY"
LOG = FR / "18_LOGS" / "workstream_team_season.log"
SEED = 20260722
B = 2000

WCOL = "soreness_burden_recent3_wp_z"
INTER = f"acute_load_7d_wp_z:{WCOL}"


def log(msg=""):
    from datetime import datetime
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | [9.5 drop_team_boot] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def design_matrix_noteam(d):
    """R1 primary-formula design matrix WITHOUT the team dummy
    (intercept + acute*soreness + chronic + prev_episode_ever +
    calendar_time + season)."""
    seasons = sorted(d["season"].unique())
    scols = [(d["season"] == s).astype(float).values for s in seasons[1:]]
    a = d["acute_load_7d_wp_z"].values
    w = d[WCOL].values
    X = np.column_stack(
        [np.ones(len(d)), a, w, a * w,
         d["chronic_load_28d_wp_z"].values,
         d["prev_episode_ever"].astype(float).values,
         d["calendar_time"].astype(float).values] + scols)
    names = (["Intercept", "acute_load_7d_wp_z", WCOL, INTER,
              "chronic_load_28d_wp_z", "prev_episode_ever", "calendar_time"]
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
    log(f"player-cluster bootstrap B={B}, seed={SEED}, design minus team; "
        "estimand = population-average marginal-logit interaction "
        "(same numpy IRLS approximation as R1 05_bootstrap_and_ipw.py "
        "stage_boot, for direct comparability with A_boot)")
    md = pd.read_csv(SAN / "07_ANALYSIS_OUTPUTS" / "modeling_dataset.csv",
                     parse_dates=["date"])
    vars_ = ["onset_day", "acute_load_7d_wp_z", WCOL, "chronic_load_28d_wp_z",
             "prev_episode_ever", "calendar_time", "team", "season",
             "player_id", "date", "prev_episode_count"]
    d = md.dropna(subset=vars_).reset_index(drop=True)
    assert len(d) == 19758 and d["onset_day"].sum() == 28 and \
        d["player_id"].nunique() == 49, "CC sample mismatch vs R1"
    X, names = design_matrix_noteam(d)
    y = d["onset_day"].values.astype(float)
    beta0, conv = irls_logit(X, y)
    ix = names.index(INTER)
    log(f"CC n={len(d)}, events={int(y.sum())}, players={d['player_id'].nunique()}; "
        f"full-sample marginal-logit fit converged={conv}; "
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
    res = dict(model_id="A_drop_team_boot", wellness_variant="soreness",
               term=INTER, n_boot_requested=B, n_boot_ok=len(ok),
               n_boot_failed=n_fail,
               beta_full_sample=float(beta0[ix]),
               OR_median=float(np.exp(np.median(ok))),
               OR_ci_low=float(np.exp(np.percentile(ok, 2.5))),
               OR_ci_high=float(np.exp(np.percentile(ok, 97.5))),
               p_OR_gt1=float(np.mean(np.exp(ok) > 1)))
    pd.DataFrame({"replicate": np.arange(B),
                  "beta_interaction": reps}).to_csv(
        OUT / "drop_team_boot_replicates.csv", index=False)
    row = pd.DataFrame([dict(
        model_id="A_drop_team_boot", wellness_variant="soreness", term=INTER,
        OR=res["OR_median"], CI_low=res["OR_ci_low"], CI_high=res["OR_ci_high"],
        p=np.nan, se=np.nan, converged=True, separation_flag=False,
        n=len(d), players=d["player_id"].nunique(), events=int(y.sum()),
        taxonomy="R2_REVIEWER_REQUESTED",
        optimizer=(f"player-cluster bootstrap B={B} (ok={len(ok)}, "
                   f"failed={n_fail}), fast marginal logit IRLS minus team, "
                   f"seed={SEED}"),
        notes=(f"P(OR>1)={res['p_OR_gt1']:.3f}; full-sample marginal beta="
               f"{res['beta_full_sample']:.4f}; design = R1 primary minus team; "
               "bootstrapped estimand = population-average marginal-logit "
               "interaction (R1 A_boot precedent; glmer bootstrap infeasible "
               "in revision window)"))])
    row.to_csv(OUT / "drop_team_boot_row.csv", index=False)
    with open(OUT / "drop_team_boot_summary.json", "w") as f:
        json.dump(res, f, indent=2)
    log(f"interaction OR: median={res['OR_median']:.3f} "
        f"[{res['OR_ci_low']:.3f}, {res['OR_ci_high']:.3f}], "
        f"P(OR>1)={res['p_OR_gt1']:.3f}, ok={len(ok)}/{B}")


if __name__ == "__main__":
    main()
