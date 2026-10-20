# -*- coding: utf-8 -*-
"""
run_backward_standardization.py
================================
R2 reproducibility freeze (SoccerMon) - exposure-engineering workstream.
Reviewer 4 #6 (taxonomy R2_REVIEWER_REQUESTED): backward-looking
(expanding-history) within-player standardization, plus the R2_INTERNAL_QA_ONLY
rolling-90-day variant (window fixed a priori).

For the value at calendar day t, the baseline mean/SD use ONLY qualifying
observations strictly BEFORE day t of the same player (full player-day grid,
not only at-risk days); day t itself is never included. Requires >= 10 prior
non-missing baseline observations and sample SD (ddof=1) > 0, else NaN.
Variant _r90 restricts the baseline to days t-90..t-1.

Inputs (read-only):
  02_R1_REPRODUCTION/r1_sandbox/02_RAW_DATA/rebuilt_player_day_base.csv
  02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/modeling_dataset.csv

Outputs:
  11_BACKWARD_STANDARDIZATION/modeling_dataset_backwardz.csv
  11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_COVERAGE.csv
  11_BACKWARD_STANDARDIZATION/BACKWARD_Z_QA.txt

Conventions mirrored from r1_sandbox/06_ANALYSIS_CODE/02_episodes_and_modeling_data.py:
  soreness_burden = 6 - soreness; fatigue_burden = 6 - fatigue;
  readiness_deficit = 11 - readiness; sample SD ddof=1; >=10 obs rule.

Deterministic: no RNG in any output; spot checks use a fixed seed.
"""
import numpy as np
import pandas as pd
from pathlib import Path

FR = Path(r"D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE")
SANDBOX = FR / "02_R1_REPRODUCTION" / "r1_sandbox"
BASE_FILE = SANDBOX / "02_RAW_DATA" / "rebuilt_player_day_base.csv"
MODEL_FILE = SANDBOX / "07_ANALYSIS_OUTPUTS" / "modeling_dataset.csv"
OUT_DIR = FR / "11_BACKWARD_STANDARDIZATION"
LOG_FILE = FR / "18_LOGS" / "workstream_exposures.log"

MIN_OBS = 10
R90_WINDOW = 90          # baseline days t-90..t-1 (fixed a priori, QA-only variant)
SPOT_N = 400             # brute-force spot checks per series per variant
SPOT_SEED = 20260902     # fixed seed for the QA sampler only

# (full-grid series name, new hist column, existing full-period z column)
SERIES = [
    ("acute_load_7d_lag",            "acute_load_7d_wp_z_hist",            "acute_load_7d_wp_z"),
    ("chronic_load_28d_lag",         "chronic_load_28d_wp_z_hist",         "chronic_load_28d_wp_z"),
    ("soreness_burden_recent3",      "soreness_burden_recent3_wp_z_hist",  "soreness_burden_recent3_wp_z"),
    ("fatigue_burden_recent3",       "fatigue_burden_recent3_wp_z_hist",   "fatigue_burden_recent3_wp_z"),
    ("readiness_deficit_recent3",    "readiness_deficit_recent3_wp_z_hist","readiness_deficit_recent3_wp_z"),
]

QA = []  # (check, status, detail)


def qa(check, status, detail=""):
    QA.append((check, status, detail))
    print(f"[{status}] {check} {detail}")


