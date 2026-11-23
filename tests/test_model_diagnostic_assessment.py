import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('model_status',Path(__file__).resolve().parents[1]/'scripts/assess_model_diagnostics.py')
status=importlib.util.module_from_spec(spec);spec.loader.exec_module(status)

class ModelStatusTests(unittest.TestCase):
    def test_optimizer_success_without_derivatives_is_not_certified(self):
        self.assertEqual(status.assess('OK',optimizer_code=0),'UNVERIFIED_NO_DERIVATIVES')
    def test_warning_overrides_historical_success_claim(self):
        self.assertEqual(status.assess('OK (gamma frailty)',warnings=['Inner loop failed']),'WARNED_UNVERIFIED')
    def test_historical_failure_remains_failure(self):
        self.assertEqual(status.assess('FAILED'),'HISTORICAL_FAILURE')
    def test_negative_hessian_is_not_stationary_success(self):
        self.assertEqual(status.assess('OK',optimizer_code=0,derivatives={'Hessian_eigenvalues':[1,-1],'scaled_gradient':None}),'STATIONARITY_UNVERIFIED')
    def test_nonfinite_diagnostics_cannot_pass(self):
        self.assertEqual(status.assess('OK',optimizer_code=0,derivatives={'Hessian_eigenvalues':[float('nan')],'scaled_gradient':[0]}),'STATIONARITY_UNVERIFIED')

    def test_narrow_numerical_checks_can_pass(self):
        self.assertEqual(status.assess('OK',optimizer_code=0,derivatives={'Hessian_eigenvalues':[1,2],'scaled_gradient':[.0001]}),'NUMERICAL_CHECKS_PASSED')
