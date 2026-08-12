---
title: New container {{ env.IMAGENAME }} / {{ env.FIRE_IMAGENAME }}
labels: enhancement
---
The OpenRecon and FIRE bundles were successfully built by @{{ env.GITHUB_ACTOR }}. To test them, download:
```bash
curl -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.IMAGENAME }}.zip
```
 
Make sure that no protocol is open, because an open protocol can prevent installation of a new package.

### Installing on XA70 / Numaris/X VA70 and later (for example, XB10 / VB10)

For syngo MR XA70 (Numaris/X VA70) and later, use the Numaris/Edge routine for installing OpenRecon applications:

1. Exit Kiosk mode on the MRAWP with `[Tab]` + `[Del]` + `[Num +]`.
2. Create `C:\Temp\OR\Packages`.
3. Copy `{{ env.IMAGENAME }}.zip` to `C:\Temp\OR\Packages` without extracting it.
4. Press the Windows key and open an elevated administrator CMD shell.
5. Change to the Numaris/Edge directory:

   ```bat
   cd /d "%MREDGEHOME%"
   ```

6. Install the package:

   ```bat
   syngo.MR.Digi.Utils.Console.exe store --install-package "C:\Temp\OR\Packages\{{ env.IMAGENAME }}.zip"
   ```

7. Installation can take several minutes. Repeat the following command until the package is listed as installed:

   ```bat
   syngo.MR.Digi.Utils.Console.exe store --list
   ```

### Installing and testing on XA60 and XA61

1. Copy the OpenRecon zip file, without extracting it, to `C:\Program Files\Siemens\Numaris\OperationalManagement\FileTransfer\incoming`.
2. On scanners that can download files directly, open an administrator PowerShell, navigate to the `incoming` folder, and run:

   ```powershell
   curl.exe -k -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.IMAGENAME }}.zip
   ```

3. Wait for the zip file to disappear from the `incoming` folder.
4. Monitor installation in `C:\ProgramData\Siemens\Numaris\log\syngo.MR.HostInfra.OpenRecon.Watcher`. It should first create a 0 KB text file named for the container and version; that file should then grow to approximately 100-200 KB.
5. Once the log file has been written, open a protocol and confirm that the package is available.
6. Run the sequence with OpenRecon enabled and check for errors in `C:\ProgramData\Siemens\Numaris\log\OpenRecon.utr`.

For FIRE:

```bash
curl -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.FIRE_IMAGENAME }}.zip
```

To install the FIRE package, unpack the zip and copy/merge the `Ice` folder into `MriCustomer` as described in `INSTALL_FIRE.txt`.

once tested upload to https://webclient.au.api.teamplay.siemens-healthineers.com/ and make available to all institutes.

Please close this issue when completed :)
