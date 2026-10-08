import argparse
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / '.github/workflows/build-config.json'


class BuildProfile(str, Enum):
    STANDARD = 'standard'
    EXPERIMENTAL_OPENRECON_RAW = 'experimental-openrecon-raw'


@dataclass(frozen=True)
class RecipePolicy:
    auto_build: bool
    profile: BuildProfile


def validate_config(config):
    if not isinstance(config, dict) or 'default' not in config:
        raise ValueError('Build config requires a default object')
    for name, entry in config.items():
        if not isinstance(entry, dict):
            raise ValueError(f'{name}: policy must be an object')
        for field in ('autoBuild', 'freeUpSpace'):
            if field in entry and type(entry[field]) is not bool:
                raise ValueError(f'{name}: {field} must be boolean')
        profile = BuildProfile(entry.get('buildProfile', 'standard'))
        if name == 'default' and profile != BuildProfile.STANDARD:
            raise ValueError('default cannot grant an experimental profile')
    return config


def recipe_policy(config, name):
    validate_config(config)
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', name) or name == 'default':
        raise ValueError('Invalid recipe name')
    entry = config.get(name, {})
    return RecipePolicy(entry.get('autoBuild', config['default'].get('autoBuild', False)),
                        BuildProfile(entry.get('buildProfile', 'standard')))


def build_routes(config, names):
    routes = {profile.value: [] for profile in BuildProfile}
    for name in sorted(set(names)):
        policy = recipe_policy(config, name)
        if policy.auto_build:
            routes[policy.profile.value].append(name)
    return routes


def experimental_label(path):
    path = Path(path).absolute()
    try:
        relative = path.relative_to(ROOT / 'recipes')
    except ValueError:
        return False
    if len(relative.parts) != 2 or relative.name != 'OpenReconLabel.json':
        return False
    if not path.is_file() or path.resolve() != path or (ROOT / 'recipes' / relative.parts[0]).is_symlink():
        return False
    return recipe_policy(json.loads(CONFIG.read_text()), relative.parts[0]).profile == BuildProfile.EXPERIMENTAL_OPENRECON_RAW


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['route', 'select'])
    parser.add_argument('selection', help='JSON array of changed paths or selected recipe names')
    args = parser.parse_args()
    names = json.loads(args.selection)
    if not isinstance(names, list) or not all(isinstance(item, str) for item in names):
        raise ValueError('Selection must be a JSON string array')
    config = validate_config(json.loads(CONFIG.read_text()))
    if args.command == 'select':
        if not names or len(set(names)) != len(names):
            raise ValueError('Selection must be nonempty and unique')
        for name in names:
            if recipe_policy(config, name).profile != BuildProfile.EXPERIMENTAL_OPENRECON_RAW:
                raise ValueError(f'{name}: not registered for experimental OpenRecon')
            if not experimental_label(ROOT / 'recipes' / name / 'OpenReconLabel.json') or not (ROOT / 'recipes' / name / 'params.sh').is_file():
                raise ValueError(f'{name}: missing canonical recipe')
        print(json.dumps(names))
    else:
        selected = []
        for path in names:
            parts = Path(path).parts
            if len(parts) >= 2 and parts[0] == 'recipes' and (ROOT / 'recipes' / parts[1]).is_dir():
                selected.append(parts[1])
        for profile, recipes in build_routes(config, selected).items():
            key = 'app_list' if profile == 'standard' else 'experimental_app_list'
            print(f'{key}={json.dumps(recipes, separators=(",", ":"))}')


if __name__ == '__main__':
    main()
