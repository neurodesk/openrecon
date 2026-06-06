import base64
import json
import jsonschema
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
from pathlib import Path


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, write_through=True)


FIRE_ENV_SCRIPT_PATH = '/etc/openrecon-fire-env.sh'
FIRE_STARTUP_VALIDATION_ENV = 'OPENRECON_FIRE_VALIDATE_STARTUP'
OPENRECON_JSON_CONFIG_VERSION = '1.1.0'
DIND_RUN_ATTEMPTS_ENV = 'OPENRECON_DIND_RUN_ATTEMPTS'
DIND_RETRY_DELAY_SECONDS_ENV = 'OPENRECON_DIND_RETRY_DELAY_SECONDS'
OPENRECON_PYTHON_CANDIDATES = ('python3.11', 'python', 'python3')


def get_positive_int_env(name, default):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        print(f'⚠️  Ignoring invalid {name}={raw_value!r}; using {default}')
        return default
    if value < 1:
        print(f'⚠️  Ignoring invalid {name}={raw_value!r}; using {default}')
        return default
    return value


def get_nonnegative_float_env(name, default):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        print(f'⚠️  Ignoring invalid {name}={raw_value!r}; using {default}')
        return default
    if value < 0:
        print(f'⚠️  Ignoring invalid {name}={raw_value!r}; using {default}')
        return default
    return value


def is_transient_dind_wrapper_start_failure(output):
    output_lower = output.lower()
    return (
        'docker: error response from daemon' in output_lower
        and 'failed to create task for container' in output_lower
        and 'waiting for init preliminary setup' in output_lower
        and 'starting docker daemon' not in output_lower
    )


def run_dind_build_process(args, max_attempts=None, retry_delay_seconds=None):
    if max_attempts is None:
        max_attempts = get_positive_int_env(DIND_RUN_ATTEMPTS_ENV, 3)
    if retry_delay_seconds is None:
        retry_delay_seconds = get_nonnegative_float_env(DIND_RETRY_DELAY_SECONDS_ENV, 5)

    combined_output_lines = []
    for attempt in range(1, max_attempts + 1):
        if max_attempts > 1:
            print(f'🐳 Starting DinD build container (attempt {attempt}/{max_attempts})...')

        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        )

        output_lines = []
        try:
            for line in process.stdout:
                output_lines.append(line)
                combined_output_lines.append(line)
                print(line, end='')

            process.wait()
            output = ''.join(output_lines)
            if process.returncode == 0:
                return ''.join(combined_output_lines)

            if attempt < max_attempts and is_transient_dind_wrapper_start_failure(output):
                print(
                    '⚠️  DinD build container failed to start with a transient Docker runtime error; '
                    f'retrying in {retry_delay_seconds:g}s.'
                )
                if retry_delay_seconds:
                    time.sleep(retry_delay_seconds)
                continue

            raise subprocess.CalledProcessError(
                process.returncode,
                args,
                output=''.join(combined_output_lines),
            )
        finally:
            if process.stdout:
                process.stdout.close()

    raise subprocess.CalledProcessError(1, args, output=''.join(combined_output_lines))


def create_openrecon_python_resolver_script():
    candidates = ' '.join(shlex.quote(candidate) for candidate in OPENRECON_PYTHON_CANDIDATES)
    return textwrap.dedent(
        f'''\
        resolve_openrecon_python() {{
            if [ -n "${{OPENRECON_PYTHON:-}}" ]; then
                if command -v "${{OPENRECON_PYTHON}}" >/dev/null 2>&1; then
                    printf "%s\\n" "${{OPENRECON_PYTHON}}"
                    return 0
                fi
                return 1
            fi
            for python_exe in {candidates}; do
                if command -v "${{python_exe}}" >/dev/null 2>&1; then
                    printf "%s\\n" "${{python_exe}}"
                    return 0
                fi
            done
            return 1
        }}
        OPENRECON_PYTHON="$(resolve_openrecon_python)"
        export OPENRECON_PYTHON
        '''
    )


def create_openrecon_python_runtime_command(log_path):
    return textwrap.dedent(
        f'''\
        set -eu
        /usr/sbin/ldconfig
        {create_openrecon_python_resolver_script()}
        exec "$OPENRECON_PYTHON" /opt/code/python-ismrmrd-server/main.py -v -H=0.0.0.0 -p=9002 -l={log_path}
        '''
    )


def validateJson(jsonFilePath, schemaFilePath):
    try:
        with open(jsonFilePath, 'r') as jsonFile:
            jsonData = json.load(jsonFile)

        with open(schemaFilePath, 'r') as schemaFile:
            schemaData = json.load(schemaFile)

        validator = jsonschema.Draft7Validator(schemaData)
        errors = list(validator.iter_errors(jsonData))

        if not errors:
            print('JSON is valid against the schema.')
            return True

        print('JSON is not valid against the schema. Errors:')
        for error in errors:
            print(error)
        return False
    except Exception as e:
        print(f'An error occurred: {e}')
        return False


def get_parameter_label(parameter):
    parameter_id = parameter.get('id', '<missing id>')
    parameter_type = parameter.get('type', '<missing type>')
    return f'{parameter_type} parameter {parameter_id!r}'


def validate_openrecon_label_metadata(json_data):
    errors = []
    parameters = json_data.get('parameters', [])
    parameter_ids = []

    for parameter in parameters:
        parameter_id = parameter.get('id')
        parameter_ids.append(parameter_id)

        if parameter.get('type') != 'choice':
            continue

        label = get_parameter_label(parameter)
        values = parameter.get('values', [])
        value_ids = [value.get('id') for value in values]
        default = parameter.get('default')

        if default == '':
            errors.append(f'{label} has an empty default. Choice defaults must name one of values[*].id.')
        elif default not in value_ids:
            errors.append(f'{label} default {default!r} is not listed in values[*].id: {value_ids!r}.')

        for value_index, value_id in enumerate(value_ids):
            if not isinstance(value_id, str) or value_id == '':
                errors.append(f'{label} value at index {value_index} has an empty or non-string id.')

        duplicate_value_ids = sorted(
            value_id for value_id in set(value_ids) if value_id is not None and value_ids.count(value_id) > 1
        )
        if duplicate_value_ids:
            errors.append(f'{label} has duplicate choice value id(s): {duplicate_value_ids!r}.')

    duplicate_parameter_ids = sorted(
        parameter_id for parameter_id in set(parameter_ids) if parameter_id is not None and parameter_ids.count(parameter_id) > 1
    )
    if duplicate_parameter_ids:
        errors.append(f'OpenReconLabel.json has duplicate parameter id(s): {duplicate_parameter_ids!r}.')

    config_parameters = [parameter for parameter in parameters if parameter.get('id') == 'config']
    if len(config_parameters) != 1:
        errors.append(f'OpenReconLabel.json must contain exactly one parameter with id "config"; found {len(config_parameters)}.')
    else:
        config_parameter = config_parameters[0]
        if config_parameter.get('type') != 'choice':
            errors.append('OpenReconLabel.json parameter "config" must have type "choice".')
        if not config_parameter.get('values'):
            errors.append('OpenReconLabel.json parameter "config" must define at least one choice value.')

    if errors:
        raise ValueError('OpenReconLabel.json metadata validation failed:\n- ' + '\n- '.join(errors))


