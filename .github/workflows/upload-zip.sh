#!/bin/bash
set -e

ZIPFILE=$1
IMAGENAME=$(echo $(basename $ZIPFILE .zip))

echo "[DEBUG] ZIPFILE: $ZIPFILE"
echo "[DEBUG] IMAGENAME: $IMAGENAME"

ls -la $ZIPFILE

#This prevents the sometimes stuck apt process from stopping the build
if [ -f "/var/lib/apt/lists/lock" ]; then
  sudo rm /var/lib/apt/lists/lock
  sudo rm /var/cache/apt/archives/lock
  sudo rm /var/lib/dpkg/lock*
fi

# check if aws cli is installed
if ! command -v aws &>/dev/null; then
  echo "[DEBUG] Installing AWS CLI"
  curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && unzip awscliv2.zip && sudo ./aws/install && rm -rf aws awscliv2.zip
fi
time aws s3 cp $ZIPFILE s3://openrecon/${IMAGENAME}.zip
echo "[DEBUG] Done with uploading to AWS Object Storage!"

if curl --output /dev/null --silent --head --fail "https://openrecon.s3.us-east-2.amazonaws.com/${IMAGENAME}.zip"; then
    echo "[DEBUG] ${IMAGENAME}.zip was freshly build and exists now :)"
    echo "[DEBUG] cleaning up $ZIPFILE and ${ZIPFILE%.zip}.tar "
    rm -f $ZIPFILE
    rm -f ${ZIPFILE%.zip}.tar
else
    echo "[ERROR] ${IMAGENAME}.zip does not exist yet. Something is WRONG"
    exit 2
fi

