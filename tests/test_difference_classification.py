import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/classify_differences.py')
impact=importlib.util.module_from_spec(spec);spec.loader.exec_module(impact)

class ImpactClassificationTests(unittest.TestCase):
    def test_protected_contrast_cannot_be_dismissed_as_precision(self):
        self.assertEqual(impact.classify('r1/r_results.csv','OR','field',{'F'})[0],'A')
    def test_large_qa_direction_change_is_optimizer_sensitivity(self):
        self.assertEqual(impact.classify('10/SEASON_STABILITY.csv','OR','field',{'A_drop_team_season'})[0],'B')
    def test_warned_frailty_is_not_claimed_to_be_converged(self):
        label,reason=impact.classify('r1/r_results.csv','CI_high','field',{'E'})
        self.assertEqual(label,'B');self.assertIn('warnings',reason)
    def test_duplicate_counts_remain_structural_failures(self):
        self.assertEqual(impact.classify('08/nonoverlap_diagnostics.csv','row_count','structure',set())[0],'D')
    def test_annotation_is_not_a_new_statistical_discrepancy(self):
        self.assertEqual(impact.classify('13/IPW_FINAL_RESULTS.csv','notes','field',set())[0],'E')
    def test_protected_structure_cannot_be_excused_as_frailty(self):
        self.assertEqual(impact.classify('r1/master_results.csv','row_key_multiset','structure',{'F'})[0],'A')
