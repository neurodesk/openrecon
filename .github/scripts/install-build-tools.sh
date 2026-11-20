#!/bin/bash
# Install what build.sh and the publish steps need on an ARC runner pod, which
# starts from the minimal actions-runner image: the Python venv module, 7z, gh,
# the AWS CLI, and the shared libraries of the Chrome that mdpdf uses for
# README.pdf.
set -euo pipefail

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  python3-venv p7zip-full gh unzip \
  libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libxkbcommon0 \
  libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
  libcairo2 libasound2t64 libdrm2 libxshmfence1

if ! command -v aws >/dev/null; then
  installer=$(mktemp -d)
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "$installer/awscliv2.zip"
  unzip -q "$installer/awscliv2.zip" -d "$installer"
  sudo "$installer/aws/install"
  rm -rf "$installer"
fi
aws --version
