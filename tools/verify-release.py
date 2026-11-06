#!/usr/bin/env python3
"""Audit release integrity, corresponding source, privacy and archive metadata."""
from pathlib import Path, PurePosixPath
import hashlib,json,re,struct,tarfile,zipfile,subprocess
root=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
credential_patterns=[
    rb'\bsk-(?:proj-|svcacct-|ant-)[A-Za-z0-9_-]{20,}',
    rb'\bsk-[A-Za-z0-9]{32,}',
    rb'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}',
    rb'\bgithub_pat_[A-Za-z0-9_]{30,}',
    rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    rb'\bAIza[A-Za-z0-9_-]{35}\b',
    rb'\bxox[baprs]-[A-Za-z0-9-]{20,}',
    rb'\bsk_(?:live|test)_[A-Za-z0-9]{16,}',
    rb'\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{30,}',
    rb'\bhf_[A-Za-z0-9]{30,}',
    rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
    rb'''(?i)(?:api[_-]?key|secret[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token)\s*["']?\s*[:=]\s*["'][A-Za-z0-9_+/=-]{24,}["']''',
]
credential_re=[re.compile(p) for p in credential_patterns]

scanned=0
private_patterns=[rb'/Users/(?!USER/|user/|username/|YOUR_USERNAME/)[A-Za-z0-9_. -]+/']
if Path.home().parent==Path('/Users'):
 private_patterns.append(rb'(?i)\b'+re.escape(Path.home().name.encode())+rb'\b')
private_re=[re.compile(p) for p in private_patterns]
def audit(name,data,upstream=False):
 global scanned
 scanned+=1
 assert not any(p.search(data) for p in credential_re),'Credential marker requires review: '+name
 assert not any(p.search(data) for p in (private_re[1:] if upstream else private_re)),'Personal path/identity marker requires review: '+name
m=json.loads((root/'release/BUILD.json').read_text());assert m['version'] in {'0.1.2','0.1.3'}
path=root/'release'/m['install_zip_name'];assert sha(path.read_bytes())==m['install_zip_sha256']
for line in (root/'release/SHA256SUMS').read_text().splitlines():
 digest,name=line.split('  ',1);assert sha((root/'release'/name).read_bytes())==digest,name
with zipfile.ZipFile(path) as z:
 assert z.testzip() is None and not z.comment
 names=z.namelist();assert sum(n.endswith('/hakux.aarch64') for n in names)==1
 assert {n.split('/')[1] for n in names if n.startswith('Emus/')}=={'XBOX'}
 for name in names:
  rel=PurePosixPath(name);info=z.getinfo(name)
  assert not rel.is_absolute() and '..' not in rel.parts
  assert not any(p in {'mods','profiles','hdd','cache','logs','Screenshots','Roms','.git','__MACOSX'} for p in rel.parts),name
  assert rel.name not in {'.DS_Store','controller-map','render-scale','menu-settings','network-mode','enabled','enabled-cheats','cheats.txt'}
  assert info.date_time==(2026,11,6,0,0,0) and not info.extra and not info.comment
  if name.endswith(('.sh','/hakux.aarch64')):assert info.external_attr>>16&0o111
  audit('install:'+name,z.read(name))
 for name,digest in m['payload_sha256'].items():assert sha(z.read(name))==digest,name
 inner=json.loads(z.read('Data/ports/hakux/BUILD.json'))
 assert all(m[k]==v for k,v in inner.items())
 core=z.read('Data/ports/hakux/hakux.aarch64');assert sha(core)==m['core_sha256']
 assert core[:4]==b'\x7fELF' and struct.unpack_from('<H',core,18)[0]==183
 for marker in [b'GAME SETTINGS:',b'MODS AND CHEATS',b'TAKE SCREENSHOT',b'toggle8',b'CONNECTIONS ON THE NETWORK']:
  assert marker in core
 assert b'SHOW FPS:' not in core and b'CLOSE MAINUI:' not in core
 cfg=json.loads(z.read('Emus/XBOX/config.json'));assert cfg['label']=='Xbox' and cfg['rompath']=='../../Roms/XBOX'
 runner=z.read('Data/ports/hakux/run.sh');assert b'HAKUX_RENDER_SCALE=0.5' in runner and b'"net=$NETWORK"' in runner
 assert b'HAKUX_HLE_QUIRKS=${HAKUX_HLE_QUIRKS:-+eq_depth_step}' in runner
 assert z.read('Data/ports/hakux/runtime-mainui.sh')==(root/'port/platform/mainui-release.sh').read_bytes()
 assert z.read('Data/ports/hakux/runtime-swap.sh')==(root/'port/platform/xbox2-swap.sh').read_bytes()
