# Section 9.3 — Acute vs chronic collinearity (Reviewer 4 concern #5)
# SoccerMon R2 reproducibility freeze. Writes ONLY under FR/07_COLLINEARITY and FR/18_LOGS.
import os, sys
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

FR = "D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE"
IN_CSV = f"{FR}/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/modeling_dataset.csv"
OUT_DIR = f"{FR}/07_COLLINEARITY"
OUT_CSV = f"{OUT_DIR}/ACUTE_CHRONIC_COLLINEARITY.csv"
LOG = f"{FR}/18_LOGS/workstream_collinearity.log"
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(f"{FR}/18_LOGS", exist_ok=True)

ACUTE = "acute_load_7d_wp_z"
CHRONIC = "chronic_load_28d_wp_z"
CC_BASE = [ACUTE, CHRONIC, "prev_episode_ever", "calendar_time", "team", "season"]

rows = []
def add(section, sample, metric, value, detail, notes):
    rows.append(dict(section=section, sample=sample, metric=metric, value=value,
                     detail=detail, taxonomy="R2_REVIEWER_REQUESTED", notes=notes))

def fisher_ci(r, n):
    z = np.arctanh(r)
    se = 1.0 / np.sqrt(n - 3)
    lo, hi = np.tanh(z - 1.959964 * se), np.tanh(z + 1.959964 * se)
    return lo, hi

def pair_stats(df, sample_label, section):
    a, c = df[ACUTE].to_numpy(), df[CHRONIC].to_numpy()
    n = len(df)
    r, p_r = stats.pearsonr(a, c)
    lo, hi = fisher_ci(r, n)
    rho, p_rho = stats.spearmanr(a, c)
    add(section, sample_label, "n_complete_cases", n, "rows",
        "CC = non-missing on acute, chronic, wellness variant, prev_episode_ever, calendar_time, team, season")
    add(section, sample_label, "pearson_r", round(float(r), 4),
        f"95% CI [{lo:.4f}, {hi:.4f}] (Fisher z); p={p_r:.3e}", "acute_load_7d_wp_z vs chronic_load_28d_wp_z")
    add(section, sample_label, "spearman_rho", round(float(rho), 4), f"p={p_rho:.3e}",
        "rank correlation, same pair")
    return r, n

# ---------------- load ----------------
df = pd.read_csv(IN_CSV)
n_all = len(df)
assert n_all == 36296, f"row count mismatch: {n_all}"

def cc_sample(wellness_col):
    cols = CC_BASE + [wellness_col]
    return df.dropna(subset=cols).copy()

cc_sor = cc_sample("soreness_burden_recent3_wp_z")
cc_fat = cc_sample("fatigue_burden_recent3_wp_z")
cc_rea = cc_sample("readiness_deficit_recent3_wp_z")

# ---------------- 1. primary soreness CC pairwise ----------------
r_sor, n_sor = pair_stats(cc_sor, "soreness_CC_primary", "9.3.1_pairwise_primary")
assert n_sor == 19758, f"soreness CC n mismatch: {n_sor}"

# ---------------- 5. QA fatigue / readiness pairwise ----------------
r_fat, n_fat = pair_stats(cc_fat, "fatigue_CC_QA", "9.3.5_pairwise_QA")
r_rea, n_rea = pair_stats(cc_rea, "readiness_CC_QA", "9.3.5_pairwise_QA")
assert n_fat == 19815, f"fatigue CC n mismatch: {n_fat}"
assert n_rea == 19817, f"readiness CC n mismatch: {n_rea}"

# ---------------- 2. two-predictor VIF ----------------
for lab, r, n in [("soreness_CC_primary", r_sor, n_sor),
                  ("fatigue_CC_QA", r_fat, n_fat),
                  ("readiness_CC_QA", r_rea, n_rea)]:
    vif2 = 1.0 / (1.0 - r**2)
    add("9.3.2_two_predictor_VIF", lab, "VIF_two_predictor", round(float(vif2), 4),
        f"1/(1-r^2), r={r:.4f}", "exact for a 2-regressor design; upper bound check for full VIF")

