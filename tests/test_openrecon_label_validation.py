import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock


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

    def test_creates_fire_config_json_from_openrecon_label_defaults(self):
        label = base_label(
            [
                config_parameter(values=[{'id': 'vesselboost', 'name': {'en': 'vesselboost'}}]),
                {'id': 'sendoriginal', 'type': 'boolean', 'default': True},
                {'id': 'vbuseblending', 'type': 'boolean', 'default': False},
                {'id': 'vboverlap', 'type': 'int', 'default': 50},
                {'id': 'runtimeonly', 'type': 'string'},
            ]
        )

        config = json.loads(openrecon_build.create_fire_config_json_text(label, 'vesselboost'))

        self.assertEqual(
            config,
            {
                'version': '1.1.0',
                'parameters': {
                    'config': 'vesselboost',
                    'sendoriginal': True,
                    'vbuseblending': False,
                    'vboverlap': 50,
                },
            },
        )

    def test_writes_fire_config_json_files_and_allows_recipe_overrides(self):
        label = base_label(
            [
                config_parameter(
                    values=[
                        {'id': 'generated', 'name': {'en': 'generated'}},
                        {'id': 'override', 'name': {'en': 'override'}},
                    ],
                    default='generated',
                ),
                {'id': 'sendoriginal', 'type': 'boolean', 'default': True},
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = pathlib.Path(tmpdir)
            stage_dir = tmpdir / 'stage'
            recipe_dir = tmpdir / 'recipe'
            stage_dir.mkdir()
            recipe_dir.mkdir()
            override = {'version': '1.1.0', 'parameters': {'config': 'override', 'sendoriginal': False}}
            (recipe_dir / 'wip_070_fire_override.json').write_text(json.dumps(override))

            written = openrecon_build.write_fire_config_json_files(stage_dir, recipe_dir, label)

            self.assertIn('fire/config/wip_070_fire_generated.json', written)
            self.assertIn('fire/config/wip_070_fire_override.json', written)
            generated_path = stage_dir / 'fire' / 'config' / 'wip_070_fire_generated.json'
            override_path = stage_dir / 'fire' / 'config' / 'wip_070_fire_override.json'
            self.assertEqual(json.loads(generated_path.read_text())['parameters']['sendoriginal'], True)
            self.assertEqual(json.loads(override_path.read_text()), override)

    def test_fire_ini_name_and_install_text_are_direct_copy_ready(self):
        ini_name = openrecon_build.get_fire_ini_filename('openreconi2iexample')
        install_text = openrecon_build.create_fire_install_text('FIRE_neurodesk_openreconi2iexample_V1.0.57.img', ini_name)

        self.assertEqual(ini_name, 'wip_070_fire_openreconi2iexample.ini')
        self.assertIn('Included scanner-copy paths', install_text)
        self.assertIn('MriCustomer\\Ice', install_text)
        self.assertIn('Ice\\wip_070_fire_*.ipr', install_text)
        self.assertIn('Ice\\fire\\chroot\\FIRE_neurodesk_openreconi2iexample_V1.0.57.img', install_text)
        self.assertIn('Ice\\fire\\wip_070_fire_openreconi2iexample.ini', install_text)
        self.assertIn('Ice\\fire\\share\\code', install_text)
        self.assertIn('README.md', install_text)
        self.assertNotIn('fire.ini.template', install_text)
        self.assertNotIn('IceFireImageAddin', install_text)
        self.assertNotIn('Typical scanner-side locations', install_text)

    def test_fire_ini_template_includes_openrecon_connection_section(self):
        ini_text = openrecon_build.create_fire_ini_template(
            'FIRE_neurodesk_openreconi2iexample_V1.0.70.img',
            '/usr/local/bin/start-fire-openrecon.sh',
            'python3',
        )

        self.assertIn('[OpenRecon]', ini_text)
        self.assertIn('hostname=192.168.2.2', ini_text)
        self.assertIn('port=9002', ini_text)
        self.assertIn('[chroot]', ini_text)
        self.assertLess(ini_text.index('[OpenRecon]'), ini_text.index('[chroot]'))

    def test_fire_bundle_stage_puts_scanner_files_under_ice(self):
        label = base_label(
            [
                config_parameter(values=[{'id': 'openreconi2iexample', 'name': {'en': 'openreconi2iexample'}}]),
                {'id': 'sendoriginal', 'type': 'boolean', 'default': False},
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = pathlib.Path(tmpdir)
            stage_dir = tmpdir / 'stage'
            recipe_dir = tmpdir / 'recipe'
            stage_dir.mkdir()
            recipe_dir.mkdir()
            (recipe_dir / 'wip_070_fire_IceFireImageAddin_VesselBoost.ipr').write_text('wrong package')
            (recipe_dir / 'wip_070_fire_IceFireImageAddin_VesselBoost.xml').write_text('wrong package')
            (recipe_dir / 'README.md').write_text('# openreconi2iexample\n')
            fire_img = tmpdir / 'FIRE_neurodesk_openreconi2iexample_V1.0.57.img'
            docs = tmpdir / 'OpenRecon_neurodesk_openreconi2iexample_V1.0.57.pdf'
            fire_img.write_text('img')
            docs.write_text('pdf')
            ini_name = openrecon_build.get_fire_ini_filename('openreconi2iexample')

            openrecon_build.build_fire_bundle_stage(
                stage_dir=stage_dir,
                fire_img_path=fire_img,
                fire_ini_name=ini_name,
                fire_ini_text='[chroot]\n',
                install_text='install\n',
                docs_source_path=docs,
                json_data=label,
                package_name='openreconi2iexample',
                recipe_dir=recipe_dir,
            )

            ice_dir = stage_dir / 'Ice'
            self.assertTrue((ice_dir / 'wip_070_fire_openreconi2iexample.ipr').is_file())
            self.assertTrue((ice_dir / 'wip_070_fire_openreconi2iexample.xml').is_file())
            self.assertTrue((ice_dir / 'fire' / 'chroot' / fire_img.name).is_file())
            self.assertTrue((ice_dir / 'fire' / ini_name).is_file())
            self.assertTrue((ice_dir / 'fire' / 'config' / 'wip_070_fire_openreconi2iexample.json').is_file())
            self.assertTrue((ice_dir / 'fire' / 'share' / 'code' / 'PLACEHOLDER.txt').is_file())
            self.assertTrue((stage_dir / 'INSTALL_FIRE.txt').is_file())
            self.assertTrue((stage_dir / 'README.md').is_file())
            self.assertTrue((stage_dir / docs.name).is_file())
            self.assertFalse((stage_dir / 'fire').exists())
            self.assertFalse((stage_dir / fire_img.name).exists())
            self.assertFalse((stage_dir / 'share').exists())
            self.assertFalse((stage_dir / 'wip_070_fire_IceFireImageAddin_VesselBoost.ipr').exists())
            self.assertFalse((stage_dir / 'wip_070_fire_IceFireImageAddin_VesselBoost.xml').exists())
            self.assertFalse((ice_dir / 'wip_070_fire_IceFireImageAddin_openreconi2iexample.ipr').exists())
            self.assertFalse((ice_dir / 'wip_070_fire_IceFireImageAddin_openreconi2iexample.xml').exists())

    def test_fire_bundle_stage_uses_exact_recipe_workflow_file_overrides(self):
        label = base_label(
            [
                config_parameter(values=[{'id': 'sodiumnufft', 'name': {'en': 'sodiumnufft'}}]),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = pathlib.Path(tmpdir)
            stage_dir = tmpdir / 'stage'
            recipe_dir = tmpdir / 'recipe'
            stage_dir.mkdir()
            recipe_dir.mkdir()
            (recipe_dir / 'wip_070_fire_sodiumnufft.xml').write_text('<custom-workflow />\n')
            (recipe_dir / 'wip_070_fire_sodiumnufft.ipr').write_text('<custom-ipr />\n')
            fire_img = tmpdir / 'FIRE_neurodesk_sodiumnufft_V0.1.4.img'
            docs = tmpdir / 'OpenRecon_neurodesk_sodiumnufft_V0.1.4.pdf'
            fire_img.write_text('img')
            docs.write_text('pdf')

            openrecon_build.build_fire_bundle_stage(
                stage_dir=stage_dir,
                fire_img_path=fire_img,
                fire_ini_name=openrecon_build.get_fire_ini_filename('sodiumnufft'),
                fire_ini_text='[chroot]\n',
                install_text='install\n',
                docs_source_path=docs,
                json_data=label,
                package_name='sodiumnufft',
                recipe_dir=recipe_dir,
            )

            ice_dir = stage_dir / 'Ice'
            self.assertEqual((ice_dir / 'wip_070_fire_sodiumnufft.xml').read_text(), '<custom-workflow />\n')
            self.assertEqual((ice_dir / 'wip_070_fire_sodiumnufft.ipr').read_text(), '<custom-ipr />\n')
            self.assertTrue((ice_dir / 'fire' / 'config' / 'wip_070_fire_sodiumnufft.json').is_file())

    def test_removes_platform_metadata_files_from_fire_bundle_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = pathlib.Path(tmpdir) / 'bundle'
            nested_dir = bundle_dir / 'fire'
            nested_dir.mkdir(parents=True)
            (bundle_dir / '._INSTALL_FIRE.txt').write_text('metadata')
            (bundle_dir / '.DS_Store').write_text('metadata')
            (nested_dir / '._config').write_text('metadata')
            (nested_dir / 'wip_070_fire_test.ini').write_text('[chroot]\n')

            openrecon_build.remove_platform_metadata_files(bundle_dir)

            self.assertFalse((bundle_dir / '._INSTALL_FIRE.txt').exists())
            self.assertFalse((bundle_dir / '.DS_Store').exists())
            self.assertFalse((nested_dir / '._config').exists())
            self.assertTrue((nested_dir / 'wip_070_fire_test.ini').exists())

    def test_config_module_validation_script_checks_importable_process_modules(self):
        script = openrecon_build.create_config_module_validation_script('OpenRecon_test:V1.0.0', ['musclemap'])

        self.assertIn('docker run --rm --platform linux/amd64', script)
        self.assertIn('/opt/code/python-ismrmrd-server', script)
        self.assertIn('importlib.util.find_spec', script)
        self.assertIn('callable(process)', script)
        self.assertIn('direct_validation_log=/tmp/openrecon_config_direct_validation.log', script)
        self.assertIn('>"${direct_validation_log}" 2>&1', script)
        self.assertIn('resolve_openrecon_python()', script)
        self.assertIn('python3 python python3.11', script)
        self.assertIn("can_import_openrecon_python_requirements", script)
        self.assertIn('"import ismrmrd"', script)
        self.assertIn('"$OPENRECON_PYTHON" - "$@"', script)
        self.assertIn('Direct container validation failed', script)
        self.assertIn('docker cp "${tmp_container}:/." "${validation_root}"', script)
        self.assertIn('create_chroot_device urandom 1 9', script)
        self.assertIn('mknod -m 666 "${device_path}"', script)
        self.assertIn('openrecon_config_validation_env.sh', script)
        self.assertIn('chroot "${validation_root}"', script)
        self.assertIn('Direct container validation output:', script)
        self.assertIn('exit "$fallback_status"', script)
        self.assertIn('musclemap', script)

    def test_retries_transient_dind_wrapper_start_failure(self):
        class FakeStdout:
            def __init__(self, lines):
                self.lines = iter(lines)

            def __iter__(self):
                return self

            def __next__(self):
                return next(self.lines)

            def close(self):
                pass

        class FakeProcess:
            def __init__(self, lines, returncode):
                self.stdout = FakeStdout(lines)
                self.returncode = returncode

            def wait(self):
                return self.returncode

        failing_lines = [
            'docker: Error response from daemon: failed to create task for container: '
            'failed to create shim task: OCI runtime create failed: runc create failed: '
            'unable to start container process: waiting for init preliminary setup: '
            'read init-p: connection reset by peer: unknown.\n',
        ]
        successful_lines = ['✓ Docker daemon is ready\n']
        processes = [
            FakeProcess(failing_lines, 125),
            FakeProcess(successful_lines, 0),
        ]

        with mock.patch.object(openrecon_build.subprocess, 'Popen', side_effect=processes) as popen_mock:
            output = openrecon_build.run_dind_build_process(
                ['docker', 'run', '--rm', 'docker:24.0-dind'],
                max_attempts=2,
                retry_delay_seconds=0,
            )

        self.assertEqual(popen_mock.call_count, 2)
        self.assertIn('✓ Docker daemon is ready', output)

    def test_does_not_retry_non_transient_dind_build_failure(self):
        class FakeStdout:
            def __iter__(self):
                return iter(['The command failed for a recipe-specific reason\n'])

            def close(self):
                pass

        class FakeProcess:
            stdout = FakeStdout()
            returncode = 1

            def wait(self):
                return self.returncode

        with mock.patch.object(openrecon_build.subprocess, 'Popen', return_value=FakeProcess()) as popen_mock:
            with self.assertRaises(subprocess.CalledProcessError):
                openrecon_build.run_dind_build_process(
                    ['docker', 'run', '--rm', 'docker:24.0-dind'],
                    max_attempts=2,
                    retry_delay_seconds=0,
                )

        self.assertEqual(popen_mock.call_count, 1)

    def test_does_not_retry_inner_validation_container_start_failure(self):
        class FakeStdout:
            def __iter__(self):
                return iter([
                    '🚀 Starting Docker daemon...\n',
                    '✓ Docker daemon is ready\n',
                    '🔍 Validating OpenRecon config modules inside image...\n',
                    'docker: Error response from daemon: failed to create task for container: '
                    'failed to create shim task: OCI runtime create failed: runc create failed: '
                    'unable to start container process: waiting for init preliminary setup: '
                    'read init-p: connection reset by peer: unknown.\n',
                ])

            def close(self):
                pass

        class FakeProcess:
            stdout = FakeStdout()
            returncode = 1

            def wait(self):
                return self.returncode

        with mock.patch.object(openrecon_build.subprocess, 'Popen', return_value=FakeProcess()) as popen_mock:
            with self.assertRaises(subprocess.CalledProcessError):
                openrecon_build.run_dind_build_process(
                    ['docker', 'run', '--rm', 'docker:24.0-dind'],
                    max_attempts=2,
                    retry_delay_seconds=0,
                )

        self.assertEqual(popen_mock.call_count, 1)

    def test_openrecon_dockerfile_resolves_python_for_runtime_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dockerfile_path = pathlib.Path(tmpdir) / 'OpenRecon.dockerfile'
            openrecon_build.write_openrecon_dockerfile(
                'openmsk:0.1.2',
                dockerfile_path,
                base_label([config_parameter()]),
            )

            dockerfile_text = dockerfile_path.read_text()

        self.assertIn('FROM openmsk:0.1.2', dockerfile_text)
        self.assertIn('resolve_openrecon_python', dockerfile_text)
        self.assertIn('python3 python python3.11', dockerfile_text)
        self.assertIn('OPENRECON_PYTHON', dockerfile_text)
        self.assertNotIn('exec python3 /opt/code/python-ismrmrd-server/main.py', dockerfile_text)

    def test_python_resolver_preserves_explicit_override(self):
        resolver = openrecon_build.create_openrecon_python_resolver_script()

        self.assertIn('if command -v "${OPENRECON_PYTHON}"', resolver)
        self.assertIn('can_import_openrecon_python_requirements "${OPENRECON_PYTHON}"', resolver)
        self.assertIn('printf "%s\\n" "${OPENRECON_PYTHON}"', resolver)
        self.assertIn('return 1', resolver)

    def test_fire_startup_script_sources_docker_env_before_resolving_python(self):
        startup_script = openrecon_build.create_fire_startup_script_text(openrecon_build.get_fire_server_command())

        env_source_index = startup_script.index('. /etc/openrecon-fire-env.sh')
        python_validation_index = startup_script.index('command -v "$OPENRECON_PYTHON"')
        startup_exec_index = startup_script.index(
            'exec sh -c \'"$OPENRECON_PYTHON" /opt/code/python-ismrmrd-server/main.py'
        )

        self.assertLess(env_source_index, python_validation_index)
        self.assertLess(env_source_index, startup_exec_index)
        self.assertIn('resolve_openrecon_python()', startup_script)
        self.assertIn('python3 python python3.11', startup_script)
        self.assertIn('OPENRECON_FIRE_VALIDATE_STARTUP', startup_script)

    def test_fire_startup_executable_supports_conda_override(self):
        command = '/opt/conda/bin/python3 /opt/code/python-ismrmrd-server/main.py -v -l "$LOG_PATH"'

        self.assertEqual(openrecon_build.get_fire_startup_executable(command), '/opt/conda/bin/python3')


if __name__ == '__main__':
    unittest.main()
