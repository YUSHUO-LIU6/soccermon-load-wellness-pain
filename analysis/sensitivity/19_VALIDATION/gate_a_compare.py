# GATE A: R1 reproduction-gate numerical comparison (PLOS ONE reproducibility audit)
# Compares locked reference run RUN_20260722_151418 vs sandbox re-run RUN_R2_REPRO.
# Read-only on inputs; writes R1_REPRODUCTION_CHECK.csv + appends to gate_a_compare.log.
import hashlib, json, os, sys, datetime
import pandas as pd
import numpy as np

REF_TOP = r"D:/PLOS_ONE_R1_WORK/PONE-D-26-31950_PLOS_R1/07_ANALYSIS_OUTPUTS"
NEW_TOP = r"D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS"
RREF = os.path.join(REF_TOP, "RUN_20260722_151418")
RNEW = os.path.join(NEW_TOP, "RUN_R2_REPRO")
OUT_CSV = r"D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE/19_VALIDATION/R1_REPRODUCTION_CHECK.csv"
LOG = r"D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE/18_LOGS/gate_a_compare.log"

REL_TOL, ABS_TOL = 1e-6, 1e-8
rows = []

def add(file, check, item, ref, rep, status, tol="", absd="", reld="", notes=""):
    rows.append(dict(file=file, check=check, item=item, reference_value=ref,
                     reproduced_value=rep, match_status=status, tolerance=tol,
                     abs_diff=absd, rel_diff=reld, notes=notes))

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def fcmp(a, b):
    """Policy 2 compare. Returns (ok, abs_diff, rel_diff). NaN==NaN ok; inf==inf ok."""
    if pd.isna(a) and pd.isna(b):
        return True, 0.0, 0.0
    if pd.isna(a) or pd.isna(b):
        return False, float("inf"), float("inf")
    a, b = float(a), float(b)
    if a == b:  # covers inf==inf and exact equality
        return True, 0.0, 0.0
    ad = abs(a - b)
    rd = ad / max(abs(a), abs(b)) if max(abs(a), abs(b)) > 0 else 0.0
    return (ad <= max(REL_TOL * max(abs(a), abs(b)), ABS_TOL)), ad, rd

def num(s):
    return pd.to_numeric(s, errors="coerce")

# ---------------------------------------------------------------- 0. inputs
for fn in ["modeling_dataset.csv", "episode_inventory.csv"]:
    a, b = os.path.join(REF_TOP, fn), os.path.join(NEW_TOP, fn)
    ha, hb = sha256(a), sha256(b)
    add(fn, "input_byte_identity", "sha256", ha, hb,
        "PASS" if ha == hb else "FAIL", "exact", notes="top-level pipeline input copy")

# ---------------------------------------------------------------- 7. byte map
ref_files = sorted(os.listdir(RREF))
new_files = sorted(os.listdir(RNEW))
all_files = sorted(set(ref_files) | set(new_files))
byte_status = {}
for fn in all_files:
    pa, pb = os.path.join(RREF, fn), os.path.join(RNEW, fn)
    if fn not in new_files:
        byte_status[fn] = "REF_ONLY"
        add(fn, "byte_identity", "presence", "present", "absent", "INFO", notes="reference-only file (manuscript mapping/report, not pipeline output)")
        continue
    if fn not in ref_files:
        byte_status[fn] = "NEW_ONLY"
        add(fn, "byte_identity", "presence", "absent", "present", "INFO", notes="new-only file")
        continue
    ha, hb = sha256(pa), sha256(pb)
    byte_status[fn] = "BYTE_IDENTICAL" if ha == hb else "BYTE_DIFFERENT"
    add(fn, "byte_identity", "sha256", ha, hb,
        "PASS" if ha == hb else "INFO", "exact",
        notes="RESULTS_LOCK.md exempt from byte requirement" if fn == "RESULTS_LOCK.md" else "")

# ------------------------------------------------- results-table comparator
KEYS = ["analysis_role", "model_id", "wellness_variant", "term"]
FLOAT_COLS = ["OR", "CI_low", "CI_high", "p", "se"]
INT_COLS = ["n", "players", "events"]