# ---------------- 3. full main-effects VIF (soreness CC) ----------------
def design_matrix(d, with_interaction):
    X = d[[ACUTE, CHRONIC, "soreness_burden_recent3_wp_z", "prev_episode_ever", "calendar_time"]].copy()
    X["prev_episode_ever"] = X["prev_episode_ever"].astype(float)
    if with_interaction:
        X["acute_x_chronic"] = X[ACUTE] * X[CHRONIC]
    dummies = pd.get_dummies(d[["team", "season"]], drop_first=True, dtype=float)
    X = pd.concat([X.reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)
    return X

def vif_table(X, tag):
    Xc = X - X.mean()  # center; intercept excluded from VIF
    out = {}
    for col in Xc.columns:
        y = Xc[col].to_numpy(dtype=float)
        Xo = Xc.drop(columns=[col]).to_numpy(dtype=float)
        r2 = sm.OLS(y, sm.add_constant(Xo)).fit().rsquared
        out[col] = 1.0 / (1.0 - r2)
    for col, v in out.items():
        add("9.3.3_full_design_VIF", "soreness_CC_primary", f"VIF[{col}]", round(float(v), 4),
            f"design={tag}", "auxiliary R^2 regression on remaining covariates; intercept excluded")
    mx = max(out.values())
    add("9.3.3_full_design_VIF", "soreness_CC_primary", f"max_VIF[{tag}]", round(float(mx), 4),
        f"variable={max(out, key=out.get)}", "max VIF across design matrix")
    return out

X_main = design_matrix(cc_sor, with_interaction=False)
X_int = design_matrix(cc_sor, with_interaction=True)
vif_main = vif_table(X_main, "main_effects_only")
vif_int = vif_table(X_int, "with_acute_x_chronic_interaction")

# ---------------- 4. condition number of scaled design matrix ----------------
def condition_stats(X, tag):
    M = X.to_numpy(dtype=float)
    # scaled: center + unit variance columns (scale = sd), intercept not included
    Ms = (M - M.mean(axis=0)) / M.std(axis=0, ddof=1)
    sv = np.linalg.svd(Ms, compute_uv=False)
    cn = sv[0] / sv[-1]
    cidx = sv[0] / sv  # condition indices per singular value
    add("9.3.4_condition_number", "soreness_CC_primary", f"condition_number[{tag}]",
        round(float(cn), 3), "scaled (centered, unit-sd) design matrix, intercept excluded",
        f"largest condition index = kappa; singular values min={sv[-1]:.4f} max={sv[0]:.4f}")
    add("9.3.4_condition_number", "soreness_CC_primary", f"max_condition_index[{tag}]",
        round(float(cidx.max()), 3), f"n_singular_values={len(sv)}",
        "internal QA row; kappa>30 would indicate serious collinearity")
    return cn

cn_main = condition_stats(X_main, "main_effects_only")
cn_int = condition_stats(X_int, "with_interaction")

# ---------------- 6. partial / within-player demeaned correlation ----------------
def within_corr(d, sample_label):
    tmp = d[["player_id", ACUTE, CHRONIC]].copy()
    tmp["a_dm"] = tmp[ACUTE] - tmp.groupby("player_id")[ACUTE].transform("mean")
    tmp["c_dm"] = tmp[CHRONIC] - tmp.groupby("player_id")[CHRONIC].transform("mean")
    r_w, p_w = stats.pearsonr(tmp["a_dm"], tmp["c_dm"])
    n_pl = tmp["player_id"].nunique()
    add("9.3.6_within_player_partial", sample_label, "within_player_demeaned_r",
        round(float(r_w), 4), f"n_players={n_pl}; p={p_w:.3e}",
        "correlation after removing player means; residual variation is within-player (structural window overlap)")
    # between-player component: correlation of player means
    pm = tmp.groupby("player_id")[[ACUTE, CHRONIC]].mean()
    r_b, p_b = stats.pearsonr(pm[ACUTE], pm[CHRONIC])
    add("9.3.6_within_player_partial", sample_label, "between_player_means_r",
        round(float(r_b), 4), f"n_players={n_pl}; p={p_b:.3e}",
        "correlation of player-level means (between-player component); near 0 expected for within-player z-scores")
    return r_w, r_b

r_within, r_between = within_corr(cc_sor, "soreness_CC_primary")

# ---------------- 8. derived non-overlap remainder check (raw lags) ----------------
sub = df.loc[cc_sor.index, ["acute_load_7d_lag", "chronic_load_28d_lag"]].dropna()
rem = (28.0 * sub["chronic_load_28d_lag"] - 7.0 * sub["acute_load_7d_lag"]) / 21.0
r_rem, p_rem = stats.pearsonr(sub["acute_load_7d_lag"], rem)
rho_rem, p_rho_rem = stats.spearmanr(sub["acute_load_7d_lag"], rem)
lo, hi = fisher_ci(r_rem, len(sub))
add("9.3.8_nonoverlap_remainder_check", "soreness_CC_primary_raw_lags", "pearson_r_acute_vs_remainder",
    round(float(r_rem), 4), f"95% CI [{lo:.4f}, {hi:.4f}]; n={len(sub)}; p={p_rem:.3e}",
    "derived check: remainder = (28*chronic_load_28d_lag - 7*acute_load_7d_lag)/21 = mean load t-28..t-8 (non-overlapping)")
add("9.3.8_nonoverlap_remainder_check", "soreness_CC_primary_raw_lags", "spearman_rho_acute_vs_remainder",
    round(float(rho_rem), 4), f"n={len(sub)}; p={p_rho_rem:.3e}",
    "derived check, rank version")

# ---------------- 7. plots ----------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(7, 6))
rng = np.random.default_rng(42)
idx = rng.choice(len(cc_sor), size=min(8000, len(cc_sor)), replace=False)
a = cc_sor[ACUTE].to_numpy(); c = cc_sor[CHRONIC].to_numpy()
ax.scatter(a[idx], c[idx], s=4, alpha=0.25, color="steelblue", rasterized=True)
xs = np.linspace(a.min(), a.max(), 100)
b1, b0 = np.polyfit(a, c, 1)
ax.plot(xs, b1 * xs + b0, color="darkred", lw=2, label=f"OLS fit (slope={b1:.3f})")
ax.set_xlabel("Acute load, 7-day within-player z (t-7..t-1)")
ax.set_ylabel("Chronic load, 28-day within-player z (t-28..t-1)")
ax.set_title(f"Acute vs chronic load — soreness complete cases (n={n_sor:,})\n"
             f"Pearson r = {r_sor:.3f}")
ax.legend()
fig.tight_layout()
fig.savefig(f"{OUT_DIR}/scatter_acute_vs_chronic_soreness_CC.png", dpi=200)
plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 5))
labels = [k for k in vif_main.keys()]
vals = [vif_main[k] for k in labels]
colors = ["darkred" if k in (ACUTE, CHRONIC) else "steelblue" for k in labels]
ax.bar(range(len(vals)), vals, color=colors)
ax.axhline(5, ls="--", color="gray", lw=1, label="VIF = 5")
ax.axhline(10, ls=":", color="black", lw=1, label="VIF = 10")
ax.set_xticks(range(len(labels)))
ax.set_xticklabels([l.replace("_wp_z", "").replace("_", "\n") for l in labels], fontsize=7)
ax.set_ylabel("Variance inflation factor")
ax.set_title(f"VIF — full main-effects design matrix, soreness CC (n={n_sor:,}); max VIF = {max(vals):.2f}")
ax.legend()
fig.tight_layout()
fig.savefig(f"{OUT_DIR}/vif_bar_main_effects_soreness_CC.png", dpi=200)
plt.close(fig)

