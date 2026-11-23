"""Portable entry points. Run with: uv run python scripts/pipeline.py --help.

Frozen scripts are staged in the ignored workspace. Only documented root paths
are relocated; frozen numerical results remain separate from fresh outputs.
"""
from pathlib import Path, PurePosixPath
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'workspace'
FR = WORK / 'r2'
SB = FR / '02_R1_REPRODUCTION/r1_sandbox'
FROZEN = ROOT / 'reproducibility/frozen'
PYTHON = sys.executable
SEED = 20260722

def configure_workspace(path):
    """Confine execution to an ignored directory, never a frozen input tree."""
    global WORK, FR, SB
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    base = ROOT / 'workspace'
    if base.is_symlink() or not candidate.is_relative_to(base):
        raise ValueError('Execution root must be inside the ignored repository workspace/')
    WORK = candidate
    FR = WORK / 'r2'
    SB = FR / '02_R1_REPRODUCTION/r1_sandbox'

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def record_execution(record):
    path = WORK / 'execution.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as out:
        out.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')

def claim_full_run(task):
    """Never mix full runs: several preserved workstreams append or resume."""
    marker = WORK / 'full_run.json'
    marker.parent.mkdir(parents=True, exist_ok=True)
    record = {'task': task, 'started_utc': utc_now(), 'seed': SEED,
              'status': 'RUNNING', 'r2_baseline': 'frozen R1, copied reference'}
    try:
        with marker.open('x') as out:
            json.dump(record, out, indent=2)
    except FileExistsError:
        raise ValueError('Full run already claimed this execution root. Rebuild in a new '
                         '--workspace directory; implicit resume is prohibited.') from None
    r1_outputs = SB / '07_ANALYSIS_OUTPUTS/RUN_PORTABLE'
    if (r1_outputs / 'r_results.csv').exists() or (FR / '17_MASTER_RESULTS/MASTER_RESULTS_R2.csv').exists():
        record['status'] = 'REFUSED_EXISTING_MODEL_OUTPUTS'
        write_json(marker, record)
        raise ValueError('Existing model outputs found; use a fresh --workspace directory')
    return marker, record

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def fingerprint(path):
    """Order-sensitive per-column digests; numerical values rounded to 8 decimals.

    Missingness is hashed explicitly. These are release checks against frozen
    derived data, not an inferential tolerance or a source-data anonymizer.
    """
    frame = pd.read_csv(path, low_memory=False)
    result = {'rows': len(frame), 'columns': list(frame.columns), 'column_digests': {}}
    for col in frame:
        s = frame[col]
        numeric = pd.api.types.is_numeric_dtype(s)
        vals = []
        for value in s:
            if pd.isna(value):
                vals.append('<MISSING>')
            elif numeric:
                x = round(float(value), 8)
                vals.append(f'{0.0 if x == 0 else x:.8f}')
            else:
                vals.append(str(value))
        payload = json.dumps(vals, ensure_ascii=False, separators=(',', ':')).encode()
        result['column_digests'][col] = hashlib.sha256(payload).hexdigest()
    return result

