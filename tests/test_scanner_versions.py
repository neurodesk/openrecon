import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from test_openrecon_label_validation import (
    REPO_ROOT, VALIDATE_RECIPES_PY, base_label, config_parameter, openrecon_build,
)


class ScannerVersionTests(unittest.TestCase):
    def test_metadata_rejects_non_numeric_scanner_versions(self):
        for version in ('2.10.0-build20261005', '1.0.0-post1', '1.0.0.post1',
                        '1.0', '١.0.0', '1.0.0\n'):
            with self.subTest(version=version):
                label = base_label([config_parameter()])
                label['general']['version'] = version
                with self.assertRaisesRegex(ValueError, 'numeric X.Y.Z'):
                    openrecon_build.validate_openrecon_label_metadata(label)

    def validate_params(self, params, version='VERSION_WILL_BE_REPLACED_BY_SCRIPT'):
        label = json.loads((REPO_ROOT / 'recipes/b0map/OpenReconLabel.json').read_text())
        label['general']['version'] = version
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory)
            (path / 'params.sh').write_text(params)
            (path / 'OpenReconLabel.json').write_text(json.dumps(label))
            return subprocess.run(
                [sys.executable, str(VALIDATE_RECIPES_PY), str(path / 'OpenReconLabel.json')],
                capture_output=True, text=True,
            )

    def test_ci_rejects_invalid_params_hidden_by_placeholder(self):
        result = self.validate_params('export version=2.10.0-build20261005\n')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('numeric X.Y.Z', result.stdout)

    def test_ci_accepts_numeric_override_for_post_release_source(self):
        result = self.validate_params(
            'export version="1.0.0.post1" # source\n'
            "export openrecon_version='1.0.0' # scanner\n"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ci_rejects_dynamic_values_without_executing_shell(self):
        result = self.validate_params('export version=$(printf 1.0.0)\n')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('literal', result.stdout)

    def test_ci_rejects_hardcoded_version_that_disagrees_with_params(self):
        result = self.validate_params('export version=2.0.0\n', '1.0.0')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('does not match', result.stdout)

    def test_ci_accepts_hardcoded_numeric_version_without_params_version(self):
        result = self.validate_params('export baseDockerImage=example/tool_1.0.0\n', '1.0.0')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ci_requires_version_when_label_is_placeholder(self):
        result = self.validate_params('export baseDockerImage=example/tool_1.0.0\n')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('numeric X.Y.Z', result.stdout)

    def test_ci_rejects_uppercase_only_version_for_placeholder(self):
        result = self.validate_params('export VERSION=1.0.0\n')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('numeric X.Y.Z', result.stdout)

    def test_ci_rejects_hash_attached_to_unquoted_version(self):
        result = self.validate_params('export version=1.0.0#suffix\n')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('literal', result.stdout)