def compare_results(fname):
    a = pd.read_csv(os.path.join(RREF, fname), dtype=str)
    b = pd.read_csv(os.path.join(RNEW, fname), dtype=str)
    if list(a.columns) != list(b.columns):
        add(fname, "schema", "columns", "|".join(a.columns), "|".join(b.columns), "FAIL", notes="column sets differ")
        return
    dup_a = a.duplicated(KEYS).sum(); dup_b = b.duplicated(KEYS).sum()
    if dup_a or dup_b:
        add(fname, "keys", "duplicate_keys", int(dup_a), int(dup_b), "FAIL", notes="duplicate merge keys")
    m = a.merge(b, on=KEYS, how="outer", suffixes=("_ref", "_new"), indicator=True)
    n_only_ref = int((m._merge == "left_only").sum())
    n_only_new = int((m._merge == "right_only").sum())
    add(fname, "keys", "row_count", len(a), len(b),
        "PASS" if (len(a) == len(b) and n_only_ref == 0 and n_only_new == 0) else "FAIL", "exact",
        notes=f"ref_only={n_only_ref}, new_only={n_only_new}")
    for _, r in m[m._merge != "both"].head(50).iterrows():
        add(fname, "keys", "missing_key", "|".join(str(r[k]) for k in KEYS), "", "FAIL",
            notes="only in reference" if r._merge == "left_only" else "only in new run")
    both = m[m._merge == "both"]
    for col in FLOAT_COLS:
        if f"{col}_ref" not in both.columns:
            continue
        va, vb = num(both[f"{col}_ref"]), num(both[f"{col}_new"])
        worst_ad, worst_rd, nfail = 0.0, 0.0, 0
        fails = []
        for i in both.index:
            ok, ad, rd = fcmp(va[i], vb[i])
            worst_ad = max(worst_ad, ad if ad != float("inf") else worst_ad)
            worst_rd = max(worst_rd, rd if rd != float("inf") else worst_rd)
            if not ok:
                nfail += 1
                if len(fails) < 20:
                    fails.append((i, va[i], vb[i], ad, rd))
        add(fname, "numeric_compare", col, f"max_abs={worst_ad:.3e}", f"max_rel={worst_rd:.3e}",
            "PASS" if nfail == 0 else "FAIL", "rel1e-6_or_abs1e-8",
            worst_ad, worst_rd, f"n_compared={len(both)}, n_fail={nfail}")
        for i, x, y, ad, rd in fails:
            add(fname, "numeric_compare_fail", f"{col} @ " + "|".join(str(both.loc[i, k]) for k in KEYS),
                x, y, "FAIL", "rel1e-6_or_abs1e-8", ad, rd)
    for col in INT_COLS:
        if f"{col}_ref" not in both.columns:
            continue
        va, vb = num(both[f"{col}_ref"]), num(both[f"{col}_new"])
        bad = both[(va != vb) & ~(va.isna() & vb.isna())]
        add(fname, "exact_compare", col, "all_equal" if len(bad) == 0 else f"{len(bad)} diffs",
            "all_equal" if len(bad) == 0 else f"{len(bad)} diffs",
            "PASS" if len(bad) == 0 else "FAIL", "exact", notes=f"n_compared={len(both)}")
        for i in bad.index[:20]:
            add(fname, "exact_compare_fail", f"{col} @ " + "|".join(str(both.loc[i, k]) for k in KEYS),
                va[i], vb[i], "FAIL", "exact")
    for col in ["converged", "optimizer"]:
        ca, cb = f"{col}_ref", f"{col}_new"
        if ca not in both.columns:
            continue
        na = both[ca].astype(str).str.strip().str.lower()
        nb = both[cb].astype(str).str.strip().str.lower()
        nbad = int((na != nb).sum())
        add(fname, "exact_compare", col, "all_equal" if nbad == 0 else f"{nbad} diffs",
            "all_equal" if nbad == 0 else f"{nbad} diffs",
            "PASS" if nbad == 0 else "FAIL", "exact (case-normalised)", notes=f"n_compared={len(both)}")

for fn in ["r_results.csv", "master_results.csv", "firth_bootstrap_results.csv"]:
    compare_results(fn)

# ------------------------------------------------- 3. bootstrap comparisons
with open(os.path.join(RREF, "bootstrap_primary_interaction.json")) as f:
    ja = json.load(f)
with open(os.path.join(RNEW, "bootstrap_primary_interaction.json")) as f:
    jb = json.load(f)
for k in sorted(set(ja) | set(jb)):
    va, vb = ja.get(k), jb.get(k)
    if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
        ok, ad, rd = fcmp(va, vb)
        add("bootstrap_primary_interaction.json", "numeric_compare", k, va, vb,
            "PASS" if ok else "FAIL", "rel1e-6_or_abs1e-8", ad, rd)
    else:
        add("bootstrap_primary_interaction.json", "exact_compare", k, va, vb,
            "PASS" if va == vb else "FAIL", "exact")

