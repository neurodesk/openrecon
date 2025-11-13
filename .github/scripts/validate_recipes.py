#!/usr/bin/env python3
"""
CI validation script that uses the validateJson function from build.py.
Handles VERSION_WILL_BE_REPLACED_BY_SCRIPT placeholder for validation purposes.
"""

import sys
import os
import json
import tempfile
import jsonschema
from pathlib import Path


def validateJson(jsonFilePath, schemaFilePath):
    """
    Validate JSON file against OpenRecon schema (from build.py).
    """
    try:
        # Load the JSON data from the file
        with open(jsonFilePath, 'r') as jsonFile:
            jsonData = json.load(jsonFile)

        # Load the JSON schema from the file
        with open(schemaFilePath, 'r') as schemaFile:
            schemaData = json.load(schemaFile)

        # Create a JSON Schema validator
        validator = jsonschema.Draft7Validator(schemaData)

        # Validate the JSON data against the schema
        errors = list(validator.iter_errors(jsonData))

        if not errors:
            print("JSON is valid against the schema.")
            return True
        else:
            print("JSON is not valid against the schema. Errors:")
            for error in errors:
                print(error)
            return False
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


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
    
    # Replace VERSION_WILL_BE_REPLACED_BY_SCRIPT with a valid version for validation
    if 'general' in json_data and 'version' in json_data['general']:
        if json_data['general']['version'] == 'VERSION_WILL_BE_REPLACED_BY_SCRIPT':
            json_data['general']['version'] = '0.0.0'
    
    if 'general' in json_data and 'regulatory_information' in json_data['general']:
        reg_info = json_data['general']['regulatory_information']
        if 'production_identifier' in reg_info:
            if reg_info['production_identifier'] == 'VERSION_WILL_BE_REPLACED_BY_SCRIPT':
                reg_info['production_identifier'] = '0.0.0'
        if 'material_number' in reg_info:
            reg_info['material_number'] = reg_info['material_number'].replace(
                'VERSION_WILL_BE_REPLACED_BY_SCRIPT', '0.0.0'
            )
    
    # Write to temporary file for validation
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        json.dump(json_data, tmp, indent=2)
        tmp_path = tmp.name
    
    try:
        # Use the existing validateJson function from build.py
        result = validateJson(tmp_path, schema_path)
        return result
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
