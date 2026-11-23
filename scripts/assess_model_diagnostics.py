"""Conservative diagnostic overlay; never rewrite historical convergence flags."""
import csv
import json
import math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def assess(status, warnings=(), optimizer_code=None, derivatives=None):
    if status.startswith('FAILED'):
        return 'HISTORICAL_FAILURE'
    if warnings:
        return 'WARNED_UNVERIFIED'
    if optimizer_code not in (None,0):
        return 'OPTIMIZER_FAILURE'
    if not derivatives:
        return 'UNVERIFIED_NO_DERIVATIVES'
    eigenvalues=derivatives.get('Hessian_eigenvalues')
    scaled=derivatives.get('scaled_gradient')
    if not eigenvalues or not all(math.isfinite(x) for x in eigenvalues) or min(eigenvalues)<=0 or not scaled or not all(math.isfinite(x) for x in scaled):
        return 'STATIONARITY_UNVERIFIED'
    if max(abs(x) for x in scaled)>0.002:
        return 'STATIONARITY_UNVERIFIED'
    return 'NUMERICAL_CHECKS_PASSED'


def read(path):
    with path.open(newline='',encoding='utf-8-sig') as stream:return list(csv.DictReader(stream))


def main():
    roots={'frozen':ROOT/'reproducibility/frozen/r1',
           'fresh':ROOT/'workspace/r1_20261123/r2/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_PORTABLE'}
    out=[]
    for scope,folder in roots.items():
        inventory=read(folder/'model_inventory.csv');diagnostics=read(folder/'diagnostic_inventory.csv')
        for row in inventory:
            if row['model_id']!='E':continue
            relevant=[d for d in diagnostics if d['model_id']=='E' and d['wellness_variant']==row['wellness_variant']]
            warns=[d['value'] for d in relevant if d['diagnostic']=='frailty_warnings']
            out.append(dict(scope=scope,model='E',variant=row['wellness_variant'],
                reported_status=row['status'],assessment=assess(row['status'],warns),
                evidence='; '.join([row['fail_reason'],*[d['diagnostic']+': '+d['value'] for d in relevant]])))
    fits=json.loads((ROOT/'reports/QA_GLMM_DIAGNOSTICS.json').read_text())
    derivative=json.loads((ROOT/'reports/QA_GLMM_STATIONARITY.json').read_text())
    for tag,fit in fits['fits'].items():
        d=derivative['fits'][tag]
        out.append(dict(scope='post-publication',model='A_drop_team_season',variant=tag,
            reported_status='optimizer code '+str(fit['optimizer_code']),
            assessment=assess('RETURNED',fit['warnings'],fit['optimizer_code'],d),
            evidence='Recomputed deviance matches stored fit; Richardson Hessian is not positive definite; initializations reach different returned coefficients/likelihoods. Numerical derivatives are diagnostic, not a global-optimum certificate.'))
    with (ROOT/'reports/MODEL_DIAGNOSTIC_ASSESSMENT.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(out[0]),lineterminator='\n');writer.writeheader();writer.writerows(out)
    print('Recorded',len(out),'diagnostic assessments; historical files unchanged')


if __name__=='__main__':main()
