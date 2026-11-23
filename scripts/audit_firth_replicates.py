"""Instrument the preserved Firth bootstrap without changing its estimates.

This post-publication diagnostic replays only the three unrecorded Firth
streams. Original acceptance, RNG order and numerical operations are retained;
criterion-based convergence is reported separately, never substituted into
the frozen results. No sampled player identities are written.
"""
from __future__ import annotations
import argparse
import ast
import copy
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import warnings

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def functions_from_source(path):
    """Load only analytical definitions, avoiding original module I/O."""
    module = ast.parse(path.read_text(encoding='utf-8-sig'))
    funcs = {'design_matrix', 'irls_logit', 'cc_frame', 'player_cluster_indices'}
    selected = []
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name in funcs:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
                t.id in {'WELL_Z', 'COVARS', 'SEED'} for t in node.targets):
            selected.append(node)
    namespace = {'np': np}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace, next(n for n in selected if isinstance(n, ast.FunctionDef) and n.name == 'irls_logit')


def instrument_irls(node, namespace):
    """Replace returns with observation-only callbacks; preserve return values."""
    last = {}
    def observe(beta, original_ok, iterations, terminal_step, reason):
        last.clear()
        last.update(iterations=int(iterations), terminal_step=float(terminal_step),
                    termination=reason, criterion_met=reason == 'step_tolerance',
                    original_ok=bool(original_ok))
        return beta, original_ok
    class Returns(ast.NodeTransformer):
        def visit_Return(self, item):
            # The source has exactly singular, tolerance, iteration-limit returns.
            first = item.value.elts[0]
            if isinstance(first, ast.Constant) and first.value is None:
                reason, count, step = 'singular_information', 'it + 1', 'float("nan")'
            elif item.col_offset > node.col_offset + 4:
                reason, count, step = 'step_tolerance', 'it + 1', 'float(np.max(np.abs(step)))'
            else:
                reason, count, step = 'iteration_limit', 'max_iter', 'float(np.max(np.abs(step)))'
            args = [*copy.deepcopy(item.value.elts), ast.parse(count, mode='eval').body,
                    ast.parse(step, mode='eval').body, ast.Constant(reason)]
            return ast.copy_location(ast.Return(ast.Call(ast.Name('_observe', ast.Load()), args, [])), item)
    modified = Returns().visit(copy.deepcopy(node))
    ast.fix_missing_locations(modified)
    ns = dict(namespace, _observe=observe)
    exec(compile(ast.Module(body=[modified], type_ignores=[]), '<instrumented preserved IRLS>', 'exec'), ns)
    return ns['irls_logit'], last


def summarize(values):
    if not len(values):
        return None
    return dict(OR=np.exp(np.median(values, axis=0)).tolist(),
                CI_low=np.exp(np.percentile(values, 2.5, axis=0)).tolist(),
                CI_high=np.exp(np.percentile(values, 97.5, axis=0)).tolist(),
                se=np.std(values, axis=0, ddof=1).tolist())


def run(dataset, reference, output):
    if output.resolve().is_relative_to((ROOT/'reproducibility/frozen').resolve()):
        raise ValueError('Frozen evidence is read-only')
    output.mkdir(parents=True, exist_ok=False)
    source = ROOT/'analysis/core/05_bootstrap_and_ipw.py'
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = list(csv.DictReader((ROOT/'reproducibility/source_manifest.csv').open()))
    expected = next(r['sha256'] for r in manifest if r['repository_path']=='analysis/core/05_bootstrap_and_ipw.py')
    if source_sha != expected:
        raise ValueError('Analytical source does not match its preserved hash')
    ns, node = functions_from_source(source)
    fit, last = instrument_irls(node, ns)
    md = pd.read_csv(dataset, parse_dates=['date'])
    ref = pd.read_csv(reference)
    rng = np.random.default_rng(ns['SEED'] + 1)
    info = dict(scope='POST_PUBLICATION_VALIDATION', started_utc=datetime.now(timezone.utc).isoformat(),
                source_sha256=source_sha, dataset_sha256=hashlib.sha256(dataset.read_bytes()).hexdigest(),
                reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
                initial_seed=ns['SEED']+1, requested_per_variant=2000,
                max_iterations=200, step_tolerance=1e-9, variants={})
    fields = ['variant','replicate','n_rows','events','iterations','termination','criterion_met',
              'original_ok','original_accepted','rejection_reason','terminal_step',
              *['beta_'+str(i) for i in range(9)]]
    with (output/'replicates.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n');writer.writeheader()
        for variant, wcol in ns['WELL_Z'].items():
            d = ns['cc_frame'](md, wcol);X, names = ns['design_matrix'](d,wcol)
            y = d['onset_day'].to_numpy(dtype=float)
            accepted, criterion = [], [];term_counts={};nonconverged_accepted=0
            for b in range(2000):
                idx = ns['player_cluster_indices'](d,rng)
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', RuntimeWarning)
                    beta, ok = fit(X[idx],y[idx],firth=True,max_iter=200)
                # Identical original acceptance rule; finite-state audit is separate.
                keep = beta is not None and not np.any(np.abs(beta)>20)
                finite = beta is not None and bool(np.isfinite(beta).all())
                independent = last['criterion_met'] and finite
                reason = 'singular_information' if beta is None else 'coefficient_limit' if not keep else ''
                if keep:
                    accepted.append(beta.copy());nonconverged_accepted += not independent
                if independent and keep:criterion.append(beta.copy())
                term_counts[last['termination']]=term_counts.get(last['termination'],0)+1
                row=dict(variant=variant,replicate=b,n_rows=len(idx),events=int(y[idx].sum()),
                         **last,original_accepted=bool(keep),rejection_reason=reason)
                row.update({'beta_'+str(i):float(v) for i,v in enumerate(beta if beta is not None else np.full(9,np.nan))})
                writer.writerow(row)
                if (b+1)%500==0:
                    stream.flush();print(variant,b+1,'/ 2000; accepted without criterion',nonconverged_accepted,flush=True)
            original_summary = summarize(np.asarray(accepted));strict_summary=summarize(np.asarray(criterion))
            rr=ref[ref.wellness_variant.eq(variant)].set_index('term')
            comparisons=[]
            for i,name in enumerate(names):
                for field in ('OR','CI_low','CI_high','se'):
                    a=float(rr.loc[name,field]);v=original_summary[field][i]
                    comparisons.append(abs(a-v)<=max(1e-8,1e-6*max(abs(a),abs(v))))
            info['variants'][variant]=dict(terms=names,completed=2000,original_accepted=len(accepted),
                original_rejected=2000-len(accepted),termination_counts=term_counts,
                accepted_without_convergence_criterion=int(nonconverged_accepted),
                convergence_criterion_accepted=len(criterion),
                reconstructed_original_summary=original_summary,
                criterion_only_diagnostic_summary=strict_summary,
                previous_fresh_summary_agreement=all(comparisons))
    info['ended_utc']=datetime.now(timezone.utc).isoformat()
    info['replicates_sha256']=hashlib.sha256((output/'replicates.csv').read_bytes()).hexdigest()
    (output/'summary.json').write_text(json.dumps(info,indent=2,allow_nan=False)+'\n')
    return info


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.dataset,args.reference,args.output)
    raise SystemExit(0 if all(v['previous_fresh_summary_agreement'] for v in result['variants'].values()) else 1)
