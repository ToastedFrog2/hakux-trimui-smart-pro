#!/usr/bin/env python3
"""Package the depth-workaround and music-service update around the v0.1 core."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-package', type=Path,
                    default=root/'release/xbox-trimui-smart-pro-2026.10.30.zip')
parser.add_argument('--output', type=Path,
                    default=root/'release/xbox-trimui-smart-pro-v0.1.1.zip')
args = parser.parse_args()
sha = lambda data: hashlib.sha256(data).hexdigest()
app = 'Data/ports/hakux/'
with zipfile.ZipFile(args.base_package) as archive:
    assert archive.testzip() is None
    payload = {name: archive.read(name) for name in archive.namelist()}
manifest = json.loads(payload.pop(app+'BUILD.json'))
core = payload[app+'hakux.aarch64']
assert sha(core) == manifest['core_sha256'] == '04b9f20f6de5cc481ed0b15e8311fadde49cb3422277131cc9d80bf5dadf6a55'
assert b'eq_depth_step' in core
launcher = (root/'port/package/hakux/run.sh').read_text()
launcher = launcher.replace('mkdir -p cache hdd logs',
    'if [ -z "${HAKUX_RENDER_SCALE:-}" ]; then export HAKUX_RENDER_SCALE=0.5; fi\nmkdir -p cache hdd logs')
launcher = launcher.replace(': > "$APP/log.txt"',
    ': > "$APP/log.txt"\nif [ -r "$APP/runtime-swap.sh" ]; then . "$APP/runtime-swap.sh"; fi')
assert launcher.count('HAKUX_HLE_QUIRKS=${HAKUX_HLE_QUIRKS:-+eq_depth_step}') == 1
payload[app+'run.sh'] = launcher.encode()
payload[app+'runtime-mainui.sh'] = (root/'port/platform/mainui-release.sh').read_bytes()
readme = payload[app+'README.txt'].decode()
readme = readme.replace('persistent black textures\nare not fixed by this release.',
    'the PowerVR depth workaround targets Halo 2 black level geometry,\nbut other missing textures and rendering faults remain possible.')
readme = readme.replace('Details: docs/INSTALL.md in the\nrepository.', 'See the repository README for installation details.')
readme += '''
v0.1.1 runtime update: the launcher enables the existing eq_depth_step
workaround by default on this PowerVR target. The emulator core is unchanged
from v0.1; no new core build is required. An explicit HAKUX_HLE_QUIRKS
environment setting is respected. Use -eq_depth_step to disable the workaround.
Halo 2 can still show rectangular shadow/lighting patches around moving
objects; the experimental square/speckle tests are not included.
The firmware musicserver is paused during gameplay to stop background CPU
use, then resumed after the OSD returns. Pausing does not release its RAM.
Session ownership and process start times prevent stale recovery from
resuming a newer session or an unrelated process with a reused PID.
'''
payload[app+'README.txt'] = readme.encode()
manifest.update(version='0.1.1', package_revision='runtime-depth-music-1',
    install_zip_name=args.output.name,
    graphics_workaround={'name': 'eq_depth_step', 'default': True,
        'activation': 'launcher environment; existing v0.1 core implementation',
        'external_override_respected': True,
        'scope': 'PowerVR target; Halo 2 black level geometry and lighting passes'},
    core_changed=False,
    validation='Unchanged v0.1 core; see HOST-VALIDATION.json and DEVICE-VALIDATION.json for runtime-update checks')
manifest['known_issues'].append('Halo 2 rectangular shadow/lighting patches around moving objects')
manifest['mainui_release']['services'] = ['MainUI', 'trimui_osdd', 'musicserver']
manifest['mainui_release']['musicserver_mode'] = 'pause during gameplay; resume after OSD restoration'
manifest['mainui_release']['musicserver_pid_reuse_protection'] = True
manifest['mainui_release']['musicserver_memory_released'] = False
manifest['device_validation'] = json.loads((root/'release/DEVICE-VALIDATION.json').read_text())
manifest['port_source_sha256'] = {
    str(path.relative_to(root/'port')): sha(path.read_bytes())
    for path in (root/'port').rglob('*')
    if path.is_file() and path.suffix in {'.c', '.h', '.inc', '.py', '.sh', '.cmake'}
    and not any(part in {'source', 'deps', 'build', 'dist', '__pycache__'}
                for part in path.relative_to(root/'port').parts)}
manifest['payload_sha256'] = {name: sha(data) for name, data in sorted(payload.items())}
for key in ['install_zip_sha256', 'install_zip_bytes']:
    manifest.pop(key, None)
payload[app+'BUILD.json'] = (json.dumps(manifest, indent=2, ensure_ascii=False)+'\n').encode()
args.output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name, data in sorted(payload.items()):
        info = zipfile.ZipInfo(name, date_time=(2026, 11, 3, 0, 0, 0))
        info.create_system = 3
        mode = 0o755 if name.endswith('.sh') or name.endswith('/hakux.aarch64') else 0o644
        info.external_attr = (0o100000 | mode) << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, data)
manifest.update(install_zip_sha256=sha(args.output.read_bytes()),
                install_zip_bytes=args.output.stat().st_size)
build = args.output.parent/'BUILD.json'
build.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
(args.output.parent/'SHA256SUMS').write_text(''.join(
    sha(path.read_bytes())+'  '+path.name+'\n' for path in [args.output, build]))
print(f'Packaged {args.output.name}; exact v0.1 core retained; no saves, cache or settings included')
