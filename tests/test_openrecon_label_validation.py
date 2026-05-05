import importlib.util
import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD_PY = REPO_ROOT / 'recipes' / 'build.py'
SPEC = importlib.util.spec_from_file_location('openrecon_build', BUILD_PY)
openrecon_build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(openrecon_build)


def base_label(parameters):
    return {
        'general': {'name': {'en': 'test'}, 'version': '1.0.0', 'vendor': 'neurodesk'},
        'reconstruction': {},
        'parameters': parameters,
    }


def config_parameter(values=None, default='validconfig'):
    if values is None:
        values = [{'id': 'validconfig', 'name': {'en': 'validconfig'}}]
    return {
        'id': 'config',
        'label': {'en': 'config'},
        'type': 'choice',
        'values': values,
        'default': default,
    }


class OpenReconLabelValidationTests(unittest.TestCase):
    def assert_validation_error(self, label, expected_text):
        with self.assertRaisesRegex(ValueError, expected_text):
            openrecon_build.validate_openrecon_label_metadata(label)

    def test_accepts_choice_default_listed_in_values(self):
        label = base_label(
            [
                config_parameter(),
                {
                    'id': 'metricsregion',
                    'label': {'en': 'Metrics Region'},
                    'type': 'choice',
                    'values': [
                        {'id': 'wholebody', 'name': {'en': 'wholebody'}},
                        {'id': 'abdomen', 'name': {'en': 'abdomen'}},
                        {'id': 'pelvis', 'name': {'en': 'pelvis'}},
                        {'id': 'thigh', 'name': {'en': 'thigh'}},
                        {'id': 'leg', 'name': {'en': 'leg'}},
                    ],
                    'default': 'wholebody',
                },
            ]
        )

        openrecon_build.validate_openrecon_label_metadata(label)

    def test_rejects_empty_choice_default(self):
        label = base_label(
            [
                config_parameter(),
                {
                    'id': 'metricsregion',
                    'label': {'en': 'Metrics Region'},
                    'type': 'choice',
                    'values': [{'id': 'wholebody', 'name': {'en': 'wholebody'}}],
                    'default': '',
                },
            ]
        )

        self.assert_validation_error(label, 'empty default')

    def test_rejects_choice_default_not_in_values(self):
        label = base_label(
            [
                config_parameter(),
                {
                    'id': 'metricsregion',
                    'label': {'en': 'Metrics Region'},
                    'type': 'choice',
                    'values': [{'id': 'wholebody', 'name': {'en': 'wholebody'}}],
                    'default': 'leg',
                },
            ]
        )

        self.assert_validation_error(label, 'not listed in values')

    def test_rejects_missing_config_parameter(self):
        label = base_label(
            [
                {
                    'id': 'metricsregion',
                    'label': {'en': 'Metrics Region'},
                    'type': 'choice',
                    'values': [{'id': 'wholebody', 'name': {'en': 'wholebody'}}],
                    'default': 'wholebody',
                },
            ]
        )

        self.assert_validation_error(label, 'exactly one parameter with id "config"; found 0')

    def test_rejects_duplicate_config_parameter(self):
        label = base_label([config_parameter(), config_parameter(default='other')])

        self.assert_validation_error(label, 'exactly one parameter with id "config"; found 2')

    def test_rejects_malformed_config_parameter(self):
        label = base_label(
            [
                {
                    'id': 'config',
                    'label': {'en': 'config'},
                    'type': 'string',
                    'default': 'validconfig',
                },
            ]
        )

        self.assert_validation_error(label, 'parameter "config" must have type "choice"')

    def test_rejects_duplicate_parameter_ids_and_choice_value_ids(self):
        label = base_label(
            [
                config_parameter(
                    values=[
                        {'id': 'validconfig', 'name': {'en': 'validconfig'}},
                        {'id': 'validconfig', 'name': {'en': 'validconfig duplicate'}},
                    ]
                ),
                {
                    'id': 'sendoriginal',
                    'label': {'en': 'Send original'},
                    'type': 'boolean',
                    'default': True,
                },
                {
                    'id': 'sendoriginal',
                    'label': {'en': 'Send original again'},
                    'type': 'boolean',
                    'default': False,
                },
            ]
        )

        self.assert_validation_error(label, 'duplicate')

    def test_extracts_config_module_names(self):
        label = base_label([config_parameter(values=[{'id': 'one', 'name': {'en': 'one'}}, {'id': 'two', 'name': {'en': 'two'}}])])

        self.assertEqual(openrecon_build.get_openrecon_config_module_names(label), ['one', 'two'])

    def test_config_module_validation_script_checks_importable_process_modules(self):
        script = openrecon_build.create_config_module_validation_script('OpenRecon_test:V1.0.0', ['musclemap'])

        self.assertIn('docker run --rm --platform linux/amd64', script)
        self.assertIn('/opt/code/python-ismrmrd-server', script)
        self.assertIn('importlib.util.find_spec', script)
        self.assertIn('callable(process)', script)
        self.assertIn('Direct container validation failed', script)
        self.assertIn('docker cp "${tmp_container}:/." "${validation_root}"', script)
        self.assertIn('openrecon_config_validation_env.sh', script)
        self.assertIn('chroot "${validation_root}"', script)
        self.assertIn('musclemap', script)


if __name__ == '__main__':
    unittest.main()
