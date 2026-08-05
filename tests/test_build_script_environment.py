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


def run_build_until_docker_check(temporary_path):
    recipe_directory = temporary_path / "recipe"
    recipe_directory.mkdir()
    (recipe_directory / "README.md").write_text("# Test recipe\n")

    fake_bin = temporary_path / "bin"
    fake_bin.mkdir()
    for command_name in ("python3", "7z"):
        fake_command = fake_bin / command_name
        fake_command.write_text("#!/bin/sh\nexit 0\n")
        fake_command.chmod(0o755)

    environment = os.environ.copy()
    environment["HOME"] = str(temporary_path)
    environment["NVM_DIR"] = str(temporary_path / ".nvm")
    environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"
    environment["CI"] = "1"

    return subprocess.run(
        ["/bin/bash", str(BUILD_SCRIPT)],
        cwd=recipe_directory,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


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

    def test_existing_nvm_mdpdf_skips_node_discovery(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            nvm_bin = temporary_path / ".nvm" / "versions" / "node" / "bin"
            nvm_bin.mkdir(parents=True)
            node_marker = temporary_path / "node-command-was-invoked"

            fake_mdpdf = nvm_bin / "mdpdf"
            fake_mdpdf.write_text("#!/bin/sh\nexit 0\n")
            fake_mdpdf.chmod(0o755)

            nvm_script = temporary_path / ".nvm" / "nvm.sh"
            nvm_script.write_text(
                f'export PATH={shlex.quote(str(nvm_bin))}:"$PATH"\n'
                "nvm() {\n"
                f"    touch {shlex.quote(str(node_marker))}\n"
                "}\n"
                "npm() {\n"
                f"    touch {shlex.quote(str(node_marker))}\n"
                "}\n"
            )

            result = run_build_until_docker_check(temporary_path)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Docker is not installed", result.stdout)
            self.assertFalse(node_marker.exists(), result.stdout)

    def test_missing_nvm_node_uses_local_version_before_installing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            nvm_directory = temporary_path / ".nvm"
            nvm_directory.mkdir()
            node_log = temporary_path / "node-commands.log"

            nvm_script = nvm_directory / "nvm.sh"
            nvm_script.write_text(
                "nvm() {\n"
                f"    printf 'nvm %s\\n' \"$*\" >> {shlex.quote(str(node_log))}\n"
                "    if [ \"$1\" = \"use\" ]; then\n"
                "        return 1\n"
                "    fi\n"
                "    npm() {\n"
                f"        printf 'npm %s\\n' \"$*\" >> {shlex.quote(str(node_log))}\n"
                "    }\n"
                "}\n"
            )

            result = run_build_until_docker_check(temporary_path)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Docker is not installed", result.stdout)
            self.assertEqual(
                node_log.read_text().splitlines(),
                [
                    "nvm use --silent v22.3.0",
                    "nvm install v22.3.0",
                    "npm install -g mdpdf",
                ],
            )

    def test_build_workflow_activates_a_virtual_environment(self):
        workflow = BUILD_WORKFLOW.read_text()

        create_index = workflow.index("python3 -m venv .venv")
        activate_index = workflow.index("source .venv/bin/activate")
        build_index = workflow.index("/bin/bash ../build.sh")
        self.assertLess(create_index, activate_index)
        self.assertLess(activate_index, build_index)


if __name__ == "__main__":
    unittest.main()
