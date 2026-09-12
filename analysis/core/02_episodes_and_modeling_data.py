#!/usr/bin/env python3
"""
02_episodes_and_modeling_data.py
================================
Phase 6 of the PLOS ONE R1 revision (SoccerMon): rebuild injury episodes from
raw injury.csv, define the NEW onset-day estimand and its protocol-concordant
risk set, and build the modeling dataset.

Inputs (read-only)
------------------
02_RAW_DATA/subjective_readonly_work/subjective/injury/injury.csv
02_RAW_DATA/rebuilt_player_day_base.csv
00_FROZEN_SUBMISSION/.../03_DERIVED_DATA/final_lower_limb_injury_episodes_7day.csv  (comparison only)

Outputs
-------
07_ANALYSIS_OUTPUTS/episode_inventory.csv
07_ANALYSIS_OUTPUTS/onset_day_inventory.csv
07_ANALYSIS_OUTPUTS/player_event_distribution.csv
07_ANALYSIS_OUTPUTS/modeling_dataset.csv
07_ANALYSIS_OUTPUTS/episode_comparison_vs_frozen.csv
03_VARIABLE_AUDIT/analysis_unit_estimand_audit.md
03_VARIABLE_AUDIT/risk_set_definition.md
logs/02_episodes.log

Key conventions (frozen in Phase 5; see 05_REVISION_SAP and
03_VARIABLE_AUDIT/canonical_variable_dictionary.csv when present):
  fatigue_burden      = 6 - fatigue        (1-5 scale)
  soreness_burden     = 6 - soreness       (1-5 scale)
  readiness_deficit   = 11 - readiness     (1-10 scale)
  within-player z     = (x - player mean) / player SD, requires >= 10 non-missing
                        observations and player SD > 0 (sample SD, ddof=1)

Episode definition (verified against frozen pipeline / manuscript Methods):
  - injury.csv `type` JSON expanded to body-location entries (306 expected)
  - lower-limb = location contains any of: hip, groin, thigh, hamstring,
    quadriceps, knee, leg, calf, shin, ankle, foot, toe  (includes groin_hip)
  - same-day duplicate reports (same player, same exact location, same date)
    collapsed to one report (protocol: same-day duplicates collapsed)
  - episodes per (player, exact body location): adjacent reports with gap
    <= washout days merge into one episode (gap_rule = adjacent_leq)
  - washouts 3 / 7 / 14 days; 7-day is primary

Expected validation counts:
  entries 306 / LL 295 / minor 230 / major 76 / non-LL 11
  episodes  3d: all=147 LL=136 knee=49 ; 7d: all=101 LL=92 knee=22 ;
            14d: all=72 LL=64 knee=12
  7d LL unique onset-days = 52 ; event players = 15
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
WS = Path(os.environ.get("SOCCERMON_WORKSPACE", REPO_ROOT / "workspace")).resolve()

INJURY_FILE = WS / "02_RAW_DATA" / "subjective_readonly_work" / "subjective" / "injury" / "injury.csv"
BASE_FILE = WS / "02_RAW_DATA" / "rebuilt_player_day_base.csv"
_frozen_default = (WS / "00_FROZEN_SUBMISSION" / "s2_archive_extracted"
                   / "S2_File_analysis_code_archive_PLOS_RERUN_FINAL_CLEAN"
                   / "03_DERIVED_DATA" / "final_lower_limb_injury_episodes_7day.csv")
FROZEN_LL_7D = Path(os.environ.get("SOCCERMON_FROZEN_EPISODES", _frozen_default)).resolve()

OUT_DIR = WS / "07_ANALYSIS_OUTPUTS"
AUDIT_DIR = WS / "03_VARIABLE_AUDIT"
LOG_FILE = WS / "logs" / "02_episodes.log"

PRIMARY_WASHOUT = 7
WASHOUTS = [3, 7, 14]

LOWER_LIMB_KEYWORDS = ["hip", "groin", "thigh", "hamstring", "quadriceps",
                       "knee", "leg", "calf", "shin", "ankle", "foot", "toe"]

SEVERITY_RANK = {"minor": 1, "moderate": 2, "major": 3}

WELLNESS_ITEMS = ["fatigue", "readiness", "soreness", "mood", "stress",
                  "sleep_quality", "sleep_duration"]

ORIGIN = pd.Timestamp("2020-01-01")


def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")


# ---------------------------------------------------------------------------
# Part A: parse raw injury.csv -> long body-location table -> episodes
# ---------------------------------------------------------------------------

def parse_injury_long():
    injury = pd.read_csv(INJURY_FILE)
    log(f"Raw injury rows: {len(injury)}")
    injury["date"] = pd.to_datetime(injury["timestamp"], format="%d.%m.%Y", errors="coerce")
    assert injury["date"].notna().all(), "unparseable injury dates"

    rows = []
    for idx, r in injury.iterrows():
        d = json.loads(str(r["type"]).replace("'", '"'))
        assert isinstance(d, dict), f"row {idx}: type is not a JSON object"
        for loc, sev in d.items():
            rows.append({
                "player_id": r["player_name"],
                "body_location": str(loc).strip().lower(),
                "severity": str(sev).strip().lower(),
                "date": r["date"],
            })
    long_df = pd.DataFrame(rows)
    n_entries = len(long_df)
    long_df["is_lower_limb"] = long_df["body_location"].apply(
        lambda l: any(k in l for k in LOWER_LIMB_KEYWORDS))
    long_df["is_knee"] = long_df["body_location"].str.contains("knee")

    n_ll = int(long_df["is_lower_limb"].sum())
    n_minor = int((long_df["severity"] == "minor").sum())
    n_major = int((long_df["severity"] == "major").sum())
    n_non_ll = int((~long_df["is_lower_limb"]).sum())
    log(f"Body-location entries: {n_entries} (expected 306)")
    log(f"  lower-limb entries: {n_ll} (expected 295)")
    log(f"  minor: {n_minor} (expected 230), major: {n_major} (expected 76)")
    log(f"  non-lower-limb entries: {n_non_ll} (expected 11)")
    log(f"  unique locations: {sorted(long_df['body_location'].unique())}")
    log(f"  players with any report: {long_df['player_id'].nunique()}; "
        f"date range {long_df['date'].min().date()} .. {long_df['date'].max().date()}")
    assert (n_entries, n_ll, n_minor, n_major, n_non_ll) == (306, 295, 230, 76, 11)

    # Protocol: same-day duplicates (same player + exact location + date) collapsed
    n_dup = int(long_df.duplicated(subset=["player_id", "body_location", "date"]).sum())
    long_df = long_df.drop_duplicates(subset=["player_id", "body_location", "date"])
    log(f"Same-day duplicate (player, location, date) entries collapsed: {n_dup} "
        f"-> {len(long_df)} reports remain")
    return long_df


def build_episodes(reports, washout_days):
    """One episode per (player, exact body location); adjacent reports with
    gap <= washout_days merge (gap_rule = adjacent_leq, as frozen pipeline)."""
    episodes = []
    for (player, loc), g in reports.groupby(["player_id", "body_location"]):
        g = g.sort_values("date").reset_index(drop=True)
        start = end = g.loc[0, "date"]
        sevs = [g.loc[0, "severity"]]
        n = 1
        for i in range(1, len(g)):
            d = g.loc[i, "date"]
            if (d - end).days <= washout_days:
                end = d
                sevs.append(g.loc[i, "severity"])
                n += 1
            else:
                episodes.append((player, loc, start, end, n, sevs))
                start = end = d
                sevs = [g.loc[i, "severity"]]
                n = 1
        episodes.append((player, loc, start, end, n, sevs))
    ep = pd.DataFrame(episodes, columns=["player_id", "body_location", "onset_date",
                                         "end_date", "n_reports", "_sevs"])
    ep["severity_max"] = ep["_sevs"].apply(
        lambda ss: max(ss, key=lambda s: SEVERITY_RANK.get(s, 0)))
    ep = ep.drop(columns=["_sevs"])
    return ep


def part_a(reports):
    inventory = []
    ep_by_scope_washout = {}
    for washout in WASHOUTS:
        for scope, sub in [("all", reports),
                           ("lower_limb", reports[reports["is_lower_limb"]]),
                           ("knee", reports[reports["is_knee"]])]:
            ep = build_episodes(sub, washout)
            ep["washout_days"] = washout
            ep["scope"] = scope
            ep_by_scope_washout[(scope, washout)] = ep
            inventory.append(ep)
            log(f"washout {washout:2d}d  {scope:11s}: {len(ep)} episodes")

    inv = pd.concat(inventory, ignore_index=True)[
        ["player_id", "body_location", "onset_date", "end_date", "n_reports",
         "severity_max", "washout_days", "scope"]]
    inv = inv.sort_values(["washout_days", "scope", "player_id", "onset_date"])
    inv.to_csv(OUT_DIR / "episode_inventory.csv", index=False, date_format="%Y-%m-%d")
    log(f"Wrote {OUT_DIR / 'episode_inventory.csv'} ({len(inv)} episode rows)")

    # Hard validation against manuscript/frozen counts
    expected = {(3, "all"): 147, (3, "lower_limb"): 136, (3, "knee"): 49,
                (7, "all"): 101, (7, "lower_limb"): 92, (7, "knee"): 22,
                (14, "all"): 72, (14, "lower_limb"): 64, (14, "knee"): 12}
    for (w, scope), n in expected.items():
        got = len(ep_by_scope_washout[(scope, w)])
        assert got == n, f"episode count mismatch washout={w} scope={scope}: {got} != {n}"
    log("Validated episode counts: 3d 147/136/49, 7d 101/92/22, 14d 72/64/12 "
        "(all/lower_limb/knee)")
    return ep_by_scope_washout


# ---------------------------------------------------------------------------
# Part B: onset-days and risk set (new estimand)
# ---------------------------------------------------------------------------

def build_onset_days(ep, washout):
    """Unique onset-days: same player + same onset date merged across locations."""
    od = (ep.groupby(["player_id", "onset_date"])
            .agg(n_locations=("body_location", "nunique"),
                 locations=("body_location", lambda s: ";".join(sorted(s))))
            .reset_index()
            .rename(columns={"onset_date": "date"})
            .sort_values(["player_id", "date"]))
    od["washout_days"] = washout
    return od


def build_risk_set(base_pd, ll_episodes, washout):
    """Protocol-concordant risk set on the player-day grid.

    A player-day t is AT RISK (primary) unless the player is inside an ongoing
    lower-limb episode, i.e. inside (onset, end] of any episode: the onset day
    itself is at risk (the player entered day t free of an ongoing episode);
    days onset+1 .. end are not; at-risk resumes at end+1.

    Sensitivity variant: at-risk resumes at end + 1 + washout (an additional
    washout-length guard window after each episode).
    """
    rs = base_pd[["player_id", "date"]].copy()
    rs["during_episode"] = 0          # t in (onset, end] of an episode
    rs["in_guard_window"] = 0         # t in (end, end + washout]
    for e in ll_episodes.itertuples():
        m = rs["player_id"] == e.player_id
        rs.loc[m & (rs["date"] > e.onset_date) & (rs["date"] <= e.end_date),
               "during_episode"] = 1
        rs.loc[m & (rs["date"] > e.end_date) & (rs["date"] <= e.end_date + pd.Timedelta(days=washout)),
               "in_guard_window"] = 1
    rs["at_risk_primary"] = (rs["during_episode"] == 0).astype(int)
    rs["at_risk_sens_end_plus_washout"] = (
        (rs["during_episode"] == 0) & (rs["in_guard_window"] == 0)).astype(int)

    onsets = (ll_episodes.groupby(["player_id", "onset_date"]).size()
              .reset_index(name="n_locations")
              .rename(columns={"onset_date": "date"}))
    rs = rs.merge(onsets, on=["player_id", "date"], how="left")
    rs["n_locations"] = rs["n_locations"].fillna(0).astype(int)
    rs["onset_day"] = (rs["n_locations"] > 0).astype(int)
    return rs


def part_b(base_pd, ep_by_scope_washout):
    # Onset-day inventory for all washouts
    od_all = []
    for w in WASHOUTS:
        od_all.append(build_onset_days(ep_by_scope_washout[("lower_limb", w)], w))
    od = pd.concat(od_all, ignore_index=True)

    # Risk set on the primary 7-day washout
    ll7 = ep_by_scope_washout[("lower_limb", PRIMARY_WASHOUT)]
    rs = build_risk_set(base_pd, ll7, PRIMARY_WASHOUT)

    # Flag whether each 7d onset-day falls inside the primary risk set
    rs_flag = rs[["player_id", "date", "at_risk_primary",
                  "at_risk_sens_end_plus_washout"]]
    od = od.merge(rs_flag, on=["player_id", "date"], how="left")
    od.to_csv(OUT_DIR / "onset_day_inventory.csv", index=False, date_format="%Y-%m-%d")
    log(f"Wrote {OUT_DIR / 'onset_day_inventory.csv'}")

    for w in WASHOUTS:
        sub = od[od["washout_days"] == w]
        log(f"washout {w:2d}d: unique LL onset-days = {len(sub)} "
            f"(multi-location days: {int((sub['n_locations'] > 1).sum())})")
    od7 = od[od["washout_days"] == PRIMARY_WASHOUT]
    n_od7 = len(od7)
    assert n_od7 == 52, f"expected 52 unique 7d onset-days, got {n_od7}"
    n_in_rs = int(od7["at_risk_primary"].sum())
    log(f"7d onset-days: {n_od7} total; {n_in_rs} occur on at-risk days "
        f"(primary risk set); {n_od7 - n_in_rs} onset-days occur while the player "
        f"is already inside another ongoing episode (excluded from risk set)")

    # Player-level distribution (all 50 players in the base grid)
    players = base_pd[["player_id"]].drop_duplicates()
    ep_counts = ll7.groupby("player_id").size().rename("ll_episodes_7d")
    od_counts = od7.groupby("player_id").size().rename("ll_onset_days_7d")
    pos_days = (rs[rs["at_risk_primary"] == 1].groupby("player_id")["onset_day"]
                .sum().rename("outcome_positive_days_in_risk_set"))
    atrisk_days = (rs.groupby("player_id")["at_risk_primary"]
                   .sum().rename("at_risk_player_days_primary"))
    atrisk_sens = (rs.groupby("player_id")["at_risk_sens_end_plus_washout"]
                   .sum().rename("at_risk_player_days_sens_end_plus_washout"))
    dist = (players.merge(ep_counts, on="player_id", how="left")
                   .merge(od_counts, on="player_id", how="left")
                   .merge(pos_days, on="player_id", how="left")
                   .merge(atrisk_days, on="player_id", how="left")
                   .merge(atrisk_sens, on="player_id", how="left")
                   .fillna(0))
    for c in dist.columns[1:]:
        dist[c] = dist[c].astype(int)
    dist["event_player"] = (dist["ll_onset_days_7d"] > 0).astype(int)
    dist = dist.sort_values("player_id")
    dist.to_csv(OUT_DIR / "player_event_distribution.csv", index=False)
    log(f"Wrote {OUT_DIR / 'player_event_distribution.csv'}")
    log(f"Event players (>=1 LL onset-day, 7d): {int(dist['event_player'].sum())} "
        f"of {len(dist)}")
    assert int(dist["event_player"].sum()) == 15

    log(f"Risk set (primary, 7d washout): "
        f"{int(rs['at_risk_primary'].sum())} at-risk player-days of {len(rs)}; "
        f"outcome positives in risk set = "
        f"{int(rs.loc[rs['at_risk_primary'] == 1, 'onset_day'].sum())}")
    log(f"Risk set (sensitivity end+1+washout): "
        f"{int(rs['at_risk_sens_end_plus_washout'].sum())} at-risk player-days; "
        f"outcome positives = "
        f"{int(rs.loc[rs['at_risk_sens_end_plus_washout'] == 1, 'onset_day'].sum())}")
    return rs, od, dist


# ---------------------------------------------------------------------------
# Part C: modeling dataset
# ---------------------------------------------------------------------------

def within_player_z(df, value_col, z_col, min_obs=10):
    """(x - player mean)/player SD over the FULL player-day base; NaN when the
    player has < min_obs non-missing values or SD == 0 (sample SD, ddof=1)."""
    g = df.groupby("player_id")[value_col]
    mean = g.transform("mean")
    sd = g.transform("std")          # ddof=1
    n = g.transform("count")
    z = (df[value_col] - mean) / sd
    z[(n < min_obs) | (sd <= 0)] = np.nan
    df[z_col] = z


def part_c(base_pd, rs, ll7):
    df = base_pd.merge(
        rs[["player_id", "date", "at_risk_primary",
            "at_risk_sens_end_plus_washout", "onset_day", "n_locations"]],
        on=["player_id", "date"], how="left", validate="one_to_one")

    # Canonical burden/deficit on lagged exposure columns (linear transform of
    # the already-lagged values: 6 - x for 1-5 items, 11 - x for readiness 1-10)
    df["fatigue_burden_lag1"] = 6 - df["fatigue_lag1"]
    df["fatigue_burden_recent3"] = 6 - df["fatigue_recent3"]
    df["soreness_burden_lag1"] = 6 - df["soreness_lag1"]
    df["soreness_burden_recent3"] = 6 - df["soreness_recent3"]
    df["readiness_deficit_lag1"] = 11 - df["readiness_lag1"]
    df["readiness_deficit_recent3"] = 11 - df["readiness_recent3"]

    # Within-player z over the full base grid (before risk-set restriction),
    # per the Phase-5 convention (>=10 obs, SD>0)
    within_player_z(df, "acute_load_7d_lag", "acute_load_7d_wp_z")
    within_player_z(df, "chronic_load_28d_lag", "chronic_load_28d_wp_z")
    within_player_z(df, "fatigue_burden_lag1", "fatigue_burden_wp_z")
    within_player_z(df, "soreness_burden_lag1", "soreness_burden_wp_z")
    within_player_z(df, "readiness_deficit_lag1", "readiness_deficit_wp_z")
    # Sensitivity: recent3 versions
    within_player_z(df, "fatigue_burden_recent3", "fatigue_burden_recent3_wp_z")
    within_player_z(df, "soreness_burden_recent3", "soreness_burden_recent3_wp_z")
    within_player_z(df, "readiness_deficit_recent3", "readiness_deficit_recent3_wp_z")

    # Event history (7d lower-limb episodes), per player, evaluated before day t
    hist = []
    ep_by_player = {p: g.sort_values("onset_date")
                    for p, g in ll7.groupby("player_id")}
    for p, g in df.groupby("player_id"):
        eps = ep_by_player.get(p)
        g = g.sort_values("date").copy()
        if eps is None:
            g["prev_episode_count"] = 0
            g["days_since_last_episode"] = np.nan
        else:
            onsets = eps["onset_date"].values
            idx = np.searchsorted(onsets, g["date"].values, side="left")
            g["prev_episode_count"] = idx
            last = np.where(idx > 0, onsets[np.clip(idx - 1, 0, None)], np.datetime64("NaT"))
            g["days_since_last_episode"] = (g["date"].values - last) / np.timedelta64(1, "D")
            g.loc[g["prev_episode_count"] == 0, "days_since_last_episode"] = np.nan
        g["prev_episode_ever"] = (g["prev_episode_count"] > 0).astype(int)
        hist.append(g)
    df = pd.concat(hist, ignore_index=True)

    df["season"] = df["year"]
    df["calendar_time"] = (df["date"] - ORIGIN).dt.days

    # Restrict to the primary risk set; keep the sensitivity flag for filtering
    model = df[df["at_risk_primary"] == 1].copy()

    wellness_lag_cols = [f"{w}_lag1" for w in WELLNESS_ITEMS]
    wellness_recent3_cols = [f"{w}_recent3" for w in WELLNESS_ITEMS]
    cols = (
        ["player_id", "date", "team", "season", "calendar_time",
         "onset_day",
         "acute_load_7d_lag", "chronic_load_28d_lag", "acwr_7_28_lag"]
        + wellness_lag_cols + wellness_recent3_cols
        + ["fatigue_burden_lag1", "fatigue_burden_recent3",
           "soreness_burden_lag1", "soreness_burden_recent3",
           "readiness_deficit_lag1", "readiness_deficit_recent3",
           "acute_load_7d_wp_z", "chronic_load_28d_wp_z",
           "fatigue_burden_wp_z", "soreness_burden_wp_z", "readiness_deficit_wp_z",
           "fatigue_burden_recent3_wp_z", "soreness_burden_recent3_wp_z",
           "readiness_deficit_recent3_wp_z",
           "prev_episode_count", "days_since_last_episode", "prev_episode_ever",
           "at_risk_sens_end_plus_washout"]
    )
    model = model[cols].sort_values(["player_id", "date"])
    model.to_csv(OUT_DIR / "modeling_dataset.csv", index=False, date_format="%Y-%m-%d")
    log(f"Wrote {OUT_DIR / 'modeling_dataset.csv'}: "
        f"{model.shape[0]} rows x {model.shape[1]} cols; "
        f"players={model['player_id'].nunique()}; "
        f"outcome positives (onset_day=1) = {int(model['onset_day'].sum())}")

    # Missingness snapshot for exposures / z columns
    expo_cols = [c for c in cols if c not in
                 ("player_id", "date", "team", "season", "calendar_time",
                  "onset_day", "prev_episode_count", "days_since_last_episode",
                  "prev_episode_ever", "at_risk_sens_end_plus_washout")]
    miss = model[expo_cols].isna().sum()
    log("Non-missing exposure counts in modeling dataset (of "
        f"{len(model)} rows):")
    for c in expo_cols:
        log(f"  {c:35s} non-missing={len(model) - int(miss[c])}")
    log(f"  days_since_last_episode             non-missing="
        f"{int(model['days_since_last_episode'].notna().sum())} "
        f"(NA = no previous episode, by design)")
    return model


# ---------------------------------------------------------------------------
# Part D: comparison against frozen derived episodes
# ---------------------------------------------------------------------------

def part_d(ll7):
    """Compare rebuilt episodes with the optional frozen reference.

    The frozen reference is a provenance check only; it is not required to
    construct the revised analytical dataset. Public users can omit it.
    """
    keys = ["player_id", "body_location", "onset_date", "end_date"]
    if not FROZEN_LL_7D.exists():
        log(f"Frozen episode reference not supplied; skipping comparison: {FROZEN_LL_7D}")
        pd.DataFrame([{
            "match_status": "REFERENCE_NOT_SUPPLIED",
            "reference_path": str(FROZEN_LL_7D),
        }]).to_csv(OUT_DIR / "episode_comparison_vs_frozen.csv", index=False)
        return None, None, None, None

    frozen = pd.read_csv(FROZEN_LL_7D, parse_dates=["onset_date", "end_date"])
    new = ll7.copy()
    merged = frozen.merge(new, on=keys, how="outer", suffixes=("_frozen", "_new"),
                          indicator=True)
    cmp_df = merged[keys + ["n_reports_frozen", "n_reports_new", "_merge"]].copy()
    cmp_df.columns = ["player_id", "body_location", "onset_date", "end_date",
                      "n_reports_frozen", "n_reports_rebuilt", "match_status"]
    status_map = {"both": "matched", "left_only": "frozen_only",
                  "right_only": "rebuilt_only"}
    cmp_df["match_status"] = cmp_df["match_status"].map(status_map)
    cmp_df = cmp_df.sort_values(keys)
    cmp_df.to_csv(OUT_DIR / "episode_comparison_vs_frozen.csv", index=False,
                  date_format="%Y-%m-%d")

    n_both = int((merged["_merge"] == "both").sum())
    n_frozen_only = int((merged["_merge"] == "left_only").sum())
    n_new_only = int((merged["_merge"] == "right_only").sum())
    log(f"Comparison vs frozen final_lower_limb_injury_episodes_7day.csv: "
        f"frozen={len(frozen)}, rebuilt={len(new)}, matched={n_both}, "
        f"frozen_only={n_frozen_only}, rebuilt_only={n_new_only}")
    if n_frozen_only == 0 and n_new_only == 0:
        log("  -> episode sets identical on (player, location, onset, end)")
    else:
        log("  -> DIFFERENCES in episode sets (see episode_comparison_vs_frozen.csv):")
        log(merged[merged["_merge"] != "both"][keys + ["_merge"]].to_string(index=False))

    both = merged[merged["_merge"] == "both"]
    nrep_diff = int((both["n_reports_frozen"] != both["n_reports_new"]).sum())
    log(f"  n_reports differs on {nrep_diff}/{n_both} matched episodes "
        f"(expected: frozen pipeline kept same-day duplicate reports, the "
        f"revision collapses them per protocol)")
    if nrep_diff:
        d = both[both["n_reports_frozen"] != both["n_reports_new"]]
        log(d[["player_id", "body_location", "onset_date",
               "n_reports_frozen", "n_reports_new"]].to_string(index=False))
    return n_both, n_frozen_only, n_new_only, nrep_diff


# ---------------------------------------------------------------------------
# Audit documents
# ---------------------------------------------------------------------------

def write_audit_md(ep_by_scope_washout, od, rs, dist, model, cmp_stats):
    n_both, n_frozen_only, n_new_only, nrep_diff = cmp_stats
    ll7 = ep_by_scope_washout[("lower_limb", PRIMARY_WASHOUT)]
    od7 = od[od["washout_days"] == PRIMARY_WASHOUT]
    n_atrisk = int(rs["at_risk_primary"].sum())
    n_atrisk_sens = int(rs["at_risk_sens_end_plus_washout"].sum())
    n_pos = int(rs.loc[rs["at_risk_primary"] == 1, "onset_day"].sum())
    n_pos_sens = int(rs.loc[rs["at_risk_sens_end_plus_washout"] == 1, "onset_day"].sum())
    n_od_in_rs = int(od7["at_risk_primary"].sum())

    if n_both is None:
        comparison_text = (
            "Frozen episode reference not supplied in the public-facing run; "
            "the provenance-only comparison was skipped. The revised analytical "
            "dataset construction is otherwise unchanged."
        )
    else:
        comparison_text = (
            f"Against the supplied frozen episode reference: rebuilt={len(ll7)}, "
            f"matched={n_both}, frozen-only={n_frozen_only}, rebuilt-only={n_new_only}; "
            f"n_reports differs on {nrep_diff} matched episodes. See "
            "`07_ANALYSIS_OUTPUTS/episode_comparison_vs_frozen.csv`."
        )

    md = f"""# Analysis-unit and estimand audit (Phase 6, R1 revision)

