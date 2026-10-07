import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_build_script_environment import BUILD_SCRIPT


class BaseImageSelectionTests(unittest.TestCase):
    def run_selection(self, base_image, cached, override='', local_only=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe = root / 'recipe'
            recipe.mkdir()
            (recipe / 'OpenReconLabel.json').write_text('{}')
            (recipe / 'params.sh').write_text(
                'export toolName=test\nexport version=1.0.0\n'
                f'export baseDockerImage={shlex.quote(base_image)}\n'
                f'export localDockerImage={shlex.quote(override)}\n'
            )
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            scripts = {'python3': 'exit 0', '7z': 'exit 0'}
            scripts['docker'] = (
                'if [ "$1 $2" = "image inspect" ]; then\n'
                '  case "$3" in\n'
                + ''.join(f'    {shlex.quote(tag)}) exit 0;;\n' for tag in cached)
                + '    *) exit 1;;\n  esac\nfi\nexit 0'
            )
            for name, script in scripts.items():
                path = bin_dir / name
                path.write_text('#!/bin/sh\n' + script + '\n')
                path.chmod(0o755)
            environment = os.environ.copy()
            environment.update(PATH=f'{bin_dir}:/usr/bin:/bin', CI='1')
            command = ['/bin/bash', str(BUILD_SCRIPT), '--ignore-mdpdf']
            if local_only:
                command.append('--local-cache')
            return subprocess.run(command, cwd=recipe, env=environment,
                                  capture_output=True, text=True)

    def test_pinned_images_never_select_stale_canonical_alias(self):
        for pin in ('registry:5000/test:20261005', 'registry/test@sha256:' + 'a' * 64):
            for cached_pin in (False, True):
                with self.subTest(pin=pin, cached_pin=cached_pin):
                    cached = ['test:1.0.0'] + ([pin] if cached_pin else [])
                    result = self.run_selection(pin, cached)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn(f'Docker image to use: {pin}\n', result.stdout)
                    if not cached_pin:
                        self.assertIn(f'Using remote image: {pin}', result.stdout)

    def test_local_only_rejects_missing_pin_despite_stale_alias(self):
        result = self.run_selection('registry/test:20261005', ['test:1.0.0'], local_only=True)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('no matching local image', result.stdout)

    def test_implicit_latest_preserves_canonical_local_convenience(self):
        result = self.run_selection('registry:5000/test_1.0.0', ['test:1.0.0'])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Docker image to use: test:1.0.0\n', result.stdout)

    def test_explicit_local_override_wins_over_pin(self):
        result = self.run_selection('registry/test:20261005', ['intentional:local'],
                                    override='intentional:local')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Docker image to use: intentional:local\n', result.stdout)