def get_openrecon_config_module_names(json_data):
    for parameter in json_data.get('parameters', []):
        if parameter.get('id') == 'config':
            return [value.get('id') for value in parameter.get('values', [])]
    return []


def get_default_openrecon_config_id(json_data):
    for parameter in json_data.get('parameters', []):
        if parameter.get('id') != 'config':
            continue
        default = parameter.get('default')
        if default:
            return default
        values = parameter.get('values', [])
        if values:
            return values[0].get('id')
    raise ValueError('OpenReconLabel.json must define a default config id for FIRE workflow generation')


def get_openrecon_parameter_defaults(json_data):
    defaults = {}
    for parameter in json_data.get('parameters', []):
        parameter_id = parameter.get('id')
        if not parameter_id or 'default' not in parameter:
            continue
        defaults[parameter_id] = parameter.get('default')
    return defaults


def create_config_module_validation_script(docker_image_name, config_module_names):
    config_modules_json = shlex.quote(json.dumps(config_module_names))
    docker_image_name_quoted = shlex.quote(docker_image_name)
    validation_python = textwrap.dedent(
        '''\
        import importlib
        import importlib.util
        import json
        import sys

        config_module_names = json.loads(sys.argv[1])
        errors = []

        for config_module_name in config_module_names:
            try:
                spec = importlib.util.find_spec(config_module_name)
            except Exception as exc:
                errors.append(f"{config_module_name!r} cannot be resolved as a Python module: {exc}")
                continue

            if spec is None:
                errors.append(f"{config_module_name!r} is not importable from /opt/code/python-ismrmrd-server")
                continue

            try:
                module = importlib.import_module(config_module_name)
            except Exception as exc:
                errors.append(f"{config_module_name!r} failed to import: {exc}")
                continue

            process = getattr(module, "process", None)
            if not callable(process):
                errors.append(f"{config_module_name!r} does not define a callable process function")

        if errors:
            print("OpenRecon config module validation failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            sys.exit(1)

        print("OpenRecon config module validation passed for: " + ", ".join(config_module_names))
        '''
    )
    return textwrap.dedent(
        f'''\
        echo "🔍 Validating OpenRecon config modules inside image..."
        config_modules_json={config_modules_json}
        direct_validation_log=/tmp/openrecon_config_direct_validation.log
        rm -f "${{direct_validation_log}}"
        if docker run --rm --platform linux/amd64 --entrypoint /bin/sh {docker_image_name_quoted} -c '{create_openrecon_python_resolver_script()}cd /opt/code/python-ismrmrd-server && "$OPENRECON_PYTHON" - "$@"' sh "$config_modules_json" >"${{direct_validation_log}}" 2>&1 <<'PY'
{validation_python}PY
        then
            cat "${{direct_validation_log}}"
            rm -f "${{direct_validation_log}}"
            echo "✓ OpenRecon config modules are valid"
        else
            validation_status=$?
            echo "⚠️  Direct container validation failed with exit code $validation_status; retrying from a copied root filesystem without starting a nested container."
            validation_root=/tmp/openrecon_config_validation_root
            rm -rf "${{validation_root}}"
            mkdir -p "${{validation_root}}"

            tmp_container="config-validation-$(date +%s)-$$"
            if (
                set -e
                docker create --platform linux/amd64 --name "${{tmp_container}}" {docker_image_name_quoted} >/dev/null
                docker cp "${{tmp_container}}:/." "${{validation_root}}"
                docker rm "${{tmp_container}}" >/dev/null
                mkdir -p "${{validation_root}}/tmp" "${{validation_root}}/dev"
                create_chroot_device() {{
                    device_name="$1"
                    device_major="$2"
                    device_minor="$3"
                    device_path="${{validation_root}}/dev/${{device_name}}"
                    if [ ! -e "${{device_path}}" ]; then
                        mknod -m 666 "${{device_path}}" c "${{device_major}}" "${{device_minor}}"
                    fi
                }}
                create_chroot_device null 1 3
                create_chroot_device zero 1 5
                create_chroot_device random 1 8
                create_chroot_device urandom 1 9
                docker inspect --format '{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}' {docker_image_name_quoted} \\
                    | sed "/^$/d; s/'/'\\\\''/g; s/^/export '/; s/$/'/" \\
                    > "${{validation_root}}/tmp/openrecon_config_validation_env.sh"

                chroot "${{validation_root}}" /bin/sh -c '. /tmp/openrecon_config_validation_env.sh && {create_openrecon_python_resolver_script()}cd /opt/code/python-ismrmrd-server && PYTHONHASHSEED=0 "$OPENRECON_PYTHON" - "$@"' sh "$config_modules_json" <<'PY'
{validation_python}PY
            ); then
                tmp_container=""
                rm -rf "${{validation_root}}"
                rm -f "${{direct_validation_log}}"
                echo "✓ OpenRecon config modules are valid"
            else
                fallback_status=$?
                echo "❌ Copied-rootfs OpenRecon config validation failed with exit code $fallback_status."
                echo "Direct container validation output:"
                cat "${{direct_validation_log}}"
                docker rm -f "${{tmp_container}}" >/dev/null 2>&1 || true
                tmp_container=""
                rm -rf "${{validation_root}}"
                rm -f "${{direct_validation_log}}"
                exit "$fallback_status"
            fi
        fi
        '''
    )


def ensure_dind_image_available(image_name, force_local_only):
    if force_local_only:
        print(f'\n🐳 Local-only mode: checking DinD image in local cache: {image_name}')
        try:
            subprocess.check_output(['docker', 'image', 'inspect', image_name], stderr=subprocess.STDOUT)
            print('✓ DinD image found in local cache')
            return
        except subprocess.CalledProcessError:
            print(f'⚠️  DinD image not found locally. Preloading {image_name}...')
    else:
        print(f'\n🐳 Pulling DinD image {image_name}...')

    pull_cmd = ['docker', 'pull', '--platform', 'linux/amd64', image_name]
    try:
        subprocess.check_output(pull_cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        docker_output = exc.output.decode('utf-8', errors='replace').strip() if exc.output else ''
        message = (
            f"Failed to prepare DinD image '{image_name}'.\n"
            f"Attempted: {' '.join(pull_cmd)}"
        )
        if docker_output:
            message += f'\nDocker output:\n{docker_output}'
        raise Exception(message) from exc

    if force_local_only:
        print('✓ DinD image preloaded')
    else:
        print('✓ DinD image ready')


def write_openrecon_dockerfile(base_docker_image, dockerfile_path, json_data):
    json_string = json.dumps(json_data, indent=2)
    encoded_json = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')
    label_name = 'com.siemens-healthineers.magneticresonance.openrecon.metadata:1.1.0'
    label_str = f'LABEL "{label_name}"="{encoded_json}"'

    with open(dockerfile_path, 'w') as file:
        file.write(f'FROM {base_docker_image}\n')
        file.write(f'{label_str}\n')
        runtime_command = create_openrecon_python_runtime_command('/tmp/python-ismrmrd-server.log')
        file.write(f'CMD {json.dumps(["/bin/bash", "-c", runtime_command])}\n')


def detect_docs_file():
    if os.path.isfile('docs.pdf'):
        return 'docs.pdf'
    return 'README.pdf'


def parse_int_env(var_name, default_value):
    raw_value = os.getenv(var_name)
    if raw_value is None or raw_value.strip() == '':
        return default_value

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f'Environment variable {var_name} must be an integer, got: {raw_value}') from exc

    if value < 0:
        raise ValueError(f'Environment variable {var_name} must be non-negative, got: {raw_value}')

    return value


