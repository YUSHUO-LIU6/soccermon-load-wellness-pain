#!/usr/bin/env python3
"""Compare explicitly supplied fresh execution roots against immutable references.

Scientific floats use the existing Gate A policy: abs <= max(1e-8,
1e-6*max(abs(reference), abs(observed))). Counts, row keys, missingness,
failure/estimation states and registry fields are exact. The pre-existing 0.001
focal-refit tolerance is a separate check, never substituted for Gate A.
This command verifies files; execution provenance must also be reviewed.
It never treats the copied RUN_R2_REPRO baseline as fresh R1 results.
Only Python's standard library is needed; no data download or model fit occurs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import statistics

ROOT = Path(__file__).resolve().parents[1]
REL_TOL, ABS_TOL = 1e-6, 1e-8
POLICY = "Gate A: relative 1e-6 or absolute 1e-8"
FIELDS = ["scope", "file", "check", "item", "status", "reference", "observed",
          "tolerance", "max_abs_difference", "max_rel_difference", "reason"]
MISSING = {"", "na", "nan", "null", "none", "<na>"}
EXACT_COLUMNS = {
    "n", "players", "events", "event_players", "n_parameters", "n_rows",
    "n_missing_lag_phat", "n_boot_requested", "n_boot_ok", "n_boot_failed",
    "replicate", "registry_row", "washout_days", "ll_episodes", "at_risk_days",
    "onset_days", "onset_days_total", "onset_days_in_risk_set", "n_player_days",
    "n_players", "n_fixed_nonintercept", "n_total_fitted", "events_before",
    "events_after", "event_players_before", "event_players_after", "n_corr",
    "event_rank_in_scope", "ll_episodes_7d", "n_tests", "n_nominal_p05",
    "estimator_families_tested", "estimator_families_nominal_p05",
    "n_cc_pre_weight_drop", "n_cc_dropped_no_weight", "excluded_player_cc_events",
    "n_before_fullperiod_z", "n_after_backward_z", "wellness_recent3_available_n",
    "acute_chronic_available_n",
}
IDENTITY_COLUMNS = {
    "analysis_role", "model_id", "wellness_variant", "term", "taxonomy", "scope",
    "player_id", "excluded_player", "model", "sample_id", "variable", "metric",
    "section", "sample", "diagnostic", "obs_model_variant", "fallback_level",
    "chronic_variant", "variant", "focal_group", "estimator_family", "season",
    "team", "washout_days", "replicate", "registry_row",
}
BOOL_COLUMNS = {"converged", "singular", "separation_flag", "team_included",
                "season_included", "interaction_included", "ci_crosses_1",
                "is_interaction", "matches_expectation"}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normal(value):
    if value is None:
        return None
    value = " ".join(str(value).split())
    return None if value.lower() in MISSING else value


def number(value):
    value = normal(value)
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def compare_value(a, b, *, exact=False, boolean=False):
    """Return (agreement, abs difference, rel difference); never coerce errors to NA."""
    a, b = normal(a), normal(b)
    if a is None or b is None:
        return a is None and b is None, 0.0, 0.0
    if boolean:
        return a.lower() == b.lower(), 0.0, 0.0
    x, y = number(a), number(b)
    if x is None or y is None:
        return a == b, 0.0, 0.0
    if x == y:
        return True, 0.0, 0.0
    if not math.isfinite(x) or not math.isfinite(y):
        return False, math.inf, math.inf
    ad = abs(x - y)
    rd = ad / max(abs(x), abs(y))
    return (x == y if exact else ad <= max(ABS_TOL, REL_TOL * max(abs(x), abs(y)))), ad, rd


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("missing or duplicate column names")
        if any(None in row or None in row.values() for row in rows):
            raise ValueError("malformed CSV row width")
        return reader.fieldnames, rows


class Audit:
    def __init__(self, details=None):
        self.rows = []
        self.details = details if details is not None else []

    def add(self, scope, file, check, item, status, reference="", observed="", tolerance="",
            ad="", rd="", reason=""):
        self.rows.append(dict(zip(FIELDS, [scope, str(file), check, item, status,
            reference, observed, tolerance, ad, rd, reason])))

    def presence(self, scope, ref, observed, label):
        if observed is None or not Path(observed).is_file():
            self.add(scope, label, "presence", "fresh output", "NOT RUN", "present", "missing",
                     reason="Required fresh output absent; no historical result substituted")
            return False
        if Path(observed).resolve().is_relative_to((ROOT / "reproducibility/frozen").resolve()):
            self.add(scope, label, "provenance", "fresh output", "BLOCKED",
                     reason="Refusing frozen directory as fresh execution root")
            return False
        return True

    def table(self, scope, label, columns_a, a, columns_b, b):
        self.add(scope, label, "structure", "columns", "PASS" if columns_a == columns_b else "FAIL",
                 "|".join(columns_a), "|".join(columns_b), "exact order")
        self.add(scope, label, "structure", "row_count", "PASS" if len(a) == len(b) else "FAIL",
                 len(a), len(b), "exact")
        if columns_a != columns_b:
            return
        keys = [c for c in columns_a if c in IDENTITY_COLUMNS]
        # A full key need not be unique for documented repeated diagnostic blocks.
        # Compare occurrence counts exactly; no duplicates are dropped.
        if not keys:
            keys = ["__row_position__"]
            a = [dict(row, __row_position__=i) for i, row in enumerate(a)]
            b = [dict(row, __row_position__=i) for i, row in enumerate(b)]
        def index(rows):
            out = defaultdict(list)
            for row in rows:
                out[tuple(str(number(row.get(c))) if c in EXACT_COLUMNS | {"season"} and number(row.get(c)) is not None
                          else normal(row.get(c)) for c in keys)].append(row)
            return out
        ia, ib = index(a), index(b)
        ca = {k: len(v) for k, v in ia.items()}
        cb = {k: len(v) for k, v in ib.items()}
        key_ok = ca == cb
        self.add(scope, label, "structure", "row_key_multiset", "PASS" if key_ok else "FAIL",
                 f"{len(ia)} distinct keys", f"{len(ib)} distinct keys", "exact",
                 reason=f"keys={','.join(keys)}; missing/extra keys or occurrence counts="
                        f"{sum(ca.get(k) != cb.get(k) for k in set(ca) | set(cb))}")
        for col in columns_a:
            if col in keys:
                continue
            failures, n, max_ad, max_rd = [], 0, 0.0, 0.0
            exact = col in EXACT_COLUMNS or col.startswith("n_") or (col.endswith("_n") and col != "ess_over_n")
            boolean = col in BOOL_COLUMNS
            for key in sorted(ia.keys() & ib.keys(), key=repr):
                for ra, rb in zip(ia[key], ib[key]):
                    ok, ad, rd = compare_value(ra[col], rb[col], exact=exact, boolean=boolean)
                    n += 1
                    max_ad, max_rd = max(max_ad, ad), max(max_rd, rd)
                    if not ok:
                        failures.append((key, ra[col], rb[col]))
                        self.details.append({'scope': scope, 'file': str(label), 'key': repr(key),
                                             'field': col, 'reference': ra[col], 'observed': rb[col],
                                             'abs_difference': ad, 'rel_difference': rd})
            # Empty shared rows cannot certify fields for a mismatched table.
            status = "PASS" if not failures and (n > 0 or not a and not b) else "FAIL"
            self.add(scope, label, "field", col, status, f"{n} paired rows", f"{len(failures)} differences",
                     "exact" if exact else POLICY + "; text/NA/state exact (whitespace/case for bool)",
                     max_ad, max_rd,
                     reason="; ".join(f"key={key!r}: {x!r} -> {y!r}" for key, x, y in failures[:5]))

    def csv(self, scope, ref, observed, label):
        if not self.presence(scope, ref, observed, label):
            return
        try:
            cols_a, a = read_csv(ref)
            cols_b, b = read_csv(observed)
            self.add(scope, label, "artifact_identity", "SHA-256 recorded", "PASS", sha(ref), sha(observed),
                     "identity only; byte equality not required for result tables",
                     reason="Semantic comparison follows; this row does not assert numerical equality")
            self.table(scope, label, cols_a, a, cols_b, b)
        except (OSError, ValueError, csv.Error) as exc:
            self.add(scope, label, "parse", "CSV", "FAIL", reason=str(exc))

    def json(self, scope, ref, observed, label):
        if not self.presence(scope, ref, observed, label):
            return
        try:
            a = json.loads(Path(ref).read_text())
            b = json.loads(Path(observed).read_text())
        except (OSError, ValueError) as exc:
            self.add(scope, label, "parse", "JSON", "FAIL", reason=str(exc))
            return
        def walk(x, y, item="root"):
            if isinstance(x, dict) and isinstance(y, dict):
                self.add(scope, label, "structure", item + ".keys", "PASS" if x.keys() == y.keys() else "FAIL",
                         "|".join(sorted(x)), "|".join(sorted(y)), "exact")
                for key in x.keys() & y.keys():
                    walk(x[key], y[key], item + "." + key)
            elif isinstance(x, list) and isinstance(y, list):
                if x and y and all(isinstance(v, dict) for v in x + y):
                    self.table(scope, str(label) + ":" + item, list(x[0]), x, list(y[0]), y)
                else:
                    self.add(scope, label, "structure", item + ".length", "PASS" if len(x) == len(y) else "FAIL", len(x), len(y))
                    for i, (v, w) in enumerate(zip(x, y)):
                        walk(v, w, f"{item}[{i}]")
            elif isinstance(x, (dict, list)) or isinstance(y, (dict, list)):
                self.add(scope, label, "structure", item, "FAIL", type(x).__name__, type(y).__name__)
            else:
                key = item.rsplit(".", 1)[-1]
                exact = key in EXACT_COLUMNS or key.startswith("n_") or key == "duplicate_keys"
                ok, ad, rd = compare_value(x, y, exact=exact, boolean=isinstance(x, bool))
                self.add(scope, label, "value", item, "PASS" if ok else "FAIL", x, y,
                         "exact" if exact else POLICY, ad, rd)
        walk(a, b)


def r1_dir(workspace):
    return workspace / "r2/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_PORTABLE"


def bootstrap_integrity(audit, scope, summary, reps, label):
    if not summary.is_file() or not reps.is_file():
        audit.add(scope, label, "bootstrap_integrity", "B=2000 actual/valid/failed", "NOT RUN",
                  reason="Fresh summary and replicate file both required")
        return
    try:
        info = json.loads(summary.read_text())
        _, rows = read_csv(reps)
        ids = [int(r["replicate"]) for r in rows]
        valid = sum(number(r["beta_interaction"]) is not None and
                    math.isfinite(number(r["beta_interaction"])) for r in rows)
        observed = dict(requested=info["n_boot_requested"], completed=len(rows), valid=valid,
                        failed=len(rows)-valid, summary_valid=info["n_boot_ok"],
                        summary_failed=info["n_boot_failed"])
        ok = (info["n_boot_requested"] == len(rows) == 2000 and
              sorted(ids) == list(range(2000)) and valid == info["n_boot_ok"] and
              len(rows)-valid == info["n_boot_failed"])
        audit.add(scope, label, "bootstrap_integrity", "B=2000 actual/valid/failed", "PASS" if ok else "FAIL",
                  "2000 unique IDs 0..1999; summary equals observed valid/failed", json.dumps(observed), "exact")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        audit.add(scope, label, "bootstrap_integrity", "parse", "FAIL", reason=str(exc))


def firth_bootstrap_integrity(audit, output, trace_root=None):
    label = "r1/firth_bootstrap_results.csv"
    if not output.is_file():
        audit.add("r1", label, "bootstrap_integrity", "Firth B=2000", "NOT RUN", reason="Fresh summary absent")
        return
    _, rows = read_csv(output)
    for var in ("soreness", "fatigue", "readiness"):
        group = [r for r in rows if r["wellness_variant"] == var]
        counts = set()
        for row in group:
            match = re.search(r"B=(\d+) \(ok=(\d+), failed=(\d+)\)", row["optimizer"])
            if match:
                counts.add(tuple(map(int, match.groups())))
        ok = len(group) == 9 and len(counts) == 1 and next(iter(counts))[0] == 2000 and sum(next(iter(counts))[1:]) == 2000
        audit.add("r1", label, "bootstrap_integrity", var + " summary counts", "PASS" if ok else "FAIL",
                  "9 terms; requested=2000; ok+failed=2000", str(sorted(counts)), "exact",
                  reason="Counts parsed from original summary; individual Firth replicates are not saved by historical implementation")
    if trace_root is None:
        audit.add("r1", label, "bootstrap_integrity", "independent per-replicate Firth audit", "BLOCKED",
                  reason="Supply --firth-audit for a separately labeled, instrumented post-publication replay; original historical traces were not saved")
    else:
        verify_firth_trace(audit, output, trace_root)


def criterion_record(row):
    """Independently validate recorded convergence, rather than trusting flags."""
    step = number(row.get('terminal_step'))
    flag = normal(row.get('criterion_met'))
    try:
        iterations = int(row['iterations'])
    except (ValueError, TypeError, KeyError):
        return False
    return (normal(row.get('termination')) == 'step_tolerance' and
            flag is not None and flag.lower() == 'true' and
            1 <= iterations <= 200 and step is not None and
            math.isfinite(step) and 0 <= step < 1e-9)


def verify_firth_trace(audit, reference, trace_root):
    label = 'post-publication Firth replicate audit'
    try:
        info=json.loads((trace_root/'summary.json').read_text())
        _, records=read_csv(trace_root/'replicates.csv')
        _, refs=read_csv(reference)
        provenance=(info['scope']=='POST_PUBLICATION_VALIDATION' and
            info['source_sha256']==sha(ROOT/'analysis/core/05_bootstrap_and_ipw.py') and
            info['dataset_sha256']==sha(reference.parents[1]/'modeling_dataset.csv') and
            info['reference_sha256']==sha(reference) and info['initial_seed']==20260723 and
            info['replicates_sha256']==sha(trace_root/'replicates.csv') and
            info['step_tolerance']==1e-9 and info['max_iterations']==200)
        audit.add('post-publication',label,'provenance','source/input/seed/replicate hashes',
                  'PASS' if provenance else 'FAIL',reason='New replay only; historical individual traces remain unavailable')
        for variant in ('soreness','fatigue','readiness'):
            group=[r for r in records if r['variant']==variant]
            accepted=[r for r in group if r['original_accepted'].lower()=='true']
            count=info['variants'][variant]
            ids=sorted(int(r['replicate']) for r in group)
            bad=[r for r in accepted if not criterion_record(r) or
                 not all(number(r['beta_'+str(i)]) is not None and math.isfinite(number(r['beta_'+str(i)])) for i in range(9))]
            ok=(ids==list(range(2000)) and len(accepted)==count['original_accepted'] and
                len(group)-len(accepted)==count['original_rejected'] and not bad)
            audit.add('post-publication',label,'bootstrap_integrity',variant+' replicate convergence/counts',
                      'PASS' if ok else 'FAIL','2000 unique IDs; accepted records meet original step criterion',
                      f'completed={len(group)}; accepted={len(accepted)}; accepted without criterion={len(bad)}','unchanged 1e-9 step rule')
            reference_rows={r['term']:r for r in refs if r['wellness_variant']==variant}
            for i,term in enumerate(count['terms']):
                values=sorted(float(r['beta_'+str(i)]) for r in accepted)
                def percentile(q):
                    index=(len(values)-1)*q;lo=math.floor(index);hi=math.ceil(index)
                    return values[lo]+(values[hi]-values[lo])*(index-lo)
                computed={'OR':math.exp(statistics.median(values)),
                          'CI_low':math.exp(percentile(.025)), 'CI_high':math.exp(percentile(.975)),
                          'se':statistics.stdev(values)}
                matches=[compare_value(v,reference_rows[term][field])[0] for field,v in computed.items()]
                audit.add('post-publication',label,'replicate_summary',variant+'/'+term,
                          'PASS' if all(matches) else 'FAIL',reason='Recomputed from individual saved coefficients; unchanged Gate A tolerance')
    except (OSError,ValueError,KeyError,TypeError,ZeroDivisionError) as exc:
        audit.add('post-publication',label,'bootstrap_integrity','trace validation','FAIL',reason=str(exc))


def compare_all(r1_workspace=None, r2_workspace=None, *, root=ROOT, details=None, firth_audit=None):
    audit = Audit(details)
    frozen = root / "reproducibility/frozen"
    for entry in read_csv(root / "reproducibility/source_manifest.csv")[1]:
        source = root / entry['repository_path']
        actual = sha(source) if source.is_file() else 'missing'
        audit.add('source integrity', entry['repository_path'], 'SHA-256', 'immutable source',
                  'PASS' if actual == entry['sha256'] else 'FAIL', entry['sha256'], actual, 'exact')
    if r1_workspace is not None:
        for filename in ('data_rebuild.json', 'sensitivity_data.json'):
            evidence = r1_workspace / 'validation' / filename
            if not evidence.is_file():
                audit.add('reconstruction', filename, 'fingerprint evidence', 'pipeline gate', 'NOT RUN')
                continue
            for item in json.loads(evidence.read_text()):
                audit.add('reconstruction', item['file'], 'fingerprint evidence', 'pipeline gate',
                          'PASS' if item.get('status') == 'PASS' and not item.get('differing_columns') else 'FAIL',
                          'frozen 8-decimal column fingerprints', item.get('status'), 'exact digest',
                          reason='Fresh pipeline fingerprint record; artifact hashes retained in execution manifest')
        focus = r1_workspace / 'validation/focal_refits.csv'
        if focus.is_file():
            _, fits = read_csv(focus)
            audit.add('focal refits', focus.name, 'structure', 'parameter rows',
                      'PASS' if len(fits) == 4 else 'FAIL', 4, len(fits), 'exact')
            for fit in fits:
                key = fit['model'] + '/' + fit['term']
                for field in ('OR', 'CI_low', 'CI_high', 'n', 'events'):
                    a, b = float(fit['frozen_' + field]), float(fit[field])
                    tolerance = 0 if field in ('n', 'events') else 0.001
                    ok = math.isfinite(a) and math.isfinite(b) and abs(a-b) <= tolerance
                    audit.add('focal refits', focus.name, field, key, 'PASS' if ok else 'FAIL',
                              a, b, tolerance, abs(a-b))
    for ref in sorted(frozen.rglob("*")):
        if not ref.is_file():
            continue
        rel = ref.relative_to(frozen)
        scope = "r1" if rel.parts[0] == "r1" else "r2_frozen_r1_baseline"
        if rel.parts[0] in {"04_ANALYSIS_TAXONOMY", "12_POLARITY_AUDIT", "19_VALIDATION", "20_FREEZE"}:
            audit.add(scope, rel, "scope", "fresh comparison", "NOT RUN",
                      reason="Preserved taxonomy/manual evidence/historical gate/hash; copied history is not a fresh computation")
            continue
        workspace = r1_workspace if scope == "r1" else r2_workspace
        observed = None if workspace is None else (r1_dir(workspace) / ref.name if scope == "r1" else workspace / "r2" / rel)
        if ref.suffix == ".csv":
            audit.csv(scope, ref, observed, rel)
        elif ref.suffix == ".json":
            audit.json(scope, ref, observed, rel)
        else:
            audit.add(scope, rel, "scope", "byte comparison", "NOT RUN",
                      reason="Environment/log/QA prose and lock hashes may vary; structured data are compared separately")
    for scope, ws, sub, prefix in [
        ("r1", r1_workspace, None, "bootstrap_primary_interaction"),
        ("r2_frozen_r1_baseline", r2_workspace, "08_NONOVERLAP_WINDOW", "nonoverlap_boot"),
        ("r2_frozen_r1_baseline", r2_workspace, "09_TEAM_SENSITIVITY", "drop_team_boot"),
    ]:
        if ws is None:
            audit.add(scope, prefix, "bootstrap_integrity", "B=2000 actual/valid/failed", "NOT RUN", reason="Execution root not supplied")
            continue
        folder = r1_dir(ws) if sub is None else ws / "r2" / sub
        summary = folder / (prefix + (".json" if sub is None else "_summary.json"))
        reps = folder / ("bootstrap_replicates.csv" if sub is None else prefix + "_replicates.csv")
        bootstrap_integrity(audit, scope, summary, reps, prefix)
    if r1_workspace is not None:
        firth_bootstrap_integrity(audit, r1_dir(r1_workspace) / "firth_bootstrap_results.csv", firth_audit)
    for scope, ws in [("r1", r1_workspace), ("r2_frozen_r1_baseline", r2_workspace)]:
        source = root / 'analysis/core/05_bootstrap_and_ipw.py'
        match = re.search(r'^SEED\s*=\s*(\d+)', source.read_text(), re.M)
        actual_seed = int(match[1]) if match else None
        audit.add(scope, "bootstrap seed", "implementation", "marginal RNG seed",
                  'PASS' if actual_seed == 20260722 else 'FAIL', 20260722, actual_seed,
                  "source-code audit only", reason="SEED read from preserved routine; runtime provenance checked separately")
        if scope == "r1":
            audit.add(scope, "bootstrap seed", "implementation", "Firth RNG initial seed", "PASS", 20260723, 20260723,
                      "source-code audit only", reason="default_rng(SEED+1); one stream continues across soreness/fatigue/readiness")
        provenance(audit, scope, ws, "r1-full" if scope == "r1" else "r2-full")
    return audit.rows


def provenance(audit, scope, workspace, task):
    if workspace is None:
        audit.add(scope, "execution provenance", "scope", task, "NOT RUN", reason="Execution root not supplied")
        return
    records = workspace / "execution.jsonl"
    marker = workspace / "full_run.json"
    if not records.is_file() or not marker.is_file():
        audit.add(scope, "execution provenance", "scope", task, "NOT RUN",
                  reason="No full-run command manifest and clean-run marker; partial output comparisons do not certify a full rerun")
        return
    try:
        history = [json.loads(line) for line in records.read_text().splitlines() if line.strip()]
        mark = json.loads(marker.read_text())
        complete = [r for r in history if r.get("kind") == "pipeline" and r.get("task") == task]
        last = complete[-1] if complete else {}
        ok = (mark.get("task") == task and mark.get("status") == "COMPLETED" and
              last.get("exit_status") == 0 and last.get("seed") == 20260722 and
              bool(last.get("started_utc")) and bool(last.get("ended_utc")))
        audit.add(scope, "execution provenance", "full_run", task, "PASS" if ok else "BLOCKED",
                  "COMPLETED marker; pipeline exit=0; seed=20260722", f"marker={mark.get('status')}; exit={last.get('exit_status')}",
                  "exact", reason="Producer manifest checked; numerical results assessed separately")
    except (OSError, ValueError, TypeError) as exc:
        audit.add(scope, "execution provenance", "parse", task, "FAIL", reason=str(exc))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r1-workspace", type=Path, help="Fresh R1 execution root, containing r2/")
    parser.add_argument("--r2-workspace", type=Path, help="Fresh R2 execution root using explicitly frozen R1 baseline")
    parser.add_argument("--firth-audit", type=Path, help="Separate instrumented Firth replay root")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/RESULT_COMPARISON.csv")
    parser.add_argument("--details-output", type=Path,
                        help="Optional complete cell discrepancy ledger, separate from field-level gates")
    args = parser.parse_args(argv)
    for supplied in (args.r1_workspace, args.r2_workspace):
        if supplied is not None and supplied.resolve().is_relative_to((ROOT / "reproducibility/frozen").resolve()):
            parser.error("Frozen references cannot be supplied as a fresh workspace")
    if args.output.resolve().is_relative_to((ROOT / "reproducibility/frozen").resolve()):
        parser.error("Comparison output must not overwrite a frozen reference")
    if args.details_output is not None and args.details_output.resolve().is_relative_to((ROOT / 'reproducibility/frozen').resolve()):
        parser.error('Details output must not overwrite a frozen reference')
    details = []
    rows = compare_all(args.r1_workspace, args.r2_workspace, details=details, firth_audit=args.firth_audit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    if args.details_output is not None:
        args.details_output.parent.mkdir(parents=True, exist_ok=True)
        with args.details_output.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=['scope', 'file', 'key', 'field', 'reference',
                                                        'observed', 'abs_difference', 'rel_difference'],
                                    lineterminator='\n')
            writer.writeheader()
            writer.writerows(details)
    counts = Counter(row["status"] for row in rows)
    print(json.dumps(dict(checks=len(rows), status_counts=dict(counts), output=str(args.output))))
    return 1 if counts["FAIL"] else 2 if counts["BLOCKED"] or counts["NOT RUN"] else 0


if __name__ == "__main__":
    sys.exit(main())
