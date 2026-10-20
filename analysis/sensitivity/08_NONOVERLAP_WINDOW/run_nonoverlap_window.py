# -*- coding: utf-8 -*-
"""
run_nonoverlap_window.py
=========================
R2 reproducibility freeze (SoccerMon) - exposure-engineering workstream.
Reviewer 4 #5 (taxonomy R2_REVIEWER_REQUESTED): non-overlapping chronic window.

chronic_load_28to8_lag = per-player daily_load.shift(8).rolling(21, min_periods=21).mean()
  -> mean of daily_load over t-28..t-1 minus the acute week, i.e. t-28..t-8
     inclusive (21 days); strictly backward-looking, zero overlap with the
     acute window t-7..t-1.
chronic_load_28to8_wp_z = within-player z using the SAME full-period rule as R1
  (mean/SD over the full 36,550-row grid per player, ddof=1, NaN if <10
  non-missing obs or SD<=0) - isolates the window-overlap change only.

Inputs (read-only):
  02_R1_REPRODUCTION/r1_sandbox/02_RAW_DATA/rebuilt_player_day_base.csv
  02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/modeling_dataset.csv

Outputs:
  08_NONOVERLAP_WINDOW/modeling_dataset_nonoverlap.csv
  08_NONOVERLAP_WINDOW/NONOVERLAP_CORRELATION.csv
  08_NONOVERLAP_WINDOW/NONOVERLAP_QA.txt

Deterministic: no RNG in any output; spot checks use a fixed seed.
"""
import numpy as np
import pandas as pd
from pathlib import Path

FR = Path(r"D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE")
SANDBOX = FR / "02_R1_REPRODUCTION" / "r1_sandbox"
BASE_FILE = SANDBOX / "02_RAW_DATA" / "rebuilt_player_day_base.csv"
MODEL_FILE = SANDBOX / "07_ANALYSIS_OUTPUTS" / "modeling_dataset.csv"
OUT_DIR = FR / "08_NONOVERLAP_WINDOW"
LOG_FILE = FR / "18_LOGS" / "workstream_exposures.log"

MIN_OBS = 10
SPOT_N = 400
SPOT_SEED = 20260902

QA = []


def qa(check, status, detail=""):
    QA.append((check, status, detail))
    print(f"[{status}] {check} {detail}")


