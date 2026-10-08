import copy
import json
from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