def get_package_selection():
    selection = os.getenv('BUILD_PACKAGE_SELECTION', 'openrecon').strip().lower()
    valid_selections = {'openrecon', 'fire', 'both'}
    if selection not in valid_selections:
        raise ValueError(
            f'BUILD_PACKAGE_SELECTION must be one of {sorted(valid_selections)}, got: {selection}'
        )
    return selection


def get_fire_bundle_base(vendor, name, version):
    override = os.getenv('fireBundleName')
    if override and override.strip():
        return override.strip()
    return f'FIRE_{vendor}_{name}_V{version}'


def get_fire_ini_filename(package_name):
    if not isinstance(package_name, str) or not package_name.strip():
        raise ValueError('OpenRecon package names must be non-empty strings')
    if package_name != Path(package_name).name or '/' in package_name or '\\' in package_name:
        raise ValueError(f'OpenRecon package name is not safe for a FIRE ini filename: {package_name!r}')
    return f'wip_070_fire_{package_name}.ini'


def get_fire_workflow_base(package_name):
    if not isinstance(package_name, str) or not package_name.strip():
        raise ValueError('OpenRecon package names must be non-empty strings')
    if package_name != Path(package_name).name or '/' in package_name or '\\' in package_name:
        raise ValueError(f'OpenRecon package name is not safe for a FIRE workflow filename: {package_name!r}')
    return f'wip_070_fire_{package_name}'


def get_fire_server_command():
    override = os.getenv('fireStartupCommand')
    if override and override.strip():
        return override.replace('{log_path}', '$LOG_PATH')
    return '"$OPENRECON_PYTHON" /opt/code/python-ismrmrd-server/main.py -v -H=0.0.0.0 -p=9002 -l "$LOG_PATH"'


def is_shell_assignment_token(token):
    name, separator, _ = token.partition('=')
    return bool(separator) and name.replace('_', 'a').isidentifier()


def get_fire_startup_executable(fire_server_command):
    try:
        tokens = shlex.split(fire_server_command)
    except ValueError as exc:
        raise ValueError(f'fireStartupCommand is not a valid shell command: {exc}') from exc

    for token in tokens:
        if token in {'exec', 'env'}:
            continue
        if is_shell_assignment_token(token):
            continue
        return token

    raise ValueError('fireStartupCommand must include an executable command')


def create_fire_startup_script_text(fire_server_command):
    fire_command_quoted = shlex.quote(fire_server_command)
    fire_startup_executable = get_fire_startup_executable(fire_server_command)
    fire_startup_executable_quoted = shlex.quote(fire_startup_executable)
    validation_env_expansion = '${' + FIRE_STARTUP_VALIDATION_ENV + ':-0}'
    if fire_startup_executable in {'$OPENRECON_PYTHON', '${OPENRECON_PYTHON}'}:
        validation_script = textwrap.dedent(
            '''\
            command -v "$OPENRECON_PYTHON" >/dev/null 2>&1
            exit $?
            '''
        )
    else:
        validation_script = textwrap.dedent(
            f'''\
            if [ -x {fire_startup_executable_quoted} ]; then
                exit 0
            fi
            command -v {fire_startup_executable_quoted} >/dev/null 2>&1
            exit $?
            '''
        )
    validation_script = textwrap.indent(validation_script.rstrip(), '    ' * 3)

    return textwrap.dedent(
        f'''\
        #!/bin/sh
        set -eu
        if [ -f {FIRE_ENV_SCRIPT_PATH} ]; then
            . {FIRE_ENV_SCRIPT_PATH}
        fi
        LOG_PATH="${{1:-/tmp/share/log/python_ismrmrd_server.log}}"
        mkdir -p "$(dirname "$LOG_PATH")"
        export LOG_PATH
        export FIRE_LOG_PATH="$LOG_PATH"
        /usr/sbin/ldconfig
        {create_openrecon_python_resolver_script()}
        if [ "{validation_env_expansion}" = "1" ]; then
{validation_script}
        fi
        exec sh -c {fire_command_quoted}
        '''
    )


def determine_output_dir():
    output_dir = os.getcwd()
    if not shutil.which('diskutil'):
        return output_dir

    try:
        volumes_output = subprocess.check_output(['ls', '/Volumes'], stderr=subprocess.DEVNULL).decode('utf-8')
        volumes = [v.strip() for v in volumes_output.split('\n') if v.strip() and v.strip() != 'Macintosh HD']

        usb_drives = []
        for vol in volumes:
            vol_path = os.path.join('/Volumes', vol)
            try:
                disk_info = subprocess.check_output(['diskutil', 'info', vol_path], stderr=subprocess.DEVNULL).decode('utf-8')
                if 'Removable Media' in disk_info or 'External' in disk_info:
                    stat = os.statvfs(vol_path)
                    free_space_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
                    usb_drives.append((vol, free_space_gb))
            except Exception:
                continue

        if not usb_drives:
            return output_dir

        print('\n🔍 Detected USB drive(s):')
        for i, (vol, free_space_gb) in enumerate(usb_drives, 1):
            print(f'   {i}. {vol} (Free: {free_space_gb:.1f} GiB)')

        if len(usb_drives) == 1:
            selected_volume = usb_drives[0][0]
            output_dir = os.path.join('/Volumes', selected_volume)
            test_file = os.path.join(output_dir, '.write_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                print(f'✓ Automatically selected USB drive: {output_dir}')
            except Exception:
                print(f'❌ Cannot write to {output_dir}. Saving locally instead.')
                output_dir = os.getcwd()
            return output_dir

        is_ci = os.getenv('GITHUB_ACTIONS') or os.getenv('CI')
        if is_ci:
            print('\n🤖 CI environment detected. Saving to current directory')
            return output_dir

        print('\n💾 Would you like to save the output directly to a USB drive?')
        while True:
            response = input('Enter drive number to save there, or press Enter to save locally: ').strip()
            if response == '':
                print('📁 Saving to current directory')
                return output_dir

            try:
                drive_idx = int(response) - 1
                if 0 <= drive_idx < len(usb_drives):
                    selected_volume = usb_drives[drive_idx][0]
                    output_dir = os.path.join('/Volumes', selected_volume)
                    test_file = os.path.join(output_dir, '.write_test')
                    try:
                        with open(test_file, 'w') as f:
                            f.write('test')
                        os.remove(test_file)
                        print(f'✓ Will save to: {output_dir}')
                        return output_dir
                    except Exception:
                        print(f'❌ Cannot write to {output_dir}. Saving locally instead.')
                        return os.getcwd()

                print(f'Please enter a number between 1 and {len(usb_drives)}, or press Enter')
            except ValueError:
                print('Please enter a valid number or press Enter')
    except Exception:
        return output_dir


def package_with_7z(zip_exe, zip_output_path, inputs, cwd=None):
    if os.path.exists(zip_output_path):
        os.remove(zip_output_path)

    cmd = [zip_exe, 'a', '-tzip', '-mm=Deflate', zip_output_path]
    cmd.extend(inputs)
    progress_report_interval_seconds = 30
    progress_report_size_step_bytes = 1024 ** 3
    progress_report_percent_step = 5

    def get_input_size_bytes(path):
        if os.path.isdir(path):
            total = 0
            for root, _, filenames in os.walk(path):
                for filename in filenames:
                    total += os.path.getsize(os.path.join(root, filename))
            return total
        return os.path.getsize(path)

    base_dir = cwd if cwd is not None else os.getcwd()
    input_size_bytes = sum(get_input_size_bytes(os.path.join(base_dir, item)) for item in inputs)
    last_reported_size = -1
    last_reported_percent = -1
    last_report_time = time.monotonic()

    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        while process.poll() is None:
            if os.path.exists(zip_output_path):
                current_size = os.path.getsize(zip_output_path)
                if current_size > last_reported_size:
                    now = time.monotonic()
                    approx_percent = None
                    should_report = last_reported_size < 0

                    if input_size_bytes > 0:
                        approx_percent = min(99, int((current_size / input_size_bytes) * 100))
                        if approx_percent >= last_reported_percent + progress_report_percent_step:
                            should_report = True

                    if current_size >= last_reported_size + progress_report_size_step_bytes:
                        should_report = True

                    if now - last_report_time >= progress_report_interval_seconds:
                        should_report = True

                    if should_report:
                        if approx_percent is not None:
                            print(
                                f'   compressing... {current_size / (1024 ** 3):.2f} GiB written '
                                f'(approx {approx_percent}% of input size)'
                            )
                            last_reported_percent = approx_percent
                        else:
                            print(f'   compressing... {current_size / (1024 ** 3):.2f} GiB written')
                        last_reported_size = current_size
                        last_report_time = now
            time.sleep(5)

        output, _ = process.communicate()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd, output=output)
    finally:
        if process.stdout:
            process.stdout.close()


