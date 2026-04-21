# neurorecon
repository for building openrecon containers

for running locally:

initial setup:
```
python3 -m venv .venv
```

run locally:
```
source .venv/bin/activate
<!-- cd recipes/THE_RECIPE_YOU_WANT_TO_BUILD e.g.:-->
cd recipes/musclemap
cd recipes/spinalcordtoolbox
cd recipes/openreconexample
# default: prefer local Docker cache first, fallback to remote image
/bin/bash ../build.sh
# force local Docker image cache (no registry pull)
/bin/bash ../build.sh --local-cache
```

When using `--local-cache` for an offline build, the script now prompts for which
artifact(s) to create: `OpenRecon`, `FIRE`, or both.

Each recipe build now emits two distributable artifacts by default:

- `OpenRecon_<vendor>_<name>_V<version>.zip`
- `FIRE_<vendor>_<name>_V<version>.zip`

Optional FIRE overrides can be exported from a recipe `params.sh` when needed:

- `fireFreeSpaceMb`
- `fireStartupCommand`
- `fireSearchString`
- `fireBundleName`