def run(argv, *, env=None, name=None):
    executable = argv[2] if len(argv)>2 and argv[1]=='--vanilla' else argv[1]
    logs = WORK / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    logfile = logs / (stamp + '_' + (name or Path(executable).stem)+'.log')
    logfile.parent.mkdir(parents=True, exist_ok=True)
    settings = os.environ.copy()
    settings.update({'SOCCERMON_EXECUTION_ROOT': str(WORK),
                     'SOCCERMON_WORKSPACE': str(SB), 'SOCCERMON_RUN_ID': 'RUN_PORTABLE',
                     'MPLBACKEND': 'Agg', 'MPLCONFIGDIR': str(WORK/'matplotlib'),
                     'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
    if env:
        settings.update(env)
    lib = Path(settings.get('SOCCERMON_R_LIBRARY', ROOT / 'workspace/R/library')).expanduser().resolve()
    settings.update({'SOCCERMON_R_LIBRARY': str(lib), 'R_LIBS_USER': str(lib),
                     'REANALYSIS_RESUME': '0'})
    record = {'kind': 'subprocess', 'argv': [str(x) for x in argv], 'cwd': str(ROOT),
              'started_utc': utc_now(), 'seed': SEED, 'log': str(logfile.relative_to(ROOT)),
              'R_library': str(lib)}
    print('Running:', ' '.join(str(x) for x in argv), flush=True)
    try:
        with logfile.open('x') as out:
            proc = subprocess.run([str(x) for x in argv], cwd=ROOT, env=settings,
                                  stdout=out, stderr=subprocess.STDOUT)
        record['exit_status'] = proc.returncode
    except BaseException as exc:
        record.update({'exit_status': None, 'error': f'{type(exc).__name__}: {exc}'})
        raise
    finally:
        record['ended_utc'] = utc_now()
        record_execution(record)
    if proc.returncode:
        print(logfile.read_text()[-7000:], file=sys.stderr)
        raise RuntimeError(f'Exit {proc.returncode}: {logfile.relative_to(ROOT)}')
    print('Completed:', logfile.relative_to(ROOT), flush=True)

def relocate(text, freeze_root):
    replacements = {
        'D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE': str(freeze_root),
        'D:/PLOS_ONE_R1_WORK/PONE-D-26-31950_PLOS_R1': str(SB),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def stage():
    for path in (FR/'18_LOGS', FR/'16_FOCAL_STABILITY', FR/'19_VALIDATION',
                 SB/'logs', SB/'02_RAW_DATA', SB/'07_ANALYSIS_OUTPUTS'):
        path.mkdir(parents=True, exist_ok=True)
    (SB/'RUN_ID.txt').write_text('RUN_PORTABLE\n')
    transformations = []
    for p in (ROOT/'analysis/sensitivity').rglob('*'):
        if p.suffix not in ('.py', '.R'):
            continue
        target = FR / p.relative_to(ROOT/'analysis/sensitivity')
        target.parent.mkdir(parents=True, exist_ok=True)
        source = p.read_text(encoding='utf-8-sig')
        staged = relocate(source, FR)
        changes = ['relocate documented Windows roots']
        if p.name == 'build_freeze_outputs.py':
            # These historical checks are read but never used by assembly.
            # Do not seed fresh R2 with stored validation outputs or imply
            # that historical raw-vs-derived gates ran in this execution.
            for line in ('gateA     = rd("19_VALIDATION/R1_REPRODUCTION_CHECK.csv")',
                         'gateB     = rd("19_VALIDATION/RAW_VS_DERIVED_RECONCILIATION.csv")'):
                if staged.count(line) != 1:
                    raise ValueError('Historical assembly source changed: '+line)
                staged = staged.replace(line, '# Portable staging: omitted unused historical gate read')
            changes.append('omit two unused historical validation reads; no analysis/result change')
        target.write_text(staged)
        transformations.append({'source': str(p.relative_to(ROOT)), 'source_sha256': sha(p),
                                'staged': str(target.relative_to(ROOT)),
                                'staged_sha256': sha(target), 'changes': changes})
    write_json(WORK/'portable_source_transformations.json', transformations)
    # R2 comparisons explicitly use frozen R1 baseline outputs, never claim
    # these files were regenerated by this staging operation.
    reference_run = SB/'07_ANALYSIS_OUTPUTS/RUN_R2_REPRO'
    reference_run.mkdir(parents=True, exist_ok=True)
    for p in (FROZEN/'r1').iterdir():
        if p.is_file():
            shutil.copyfile(p, reference_run/p.name)
    for folder in ('04_ANALYSIS_TAXONOMY', '12_POLARITY_AUDIT'):
        dest = FR/folder
        dest.mkdir(parents=True, exist_ok=True)
        for p in (FROZEN/folder).iterdir():
            shutil.copyfile(p, dest/p.name)
    write_json(WORK/'baseline_origin.json', {
        'r2_baseline': 'frozen RUN_R2_REPRO; copied, not refitted',
        'fresh_r1_run': 'RUN_PORTABLE', 'seed': SEED,
    })

def raw_archive(source=None):
    target = WORK/'downloads/subjective.zip'
    expected = (ROOT/'data/subjective.zip.sha256').read_text().split()[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    if source:
        src = Path(source).expanduser().resolve()
        if sha(src) != expected:
            raise ValueError('Supplied subjective.zip SHA-256 differs from frozen input')
        if src != target:
            shutil.copyfile(src, target)
    elif not target.exists() or sha(target) != expected:
        url = 'https://zenodo.org/records/10033832/files/subjective.zip?download=1'
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = response.read()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError('Downloaded subjective.zip SHA-256 differs from frozen input')
        target.write_bytes(payload)
    if sha(target) != expected:
        raise ValueError('Cached raw archive failed SHA-256 verification')
    dest = SB/'02_RAW_DATA/subjective_readonly_work'
    with zipfile.ZipFile(target) as archive:
        for member in archive.infolist():
            path = PurePosixPath(member.filename)
            if path.is_absolute() or '..' in path.parts or ((member.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Unsafe ZIP member: '+member.filename)
            if member.is_dir():
                continue
            output = dest.joinpath(*path.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(member))
    write_json(WORK/'raw_input.json', {'doi':'10.5281/zenodo.10033832', 'sha256':expected,
                                     'bytes':target.stat().st_size})

def rebuild(source=None):
    stage()
    raw_archive(source)
    for name in ('01_raw_audit_and_rebuild.py', '02_episodes_and_modeling_data.py', '03_missingness_ipw.py'):
        run([PYTHON, ROOT/'analysis/core'/name])
    verify_data()

def verify_data():
    expected = json.loads((ROOT/'reproducibility/data_fingerprints.json').read_text())
    checks = []
    for rel, ref in expected.items():
        p = SB/rel
        if not p.exists():
            checks.append({'file':rel,'status':'FAIL','reason':'missing derived output'})
            continue
        actual = fingerprint(p)
        changed = [c for c in ref['columns'] if actual['column_digests'].get(c) != ref['column_digests'][c]]
        ok = actual['rows']==ref['rows'] and actual['columns']==ref['columns'] and not changed
        checks.append({'file':rel,'status':'PASS' if ok else 'FAIL','rows':actual['rows'],
                       'columns':len(actual['columns']),'differing_columns':changed})
    write_json(WORK/'validation/data_rebuild.json', checks)
    print(json.dumps(checks, indent=2))
    if any(x['status']!='PASS' for x in checks):
        raise ValueError('Derived data differ from frozen 8-decimal column fingerprints')

def verify_frozen():
    rows = list(csv.DictReader((ROOT/'reproducibility/source_manifest.csv').open()))
    bad = [r['repository_path'] for r in rows if not (ROOT/r['repository_path']).is_file()
           or sha(ROOT/r['repository_path']) != r['sha256']]
    if bad:
        raise ValueError('Source manifest mismatch: '+str(bad))
    sap = ROOT/'protocol/revision_sap'
    sap_hashes = (sap/'SAP_FREEZE_HASH.txt').read_text().splitlines()
    for line in sap_hashes:
        if ': ' in line and not line.startswith('composite_sha256'):
            name, digest = line.split(': ', 1)
            if name.endswith(('.csv','.md')) and sha(sap/name) != digest.strip():
                raise ValueError('SAP hash mismatch: '+name)
    registry = pd.read_csv(FROZEN/'17_MASTER_RESULTS/MODEL_REGISTRY.csv')
    master = pd.read_csv(FROZEN/'17_MASTER_RESULTS/MASTER_RESULTS_R2.csv')
    if len(master)!=678:
        raise ValueError('Frozen master row count changed')
    audit = WORK/'frozen_audit'
    shutil.copytree(FROZEN, audit, dirs_exist_ok=True)
    r1 = audit/'02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_R2_REPRO'
    shutil.copytree(FROZEN/'r1', r1, dirs_exist_ok=True)
    script = audit/'20_FREEZE/build_validation.py'
    script.parent.mkdir(parents=True, exist_ok=True)
    source = ROOT/'analysis/sensitivity/20_FREEZE/build_validation.py'
    script.write_text(relocate(source.read_text(), audit))
    run([PYTHON, script], name='verify_frozen')
    checks = pd.read_csv(audit/'19_VALIDATION/NUMERIC_CONSISTENCY_CHECK.csv')
    if len(checks)!=54 or not checks.status.eq('PASS').all():
        raise ValueError('Frozen numerical consistency checks failed')
    summary = {'source_files_verified':len(rows),'sap_hashes_verified':True,
               'frozen_master_rows':len(master),'frozen_registry_rows':len(registry),
               'reexecuted_frozen_consistency_checks':len(checks),'status':'PASS',
               'scope':'Fresh checks of stored results; models and bootstrap were not refitted.'}
    write_json(WORK/'validation/frozen_audit.json', summary)
    print(json.dumps(summary, indent=2))

def diagnostics():
    stage()
    # Diagnostic source scripts use these frozen R1 inventories and freshly
    # reconstructed data. No frozen R2 diagnostic outputs are preloaded.
    for rel in ('05_SAMPLE_EVENT_AUDIT/run_sample_event_audit.py',
                '06_SPARSE_DATA/run_sparse_data_diagnostics.py',
                '07_COLLINEARITY/run_collinearity_9_3.py',
                '08_NONOVERLAP_WINDOW/run_nonoverlap_window.py',
                '11_BACKWARD_STANDARDIZATION/run_backward_standardization.py'):
        run([PYTHON, FR/rel])
    verify_sensitivity_data()

def verify_sensitivity_data():
    expected = json.loads((ROOT/'reproducibility/sensitivity_fingerprints.json').read_text())
    checks = []
    for rel, ref in expected.items():
        actual = fingerprint(FR/rel)
        changed = [c for c in ref['columns'] if actual['column_digests'].get(c)!=ref['column_digests'][c]]
        checks.append({'file':rel,'rows':actual['rows'],'columns':len(actual['columns']),
                       'differing_columns':changed,'status':'PASS' if actual==ref else 'FAIL'})
    write_json(WORK/'validation/sensitivity_data.json',checks)
    if any(x['status']!='PASS' for x in checks):
        raise ValueError('Sensitivity-data fingerprints differ from frozen values')
    print('Sensitivity data: 2 frozen fingerprint checks PASS')

def r_run(script, name=None):
    # Prepend the explicitly selected local library before source-level
    # library() calls. This also survives a site configuration that rewrites
    # R_LIBS_USER. Analysis scripts and formulas remain unchanged.
    expression = ('lib <- Sys.getenv("SOCCERMON_R_LIBRARY"); '
                  'if (dir.exists(lib)) .libPaths(c(normalizePath(lib), .libPaths())); '
                  'source('+json.dumps(str(script))+', chdir=FALSE)')
    run(['Rscript', '--vanilla', '-e', expression], name=name or Path(script).stem)

def focus():
    if not (FR/'11_BACKWARD_STANDARDIZATION/modeling_dataset_backwardz.csv').exists():
        diagnostics()
    r_run(ROOT/'scripts/refit_focus.R')
    result = pd.read_csv(WORK/'validation/focal_refits.csv')
    if len(result)!=4 or not result.status.eq('PASS').all():
        raise ValueError('Focal Firth model refits differ from frozen results')
    print(result.to_string(index=False))

def figures():
    """Run the preserved manuscript figure script against fresh R1 results."""
    fresh = SB/'07_ANALYSIS_OUTPUTS/RUN_PORTABLE/master_results.csv'
    if not fresh.is_file():
        raise ValueError('Fresh finalized R1 master_results.csv is required for figures')
    source = ROOT/'analysis/reporting/06b_make_figures.py'
    staged = WORK/'reporting/06b_make_figures.py'
    staged.parent.mkdir(parents=True, exist_ok=True)
    text = relocate(source.read_text(encoding='utf-8-sig'), FR)
    text = text.replace('"RUN_20260722_151418"', '"RUN_PORTABLE"')
    # The retained figure source checks an obsolete `washout` column. The
    # actual archived/rebuilt schema uses `washout_days`; its fallback would
    # otherwise plot all three washouts while labeling the plot as seven days.
    old = 'o = onset[(onset["washout"] == 7) & (onset["scope"] == "lower_limb")] if "washout" in onset.columns else onset.copy()'
    if text.count(old) != 1:
        raise ValueError('Reporting source changed; review the 7-day schema adaptation')
    text = text.replace(old, 'o = onset.loc[onset["washout_days"].eq(7)].copy()')
    text = text.replace('Interaction odds ratio (acute load × soreness burden), log scale',
                        'Interaction effect ratio (logistic OR / Cox HR), log scale')
    staged.write_text(text)
    write_json(WORK/'reporting/provenance.json', {
        'source': str(source.relative_to(ROOT)), 'source_sha256': sha(source),
        'staged_sha256': sha(staged), 'input': str(fresh.relative_to(ROOT)),
        'input_sha256': sha(fresh), 'transformations': ['relocate Windows root',
                                                       'select fresh RUN_PORTABLE',
                                                       'select washout_days=7 using actual archived input schema',
                                                       'label logistic OR and Cox HR distinctly in mixed-estimator forest']})
    run([PYTHON, staged], name='fresh_manuscript_figures')
    folder = SB/'10_FIGURES'
    onset = pd.read_csv(folder/'Fig1_data.csv')
    episodes = pd.read_csv(folder/'Fig2_data.csv')
    params = json.loads((folder/'Fig3_params.json').read_text())
    x = pd.read_csv(folder/'Fig3_data.csv')['acute_z'].to_numpy()
    curves = []
    for soreness in (-1, 0, 1):
        logit = (params['intercept'] + params['logit_offset'] + params['acute']*x
                 + params['soreness']*soreness + params['interaction']*x*soreness)
        curves.extend({'acute_z': float(a), 'soreness_z': soreness,
                       'conditional_probability_percent': float(b)}
                      for a, b in zip(x, 100/(1+np.exp(-logit))))
    pd.DataFrame(curves).to_csv(folder/'Fig3_curves.csv', index=False)
    checks = {'Fig1_onset_days': len(onset),
              'Fig1_unique_player_dates': len(onset.drop_duplicates(['player_id','date'])),
              'Fig2_event_players': len(episodes),
              'Fig2_total_episodes': int(episodes['ll_episodes_7d'].sum()),
              'Fig2_maximum_episodes': int(episodes['ll_episodes_7d'].max())}
    expected = dict(zip(checks, (52, 52, 15, 92, 45)))
    write_json(WORK/'validation/figure_data.json', [
        {'check': key, 'observed': value, 'expected': expected[key],
         'status': 'PASS' if value == expected[key] else 'FAIL'}
        for key, value in checks.items()])
    if checks != expected:
        raise ValueError('Fresh manuscript figure data differ from published count targets')

def full_r1():
    stage()
    helper = ROOT/'analysis/core/05_bootstrap_and_ipw.py'
    for arg in ('prep','ipw'):
        run([PYTHON,helper,arg], name='r1_'+arg)
    r_run(ROOT/'analysis/core/04_run_reanalysis.R', name='r1_models')
    for arg in ('bootstrap','firth_boot','finalize'):
        run([PYTHON,helper,arg], name='r1_'+arg)
    print('Fresh R1 results:', SB/'07_ANALYSIS_OUTPUTS/RUN_PORTABLE')
    print('Compare these against reproducibility/frozen/r1 before interpreting differences.')

def full_r2():
    stage()
    commands = [
      '05_SAMPLE_EVENT_AUDIT/run_sample_event_audit.py','06_SPARSE_DATA/run_sparse_data_diagnostics.py',
      '07_COLLINEARITY/run_collinearity_9_3.py','08_NONOVERLAP_WINDOW/run_nonoverlap_window.py',
      '08_NONOVERLAP_WINDOW/run_nonoverlap_models.R','08_NONOVERLAP_WINDOW/run_nonoverlap_boot.py',
      '09_TEAM_SENSITIVITY/run_drop_team.R','09_TEAM_SENSITIVITY/run_drop_team_boot.py',
      '09_TEAM_SENSITIVITY/assemble_drop_team_table.R','10_SEASON_SENSITIVITY/run_season_stability.R',
      '11_BACKWARD_STANDARDIZATION/run_backward_standardization.py',
      '11_BACKWARD_STANDARDIZATION/run_backwardz_models.R','11_BACKWARD_STANDARDIZATION/run_backwardz_firth_maxit.R',
      '13_IPW_FINAL/run_ipw_final.py','13_IPW_FINAL/run_ipw_final.R','13_IPW_FINAL/run_ipw_final.py',
      '14_EVENT_INFLUENCE/run_leave_one_out_qa.R','14_EVENT_INFLUENCE/run_event_concentration.py',
      '20_FREEZE/build_freeze_outputs.py',
    ]
    # Stage 05 reconstructs the weight files needed by the R2 IPW checks; it
    # writes to RUN_PORTABLE, which is copied as the weight input only.
    helper = ROOT/'analysis/core/05_bootstrap_and_ipw.py'
    run([PYTHON,helper,'prep'],name='r2_baseline_prep')
    run([PYTHON,helper,'ipw'],name='r2_baseline_ipw')
    for p in (SB/'07_ANALYSIS_OUTPUTS/RUN_PORTABLE').glob('ipw_weights_*.csv'):
        shutil.copyfile(p, SB/'07_ANALYSIS_OUTPUTS/RUN_R2_REPRO'/p.name)
    ipw_stages = iter(('stage1', 'finalize'))
    for rel in commands:
        if rel.endswith('.R'):
            r_run(FR/rel)
        else:
            # IPW stage 1 / stage 2 are selected explicitly by its CLI.
            extra = [next(ipw_stages)] if rel=='13_IPW_FINAL/run_ipw_final.py' else []
            run([PYTHON,FR/rel,*extra])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task',choices=['verify-frozen','rebuild','verify-data','verify-sensitivity-data','diagnostics','refit-focus','r1-full','r2-full','figures','plot'])
    parser.add_argument('--raw-zip',help='Local subjective.zip; otherwise download the documented public input')
    parser.add_argument('--workspace', default=os.environ.get('SOCCERMON_EXECUTION_ROOT', 'workspace'),
                        help='Independent execution root inside ignored repository workspace/')
    args = parser.parse_args()
    configure_workspace(args.workspace)
    functions = {'verify-frozen':verify_frozen,'rebuild':lambda:rebuild(args.raw_zip),
                 'verify-data':verify_data,'verify-sensitivity-data':verify_sensitivity_data,
                 'diagnostics':diagnostics,'refit-focus':focus,
                 'r1-full':full_r1,'r2-full':full_r2,
                 'figures': figures,
                 'plot':lambda:run([PYTHON,ROOT/'scripts/plot_focal_results.py'])}
    record = {'kind': 'pipeline', 'task': args.task, 'argv': sys.argv,
              'execution_root': str(WORK), 'started_utc': utc_now(), 'seed': SEED}
    marker = None
    try:
        if args.task in ('r1-full', 'r2-full'):
            marker, full_record = claim_full_run(args.task)
        functions[args.task]()
        record['exit_status'] = 0
    except BaseException as exc:
        record.update({'exit_status': 1, 'error': f'{type(exc).__name__}: {exc}'})
        raise
    finally:
        record['ended_utc'] = utc_now()
        record_execution(record)
        if marker is not None:
            full_record.update({'ended_utc': record['ended_utc'],
                                'status': 'COMPLETED' if record['exit_status'] == 0 else 'INCOMPLETE',
                                'exit_status': record['exit_status']})
            write_json(marker, full_record)

if __name__=='__main__':
    main()
