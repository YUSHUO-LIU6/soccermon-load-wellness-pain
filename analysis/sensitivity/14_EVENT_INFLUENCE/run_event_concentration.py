#!/usr/bin/env python3
"""
run_event_concentration.py — R2 freeze plan section 9.10 (Python side)
PONE-D-26-31950 (SoccerMon) R2 reproducibility freeze.

1) EVENT_CONCENTRATION.csv — per event player: event count, % of events,
   cumulative %, team, season(s); both scopes (risk-set 42 onset-days,
   soreness-CC 28 onset-days).
2) Verify the R1 'exclude highest contributor' (S5) sensitivity inputs:
   R1 defined the highest contributor by lower-limb episode count
   (player_event_distribution.csv ll_episodes_7d = 45 ->
   TeamA-4051bba7-1170-4c43-b912-8c38815a7625), NOT by risk-set onset-day
   share. Check that the S5 rows in master_results.csv used exactly that
   exclusion (n, players, events arithmetic against the soreness CC sample).
3) Forest-style plot of leave-one-out interaction ORs (reads
   LEAVE_ONE_EVENT_PLAYER_OUT_QA.csv written by run_leave_one_out_qa.R;
   internal QA, English labels).

Taxonomy: R2_INTERNAL_QA_ONLY. Seed 20260722 (no stochastic steps).
"""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

SEED = 20260722
TAXONOMY = "R2_INTERNAL_QA_ONLY"
HIGH_PLAYER = "TeamA-4051bba7-1170-4c43-b912-8c38815a7625"

FR = Path(r"D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE")
SB = FR / "02_R1_REPRODUCTION" / "r1_sandbox"
RUN = SB / "07_ANALYSIS_OUTPUTS" / "RUN_R2_REPRO"
OUTDIR = FR / "14_EVENT_INFLUENCE"
OUTDIR.mkdir(parents=True, exist_ok=True)

WCOL = "soreness_burden_recent3_wp_z"
CC_BASE = ["onset_day", "acute_load_7d_wp_z", WCOL, "chronic_load_28d_wp_z",
           "prev_episode_ever", "calendar_time", "team", "season",
           "player_id", "date", "prev_episode_count"]

md = pd.read_csv(SB / "07_ANALYSIS_OUTPUTS" / "modeling_dataset.csv")
ped = pd.read_csv(SB / "07_ANALYSIS_OUTPUTS" / "player_event_distribution.csv")
master = pd.read_csv(RUN / "master_results.csv")
cc = md.dropna(subset=CC_BASE)

SAFEGUARD = ("28 CC onset-days / 9 event players = severe information limit; "
             "multiple estimators share the same events; TeamB contributes 0 "
             "CC events so the team coefficient is degenerate (separation); "
             "nominal p<0.05 must never be called robust.")

# ---------------------------------------------------------------- 1) table --
scopes = {"risk_set_42": md, "soreness_cc_28": cc}
rows = []
for scope, d in scopes.items():
    ons = d[d["onset_day"] == 1]
    tot = len(ons)
    seasons_of = ons.groupby("player_id")["season"].apply(
        lambda s: ";".join(str(x) for x in sorted(s.unique())))
    cnt = ons.groupby("player_id").size().sort_values(ascending=False)
    team_of = md.groupby("player_id")["team"].first()
    cum = cnt.cumsum() / tot * 100
    for rank, (pid, e) in enumerate(cnt.items(), start=1):
        rows.append({
            "taxonomy": TAXONOMY,
            "scope": scope,
            "player_id": pid,
            "team": team_of[pid],
            "seasons_of_events": seasons_of[pid],
            "events": int(e),
            "pct_of_scope_events": round(e / tot * 100, 2),
            "cumulative_pct": round(cum[pid], 2),
            "event_rank_in_scope": rank,
            "ll_episodes_7d": int(ped.set_index("player_id")
                                  .loc[pid, "ll_episodes_7d"]),
            "notes": SAFEGUARD if rank == 1 else "",
        })
conc = pd.DataFrame(rows)
conc.to_csv(OUTDIR / "EVENT_CONCENTRATION.csv", index=False)

# ------------------------------------------------------- 2) S5 verification --
ped_i = ped.set_index("player_id")
top_by_episodes = ped_i["ll_episodes_7d"].idxmax()
n_epi = int(ped_i["ll_episodes_7d"].max())
top_by_onset_risk = md[md.onset_day == 1].groupby("player_id").size().idxmax()

