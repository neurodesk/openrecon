#!/bin/bash
set -e
#This script will run inside the tool directory

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
if [[ "$2" == "--ignore-mdpdf" ]]; then
    echo "Ignoring mdpdf."
else
    mdpdf README.md
fi

# source tool-specific parameters
source params.sh

# Check if a local image with format ${toolName}:${version} exists
LOCAL_IMAGE_TAG="${toolName}:${version}"
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

# Create a temporary backup of OpenReconLabel.json
echo "Creating backup of OpenReconLabel.json..."
cp OpenReconLabel.json OpenReconLabel.json.backup

# replace VERSION_WILL_BE_REPLACED_BY_SCRIPT in OpenReconLabel.json with $version
# run correct sed command on MacOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/VERSION_WILL_BE_REPLACED_BY_SCRIPT/$version/g" OpenReconLabel.json
fi
# run correct sed command on Linux
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sed -i "s/VERSION_WILL_BE_REPLACED_BY_SCRIPT/$version/g" OpenReconLabel.json
fi

echo "This is the OpenReconLabel.json file:"
echo "----------------------------------------"
cat OpenReconLabel.json
echo "----------------------------------------"

echo "baseDockerImage: $baseDockerImage"

# build zip file
echo "Building OpenRecon file..."
python3 ../build.py

# restore VERSION_WILL_BE_REPLACED_BY_SCRIPT in OpenReconLabel.json from backup
echo "Restoring VERSION_WILL_BE_REPLACED_BY_SCRIPT in OpenReconLabel.json..."
mv OpenReconLabel.json.backup OpenReconLabel.json
echo "OpenReconLabel.json restored from backup."
