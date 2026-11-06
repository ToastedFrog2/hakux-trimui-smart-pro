#!/usr/bin/env python3
"""Build the v0.1.2 installer from the retained v0.1.1 runtime and current core."""
from pathlib import Path
import argparse,hashlib,json,struct,zipfile
r=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--core',type=Path,required=True)
p.add_argument('--output',type=Path,default=r/'release/xbox-trimui-smart-pro-v0.1.2.zip')
a=p.parse_args();sha=lambda b:hashlib.sha256(b).hexdigest();app='Data/ports/hakux/'
core=a.core.read_bytes()
assert core[:4]==b'\x7fELF' and struct.unpack_from('<H',core,18)[0]==183
assert b'/Users/' not in core and b'SHOW FPS:' not in core
for marker in [b'GAME SETTINGS:',b'MODS AND CHEATS',b'TAKE SCREENSHOT',b'toggle8',b'CONNECTIONS ON THE NETWORK']:
 assert marker in core
with zipfile.ZipFile(r/'release/xbox-trimui-smart-pro-v0.1.1.zip') as z:
 assert z.testzip() is None;payload={n:z.read(n) for n in z.namelist()}
m=json.loads(payload.pop(app+'BUILD.json'))
payload[app+'hakux.aarch64']=core
runner=(r/'port/package/hakux/run.sh').read_text()
runner=runner.replace('mkdir -p cache hdd logs','if [ -z "${HAKUX_RENDER_SCALE:-}" ]; then export HAKUX_RENDER_SCALE=0.5; fi\nmkdir -p cache hdd logs')
runner=runner.replace(': > "$APP/log.txt"',': > "$APP/log.txt"\nif [ -r "$APP/runtime-swap.sh" ]; then . "$APP/runtime-swap.sh"; fi')
payload[app+'run.sh']=runner.encode()
payload[app+'runtime-mainui.sh']=(r/'port/platform/mainui-release.sh').read_bytes()
payload[app+'README.txt']=b'''hakuX for the original TrimUI Smart Pro (TG5040) - v0.1.2

Copy Data and Emus to the SD card root, merging folders with the game closed.
Put your own Xbox images in Roms/XBOX. Saves, caches and existing choices
are preserved. No game files, BIOS, saves, profiles or cheat/mod packs are
included. This is experimental software; compatibility and speed vary.

Menu opens settings; B returns/resumes. Hold Start + Select about 1.2 seconds
to exit. Controls, picture options, frame skip, scale and LAN save per game
and certificate version under profiles/TITLEID.VERSION. Existing global
files remain the defaults until a game has its own override. Fresh installs
use the original controls, 0.5x scale, frame skip Off and LAN Off.

Scale and LAN changes require Apply settings and restart game; save first.
LAN: Connections on the network exposes the Ethernet-over-UDP tunnel for
local System Link. Matching versions and UDP 3075 are required. Two-console
gameplay is unverified; Xbox Live and direct physical-Xbox bridging are not
provided. See docs/LAN.md in the repository.

Mods and Cheats supports user-supplied, version-matched files. No codes are
bundled or downloaded automatically. Mods require a restart; runtime cheats
apply on resume. toggle8 restores its previous flag value when disabled;
ordinary writes and gameplay/save changes may require a reload to undo.

Take Screenshot saves an opaque PNG to Screenshots/XBOX on the SD card.
The overlay is hidden for capture. The original firmware fbscreencap tool
is required. RGB pixels are preserved and unused alpha/metadata discarded.

MainUI and OSD close during gameplay and return on exit. musicserver pauses
and resumes; its allocated RAM remains. Automatic shared 512 MiB swap uses
eligible internal ext4 storage with at least 1 GiB free before allocation.
Create disable-swap to opt out. Swap does not guarantee higher FPS.

PowerVR eq_depth_step remains enabled. Rendering faults, compilation pauses,
loading blockers, thermal slowdown and crashes remain possible. No universal
30 FPS guarantee. See README and docs for build instructions and limitations.
'''
m.update(version='0.1.2',package_revision='per-game-menu-1',core_build='per-game-menu-opaque-capture',
 core_sha256=sha(core),core_changed=True,device_tested_core=False,device_smoke_tested=False,
 install_zip_name=a.output.name,validation='Host regressions passed; prior per-game core has device menu/gameplay reports; final capture correction is host-tested')
