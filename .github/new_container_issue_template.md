---
title: New container {{ env.IMAGENAME }}
labels: enhancement
---
The container has been successfully build by @{{ env.GITHUB_ACTOR }}. To test the container, download:
```
curl -O https://openrecon.neurodesk.org/{{ env.IMAGENAME }}.zip
```
 
and copy the zip file to C:\Program Files\Siemens\Numaris\OperationalManagement\FileTransfer\incoming

once tested upload to https://webclient.au.api.teamplay.siemens-healthineers.com/ and make available to all institutes.

Please close this issue when completed :)