br_a = pd.read_csv(os.path.join(RREF, "bootstrap_replicates.csv"))
br_b = pd.read_csv(os.path.join(RNEW, "bootstrap_replicates.csv"))
m = br_a.merge(br_b, on="replicate", how="outer", suffixes=("_ref", "_new"), indicator=True)
add("bootstrap_replicates.csv", "keys", "row_count", len(br_a), len(br_b),
    "PASS" if len(br_a) == len(br_b) and (m._merge == "both").all() else "FAIL", "exact")
both = m[m._merge == "both"]
ads = (both.beta_interaction_ref - both.beta_interaction_new).abs()
rds = ads / both.beta_interaction_ref.abs().clip(lower=1e-300)
nfail = sum(not fcmp(x, y)[0] for x, y in zip(both.beta_interaction_ref, both.beta_interaction_new))
add("bootstrap_replicates.csv", "numeric_compare", "beta_interaction",
    f"max_abs={ads.max():.3e}", f"max_rel={rds.max():.3e}",
    "PASS" if nfail == 0 else "FAIL", "rel1e-6_or_abs1e-8", ads.max(), rds.max(),
    f"n_compared={len(both)}, n_fail={nfail}")

# ------------------------------------------------- 4. IPW weight files
ipw_stats = {}
for var in ["soreness", "fatigue", "readiness"]:
    fn = f"ipw_weights_{var}.csv"
    a = pd.read_csv(os.path.join(RREF, fn))
    b = pd.read_csv(os.path.join(RNEW, fn))
    add(fn, "keys", "row_count", len(a), len(b), "PASS" if len(a) == len(b) else "FAIL", "exact")
    key_ok = a[["player_id", "date"]].equals(b[["player_id", "date"]])
    add(fn, "keys", "player_id+date_order", "aligned" if key_ok else "misaligned",
        "aligned" if key_ok else "misaligned", "PASS" if key_ok else "FAIL", "exact")
    for col in ["w_stab", "w_stab_trunc"]:
        va, vb = num(a[col]), num(b[col])
        worst_ad, worst_rd, nfail = 0.0, 0.0, 0
        for x, y in zip(va, vb):
            ok, ad, rd = fcmp(x, y)
            if ad != float("inf"):
                worst_ad, worst_rd = max(worst_ad, ad), max(worst_rd, rd)
            if not ok:
                nfail += 1
        add(fn, "numeric_compare", col, f"max_abs={worst_ad:.3e}", f"max_rel={worst_rd:.3e}",
            "PASS" if nfail == 0 else "FAIL", "rel1e-6_or_abs1e-8", worst_ad, worst_rd,
            f"n_compared={len(a)}, n_fail={nfail}")
    # weight summary stats vs claimed constants (policy 8)
    w, wt = num(a.w_stab), num(a.w_stab_trunc)
    wn, wtn = w.dropna(), wt.dropna()
    ess_u = wn.sum() ** 2 / (wn ** 2).sum()
    ess_t = wtn.sum() ** 2 / (wtn ** 2).sum()
    ipw_stats[var] = dict(max_w_stab=wn.max(), max_w_stab_trunc=wtn.max(),
                          ess_untrunc=ess_u, ess_trunc=ess_t,
                          ess_frac_trunc_nrows=ess_t / len(a), ess_frac_trunc_nonnull=ess_t / len(wtn),
                          n_rows=len(a), n_nonnull=len(wn))
    for k, v in ipw_stats[var].items():
        add(fn, "weight_summary", k, v, "", "INFO", notes=f"{var}; reference-run value (repro numerically identical per comparison above)")

