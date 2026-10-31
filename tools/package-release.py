#!/usr/bin/env python3
"""Package a supplied ARM64 core; no network, credentials or device access."""
from pathlib import Path
import argparse, hashlib, json, struct, zipfile
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--binary',required=True,type=Path)
p.add_argument('--output',type=Path,default=root/'release/xbox-trimui-smart-pro-2026.10.30.zip')
p.add_argument('--source-root',type=Path,default=root/'port',help='Root containing unpacked source/ and deps/')
p.add_argument('--frame-skip-preview',action='store_true',help='Label the new menu/presenter build as host-tested preview')
p.add_argument('--named-directory-fix',action='store_true',help='Package the verified Xbox Win32 named-directory fix')
p.add_argument('--scale075-preview',action='store_true',help='Package the host-checked 0.75x scale addition')
a=p.parse_args()
assert sum([a.frame_skip_preview,a.named_directory_fix,a.scale075_preview])<=1,'Choose one release profile'
tested='893afce7818b68d294f7ff3258400fd0dc6120c7698d8be0df109d6ef4bdcab2'
sha=lambda b:hashlib.sha256(b).hexdigest()
binary=a.binary.read_bytes()
assert binary[:4]==b'\x7fELF' and binary[4:6]==b'\x02\x01' and struct.unpack_from('<H',binary,18)[0]==183,'Expected 64-bit little-endian AArch64 ELF'
is_tested=sha(binary)==tested
has_frame_skip=b'FRAME SKIP: %s' in binary and b'SKIP 1 (DISPLAY)' in binary
assert b'SHOW FPS:' not in binary,'FPS overlay must be absent from this release'
has_mapping=b'XBOX - CONTROLLER MAPPING' in binary
has_mainui=(root/'port/platform/mainui-release.sh').is_file()
device_evidence={}
if a.frame_skip_preview or a.named_directory_fix or a.scale075_preview:
    assert b'FRAME SKIP: %s' in binary and b'SKIP 1 (DISPLAY)' in binary
    assert not is_tested
    evidence=json.loads((root/'release/HOST-VALIDATION.json').read_text())
    assert evidence['core_sha256']==sha(binary),'Run and record host validation for the selected core'
if a.scale075_preview:
    assert b'0.75X' in binary and b'\\Win32NamedObjects\\' in binary
    assert evidence['host_tests']['scale075']
    device_evidence=json.loads((root/'release/DEVICE-VALIDATION.json').read_text())
    assert device_evidence['core_sha256']==sha(binary)
if a.named_directory_fix:
    assert b'\\Win32NamedObjects\\' in binary
    assert evidence['host_tests']['named_directory']
    device_evidence=json.loads((root/'release/DEVICE-VALIDATION.json').read_text())
    assert device_evidence['core_sha256']==sha(binary)
    assert device_evidence['tests']['halo_ce_startup_passed']
    is_tested=True
version='2026.10.30-controller-map' if has_mapping else '2026.10.30-auto-ui' if has_mainui and a.scale075_preview else '2026.10.30-scale075-preview' if a.scale075_preview else '2026.10.30-named-directory-fix' if a.named_directory_fix else '2026.10.29-frameskip-preview' if a.frame_skip_preview else '2026.10.29' if is_tested else 'local-rebuild'
sources=json.loads((root/'sources/SOURCES.json').read_text())
files={};app='Data/ports/hakux/'
files[app+'hakux.aarch64']=(binary,0o755)
launcher=(root/'port/package/hakux/run.sh').read_text()
needle='mkdir -p cache hdd logs'
assert launcher.count(needle)==1
launcher=launcher.replace(needle,'if [ -z "${HAKUX_RENDER_SCALE:-}" ]; then export HAKUX_RENDER_SCALE=0.5; fi\n'+needle)
needle=': > "$APP/log.txt"';assert launcher.count(needle)==1
launcher=launcher.replace(needle,needle+'\nif [ -r "$APP/runtime-swap.sh" ]; then . "$APP/runtime-swap.sh"; fi')
files[app+'run.sh']=(launcher.encode(),0o755)
if has_mainui:files[app+'runtime-mainui.sh']=((root/'port/platform/mainui-release.sh').read_bytes(),0o755)
files[app+'runtime-swap.sh']=((root/'port/platform/xbox2-swap.sh').read_bytes(),0o755)
files['Data/ports/hakux-disc.sh']=((root/'port/platform/disc-container.sh').read_bytes(),0o755)
config=json.loads((root/'port/package/XBOX/config.json').read_text())
config.update(label='Xbox',iconsmall='iconsmall.png')
assert config['rompath']=='../../Roms/XBOX'
files['Emus/XBOX/config.json']=((json.dumps(config,indent=2)+'\n').encode(),0o644)
files['Emus/XBOX/launch.sh']=(b'#!/bin/sh\nexec /bin/sh /mnt/SDCARD/Data/ports/hakux-disc.sh /mnt/SDCARD/Data/ports/hakux/run.sh "$@"\n',0o755)
icon=(root/'port/package/XBOX/icon.png').read_bytes()
for name in ['icon.png','iconsmall.png']:files['Emus/XBOX/'+name]=(icon,0o644)
for name in ['LICENSE','COPYING']:
    files[app+'licenses/hakuX-'+name]=((a.source_root/'source'/name).read_bytes(),0o644)
