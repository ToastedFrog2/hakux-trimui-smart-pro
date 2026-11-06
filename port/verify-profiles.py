#!/usr/bin/env python3
"""Exercise actual profile and XDVDFS code against synthetic Xbox discs."""
from pathlib import Path
import os,struct,subprocess,tempfile
r=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='hakux-profiles-check-') as td:
 t=Path(td)
 for version in [1,2]:
  data=bytearray(0x21000);magic=b'MICROSOFT*XBOX*MEDIA';data[0x10000:0x10014]=magic;data[0x107ec:0x10800]=magic
  struct.pack_into('<II',data,0x10014,33,28)
  struct.pack_into('<HHIIBB',data,33*2048,0,0,64,4096,0x20,11);data[33*2048+14:33*2048+25]=b'default.xbe'
  start=64*2048;data[start:start+4]=b'XBEH';struct.pack_into('<I',data,start+0x104,0x10000);struct.pack_into('<I',data,start+0x118,0x10200)
  struct.pack_into('<I',data,start+0x200,0xb0);struct.pack_into('<I',data,start+0x208,0x12345678);struct.pack_into('<I',data,start+0x2ac,version)
  (t/f'game{version}.iso').write_bytes(data)
 exe=t/'check'
 subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-O1','-g','-DHLE_HOST_TEST','-I'+str(r/'source'),'-I'+str(r/'platform/include'),str(r/'tests/profiles.c'),str(r/'source/native/core/xdvdfs.c'),'-o',str(exe)],check=True)
 subprocess.run([str(exe),str(t/'game1.iso'),str(t/'game2.iso')],cwd=t,check=True,timeout=5)
