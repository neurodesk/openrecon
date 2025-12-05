#!/bin/bash
# build image here: https://github.com/NeuroDesk/neurocontainers and add mrd server instructions: https://www.neurodesk.org/docs/getting-started/neurocontainers/openrecon/
# specify the repostiory and name of the docker image: https://hub.docker.com/orgs/vnmd/repositories
export toolName=metabody
export version=1.0.0
export baseDockerImage=vnmd/${toolName}_${version}
# this image is build based on 
# https://github.com/neurodesk/neurocontainers/blob/main/recipes/metabody/build.yaml