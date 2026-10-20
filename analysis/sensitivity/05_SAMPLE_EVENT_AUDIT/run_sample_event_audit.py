#!/usr/bin/env python3
"""
run_sample_event_audit.py — R2 freeze plan section 9.1
PONE-D-26-31950 (SoccerMon) R2 reproducibility freeze.

Final sample/event audit over:
  - theoretical player-day grid (50 players x 731 days = 36,550; rebuilt from
    sandbox 02_RAW_DATA/rebuilt_player_day_base.csv)
  - primary risk set (modeling_dataset.csv, 36,296 player-days)
  - wellness target sets (recent3 wellness z available) per variant
  - wellness complete-case sets per variant (mirror cc_sample() in
    06_ANALYSIS_CODE/04_run_reanalysis.R: non-missing on all Model A covariates
    EXCEPT days_since_last_episode, which is NA by design)

Inputs (read-only sandbox):
  07_ANALYSIS_OUTPUTS/modeling_dataset.csv
  07_ANALYSIS_OUTPUTS/episode_inventory.csv
  07_ANALYSIS_OUTPUTS/onset_day_inventory.csv
  02_RAW_DATA/rebuilt_player_day_base.csv

Outputs (this directory):
  SAMPLE_EVENT_AUDIT.csv   one row per sample definition
  EVENTS_BY_PLAYER.csv     risk-set + soreness-CC scopes, cumulative event share
  EVENTS_BY_TEAM.csv       both scopes
  EVENTS_BY_SEASON.csv     both scopes

Taxonomy: R2_INTERNAL_QA_ONLY (audit layer; no inferential claims).
Seed 20260722 (fixed; no stochastic steps in this audit).
"""
import pandas as pd
import numpy as np
from pathlib import Path

SEED = 20260722
TAXONOMY = "R2_INTERNAL_QA_ONLY"

FR = Path(r"D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE")
SB = FR / "02_R1_REPRODUCTION" / "r1_sandbox"
OUTDIR = FR / "05_SAMPLE_EVENT_AUDIT"
OUTDIR.mkdir(parents=True, exist_ok=True)

WELL = {
    "soreness": "soreness_burden_recent3_wp_z",
    "fatigue": "fatigue_burden_recent3_wp_z",
    "readiness": "readiness_deficit_recent3_wp_z",
}
# mirror cc_sample() in 04_run_reanalysis.R (days_since_last_episode excluded
# by design: NA when no previous episode; not a Model A covariate)
CC_BASE = ["onset_day", "acute_load_7d_wp_z", "chronic_load_28d_wp_z",
           "prev_episode_ever", "calendar_time", "team", "season",
           "player_id", "date", "prev_episode_count"]

md = pd.read_csv(SB / "07_ANALYSIS_OUTPUTS" / "modeling_dataset.csv")
grid = pd.read_csv(SB / "02_RAW_DATA" / "rebuilt_player_day_base.csv")
ep = pd.read_csv(SB / "07_ANALYSIS_OUTPUTS" / "episode_inventory.csv")
od = pd.read_csv(SB / "07_ANALYSIS_OUTPUTS" / "onset_day_inventory.csv")

assert len(md) == 36296 and md["onset_day"].sum() == 42
assert len(grid) == 36550 and grid["player_id"].nunique() == 50


def cc_sample(d, wcol):
    return d.dropna(subset=CC_BASE + [wcol])


def sample_row(sample_id, d, wcol=None, note=""):
    n = len(d)
    ev = int(d["onset_day"].sum())
    evp = int(d.loc[d["onset_day"] == 1, "player_id"].nunique())
    if wcol is not None:
        well_avail = int(d[wcol].notna().sum())
    else:
        well_avail = pd.NA
    ac = int((d["acute_load_7d_wp_z"].notna() &
              d["chronic_load_28d_wp_z"].notna()).sum()) if "acute_load_7d_wp_z" in d else pd.NA
    return {
        "taxonomy": TAXONOMY,
        "sample_id": sample_id,
        "n_player_days": n,
        "n_players": int(d["player_id"].nunique()),
        "onset_days": ev,
        "event_players": evp,
        "wellness_recent3_available_n": well_avail,
        "wellness_recent3_available_prop": (round(well_avail / n, 4)
                                            if wcol is not None and n else pd.NA),
        "acute_chronic_available_n": ac,
        "acute_chronic_available_prop": (round(ac / n, 4)
                                         if ac is not pd.NA and n else pd.NA),
        "notes": note,
    }


rows = []

# 1. theoretical grid — attach onset_day from the risk set for event counts
g = grid.merge(md[["player_id", "date", "onset_day"]],
               on=["player_id", "date"], how="left")
g["onset_day"] = g["onset_day"].fillna(0).astype(int)
rows.append(sample_row(
    "theoretical_grid_50x731", g, wcol=None,
    note=("50 players x 731 days (2020-01-01..2021-12-31) from "
          "02_RAW_DATA/rebuilt_player_day_base.csv; onset_day attached from "
          "primary risk set; wellness/load z-scores are defined within the "
          "risk set only, so availability is NA here.")))

# 2. primary risk set
rows.append(sample_row(
    "primary_risk_set", md, wcol=None,
    note=("modeling_dataset.csv at-risk player-days; wellness availability "
          "reported per-variant in the target/CC rows below.")))
# risk-set availability of each wellness exposure recorded via target rows

