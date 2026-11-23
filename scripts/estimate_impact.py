"""Inspect direction/null-interval changes for matched numerical estimates."""
import csv
from pathlib import Path
from verify_results import compare_value, number
ROOT=Path(__file__).resolve().parents[1]
TABLES=['r1/r_results.csv','08_NONOVERLAP_WINDOW/NONOVERLAP_WINDOW_RESULTS.csv',
'09_TEAM_SENSITIVITY/drop_team_model_rows.csv','10_SEASON_SENSITIVITY/SEASON_STABILITY.csv',
'11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv','13_IPW_FINAL/IPW_FINAL_RESULTS.csv']


def read(path):
    with path.open(newline='',encoding='utf-8-sig') as stream:return list(csv.DictReader(stream))


def ratio_state(row):
    x=number(row['OR'])
    if x is None or x<=0:return 'not_estimable'
    return 'above_one' if x>1 else 'below_one' if x<1 else 'one'


def interval_state(row):
    lo,hi=number(row['CI_low']),number(row['CI_high'])
    if lo is None or hi is None or lo<=0 or hi<=0:return 'not_estimable'
    return 'includes_one' if lo<=1<=hi else 'excludes_one'


def main():
    output=[]
    for table in TABLES:
        ref=ROOT/'reproducibility/frozen'/table
        fresh=(ROOT/'workspace/r1_20261123/r2/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_PORTABLE'/Path(table).name
               if table.startswith('r1/') else ROOT/'workspace/r2_20261123/r2'/table)
        def keyed(rows):return {(r['model_id'],r['wellness_variant'],r['term']):r for r in rows}
        a,b=keyed(read(ref)),keyed(read(fresh))
        for key in sorted(a.keys() & b.keys()):
            if key[0].startswith(('CMP_','SUMMARY')):continue
            x,y=a[key],b[key]
            if all(compare_value(x.get(f),y.get(f))[0] for f in ['OR','CI_low','CI_high','p','se']):continue
            output.append(dict(source=table,model=key[0],variant=key[1],term=key[2],
                frozen_OR=x['OR'],fresh_OR=y['OR'],frozen_CI_low=x['CI_low'],fresh_CI_low=y['CI_low'],
                frozen_CI_high=x['CI_high'],fresh_CI_high=y['CI_high'],
                frozen_direction=ratio_state(x),fresh_direction=ratio_state(y),
                frozen_interval=interval_state(x),fresh_interval=interval_state(y),
                direction_changed=ratio_state(x)!=ratio_state(y),interval_state_changed=interval_state(x)!=interval_state(y),
                interpretation='Unverified frailty / rejected fallback; no new scientific inference' if key[0]=='E' or '_REJECTED_' in key[0] else
                               'Internal QA; excluded from published scientific model space' if x.get('taxonomy')=='R2_INTERNAL_QA_ONLY' else
                               'Retained sensitivity; strict numerical differences remain'))
    with (ROOT/'reports/ESTIMATE_IMPACT.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(output[0]),lineterminator='\n');writer.writeheader();writer.writerows(output)
    print('Affected matched estimates:',len(output))
    for r in output:
        if r['direction_changed'] or r['interval_state_changed']:
            print(r['model'],r['variant'],r['term'],r['frozen_direction'],r['fresh_direction'],r['frozen_interval'],r['fresh_interval'])


if __name__=='__main__':main()
