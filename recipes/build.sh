#!/bin/bash
set -e
#This script will run inside the tool directory

# Command-line options
IGNORE_MDPDF=false
FORCE_LOCAL_CACHE=false
BUILD_PACKAGE_SELECTION=${BUILD_PACKAGE_SELECTION:-both}

usage() {
    cat <<EOF
Usage: /bin/bash ../build.sh [options]

Options:
  --ignore-mdpdf               Skip README.md -> README.pdf generation
  --local-cache                Force using an already-cached local base Docker image
                               (auto-preloads the DinD bootstrap image if needed)
  -h, --help                   Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ignore-mdpdf)
            IGNORE_MDPDF=true
            shift
            ;;
        --local-cache)
            FORCE_LOCAL_CACHE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'"
            usage
            exit 1
            ;;
    esac
done

# When running offline with a forced local cache, allow the user to limit which
# distributable package(s) should be created.
if [[ "$FORCE_LOCAL_CACHE" == "true" ]]; then
    is_ci=${GITHUB_ACTIONS:-${CI:-}}
    if [[ -z "$is_ci" && -t 0 && -z "${BUILD_PACKAGE_SELECTION_OVERRIDE:-}" ]]; then
        echo ""
        echo "📦 Offline build package selection"
        echo "  1) OpenRecon package only"
        echo "  2) FIRE package only"
        echo "  3) Both packages"
        while true; do
            read -r -p "Select package(s) to create [3]: " package_choice
            case "${package_choice:-3}" in
                1)
                    BUILD_PACKAGE_SELECTION=openrecon
                    break
                    ;;
                2)
                    BUILD_PACKAGE_SELECTION=fire
                    break
                    ;;
                3)
                    BUILD_PACKAGE_SELECTION=both
                    break
                    ;;
                *)
                    echo "Please enter 1, 2, or 3."
                    ;;
            esac
        done
    fi
fi

case "$BUILD_PACKAGE_SELECTION" in
    openrecon|fire|both)
        ;;
    *)
        echo "Error: BUILD_PACKAGE_SELECTION must be one of: openrecon, fire, both"
        exit 1
        ;;
esac

export BUILD_PACKAGE_SELECTION
echo "Package selection: $BUILD_PACKAGE_SELECTION"

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
if [[ "$IGNORE_MDPDF" == "true" ]]; then
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

LOCAL_IMAGE_TAG=""
CANONICAL_LOCAL_TAG=""

# Prefer local "name:version" tags when available.
# If toolName is not defined in params.sh, derive from baseDockerImage like:
#   vnmd/vesselboost_2.0.0 -> vesselboost:2.0.0
if [ -n "$toolName" ]; then
    CANONICAL_LOCAL_TAG="${toolName}:${docker_version}"
else
    BASE_IMAGE_BASENAME="${baseDockerImage##*/}"
    if [[ "$BASE_IMAGE_BASENAME" == *_* ]]; then
        DERIVED_TOOL_NAME="${BASE_IMAGE_BASENAME%_*}"
        DERIVED_TOOL_VERSION="${BASE_IMAGE_BASENAME##*_}"
        CANONICAL_LOCAL_TAG="${DERIVED_TOOL_NAME}:${DERIVED_TOOL_VERSION}"
    fi
fi

# Preferred local lookup order:
# 1) explicit localDockerImage override
# 2) canonical local name:version (tool:version)
# 3) baseDockerImage tag itself
if [ -n "$localDockerImage" ] && docker image inspect "$localDockerImage" >/dev/null 2>&1; then
    LOCAL_IMAGE_TAG="$localDockerImage"
elif [ -n "$CANONICAL_LOCAL_TAG" ] && docker image inspect "$CANONICAL_LOCAL_TAG" >/dev/null 2>&1; then
    LOCAL_IMAGE_TAG="$CANONICAL_LOCAL_TAG"
elif docker image inspect "$baseDockerImage" >/dev/null 2>&1; then
    LOCAL_IMAGE_TAG="$baseDockerImage"
fi

if [[ "$FORCE_LOCAL_CACHE" == "true" ]]; then
    if [ -z "$LOCAL_IMAGE_TAG" ]; then
        echo "Error: --local-cache was requested, but no matching local image was found."
        echo "Checked:"
        if [ -n "$localDockerImage" ]; then
            echo "  - $localDockerImage (from localDockerImage)"
        fi
        if [ -n "$CANONICAL_LOCAL_TAG" ]; then
            echo "  - $CANONICAL_LOCAL_TAG (canonical local name:version)"
        fi
        echo "  - $baseDockerImage (from baseDockerImage)"
        exit 1
    fi

    echo "Using local cached Docker image (forced): $LOCAL_IMAGE_TAG"
    export baseDockerImage="$LOCAL_IMAGE_TAG"
    export DOCKER_IMAGE_TO_USE="$LOCAL_IMAGE_TAG"
    export USE_LOCAL_IMAGE=true
    export FORCE_LOCAL_ONLY=true
else
    if [ -n "$LOCAL_IMAGE_TAG" ]; then
        echo "Local Docker cache hit. Using local image: $LOCAL_IMAGE_TAG"
        export baseDockerImage="$LOCAL_IMAGE_TAG"
        export DOCKER_IMAGE_TO_USE="$LOCAL_IMAGE_TAG"
        export USE_LOCAL_IMAGE=true
    else
        echo "No local cache hit. Using remote image: $baseDockerImage"
        export DOCKER_IMAGE_TO_USE="$baseDockerImage"
        export USE_LOCAL_IMAGE=false
    fi
    export FORCE_LOCAL_ONLY=false
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

echo ""
echo "🧹 Cleaning up generated build artifacts..."
if [ -f "README.pdf" ]; then
    rm -f README.pdf
    echo "✓ Removed README.pdf"
fi
if [ -f "OpenRecon.dockerfile" ]; then
    rm -f OpenRecon.dockerfile
    echo "✓ Removed OpenRecon.dockerfile"
fi
