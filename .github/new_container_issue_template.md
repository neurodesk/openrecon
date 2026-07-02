---
title: New container {{ env.IMAGENAME }} / {{ env.FIRE_IMAGENAME }}
labels: enhancement
---
The OpenRecon and FIRE bundles were successfully built by @{{ env.GITHUB_ACTOR }}. To test them, download:
```bash
curl -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.IMAGENAME }}.zip
```
 
For OpenRecon, copy the zip file to C:\Program Files\Siemens\Numaris\OperationalManagement\FileTransfer\incoming.

On scanners that can download files directly, open an administrator PowerShell, navigate to that `incoming` folder, and run:

```powershell
curl.exe -k -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.IMAGENAME }}.zip
```

For FIRE:

```bash
curl -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.FIRE_IMAGENAME }}.zip
```

To install the FIRE package, unpack the zip and copy/merge the `Ice` folder into `MriCustomer` as described in `INSTALL_FIRE.txt`.

once tested upload to https://webclient.au.api.teamplay.siemens-healthineers.com/ and make available to all institutes.

Please close this issue when completed :)
