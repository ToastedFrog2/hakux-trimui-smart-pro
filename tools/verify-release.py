#!/usr/bin/env python3
"""Verify public release integrity, layout and normalized archive metadata."""
from pathlib import Path, PurePosixPath
import hashlib, json, re, struct, tarfile, zipfile
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
def check_credentials(name,data):
    global scanned
    scanned+=1
    # Only the path is reported; never print a matching value.
    assert not any(p.search(data) for p in credential_re),'Possible credential requires review: '+name
manifest=json.loads((root/'release/BUILD.json').read_text())
zip_path=root/'release/xbox-trimui-smart-pro-2026.10.30.zip'
assert sha(zip_path.read_bytes())==manifest['install_zip_sha256']
for line in (root/'release/SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1)
    assert sha((root/'release'/name).read_bytes())==digest,name
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
    names=set(z.namelist())
    assert not any(n.startswith(('Data/ports/hakux2/','Emus/XBOX2/','Roms/')) for n in names)
    assert {n.split('/')[1] for n in names if n.startswith('Emus/')}=={'XBOX'}
    assert sum(n.endswith('/hakux.aarch64') for n in names)==1
    assert manifest['package_revision'] in {'automatic-swap-1','frame-skip-preview-1','named-directory-1','scale075-preview-1','auto-ui-1','controller-map-1'}
    assert manifest['automatic_swap']['size_mib']==512
    for n in names:
        check_credentials('install ZIP:'+n,z.read(n))
        assert not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts
        assert not any(p in {'hdd','cache','logs','__MACOSX','.git'} for p in PurePosixPath(n).parts)
        assert PurePosixPath(n).name not in {'render-scale','swap-file','picture-settings','menu-settings','controller-map','controller-map.tmp','.DS_Store'}
        info=z.getinfo(n)
        expected_time=(2026,10,30,0,0,0) if manifest['package_revision'] in {'named-directory-1','scale075-preview-1','auto-ui-1','controller-map-1'} else (2026,10,29,0,0,0)
        assert info.date_time==expected_time and not info.extra and not info.comment
        if n.endswith('.sh'):assert info.external_attr>>16&0o111
    if manifest['package_revision'] in {'auto-ui-1','controller-map-1'}:
        assert z.read('Data/ports/hakux/runtime-mainui.sh')==(root/'port/platform/mainui-release.sh').read_bytes()
        assert manifest['mainui_release']['default'] is True
        assert manifest['mainui_release']['menu_option'] is False
    if manifest['package_revision'] in {'controller-map-1'}:
        assert manifest['controller_mapping']['available'] and manifest['controller_mapping']['fixed_menu_and_exit_shortcuts']
        assert b'XBOX - CONTROLLER MAPPING' in z.read('Data/ports/hakux/hakux.aarch64')
        assert b'hakux-ui-owner' in z.read('Data/ports/hakux/runtime-mainui.sh')
    b=z.read('Data/ports/hakux/hakux.aarch64')
    if manifest['package_revision'] in {'auto-ui-1','controller-map-1'}:assert b'CLOSE MAINUI:' not in b
    assert b'SHOW FPS:' not in b
    assert sha(b)==manifest['core_sha256']
    if manifest['package_revision'] in {'frame-skip-preview-1','named-directory-1','scale075-preview-1','auto-ui-1','controller-map-1'}:
        if manifest['package_revision']=='frame-skip-preview-1':assert not manifest['device_tested_core']
        assert manifest['frame_skip']['default']=='off' and manifest['frame_skip']['live']
        assert b'FRAME SKIP: %s' in b and b'SKIP 1 (DISPLAY)' in b
        host=json.loads((root/'release/HOST-VALIDATION.json').read_text())
        assert host['core_sha256']==sha(b)
        if manifest['package_revision'] in {'scale075-preview-1','auto-ui-1','controller-map-1'}:
            assert b'0.75X' in b and host['host_tests']['scale075']
            assert manifest['render_scales']==[0.35,0.5,0.75,1]
            assert b'0.35|0.5|0.75|1' in z.read('Data/ports/hakux/run.sh')
            device=json.loads((root/'release/DEVICE-VALIDATION.json').read_text())
            assert device==manifest['device_validation'] and device['core_sha256']==sha(b)
        if manifest['package_revision']=='named-directory-1':
            device=json.loads((root/'release/DEVICE-VALIDATION.json').read_text())
            assert device==manifest['device_validation'] and device['core_sha256']==sha(b)
            assert device['tests']['halo_ce_startup_passed']
            assert b'\\Win32NamedObjects\\' in b and host['host_tests']['named_directory']
    else:
        assert sha(b)=='893afce7818b68d294f7ff3258400fd0dc6120c7698d8be0df109d6ef4bdcab2'
    assert b[:4]==b'\x7fELF' and struct.unpack_from('<H',b,18)[0]==183
    for n,digest in manifest['payload_sha256'].items():assert sha(z.read(n))==digest,n
    cfg=json.loads(z.read('Emus/XBOX/config.json'))
    assert cfg['label']=='Xbox' and cfg['rompath']=='../../Roms/XBOX'
    launcher=z.read('Data/ports/hakux/run.sh')
    assert b'HAKUX_RENDER_SCALE=0.5' in launcher and b'runtime-swap.sh' in launcher
    swap=z.read('Data/ports/hakux/runtime-swap.sh')
    assert swap==(root/'port/platform/xbox2-swap.sh').read_bytes()
    assert b'count=512' in swap and b'disable-swap' in swap and b'ln -T' in swap
    assert b'/Users/' not in launcher and not re.search(rb'\b192\.168\.\d+\.\d+\b',launcher)
    for n in ['Emus/XBOX/icon.png','Emus/XBOX/iconsmall.png']:
        data=z.read(n);pos=8
        while pos<len(data):
            length=int.from_bytes(data[pos:pos+4],'big');kind=data[pos+4:pos+8]
            assert kind not in {b'tEXt',b'zTXt',b'iTXt',b'eXIf',b'tIME',b'iCCP'}
            pos+=length+12
sources=json.loads((root/'sources/SOURCES.json').read_text())
for name,digest in manifest.get('port_source_sha256',{}).items():
    assert sha((root/'port'/name).read_bytes())==digest,name
count=0
for e in sources['archives']:
    p=root/'sources'/e['file'];assert sha(p.read_bytes())==e['sha256']
    assert p.stat().st_size<25*1024*1024
    with tarfile.open(p,'r:gz') as tar:
        members=tar.getmembers();assert len(members)==e['source_files']
        for m in members:
            if m.isfile():check_credentials(e['file']+':'+m.name,tar.extractfile(m).read())
            assert m.uid==m.gid==0 and m.uname==m.gname=='' and not m.pax_headers
            assert '.git' not in PurePosixPath(m.name).parts
            assert not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts
            assert m.isfile() or m.issym()
            if m.issym():assert not PurePosixPath(m.linkname).is_absolute()
        count+=len(members)
files=[p for p in root.rglob('*') if p.is_file() and not any(part in {'.git','__pycache__'} for part in p.relative_to(root).parts)]
fallback=root/'release/known-working-named-directory'
if fallback.exists():
    prior=json.loads((fallback/'BUILD.json').read_text())
    for line in (fallback/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);assert sha((fallback/name).read_bytes())==digest,name
    with zipfile.ZipFile(fallback/'xbox-trimui-smart-pro-2026.10.30.zip') as z:
        assert z.testzip() is None
        assert sha(z.read('Data/ports/hakux/hakux.aarch64'))==prior['core_sha256']=='0fa36241953deff7755ff570f99b7ef5a43171fda540b059b365f7df6c602e6a'
        for n in z.namelist():check_credentials('named-directory fallback:'+n,z.read(n))
    with tarfile.open(fallback/'port-source.tar.gz','r:gz') as tar:
        for m in tar.getmembers():
            assert m.uid==m.gid==0 and m.uname==m.gname=='' and not m.pax_headers
            assert m.isfile() and '..' not in PurePosixPath(m.name).parts
            check_credentials('named-directory port source:'+m.name,tar.extractfile(m).read())
backup=root/'release/known-working'
if backup.exists():
    old=json.loads((backup/'BUILD.json').read_text())
    oldzip=backup/'xbox-trimui-smart-pro-2026.10.29.zip'
    assert sha(oldzip.read_bytes())==old['install_zip_sha256']
    with zipfile.ZipFile(oldzip) as z:
        assert z.testzip() is None
        assert sha(z.read('Data/ports/hakux/hakux.aarch64'))=='893afce7818b68d294f7ff3258400fd0dc6120c7698d8be0df109d6ef4bdcab2'
        for n in z.namelist():check_credentials('known working ZIP:'+n,z.read(n))
    with tarfile.open(backup/'port-source.tar.gz','r:gz') as tar:
        for m in tar.getmembers():
            assert m.uid==m.gid==0 and m.uname==m.gname=='' and not m.pax_headers
            assert m.isfile() and '..' not in PurePosixPath(m.name).parts
            check_credentials('previous port source:'+m.name,tar.extractfile(m).read())
for p in files:
    rel=p.relative_to(root)
    if p.suffix not in {'.gz','.zip'}:check_credentials(str(rel),p.read_bytes())
    if p.suffix.lower()=='.png':
        data=p.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n',rel
        pos=8
        while pos<len(data):
            length=int.from_bytes(data[pos:pos+4],'big');kind=data[pos+4:pos+8]
            assert kind in {b'IHDR',b'PLTE',b'tRNS',b'IDAT',b'IEND',b'sRGB'},'Unexpected image metadata: '+str(rel)
            pos+=length+12
        assert pos==len(data),rel

    assert not p.is_symlink() and p.stat().st_size<25*1024*1024,rel
    assert '.DS_Store' not in rel.parts and not any(s.startswith('._') for s in rel.parts)
    assert not str(rel).startswith(('port/source/','port/deps/','port/build/','port/dist/','local/')), 'Clean local staging before uploading: '+str(rel)
    if p.suffix in {'.md','.py','.sh','.cmake','.json','.h','.c','.inc'} and p!=Path(__file__).resolve():
        assert not re.search(rb'/Users/[^/\s]+/',p.read_bytes()),rel
print(f'PASS: tested ARM64 core, ZIP/source hashes, preserved-data layout, public archive metadata; {count} source entries, {len(files)} upload files; {scanned} credential scans with no matches')
