#!/usr/bin/env python3
from pathlib import Path
import os,subprocess,tempfile,sys,struct,zlib,binascii
r=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='hakux-extras-check-') as td:
 t=Path(td);d=t/'mods/12345678.3/test-mod';(d/'files').mkdir(parents=True);(t/'shots').mkdir()
 (d/'mod.txt').write_text('name: Test overlay\n[default.xbe]\n0x00010020: 00 -> 01\n')
 (d/'files/data.bin').write_bytes(b'overlay')
 (d.parent/'cheats.txt').write_text('[Live write]\nnote: test code only\nw8 0x10000 42\n[Once write]\nonce\nw8 0x10001 7\n')
 def chunk(k,b):return struct.pack('>I',len(b))+k+b+struct.pack('>I',binascii.crc32(k+b)&0xffffffff)
 fixture=t/'source.png';fixture.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(bytes([0,21,42,63,0])))+chunk(b'IEND',b''))
 tool=t/'screenshot-tool';tool.write_text('#!/bin/sh\ncat "$HAKUX_TEST_PNG" > "$2"\n');tool.chmod(0o755)
 exe=t/'test';flags=['-std=gnu11','-O1','-g','-ffunction-sections','-fdata-sections','-Wl,-dead_strip' if sys.platform=='darwin' else '-Wl,--gc-sections','-I'+str(r/'source'),'-I'+str(r/'platform/include'),'-DHLE_HOST_TEST']
 subprocess.run(['cc',*flags,str(r/'tests/extras.c'),str(r/'platform/extras.c'),str(r/'platform/profile.c'),str(r/'platform/png.c'),str(r/'source/native/core/cheats.c'),str(r/'source/native/core/mods.c'),'-o',str(exe),'-lpthread','-lz'],check=True)
 subprocess.run([str(exe)],cwd=t,env=dict(os.environ,HAKUX_SCREENSHOT_DIR=str(t/'shots'),HAKUX_SCREENSHOT_TOOL=str(tool),HAKUX_TEST_PNG=str(fixture)),check=True,timeout=10)
 shots=list((t/'shots').glob('*.png'));assert len(shots)==1 and shots[0].read_bytes()[25]==2
 assert not (d.parent/'enabled-cheats.tmp').exists()
 print('PASS screenshot request: background capture, unique game/version filename, saved file and no discarded staging files')