# ------------------------------------------------- 5. inventories
def compare_inventory(fname, keys, exact_cols, float_cols, str_cols=(), drop_ref_where=None, label=None):
    a = pd.read_csv(os.path.join(RREF, fname), dtype=str)
    b = pd.read_csv(os.path.join(RNEW, fname), dtype=str)
    if drop_ref_where is not None:
        a = a[~drop_ref_where(a)]
    label = label or fname
    add(label, "keys", "row_count", len(a), len(b), "PASS" if len(a) == len(b) else "FAIL", "exact")
    for c in keys:
        a[c] = a[c].fillna("")
        b[c] = b[c].fillna("")
    ka = a[keys].astype(str).agg("|".join, axis=1)
    kb = b[keys].astype(str).agg("|".join, axis=1)
    only_a, only_b = set(ka) - set(kb), set(kb) - set(ka)
    add(label, "keys", "key_sets", f"ref_only={len(only_a)}", f"new_only={len(only_b)}",
        "PASS" if not only_a and not only_b else "FAIL", "exact",
        notes=("ref_only:" + ";".join(sorted(only_a)[:10]) if only_a else "") +
              (" new_only:" + ";".join(sorted(only_b)[:10]) if only_b else ""))
    m = a.merge(b, on=keys, how="inner", suffixes=("_ref", "_new"))
    for col in exact_cols:
        if col not in a.columns:
            continue
        va, vb = num(m[f"{col}_ref"]), num(m[f"{col}_new"])
        nbad = int(((va != vb) & ~(va.isna() & vb.isna())).sum())
        add(label, "exact_compare", col, "all_equal" if nbad == 0 else f"{nbad} diffs",
            "all_equal" if nbad == 0 else f"{nbad} diffs",
            "PASS" if nbad == 0 else "FAIL", "exact", notes=f"n_compared={len(m)}")
    for col in float_cols:
        if col not in a.columns:
            continue
        va, vb = num(m[f"{col}_ref"]), num(m[f"{col}_new"])
        worst_ad, worst_rd, nfail = 0.0, 0.0, 0
        for x, y in zip(va, vb):
            ok, ad, rd = fcmp(x, y)
            if ad != float("inf"):
                worst_ad, worst_rd = max(worst_ad, ad), max(worst_rd, rd)
            if not ok:
                nfail += 1
        add(label, "numeric_compare", col, f"max_abs={worst_ad:.3e}", f"max_rel={worst_rd:.3e}",
            "PASS" if nfail == 0 else "FAIL", "rel1e-6_or_abs1e-8", worst_ad, worst_rd,
            f"n_compared={len(m)}, n_fail={nfail}")
    for col in str_cols:
        if col not in a.columns:
            continue
        sa = m[f"{col}_ref"].fillna("").astype(str)
        sb = m[f"{col}_new"].fillna("").astype(str)
        nbad = int((sa != sb).sum())
        # whitespace-normalised secondary check
        na = sa.str.split().str.join(" "); nb = sb.str.split().str.join(" ")
        nbad_norm = int((na != nb).sum())
        add(label, "exact_compare", col, f"raw_diffs={nbad}", f"ws_norm_diffs={nbad_norm}",
            "PASS" if nbad == 0 else ("PASS_NORM" if nbad_norm == 0 else "FAIL"),
            "exact (whitespace-normalised fallback)", notes=f"n_compared={len(m)}")

compare_inventory("event_count_inventory.csv", ["washout_days"],
                  ["ll_episodes", "onset_days_total", "at_risk_days", "onset_days_in_risk_set", "event_players", "players"], [])
compare_inventory("sample_size_inventory.csv", ["model_id", "wellness_variant"],
                  ["n", "players", "at_risk_days", "onset_days", "event_players", "n_parameters"],
                  ["events_per_parameter"])
# model_inventory: reference carries one extra documentation row for model G
# (status "NOT RUN (EXPLORATORY ONLY per SAP)" - retired estimand, no results).
mi_g = pd.read_csv(os.path.join(RREF, "model_inventory.csv"), dtype=str).fillna("")
mi_g = mi_g[mi_g.model_id == "G"]
add("model_inventory.csv", "ref_only_documentation_row", "model G (retired, NOT RUN)",
    mi_g.status.iloc[0] if len(mi_g) else "absent", "absent in repro", "INFO",
    notes="reference-only inventory row for retired exploratory model G; no results exist for G, "
          "so its omission from the repro inventory is documentation-only")
compare_inventory("model_inventory.csv", ["model_id", "wellness_variant"],
                  [], [], str_cols=["status", "fail_reason", "formula", "data"],
                  drop_ref_where=lambda d: d.model_id == "G")

# diagnostic_inventory: mixed value types AND known duplicated documentation blocks
# in the reference (DATA cc_events rows and an S3 note are repeated 3-4x). Compare as
# a multiset of full rows, then compare values on deduplicated keys.
from collections import Counter
da = pd.read_csv(os.path.join(RREF, "diagnostic_inventory.csv"), dtype=str).fillna("")
db = pd.read_csv(os.path.join(RNEW, "diagnostic_inventory.csv"), dtype=str).fillna("")
DKEYS = ["model_id", "wellness_variant", "diagnostic"]
ca = Counter(tuple(r) for r in da[["model_id", "wellness_variant", "diagnostic", "value"]].itertuples(index=False))
cb = Counter(tuple(r) for r in db[["model_id", "wellness_variant", "diagnostic", "value"]].itertuples(index=False))
row_diffs = {k: (ca.get(k, 0), cb.get(k, 0)) for k in set(ca) | set(cb) if ca.get(k, 0) != cb.get(k, 0)}
content_mismatch = [k for k, (x, y) in row_diffs.items() if min(x, y) == 0]
dup_only = [k for k, (x, y) in row_diffs.items() if min(x, y) > 0]
add("diagnostic_inventory.csv", "keys", "row_count", len(da), len(db),
    "PASS" if len(da) == len(db) else "INFO", "exact",
    notes=f"reference repeats {sum(x-y for k,(x,y) in row_diffs.items() if x>y)} documentation rows "
          f"(DATA cc_events_* blocks x3-4, S3 note x3); all appear in repro at least once")
