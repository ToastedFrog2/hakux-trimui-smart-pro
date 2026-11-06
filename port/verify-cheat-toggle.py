#!/usr/bin/env python3
from pathlib import Path
import os,subprocess,tempfile
r=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='hakux-toggle-check-') as td:
 exe=Path(td)/'check'
 subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-O1','-g','-fsanitize=address,undefined','-I'+str(r/'source'),str(r/'tests/toggle-cheats.c'),str(r/'source/native/core/cheats.c'),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,timeout=5)
