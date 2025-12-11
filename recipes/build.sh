#!/bin/bash
set -e
#This script will run inside the tool directory

# Cleanup function to restore backup on exit (including interruptions)
cleanup() {
    exit_code=$?
    if [ -f "OpenReconLabel.json.backup" ]; then
        echo ""
        echo "🔄 Restoring OpenReconLabel.json from backup..."
        mv OpenReconLabel.json.backup OpenReconLabel.json
        echo "✓ OpenReconLabel.json restored."
    fi
    if [ -f "README.md.backup" ]; then
        echo "🔄 Restoring README.md from backup..."
        mv README.md.backup README.md
        echo "✓ README.md restored."
    fi
    # Exit with the original exit code
    exit $exit_code
}

# Set trap to call cleanup on EXIT, INT (Ctrl+C), TERM, and other signals
trap cleanup EXIT INT TERM

# check and install dependencies
if ! command -v pip3 &> /dev/null; then
    #check if on MacOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install python3
    fi
    # check if on Linux
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # check if apt is available
        if command -v apt &> /dev/null; then
            sudo apt update
            sudo apt install -y python3 python3-pip
        # check if yum is available
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3 python3-pip
        # check if dnf is available
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y python3 python3-pip
        else
            echo "Error: No package manager found. Please install Python 3 and pip manually."
            exit 1
        fi
    fi
fi

if ! pip3 show jsonschema &> /dev/null; then
    pip3 install jsonschema
fi

if ! pip3 show packaging &> /dev/null; then
    pip3 install packaging
fi

if ! command -v 7z &> /dev/null; then
    # check if on MacOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install p7zip
    fi
    # check if on Linux
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # check if apt is available
        if command -v apt &> /dev/null; then
            sudo apt update
            sudo apt install -y p7zip-full
        # check if yum is available
        elif command -v yum &> /dev/null; then
            sudo yum install -y p7zip-full
        # check if dnf is available
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y p7zip-full
        else
            echo "Error: No package manager found. Please install p7zip manually."
            exit 1
        fi
    fi
fi

if ! command -v mdpdf &> /dev/null; then
    # check if directory $HOME/.nvm exists:
    if [ ! -d "$HOME/.nvm" ]; then
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash
        source ~/.bashrc
        nvm list-remote
        nvm install v22.3.0
        nvm list
    else
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
    fi
    npm install mdpdf -g
fi

# check docker version
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker."
    exit 1
fi

# build pdf file from README.md
# source tool-specific parameters
source params.sh

# Handle openrecon_version if set
# When openrecon_version is set, use 'version' for docker operations
# and 'openrecon_version' for OpenRecon-specific files and metadata
if [ -n "$openrecon_version" ]; then
    echo "🔧 openrecon_version detected: $openrecon_version"
    echo "   Docker operations will use version: $version"
    echo "   OpenRecon metadata will use version: $openrecon_version"
    # Store original version for docker operations
    docker_version="$version"
    # Use openrecon_version for everything else
    version="$openrecon_version"
else
    echo "📦 Using standard version: $version (for both Docker and OpenRecon)"
    docker_version="$version"
fi

# Create backups before any modifications
echo "Creating backup of OpenReconLabel.json..."
cp OpenReconLabel.json OpenReconLabel.json.backup

if [ -f "README.md" ]; then
    echo "Creating backup of README.md..."
    cp README.md README.md.backup
    
    # Replace VERSION_WILL_BE_REPLACED_BY_SCRIPT in README.md with $version
    # run correct sed command on MacOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/VERSION_WILL_BE_REPLACED_BY_SCRIPT/$version/g" README.md
    fi
    # run correct sed command on Linux
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sed -i "s/VERSION_WILL_BE_REPLACED_BY_SCRIPT/$version/g" README.md
    fi
    echo "✓ Version replaced in README.md"
fi

# Build PDF from README.md (after version replacement)
if [[ "$2" == "--ignore-mdpdf" ]]; then
    echo "Ignoring mdpdf."