Generated by `06_ANALYSIS_CODE/02_episodes_and_modeling_data.py`
(see `logs/02_episodes.log`). Primary washout = 7 days; time scale = calendar day.

## Five different "event" denominators — do not conflate

| # | Quantity | Definition | Value (7d washout) |
|---|----------|-----------|--------------------|
| 1 | Body-location episodes | Episodes built per (player, exact body location); same player can have several episodes starting the same day at different locations | all=101, lower-limb=92, knee=22 (3d: 147/136/49; 14d: 72/64/12) |
| 2 | Unique onset-days | Player-days with >= 1 lower-limb episode onset; same-day multi-location onsets merged | {len(od7)} |
| 3 | Old risk-window positive days (frozen pipeline outcome) | Player-days flagged `future_1_7d_lower_limb_episode_onset=1`: day not inside an episode of that location AND a new onset within the next 1-7 days; these are *prediction-window* days, not events | 330 (of 36,550); 198 after within-player-z complete-case filtering in the frozen primary model sample (n=16,992) |
| 4 | Event players | Players with >= 1 lower-limb onset-day | {int(dist['event_player'].sum())} of {len(dist)} |
| 5 | At-risk player-days (NEW estimand denominator) | Player-days in the protocol-concordant risk set (not inside an ongoing lower-limb episode; onset day at risk; resume end+1) | {n_atrisk} of {len(rs)} player-days; outcome-positive days (onset_day=1) = {n_pos} |

