import contextlib
import io
import json
import os
import shlex
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_build_script_environment import BUILD_SCRIPT, REPOSITORY_ROOT
from test_openrecon_label_validation import openrecon_build


class BaseImageSelectionTests(unittest.TestCase):
    def run_selection(self, base_image, cached, override='', local_only=False,
                      remote_only=False, flags=()):
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
            scripts = {'python3': (
                'if [ "$1" = "-u" ]; then\n'
                '  printf "BUILD_ENV:%s|%s|%s|%s\\n" "$baseDockerImage" '
                '"$DOCKER_IMAGE_TO_USE" "$USE_LOCAL_IMAGE" "$FORCE_LOCAL_ONLY"\n'
                '  printf "REGISTRY_IMAGE:%s\\n" "$REGISTRY_BASE_DOCKER_IMAGE"\n'
                'fi\nexit 0'
            ), '7z': 'exit 0'}
            scripts['docker'] = (
                'if [ "$1 $2" = "image inspect" ]; then\n'
                '  echo "$3" >> docker-inspections.log\n'
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
            if remote_only:
                command.append('--remote-only')
            command.extend(flags)
            result = subprocess.run(command, cwd=recipe, env=environment,
                                    capture_output=True, text=True)
            inspection_log = recipe / 'docker-inspections.log'
            result.inspections = inspection_log.read_text().splitlines() if inspection_log.exists() else []
            return result

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
        self.assertIn('REGISTRY_IMAGE:registry/test:20261005\n', result.stdout)

    def test_remote_only_ignores_all_host_images_and_preserves_reference(self):
        for reference in ('registry:5000/test_1.0.0', 'registry/test:latest',
                          'registry/test:20261005', 'registry/test@sha256:' + 'a' * 64):
            for cached in ([], ['test:1.0.0', reference, 'intentional:local']):
                with self.subTest(reference=reference, cached=cached):
                    result = self.run_selection(reference, cached, override='intentional:local',
                                                remote_only=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn(f'Using remote image (forced): {reference}', result.stdout)
                    self.assertIn(f'BUILD_ENV:{reference}|{reference}|false|false\n', result.stdout)
                    self.assertEqual(result.inspections, [])

    def test_remote_only_and_local_cache_conflict_in_either_order(self):
        for flags in (('--remote-only', '--local-cache'), ('--local-cache', '--remote-only')):
            with self.subTest(flags=flags):
                result = self.run_selection('registry/test_1.0.0', ['test:1.0.0'], flags=flags)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('--remote-only and --local-cache cannot be used together', result.stdout)
                self.assertNotIn('Using virtual-environment Python', result.stdout)
                self.assertNotIn('BUILD_ENV:', result.stdout)
                self.assertEqual(result.inspections, [])

    def test_local_cache_still_requires_and_uses_local_image(self):
        result = self.run_selection('registry/test_1.0.0', ['test:1.0.0'], local_only=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('BUILD_ENV:test:1.0.0|test:1.0.0|true|true\n', result.stdout)

    def test_publishing_workflows_require_remote_base_images(self):
        for filename in ('build-apps.yml', 'build-experimental-openrecon.yml'):
            with self.subTest(workflow=filename):
                workflow = (REPOSITORY_ROOT / '.github/workflows' / filename).read_text()
                build_commands = [line for line in workflow.splitlines() if '/bin/bash ../build.sh' in line]
                self.assertTrue(build_commands)
                for command in build_commands:
                    self.assertIn('--remote-only', command)
                    self.assertNotIn('--local-cache', command)

    def test_remote_dind_build_does_not_reuse_base_image_archive(self):
        # Even an existing .base_image.tar must not be loaded into a remote build.
        with (
            mock.patch.object(openrecon_build.os.path, 'exists', return_value=True),
            mock.patch.object(openrecon_build, 'ensure_dind_image_available') as ensure_dind,
            mock.patch.object(openrecon_build, 'run_dind_build_process') as run_dind,
            mock.patch.object(openrecon_build.subprocess, 'check_output') as check_output,
            mock.patch.object(openrecon_build.subprocess, 'run'),
        ):
            for _ in range(2):
                archive = openrecon_build.build_artifacts_in_dind(
                    docker_image_name='openrecon_test:v1.0.0',
                    dockerfile_path='OpenRecon.dockerfile',
                    openrecon_tar_name='OpenRecon_test.tar',
                    fire_img_name='FIRE_test.img',
                    fire_rootfs_tar_name='FIRE_test.rootfs.tar',
                    create_openrecon_package=True,
                    create_fire_package=False,
                    use_local_image=False,
                    base_docker_image='registry/test_1.0.0',
                    force_local_only=False,
                    keep_cache=True,
                    fire_free_space_mb=50,
                    fire_server_command=openrecon_build.get_fire_server_command(),
                    startup_script_path='/usr/local/bin/start-fire-openrecon.sh',
                    validate_default_runtime=True,
                    config_module_names=['test'],
                )
                self.assertIsNone(archive)

        self.assertEqual(run_dind.call_count, 2)
        volumes = []
        for call in check_output.call_args_list:
            command = call.args[0]
            self.assertEqual(command[:3], ['docker', 'volume', 'create'])
            volumes.append(command[3])
        self.assertEqual(len(set(volumes)), 2)
        for call, volume in zip(run_dind.call_args_list, volumes):
            command = call.args[0]
            self.assertIn(f'{volume}:/var/lib/docker', command)
            self.assertIn('docker build ', command[-1])
            self.assertNotIn('docker load', command[-1])
            self.assertNotIn('.base_image.tar', command[-1])
        ensure_dind.assert_called_with('docker:24.0-dind', False)


class BaseImageArchiveTests(unittest.TestCase):
    PINNED_IMAGE = 'registry/test:20261014@sha256:' + 'a' * 64
    CONFIG = 'blobs/sha256/' + 'b' * 64
    LAYER = 'blobs/sha256/' + 'c' * 64

    def write_tar(self, path, members):
        with tarfile.open(path, 'w') as archive:
            for name, content in members.items():
                member = tarfile.TarInfo(name)
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))

    def write_archive(self, path, missing=()):
        manifest = [{'Config': self.CONFIG, 'RepoTags': [], 'Layers': [self.LAYER]}]
        members = {
            'manifest.json': json.dumps(manifest).encode(),
            self.CONFIG: b'{}',
            self.LAYER: b'layer contents',
        }
        self.write_tar(path, {name: content for name, content in members.items() if name not in missing})

    @contextlib.contextmanager
    def build_context(self, missing=(), existing=True):
        with tempfile.TemporaryDirectory() as directory, contextlib.chdir(directory):
            root = Path(directory)
            if existing:
                self.write_archive(root / '.base_image.tar', missing)
            openrecon_build.write_openrecon_dockerfile(
                self.PINNED_IMAGE, 'OpenRecon.dockerfile', {},
            )

            def docker_command(command, **kwargs):
                if command[:2] == ['docker', 'save']:
                    self.write_archive(root / command[3], missing)
                return b''

            with (
                mock.patch.dict(os.environ, {'CI': '1'}),
                mock.patch.object(openrecon_build, 'ensure_dind_image_available') as ensure_dind,
                mock.patch.object(openrecon_build, 'run_dind_build_process') as run_dind,
                mock.patch.object(openrecon_build.subprocess, 'check_output', side_effect=docker_command),
                mock.patch.object(openrecon_build.subprocess, 'run'),
            ):
                yield root, ensure_dind, run_dind

    def build(self, **overrides):
        arguments = dict(
            docker_image_name='openrecon_test:v1.0.0',
            dockerfile_path='OpenRecon.dockerfile',
            openrecon_tar_name='OpenRecon_test.tar',
            fire_img_name='FIRE_test.img',
            fire_rootfs_tar_name='FIRE_test.rootfs.tar',
            create_openrecon_package=True,
            create_fire_package=False,
            use_local_image=True,
            base_docker_image=self.PINNED_IMAGE,
            force_local_only=False,
            keep_cache=True,
            fire_free_space_mb=50,
            fire_server_command=openrecon_build.get_fire_server_command(),
            startup_script_path='/usr/local/bin/start-fire-openrecon.sh',
            validate_default_runtime=True,
            config_module_names=['test'],
        )
        arguments.update(overrides)
        return openrecon_build.build_artifacts_in_dind(**arguments)

    def test_incomplete_digest_cache_falls_back_to_registry(self):
        for existing in (False, True):
            for missing in ((self.CONFIG,), (self.LAYER,), (self.CONFIG, self.LAYER)):
                with self.subTest(existing=existing, missing=missing), self.build_context(
                    missing=missing, existing=existing,
                ) as (root, _, run_dind):
                    self.assertIsNone(self.build())
                    self.assertFalse((root / '.base_image.tar').exists())
                    self.assertNotIn('docker load', run_dind.call_args.args[0][-1])
                    self.assertEqual(
                        (root / 'OpenRecon.dockerfile').read_text().splitlines()[0],
                        f'FROM {self.PINNED_IMAGE}',
                    )

    def test_incomplete_digest_cache_fails_in_local_only_mode(self):
        for existing in (False, True):
            for missing in ((self.CONFIG,), (self.LAYER,), (self.CONFIG, self.LAYER)):
                with self.subTest(existing=existing, missing=missing), self.build_context(
                    missing=missing, existing=existing,
                ) as (root, ensure_dind, run_dind):
                    with self.assertRaisesRegex(RuntimeError, f'cache integrity.*{missing[0]}'):
                        self.build(force_local_only=True)
                    self.assertFalse((root / '.base_image.tar').exists())
                    ensure_dind.assert_not_called()
                    run_dind.assert_not_called()

    def test_complete_archive_is_loaded_in_online_and_local_only_modes(self):
        for existing in (False, True):
            for local_only in (False, True):
                with self.subTest(existing=existing, local_only=local_only), self.build_context(
                    existing=existing,
                ) as (root, ensure_dind, run_dind):
                    self.assertEqual(self.build(force_local_only=local_only), '.base_image.tar')
                    self.assertTrue((root / '.base_image.tar').is_file())
                    self.assertIn('docker load -i /workspace/.base_image.tar', run_dind.call_args.args[0][-1])
                    ensure_dind.assert_called_once_with('docker:24.0-dind', local_only)

    def test_incomplete_local_override_falls_back_to_declared_registry_reference(self):
        with self.build_context(missing=(self.LAYER,)) as (root, _, run_dind):
            dockerfile = root / 'OpenRecon.dockerfile'
            openrecon_build.write_openrecon_dockerfile('intentional:local', dockerfile, {})
            original_instructions = dockerfile.read_text().splitlines()[1:]
            self.assertIsNone(self.build(
                base_docker_image='intentional:local', registry_base_docker_image=self.PINNED_IMAGE,
            ))
            self.assertEqual(dockerfile.read_text().splitlines(), [
                f'FROM {self.PINNED_IMAGE}', *original_instructions,
            ])
            self.assertNotIn('docker load', run_dind.call_args.args[0][-1])

    def test_invalid_archives_fail_before_starting_dind(self):
        manifests = [b'not JSON', b'[]', b'{}', b'[{}]',
                     b'[{"Config": "config.json", "Layers": "layer.tar"}]',
                     b'[{"Config": "config.json", "Layers": [null]}]']
        invalid_members = [
            {},
            *({'manifest.json': manifest, 'config.json': b'{}'} for manifest in manifests),
        ]
        for members in invalid_members:
            with self.subTest(members=members), self.build_context() as (root, ensure_dind, run_dind):
                self.write_tar(root / '.base_image.tar', members)
                with self.assertRaisesRegex(RuntimeError, 'cache integrity'):
                    self.build(force_local_only=True)
                ensure_dind.assert_not_called()
                run_dind.assert_not_called()
                self.assertFalse((root / '.base_image.tar').exists())

    def test_truncated_archive_is_rejected(self):
        with self.build_context() as (root, ensure_dind, run_dind):
            archive_path = root / '.base_image.tar'
            with tarfile.open(archive_path) as archive:
                layer_offset = archive.getmember(self.LAYER).offset_data
            with archive_path.open('r+b') as archive_file:
                archive_file.truncate(layer_offset + 3)
            with self.assertRaisesRegex(RuntimeError, 'cache integrity'):
                self.build(force_local_only=True)
            ensure_dind.assert_not_called()
            run_dind.assert_not_called()

    def test_classic_docker_save_layout_and_scratch_images_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / 'image.tar'
            for layers in ([], ['layer/layer.tar']):
                with self.subTest(layers=layers):
                    manifest = [{'Config': 'config.json', 'Layers': layers}]
                    self.write_tar(archive_path, {
                        'manifest.json': json.dumps(manifest).encode(),
                        'config.json': b'{}',
                        'layer/layer.tar': b'layer contents',
                    })
                    openrecon_build.validate_docker_image_archive(archive_path)