assert m['automatic_swap']['size_mib']==512 and m['fresh_install_defaults']['lan']=='off'
assert m['menu_extras']['game_specific_files_included'] is False
assert m['controller_mapping']['global'] is False
if m['version']=='0.1.3':
 assert m['halo2_update']=={'texture_limit':768,'upload_arena_mib':32,'readback_buffer_mib':4,'streaming_rearm_limit':8,'published_clock_read_budget':64,'installer_changes_system_swappiness':False}
for report in ['HOST-VALIDATION.json','DEVICE-VALIDATION.json']:
 assert json.loads((root/'release'/report).read_text())['core_sha256']==m['core_sha256']
for name,digest in m['port_source_sha256'].items():assert sha((root/'port'/name).read_bytes())==digest,name
sources=json.loads((root/'sources/SOURCES.json').read_text());entries=0
for item in sources['archives']:
 archive=root/'sources'/item['file'];assert sha(archive.read_bytes())==item['sha256']
 assert m['source_archives'][item['file']]==item['sha256']
 assert archive.stat().st_size==item['archive_bytes']
 with tarfile.open(archive) as tar:
  members=tar.getmembers();assert len(members)==item['source_files']
  for member in members:
   rel=PurePosixPath(member.name)
   assert member.uid==member.gid==0 and member.uname==member.gname=='' and not member.pax_headers
   assert not rel.is_absolute() and '..' not in rel.parts and '.git' not in rel.parts
   assert member.isfile() or member.issym()
   assert not (str(rel).startswith('source/mods/') and str(rel)!='source/mods/README.md'),'Game-specific pack in source archive: '+str(rel)
   if member.isfile():audit(item['file']+':'+member.name,tar.extractfile(member).read(),upstream=True)
   if member.issym():assert not PurePosixPath(member.linkname).is_absolute()
  entries+=len(members)
# Git ignores local build/staging directories; audit the actual upload candidates.
names=set(subprocess.check_output(['git','ls-files','-z'],cwd=root).split(b'\0'))
names.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=root).split(b'\0'))
for encoded in names:
 if not encoded:continue
 rel=Path(encoded.decode());file=root/rel
 if not file.exists():continue
 assert not file.is_symlink() and file.stat().st_size<25*1024*1024,str(rel)
 assert not any(p in {'__MACOSX','.DS_Store','mods','profiles'} or p.startswith('._') for p in rel.parts),str(rel)
 data=file.read_bytes()
 if file.suffix=='.zip':
  with zipfile.ZipFile(file) as archive:
   assert not archive.comment and archive.testzip() is None
   for name in archive.namelist():
    assert not archive.getinfo(name).extra and not archive.getinfo(name).comment
    assert not any(p in {'mods','profiles','hdd','cache','logs','__MACOSX'} for p in PurePosixPath(name).parts)
    audit(str(rel)+':'+name,archive.read(name))
 elif file.suffix!='.gz':audit(str(rel),data)
 if file.suffix=='.png':
  assert data.startswith(b'\x89PNG\r\n\x1a\n');at=8
  while at<len(data):
   n=int.from_bytes(data[at:at+4],'big');assert data[at+4:at+8] in {b'IHDR',b'PLTE',b'tRNS',b'IDAT',b'IEND',b'sRGB'}
   at+=n+12
  assert at==len(data)
print(f'PASS release: payload/source checksums, normalized metadata, preserved-data layout, no game-specific packs; {entries} source entries and {scanned} privacy/credential scans')
