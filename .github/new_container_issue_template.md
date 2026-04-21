---
title: New container {{ env.IMAGENAME }} / {{ env.FIRE_IMAGENAME }}
labels: enhancement
---
The OpenRecon and FIRE bundles were successfully built by @{{ env.GITHUB_ACTOR }}. To test them, download:
```
curl -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.IMAGENAME }}.zip
curl -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.FIRE_IMAGENAME }}.zip
```
 
For OpenRecon, copy the zip file to C:\Program Files\Siemens\Numaris\OperationalManagement\FileTransfer\incoming.

For FIRE, unpack the zip and install the `.img`, `fire.ini.template`, and `share` contents under `%CustomerIceProgs%\fire\` as described in `INSTALL_FIRE.txt`.

once tested upload to https://webclient.au.api.teamplay.siemens-healthineers.com/ and make available to all institutes.

Please close this issue when completed :)