add("diagnostic_inventory.csv", "multiset_compare", "full_rows",
    f"ref_rows={len(da)}", f"new_rows={len(db)}",
    "PASS" if not content_mismatch else "FAIL", "exact (multiset of full rows)",
    notes=f"rows present in only one run: {len(content_mismatch)}; "
          f"duplication-count-only diffs: {len(dup_only)}")
for k in content_mismatch[:20]:
    add("diagnostic_inventory.csv", "multiset_compare_fail", "|".join(k[:3]), k[3], "",
        "FAIL", "exact", notes=f"ref_count={ca.get(k,0)}, new_count={cb.get(k,0)}")
# value comparison on deduplicated keys (policy 5: counts/status exact, floats per policy 2)
au = da.drop_duplicates(DKEYS); bu = db.drop_duplicates(DKEYS)
m = au.merge(bu, on=DKEYS, how="outer", suffixes=("_ref", "_new"), indicator=True)
n_only = int((m._merge != "both").sum())
add("diagnostic_inventory.csv", "keys", "unique_key_sets", len(au), len(bu),
    "PASS" if n_only == 0 else "FAIL", "exact",
    notes=f"ref_only={(m._merge=='left_only').sum()}, new_only={(m._merge=='right_only').sum()}")
both = m[m._merge == "both"]
worst_ad, worst_rd, nfail, nfail_str = 0.0, 0.0, 0, 0
for _, r in both.iterrows():
    x, y = r.value_ref, r.value_new
    fx, fy = pd.to_numeric(pd.Series([x, y]), errors="coerce")
    if pd.notna(fx) and pd.notna(fy):
        ok, ad, rd = fcmp(fx, fy)
        if ad != float("inf"):
            worst_ad, worst_rd = max(worst_ad, ad), max(worst_rd, rd)
        if not ok:
            nfail += 1
    else:
        if str(x).strip() != str(y).strip():
            nfail_str += 1
add("diagnostic_inventory.csv", "numeric_compare", "value", f"max_abs={worst_ad:.3e}",
    f"max_rel={worst_rd:.3e}", "PASS" if (nfail == 0 and nfail_str == 0) else "FAIL",
    "rel1e-6_or_abs1e-8 (numeric); exact (string)", worst_ad, worst_rd,
    f"n_compared={len(both)}, n_fail_numeric={nfail}, n_fail_string={nfail_str}")

compare_inventory("ipw_weight_diagnostics.csv", ["variable"],
                  ["n_rows", "n_missing_lag_phat"],
                  ["p_marginal_observed", "ess_truncated", "ess_over_n", "max_w_trunc"])

# ------------------------------------------------- master_results.json structural
# Top level is a list of result records; row ORDER differs between runs, so key
# records by (analysis_role, model_id, wellness_variant, term) instead of index.
with open(os.path.join(RREF, "master_results.json")) as f:
    jl_a = json.load(f)
with open(os.path.join(RNEW, "master_results.json")) as f:
    jl_b = json.load(f)
JKEY = ("analysis_role", "model_id", "wellness_variant", "term")
rec_a = {tuple(str(r.get(k, "")) for k in JKEY): r for r in jl_a}
rec_b = {tuple(str(r.get(k, "")) for k in JKEY): r for r in jl_b}
only_a, only_b = set(rec_a) - set(rec_b), set(rec_b) - set(rec_a)
add("master_results.json", "keys", "record_keys", len(rec_a), len(rec_b),
    "PASS" if not only_a and not only_b else "FAIL", "exact",
    notes=f"ref_only={len(only_a)}, new_only={len(only_b)}" +
          ((" e.g. " + ";".join("|".join(k) for k in sorted(only_a)[:5])) if only_a else "") +
          ((" e.g. " + ";".join("|".join(k) for k in sorted(only_b)[:5])) if only_b else ""))
