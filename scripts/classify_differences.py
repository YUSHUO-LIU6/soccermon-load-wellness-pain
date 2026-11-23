"""Assign scientific-impact classes without changing strict comparison outcomes.

A: protected scientific contrast discrepancy; B: estimation/optimizer sensitivity;
C: small numerical drift; D: ordering/duplicate/structural artifact;
E: diagnostic annotation. Classification is an interpretation layer, never PASS.
"""
import argparse
import ast
from collections import Counter
import csv
import json
from pathlib import Path
import math

ROOT=Path(__file__).resolve().parents[1]
NUMERIC={'OR','CI_low','CI_high','p','se','delta_logOR','abs_delta_logOR','pct_change_logOR'}
PROTECTED={'F','F_hist','F_nonoverlap','F_nonoverlap_dropteam','F_drop_team','F_drop_season','F_boot','A_boot','A_drop_team_boot','A_nonoverlap_dropteam_boot'}


def classify(file,item,check,models):
    if item in {'event_rank_in_scope','cumulative_pct'}:
        return 'D','Tied event counts have no stable secondary sort; individual counts and event totals are unchanged.'
    if 'diagnostics.csv' in file and check=='structure':
        return 'D','Frozen append/resume artifacts repeat DATA records; clean-run duplicate multiplicities differ.'
    if models & PROTECTED and (item in NUMERIC or check=='structure'):
        return 'A','A protected scientific contrast or its row structure differs; direct scientific review is required.'
    if file.startswith('r1/') and models == {'E'} and (check=='structure' or 'model_inventory' in file or 'diagnostic_inventory' in file):
        return 'B','Ancillary E/readiness changes from historical failure to warning-bearing returned coefficients; alias diagnostics also differ. Neither state proves convergence.'
    if item in NUMERIC and models & PROTECTED:
        return 'A','A protected Firth/bootstrap contrast differs; requires direct scientific review before release.'
    if 'E' in models:
        return 'B','Gamma-frailty fits have inner-loop convergence warnings and aliasing in both environments; do not interpret new coefficients or borderline CI changes as independent evidence.'
    if 'A_drop_team_season' in models or item in {'direction','language_flags'}:
        return 'B','Joint team/season-removal internal-QA GLMM is optimizer-sensitive, including an event-history direction change; it is excluded from the published scientific model space.'
    if item not in NUMERIC:
        return 'E','Diagnostic/provenance annotation differs (including printed refit agreement); underlying numeric fields are assessed separately.'
    if any('_REJECTED_' in m for m in models):
        return 'B','Rejected or separated fallback coefficients are optimizer-sensitive and retained solely for transparency; accepted-model estimates are assessed separately.'
    if not models:
        return 'E','Unclassified numerical or structural evidence requires review; no precision explanation is assumed.'
    return 'C','Matched accepted fits show numerical drift above the unchanged strict tolerance; magnitude and null-crossing checks are retained in the impact ledger.'


def read(path):
    with path.open(newline='',encoding='utf-8-sig') as stream:return list(csv.DictReader(stream))


def detail_models(detail,root):
    label=detail['file'].split(':',1)[0]
    path=root/'reproducibility/frozen'/label
    if path.suffix=='.json':path=path.with_suffix('.csv')
    if not path.exists():return set()
    with path.open(newline='',encoding='utf-8-sig') as stream:cols=next(csv.reader(stream))
    from verify_results import IDENTITY_COLUMNS
    keys=[c for c in cols if c in IDENTITY_COLUMNS]
    identity=dict(zip(keys,ast.literal_eval(detail['key'])))
    return {identity['model_id']} if 'model_id' in identity else set()


def structural_models(file, root):
    if not file.startswith('r1/'):
        return set()
    label=file.split(':',1)[0].replace('.json','.csv')
    ref=root/'reproducibility/frozen'/label
    fresh=root/'workspace/r1_20261123/r2/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_PORTABLE'/Path(label).name
    if not ref.exists() or not fresh.exists():return set()
    a,b=read(ref),read(fresh)
    from verify_results import IDENTITY_COLUMNS
    keys=[c for c in a[0] if c in IDENTITY_COLUMNS]
    if 'model_id' not in keys:return set()
    ca=Counter(tuple(row[c] for c in keys) for row in a)
    cb=Counter(tuple(row[c] for c in keys) for row in b)
    return {k[keys.index('model_id')] for k in ca.keys()|cb.keys() if ca[k]!=cb[k]}


def run(root=ROOT):
    gates=read(root/'reports/RESULT_COMPARISON.csv');details=read(root/'reports/NUMERICAL_DISCREPANCIES.csv')
    output=[]
    for row in gates:
        if row['status']!='FAIL':continue
        matching=[d for d in details if d['file']==row['file'] and d['field']==row['item']]
        models=set().union(*(detail_models(d,root) for d in matching)) if matching else set()
        if row['check']=='structure':models |= structural_models(row['file'],root)
        category,explanation=classify(row['file'],row['item'],row['check'],models)
        output.append(dict(scope=row['scope'],file=row['file'],check=row['check'],item=row['item'],
            strict_status='FAIL',impact_class=category,models=';'.join(sorted(models)),
            explanation=explanation,primary_contrast_affected='REVIEW' if category=='A' else 'No observed protected-contrast discrepancy',
            max_abs_difference=row['max_abs_difference'],max_rel_difference=row['max_rel_difference']))
    path=root/'reports/FAIL_IMPACT_CLASSIFICATION.csv'
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(output[0]),lineterminator='\n');writer.writeheader();writer.writerows(output)
    summary={'scope':'Interpretation of unchanged strict FAIL outcomes; no tolerance/reference modification',
             'strict_fail_gates':len(output),'impact_class_counts':dict(Counter(r['impact_class'] for r in output)),
             'protected_contrast_discrepancy_gates':sum(r['impact_class']=='A' for r in output)}
    (root/'reports/FAIL_IMPACT_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
    return output


if __name__=='__main__':run()
