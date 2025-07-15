#!/bin/bash
# build image here: https://github.com/NeuroDesk/neurocontainers and add mrd server instructions: https://www.neurodesk.org/docs/getting-started/neurocontainers/openrecon/
# specify the repostiory and name of the docker image: https://hub.docker.com/orgs/vnmd/repositories
export version=3.0.0
# rebuild
export baseDockerImage=vnmd/prostatefiducialseg_${version}