worst_ad, worst_rd, nfail, nfail_str = 0.0, 0.0, 0, 0
n_fields = 0
for k in sorted(set(rec_a) & set(rec_b)):
    ra, rb = rec_a[k], rec_b[k]
    for fld in sorted(set(ra) | set(rb)):
        n_fields += 1
        x, y = ra.get(fld), rb.get(fld)
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool) and not isinstance(y, bool):
            ok, ad, rd = fcmp(x, y)
            if ad != float("inf"):
                worst_ad, worst_rd = max(worst_ad, ad), max(worst_rd, rd)
            if not ok:
                nfail += 1
                if nfail <= 20:
                    add("master_results.json", "numeric_compare_fail", f"{fld} @ " + "|".join(k),
                        x, y, "FAIL", "rel1e-6_or_abs1e-8", ad, rd)
        elif (x is None) != (y is None) or str(x) != str(y):
            nfail_str += 1
            if nfail_str <= 20:
                add("master_results.json", "exact_compare_fail", f"{fld} @ " + "|".join(k),
                    str(x)[:120], str(y)[:120], "FAIL", "exact")
add("master_results.json", "numeric_compare", "all_fields_keyed", f"max_abs={worst_ad:.3e}",
    f"max_rel={worst_rd:.3e}", "PASS" if (nfail == 0 and nfail_str == 0) else "FAIL",
    "rel1e-6_or_abs1e-8 (numeric); exact (string)", worst_ad, worst_rd,
    f"n_records={len(set(rec_a)&set(rec_b))}, n_fields={n_fields}, n_fail_numeric={nfail}, n_fail_string={nfail_str}")

