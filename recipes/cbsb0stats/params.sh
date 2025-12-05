#!/bin/bash
# specify the repostiory and name of the docker image
export toolName=cbsb0stats
export version=1.1.0
export baseDockerImage=vnmd/${toolName}_${version}
# this image is build based on 
# https://github.com/neurodesk/neurocontainers/blob/main/recipes/cbsb0stats/build.yaml