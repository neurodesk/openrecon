#!/usr/bin/env python3
"""
Standalone script to validate OpenReconLabel.json files against the OpenRecon schema.
This script is designed to be used in CI/CD pipelines and can validate multiple files.
"""

import json
import jsonschema
import sys
import os
from pathlib import Path


def validate_json_file(json_file_path, schema_file_path):
    """
    Validate a JSON file against a JSON schema.
    
    Args:
        json_file_path: Path to the JSON file to validate
        schema_file_path: Path to the JSON schema file
        
    Returns:
        tuple: (is_valid: bool, errors: list)
    """
    try:
        # Load the JSON data from the file
        with open(json_file_path, 'r') as json_file:
            json_data = json.load(json_file)

        # Handle VERSION_WILL_BE_REPLACED_BY_SCRIPT placeholder
        # This placeholder is replaced during the build process, but for validation
        # we need to temporarily replace it with a valid version string
        if 'general' in json_data and 'version' in json_data['general']:
            if json_data['general']['version'] == 'VERSION_WILL_BE_REPLACED_BY_SCRIPT':
                json_data['general']['version'] = '0.0.0'
        
        # Also handle it in production_identifier within regulatory_information
        if 'general' in json_data and 'regulatory_information' in json_data['general']:
            reg_info = json_data['general']['regulatory_information']
            if 'production_identifier' in reg_info:
                if reg_info['production_identifier'] == 'VERSION_WILL_BE_REPLACED_BY_SCRIPT':
                    reg_info['production_identifier'] = '0.0.0'
            if 'material_number' in reg_info:
                reg_info['material_number'] = reg_info['material_number'].replace('VERSION_WILL_BE_REPLACED_BY_SCRIPT', '0.0.0')

        # Load the JSON schema from the file
        with open(schema_file_path, 'r') as schema_file:
            schema_data = json.load(schema_file)

        # Create a JSON Schema validator
        validator = jsonschema.Draft7Validator(schema_data)

        # Validate the JSON data against the schema
        errors = list(validator.iter_errors(json_data))

        return (len(errors) == 0, errors)
    
    except json.JSONDecodeError as e:
        return (False, [f"JSON parsing error: {e}"])
    except FileNotFoundError as e:
        return (False, [f"File not found: {e}"])
    except Exception as e:
        return (False, [f"Unexpected error: {e}"])


def main():
    """
    Main function to validate OpenReconLabel.json files.
    Accepts file paths as command line arguments or validates all files in recipes directory.
    """
    # Determine the base directory (where this script is located)
    script_dir = Path(__file__).parent.resolve()
    schema_path = script_dir / 'OpenReconSchema_1.1.0.json'
    
    # Check if schema file exists
    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}")
        sys.exit(1)
    
    # Get list of files to validate
    files_to_validate = []
    
    if len(sys.argv) > 1:
        # Validate files provided as command line arguments
        for arg in sys.argv[1:]:
            file_path = Path(arg).resolve()
            if file_path.exists():
                files_to_validate.append(file_path)
            else:
                print(f"Warning: File not found: {arg}")
    else:
        # Find all OpenReconLabel.json files in recipes subdirectories
        for recipe_dir in script_dir.iterdir():
            if recipe_dir.is_dir() and recipe_dir.name not in ['.git', '__pycache__']:
                json_file = recipe_dir / 'OpenReconLabel.json'
                if json_file.exists():
                    files_to_validate.append(json_file)
    
    if not files_to_validate:
        print("No OpenReconLabel.json files found to validate.")
        sys.exit(0)
    
    # Validate all files
    all_valid = True
    results = []
    
    print(f"Validating {len(files_to_validate)} OpenReconLabel.json file(s) against schema...")
    print(f"Schema: {schema_path}")
    print("-" * 80)
    
    for json_file in files_to_validate:
        relative_path = json_file.relative_to(script_dir.parent) if json_file.is_relative_to(script_dir.parent) else json_file
        print(f"\nValidating: {relative_path}")
        
        is_valid, errors = validate_json_file(json_file, schema_path)
        
        if is_valid:
            print(f"  ✓ VALID")
            results.append((json_file, True, []))
        else:
            print(f"  ✗ INVALID")
            all_valid = False
            results.append((json_file, False, errors))
            
            for error in errors:
                if isinstance(error, str):
                    print(f"    - {error}")
                else:
                    # Format jsonschema ValidationError
                    path = '.'.join(str(p) for p in error.path) if error.path else 'root'
                    print(f"    - Path: {path}")
                    print(f"      Error: {error.message}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    valid_count = sum(1 for _, is_valid, _ in results if is_valid)
    invalid_count = len(results) - valid_count
    
    print(f"Total files: {len(results)}")
    print(f"Valid: {valid_count}")
    print(f"Invalid: {invalid_count}")
    
    if all_valid:
        print("\n✓ All OpenReconLabel.json files are valid!")
        sys.exit(0)
    else:
        print("\n✗ Some OpenReconLabel.json files are invalid!")
        print("Please fix the validation errors before merging.")
        sys.exit(1)


if __name__ == '__main__':
    main()