### Why they differ

- (1) counts episodes per body location; (2) collapses same-day onsets across
  locations to one event per player-day — the unit the revised outcome uses.
- (3) is the frozen submission's outcome: a 1-7-day *look-ahead* window. One
  episode generates up to 7 positive window-days, so 92 episodes inflate to 330
  positive days; it is a different estimand (prediction within 7 days vs
  day-t onset) and is retained only as the comparability benchmark.
- (4) is a player-level count — relevant to clustering/frailty, not a day-level
  denominator.
- (5) is the revised denominator: of the {len(od7)} unique onset-days,
  {len(od7) - n_od_in_rs} occur while the player is already inside another
  ongoing lower-limb episode and are therefore not at-risk; the observed
  outcome-positive days in the risk set are {n_pos}.

Sensitivity risk set (at-risk resumes end+1+washout): {n_atrisk_sens} at-risk
player-days, {n_pos_sens} outcome-positive days.

## Comparison with the frozen derived file (Part D)

{comparison_text}

The frozen pipeline's 52 unique onset-days and 330/198 risk-window numbers are
quoted from its own logs
(`00_FROZEN_SUBMISSION/.../08_LOGS/03_build_player_day_outcomes_log.txt`,
`04_create_within_player_features_log.txt`).
"""
    (AUDIT_DIR / "analysis_unit_estimand_audit.md").write_text(md, encoding="utf-8")
    log(f"Wrote {AUDIT_DIR / 'analysis_unit_estimand_audit.md'}")


def write_risk_set_md():
    md = """# Risk-set definition (Phase 6, R1 revision)