def expanding_hist_z(values, window=None, min_obs=MIN_OBS):
    """Backward-looking within-player z for one player's date-ordered series.

    z_t = (x_t - mean(baseline)) / sd(baseline), baseline = non-missing x on
    days strictly before t (last `window` days if window given). NaN when x_t
    is missing, < min_obs baseline observations, or sample SD (ddof=1) <= 0.
    Deliberately plain loop code: the baseline slice is x[lo:i], which can
    never contain day t or any later day.
    """
    x = np.asarray(values, dtype=float)
    n = len(x)
    out = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(x[i]):
            continue
        lo = 0 if window is None else max(0, i - window)
        base = x[lo:i]
        base = base[~np.isnan(base)]
        if base.size < min_obs:
            continue
        sd = base.std(ddof=1)
        if not (sd > 0):
            continue
        out[i] = (x[i] - base.mean()) / sd
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    base = pd.read_csv(BASE_FILE, parse_dates=["date"], low_memory=False)
    model = pd.read_csv(MODEL_FILE, parse_dates=["date"], low_memory=False)
    assert len(base) == 36550 and base["player_id"].nunique() == 50
    assert not base.duplicated(["player_id", "date"]).any()
    assert len(model) == 36296
    assert not model.duplicated(["player_id", "date"]).any()
    base = base.sort_values(["player_id", "date"]).reset_index(drop=True)

    # Full-grid burden/deficit series (mirror 02_episodes_and_modeling_data.py)
    base["soreness_burden_recent3"] = 6 - base["soreness_recent3"]
    base["fatigue_burden_recent3"] = 6 - base["fatigue_recent3"]
    base["readiness_deficit_recent3"] = 11 - base["readiness_recent3"]

    # QA: full-grid burden series identical to modeling-dataset columns
    chk = model.merge(base[["player_id", "date", "soreness_burden_recent3",
                            "fatigue_burden_recent3", "readiness_deficit_recent3"]],
                      on=["player_id", "date"], how="left", suffixes=("", "_grid"))
    for c in ["soreness_burden_recent3", "fatigue_burden_recent3",
              "readiness_deficit_recent3"]:
        ok = np.allclose(chk[c].to_numpy(dtype=float),
                         chk[f"{c}_grid"].to_numpy(dtype=float), equal_nan=True)
        qa(f"burden series {c}: full-grid recompute == modeling_dataset column",
           "PASS" if ok else "FAIL")

    # ---------------------------------------------------------------- B + C
    g = base.groupby("player_id", sort=False)
    new_cols = {}
    sd_zero_notes = []
    for series, hist_col, _ in SERIES:
        for variant, window in [("hist", None), ("r90", R90_WINDOW)]:
            col = hist_col if variant == "hist" else hist_col.replace("_hist", "_r90")
            vals = g[series].transform(lambda s: expanding_hist_z(s.to_numpy(), window))
            new_cols[col] = vals
            # players whose every computed baseline had SD<=0 or who lost z entirely
        # anomaly scan: player-days where >=10 prior obs but z is NaN -> SD<=0
        tmp = base[["player_id", "date"]].copy()
        tmp["x"] = base[series]
        tmp["z"] = new_cols[hist_col]
        for pid, gp in tmp.groupby("player_id", sort=False):
            x = gp["x"].to_numpy(dtype=float)
            prior_counts = np.array([np.sum(~np.isnan(x[:i])) for i in range(len(x))])
            suspect = gp[(prior_counts >= MIN_OBS) & gp["z"].isna() & gp["x"].notna()]
            if len(suspect):
                sd_zero_notes.append(
                    f"{series}: player {pid} has {len(suspect)} day(s) with "
                    f">={MIN_OBS} prior obs but NaN z (baseline SD<=0), "
                    f"first at {suspect['date'].iloc[0].date()}")
    zdf = pd.DataFrame(new_cols)
    zdf[["player_id", "date"]] = base[["player_id", "date"]]

    # ---------------------------------------------------------------- D: QA
    # Brute-force leakage/correctness spot checks (fixed seed; QA only)
    rng = np.random.default_rng(SPOT_SEED)
    for series, hist_col, _ in SERIES:
        for variant, window in [("hist", None), ("r90", R90_WINDOW)]:
            col = hist_col if variant == "hist" else hist_col.replace("_hist", "_r90")
            idx = rng.choice(len(base), size=SPOT_N, replace=False)
            worst = 0.0
            n_checked = 0
            for i in idx:
                row = base.iloc[i]
                sub = base[(base["player_id"] == row["player_id"])
                           & (base["date"] < row["date"])]
                if window is not None:
                    sub = sub[sub["date"] >= row["date"] - pd.Timedelta(days=window)]
                bvals = sub[series].dropna().to_numpy(dtype=float)
                xt = row[series]
                if np.isnan(xt) or bvals.size < MIN_OBS:
                    expect = np.nan
                else:
                    sd = bvals.std(ddof=1)
                    expect = (xt - bvals.mean()) / sd if sd > 0 else np.nan
                got = zdf[col].iloc[i]
                if np.isnan(expect) and np.isnan(got):
                    continue
                if np.isnan(expect) != np.isnan(got):
                    qa(f"brute-force {col}", "FAIL",
                       f"NaN mismatch at {row['player_id']} {row['date'].date()}: "
                       f"expected {expect}, got {got}")
                    worst = None
                    break
                worst = max(worst, abs(expect - got))
                n_checked += 1
            else:
                ok = worst is not None and worst < 1e-9
                qa(f"brute-force spot check {col} (n={SPOT_N}, leakage-free "
                   f"baseline < t{', last 90d' if window else ''})",
                   "PASS" if ok else "FAIL",
                   f"max|diff|={worst:.2e} on {n_checked} non-NaN pairs" if ok else "")

    # Determinism: recompute one column, require bit-identical result
    recompute = g["acute_load_7d_lag"].transform(
        lambda s: expanding_hist_z(s.to_numpy(), None))
    det = np.array_equal(recompute.to_numpy(dtype=float),
                         zdf["acute_load_7d_wp_z_hist"].to_numpy(dtype=float),
                         equal_nan=True)
    qa("determinism: acute_load_7d_wp_z_hist recomputed bit-identical",
       "PASS" if det else "FAIL")

    # min-obs / SD>0 enforcement on the full grid (NaN pattern audit)
    for series, hist_col, _ in SERIES:
        z = zdf[hist_col].to_numpy(dtype=float)
        x = base[series].to_numpy(dtype=float)
        # count prior non-missing per row (vectorised per player)
        counts = np.zeros(len(base), dtype=int)
        pos = 0
        for pid, gp in base.groupby("player_id", sort=False):
            xv = gp[series].to_numpy(dtype=float)
            pc = np.concatenate([[0], np.cumsum(~np.isnan(xv))])[:-1]
            counts[pos:pos + len(gp)] = pc
            pos += len(gp)
        must_be_nan = (counts < MIN_OBS) | np.isnan(x)
        ok = bool(np.all(np.isnan(z[must_be_nan])))
        qa(f"min-obs rule enforced for {hist_col} (all rows with <{MIN_OBS} "
           f"prior obs or missing x_t are NaN)", "PASS" if ok else "FAIL")

    # ---------------------------------------------------------------- merge
    # Original 41 columns are carried through byte-identically (read as str and
    # rewritten verbatim); only the 10 new columns are serialized as floats.
    model_str = pd.read_csv(MODEL_FILE, dtype=str)
    out = model.merge(zdf, on=["player_id", "date"], how="left", validate="one_to_one")
    assert len(out) == len(model)
    # left-merge preserves model row order; verify key alignment before concat
    assert (out["player_id"].to_numpy() == model_str["player_id"].to_numpy()).all()
    assert (out["date"].dt.strftime("%Y-%m-%d").to_numpy()
            == model_str["date"].to_numpy()).all()
    out_csv = pd.concat([model_str, out[list(new_cols)].reset_index(drop=True)], axis=1)
    out_path = OUT_DIR / "modeling_dataset_backwardz.csv"
    out_csv.to_csv(out_path, index=False)
    print(f"wrote {out_path} ({out_csv.shape[0]} rows x {out_csv.shape[1]} cols, "
          f"+{len(new_cols)} new columns)")

    # ---------------------------------------------------------------- coverage
    rows = []
    risk = out  # modeling dataset = primary risk set
    n_events_total = int(risk["onset_day"].sum())

    def ev_stats(mask):
        sub = risk[mask]
        return (int(sub["onset_day"].sum()),
                int(sub.loc[sub["onset_day"] == 1, "player_id"].nunique()))

    for series, hist_col, full_col in SERIES:
        for variant, col in [("hist", hist_col),
                             ("r90", hist_col.replace("_hist", "_r90"))]:
            before = risk[full_col].notna()
            after = risk[col].notna()
            eb, pb = ev_stats(before)
            ea, pa = ev_stats(after)
            both = before & after
            r = np.corrcoef(risk.loc[both, full_col], risk.loc[both, col])[0, 1]
            rows.append({
                "section": "risk_set", "variable": series, "variant": variant,
                "sample": "risk_set",
                "n_before_fullperiod_z": int(before.sum()),
                "n_after_backward_z": int(after.sum()),
                "pct_lost": round(100 * (int(before.sum()) - int(after.sum()))
                                  / int(before.sum()), 4),
                "events_before": eb, "events_after": ea,
                "event_players_before": pb, "event_players_after": pa,
                "pearson_corr_fullperiod_vs_backward": round(float(r), 6),
                "n_corr": int(both.sum()),
            })

    # soreness complete-case sample: full-period z vs backward-z CC definition
    cc_full_cols = ["acute_load_7d_wp_z", "chronic_load_28d_wp_z",
                    "soreness_burden_recent3_wp_z", "prev_episode_ever",
                    "calendar_time", "team", "season"]
    cc_base = risk[cc_full_cols].notna().all(axis=1)
    n_cc_full = int(cc_base.sum())
    e_cc_full, p_cc_full = ev_stats(cc_base)
    for variant, suffix in [("hist", "_hist"), ("r90", "_r90")]:
        cc_cols = ["acute_load_7d_wp_z" + suffix, "chronic_load_28d_wp_z" + suffix,
                   "soreness_burden_recent3_wp_z" + suffix, "prev_episode_ever",
                   "calendar_time", "team", "season"]
        m = risk[cc_cols].notna().all(axis=1)
        e, p = ev_stats(m)
        rows.append({
            "section": "soreness_cc", "variable": "soreness_complete_case",
            "variant": variant, "sample": "soreness_cc",
            "n_before_fullperiod_z": n_cc_full,
            "n_after_backward_z": int(m.sum()),
            "pct_lost": round(100 * (n_cc_full - int(m.sum())) / n_cc_full, 4),
            "events_before": e_cc_full, "events_after": e,
            "event_players_before": p_cc_full, "event_players_after": p,
            "pearson_corr_fullperiod_vs_backward": "", "n_corr": "",
        })
    cov = pd.DataFrame(rows)
    cov_path = OUT_DIR / "BACKWARD_STANDARDIZATION_COVERAGE.csv"
    cov.to_csv(cov_path, index=False)
    print(f"wrote {cov_path} ({len(cov)} rows)")

    # ---------------------------------------------------------------- QA file
    qa_path = OUT_DIR / "BACKWARD_Z_QA.txt"
    with open(qa_path, "w", encoding="utf-8") as f:
        f.write("BACKWARD_STANDARDIZATION QA - R2 freeze, exposure workstream\n")
        f.write("script: 11_BACKWARD_STANDARDIZATION/run_backward_standardization.py\n")
        f.write(f"risk-set rows={len(risk)}, total events={n_events_total}, "
                f"soreness CC (full-period z) N={n_cc_full}\n\n")
        for check, status, detail in QA:
            f.write(f"[{status}] {check} {detail}\n")
        f.write("\nAnomalies (baseline SD<=0 / players losing all z):\n")
        if sd_zero_notes:
            for s in sd_zero_notes:
                f.write(f"- {s}\n")
        else:
            f.write("- none\n")
    n_fail = sum(1 for _, s, _ in QA if s == "FAIL")
    print(f"wrote {qa_path} ({len(QA)} checks, {n_fail} FAIL)")
    if sd_zero_notes:
        print("ANOMALIES:")
        for s in sd_zero_notes:
            print(" -", s)

    # ---------------------------------------------------------------- log
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("[workstream exposures: backward standardization (R4#6) + r90 QA variant] run complete\n")
        f.write(f"input: {MODEL_FILE} (n={len(model)}), base grid (n={len(base)})\n")
        f.write(f"outputs: {out_path} (+10 cols); {cov_path}; {qa_path}\n")
        f.write(f"soreness CC: full-period z N={n_cc_full} (events={e_cc_full}, event players={p_cc_full}); "
                f"hist N={cov.iloc[-2]['n_after_backward_z']} (events={cov.iloc[-2]['events_after']}, "
                f"event players={cov.iloc[-2]['event_players_after']}); "
                f"r90 N={cov.iloc[-1]['n_after_backward_z']} (events={cov.iloc[-1]['events_after']}, "
                f"event players={cov.iloc[-1]['event_players_after']})\n")
        corrs = {r["variable"]: r["pearson_corr_fullperiod_vs_backward"]
                 for _, r in cov[(cov.section == "risk_set") & (cov.variant == "hist")].iterrows()}
        f.write(f"full-period vs hist z Pearson (risk set): "
                + "; ".join(f"{k}={v}" for k, v in corrs.items()) + "\n")
        f.write(f"QA checks: {len(QA)} run, {n_fail} FAIL; "
                f"SD<=0 anomaly groups: {len(sd_zero_notes)}\n\n")
    print(f"appended {LOG_FILE}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
