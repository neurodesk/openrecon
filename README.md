# neurorecon

Repository for building OpenRecon containers.

## JSON Validation

All OpenRecon recipes must have a valid `OpenReconLabel.json` file that conforms to the OpenRecon schema. This validation is automatically enforced on pull requests.

### Running Validation Locally

To validate your OpenReconLabel.json files before submitting a PR:

```bash
# Validate all recipes
python3 recipes/validate_json.py

# Validate specific recipes
python3 recipes/validate_json.py recipes/myrecipe/OpenReconLabel.json
```

### Schema Requirements

- **Parameter IDs**: Must match pattern `^[A-Za-z0-9]+$` (alphanumeric only, no underscores or special characters)
- **Version**: Must follow semantic versioning (e.g., `1.0.0`)
- **Double type parameters**: Values must be multiples of 0.1
- **Protocol**: Must be "ISMRMRD" with version "1.4.1"

See `recipes/OpenReconSchema_1.1.0.json` for the complete schema specification.
