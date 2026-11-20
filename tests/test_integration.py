"""Failure boundaries and relocatability of the build orchestrator."""
import json
import importlib
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from integration import integration_files, plan, run_pipeline, source_audit
from components import check_serial_confirmation
from workspace import environment


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdkhm test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()

    def pipeline(self, stages):
        path = self.root / "config/build/pipeline.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"stages": stages, "profiles": {"build": list(stages)}}))

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

    def test_kernel_profile_default_and_override(self):
        with patch.dict(os.environ, {}, clear=True):
            env = environment(self.root)
        self.assertEqual(env["RDKHM_KERNEL_PROFILE"], "default")
        (self.root / "config/workspace.local.json").write_text(
            json.dumps({"RDKHM_KERNEL_PROFILE": "rt"}))
        with patch.dict(os.environ, {}, clear=True):
            env = environment(self.root)
        self.assertEqual(env["RDKHM_KERNEL_PROFILE"], "rt")

    def test_invalid_kernel_profile_fails(self):
        (self.root / "config/workspace.local.json").write_text(
            json.dumps({"RDKHM_KERNEL_PROFILE": "preempt"}))
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                environment(self.root)

    def test_patch_state_is_revalidated_after_manual_revert(self):
        patcher = importlib.import_module("apply-patches")
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"],
                       check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        target = repo / "file.txt"
        target.write_text("base\n")
        subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "base"], check=True)
        target.write_text("patched\n")
        diff = subprocess.check_output(["git", "-C", str(repo), "diff"])
        patch_dir = self.root / "patches"
        patch_dir.mkdir()
        (patch_dir / "test.patch").write_bytes(diff)
        subprocess.run(["git", "-C", str(repo), "checkout", "--", "file.txt"], check=True)
        entry = {"repo": "repo", "patch": "test.patch"}
        state = {"patches": {}}
        with patch.object(patcher, "ROOT", self.root):
            self.assertEqual(patcher.apply_one(entry, state), "applied")
            self.assertEqual(target.read_text(), "patched\n")
            subprocess.run(["git", "-C", str(repo), "checkout", "--", "file.txt"], check=True)
            self.assertEqual(patcher.apply_one(entry, state), "applied")
            self.assertEqual(target.read_text(), "patched\n")

    def test_hap_signing_requires_java(self):
        hap = importlib.import_module("build-hap")
        with patch.object(hap.shutil, "which", return_value=None):
            with self.assertRaises(RuntimeError):
                hap._sign_hap(Path("unsigned.hap"), Path("app"), "settings", {})

    def test_rt_profile_is_opt_in_and_wired(self):
        root = Path(__file__).resolve().parents[1]
        patcher = importlib.import_module("apply-patches")
        collections = {"kernel": [], "kernel-rt": [], "openharmony": []}
        self.assertNotIn("kernel-rt", patcher.selected_collections(collections, None))
        self.assertEqual(patcher.selected_collections(collections, ["kernel-rt"]),
                         ["kernel-rt"])
        manifest = json.loads((root / "config/patches.json").read_text())
        self.assertIn("kernel-rt", manifest["collections"])
        self.assertEqual(
            [entry["patch"] for entry in manifest["collections"]["kernel-rt"]],
            ["optional/preempt-rt/patch-6.1.83-rt28.patch"])
        self.assertIn(
            "CONFIG_PREEMPT_RT=y",
            (root / "config/kernel/hobot_x5_rdk_ubuntu_rt_defconfig").read_text())
        builder = (root / "scripts/build-kernel.sh").read_text()
        self.assertIn("hobot_x5_rdk_ubuntu_defconfig", builder)
        self.assertIn("hobot_x5_rdk_ubuntu_rt_defconfig", builder)

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
        path = self.root / "config/sources/repo.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<manifest><project")
        with self.assertRaises(ET.ParseError):
            run_pipeline(self.root, "build", os.environ.copy())
        report = json.loads(next((self.root / "out/runs").glob("*/run.json")).read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["steps"], [])

    def test_unknown_target_rejected(self):
        self.pipeline({})
        with self.assertRaises(ValueError):
            plan(self.root, "typo")

    def test_manifest_path_defaults_to_project_name(self):
        path = self.root / "config/sources/openharmony.lock.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('<manifest><project name="missing" revision="abc"/></manifest>')
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

    def test_serial_required_needs_confirmation(self):
        config = {"kind": "libs", "serial_required": True}
        with self.assertRaises(ValueError):
            check_serial_confirmation("display", config, True, False)
        check_serial_confirmation("display", config, True, True)
        check_serial_confirmation("display", config, False, False)
        check_serial_confirmation("display", {"kind": "libs"}, True, False)


if __name__ == "__main__":
    unittest.main()