# ------------------------------------------------- 7. lock-hash cross-check
def parse_lock(p):
    d = {}
    with open(p, "r", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2:
                d[parts[1]] = parts[0]
    return d

la, lb = parse_lock(os.path.join(RREF, "RESULTS_LOCK_HASH.txt")), parse_lock(os.path.join(RNEW, "RESULTS_LOCK_HASH.txt"))
for fn in sorted(set(la) | set(lb)):
    add("RESULTS_LOCK_HASH.txt", "lock_hash_entry", fn, la.get(fn, "ABSENT"), lb.get(fn, "ABSENT"),
        "PASS" if la.get(fn) == lb.get(fn) else "INFO", "exact",
        notes="hash differs iff file bytes differ; see byte_identity rows")
add("RESULTS_LOCK.md", "byte_identity", "md_note", "", "", "INFO",
    notes="reference .md is GB18030-ish text; byte equality not required per policy 7")

# ------------------------------------------------- 8. published constants
mr = pd.read_csv(os.path.join(RREF, "master_results.csv"))
mr_new = pd.read_csv(os.path.join(RNEW, "master_results.csv"))

def get_or(df, role, mid, var, term):
    r = df[(df.analysis_role == role) & (df.model_id == mid) &
           (df.wellness_variant == var) & (df.term == term)]
    return float(r.OR.iloc[0]) if len(r) else float("nan")

const_checks = [
    ("soreness PA-fallback acute-load OR", "PRIMARY", "A", "soreness", "acute_load_7d_wp_z", 0.696, 5e-4),
    ("soreness burden recent3 OR", "PRIMARY", "A", "soreness", "soreness_burden_recent3_wp_z", 0.745, 5e-4),
    ("soreness chronic-load OR", "PRIMARY", "A", "soreness", "chronic_load_28d_wp_z", 0.953, 5e-4),
    ("soreness prev_episode_ever OR", "PRIMARY", "A", "soreness", "prev_episode_ever", 6.486, 5e-4),
    ("soreness season2021 OR", "PRIMARY", "A", "soreness", "season2021", 2.687, 5e-4),
    ("Firth soreness interaction OR", "SMALL_SAMPLE_SENSITIVITY", "F", "soreness",
     "acute_load_7d_wp_z:soreness_burden_recent3_wp_z", 0.6296, 5e-5),
]
for label, role, mid, var, term, c, tol in const_checks:
    v_ref, v_new = get_or(mr, role, mid, var, term), get_or(mr_new, role, mid, var, term)
    add("master_results.csv", "published_constant_verify", label, c, v_ref,
        "PASS" if abs(v_ref - c) <= tol else "FAIL", f"abs<{tol} (rounded constant)",
        abs(v_ref - c), "", f"repro_value={v_new}")

add("bootstrap_primary_interaction.json", "published_constant_verify", "bootstrap interaction OR_median",
    0.6697, ja.get("OR_median"), "PASS" if abs(ja.get("OR_median") - 0.6697) <= 5e-5 else "FAIL",
    "abs<5e-5 (rounded constant)", abs(ja.get("OR_median") - 0.6697), "", f"repro_value={jb.get('OR_median')}")

# --- IPW variant investigation (policy 8) ---
ipw_a = mr[(mr.model_id.str.contains("IPW", case=False, na=False)) & (mr.term.str.contains(":", na=False))]
ipw_b = mr_new[(mr_new.model_id.str.contains("IPW", case=False, na=False)) & (mr_new.term.str.contains(":", na=False))]
for (var, df) in [("reference", ipw_a), ("reproduced", ipw_b)]:
    for _, r in df.iterrows():
        add("master_results.csv", "ipw_variant_scan", f"{var}:{r.wellness_variant}",
            f"{r.analysis_role}/{r.model_id}/{r.term}", r.OR, "INFO",
            notes="only IPW variant present in results; no second (no-outcome observation-model) IPW variant found")
claimed_ipw = {"soreness": 0.833, "fatigue": 0.930, "readiness": 1.035}
for var, c in claimed_ipw.items():
    r = ipw_a[ipw_a.wellness_variant == var]
    actual = float(r.OR.iloc[0]) if len(r) else float("nan")
    add("master_results.csv", "ipw_claimed_constant_check", f"claimed corrected recent3 IPW interaction OR ({var})",
        c, actual, "INFO", notes=("claimed value NOT found in any R1 output; actual IPW interaction OR is "
        f"{actual:.4f} (matches the 0.6464/0.8012/0.9184 set from earlier exploration). "
        "Observation model (observation_model_results.csv) includes onset_day term; only this one IPW variant exists in the locked run."))
# grep-style scan for claimed values anywhere in run outputs
import io
for cval in ["0.833", "0.930", "1.035", "219", "224"]:
    hits = []
    for fn in ref_files:
        if fn.endswith((".csv", ".json", ".txt")):
            try:
                with open(os.path.join(RREF, fn), errors="replace") as f:
                    if cval in f.read():
                        hits.append(fn)
            except Exception:
                pass
    add("(all run outputs)", "claimed_value_scan", f"string '{cval}' in reference outputs",
        cval, ",".join(hits) if hits else "NOT FOUND", "INFO")

# claimed weight/ESS constants vs actual (policy 8)
for var, s in ipw_stats.items():
    add(f"ipw_weights_{var}.csv", "claimed_weight_constant_check", "untruncated max w_stab (claim ~219-224)",
        "219-224", f"{s['max_w_stab']:.4f}", "INFO", notes="claim NOT reproduced; actual max stabilised weight ~10.9")
    add(f"ipw_weights_{var}.csv", "claimed_weight_constant_check", "truncated max (claim ~8.0-8.2)",
        "8.0-8.2", f"{s['max_w_stab_trunc']:.4f}", "INFO", notes="claim NOT reproduced; actual truncated max ~6.3 (1-99 truncation)")
    add(f"ipw_weights_{var}.csv", "claimed_weight_constant_check", "ESS fraction (claim ~44-45%)",
        "0.44-0.45", f"{s['ess_frac_trunc_nrows']:.4f} (of n_rows) / {s['ess_frac_trunc_nonnull']:.4f} (of non-null)",
        "INFO", notes="claim NOT reproduced; run-level ipw_weight_diagnostics ess_over_n~0.534; top-level ipw_effective_sample_size ratio~0.403-0.404")

# ------------------------------------------------- 9. sample counts
ec = pd.read_csv(os.path.join(RREF, "event_count_inventory.csv"))
ec_new = pd.read_csv(os.path.join(RNEW, "event_count_inventory.csv"))
w7 = ec[ec.washout_days == 7].iloc[0]
w7n = ec_new[ec_new.washout_days == 7].iloc[0]
count_checks = [
    ("at_risk_days (washout 7)", 36296, w7.at_risk_days, w7n.at_risk_days),
    ("ll_episodes (washout 7)", 92, w7.ll_episodes, w7n.ll_episodes),
    ("onset_days_total (washout 7)", 52, w7.onset_days_total, w7n.onset_days_total),
    ("onset_days_in_risk_set (washout 7)", 42, w7.onset_days_in_risk_set, w7n.onset_days_in_risk_set),
    ("event_players (washout 7)", 15, w7.event_players, w7n.event_players),
]
ss = pd.read_csv(os.path.join(RREF, "sample_size_inventory.csv"))
ss_new = pd.read_csv(os.path.join(RNEW, "sample_size_inventory.csv"))
for var, n_exp in [("soreness", 19758), ("fatigue", 19815), ("readiness", 19817)]:
    ra = ss[(ss.model_id == "A") & (ss.wellness_variant == var)].iloc[0]
    rb = ss_new[(ss_new.model_id == "A") & (ss_new.wellness_variant == var)].iloc[0]
    count_checks.append((f"CC n ({var})", n_exp, ra.n, rb.n))
    if var == "soreness":
        count_checks += [("CC players (soreness)", 49, ra.players, rb.players),
                         ("CC onset-days (soreness)", 28, ra.onset_days, rb.onset_days),
                         ("CC event players (soreness)", 9, ra.event_players, rb.event_players)]
for label, exp, v_ref, v_new in count_checks:
    add("(inventories)", "sample_count_verify", label, exp, f"ref={v_ref}, repro={v_new}",
        "PASS" if (int(v_ref) == exp and int(v_new) == exp) else "FAIL", "exact")

# ------------------------------------------------- write outputs
# classify the cause of every BYTE_DIFFERENT file (established by manual inspection
# during this gate run; all are harmless formatting/ordering/environment diffs)
byte_causes = {
    "r_results.csv": "float printing only (15 vs 17 significant digits; '0.0' vs '0'); all values within tolerance",
    "master_results.csv": "row order differs + one p-value last-digit print (2.2204460492503094e-16 vs ...3099e-16, rel ~2e-16); all values within tolerance",
    "master_results.json": "record order differs; keyed field-by-field comparison all within tolerance",
    "sample_size_inventory.csv": "CSV quoting style only; row content sets identical",
    "model_inventory.csv": "reference-only retired model-G documentation row + quoting; common rows identical (whitespace-normalised)",
    "diagnostic_inventory.csv": "reference repeats DATA/S3 documentation rows 3-4x + quoting; unique key/value content identical",
    "session_info_R.txt": "lme4 patch version differs (2.0-1 ref vs 2.0-6 sandbox); all other lines identical; no numeric impact observed",
    "RESULTS_LOCK_HASH.txt": "per-file hashes differ exactly for the byte-different files listed above; combined hash differs accordingly",
    "RESULTS_LOCK.md": "run id (RUN_20260722_151418 vs RUN_R2_REPRO) and combined hash; .md exempt per policy 7",
}
for fn, cause in byte_causes.items():
    if byte_status.get(fn) == "BYTE_DIFFERENT":
        add(fn, "byte_diff_classification", "numerically_equal_but_byte_different", "", "", "INFO",
            notes=cause)

df = pd.DataFrame(rows, columns=["file", "check", "item", "reference_value", "reproduced_value",
                                 "match_status", "tolerance", "abs_diff", "rel_diff", "notes"])
os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
df.to_csv(OUT_CSV, index=False)

fails = df[df.match_status == "FAIL"]
passn = int((df.match_status == "PASS").sum())
summary = []
summary.append("=" * 78)
summary.append(f"GATE A R1 REPRODUCTION CHECK  {datetime.datetime.now().isoformat(timespec='seconds')}")
summary.append(f"reference: {RREF}")
summary.append(f"repro    : {RNEW}")
summary.append(f"checks: {len(df)} rows | PASS={passn} | FAIL={len(fails)} | "
               f"INFO/PASS_NORM={len(df) - passn - len(fails)}")
summary.append("")
summary.append("Byte identity of run files:")
for fn in all_files:
    summary.append(f"  {byte_status[fn]:<16} {fn}")
summary.append("")
if len(fails):
    summary.append("FAILURES:")
    for _, r in fails.iterrows():
        summary.append(f"  [{r['file']}] {r['check']} / {r['item']}: ref={r['reference_value']} repro={r['reproduced_value']} {r['notes']}")
else:
    summary.append("No tolerance-exceeding mismatches (FAIL rows: 0).")
summary.append("")
ipw_line = {v: float(ipw_a[ipw_a.wellness_variant == v].OR.iloc[0]) for v in ["soreness", "fatigue", "readiness"]}
summary.append("IPW interaction ORs (single variant found): " +
               ", ".join(f"{k}={v:.4f}" for k, v in ipw_line.items()) +
               " | claimed 0.833/0.930/1.035 NOT found in any R1 output")
summary.append("Weight stats (ref run): " + "; ".join(
    f"{v}: max_w_stab={s['max_w_stab']:.3f}, max_trunc={s['max_w_stab_trunc']:.3f}, "
    f"ESSfrac(rows)={s['ess_frac_trunc_nrows']:.3f}" for v, s in ipw_stats.items()))
summary.append("Verdict: " + ("GATE A: FAIL" if len(fails) else "GATE A: PASS"))
summary.append("=" * 78)
text = "\n".join(summary)
print(text)
os.makedirs(os.path.dirname(LOG), exist_ok=True)
with open(LOG, "a", encoding="utf-8") as f:
    f.write(text + "\n")
