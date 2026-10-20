# -*- coding: utf-8 -*-
# 06b_make_figures.py — Fig1/2/3 + S1_Fig（PNG 300dpi + 数据 csv），数字全部来自结构化结果源
import os, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WS = r"D:/PLOS_ONE_R1_WORK/PONE-D-26-31950_PLOS_R1"
RUN = os.path.join(WS, "07_ANALYSIS_OUTPUTS", "RUN_20260722_151418")
FIG = os.path.join(WS, "10_FIGURES")
os.makedirs(FIG, exist_ok=True)

mr = pd.read_csv(os.path.join(RUN, "master_results.csv"))
onset = pd.read_csv(os.path.join(WS, "07_ANALYSIS_OUTPUTS", "onset_day_inventory.csv"))
ped = pd.read_csv(os.path.join(WS, "07_ANALYSIS_OUTPUTS", "player_event_distribution.csv"))
md = pd.read_csv(os.path.join(WS, "07_ANALYSIS_OUTPUTS", "modeling_dataset.csv"))

# ---------- Fig 1: onset timeline ----------
o = onset[(onset["washout"] == 7) & (onset["scope"] == "lower_limb")] if "washout" in onset.columns else onset.copy()
if "scope" in o.columns:
    o = o[o["scope"] == "lower_limb"]
o["date"] = pd.to_datetime(o["date"])
team_map = md.groupby("player_id")["team"].first()
o["team"] = o["player_id"].map(team_map)
players = sorted(o["player_id"].unique())
y = {p: i for i, p in enumerate(players)}
fig, ax = plt.subplots(figsize=(9, 4.5))
for team, mk, c in (("TeamA", "o", "#2166ac"), ("TeamB", "s", "#b2182b")):
    sub = o[o["team"] == team]
    ax.scatter(sub["date"], [y[p] for p in sub["player_id"]], marker=mk, c=c, s=28, label=team, alpha=.85)
ax.set_yticks(list(y.values())); ax.set_yticklabels([f"player {i+1}" for i in range(len(players))], fontsize=6)
ax.set_xlabel("Date"); ax.set_ylabel("Player (event players only)")
ax.set_title("Unique lower-limb onset-days (7-day washout); same-day multi-location onsets merged")
ax.legend()
fig.tight_layout(); fig.savefig(os.path.join(FIG, "Fig1.png"), dpi=300); plt.close(fig)
o[["player_id", "date", "team"]].to_csv(os.path.join(FIG, "Fig1_data.csv"), index=False)

# ---------- Fig 2: concentration ----------
pe = ped[ped["episodes_7d_ll"] > 0] if "episodes_7d_ll" in ped.columns else ped[ped.iloc[:, 1] > 0]
col = "episodes_7d_ll" if "episodes_7d_ll" in ped.columns else ped.columns[1]
pe = pe.sort_values(col, ascending=False)
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(range(len(pe)), pe[col], color="#4393c3")
ax.set_xticks(range(len(pe))); ax.set_xticklabels([f"P{i+1}" for i in range(len(pe))], fontsize=8)
ax.set_xlabel("Player (anonymised, sorted)"); ax.set_ylabel("Lower-limb body-location episodes")
ax.set_title("Episode concentration among the 15 event players (7-day washout)")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "Fig2.png"), dpi=300); plt.close(fig)
pe.to_csv(os.path.join(FIG, "Fig2_data.csv"), index=False)

# ---------- Fig 3: conditional predicted probability (Firth 系数) ----------
f = mr[(mr["model_id"] == "F") & (mr["wellness_variant"] == "soreness")].set_index("term")
def beta(t):
    return np.log(f.loc[t, "OR"])
b0 = beta("(Intercept)")
bA = beta("acute_load_7d_wp_z")
bS = beta("soreness_burden_recent3_wp_z")
bI = [t for t in f.index if ":" in t][0]
bInt = beta(bI)
# 条件化：其余协变量固定于参考/均值。z 变量均值为 0、prev_episode_ever=0、team=TeamA、season=2020 均无贡献；
# calendar_time 为未标准化天数，必须固定于 complete-case 均值，否则概率被系统性高估。
b_cal = beta("calendar_time")
cc_vars = ["onset_day", "acute_load_7d_wp_z", "soreness_burden_recent3_wp_z", "chronic_load_28d_wp_z",
           "prev_episode_ever", "calendar_time", "team", "season"]