hi = {
    "r1_definition": "ll_episodes_7d (lower-limb episode count, 7d washout)",
    "r1_highest_contributor": top_by_episodes,
    "r1_highest_contributor_episodes": n_epi,
    "expected_player": HIGH_PLAYER,
    "matches_expectation": bool(top_by_episodes == HIGH_PLAYER),
    "risk_set_onset_days": int(md[(md.player_id == HIGH_PLAYER)
                                  & (md.onset_day == 1)].shape[0]),
    "risk_set_onset_share_pct": round(
        md[(md.player_id == HIGH_PLAYER) & (md.onset_day == 1)].shape[0]
        / md.onset_day.sum() * 100, 2),
    "soreness_cc_onset_days": int(cc[(cc.player_id == HIGH_PLAYER)
                                     & (cc.onset_day == 1)].shape[0]),
    "soreness_cc_onset_share_pct": round(
        cc[(cc.player_id == HIGH_PLAYER) & (cc.onset_day == 1)].shape[0]
        / cc.onset_day.sum() * 100, 2),
    "top_by_risk_set_onset_days": top_by_onset_risk,
}

# S5 rows in master_results: n / players / events must equal CC minus player
s5 = master[master.model_id == "S5_exclude_high_contributor"].iloc[0]
cc_x = cc[cc.player_id != HIGH_PLAYER]
checks = {
    "s5_n_matches": int(s5["n"]) == len(cc_x),
    "s5_players_matches": int(s5["players"]) == cc_x.player_id.nunique(),
    "s5_events_matches": int(s5["events"]) == int(cc_x.onset_day.sum()),
    "s5_n": int(s5["n"]), "cc_minus_player_n": len(cc_x),
    "s5_events": int(s5["events"]),
    "cc_minus_player_events": int(cc_x.onset_day.sum()),
}
verif = {**hi, **checks}
verif["definition_discrepancy_note"] = (
    "R1 S5 'highest contributor' is defined by lower-limb EPISODE count "
    f"({n_epi} episodes); by risk-set ONSET-DAY share the top contributor is "
    f"{top_by_onset_risk} (11/42 = 26.2%) and {HIGH_PLAYER} ranks 2nd "
    "(7/42 = 16.7%). In the soreness CC scope both players tie at 6/28 "
    "= 21.4%. The R1 exclusion is reproduced exactly as registered; this "
    "note documents the definition dependency.")
verif["safeguards"] = SAFEGUARD
pd.DataFrame([verif]).to_csv(OUTDIR / "S5_EXCLUSION_VERIFICATION.csv",
                             index=False)
print("S5 verification:", checks, "| top by episodes:",
      top_by_episodes == HIGH_PLAYER)

# ------------------------------------------------------------ 3) forest ----
loo_path = OUTDIR / "LEAVE_ONE_EVENT_PLAYER_OUT_QA.csv"
if not loo_path.exists():
    print("LOO csv not found yet — run run_leave_one_out_qa.R first, then "
          "re-run with --plot-only", file=sys.stderr)
    sys.exit(2)

loo = pd.read_csv(loo_path)
iterm = f"acute_load_7d_wp_z:{WCOL}"
fx = loo[(loo.model == "firth_full") & (loo.term == iterm)].copy()
fx = fx.sort_values("OR").reset_index(drop=True)
ref = master[(master.model_id == "F") &
             (master.wellness_variant == "soreness") &
             (master.term == iterm)].iloc[0]

labels = [p.replace("TeamA-", "A-").replace("TeamB-", "B-")[:12] + "…"
          for p in fx.excluded_player]
xp_events = cc[cc.onset_day == 1].groupby("player_id").size()
labels = [f"minus {l} ({int(xp_events[p])} ev)" for l, p in
          zip(labels, fx.excluded_player)]

fig, ax = plt.subplots(figsize=(7.2, 4.6))
y = np.arange(len(fx)) + 1
ax.errorbar(fx.OR, y,
            xerr=[fx.OR - fx.CI_low, fx.CI_high - fx.OR],
            fmt="o", color="#1f77b4", ecolor="#1f77b4", capsize=3, ms=5)
ax.errorbar([ref.OR], [0],
            xerr=[[ref.OR - ref.CI_low], [ref.CI_high - ref.OR]],
            fmt="s", color="#d62728", ecolor="#d62728", capsize=3, ms=6)
ax.axvline(1.0, color="grey", lw=0.8, ls="--")
ax.set_yticks([0] + list(y))
ax.set_yticklabels([f"Full sample (Firth, 28 events)"] + labels, fontsize=8)
ax.set_xscale("log")
ax.set_xlabel("OR, acute x soreness interaction\n(log scale; profile-likelihood 95% CI)", fontsize=9)
ax.set_title("Leave-one-event-player-out QA — Firth interaction OR\n"
             "(soreness CC sample; R2_INTERNAL_QA_ONLY)", fontsize=9)
ax.set_ylim(-0.7, len(fx) + 0.7)
fig.tight_layout()
fig.savefig(OUTDIR / "LOO_FIRTH_INTERACTION_FOREST.png", dpi=200)
print("wrote forest plot")
print(fx[["excluded_player", "OR", "CI_low", "CI_high", "p",
          "pct_change_OR"]].to_string(index=False))