for path in sorted((a.source_root/'source/licenses').glob('*.txt')):
    files[app+'licenses/'+path.name]=(path.read_bytes(),0o644)
for component,name in [('SDL2','LICENSE.txt'),('zlib','LICENSE')]:
    files[app+'licenses/'+component+'-LICENSE.txt']=((a.source_root/'deps'/component/name).read_bytes(),0o644)
readme='''Xbox for the original TrimUI Smart Pro TG5040

Install Data/ and Emus/ into the SD card root, merging folders. Games go in
Roms/XBOX. PortMaster is not required. Default scale on a fresh install is 0.5x.
Existing saves, caches, scale, picture and swap settings are not in this payload.
Menu opens settings; hold Start+Select about 1.2 seconds to exit.
Scale changes require Apply scale and restart; save in-game first.

Experimental: missing/black textures, slowdowns, crashes and driver stalls
remain possible. First-run shaders can stutter; persistent black textures
are not fixed by this release. No guaranteed 30 FPS or all-game compatibility.
Swap is automatic for all games: existing configured/system swap is reused;
otherwise 512 MiB is created on writable internal ext4 with at least 1 GiB
free before allocation. First launch may take longer. Existing files/settings
are preserved; setup failures are logged and do not stop the game. Create
disable-swap in the app folder to opt out. Details: docs/INSTALL.md in the
repository. No games, BIOS, saves, swap file or shader cache are bundled.

Based on rfandango/hakuX; matching modified source is in sources/ in the
accompanying repository. License texts are in licenses/. Preserve attribution.
'''
files[app+'README.txt']=(readme.encode(),0o644)
if has_frame_skip:
    if a.frame_skip_preview:
        readme='FRAME-SKIP PREVIEW — host-tested, not yet tested on the handheld.\n\n'+readme
    if a.named_directory_fix:
        readme='XBOX NAMED-DIRECTORY FIX — see repository compatibility notes for limited device tests.\n\n'+readme
    if a.scale075_preview:
        readme=('AUTOMATIC MAINUI + OSD MEMORY RELEASE' if has_mainui else '0.75X SCALE PREVIEW')+' — see repository for limited device test results.\n\n'+readme
        readme+='\nMenu render scales: 0.35x / 0.5x / 0.75x / 1x. Apply scale and restart\nto change resolution. 0.75x is sharper than 0.5x and can be slower.\n'
    readme+='\nMenu → Frame skip: Off / Skip 1 (Display). Changes apply live and persist.\nThis skips alternate display updates, preserving all guest drawing/timing.\nMenus always update normally. This is not a texture fix or FPS guarantee.\n'
    if has_mainui:
        readme+='\nMainUI and the TrimUI OSD close automatically for Xbox games and return on\nexit. No menu toggle or setup is required. An independent guard restores\nthem if the launcher dies. Linux, networking and input remain running.\n'
    if has_mapping:
        readme+='\nMenu > Controller Mapping: Up/Down selects an Xbox action; Left/Right or A\nchanges its physical input. B returns, Menu resumes. Changes persist for all\ngames in controller-map. Reset to defaults restores the original layout.\nPhysical Menu, menu navigation and Start + Select to exit remain fixed.\n'
    if has_mapping:
        readme+='\nFresh installs use default controls: L3/R3 are Xbox stick clicks. No saved\ncontroller-map, menu-settings or render-scale file is bundled. Existing\nsettings on an updated card are preserved; use Controller Mapping > Reset\nto defaults to clear a previous layout. The FPS overlay has been removed.\n'
    files[app+'README.txt']=(readme.encode(),0o644)
