#!/usr/bin/env python3
"""Verify and unpack bundled corresponding source without network access."""
from pathlib import Path, PurePosixPath
import hashlib, json, os, tarfile
root=Path(__file__).resolve().parent
bundle=root.parent/'sources'
manifest=json.loads((bundle/'SOURCES.json').read_text())
for folder in [root/'source',root/'deps']:
    if folder.exists():raise SystemExit(f'{folder.name} already exists; retain it or move it aside before unpacking')
for entry in manifest['archives']:
    path=bundle/entry['file']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
        raise SystemExit('Checksum mismatch: '+entry['file'])
    with tarfile.open(path,'r:gz') as tar:
        for m in tar.getmembers():
            rel=PurePosixPath(m.name)
            if rel.is_absolute() or '..' in rel.parts or rel.parts[0] not in {'source','deps'}:
                raise SystemExit('Unsafe source path')
            if m.issym():
                target=PurePosixPath(m.linkname)
                if target.is_absolute() or not (root/m.name).parent.joinpath(m.linkname).resolve().is_relative_to(root):
                    raise SystemExit('Unsafe source link')
            elif not m.isfile():raise SystemExit('Unexpected source entry')
            # No archive member may write through an earlier symbolic link.
            if any(p.is_symlink() for p in (root/m.name).parents if p!=root and p.is_relative_to(root)):
                raise SystemExit('Source parent is a link')
        tar.extractall(root)
(root/'deps/lib').mkdir(exist_ok=True)
print('Verified and unpacked matching hakuX, FEX and dependency source. See docs/BUILDING.md.')
