import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPOSITORY_ROOT / "recipes" / "build.sh"
TEST_RECIPE_DIR = REPOSITORY_ROOT / "recipes" / "qsmxt"
BUILD_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "build-apps.yml"


class BuildScriptEnvironmentTests(unittest.TestCase):
    def test_rejects_system_python_before_installing_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            fake_bin = temporary_path / "bin"
            fake_bin.mkdir()
            pip_marker = temporary_path / "pip-was-invoked"
            fake_python = fake_bin / "python3"
            fake_pip = fake_bin / "pip3"
            fake_python.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"-c\" ]; then\n"
                "    exit 1\n"
                "fi\n"
                "if [ \"$1\" = \"-m\" ] && [ \"$2\" = \"pip\" ]; then\n"
                f"    touch {shlex.quote(str(pip_marker))}\n"
                "fi\n"
                "exit 99\n"
            )
            fake_python.chmod(0o755)
            fake_pip.write_text(
                "#!/bin/sh\n"
                f"touch {shlex.quote(str(pip_marker))}\n"
                "exit 99\n"
            )
            fake_pip.chmod(0o755)

            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"
            environment["CI"] = "1"
            environment.pop("VIRTUAL_ENV", None)

            result = subprocess.run(
                ["/bin/bash", str(BUILD_SCRIPT)],
                cwd=TEST_RECIPE_DIR,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("virtual environment", result.stdout.lower())
            self.assertFalse(pip_marker.exists(), result.stdout)

    def test_dependency_and_build_commands_share_the_selected_python(self):
        script = BUILD_SCRIPT.read_text()

        self.assertNotIn("pip3 install", script)
        self.assertIn('"$PYTHON_BIN" -m pip install jsonschema', script)
        self.assertIn('"$PYTHON_BIN" -m pip install packaging', script)
        self.assertIn('"$PYTHON_BIN" -u "$BUILD_SCRIPT_DIR/build.py"', script)

    def test_build_workflow_activates_a_virtual_environment(self):
        workflow = BUILD_WORKFLOW.read_text()

        create_index = workflow.index("python3 -m venv .venv")
        activate_index = workflow.index("source .venv/bin/activate")
        build_index = workflow.index("/bin/bash ../build.sh")
        self.assertLess(create_index, activate_index)
        self.assertLess(activate_index, build_index)


if __name__ == "__main__":
    unittest.main()
