#!/bin/bash
# build image here: https://github.com/NeuroDesk/neurocontainers and add mrd server instructions: https://www.neurodesk.org/docs/getting-started/neurocontainers/openrecon/
# specify the repostiory and name of the docker image: https://hub.docker.com/orgs/vnmd/repositories
export toolName=musclemap
export version=0.4.0
export baseDockerImage=vnmd/${toolName}_${version}