def get_path_size_bytes(path):
    if os.path.isdir(path):
        total = 0
        for root, _, filenames in os.walk(path):
            for filename in filenames:
                total += os.path.getsize(os.path.join(root, filename))
        return total
    return os.path.getsize(path)


def remove_platform_metadata_files(path):
    if not os.path.isdir(path):
        return

    for root, _, filenames in os.walk(path):
        for filename in filenames:
            if filename == '.DS_Store' or filename.startswith('._'):
                os.remove(os.path.join(root, filename))


def create_fire_ini_template(
    fire_img_name,
    startup_script_path,
    fire_search_string,
    fire_hostname='192.168.2.2',
    fire_port=9002,
):
    return textwrap.dedent(
        f'''\
        ; FIRE configuration generated by neurorecon.
        ; Copy this file to the scanner FIRE folder or reference it from your workflow XML.
        [OpenRecon]
        hostname={fire_hostname}
        port={fire_port}

        [chroot]
        start_chroot=true
        chroot_image_path=/opt/medcom/MriCustomer/ice/fire/chroot
        chroot_image_name={fire_img_name}
        chroot_command={startup_script_path} /tmp/share/log/python_ismrmrd_server_`date '+%Y%m%d_%H%M%S'`.log
        chroot_search_string={fire_search_string}
        chroot_stop_after_finish=true
        chroot_allowable_residual_memory_usage=128
        '''
    )


def create_fire_ipr_text():
    return textwrap.dedent(
        '''\
        <XProtocol>
        {
            <ID> 1000000

            <ParamMap."">
            {
            }

            <ProtocolComposer."OpenReconConfigurator">
            {
                <Dll>"wip_070_fire_OpenRecon"
            }

            <ProtocolComposer."FireSshTunnelConfigurator">
            {
                <Dll>"wip_070_fire_IceFire"
            }

            <ProtocolComposer."FireConfigurator">
            {
                <Dll>"wip_070_fire_IceFire"
            }
        }
        '''
    )


def create_fire_workflow_xml_text(config_id, fire_ini_name):
    return textwrap.dedent(
        f'''\
        <?xml version="1.0" encoding="UTF-8" standalone="no" ?>
        <OpenReconConfiguration xmlns="OpenRecon" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="OpenRecon ./OpenRecon.xsd">

          <Marshal>
            <Anchor>Flags</Anchor>
            <IniFile>%CustomerIceProgs%\\fire\\{fire_ini_name}</IniFile>
            <Config>{config_id}</Config>
            <LocalConfig></LocalConfig>
            <JsonConfig></JsonConfig>
            <ParameterMap>%CustomerIceProgs%\\fire\\wip_070_fire_IsmrmrdParameterMap_Siemens.xml</ParameterMap>
            <XslStylesheet>%CustomerIceProgs%\\fire\\wip_070_fire_IsmrmrdParameterMap_Siemens.xsl</XslStylesheet>
            <SendWaveformData>false</SendWaveformData>
            <MinimumMemoryLimit>2048.0</MinimumMemoryLimit>
            <PurgeIrisMemory>false</PurgeIrisMemory>
            <WaitingIntervalForStartOnMarsInSeconds>1.0</WaitingIntervalForStartOnMarsInSeconds>
            <WaitingIntervalForCheckToStopOnMarsInSeconds>3.0</WaitingIntervalForCheckToStopOnMarsInSeconds>
            <ConnectionTimeOut>3.0</ConnectionTimeOut>
            <ConnectionRetryLimit>10</ConnectionRetryLimit>
            <SavedProtocolSectionList></SavedProtocolSectionList>
            <QueryDependencyStatus>false</QueryDependencyStatus>
            <SendDependentData>false</SendDependentData>
            <AdjParameterMap>%CustomerIceProgs%\\fire\\wip_070_fire_IsmrmrdParameterMap_Siemens.xml</AdjParameterMap>
            <AdjXslStylesheet>%CustomerIceProgs%\\fire\\wip_070_fire_IsmrmrdParameterMap_Siemens.xsl</AdjXslStylesheet>
            <AdjConfig>default_measurement_dependencies.xml</AdjConfig>
            <AdjLocalConfig></AdjLocalConfig>
            <InitiateConnection>auto</InitiateConnection>
          </Marshal>

          <RawEmitter>
            <Anchor>none</Anchor>
            <PassOnData>false</PassOnData>
            <CheckLimitsPassOnData>true</CheckLimitsPassOnData>
            <RefAsFlashReadOut>false</RefAsFlashReadOut>
            <CompressionPrecision>0</CompressionPrecision>
            <CompressionTolerance>0.0</CompressionTolerance>
            <ParseTrajectory>false</ParseTrajectory>
            <ParseMdhRadialAngles>false</ParseMdhRadialAngles>
            <StoreRadialAngles>false</StoreRadialAngles>
          </RawEmitter>

          <ImageEmitter>
            <Anchor></Anchor>
            <PassOnData>false</PassOnData>
            <EmitNormOriented>true</EmitNormOriented>
          </ImageEmitter>

          <Injector>
            <Anchor></Anchor>
            <SplitChannels>false</SplitChannels>
            <UseIceFillingMiniHeader>true</UseIceFillingMiniHeader>
            <DistorCorMode></DistorCorMode>
          </Injector>

          <Configurator>
            <DisableSystemNoiseAdjust>false</DisableSystemNoiseAdjust>
            <OnlyEmitData>false</OnlyEmitData>
            <AutoConfigure>image2image</AutoConfigure>
            <FunctorRemoveList></FunctorRemoveList>
            <RemoveIntermediateFunctors>false</RemoveIntermediateFunctors>
            <DisableNormOrientation>false</DisableNormOrientation>
            <Use16Bit>true</Use16Bit>
            <CorrectPipeServiceOrder>true</CorrectPipeServiceOrder>
          </Configurator>

        </OpenReconConfiguration>
        '''
    )