Generated by `06_ANALYSIS_CODE/02_episodes_and_modeling_data.py`.

## Episode construction

- Source: raw `injury.csv` (162 reports); `type` JSON expanded to 306
  body-location entries; same-day duplicates (same player, exact location,
  date) collapsed per protocol.
- Lower limb = location contains hip/groin/thigh/hamstring/quadriceps/knee/
  leg/calf/shin/ankle/foot/toe (includes `groin_hip`), as in the manuscript
  Methods and the frozen pipeline.
- Episodes per (player, exact body location): adjacent reports separated by
  <= `washout` days merge into one episode (`adjacent_leq` gap rule).
- Washout = 7 days (primary); 3 and 14 days retained as sensitivity variants
  in `episode_inventory.csv` / `onset_day_inventory.csv`.

## Time scale

Calendar day (2020-01-01 .. 2021-12-31 grid of `rebuilt_player_day_base.csv`).
`calendar_time` = days since 2020-01-01. No alignment to episode onset; each
player contributes all of his observed player-days.

## Outcome (new estimand)

`onset_day(t) = 1` if player has >= 1 lower-limb episode onset on day t
(any location; same-day multi-location onsets count once).

## Risk set (protocol-concordant, primary)

A player-day t contributes to the risk set iff the player is NOT inside an
ongoing lower-limb episode at the start of day t:

- the onset day t itself IS at risk (the onset is the event being modelled);
- days onset+1 .. end of an episode are NOT at risk — no new onset can be
  counted while the player is already injured;
- at-risk resumes at end+1.

Consequence: an episode whose onset falls inside another ongoing episode of
the same player contributes no at-risk day and no outcome event (it is not
part of the estimand's observable risk set).

## Sensitivity risk set

`at_risk_sens_end_plus_washout`: additionally excludes days
end+1 .. end+washout after every episode (at-risk resumes end+1+washout),
guard window against under-reported episode tails. Stored as a column in
`modeling_dataset.csv`; filter `== 1` to use.

## Event-history variables (per player, evaluated before day t)

- `prev_episode_count`: number of prior 7-day lower-limb episodes
  (onset < t), across all body locations.
- `days_since_last_episode`: t minus the most recent prior episode onset
  (days); NA when the player has had no prior episode.
- `prev_episode_ever`: 1 if `prev_episode_count` > 0.

## Exposures

All exposures are lagged (information up to t-1 only): `acute_load_7d_lag`,
`chronic_load_28d_lag`, `acwr_7_28_lag`, wellness `_lag1` / `_recent3`.
Canonical direction: `fatigue_burden = 6 - fatigue`,
`soreness_burden = 6 - soreness`, `readiness_deficit = 11 - readiness`
(higher = worse). Within-player z-scores computed over the full player-day
base per player: (x - player mean) / player SD, requiring >= 10 non-missing
observations and SD > 0 (sample SD, ddof=1); `_recent3_wp_z` variants are the
sensitivity versions.
"""
    (AUDIT_DIR / "risk_set_definition.md").write_text(md, encoding="utf-8")
    log(f"Wrote {AUDIT_DIR / 'risk_set_definition.md'}")


# ---------------------------------------------------------------------------

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    open(LOG_FILE, "w", encoding="utf-8").close()

    log("=" * 72)
    log("02_episodes_and_modeling_data.py — Phase 6 episode/risk-set/modeling build")
    log("=" * 72)

    log("\n--- Part A: episode rebuild from raw injury.csv ---")
    reports = parse_injury_long()
    ep_by_scope_washout = part_a(reports)

    log("\n--- Part B: onset-days and risk set (new estimand) ---")
    base_pd = pd.read_csv(BASE_FILE, parse_dates=["date"], low_memory=False)
    log(f"Player-day base: {base_pd.shape[0]} rows x {base_pd.shape[1]} cols; "
        f"players={base_pd['player_id'].nunique()}; "
        f"dates {base_pd['date'].min().date()} .. {base_pd['date'].max().date()}")
    rs, od, dist = part_b(base_pd, ep_by_scope_washout)

    log("\n--- Part C: modeling dataset ---")
    ll7 = ep_by_scope_washout[("lower_limb", PRIMARY_WASHOUT)]
    model = part_c(base_pd, rs, ll7)

    log("\n--- Part D: comparison vs frozen derived episodes ---")
    cmp_stats = part_d(ll7)

    log("\n--- Audit documents ---")
    write_audit_md(ep_by_scope_washout, od, rs, dist, model, cmp_stats)
    write_risk_set_md()

    log("\nDone.")


if __name__ == "__main__":
    sys.exit(main())