m['fresh_install_defaults']['lan']='off'
m['controller_mapping'].update({'global':False,'scope':'title ID and certificate version','file':'profiles/TITLEID.VERSION/controller-map'})
m['lan']={'available':True,'default':'off','modes':['off','lan'],'label':'LAN: Connections on the network','restart_required':True,'udp_port':3075,'two_console_gameplay_tested':False}
m['per_game_settings']={'key':'title_id.certificate_version','directory':'profiles','legacy_files':'preserved inherited defaults','settings':['controller-map','menu-settings','render-scale','network-mode']}
m['menu_extras']={'mods':True,'runtime_cheats':True,'game_specific_files_included':False,'new_entries_default':'off','mod_changes_restart_required':True,'screenshots':'Screenshots/XBOX','screenshot_format':'opaque RGB PNG; RGB preserved; metadata removed'}
m['device_validation']={'core_sha256':sha(core),'tests':{},'tested_base_core_sha256':'b689bf6e29b374f803800c864d640d1a4478d1187aa5da157464529fa8e8e975',
 'base_core_checks':['Halo CE boot, per-game profile display and settings write','User reports working Halo 2 gameplay and menu','Framebuffer screenshot capture, followed by host alpha correction'],
 'limits':['Final screenshot normalization is host-tested; this exact rebuilt core has not been gameplay-tested','Two-console System Link gameplay is unverified','Long-session stability and all-game compatibility are not established']}
m['graphics_workaround']['activation']='PowerVR core default and launcher environment; explicit override respected'
m['source_archives']={entry['file']:entry['sha256'] for entry in json.loads((r/'sources/SOURCES.json').read_text())['archives']}
m['port_source_sha256']={str(f.relative_to(r/'port')):sha(f.read_bytes()) for f in (r/'port').rglob('*') if f.is_file() and f.suffix in {'.c','.h','.inc','.py','.sh','.cmake'} and not any(v in {'source','deps','build','dist','__pycache__'} for v in f.relative_to(r/'port').parts)}
m['payload_sha256']={n:sha(b) for n,b in sorted(payload.items())}
for key in ['install_zip_sha256','install_zip_bytes']:m.pop(key,None)
payload[app+'BUILD.json']=(json.dumps(m,indent=2)+'\n').encode()
a.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(a.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name,data in sorted(payload.items()):
  assert not any(part in {'mods','profiles','hdd','cache','logs','Screenshots','.git','__MACOSX'} for part in Path(name).parts)
  assert Path(name).name not in {'controller-map','menu-settings','render-scale','network-mode','enabled','enabled-cheats','.DS_Store'}
  info=zipfile.ZipInfo(name,(2026,11,6,0,0,0));info.create_system=3
  info.external_attr=(0o100000|(0o755 if name.endswith(('.sh','/hakux.aarch64')) else 0o644))<<16
  info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
m.update(install_zip_sha256=sha(a.output.read_bytes()),install_zip_bytes=a.output.stat().st_size)
(r/'release/BUILD.json').write_text(json.dumps(m,indent=2)+'\n')
(r/'release/DEVICE-VALIDATION.json').write_text(json.dumps(m['device_validation'],indent=2)+'\n')
host={'core_sha256':sha(core),'host_tests':{'profiles':'Actual XDVDFS identity, certificate-version isolation, inherited defaults, scale/LAN validation and descriptor ownership',
 'menu':'Actual navigation, pause/resume, remapping, per-game persistence, bounded rendering and confirmed restart',
 'native_cheats':'Original engine regressions plus guarded toggle8 restoration, unmapped memory and existing-state preservation under sanitizers',
 'screenshot':'Actual asynchronous request and PNG normalization: RGB/RGBA, all five filters, exact RGB, opaque output, metadata removal, malformed rejection under sanitizers',
 'vcpu_safety':'Actual time expiry, copied-buffer protection and common MMIO path; faulty variants reproduce the prior failures',
 'source_correspondence':'Full clean source plus patches matches the build inputs; applying all patches twice is idempotent'},'limits':m['device_validation']['limits']}
(r/'release/HOST-VALIDATION.json').write_text(json.dumps(host,indent=2)+'\n')
files=[a.output,r/'release/BUILD.json',r/'release/HOST-VALIDATION.json',r/'release/DEVICE-VALIDATION.json']
(r/'release/SHA256SUMS').write_text(''.join(sha(f.read_bytes())+'  '+f.name+'\n' for f in files))
print('Packaged '+a.output.name+'; no game-specific files, saved choices or personal data included')
