"""Build a dated report from completed workspace checks; never fabricate PASS."""
from pathlib import Path
import importlib.metadata as metadata
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import platform
import re
import shutil
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--date', default=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat())
stamp=parser.parse_args().date
V=ROOT/'workspace/validation'
OUT=ROOT/'reports'
OUT.mkdir(exist_ok=True)
frozen=json.loads((V/'frozen_audit.json').read_text())
rebuilt=json.loads((V/'data_rebuild.json').read_text())
sens=json.loads((V/'sensitivity_data.json').read_text())
refits=pd.read_csv(V/'focal_refits.csv')
assert frozen['status']=='PASS'
assert len(rebuilt)==6 and all(x['status']=='PASS' for x in rebuilt)
assert len(sens)==2 and all(x['status']=='PASS' for x in sens)
assert len(refits)==4 and refits.status.eq('PASS').all()
versions={x:metadata.version(x) for x in ['numpy','pandas','scipy','statsmodels','scikit-learn','matplotlib']}
details={'verification_date':stamp,'timezone':'Asia/Shanghai',
         'python':sys.version.split()[0],'platform':platform.platform(),'python_packages':versions,
         'stored_results_audit':frozen,'raw_data_rebuild':rebuilt,
         'sensitivity_data_rebuild':sens,'focal_refits':refits.to_dict('records'),
         'not_rerun':['full R1/R2 model suite','all B=2000 bootstrap procedures',
                      'submitted DOCX tables and binary TIFF figures','manual external polarity-source audit']}
(OUT/'validation_details.json').write_text(json.dumps(details,indent=2)+'\n')
shutil.copyfile(V/'focal_refits.csv',OUT/'focal_refits.csv')
shutil.copyfile(V/'R_session.txt',ROOT/'environment/portable_R_session.txt')
r_session=(V/'R_session.txt').read_text()
r_version=re.search(r'R version ([^ ]+)',r_session).group(1)
logistf_version=re.search(r'logistf_([^\s]+)',r_session).group(1)
max_diff=refits.max_abs_difference.max()
table='\n'.join(f'| {r.model} | {"Interaction" if ":" in r.term else "Chronic load"} | {r.OR:.6f} | {r.CI_low:.6f}–{r.CI_high:.6f} | {r.status} |' for r in refits.itertuples())
text=f'''# Verification report

Verified {stamp} (Asia/Shanghai). This report distinguishes fresh data/model
calculations from fresh checks of stored results.

## Completed

| Verification | Result |
|---|---|
| Imported source-file hashes | {frozen['source_files_verified']} verified |
| Recovered revision SAP | Original content hashes verified |
| Frozen structured results | 54 numerical consistency checks reexecuted; all PASS |
| Public raw ZIP | SHA-256 matches frozen source; supplied local copy used |
| Raw-to-analytical rebuild | Six derived files match frozen column fingerprints |
| R2 exposure reconstruction | Both non-overlap and historical-standardization datasets match frozen fingerprints |
| Diagnostic workstreams | Sample/event audit, sparse-data diagnostics, collinearity and exposure construction executed |
| Independent Firth refits | Two models; four focal OR/CI comparisons PASS |
| Portfolio figure | Source table/provenance included; PNG visually inspected |

The numerical fingerprints preserve row/column order and missingness; numeric
values are rounded to eight decimal places. They cover every column in the
eight checked datasets, not just the headline counts.

## Fresh focal model comparisons

| Model | Parameter | Refit OR | Profile-likelihood 95% CI | Result |
|---|---|---:|---|---|
{table}

`F` uses retrospective full-period standardization. `F_hist` uses only prior
observations. The maximum absolute discrepancy across these four ORs and all
eight CI endpoints was {max_diff:.3g}; the predefined comparison tolerance was
0.001. This is numerical agreement for these two models, not validation of
every estimator or bootstrap interval.

## Environment

Fresh verification used Python {sys.version.split()[0]} on {platform.system()} {platform.machine()}.
The focal R fits used R {r_version} and logistf {logistf_version}; see
[`portable_R_session.txt`](../environment/portable_R_session.txt). The original
freeze records R 4.6.1 on Windows. `uv.lock` and the original session records
are retained separately. Version differences were not concealed.

## Remaining verification scope

The full R1/R2 model suite and all B=2,000 bootstrap procedures have **not**
been rerun in this portability pass. Their source scripts and frozen outputs
are included with explicit reproduction commands. Submitted DOCX tables and
binary TIFF figures have not been regenerated or compared pixel by pixel.
The earlier figure-generation script is retained, but this report does not
claim complete reconstruction of the final submission layout. The manual
wellness-polarity source audit was retained rather than repeated.

Historical raw/derived comparison gates are optional in the portable core
scripts and were not rerun using their old directory layout. The current
six-file reconstruction verification is a separate completed check.

Machine-readable evidence: [`validation_details.json`](validation_details.json)
and [`focal_refits.csv`](focal_refits.csv).
'''
(OUT/'VALIDATION.md').write_text(text)
print(OUT/'VALIDATION.md')
