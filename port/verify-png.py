#!/usr/bin/env python3
"""Check framebuffer PNG normalization preserves RGB for all PNG row filters."""
from pathlib import Path
import binascii,struct,subprocess,tempfile,os,zlib
r=Path(__file__).resolve().parent
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',binascii.crc32(kind+data)&0xffffffff)
def paeth(a,b,c):
 p=a+b-c;da,db,dc=abs(p-a),abs(p-b),abs(p-c)
 return a if da<=db and da<=dc else b if db<=dc else c
def fixture(bpp,filter):
 w,h=7,5;prior=bytes(w*bpp);raw=bytearray();expected=bytearray()
 for y in range(h):
  row=bytearray()
  for x in range(w):
   rgb=bytes(((x*67+y*13+k*29)&255) for k in range(3));row.extend(rgb);expected.extend(rgb)
   if bpp==4:row.append(0 if y%2==0 else 128)
  encoded=bytearray()
  for i,v in enumerate(row):
   a=row[i-bpp] if i>=bpp else 0;b=prior[i];c=prior[i-bpp] if i>=bpp else 0
   predictor=[0,a,b,(a+b)//2,paeth(a,b,c)][filter]
   encoded.append((v-predictor)&255)
  raw.append(filter);raw.extend(encoded);prior=row
 header=struct.pack('>IIBBBBB',w,h,8,6 if bpp==4 else 2,0,0,0)
 png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',header)+chunk(b'tEXt',b'Comment\0capture metadata')+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
 return png,bytes(expected)
with tempfile.TemporaryDirectory(prefix='hakux-png-check-') as td:
 t=Path(td);exe=t/'check'
 subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-O1','-g','-fsanitize=address,undefined','-I'+str(r/'platform/include'),str(r/'tests/png.c'),str(r/'platform/png.c'),'-lz','-o',str(exe)],check=True)
 for bpp in [3,4]:
  for filter in range(5):
   png,expected=fixture(bpp,filter);path=t/'image.png';path.write_bytes(png)
   subprocess.run([str(exe),str(path)],check=True,timeout=5)
   out=path.read_bytes();at=8;types=[];packed=b''
   while at<len(out):
    n=struct.unpack_from('>I',out,at)[0];kind=out[at+4:at+8];data=out[at+8:at+8+n];types.append(kind)
    assert binascii.crc32(kind+data)&0xffffffff==struct.unpack_from('>I',out,at+8+n)[0]
    if kind==b'IHDR':assert struct.unpack('>IIBBBBB',data)==(7,5,8,2,0,0,0)
    if kind==b'IDAT':packed+=data
    at+=n+12
   assert types==[b'IHDR',b'IDAT',b'IEND']
   raw=zlib.decompress(packed);assert all(raw[y*22]==0 for y in range(5))
   assert b''.join(raw[y*22+1:y*22+22] for y in range(5))==expected
 for broken in [b'bad',fixture(4,0)[0][:-1],fixture(4,0)[0]+b'extra',fixture(4,0)[0].replace(b'IHDR',b'JHDR',1)]:
  path=t/'bad.png';path.write_bytes(broken);assert subprocess.run([str(exe),str(path)],timeout=5).returncode!=0;assert path.read_bytes()==broken
 assert not list(t.glob('*.opaque-*'))
 print('PASS PNG normalization: RGB/RGBA, all five filters, invisible alpha, exact RGB preservation, metadata removal and malformed-file rejection (ASan/UBSan)')