manifest={'name':'hakuX for TrimUI Smart Pro — Xbox','version':version,
 'core_build':'2026-10-30-controller-map-1' if has_mapping else '2026-10-30-scale075-1' if a.scale075_preview else '2026-10-30-named-directory-1' if a.named_directory_fix else '2026-10-29-frame-skip-preview-1' if a.frame_skip_preview else '2026-10-29-named-objects-save-1' if is_tested else 'local-rebuild',
 'core_sha256':sha(binary),'hardware':'original TrimUI Smart Pro TG5040 / Cortex-A53 / PowerVR GE8300 / 1 GiB RAM',
 'default_render_scale':0.5,'device_tested_core':is_tested,
 'device_smoke_tested':bool(device_evidence.get('tests',{}).get('controller_mapping_menu_display') or device_evidence.get('tests',{}).get('scale075_menu_and_render_size_passed')),
 'package_revision':'controller-map-1' if has_mapping else 'auto-ui-1' if has_mainui else 'scale075-preview-1' if a.scale075_preview else 'named-directory-1' if a.named_directory_fix else 'frame-skip-preview-1' if a.frame_skip_preview else 'automatic-swap-1',
 'fresh_install_defaults':{'render_scale':0.5,'controller_mapping':'identity; L3 and R3 are Xbox stick clicks','frame_skip':'off','aspect':'auto','upscale':'bilinear','fxaa':'off','color':'original','saved_settings_bundled':False},
 'controller_mapping':{'available':has_mapping,'global':True,'live_on_resume':True,'persisted':True,'file':'controller-map','fixed_menu_and_exit_shortcuts':True},
 'mainui_release':{'available':has_mainui,'default':True,'menu_option':False,'services':['MainUI','trimui_osdd'],'applies':'each game launch','automatic_menu_restore':True,'launcher_death_guard':True,'session_ownership':True},
 'render_scales':[0.35,0.5,0.75,1] if a.scale075_preview else [0.35,0.5,1],
 'frame_skip':{'available':has_frame_skip,'modes':['off','skip1-display'] if has_frame_skip else [],'default':'off','live':True,'persisted':True,'device_tested':False},
 'automatic_swap':{'shared':True,'size_mib':512,'minimum_free_mib':1024,'filesystem':'internal writable ext4','existing_configuration_preserved':True,'creation_device_tested':False},
 'validation': '0.75x geometry/options/copies, 48 generated Vulkan shaders and menu/launcher host checks passed; see DEVICE-VALIDATION.json for limited device observations' if a.scale075_preview else 'Xbox Win32 named-directory host checks passed; limited handheld tests recorded in DEVICE-VALIDATION.json; long-session compatibility unverified' if a.named_directory_fix else 'Host ASan/UBSan menu and real presenter checks passed; handheld validation pending' if a.frame_skip_preview else 'Chicago Enforcer gameplay confirmed; other game and stability limits described in docs/COMPATIBILITY.md' if is_tested else 'Local rebuild; device validation required',
 'device_validation':device_evidence,
 'known_issues':['Halo 2 black/missing textures','game-specific performance and compatibility','possible memory/GPU freezes'],
 'source_archives':{e['file']:e['sha256'] for e in sources['archives']},
 'port_source_sha256':{str(p.relative_to(root/'port')):sha(p.read_bytes()) for p in (root/'port').rglob('*') if p.is_file() and p.suffix in {'.c','.h','.inc','.py','.sh','.cmake'} and not any(part in {'source','deps','build','dist','__pycache__'} for part in p.relative_to(root/'port').parts)},
 'payload_sha256':{name:sha(value[0]) for name,value in sorted(files.items())}}
files[app+'BUILD.json']=((json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode(),0o644)
a.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(a.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name,(data,mode) in sorted(files.items()):
        info=zipfile.ZipInfo(name,date_time=(2026,10,30,0,0,0) if a.named_directory_fix or a.scale075_preview else (2026,10,29,0,0,0));info.create_system=3
        info.external_attr=(0o100000|mode)<<16;info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,data)
manifest['install_zip_sha256']=sha(a.output.read_bytes())
manifest['install_zip_bytes']=a.output.stat().st_size
mp=a.output.parent/'BUILD.json';mp.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
(a.output.parent/'SHA256SUMS').write_text(''.join(sha(f.read_bytes())+'  '+f.name+'\n' for f in [a.output,mp]))
print(f'Packaged {a.output.name}: {a.output.stat().st_size/1048576:.2f} MiB; tested core={is_tested}')