# ---------------- write outputs ----------------
out = pd.DataFrame(rows, columns=["section", "sample", "metric", "value", "detail", "taxonomy", "notes"])
out.to_csv(OUT_CSV, index=False)

summary_lines = [
    f"[section 9.3 collinearity] run complete",
    f"input: {IN_CSV} (n={n_all})",
    f"soreness CC n={n_sor} (expected 19,758); fatigue CC n={n_fat} (expected 19,815); readiness CC n={n_rea} (expected 19,817)",
    f"soreness CC: Pearson r={r_sor:.4f}, two-predictor VIF={1/(1-r_sor**2):.4f}",
    f"full main-effects design: max VIF={max(vif_main.values()):.4f} ({max(vif_main, key=vif_main.get)}); "
    f"with interaction max VIF={max(vif_int.values()):.4f} ({max(vif_int, key=vif_int.get)})",
    f"condition number (scaled): main={cn_main:.2f}, with_interaction={cn_int:.2f}",
    f"within-player demeaned r={r_within:.4f}; between-player means r={r_between:.4f}",
    f"acute vs non-overlap remainder (t-28..t-8, raw): Pearson r={r_rem:.4f} (n={len(sub)})",
    f"outputs: {OUT_CSV}; scatter_acute_vs_chronic_soreness_CC.png; vif_bar_main_effects_soreness_CC.png",
]
with open(LOG, "a", encoding="utf-8") as f:
    f.write("\n".join(summary_lines) + "\n\n")

print("\n".join(summary_lines))
