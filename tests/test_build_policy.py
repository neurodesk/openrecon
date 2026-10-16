import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import build_policy as policy
import validate_recipes


class BuildPolicyTests(unittest.TestCase):
    def setUp(self):
        self.config = {'default': {'autoBuild': True},
                       'kspacefilter': {'autoBuild': True, 'buildProfile': 'experimental-openrecon-raw'},
                       'disabled': {'autoBuild': False}}

    def test_exclusive_routes_and_standard_defaults(self):
        self.assertEqual(policy.build_routes(self.config, ['kspacefilter', 'ordinary', 'disabled', 'ordinary']),
                         {'standard': ['ordinary'], 'experimental-openrecon-raw': ['kspacefilter']})
        self.assertEqual(policy.recipe_policy(self.config, 'unregistered').profile, policy.BuildProfile.STANDARD)

    def test_invalid_profiles_and_types_fail(self):
        for entry in ({'buildProfile': 'unknown'}, {'autoBuild': 'true'}, {'freeUpSpace': 1}):
            config = copy.deepcopy(self.config)
            config['kspacefilter'] = entry
            with self.assertRaises(ValueError):
                policy.recipe_policy(config, 'kspacefilter')
        self.config['default']['buildProfile'] = 'experimental-openrecon-raw'
        with self.assertRaises(ValueError):
            policy.recipe_policy(self.config, 'ordinary')

    def test_raw_validation_requires_trusted_canonical_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            recipe = root / 'recipes/kspacefilter'
            recipe.mkdir(parents=True)
            label = recipe / 'OpenReconLabel.json'
            original = json.loads((ROOT / 'recipes/kspacefilter/OpenReconLabel.json').read_text())
            (recipe / 'params.sh').write_text('export version=0.1.0\n')
            config = root / 'config.json'
            config.write_text(json.dumps(self.config))
            schema = ROOT / 'recipes/OpenReconSchema_1.1.0.json'
            with patch.object(policy, 'ROOT', root), patch.object(policy, 'CONFIG', config):
                label.write_text(json.dumps(original))
                self.assertTrue(validate_recipes.validate_recipe(label, schema))
                for field, value in [('emitter', 'image'), ('content_qualification_type', 'PRODUCT'), ('emitter', 5), ('port', '9002')]:
                    malformed = copy.deepcopy(original)
                    malformed['reconstruction'][field] = value
                    label.write_text(json.dumps(malformed))
                    self.assertFalse(validate_recipes.validate_recipe(label, schema))
                label.write_text(json.dumps(original))
                outside = root / 'outside/kspacefilter'
                outside.mkdir(parents=True)
                other = outside / 'OpenReconLabel.json'
                other.write_text(json.dumps(original))
                (outside / 'params.sh').write_text('export version=0.1.0\n')
                self.assertFalse(validate_recipes.validate_recipe(other, schema))
                config.write_text(json.dumps({'default': {'autoBuild': True}}))
                self.assertFalse(validate_recipes.validate_recipe(label, schema))
                config.write_text(json.dumps(self.config))
                label.unlink()
                label.symlink_to(other)
                self.assertFalse(policy.experimental_label(label))

    def test_manual_selection_rejects_unregistered_default_and_invalid_inputs(self):
        for selection in ('["ordinary"]', '["default"]', '[]', '["kspacefilter", "kspacefilter"]', '[1]', '{}', '["../kspacefilter"]'):
            with patch.object(sys, 'argv', ['build_policy.py', 'select', selection]):
                with self.assertRaises(ValueError):
                    policy.main()
        with patch.object(sys, 'argv', ['build_policy.py', 'select', '["kspacefilter"]']):
            policy.main()


class BuildCleanupTests(unittest.TestCase):
    def run_cleanup(self, root, application):
        return subprocess.run(
            ['bash', str(ROOT / '.github/scripts/cleanup-build.sh'), application],
            cwd=root, capture_output=True, text=True, check=False,
        )

    def test_removes_outputs_and_preserves_recipe_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe = root / 'recipes/test-app'
            recipe.mkdir(parents=True)
            for name in ('OpenReconLabel.json', 'params.sh', 'README.md',
                         'OpenRecon_test.tar', 'FIRE_test.img',
                         'FIRE_test.rootfs.tar', '.base_image.tar'):
                (recipe / name).write_text('fixture')
            for name in ('openrecon', 'fire', 'fire-bundle-stage'):
                (recipe / name).mkdir()
                (recipe / name / 'output').write_text('fixture')

            result = self.run_cleanup(root, 'test-app')

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(sorted(path.name for path in recipe.iterdir()),
                             ['OpenReconLabel.json', 'README.md', 'params.sh'])
            self.assertEqual(self.run_cleanup(root, 'test-app').returncode, 0)

    def test_rejects_invalid_names_without_deleting_outside_recipes(self):
        for application in ('', '..', '../outside', 'outside/../../outside'):
            with self.subTest(application=application), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'recipes').mkdir()
                (root / 'recipes/outside').mkdir()
                output = root / 'openrecon'
                output.mkdir()
                marker = output / 'keep'
                marker.write_text('outside recipe')
                (root / 'outside').symlink_to(root, target_is_directory=True)

                result = self.run_cleanup(root, application)

                self.assertTrue(marker.is_file(), result.stdout + result.stderr)
                self.assertNotEqual(result.returncode, 0)

    def test_rejects_symlinked_and_unregistered_recipe_directories(self):
        for symlinked in (False, True):
            with self.subTest(symlinked=symlinked), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                recipes = root / 'recipes'
                recipes.mkdir()
                recipe = root / 'outside' if symlinked else recipes / 'unknown'
                (recipe / 'fire').mkdir(parents=True)
                marker = recipe / 'fire/keep'
                marker.write_text('keep')
                if symlinked:
                    (recipe / 'OpenReconLabel.json').write_text('{}')
                    (recipes / 'unknown').symlink_to(recipe, target_is_directory=True)

                result = self.run_cleanup(root, 'unknown')

                self.assertTrue(marker.is_file(), result.stdout + result.stderr)
                self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
