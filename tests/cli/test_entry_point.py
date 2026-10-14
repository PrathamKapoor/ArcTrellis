"""Installed console entry point: declaration, resolution and a real subprocess run."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from importlib.metadata import entry_points
from pathlib import Path

from tests.orchestration.repository import PLAIN_SOURCE, write_sources

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALLED_SCRIPT = PROJECT_ROOT / ".venv" / "Scripts" / "arctrellis.exe"
POSIX_SCRIPT = PROJECT_ROOT / ".venv" / "bin" / "arctrellis"


class EntryPointDeclarationTests(unittest.TestCase):
    def test_pyproject_declares_the_console_entry_point(self) -> None:
        text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[project.scripts]", text)
        self.assertIn('arctrellis = "arctrellis.cli.main:entry_point"', text)

    def test_installed_metadata_exposes_arctrellis(self) -> None:
        scripts = {item.name: item.value for item in entry_points(group="console_scripts")}
        if "arctrellis" not in scripts:
            self.skipTest("the project is not installed in this interpreter")
        self.assertEqual(scripts["arctrellis"], "arctrellis.cli.main:entry_point")

    def test_entry_point_target_is_callable(self) -> None:
        from arctrellis.cli.main import entry_point

        self.assertTrue(callable(entry_point))

    def test_no_additional_entry_points_are_declared(self) -> None:
        text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        section = text.split("[project.scripts]", 1)[1].split("[", 1)[0]
        declarations = [line for line in section.splitlines() if "=" in line and not line.strip().startswith("#")]
        self.assertEqual(len(declarations), 1)


class InstalledConsoleScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = INSTALLED_SCRIPT if INSTALLED_SCRIPT.exists() else POSIX_SCRIPT
        if not cls.script.exists():
            raise unittest.SkipTest("the console script is not installed in this checkout")
        cls._temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls._temporary.name)
        write_sources(cls.root, PLAIN_SOURCE)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "_temporary"):
            cls._temporary.cleanup()

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.script), *args],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

    def test_installed_script_reports_its_version(self) -> None:
        result = self.run_script("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("arctrellis", result.stdout)

    def test_installed_script_analyzes_a_repository(self) -> None:
        result = self.run_script("analyze", str(self.root))
        self.assertEqual(result.returncode, 0)
        self.assertIn("entities:", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_installed_script_emits_valid_json_on_stdout(self) -> None:
        import json

        result = self.run_script("analyze", str(self.root), "--json")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertIn("counts", payload)
        self.assertEqual(result.stderr, "")

    def test_installed_script_exit_codes_are_stable(self) -> None:
        missing = str(self.root / "absent")
        self.assertEqual(self.run_script("analyze", missing).returncode, 4)
        self.assertEqual(self.run_script("query", str(self.root), "--intent", "find-callers").returncode, 2)
        self.assertEqual(self.run_script("query", str(self.root), "--intent", "nope", "--entity-id", "x").returncode, 5)
        self.assertEqual(self.run_script("search", str(self.root), "x", "--limit", "0").returncode, 2)

    def test_installed_script_prints_no_traceback(self) -> None:
        result = self.run_script("analyze", str(self.root / "absent"))
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_module_invocation_matches_the_console_script(self) -> None:
        module = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; from arctrellis.cli.main import main; sys.exit(main(sys.argv[1:]))",
                "analyze",
                str(self.root),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        script = self.run_script("analyze", str(self.root), "--json")
        self.assertEqual(module.returncode, script.returncode)
        self.assertEqual(module.stdout, script.stdout)


if __name__ == "__main__":
    unittest.main()
