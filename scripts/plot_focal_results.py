"""Plot frozen Firth estimates with their reported profile-likelihood 95% CIs."""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT/'reproducibility/frozen'
OUT = ROOT/'reports'
OUT.mkdir(exist_ok=True)
specs = [
    ('Retrospective full-period', 'r1/r_results.csv', 'F', ''),
    ('Prior observations only', '11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv', 'F_hist', '_hist'),
]
rows = []
for label, path, mid, suffix in specs:
    data = pd.read_csv(FROZEN/path)
    terms = {'Acute load × soreness':f'acute_load_7d_wp_z{suffix}:soreness_burden_recent3_wp_z{suffix}',
             'Chronic load':f'chronic_load_28d_wp_z{suffix}'}
    for panel, term in terms.items():
        selected = data[(data.model_id==mid)&(data.wellness_variant=='soreness')&(data.term==term)]
        if len(selected)!=1:
            raise ValueError(f'Expected exactly one frozen row: {path} {mid} {term}')
        r = selected.iloc[0]
        rows.append({'standardization':label,'parameter':panel,'model_id':mid,'term':term,
                     'OR':float(r.OR),'CI_low':float(r.CI_low),'CI_high':float(r.CI_high),
                     'n':int(r.n),'events':int(r.events),'source':path})
table = pd.DataFrame(rows)
table.to_csv(OUT/'standardization_sensitivity_data.csv',index=False)
with plt.rc_context({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none',
                     'axes.spines.top':False,'axes.spines.right':False}):
    fig, axes = plt.subplots(1,2,figsize=(11.5,4.5),layout='constrained',sharex=True,sharey=True)
    colors = ['#005A8D','#A64B00']
    for ax, parameter in zip(axes,['Acute load × soreness','Chronic load']):
        for i, (label, *_rest) in enumerate(specs):
            r = table[(table.parameter==parameter)&(table.standardization==label)].iloc[0]
            y = 1-i
            ax.errorbar(r.OR,y,xerr=np.array([[r.OR-r.CI_low],[r.CI_high-r.OR]]),
                        fmt=['o','s'][i],color=colors[i],markersize=7,capsize=4,lw=2)
            ax.text(0.03,0.83-0.49*i,f'{r.OR:.2f} [{r.CI_low:.2f}, {r.CI_high:.2f}]',
                    transform=ax.transAxes,fontsize=10,color=colors[i])
        ax.axvline(1,color='#555555',ls='--',lw=1,zorder=0)
        ax.set_xscale('log'); ax.set_xlim(.25,4); ax.set_ylim(-.45,1.45)
        ax.set_xticks([.25,.5,1,2,4],labels=['0.25','0.5','1','2','4'])
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xlabel('Odds ratio (log scale)'); ax.set_title(parameter,fontweight='bold',pad=12)
        ax.grid(axis='x',color='#E4E4E4',lw=.7)
    axes[0].set_yticks([1,0],labels=['Retrospective\nfull-period','Prior observations\nonly'])
    fig.suptitle('Estimates depend on the within-player reference distribution',fontsize=15,fontweight='bold')
    fig.supxlabel('Firth logistic regression; profile-likelihood 95% CIs.\n'
                  'Complete cases: 19,758 days / 28 onset-days versus 19,216 days / 27 onset-days.',fontsize=10)
    fig.savefig(OUT/'standardization_sensitivity.png',dpi=180,facecolor='white')
    fig.savefig(OUT/'standardization_sensitivity.svg',facecolor='white')
    plt.close(fig)

manifest = {'purpose':'Research portfolio illustration, not a replacement for submitted figures',
            'source':'Frozen structured results; no model was refitted by this plotting script',
            'uncertainty':'Profile-likelihood 95% confidence intervals from logistf; these are not cluster-bootstrap intervals',
            'sample':'Same underlying cohort, different complete-case samples after baseline construction',
            'selection':'Both focal parameters, soreness variant, same Firth estimator and covariates, team retained',
            'source_data_sha256':hashlib.sha256((OUT/'standardization_sensitivity_data.csv').read_bytes()).hexdigest(),
            'matplotlib_version':matplotlib.__version__}
(OUT/'figure_provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(OUT/'standardization_sensitivity.png')
