#!/bin/bash
# build image here: https://github.com/NeuroDesk/neurocontainers and add mrd server instructions: https://www.neurodesk.org/docs/getting-started/neurocontainers/openrecon/
# specify the repostiory and name of the docker image: https://hub.docker.com/orgs/vnmd/repositories
export toolName=sodiumgridding_ptpi
export version=0.1.0
export baseDockerImage=vnmd/${toolName}_${version}
# this image is build based on 
# https://github.com/neurodesk/neurocontainers/blob/main/recipes/sodiumgridding_ptpi/build.yaml
# source .venv/bin/activate
# cd recipes/sodiumgridding_ptpi
# /bin/bash ../build.sh --local-cache
