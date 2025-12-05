#!/bin/bash
# specify the repostiory and name of the docker image
export toolName=afib1
export version=1.6.0
export baseDockerImage=vnmd/${toolName}_${version}
# this image is build based on 
# https://github.com/neurodesk/neurocontainers/blob/main/recipes/afib1/build.yaml