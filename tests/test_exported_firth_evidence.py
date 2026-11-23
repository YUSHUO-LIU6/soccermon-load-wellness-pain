"""Validate the shipped replicate artifact against immutable published summaries.

No raw data, R library, optimizer or bootstrap rerun is required.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import unittest
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('gates',ROOT/'scripts/verify_results.py')
gates=importlib.util.module_from_spec(spec);spec.loader.exec_module(gates)

class ExportedEvidenceTests(unittest.TestCase):
    def test_replicates_reconstruct_frozen_firth_summaries(self):
        summary=json.loads((ROOT/'reports/FIRTH_REPLICATE_SUMMARY.json').read_text())
        artifact=ROOT/'reports/FIRTH_REPLICATE_DIAGNOSTICS.csv'
        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(),summary['replicates_sha256'])
        self.assertEqual(hashlib.sha256((ROOT/'analysis/core/05_bootstrap_and_ipw.py').read_bytes()).hexdigest(),summary['source_sha256'])
        self.assertEqual(summary['initial_seed'],20260723)
        with artifact.open(newline='') as stream:records=list(csv.DictReader(stream))
        with (ROOT/'reproducibility/frozen/r1/firth_bootstrap_results.csv').open(newline='') as stream:reference=list(csv.DictReader(stream))
        self.assertEqual(len(records),6000)
        for variant in ('soreness','fatigue','readiness'):
            group=[r for r in records if r['variant']==variant]
            self.assertEqual(sorted(int(r['replicate']) for r in group),list(range(2000)))
            accepted=[r for r in group if r['original_accepted']=='True']
            self.assertEqual(len(accepted),2000 if variant!='readiness' else 1999)
            self.assertTrue(all(gates.criterion_record(r) for r in accepted))
            expected={r['term']:r for r in reference if r['wellness_variant']==variant}
            for i,term in enumerate(summary['variants'][variant]['terms']):
                values=sorted(float(r['beta_'+str(i)]) for r in accepted)
                def percentile(q):
                    pos=(len(values)-1)*q;lo=math.floor(pos);hi=math.ceil(pos)
                    return values[lo]+(values[hi]-values[lo])*(pos-lo)
                computed={'OR':math.exp(statistics.median(values)),
                          'CI_low':math.exp(percentile(.025)),
                          'CI_high':math.exp(percentile(.975)),
                          'se':statistics.stdev(values)}
                for field,value in computed.items():
                    self.assertTrue(gates.compare_value(value,expected[term][field])[0],(variant,term,field))