def create_fire_install_text(fire_img_name, fire_ini_name):
    return textwrap.dedent(
        f'''\
        FIRE Installation Notes
        =======================

        This bundle contains an `Ice` folder laid out like `%CustomerIceProgs%`, typically `...\\MriCustomer\\Ice`.
        Copy or merge the `Ice` folder into `...\\MriCustomer` on the scanner.

        Included scanner-copy paths
        ---------------------------
        - `Ice\\wip_070_fire_*.ipr`
        - `Ice\\wip_070_fire_*.xml`
        - `Ice\\fire\\chroot\\{fire_img_name}`
        - `Ice\\fire\\{fire_ini_name}`
        - `Ice\\fire\\config\\wip_070_fire_*.json`
        - `Ice\\fire\\share\\code`, `Ice\\fire\\share\\dependency`, `Ice\\fire\\share\\log`
        - `INSTALL_FIRE.txt`, `README.md`, and the included PDF stay next to `Ice` as documentation.

        Additional `Ice\\fire\\*.ini` files will land under `%CustomerIceProgs%\\fire\\` when you copy `Ice`;
        use them only when your workflow XML references those specific files.

        Notes
        -----
        - The generated chroot startup script is inside the image at `/usr/local/bin/start-fire-openrecon.sh`
        - FIRE JSON config files are generated from `OpenReconLabel.json` defaults unless a recipe-provided JSON file overrides them
        - FIRE mounts `%CustomerIceProgs%\\fire\\share\\` inside the chroot as `/tmp/share/`
        - Unmount or stop the FIRE chroot service before replacing an installed `.img` on the scanner host
        '''
    )


def get_fire_config_filename(config_id):
    if not isinstance(config_id, str) or not config_id.strip():
        raise ValueError('OpenRecon config ids must be non-empty strings')
    if config_id != Path(config_id).name or '/' in config_id or '\\' in config_id:
        raise ValueError(f'OpenRecon config id is not safe for a FIRE config filename: {config_id!r}')
    return f'wip_070_fire_{config_id}.json'


def create_fire_config_json_payload(json_data, config_id):
    parameters = get_openrecon_parameter_defaults(json_data)
    parameters['config'] = config_id
    return {
        'version': OPENRECON_JSON_CONFIG_VERSION,
        'parameters': parameters,
    }


def create_fire_config_json_text(json_data, config_id):
    return json.dumps(create_fire_config_json_payload(json_data, config_id), indent=4) + '\n'


def iter_recipe_fire_config_json_overrides(recipe_dir):
    override_paths = []

    for path in sorted(recipe_dir.glob('wip_070_fire_*.json')):
        if path.is_file():
            override_paths.append(path)

    fire_config_dir = recipe_dir / 'fire' / 'config'
    if fire_config_dir.is_dir():
        for path in sorted(fire_config_dir.glob('*.json')):
            if path.is_file():
                override_paths.append(path)

    return override_paths


def write_fire_config_json_files(stage_dir, recipe_dir, json_data):
    config_dir = stage_dir / 'fire' / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)

    written_files = []

    for config_id in get_openrecon_config_module_names(json_data):
        config_path = config_dir / get_fire_config_filename(config_id)
        config_path.write_text(create_fire_config_json_text(json_data, config_id))
        written_files.append(str(Path('fire') / 'config' / config_path.name))

    for override_path in iter_recipe_fire_config_json_overrides(recipe_dir):
        target_path = config_dir / override_path.name
        shutil.copy2(override_path, target_path)
        rel_path = str(Path('fire') / 'config' / target_path.name)
        if rel_path not in written_files:
            written_files.append(rel_path)

    return written_files


def copy_optional_fire_ini_files(stage_dir, recipe_dir):
    fire_dir = stage_dir / 'fire'
    fire_dir.mkdir(parents=True, exist_ok=True)

    copied_files = []

    for path in sorted(recipe_dir.glob('fire_*.ini')):
        if path.is_file():
            shutil.copy2(path, fire_dir / path.name)
            copied_files.append(str(Path('fire') / path.name))

    return copied_files


def build_fire_bundle_stage(stage_dir, fire_img_path, fire_ini_name, fire_ini_text, install_text, docs_source_path, json_data, package_name, recipe_dir=None):
    if recipe_dir is None:
        recipe_dir = Path.cwd()

    ice_dir = stage_dir / 'Ice'
    ice_dir.mkdir(parents=True, exist_ok=True)

    fire_dir = ice_dir / 'fire'
    fire_dir.mkdir(parents=True, exist_ok=True)

    chroot_dir = fire_dir / 'chroot'
    chroot_dir.mkdir(parents=True, exist_ok=True)

    share_dir = fire_dir / 'share'
    (share_dir / 'code').mkdir(parents=True, exist_ok=True)
    (share_dir / 'dependency').mkdir(parents=True, exist_ok=True)
    (share_dir / 'log').mkdir(parents=True, exist_ok=True)

    for rel_path, message in {
        Path('fire/share/code/PLACEHOLDER.txt'): 'Optional synchronized FIRE source files can be placed here.\n',
        Path('fire/share/dependency/PLACEHOLDER.txt'): 'Dependent measurement outputs can be placed here.\n',
        Path('fire/share/log/PLACEHOLDER.txt'): 'FIRE runtime logs can be written here.\n',
    }.items():
        (ice_dir / rel_path).write_text(message)

    (fire_dir / fire_ini_name).write_text(fire_ini_text)
    (stage_dir / 'INSTALL_FIRE.txt').write_text(install_text)
    shutil.copy2(fire_img_path, chroot_dir / fire_img_path.name)
    shutil.copy2(docs_source_path, stage_dir / Path(docs_source_path).name)
    readme_source_path = recipe_dir / 'README.md'
    if readme_source_path.is_file():
        shutil.copy2(readme_source_path, stage_dir / 'README.md')
    copy_optional_fire_ini_files(ice_dir, recipe_dir)
    workflow_base = get_fire_workflow_base(package_name)
    default_config_id = get_default_openrecon_config_id(json_data)
    (ice_dir / f'{workflow_base}.ipr').write_text(create_fire_ipr_text())
    (ice_dir / f'{workflow_base}.xml').write_text(create_fire_workflow_xml_text(default_config_id, fire_ini_name))
    write_fire_config_json_files(ice_dir, recipe_dir, json_data)