def within_player_z(df, value_col, z_col, min_obs=MIN_OBS):
    """R1 convention (02_episodes_and_modeling_data.py): (x - player mean) /
    player SD over the FULL grid; NaN if < min_obs non-missing or SD<=0 (ddof=1)."""
    gp = df.groupby("player_id")[value_col]
    mean = gp.transform("mean")
    sd = gp.transform("std")
    n = gp.transform("count")
    z = (df[value_col] - mean) / sd
    z[(n < min_obs) | (sd <= 0)] = np.nan
    df[z_col] = z


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    base = pd.read_csv(BASE_FILE, parse_dates=["date"], low_memory=False)
    model = pd.read_csv(MODEL_FILE, parse_dates=["date"], low_memory=False)
    assert len(base) == 36550 and base["player_id"].nunique() == 50
    assert len(model) == 36296
    base = base.sort_values(["player_id", "date"]).reset_index(drop=True)

    # ------------------------------------------------ A: non-overlapping window
    g = base.groupby("player_id", sort=False)
    base["chronic_load_28to8_lag"] = g["daily_load"].transform(
        lambda s: s.shift(8).rolling(21, min_periods=21).mean())
    within_player_z(base, "chronic_load_28to8_lag", "chronic_load_28to8_wp_z")

    # Window arithmetic verification (brute force, fixed-seed sample)
    rng = np.random.default_rng(SPOT_SEED)
    worst = 0.0
    n_checked = 0
    idx = rng.choice(len(base), size=SPOT_N, replace=False)
    nan_mismatch = 0
    for i in idx:
        row = base.iloc[i]
        hist = base[(base["player_id"] == row["player_id"])
                    & (base["date"] >= row["date"] - pd.Timedelta(days=28))
                    & (base["date"] <= row["date"] - pd.Timedelta(days=8))]
        loads = hist["daily_load"].to_numpy(dtype=float)
        expect = loads.mean() if len(loads) == 21 else np.nan
        got = base["chronic_load_28to8_lag"].iloc[i]
        if np.isnan(expect) or np.isnan(got):
            if not (np.isnan(expect) and np.isnan(got)):
                nan_mismatch += 1
            continue
        worst = max(worst, abs(expect - got))
        n_checked += 1
    ok = nan_mismatch == 0 and worst < 1e-9
    qa("chronic_load_28to8_lag == mean(daily_load[t-28..t-8]) (brute force, "
       f"n={SPOT_N})", "PASS" if ok else "FAIL",
       f"max|diff|={worst:.2e} on {n_checked} pairs, NaN mismatches={nan_mismatch}")

    # Disjointness vs acute window t-7..t-1: chronic covers t-28..t-8, and
    # t-8 < t-7, so index sets are disjoint for every t by construction.
    chronic_idx = set(range(-28, -7))   # t-28 .. t-8
    acute_idx = set(range(-7, 0))       # t-7  .. t-1
    qa("window disjointness: {t-28..t-8} vs {t-7..t-1} share no index",
       "PASS" if chronic_idx.isdisjoint(acute_idx) else "FAIL")

    # Missingness pattern must equal chronic_load_28d_lag (both need 28 prior days)
    same_miss = bool((base["chronic_load_28to8_lag"].isna()
                      == base["chronic_load_28d_lag"].isna()).all())
    qa("missingness pattern identical to chronic_load_28d_lag (both require "
       "28 prior days)", "PASS" if same_miss else "FAIL")

    # ------------------------------------------------ merge onto modeling dataset
    # Original 41 columns are carried through byte-identically (read as str and
    # rewritten verbatim); only the two new columns are serialized as floats.
    model_str = pd.read_csv(MODEL_FILE, dtype=str)
    add = base[["player_id", "date", "chronic_load_28to8_lag", "chronic_load_28to8_wp_z"]]
    out = model.merge(add, on=["player_id", "date"], how="left", validate="one_to_one")
    assert len(out) == len(model)
    # left-merge preserves model row order; verify key alignment before concat
    assert (out["player_id"].to_numpy() == model_str["player_id"].to_numpy()).all()
    assert (out["date"].dt.strftime("%Y-%m-%d").to_numpy()
            == model_str["date"].to_numpy()).all()
    newc = ["chronic_load_28to8_lag", "chronic_load_28to8_wp_z"]
    out_csv = pd.concat([model_str, out[newc].reset_index(drop=True)], axis=1)
    out_path = OUT_DIR / "modeling_dataset_nonoverlap.csv"
    out_csv.to_csv(out_path, index=False)
    print(f"wrote {out_path} ({out_csv.shape[0]} rows x {out_csv.shape[1]} cols, +2 columns)")

    # ------------------------------------------------ correlation on soreness CC
    cc_cols = ["acute_load_7d_wp_z", "chronic_load_28to8_wp_z",
               "soreness_burden_recent3_wp_z", "prev_episode_ever",
               "calendar_time", "team", "season"]
    cc = out[out[cc_cols].notna().all(axis=1)]
    n_cc = len(cc)
    n_ev = int(cc["onset_day"].sum())
    n_ep = int(cc.loc[cc["onset_day"] == 1, "player_id"].nunique())
    a = cc["acute_load_7d_wp_z"].to_numpy(dtype=float)
    c = cc["chronic_load_28to8_wp_z"].to_numpy(dtype=float)
    pear = float(np.corrcoef(a, c)[0, 1])
    ra = pd.Series(a).rank(method="average").to_numpy()
    rc = pd.Series(c).rank(method="average").to_numpy()
    spear = float(np.corrcoef(ra, rc)[0, 1])
    # reference: R1 overlapping chronic z on its own CC sample
    cc_cols_r1 = ["acute_load_7d_wp_z", "chronic_load_28d_wp_z",
                  "soreness_burden_recent3_wp_z", "prev_episode_ever",
                  "calendar_time", "team", "season"]
    cc_r1 = out[out[cc_cols_r1].notna().all(axis=1)]
    pear_r1 = float(np.corrcoef(cc_r1["acute_load_7d_wp_z"],
                                cc_r1["chronic_load_28d_wp_z"])[0, 1])
    corr_df = pd.DataFrame([
        {"chronic_variant": "chronic_load_28to8_wp_z (non-overlap, t-28..t-8)",
         "sample": "soreness_cc", "n": n_cc, "events": n_ev,
         "event_players": n_ep, "pearson": round(pear, 6),
         "spearman": round(spear, 6)},
        {"chronic_variant": "chronic_load_28d_wp_z (R1 overlap, t-28..t-1; reference)",
         "sample": "soreness_cc", "n": len(cc_r1),
         "events": int(cc_r1["onset_day"].sum()),
         "event_players": int(cc_r1.loc[cc_r1["onset_day"] == 1, "player_id"].nunique()),
         "pearson": round(pear_r1, 6),
         "spearman": round(float(np.corrcoef(
             cc_r1["acute_load_7d_wp_z"].rank(method="average"),
             cc_r1["chronic_load_28d_wp_z"].rank(method="average"))[0, 1]), 6)},
    ])
    corr_path = OUT_DIR / "NONOVERLAP_CORRELATION.csv"
    corr_df.to_csv(corr_path, index=False)
    print(f"wrote {corr_path}: nonoverlap soreness CC N={n_cc}, events={n_ev}, "
          f"event players={n_ep}, Pearson={pear:.4f}, Spearman={spear:.4f} "
          f"(R1 overlap reference N={len(cc_r1)}, Pearson={pear_r1:.4f})")
    qa("nonoverlap soreness CC N == 19,758 (same 28-prior-day requirement as R1 "
       "chronic)", "PASS" if n_cc == 19758 else "WARN", f"N={n_cc}")

    # ------------------------------------------------ QA file + log
    qa_path = OUT_DIR / "NONOVERLAP_QA.txt"
    with open(qa_path, "w", encoding="utf-8") as f:
        f.write("NONOVERLAP WINDOW QA - R2 freeze, exposure workstream\n")
        f.write("script: 08_NONOVERLAP_WINDOW/run_nonoverlap_window.py\n\n")
        for check, status, detail in QA:
            f.write(f"[{status}] {check} {detail}\n")
    n_fail = sum(1 for _, s, _ in QA if s == "FAIL")
    print(f"wrote {qa_path} ({len(QA)} checks, {n_fail} FAIL)")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("[workstream exposures: non-overlapping chronic window (R4#5)] run complete\n")
        f.write(f"input: {MODEL_FILE} (n={len(model)})\n")
        f.write(f"outputs: {out_path} (+2 cols); {corr_path}; {qa_path}\n")
        f.write(f"nonoverlap soreness CC: N={n_cc}, events={n_ev}, event players={n_ep}; "
                f"acute x chronic_load_28to8_wp_z Pearson={pear:.4f}, Spearman={spear:.4f} "
                f"(R1 overlap reference Pearson={pear_r1:.4f}, N={len(cc_r1)})\n")
        f.write(f"QA checks: {len(QA)} run, {n_fail} FAIL\n\n")
    print(f"appended {LOG_FILE}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
