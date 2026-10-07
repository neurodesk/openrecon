#!/bin/bash
# specify the repository and name of the docker image
export toolName=b0map
export version=1.0.0.post1
export openrecon_version=1.0.0
export baseDockerImage=vnmd/${toolName}_${version}
# this image is build based on 
# https://github.com/neurodesk/neurocontainers/blob/main/recipes/b0map/build.yaml