def build_artifacts_in_dind(
    docker_image_name,
    dockerfile_path,
    openrecon_tar_name,
    fire_img_name,
    fire_rootfs_tar_name,
    create_openrecon_package,
    create_fire_package,
    use_local_image,
    base_docker_image,
    force_local_only,
    keep_cache,
    fire_free_space_mb,
    fire_server_command,
    startup_script_path,
    validate_default_runtime,
    config_module_names,
):
    base_image_tar = None
    if use_local_image:
        print('Using local base image:', base_docker_image)
        base_image_tar = '.base_image.tar'
        is_ci = os.getenv('GITHUB_ACTIONS') or os.getenv('CI')
        if os.path.exists(base_image_tar):
            if is_ci:
                print(f'\n🤖 CI environment detected. Reusing existing {base_image_tar}')
            elif keep_cache:
                print(f'\n💾 Reusing existing {base_image_tar} because KEEP_CACHE=true')
            else:
                print(f'\n🗑️  Removing existing {base_image_tar} because KEEP_CACHE=false')
                os.remove(base_image_tar)

        if not os.path.exists(base_image_tar):
            print(f'💾 Saving base image to {base_image_tar}... (this may take 2-3 minutes)')
            subprocess.check_output(['docker', 'save', '-o', base_image_tar, base_docker_image], stderr=subprocess.STDOUT)
            print('✓ Base image saved successfully')
    else:
        print('Using remote base image:', base_docker_image)

    docker_client_image = 'docker:24.0-dind'
    ensure_dind_image_available(docker_client_image, force_local_only)

    load_image_cmd = ''
    if use_local_image and base_image_tar:
        load_image_cmd = textwrap.dedent(
            f'''\
            echo "📦 Loading base image from tar file... (this may take 2-3 minutes)"
            docker load -i /workspace/{base_image_tar}
            echo "✓ Base image loaded into DinD daemon"
            '''
        )

    startup_script_rel = startup_script_path.lstrip('/')
    startup_script_dir_rel = os.path.dirname(startup_script_rel)
    startup_script_path_quoted = shlex.quote(startup_script_path)
    startup_script_text = create_fire_startup_script_text(fire_server_command)
    startup_script_printf_lines = ' \\\n                '.join(
        shlex.quote(line) for line in startup_script_text.splitlines()
    )
    docker_image_name_quoted = shlex.quote(docker_image_name)
    validate_default_runtime_flag = '1' if validate_default_runtime else '0'
    config_module_validation_script = create_config_module_validation_script(docker_image_name, config_module_names)

    artifact_label = 'Docker image'
    if create_openrecon_package and create_fire_package:
        artifact_label = 'Docker image, OpenRecon package, and FIRE chroot image'
    elif create_openrecon_package:
        artifact_label = 'Docker image and OpenRecon package'
    elif create_fire_package:
        artifact_label = 'Docker image and FIRE chroot image'

    print('\n' + '=' * 70)
    print(f'STEP 2/6: Building {artifact_label}')
    print('=' * 70)

    volume_name = f'docker-build-{uuid.uuid4().hex[:8]}'
    print(f'📁 Creating temporary Docker volume: {volume_name}')
    subprocess.check_output(['docker', 'volume', 'create', volume_name], stderr=subprocess.STDOUT)

    docker_build_script = textwrap.dedent(
        f'''\
        set -eu

        cleanup() {{
            if command -v mountpoint >/dev/null 2>&1 && [ "${{mounted:-0}}" -eq 1 ] && mountpoint -q "${{mount_dir}}"; then
                umount "${{mount_dir}}" || true
            fi
            if [ -n "${{tmp_container:-}}" ]; then
                docker rm -f "${{tmp_container}}" >/dev/null 2>&1 || true
            fi
        }}
        trap cleanup EXIT

        echo "🚀 Starting Docker daemon..."
        dockerd --host=unix:///var/run/docker.sock --host=tcp://0.0.0.0:2375 &

        timeout=60
        while ! DOCKER_HOST=unix:///var/run/docker.sock docker version >/dev/null 2>&1; do
            sleep 2
            timeout=$((timeout - 2))
            if [ $timeout -le 0 ]; then
                echo "❌ Docker daemon failed to start"
                exit 1
            fi
        done

        echo "✓ Docker daemon is ready"
        export DOCKER_HOST=unix:///var/run/docker.sock
        {load_image_cmd}

        echo "🔨 Building Docker image..."
        DOCKER_BUILDKIT=1 BUILDKIT_PROGRESS=plain docker build --progress=plain --platform linux/amd64 -t {docker_image_name} -f {dockerfile_path} ./
        echo "✓ Docker image built successfully"
        {config_module_validation_script}
        if [ "{1 if create_openrecon_package else 0}" = "1" ]; then
            echo "💾 Saving OpenRecon image tar..."
            docker save -o /workspace/{openrecon_tar_name} {docker_image_name}
            chmod 644 /workspace/{openrecon_tar_name}
            echo "✓ Image saved to {openrecon_tar_name}"
        fi

        if [ "{1 if create_fire_package else 0}" = "1" ]; then
            echo "📤 Exporting container filesystem for FIRE..."
            tmp_container="fire-export-$(date +%s)-$$"
            rootfs_tar_path=/tmp/fire_rootfs_export.tar
            docker create --name "${{tmp_container}}" {docker_image_name} >/dev/null
            docker export -o "${{rootfs_tar_path}}" "${{tmp_container}}"
            docker rm "${{tmp_container}}" >/dev/null
            tmp_container=""
            echo "✓ Container filesystem exported to temporary storage"

            echo "🧰 Installing FIRE image creation tools..."
            apk add --no-cache e2fsprogs util-linux >/dev/null

            extract_dir=/tmp/fire_rootfs_extract
            rm -rf "${{extract_dir}}"
            mkdir -p "${{extract_dir}}"

            echo "📦 Expanding exported filesystem for sizing..."
            tar -xf "${{rootfs_tar_path}}" -C "${{extract_dir}}"
            rm -f "${{rootfs_tar_path}}"

            rootfs_bytes=$(du -sb "${{extract_dir}}" | awk '{{print $1}}')
            rootfs_buffer_bytes=$(( rootfs_bytes / 5 ))
            img_size_mb=$(( (rootfs_bytes + rootfs_buffer_bytes + 1048575) / 1048576 + {fire_free_space_mb} + 128 ))
            if [ "$img_size_mb" -le 0 ]; then
                echo "❌ Computed FIRE image size is invalid"
                exit 1
            fi

            workspace_free_kb=$(df -Pk /workspace | awk 'NR==2 {{print $4}}')
            workspace_free_bytes=$(( workspace_free_kb * 1024 ))
            required_img_bytes=$(( img_size_mb * 1048576 ))
            if [ "$workspace_free_bytes" -lt "$required_img_bytes" ]; then
                echo "❌ Not enough free space in /workspace to allocate the FIRE chroot image"
                echo "   Required for image file: $required_img_bytes bytes ($(awk 'BEGIN {{printf \"%.2f\", '"$required_img_bytes"' / 1024 / 1024 / 1024}}') GiB)"
                echo "   Available in /workspace: $workspace_free_bytes bytes ($(awk 'BEGIN {{printf \"%.2f\", '"$workspace_free_bytes"' / 1024 / 1024 / 1024}}') GiB)"
                echo "   Try freeing local disk space, choosing a smaller image, or building on a larger filesystem."
                exit 1
            fi

            echo "🧱 Creating FIRE chroot image ({fire_img_name}) with $img_size_mb MiB..."
            echo "   Expanded rootfs size: $rootfs_bytes bytes"
            echo "   Added sizing buffer: $rootfs_buffer_bytes bytes + {fire_free_space_mb} MiB free space"
            dd if=/dev/zero of=/workspace/{fire_img_name} bs=1M count="${{img_size_mb}}" status=none
            mke2fs -F -t ext3 /workspace/{fire_img_name} >/dev/null 2>&1

            mount_dir=/mnt/fire_chroot_build
            mounted=0
            mkdir -p "${{mount_dir}}"
            mount -o loop /workspace/{fire_img_name} "${{mount_dir}}"
            mounted=1

            echo "📦 Copying expanded root filesystem into FIRE chroot image..."
            cp -a "${{extract_dir}}"/. "${{mount_dir}}"/
            rm -rf "${{extract_dir}}"

            mkdir -p "${{mount_dir}}/{startup_script_dir_rel}"
            mkdir -p "${{mount_dir}}/tmp/share/code" "${{mount_dir}}/tmp/share/dependency" "${{mount_dir}}/tmp/share/log"
            mkdir -p "${{mount_dir}}/etc"

            fire_env_lines=/tmp/fire_image_env.list
            docker inspect --format '{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}' {docker_image_name_quoted} > "${{fire_env_lines}}"
            sed "/^$/d; s/'/'\\\\''/g; s/^/export '/; s/$/'/" "${{fire_env_lines}}" > "${{mount_dir}}{FIRE_ENV_SCRIPT_PATH}"
            rm -f "${{fire_env_lines}}"
            chmod 644 "${{mount_dir}}{FIRE_ENV_SCRIPT_PATH}"

            printf '%s\n' \
                {startup_script_printf_lines} \
                > "${{mount_dir}}/{startup_script_rel}"
            chmod 755 "${{mount_dir}}/{startup_script_rel}"

            echo "🔍 Validating FIRE chroot contents..."
            if ! chroot "${{mount_dir}}" /bin/sh -c 'test -x /usr/sbin/ldconfig'; then
                echo "❌ FIRE image validation failed: /usr/sbin/ldconfig not found inside the chroot"
                exit 1
            fi
            if [ "{validate_default_runtime_flag}" = "1" ] && ! chroot "${{mount_dir}}" /bin/sh -c '. {FIRE_ENV_SCRIPT_PATH} && test -f /opt/code/python-ismrmrd-server/main.py'; then
                echo "❌ FIRE image validation failed: /opt/code/python-ismrmrd-server/main.py not found inside the chroot"
                exit 1
            fi
            if ! chroot "${{mount_dir}}" /bin/sh -c 'test -x {startup_script_path}'; then
                echo "❌ FIRE image validation failed: generated startup script is missing or not executable"
                exit 1
            fi
            if ! chroot "${{mount_dir}}" /bin/sh -c 'OPENRECON_FIRE_VALIDATE_STARTUP=1 "$1"' sh {startup_script_path_quoted}; then
                echo "❌ FIRE image validation failed: generated startup script cannot resolve its configured executable after sourcing Docker image environment"
                exit 1
            fi

            sync
            umount "${{mount_dir}}"
            mounted=0
            chmod 644 /workspace/{fire_img_name}
            echo "✓ FIRE chroot image created at {fire_img_name}"
        fi
        '''
    )

    dind_run_args = [
        'docker', 'run', '--rm', '--privileged',
        '--platform', 'linux/amd64',
        '-v', f'{volume_name}:/var/lib/docker',
        '-v', f'{os.getcwd()}:/workspace',
        '-w', '/workspace',
        docker_client_image,
        'sh', '-c', docker_build_script,
    ]

    try:
        run_dind_build_process(dind_run_args)
    finally:
        print(f'\n🗑️  Cleaning up temporary Docker volume: {volume_name}')
        subprocess.run(['docker', 'volume', 'rm', '-f', volume_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return base_image_tar


if __name__ == '__main__':
    jsonFilePath = 'OpenReconLabel.json'
    schemaFilePath = '../OpenReconSchema_1.1.0.json'
    dockerfilePath = 'OpenRecon.dockerfile'

    dockerImageToUse = os.getenv('DOCKER_IMAGE_TO_USE')
    baseDockerImage = dockerImageToUse if dockerImageToUse else os.getenv('baseDockerImage')
    useLocalImage = os.getenv('USE_LOCAL_IMAGE', 'false').lower() == 'true'
    forceLocalOnly = os.getenv('FORCE_LOCAL_ONLY', 'false').lower() == 'true'
    keepCache = os.getenv('KEEP_CACHE', 'false').lower() == 'true'
    packageSelection = get_package_selection()
    createOpenReconPackage = packageSelection in {'openrecon', 'both'}
    createFirePackage = packageSelection in {'fire', 'both'}

    if not validateJson(jsonFilePath, schemaFilePath):
        raise Exception('Not writing Dockerfile because JSON is not valid')

    with open(jsonFilePath, 'r') as jsonFile:
        jsonData = json.load(jsonFile)

    validate_openrecon_label_metadata(jsonData)
    print('OpenReconLabel.json metadata checks passed.')

    write_openrecon_dockerfile(baseDockerImage, dockerfilePath, jsonData)
    print('Wrote Dockerfile:', os.path.abspath(dockerfilePath))

    docsFile = detect_docs_file()
    if not os.path.isfile(docsFile):
        raise Exception('Could not find documentation file: ' + docsFile)

    zipExe = None
    if createOpenReconPackage:
        zipExe = shutil.which('7z')
    if createOpenReconPackage and zipExe is None:
        raise Exception('Could not find 7-Zip executable in PATH. Please download and install 7-Zip')

    version = jsonData['general']['version']
    vendor = jsonData['general']['vendor']
    name = jsonData['general']['name']['en']

    openreconBundleBase = f'OpenRecon_{vendor}_{name}_V{version}'
    openreconTarName = openreconBundleBase + '.tar'
    openreconPdfName = openreconBundleBase + '.pdf'
    fireBundleBase = get_fire_bundle_base(vendor, name, version)
    fireImgName = fireBundleBase + '.img'
    fireRootfsTarName = fireBundleBase + '.rootfs.tar'
    fireSearchString = os.getenv('fireSearchString', 'python3').strip() or 'python3'
    fireFreeSpaceMb = parse_int_env('fireFreeSpaceMb', 50)
    fireHostname = os.getenv('fireHostname', '192.168.2.2').strip() or '192.168.2.2'
    firePort = parse_int_env('firePort', int(jsonData.get('reconstruction', {}).get('port', 9002)))
    fireServerCommand = get_fire_server_command()
    startupScriptPath = '/usr/local/bin/start-fire-openrecon.sh'
    validateDefaultFireRuntime = not (os.getenv('fireStartupCommand') or '').strip()

    dockerImagename = (f'OpenRecon_{vendor}_{name}:V{version}').lower()

    build_start = time.time()
    base_image_tar = None
    openrecon_zip_output_path = None
    fire_bundle_output_path = None

    try:
        print('=' * 70)
        print('PRE-BUILD: Checking CUDA version in base image')
        print('=' * 70)
        print(f'Base image: {baseDockerImage}')
        from checkCudaVersion import checkCudaVersionInContainer
        checkCudaVersionInContainer(baseDockerImage, maxCudaVersion='11.8')

        print('=' * 70)
        print('PRE-BUILD: Checking user in base image')
        print('=' * 70)
        print(f'Base image: {baseDockerImage}')
        from checkRootUser import checkRootUserInContainer
        checkRootUserInContainer(baseDockerImage)

        print('=' * 70)
        print('PRE-BUILD: Checking README.md for PDF rendering issues')
        print('=' * 70)
        from checkReadmeIssues import check_readme_file
        readme_path = 'README.md'
        if os.path.isfile(readme_path):
            print(f'Checking {readme_path}...')
            if not check_readme_file(readme_path):
                print('\n❌ README.md has issues that need to be fixed')
                print('   These issues can cause blank PDFs or rendering problems.')
                raise Exception('README validation failed')
            print('✅ README.md passed all checks.')
        else:
            print('⚠️  No README.md found, skipping check')

        print('=' * 70)
        print('STEP 1/6: Preparing Docker image build')
        print('=' * 70)
        print('Attempting to create Docker image with tag:', dockerImagename, '...')
        print(f'Package selection inside build.py: {packageSelection}')

        base_image_tar = build_artifacts_in_dind(
            docker_image_name=dockerImagename,
            dockerfile_path=dockerfilePath,
            openrecon_tar_name=openreconTarName,
            fire_img_name=fireImgName,
            fire_rootfs_tar_name=fireRootfsTarName,
            create_openrecon_package=createOpenReconPackage,
            create_fire_package=createFirePackage,
            use_local_image=useLocalImage,
            base_docker_image=baseDockerImage,
            force_local_only=forceLocalOnly,
            keep_cache=keepCache,
            fire_free_space_mb=fireFreeSpaceMb,
            fire_server_command=fireServerCommand,
            startup_script_path=startupScriptPath,
            validate_default_runtime=validateDefaultFireRuntime,
            config_module_names=get_openrecon_config_module_names(jsonData),
        )

        print('\n' + '=' * 70)
        print('STEP 3/6: Preparing documentation')
        print('=' * 70)
        print(f'📄 Copying documentation to {openreconPdfName}...')
        shutil.copy(docsFile, openreconPdfName)
        print('✓ Documentation copied')

        print('\n' + '=' * 70)
        print('STEP 4/6: Selecting output location')
        print('=' * 70)
        output_dir = determine_output_dir()

        print('\n' + '=' * 70)
        print('STEP 5/6: Creating distributable packages')
        print('=' * 70)

        if createOpenReconPackage:
            openrecon_output_dir = os.path.join(output_dir, 'openrecon')
            os.makedirs(openrecon_output_dir, exist_ok=True)
            openrecon_zip_output_path = os.path.join(openrecon_output_dir, openreconBundleBase + '.zip')
            print(f'📦 Packaging OpenRecon bundle into {os.path.basename(openrecon_zip_output_path)}...')
            package_with_7z(zipExe, openrecon_zip_output_path, [openreconTarName, openreconPdfName])
            print('✓ OpenRecon package created successfully')

        if createFirePackage:
            fire_output_dir = os.path.join(output_dir, 'fire')
            os.makedirs(fire_output_dir, exist_ok=True)
            fire_bundle_output_path = os.path.join(fire_output_dir, fireBundleBase)
            fireIniName = get_fire_ini_filename(name)
            fire_ini_text = create_fire_ini_template(
                fireImgName,
                startupScriptPath,
                fireSearchString,
                fire_hostname=fireHostname,
                fire_port=firePort,
            )
            install_text = create_fire_install_text(fireImgName, fireIniName)
            with tempfile.TemporaryDirectory(dir=os.getcwd(), prefix='fire-bundle-') as stage_dir_str:
                stage_dir = Path(stage_dir_str)
                build_fire_bundle_stage(
                    stage_dir=stage_dir,
                    fire_img_path=Path(fireImgName),
                    fire_ini_name=fireIniName,
                    fire_ini_text=fire_ini_text,
                    install_text=install_text,
                    docs_source_path=openreconPdfName,
                    json_data=jsonData,
                    package_name=name,
                    recipe_dir=Path.cwd(),
                )
                if os.path.exists(fire_bundle_output_path):
                    if os.path.isdir(fire_bundle_output_path):
                        shutil.rmtree(fire_bundle_output_path)
                    else:
                        os.remove(fire_bundle_output_path)
                print(f'📁 Writing FIRE bundle folder to {fire_bundle_output_path}...')
                shutil.copytree(stage_dir, fire_bundle_output_path)
                remove_platform_metadata_files(fire_bundle_output_path)
            print('✓ FIRE bundle folder created successfully')

        print('\n' + '=' * 70)
        print('STEP 6/6: Cleanup')
        print('=' * 70)
        print('🗑️  Cleaning up temporary files...')
        for temp_path in [openreconTarName, openreconPdfName, fireImgName, fireRootfsTarName]:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    print(f'   Removed {temp_path}')
            except Exception as exc:
                print(f'   Warning: Could not remove {temp_path}: {exc}')

        if useLocalImage and base_image_tar and os.path.exists(base_image_tar):
            if keepCache:
                print(f'💾 Keeping {base_image_tar} for next build (KEEP_CACHE=true)')
            else:
                os.remove(base_image_tar)
                print(f'🗑️  Removed temporary tar file: {base_image_tar}')

        total_time = time.time() - build_start
        print('\n' + '=' * 70)
        print(f'✅ BUILD COMPLETED SUCCESSFULLY in {total_time:.1f} seconds ({total_time / 60:.1f} minutes)')
        print('=' * 70)
        for label, path in [('OpenRecon', openrecon_zip_output_path), ('FIRE', fire_bundle_output_path)]:
            if not path:
                continue
            print(f'📦 {label} Output: {path}')
            if os.path.exists(path):
                size_bytes = get_path_size_bytes(path)
                size_gb = size_bytes / (1024 ** 3)
                print(f'📊 {label} Size: {size_gb:.2f} GiB')
        print('=' * 70)

    except subprocess.CalledProcessError as e:
        print('Command failed with return code:', e.returncode)
        if hasattr(e.output, 'decode'):
            print('Error output:\n' + e.output.decode('utf-8'))
        else:
            print('Error output:\n' + str(e.output))
        raise
    except Exception as e:
        print(f'Build failed: {e}')
        raise