# 3+4. wellness target sets (exposure available) and CC sets
for v, wcol in WELL.items():
    tgt = md[md[wcol].notna()]
    rows.append(sample_row(
        f"wellness_target_{v}", tgt, wcol=wcol,
        note=(f"risk-set rows with non-missing {wcol}; not yet complete-case "
              f"on remaining Model A covariates.")))
    cc = cc_sample(md, wcol)
    rows.append(sample_row(
        f"wellness_cc_{v}", cc, wcol=wcol,
        note=("complete case on all Model A covariates except "
              "days_since_last_episode (NA by design); mirrors cc_sample() in "
              "04_run_reanalysis.R.")))

audit = pd.DataFrame(rows)

# ---- consistency cross-checks against inventory files -----------------------
ll = ep[ep["scope"] == "lower_limb"]
ep_per_player = ll.groupby("player_id").size()
od_dedup = od.drop_duplicates(subset=["player_id", "date", "washout_days"])
od3 = od_dedup[od_dedup["washout_days"] == 3]
cross = {
    "ll_episode_rows": len(ll),
    "ll_episode_players": int(ll["player_id"].nunique()),
    "onset_inventory_unique_player_dates_w3d": len(od3),
    "onset_inventory_at_risk_primary_w3d": int(od3["at_risk_primary"].sum()),
    "risk_set_onset_days": int(md["onset_day"].sum()),
}
print("cross-checks:", cross)

# ---- event distributions ----------------------------------------------------
scopes = {
    "risk_set_42": md,
    "soreness_cc_28": cc_sample(md, WELL["soreness"]),
}

# EVENTS_BY_PLAYER: all 50 players x 2 scopes, sorted by events desc, cum share
pb_rows = []
for scope, d in scopes.items():
    meta = md.groupby("player_id").agg(
        team=("team", "first"),
        seasons=("season", lambda s: ";".join(str(x) for x in sorted(s.unique()))),
    )
    ev = d.groupby("player_id")["onset_day"].sum().reindex(meta.index, fill_value=0)
    tot = ev.sum()
    order = ev.sort_values(ascending=False)
    cum = order.cumsum() / tot
    for rank, (pid, e) in enumerate(order.items(), start=1):
        pb_rows.append({
            "taxonomy": TAXONOMY,
            "scope": scope,
            "player_id": pid,
            "team": meta.loc[pid, "team"],
            "seasons_active": meta.loc[pid, "seasons"],
            "events": int(e),
            "pct_of_scope_events": round(e / tot * 100, 2),
            "cumulative_pct": round(cum.loc[pid] * 100, 2),
            "event_rank_in_scope": rank,
        })
events_by_player = pd.DataFrame(pb_rows)

# EVENTS_BY_TEAM / EVENTS_BY_SEASON
def by_group(d, col, scope):
    out = []
    tot_ev = d["onset_day"].sum()
    for lv, g2 in d.groupby(col):
        out.append({
            "taxonomy": TAXONOMY,
            "scope": scope,
            col: lv,
            "player_days": len(g2),
            "events": int(g2["onset_day"].sum()),
            "pct_of_scope_events": round(g2["onset_day"].sum() / tot_ev * 100, 2),
            "event_players": int(g2.loc[g2["onset_day"] == 1, "player_id"].nunique()),
            "players": int(g2["player_id"].nunique()),
        })
    return out

tb_rows, sn_rows = [], []
for scope, d in scopes.items():
    tb_rows += by_group(d, "team", scope)
    sn_rows += by_group(d, "season", scope)
events_by_team = pd.DataFrame(tb_rows)
events_by_season = pd.DataFrame(sn_rows)

# highest contributor (both scopes) -> annotate SAMPLE_EVENT_AUDIT notes
hi = {}
for scope, d in scopes.items():
    ev = d.groupby("player_id")["onset_day"].sum()
    top_pid, top_n = ev.idxmax(), int(ev.max())
    hi[scope] = (top_pid, top_n, top_n / ev.sum())
    print(f"{scope}: highest contributor {top_pid} events={top_n} "
          f"share={top_n/ev.sum()*100:.1f}%")

audit.loc[audit["sample_id"] == "primary_risk_set", "notes"] += (
    f" Highest event contributor: {hi['risk_set_42'][0]} with "
    f"{hi['risk_set_42'][1]}/42 events ({hi['risk_set_42'][2]*100:.1f}%).")
audit.loc[audit["sample_id"] == "wellness_cc_soreness", "notes"] += (
    f" Highest event contributor: {hi['soreness_cc_28'][0]} with "
    f"{hi['soreness_cc_28'][1]}/28 events ({hi['soreness_cc_28'][2]*100:.1f}%)."
    " Manuscript-facing event distribution uses this sample. 28 CC onset-days "
    "across 9 event players is a severe information limit; TeamB contributes "
    "0 CC events (separation).")

audit.to_csv(OUTDIR / "SAMPLE_EVENT_AUDIT.csv", index=False)
events_by_player.to_csv(OUTDIR / "EVENTS_BY_PLAYER.csv", index=False)
events_by_team.to_csv(OUTDIR / "EVENTS_BY_TEAM.csv", index=False)
events_by_season.to_csv(OUTDIR / "EVENTS_BY_SEASON.csv", index=False)
print("wrote:", [p.name for p in OUTDIR.glob("*.csv")])
print(audit[["sample_id", "n_player_days", "n_players", "onset_days",
             "event_players"]].to_string(index=False))
