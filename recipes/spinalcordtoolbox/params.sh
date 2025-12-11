#!/bin/bash
# build image here: https://github.com/NeuroDesk/neurocontainers and add mrd server instructions: https://www.neurodesk.org/docs/getting-started/neurocontainers/openrecon/
# specify the repostiory and name of the docker image: https://hub.docker.com/orgs/vnmd/repositories
export toolName=spinalcordtoolbox
export version=7.2
export baseDockerImage=vnmd/${toolName}_${version}
export openrecon_version=${version}.0 #this is only necessary if tool version is not following semantic versioning
# this image is build based on 
# https://github.com/neurodesk/neurocontainers/blob/main/recipes/spinalcordtoolbox/build.yaml
