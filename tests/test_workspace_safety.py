"""Exercise the actual runner safety functions without importing statistical packages."""
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.root = self.root.resolve()
        # Compile unchanged function ASTs from the production file; avoid loading
        # pandas/numpy merely to test directory guards in the data-free CI job.
        module = ast.parse((ROOT / "scripts/pipeline.py").read_text())
        names = {"configure_workspace", "claim_full_run", "write_json", "utc_now"}
        module.body = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in names]
        self.namespace = dict(Path=Path, ROOT=self.root, SEED=20260722, json=json,
                              datetime=datetime, timezone=timezone)
        exec(compile(module, str(ROOT / "scripts/pipeline.py"), "exec"), self.namespace)

    def configure(self, path):
        self.namespace["configure_workspace"](path)

    def test_only_repository_workspace_is_accepted(self):
        self.configure("workspace/r1-audit")
        self.assertEqual(self.namespace["WORK"], self.root / "workspace/r1-audit")
        for path in ["reproducibility/frozen", "workspace/../../escape", self.root.parent / "elsewhere"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.configure(path)

    def test_workspace_symlink_cannot_escape(self):
        (self.root / "workspace").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.configure("workspace/run")

    def test_nested_symlink_cannot_escape(self):
        (self.root / "workspace").mkdir()
        (self.root / "workspace/escape").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.configure("workspace/escape/run")

    def test_duplicate_full_run_is_refused_without_overwriting_marker(self):
        self.configure("workspace/run")
        marker, _ = self.namespace["claim_full_run"]("r1-full")
        before = marker.read_bytes()
        with self.assertRaises(ValueError):
            self.namespace["claim_full_run"]("r2-full")
        self.assertEqual(marker.read_bytes(), before)

    def test_existing_model_outputs_are_preserved_and_refused(self):
        self.configure("workspace/run")
        output = self.namespace["SB"] / "07_ANALYSIS_OUTPUTS/RUN_PORTABLE/r_results.csv"
        output.parent.mkdir(parents=True)
        output.write_text("preserved existing output\n")
        with self.assertRaises(ValueError):
            self.namespace["claim_full_run"]("r1-full")
        self.assertEqual(output.read_text(), "preserved existing output\n")
        marker = json.loads((self.namespace["WORK"] / "full_run.json").read_text())
        self.assertEqual(marker["status"], "REFUSED_EXISTING_MODEL_OUTPUTS")


if __name__ == "__main__":
    unittest.main()