cc = md.dropna(subset=[c for c in cc_vars if c in md.columns])
mean_cal = float(cc["calendar_time"].mean())
offset = b_cal * mean_cal
print(f"Fig3: calendar_time fixed at CC mean {mean_cal:.1f}, logit offset {offset:.2f}")
x = np.linspace(-2, 2, 121)
fig, ax = plt.subplots(figsize=(7, 4.5))
for s, c, lab in [(-1, "#2166ac", "soreness burden -1 SD (less sore than usual)"),
                  (0, "#7f7f7f", "soreness burden mean"),
                  (1, "#b2182b", "soreness burden +1 SD (sorer than usual)")]:
    logit = b0 + offset + bA * x + bS * s + bInt * x * s
    p = 1 / (1 + np.exp(-logit))
    ax.plot(x, p * 100, color=c, label=lab)
ax.set_xlabel("Within-player acute load deviation (z, lagged 7-day)")
ax.set_ylabel("Conditional onset probability (%)")
ax.set_title("Acute load × soreness burden interaction (Firth model, conditional)")
ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "Fig3.png"), dpi=300); plt.close(fig)
pd.DataFrame({"acute_z": x}).to_csv(os.path.join(FIG, "Fig3_data.csv"), index=False)
with open(os.path.join(FIG, "Fig3_params.json"), "w") as fh:
    json.dump({"intercept": b0, "acute": bA, "soreness": bS, "interaction": bInt, "term": bI,
               "calendar_time_coef": b_cal, "calendar_time_fixed_at_cc_mean": mean_cal, "logit_offset": offset,
               "note": "conditional logits; z-covariates at 0, prev_episode_ever=0, team=TeamA, season=2020; burden coding higher=worse"}, fh, indent=1)

# ---------- S1_Fig: 交互森林图 ----------
sel = []
for role, model, lab in [("SMALL_SAMPLE_SENSITIVITY", "F", "Firth (F)"),
                         ("SMALL_SAMPLE_SENSITIVITY", "F_boot", "Firth bootstrap"),
                         ("PRIMARY_BOOTSTRAP", "A_boot", "Marginal bootstrap (A_boot)"),
                         ("KEY_SENSITIVITY", "B", "Andersen-Gill (B)"),
                         ("SENSITIVITY", "C", "PWP total-time (C)"),
                         ("SENSITIVITY", "D", "PWP gap-time (D)"),
                         ("SENSITIVITY", "E", "Shared frailty (E)"),
                         ("SENSITIVITY_IPW", "IPW", "IPW-weighted"),
                         ("SENSITIVITY", "S1_washout3d", "Washout 3-day (GLMM)")]:
    q = mr[(mr["analysis_role"] == role) & (mr["model_id"] == model) &
           (mr["wellness_variant"] == "soreness") & (mr["term"].astype(str).str.contains(":"))]
    if len(q):
        r = q.iloc[0]
        sel.append((lab, r["OR"], r["CI_low"], r["CI_high"]))
fig, ax = plt.subplots(figsize=(7, 4.5))
ys = list(range(len(sel)))[::-1]
for yi, (lab, orv, lo, hi) in zip(ys, sel):
    ax.errorbar(orv, yi, xerr=[[orv - lo], [hi - orv]], fmt="o", color="#2166ac", capsize=3)
ax.axvline(1.0, color="k", ls="--", lw=1)
ax.set_yticks(ys); ax.set_yticklabels([s[0] for s in sel], fontsize=8)
ax.set_xlabel("Interaction odds ratio (acute load × soreness burden), log scale")
ax.set_xscale("log")
ax.set_title("Primary interaction across estimators")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "S1_Fig.png"), dpi=300); plt.close(fig)
pd.DataFrame(sel, columns=["estimator", "OR", "CI_low", "CI_high"]).to_csv(os.path.join(FIG, "S1_Fig_data.csv"), index=False)

print("figures:", os.listdir(FIG))
print("DONE")
