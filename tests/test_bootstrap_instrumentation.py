"""Numerical parity and truthful termination recording for the preserved IRLS."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('trace',ROOT/'scripts/audit_firth_replicates.py')
trace=importlib.util.module_from_spec(spec);spec.loader.exec_module(trace)

class InstrumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns,cls.node=trace.functions_from_source(ROOT/'analysis/core/05_bootstrap_and_ipw.py')

    def test_converged_estimate_is_bit_identical(self):
        X=np.column_stack([np.ones(100),np.linspace(-1,1,100)])
        y=(np.arange(100)%3==0).astype(float)
        actual,last=trace.instrument_irls(self.node,self.ns)
        original,ok=self.ns['irls_logit'](X,y,firth=True,max_iter=200)
        observed,observed_ok=actual(X,y,firth=True,max_iter=200)
        np.testing.assert_array_equal(original,observed)
        self.assertEqual(ok,observed_ok);self.assertTrue(last['criterion_met'])
        self.assertLess(last['terminal_step'],1e-9)

    def test_iteration_limit_preserves_legacy_flag_but_reports_nonconvergence(self):
        X=np.column_stack([np.ones(10),np.arange(10)])
        y=np.array([0,0,0,0,0,1,1,1,1,1],dtype=float)
        actual,last=trace.instrument_irls(self.node,self.ns)
        original,ok=self.ns['irls_logit'](X,y,firth=True,max_iter=1)
        observed,observed_ok=actual(X,y,firth=True,max_iter=1)
        np.testing.assert_array_equal(original,observed)
        self.assertTrue(ok and observed_ok)
        self.assertFalse(last['criterion_met']);self.assertEqual(last['termination'],'iteration_limit')
        self.assertEqual(last['iterations'],1)

    def test_singular_information_is_explicit(self):
        actual,last=trace.instrument_irls(self.node,self.ns)
        beta,ok=actual(np.ones((10,2)),np.zeros(10),firth=True,max_iter=200)
        self.assertIsNone(beta);self.assertFalse(ok)
        self.assertEqual(last['termination'],'singular_information')
        self.assertFalse(last['criterion_met'])
