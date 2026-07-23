# neurorecon

Repository for building OpenRecon containers.

## Local setup on macOS

Install and start Docker Desktop. If Python 3 or 7-Zip is not already
available, install them with Homebrew:

```bash
brew install python p7zip
```

From the repository root, create and activate the local Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install jsonschema packaging
```

Confirm that Python and pip both resolve inside this repository's `.venv`:

```bash
command -v python3
python -m pip --version
```

Both paths should contain `/neurorecon/.venv/`. Activation applies only to the
current terminal, so activate the environment again after opening a new one.

Choose one recipe and run the build from its directory. For example:

```bash
cd recipes/qsmxt

# Prefer the local Docker cache, then fall back to the remote image.
/bin/bash ../build.sh

# Or require an already-cached local Docker image.
/bin/bash ../build.sh --local-cache
```

`build.sh` refuses to install Python packages unless a virtual environment is
active. Missing `jsonschema` and `packaging` dependencies are installed into
that environment using the same Python interpreter that runs the build.

When using `--local-cache` for an offline build, the script now prompts for which
artifact(s) to create: `OpenRecon`, `FIRE`, or both.

Each recipe build now emits two distributable artifacts by default:

- `OpenRecon_<vendor>_<name>_V<version>.zip`
- `FIRE_<vendor>_<name>_V<version>/`

Optional FIRE overrides can be exported from a recipe `params.sh` when needed:

- `fireFreeSpaceMb`
- `fireStartupCommand`
- `fireSearchString`
- `fireHostname`
- `firePort`
- `fireBundleName`
