#!/usr/bin/env python3
"""
CI validation script that uses the validateJson function from build.py.
Resolves scanner version placeholders from literal params.sh assignments.
"""

import sys
import os
import json
import tempfile
import re
from pathlib import Path

# Import validators from build.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'recipes'))
from build_policy import experimental_label
from build import validateJson, validate_openrecon_label_metadata, validate_scanner_version


def scanner_version_from_params(params_path):
    """Read only literal version assignments; never execute recipe shell code."""
    values = {}
    assignment = re.compile(r'^\s*(?:export\s+)?(version|openrecon_version)=(.*)$')
    for line in params_path.read_text().splitlines():
        match = assignment.match(line)
        if not match:
            continue
        name, raw = match.groups()
        literal = re.fullmatch(
            r"(?:'([A-Za-z0-9._+-]+)'|\"([A-Za-z0-9._+-]+)\"|([A-Za-z0-9._+-]+))(?:\s+#.*)?\s*",
            raw,
        )
        if literal is None:
            raise ValueError(f'{params_path}: {name} must be a literal value, without shell expansion.')
        values[name] = next(value for value in literal.groups() if value is not None)
    version = values.get('openrecon_version', values.get('version'))
    if version is not None:
        validate_scanner_version(version)
    return version


def validate_recipe(recipe_json_path, schema_path):
    """
    Validate a recipe JSON file, handling the VERSION placeholder.
    
    Args:
        recipe_json_path: Path to OpenReconLabel.json
        schema_path: Path to schema file
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Read the original JSON
    with open(recipe_json_path, 'r') as f:
        json_data = json.load(f)
    
    try:
        version = scanner_version_from_params(Path(recipe_json_path).with_name('params.sh'))
        label_version = json_data.get('general', {}).get('version')
        if version is None:
            version = label_version
            validate_scanner_version(version)
        if label_version not in ('VERSION_WILL_BE_REPLACED_BY_SCRIPT', version):
            raise ValueError(
                f'general.version {label_version!r} does not match params.sh scanner version {version!r}.'
            )
        json_data = json.loads(json.dumps(json_data).replace('VERSION_WILL_BE_REPLACED_BY_SCRIPT', version))
    except (ValueError, OSError) as error:
        print(error)
        return False

    # Write to temporary file for validation
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        json.dump(json_data, tmp, indent=2)
        tmp_path = tmp.name
    
    try:
        # Use the existing validateJson function from build.py
        if not validateJson(tmp_path, schema_path, experimental_raw_return=experimental_label(recipe_json_path)):
            return False
        try:
            validate_openrecon_label_metadata(json_data)
        except ValueError as error:
            print(error)
            return False
        return True
    finally:
        # Clean up temp file
        os.unlink(tmp_path)


def main():
    """Main function to validate recipe files."""
    script_dir = Path(__file__).parent.parent.parent
    recipes_dir = script_dir / 'recipes'
    schema_path = recipes_dir / 'OpenReconSchema_1.1.0.json'
    
    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}")
        sys.exit(1)
    
    # Get list of files to validate from command line args
    files_to_validate = []
    
    if len(sys.argv) > 1:
        # Validate specific files
        for arg in sys.argv[1:]:
            file_path = Path(arg)
            if file_path.exists():
                files_to_validate.append(file_path)
            else:
                print(f"Warning: File not found: {arg}")
    else:
        # Find all OpenReconLabel.json files
        for recipe_dir in recipes_dir.iterdir():
            if recipe_dir.is_dir() and recipe_dir.name not in ['.git', '__pycache__']:
                json_file = recipe_dir / 'OpenReconLabel.json'
                if json_file.exists():
                    files_to_validate.append(json_file)
    
    if not files_to_validate:
        print("No OpenReconLabel.json files found to validate.")
        sys.exit(0)
    
    # Validate all files
    all_valid = True
    print(f"Validating {len(files_to_validate)} OpenReconLabel.json file(s)...")
    print("-" * 80)
    
    for json_file in files_to_validate:
        relative_path = json_file.relative_to(script_dir) if json_file.is_relative_to(script_dir) else json_file
        print(f"\nValidating: {relative_path}")
        
        is_valid = validate_recipe(json_file, schema_path)
        
        if not is_valid:
            all_valid = False
    
    print("\n" + "=" * 80)
    if all_valid:
        print("✓ All OpenReconLabel.json files are valid!")
        sys.exit(0)
    else:
        print("✗ Some OpenReconLabel.json files are invalid!")
        print("Please fix the validation errors before merging.")
        sys.exit(1)


if __name__ == '__main__':
    main()
