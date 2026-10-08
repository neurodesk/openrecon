import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import uuid
import zipfile

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import validateJson, validate_openrecon_label_metadata

parser = argparse.ArgumentParser()
parser.add_argument('zip', type=Path)
parser.add_argument('--source-image', help='Optional registry-pinned source to compare inherited layers')
args = parser.parse_args()
package = args.zip.resolve()
temporary = tempfile.TemporaryDirectory(prefix='kspacefilter-package-')
extract = Path(temporary.name)
with zipfile.ZipFile(package) as archive:
    names = archive.namelist()
    assert len(names) == 2, names
    assert set(names) == {'OpenRecon_neurodesk_kspacefilter_V0.1.0.tar', 'OpenRecon_neurodesk_kspacefilter_V0.1.0.pdf'}, names
    assert archive.testzip() is None, 'ZIP CRC failure'
    archive.extractall(extract)
pdf = extract / 'OpenRecon_neurodesk_kspacefilter_V0.1.0.pdf'
reader = PdfReader(pdf)
assert reader.pages and all(page.extract_text().strip() for page in reader.pages), 'Empty PDF pages'
pdf_text = '\n'.join(page.extract_text() for page in reader.pages)
for phrase in ('Research only', 'custom ICE adapter', 'has not been supplied or tested on a scanner', 'No native scanner SDK adapter'):
    assert phrase in pdf_text, ('Missing research limitation', phrase)
assert 'Reconstructed images are returned' not in pdf_text

examples = []
for position, character in enumerate(pdf_text):
    if character != '{':
        continue
    try:
        value, end = json.JSONDecoder().raw_decode(pdf_text[position:])
    except ValueError:
        continue
    if isinstance(value, dict) and 'parameters' in value:
        examples.append(value)
expected_examples = [
    {'parameters': {'config': 'kspacefilter'}},
    {'parameters': {'config': 'kspacefilter'}, 'kspacefilter': {
        'mode': 'readout-edge-zero', 'input_domain': 'raw-uniform-cartesian-kspace',
        'measurement_role': 'imaging',
    }},
]
assert examples == expected_examples, ('Incomplete PDF JSON examples', examples)
assert '--experimental-raw-return' in pdf_text
image_tar = extract / 'OpenRecon_neurodesk_kspacefilter_V0.1.0.tar'
with tarfile.open(image_tar) as archive:
    manifest = json.load(archive.extractfile('manifest.json'))
    assert len(manifest) == 1, manifest
    config_bytes = archive.extractfile(manifest[0]['Config']).read()
    config = json.loads(config_bytes)
label_key = 'com.siemens-healthineers.magneticresonance.openrecon.metadata:1.1.0'
label = json.loads(base64.b64decode(config['config']['Labels'][label_key]))
assert label['general']['id'] == 'kspacefilter' and label['general']['version'] == '0.1.0', label
assert label['reconstruction']['emitter'] == label['reconstruction']['injector'] == 'raw', label
assert label['reconstruction']['content_qualification_type'] == 'RESEARCH', label
validate_openrecon_label_metadata(label)
label_path = extract / 'label.json'
label_path.write_text(json.dumps(label))
assert validateJson(label_path, Path(__file__).resolve().parents[1] / 'OpenReconSchema_1.1.0.json', experimental_raw_return=True)
if args.source_image:
    assert '@sha256:' in args.source_image, 'Source image must be digest pinned'
    source = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.source_image], text=True))[0]
    assert config['rootfs']['diff_ids'] == source['RootFS']['Layers'], 'Wrapper changed runtime filesystem'
    assert config['config'].get('Entrypoint') == source['Config'].get('Entrypoint'), 'Wrapper changed inherited entrypoint'
assert 'python-ismrmrd-server/main.py' in config['config']['Cmd'][-1], config['config']
subprocess.run(['docker', 'load', '-i', str(image_tar)], check=True)
image = manifest[0]['RepoTags'][0]
smoke_container = 'kspacefilter-smoke-' + uuid.uuid4().hex
try:
    case = subprocess.run(['docker', 'run', '--name', smoke_container, '--rm', '--network', 'none', image,
                           'bash', '-lc', 'python /opt/code/python-ismrmrd-server/smoke_kspacefilter.py --server /opt/code/python-ismrmrd-server'],
                          capture_output=True, text=True, timeout=90)
    assert case.returncode == 0, (case.stdout, case.stderr)
finally:
    subprocess.run(['docker', 'rm', '-f', smoke_container], capture_output=True)
client_code = """
import json, socket, sys, time
import ismrmrd
sys.path.insert(0, '/opt/code/python-ismrmrd-server')
from connection import Connection
from smoke_kspacefilter import acquisition, metadata, check
for attempt in range(100):
    try:
        with socket.create_connection(('127.0.0.1',9002),timeout=.2):
            break
    except OSError:
        time.sleep(.1)
else:
    raise RuntimeError('Packaged default startup did not open MRD port')
masked_config = json.loads(sys.argv[1])
for config,filtered in (({'parameters':{'config':'kspacefilter'}},False),(masked_config,True)):
    with socket.create_connection(('127.0.0.1',9002),timeout=10) as sock:
        client=Connection(sock,False)
        client.send_config_file('openrecon')
        client.send_metadata(ismrmrd.xsd.ToXML(metadata()))
        client.send_text(json.dumps(config))
        before=acquisition()
        client.send_acquisition(before)
        check(before,next(client),filtered)
        client.send_close()
        assert next(client) is None
print('PASS default packaged startup, unchanged and filtered acquisitions before EOF')
"""
container = subprocess.check_output(['docker','run','--rm','-d','--network','none',image],text=True).strip()
try:
    config_text = Path(__file__).with_name('wip_070_fire_kspacefilter.json').read_text()
    startup = subprocess.run(['docker','exec',container,'python','-c',client_code,config_text],capture_output=True,text=True,timeout=40)
    assert startup.returncode == 0,(startup.stdout,startup.stderr)
finally:
    subprocess.run(['docker','rm','-f',container],check=True,capture_output=True)
print('PASS archive CRC/inventory, raw/raw RESEARCH metadata, PDF examples/limitations, full MRD smoke and default startup before EOF')
digest = hashlib.sha256()
with package.open('rb') as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
print(json.dumps({'sha256': digest.hexdigest(), 'image': image, 'source_layers_checked': bool(args.source_image)}))
temporary.cleanup()