else
    if [ -f "README.md" ]; then
        if [ -f "README.pdf" ]; then
            echo "⏭️  README.pdf already exists, skipping PDF generation."
        else
            echo "📄 Generating PDF from README.md..."
            mdpdf README.md
        fi
    fi
fi

# Check if a local image with format ${toolName}:${docker_version} exists
# Note: docker_version is either the original version (when openrecon_version is set) or same as version
LOCAL_IMAGE_TAG="${toolName}:${docker_version}"
echo "Checking if local Docker image exists: $LOCAL_IMAGE_TAG"
if docker image inspect "$LOCAL_IMAGE_TAG" >/dev/null 2>&1; then
    echo "Local Docker image found. Using local version: $LOCAL_IMAGE_TAG"
    # Replace the remote image reference with local tag in baseDockerImage
    export baseDockerImage="$LOCAL_IMAGE_TAG"
    export DOCKER_IMAGE_TO_USE="$LOCAL_IMAGE_TAG"
    export USE_LOCAL_IMAGE=true
else
    echo "Local Docker image not found. Using remote image: $baseDockerImage"
    export DOCKER_IMAGE_TO_USE="$baseDockerImage"
    export USE_LOCAL_IMAGE=false
fi

# Check if localDockerImage is set and exists locally (for backward compatibility)
if [ -n "$localDockerImage" ]; then
    echo "Checking if localDockerImage override exists: $localDockerImage"
    if docker image inspect "$localDockerImage" >/dev/null 2>&1; then
        echo "Local Docker image override found. Using: $localDockerImage"
        export baseDockerImage="$localDockerImage"
        export DOCKER_IMAGE_TO_USE="$localDockerImage"
        export USE_LOCAL_IMAGE=true
    fi
fi

echo "Docker image to use: $DOCKER_IMAGE_TO_USE"

# Replace VERSION_WILL_BE_REPLACED_BY_SCRIPT in OpenReconLabel.json with $version
# run correct sed command on MacOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/VERSION_WILL_BE_REPLACED_BY_SCRIPT/$version/g" OpenReconLabel.json
fi
# run correct sed command on Linux
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sed -i "s/VERSION_WILL_BE_REPLACED_BY_SCRIPT/$version/g" OpenReconLabel.json
fi
echo "✓ Version replaced in OpenReconLabel.json"

echo "This is the OpenReconLabel.json file:"
echo "----------------------------------------"
cat OpenReconLabel.json
echo "----------------------------------------"

echo "baseDockerImage: $baseDockerImage"

# build zip file
echo "Building OpenRecon file..."
python3 ../build.py

# Note: Backup restoration now handled by cleanup trap function
# This ensures restoration even if script is interrupted

# Optional cleanup of build artifacts
echo ""
echo "🧹 Build artifacts cleanup"
echo "The following files can be removed:"
if [ -f "README.pdf" ]; then
    echo "  - README.pdf"
fi
if [ -f "OpenRecon.dockerfile" ]; then
    echo "  - OpenRecon.dockerfile"
fi
# Find the ZIP file (it follows the naming convention OpenRecon_vendor_name_Vversion.zip)
ZIP_FILE=$(ls OpenRecon_*.zip 2>/dev/null | head -n 1)
if [ -n "$ZIP_FILE" ]; then
    echo "  - $ZIP_FILE"
fi

while true; do
    read -p "Do you want to remove these files? (y/n): " response
    case "$response" in
        [Yy]* )
            if [ -f "README.pdf" ]; then
                rm -f README.pdf
                echo "✓ Removed README.pdf"
            fi
            if [ -f "OpenRecon.dockerfile" ]; then
                rm -f OpenRecon.dockerfile
                echo "✓ Removed OpenRecon.dockerfile"
            fi
            if [ -n "$ZIP_FILE" ] && [ -f "$ZIP_FILE" ]; then
                rm -f "$ZIP_FILE"
                echo "✓ Removed $ZIP_FILE"
            fi
            echo "🎉 Cleanup complete!"
            break
            ;;
        [Nn]* )
            echo "⏭️  Skipping cleanup. Files retained for reference."
            break
            ;;
        * )
            echo "Please answer y or n."
            ;;
    esac
done
