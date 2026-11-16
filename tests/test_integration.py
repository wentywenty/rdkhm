"""Failure boundaries and relocatability of the build orchestrator."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from integration import integration_files, plan, run_pipeline, source_audit
from workspace import environment


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdkhm test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "sources.lock.tsv").write_text("# empty fixture\n")

    def pipeline(self, stages):
        (self.root / "config/pipeline.json").write_text(json.dumps({
            "stages": stages, "profiles": {"build": list(stages)}}))

    def test_environment_overrides_and_relative_paths(self):
        (self.root / "config/workspace.local.json").write_text(json.dumps({
            "RDKHM_BSP": "inputs/bsp", "JOBS": "2"}))
        with patch.dict(os.environ, {"JOBS": "7"}, clear=True):
            env = environment(self.root)
        self.assertEqual(env["JOBS"], "7")
        self.assertEqual(env["RDKHM_BSP"], str(self.root / "inputs/bsp"))

    def test_invalid_setting_fails(self):
        (self.root / "config/workspace.local.json").write_text('{"HOME":"/bad"}')
        with self.assertRaises(ValueError):
            environment(self.root)

    def test_pipeline_stops_and_retains_failure(self):
        self.pipeline({"one": [[sys.executable, "-c", "raise SystemExit(17)"]],
                       "two": [[sys.executable, "-c", "open('unexpected', 'w').close()"]]})
        with self.assertRaises(RuntimeError):
            run_pipeline(self.root, "build", os.environ.copy())
        self.assertFalse((self.root / "unexpected").exists())
        report = json.loads(next((self.root / "out/runs").glob("*/run.json")).read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["steps"][0]["returncode"], 17)
        self.assertEqual(len(report["steps"]), 1)

    def test_success_is_not_board_validation(self):
        self.pipeline({"one": [[sys.executable, "-c", "print('ok')"]]})
        run_pipeline(self.root, "build", os.environ.copy())
        report = json.loads(next((self.root / "out/runs").glob("*/run.json")).read_text())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["board_validation"], "not-run")

    def test_snapshot_failure_is_recorded(self):
        self.pipeline({"one": []})
        (self.root / "sources.lock.tsv").unlink()
        with self.assertRaises(FileNotFoundError):
            run_pipeline(self.root, "build", os.environ.copy())
        report = json.loads(next((self.root / "out/runs").glob("*/run.json")).read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["steps"], [])

    def test_unknown_target_rejected(self):
        self.pipeline({})
        with self.assertRaises(ValueError):
            plan(self.root, "typo")

    def test_manifest_path_defaults_to_project_name(self):
        (self.root / "config/openharmony.lock.xml").write_text(
            '<manifest><project name="missing" revision="abc"/></manifest>')
        destination = self.root / "audit"
        destination.mkdir()
        summary = source_audit(self.root, destination)
        self.assertEqual(summary["revision_mismatches_or_missing"], 1)
        records = json.loads((destination / "openharmony-source-state.json").read_text())
        self.assertEqual(records[0]["path"], "missing")

    def test_source_hash_changes_and_local_settings_excluded(self):
        path = self.root / "config/item.json"
        path.write_text("{}")
        first = integration_files(self.root)
        (self.root / "config/workspace.local.json").write_text('{"JOBS":"2"}')
        self.assertEqual(first, integration_files(self.root))
        path.write_text('{"changed":true}')
        self.assertNotEqual(first, integration_files(self.root))


if __name__ == "__main__":
    unittest.main()
