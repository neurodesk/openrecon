---
title: New container {{ env.IMAGENAME }} / {{ env.FIRE_IMAGENAME }}
labels: enhancement
---
Two separate bundles were successfully built by @{{ env.GITHUB_ACTOR }} from the same container: an **OpenRecon** package for the scanner package store, and a **FIRE** package for the WIP 070 FIRE framework. They are installed and configured independently, so follow only the section for the one you are testing.

## OpenRecon

Download the OpenRecon bundle:

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

## FIRE

Download the FIRE bundle:

```bash
curl -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.FIRE_IMAGENAME }}.zip
```

FIRE can run this reconstruction in two ways. Option A is what the bundle ships configured for and needs no network setup. Option B runs the same container on separate hardware, which is the option to pick when the reconstruction needs more memory than MARS has.

### FIRE option A: chroot image on MARS (default)

Unpack the zip and copy/merge the `Ice` folder into `MriCustomer` as described in `INSTALL_FIRE.txt`. The chroot image lands in `%CustomerIceProgs%\fire\chroot\` and `%CustomerIceProgs%\fire\{{ env.FIRE_INI_NAME }}` already has `start_chroot=true`, so no further configuration is needed.

### FIRE option B: Docker container on another machine (same network as MARS, or through an SSH tunnel)

The same container can run under Docker on any machine MARS can reach: either directly on the scanner-internal network that MARS sits on (`192.168.2.x`), or on an external machine reached through the SSH tunnel that FIRE opens from the scanner host. `wip_070_fire_fire_mars_ssh.ini` in the WIP 070 package is the reference configuration for the tunnel variant.

Install the FIRE bundle as in option A first, so the workflow XML and ini file are present on the scanner.

#### B1. Get the container onto the compute machine

Either pull the Neurodesk container this bundle is built from, which avoids copying zip files around:

```bash
docker pull {{ env.BASE_DOCKER_IMAGE }}
```

This is the same container with the same tools and the same `python-ismrmrd-server`; the OpenRecon build only adds the OpenRecon metadata label and a pre-set start command on top of it, so the start command has to be given explicitly in step B2.

Or load the exact built image out of the OpenRecon zip, which contains it as a `docker save` tar:

```bash
curl -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.IMAGENAME }}.zip
unzip {{ env.IMAGENAME }}.zip
docker load -i {{ env.IMAGENAME }}.tar
```

#### B2. Start the server

The server listens on `0.0.0.0:9002` inside the container, the same way the upstream `kspacekelvin/fire-python` server is run (`docker run --rm -it -p 9002:9002 kspacekelvin/fire-python`), so only the port publication has to be set.

With the registry image, pass the start command explicitly:

```bash
docker run --rm -it -p 9002:9002 -v /tmp/share:/tmp/share {{ env.BASE_DOCKER_IMAGE }} \
  /bin/bash -c '/usr/sbin/ldconfig; exec python3 /opt/code/python-ismrmrd-server/main.py -v -H=0.0.0.0 -p=9002 -l=/tmp/python-ismrmrd-server.log'
```

With the image loaded from the OpenRecon zip, the start command is already baked in:

```bash
docker run --rm -it -p 9002:9002 -v /tmp/share:/tmp/share {{ env.DOCKER_IMAGE_TAG }}
```

For a long-lived service, run it detached instead:

```bash
docker run -d --restart unless-stopped --name fire-server -p 9002:9002 -v /tmp/share:/tmp/share {{ env.DOCKER_IMAGE_TAG }}
```

- To listen on a different port on the compute machine, remap the host side only and keep `9002` inside the container, for example `-p 9010:9002`.
- Add `--gpus all` if the reconstruction uses CUDA.
- The server writes its log to `/tmp/python-ismrmrd-server.log` inside the container; `docker logs -f fire-server` shows the same output.
- Confirm the port is reachable from the scanner before scanning, for example `nc -vz <IP of the compute machine> 9002`.

#### B3. Point FIRE at that machine

Edit `%CustomerIceProgs%\fire\{{ env.FIRE_INI_NAME }}` on the scanner, which is the ini file the FIRE workflow XML references in `<IniFile>`. `start_chroot` has to be `false` so MARS does not start the local chroot as well.

Same network as MARS, no tunnel; send the data straight to the machine running the container:

```ini
[fire]
hostname=<IP of the machine running the container>
port=9002

[chroot]
start_chroot=false

[tunnel]
open_tunnel=false
```

Through the SSH tunnel from the scanner host, the `wip_070_fire_fire_mars_ssh.ini` pattern; FIRE sends to a local port on the host and `plink.exe` forwards it to the container:

```ini
[fire]
hostname=192.168.2.1
port=9003

[chroot]
start_chroot=false

[tunnel]
open_tunnel=true
local_hostname=192.168.2.1
local_fire_port=9003
remote_hostname=<IP of the machine running the container>
remote_ssh_port=22
remote_fire_port=9002
remote_user=<user on the compute machine>
remote_ssh_key_file=id_rsa.ppk
remote_ssh_fingerprint=<MD5 host fingerprint of the compute machine>
auto_close_duration=900
```

- The bundled ini ships `hostname` and `port` in its leading section with the MARS defaults (`192.168.2.2:9002`); replace that leading section with the block above.
- `remote_fire_port` is the host side of the `-p` mapping used in step B2, and `port` in `[fire]` has to match `local_fire_port`.
- `local_hostname` is the IP of the scanner host system, typically `192.168.2.1`; confirm it with `ipconfig` on the host.
- `remote_ssh_key_file` is a PuTTY `.ppk` private key that has to sit in `C:\Medcom\MriCustomer\ice\fire\`. Create the key pair with `ssh-keygen -t rsa -b 4096`, convert it with `puttygen ~/.ssh/id_rsa -o ~/.ssh/id_rsa.ppk`, and install the public key on the compute machine with `ssh-copy-id -i ~/.ssh/id_rsa.pub <user>@<IP>`.
- Read the fingerprint with `ssh-keygen -E md5 -l -f <(ssh-keyscan <IP>)` on Linux or `plink.exe -v <IP>` on Windows, and enter the 32-character MD5 string without the `MD5:` prefix.


## Release

Once tested, upload the openrecon bundles to https://webclient.au.api.teamplay.siemens-healthineers.com/ and make them available to all institutes.

