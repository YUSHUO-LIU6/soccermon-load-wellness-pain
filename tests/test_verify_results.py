"""Data-free regression checks for acceptance gates and immutable sources."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_results", ROOT / "scripts/verify_results.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class NumericPolicyTests(unittest.TestCase):
    def test_historical_policy_and_strict_counts(self):
        self.assertTrue(verify.compare_value(1, 1.0000009)[0])
        self.assertFalse(verify.compare_value(1, 1.000002)[0])
        self.assertFalse(verify.compare_value(1, 1.0000001, exact=True)[0])

    def test_missingness_and_invalid_values(self):
        self.assertTrue(verify.compare_value("NA", None)[0])
        self.assertFalse(verify.compare_value("NA", "invalid coefficient")[0])
        self.assertFalse(verify.compare_value("NA", "0")[0])
        self.assertFalse(verify.compare_value("Inf", "-Inf")[0])
        self.assertTrue(verify.compare_value("inf", "Inf")[0])

    def test_states_are_not_numerical_results(self):
        self.assertFalse(verify.compare_value("FAILED", "OK")[0])
        self.assertTrue(verify.compare_value("TRUE", True, boolean=True)[0])
        self.assertFalse(verify.compare_value("FALSE", True, boolean=True)[0])


class TableTests(unittest.TestCase):
    def test_nested_result_json_accepts_path_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref, fresh = Path(tmp) / 'reference.json', Path(tmp) / 'fresh.json'
            data = {'results': [{'model_id': 'F', 'term': 'interaction', 'OR': 0.63}]}
            ref.write_text(json.dumps(data))
            fresh.write_text(json.dumps(data))
            audit = verify.Audit()
            audit.json('r2', ref, fresh, Path('master_results.json'))
            self.assertTrue(all(row['status'] == 'PASS' for row in audit.rows))

    def test_ess_ratio_is_not_an_integer_count(self):
        audit = verify.Audit()
        audit.table('test', 'weights', ['variable', 'ess_over_n'],
                    [{'variable': 'soreness', 'ess_over_n': '0.534233181521007'}],
                    ['variable', 'ess_over_n'],
                    [{'variable': 'soreness', 'ess_over_n': '0.5342331815210072'}])
        self.assertTrue(all(row['status'] == 'PASS' for row in audit.rows))

    columns = ["model_id", "wellness_variant", "term", "OR", "CI_low", "n", "converged"]
    rows = [dict(model_id="F", wellness_variant="soreness", term="interaction", OR="0.6", CI_low="0.4", n="100", converged="TRUE"),
            dict(model_id="E", wellness_variant="soreness", term="interaction", OR="NA", CI_low="NA", n="100", converged="FALSE")]

    def compare(self, rows, columns=None):
        audit = verify.Audit()
        audit.table("test", "model.csv", self.columns, self.rows, columns or self.columns, rows)
        return audit.rows

    def test_keyed_row_reordering(self):
        self.assertTrue(all(r["status"] == "PASS" for r in self.compare(list(reversed(self.rows)))))

    def test_failure_and_missingness_preserved(self):
        rows = [dict(r) for r in self.rows]
        rows[1]["OR"] = "1"
        self.assertTrue(any(r["item"] == "OR" and r["status"] == "FAIL" for r in self.compare(rows)))

    def test_duplicate_and_missing_keys_fail(self):
        rows = [self.rows[0], self.rows[0]]
        self.assertTrue(any(r["item"] == "row_key_multiset" and r["status"] == "FAIL" for r in self.compare(rows)))

    def test_dropped_column_fails(self):
        self.assertTrue(any(r["status"] == "FAIL" for r in self.compare(self.rows, self.columns[:-1])))

    def test_count_changes_fail_even_within_float_tolerance(self):
        rows = [dict(r) for r in self.rows]
        rows[0]["n"] = "100.000001"
        self.assertTrue(any(r["item"] == "n" and r["status"] == "FAIL" for r in self.compare(rows)))

    def test_missing_fresh_result_is_not_pass(self):
        audit = verify.Audit()
        audit.csv("test", ROOT / "reproducibility/frozen/r1/r_results.csv", None, "missing.csv")
        self.assertEqual([r["status"] for r in audit.rows], ["NOT RUN"])

    def test_frozen_path_cannot_be_claimed_fresh(self):
        audit = verify.Audit()
        path = ROOT / "reproducibility/frozen/r1/r_results.csv"
        audit.csv("test", path, path, "copied.csv")
        self.assertEqual([r["status"] for r in audit.rows], ["BLOCKED"])


class BootstrapTests(unittest.TestCase):
    def check(self, ids, valid=2000, summary_valid=2000):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            summary, reps = folder / "summary.json", folder / "reps.csv"
            summary.write_text(json.dumps(dict(n_boot_requested=2000, n_boot_ok=summary_valid,
                                                n_boot_failed=2000-summary_valid)))
            with reps.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["replicate", "beta_interaction"])
                writer.writerows((n, 0.1 if i < valid else "NA") for i, n in enumerate(ids))
            audit = verify.Audit()
            verify.bootstrap_integrity(audit, "test", summary, reps, "bootstrap")
            return audit.rows[0]["status"]

    def test_complete_bootstrap_passes(self):
        self.assertEqual(self.check(range(2000)), "PASS")

    def test_duplicate_ids_and_invalid_count_fail(self):
        self.assertEqual(self.check([0] * 2000), "FAIL")
        self.assertEqual(self.check(range(2000), valid=1999), "FAIL")
        self.assertEqual(self.check(range(1999)), "FAIL")


class ProvenanceTests(unittest.TestCase):
    def test_incomplete_pipeline_cannot_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "execution.jsonl").write_text(json.dumps(dict(kind="pipeline", task="r1-full", exit_status=1)) + "\n")
            (folder / "full_run.json").write_text(json.dumps(dict(task="r1-full", status="INCOMPLETE")))
            audit = verify.Audit()
            verify.provenance(audit, "r1", folder, "r1-full")
            self.assertEqual(audit.rows[0]["status"], "BLOCKED")


class FrozenIntegrityTests(unittest.TestCase):
    def test_imported_sources_are_immutable(self):
        with (ROOT / "reproducibility/source_manifest.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertGreater(len(rows), 0)
        for row in rows:
            with self.subTest(file=row["repository_path"]):
                path = ROOT / row["repository_path"]
                self.assertTrue(path.is_file())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])

    def test_expected_data_fingerprint_inventory(self):
        for filename, expected in [("data_fingerprints.json", 6), ("sensitivity_fingerprints.json", 2)]:
            document = json.loads((ROOT / "reproducibility" / filename).read_text())
            self.assertEqual(len(document), expected)
            for value in document.values():
                self.assertEqual(set(value["columns"]), set(value["column_digests"]))
                self.assertGreater(value["rows"], 0)


if __name__ == "__main__":
    unittest.main()
