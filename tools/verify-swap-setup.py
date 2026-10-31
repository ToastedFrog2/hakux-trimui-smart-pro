#!/usr/bin/env python3
"""Exercise the actual swap helper with isolated files and mocked kernel tools."""
from pathlib import Path
import json,os,subprocess,sys,tempfile
root=Path(__file__).resolve().parents[1]
source=(root/'port/platform/xbox2-swap.sh').read_text()
mock=r'''
import json,os,signal,sys
from pathlib import Path
cmd=Path(sys.argv[0]).name;a=sys.argv[1:];fault=os.environ.get('FAULT','')
with open(os.environ['CALLS'],'a') as f:f.write(json.dumps([cmd,a])+'\n')
if cmd=='id':print('501' if fault=='not_root' else '0')
elif cmd=='df':
 print('Filesystem 1024-blocks Used Available Capacity Mounted on')
 free='900000' if fault=='low_space' else 'garbage' if fault=='bad_df' else '6000000'
 print('fixture 7000000 1000000 '+free+' 15% '+os.environ['DISK'])
elif cmd=='dd':
 assert 'bs=1048576' in a and 'count=512' in a
 p=Path(next(x[3:] for x in a if x.startswith('of=')))
 assert p.name.startswith('.hakux-swap-new.')
 p.write_bytes(b'allocated fixture')
 if fault=='allocation_fail':sys.exit(1)
 if fault=='publish_race':(p.parent/'hakux.swap').write_bytes(b'other process data')
 if fault=='publish_directory_race':(p.parent/'hakux.swap').mkdir()
elif cmd=='mkswap':
 p=Path(a[-1]);assert p.name.startswith('.hakux-swap-new.')
 if fault=='format_fail':sys.exit(1)
 p.write_bytes(b'valid swap fixture')
elif cmd=='swapon':
 p=Path(a[-1]);assert a[:2]==['-p','10']
 if fault=='activate_fail' or not p.read_bytes().startswith(b'valid swap'):sys.exit(1)
 with open(os.environ['SWAPS'],'a') as f:f.write(str(p)+' file 524284 0 10\n')
 if fault=='signal_after_activate':os.kill(os.getppid(),signal.SIGTERM)
elif cmd=='sync':pass
elif cmd=='ln':
 assert a[0]=='-T'
 try:os.link(a[-2],a[-1])
 except OSError:sys.exit(1)
else:raise AssertionError(cmd)
'''
count=0
with tempfile.TemporaryDirectory(prefix='hakux-auto-swap-') as td:
 base=Path(td)
 def setup(name,fault=''):
  d=base/name;d.mkdir();app=d/'app with spaces';app.mkdir();disk=d/'internal';disk.mkdir();sd=d/'card';sd.mkdir();bins=d/'bin';bins.mkdir()
  swaps=d/'swaps';swaps.write_text('Filename Type Size Used Priority\n')
  mounts=d/'mounts';mounts.write_text('/dev/internal '+str(disk)+' ext4 rw,relatime 0 0\n')
  calls=d/'calls';calls.touch();helper=d/'helper.sh'
  helper.write_text(source.replace('/mnt/UDISK',str(disk)).replace('/mnt/SDCARD',str(sd)).replace('/proc/swaps',str(swaps)).replace('/proc/mounts',str(mounts)).replace('/tmp/hakux-swap-setup.lock',str(d/'lock')))
  for name in ['id','df','dd','mkswap','swapon','sync','ln']:
   p=bins/name;p.write_text('#!'+sys.executable+'\n'+mock);p.chmod(0o755)
  env=dict(os.environ,APP=str(app),PATH=str(bins)+':'+os.environ['PATH'],CALLS=str(calls),SWAPS=str(swaps),DISK=str(disk),FAULT=fault)
  return {'dir':d,'app':app,'disk':disk,'sd':sd,'swaps':swaps,'mounts':mounts,'calls':calls,'helper':helper,'env':env}
 def run(s):
  # Outer trap must survive sourcing; internal variables must stay in subshell.
  marker=s['dir']/'outer-cleanup'
  script='trap \'printf done > "$OUTER_MARKER"\' EXIT; . "$1"; test -z "${HAKUX_SWAP_STAGE+x}"; :'
  env=dict(s['env'],OUTER_MARKER=str(marker))
  subprocess.run(['/bin/sh','-c',script,'test',str(s['helper'])],env=env,check=True)
  assert marker.read_text()=='done'
  assert not list(s['disk'].glob('.hakux-swap-new.*'))
  assert not list(s['app'].glob('.swap-config.*'))
 def calls(s,name):return [a for c,a in map(json.loads,s['calls'].read_text().splitlines()) if c==name]
 def passed(name):
  global count
  count+=1;print('PASS',name)
 s=setup('fresh');(s['disk']/'.hakux-swap-new.orphan').write_bytes(b'partial own allocation');keep=s['disk']/'other.swap';keep.write_bytes(b'other data')
 run(s);file=s['disk']/'hakux.swap';assert file.read_bytes()==b'valid swap fixture';assert file.stat().st_mode&0o777==0o600
 assert (s['app']/'swap-file').read_text()==str(file)+'\n';assert len(calls(s,'dd'))==len(calls(s,'mkswap'))==len(calls(s,'swapon'))==1
 assert keep.read_bytes()==b'other data';assert not (s['dir']/'lock').exists();passed('first launch allocates requested 512 MiB once, formats only its stage, publishes/configures, cleans staging and preserves unrelated files')
 run(s);assert len(calls(s,'dd'))==len(calls(s,'mkswap'))==len(calls(s,'swapon'))==1;passed('repeat launch reuses active configured swap')
 s['swaps'].write_text('Filename Type Size Used Priority\n');run(s);assert len(calls(s,'swapon'))==2 and len(calls(s,'dd'))==1;passed('after reboot configured file reactivates without reallocation')
 s=setup('existing_global');s['swaps'].write_text('Filename Type Size Used Priority\n/another/swap file 524284 50 5\n');run(s);assert not calls(s,'dd') and not calls(s,'swapon');passed('existing system swap reused, no second file')
 s=setup('existing_config');f=s['sd']/'custom.swap';f.write_bytes(b'valid swap custom');cfg=s['app']/'swap-file';cfg.write_text(str(f)+'\n');run(s);assert f.read_bytes()==b'valid swap custom' and cfg.read_text()==str(f)+'\n';assert not calls(s,'mkswap');passed('explicit existing config and custom file preserved')
 s=setup('existing_default');f=s['disk']/'hakux.swap';f.write_bytes(b'valid swap original');run(s);assert not calls(s,'dd') and not calls(s,'mkswap');assert f.read_bytes()==b'valid swap original';passed('existing default reused without formatting')
 s=setup('invalid_default');f=s['disk']/'hakux.swap';f.write_bytes(b'user data');run(s);assert f.read_bytes()==b'user data';assert not calls(s,'dd') and not calls(s,'mkswap') and not (s['app']/'swap-file').exists();passed('invalid pre-existing file is never reformatted or removed')
 for name,fault in [('low_space','low_space'),('bad_df','bad_df'),('not_root','not_root')]:
  s=setup(name,fault);run(s);assert not calls(s,'dd') and not (s['disk']/'hakux.swap').exists();passed(name+' skips creation and returns normally')
 for name,line in [('fat32','vfat rw'),('readonly','ext4 ro')]:
  s=setup(name);s['mounts'].write_text('/dev/internal '+str(s['disk'])+' '+line+' 0 0\n');run(s);assert not calls(s,'dd');passed(name+' storage skipped')
 for name,fault in [('allocation_failure','allocation_fail'),('format_failure','format_fail'),('activation_failure','activate_fail')]:
  s=setup(name,fault);run(s);assert not (s['disk']/'hakux.swap').exists() and not (s['app']/'swap-file').exists();passed(name+' leaves no new swap or config; launch may continue')
 s=setup('invalid_config');cfg=s['app']/'swap-file';cfg.write_text('/unsupported/path\n');run(s);assert cfg.read_text()=='/unsupported/path\n' and not calls(s,'dd');passed('invalid explicit config retained without replacement')
 s=setup('missing_configured_file');cfg=s['app']/'swap-file';cfg.write_text(str(s['disk']/'missing.swap')+'\n');run(s);assert cfg.exists() and not calls(s,'dd');passed('missing configured file does not trigger replacement')
 s=setup('disabled');(s['app']/'disable-swap').touch();run(s);assert not calls(s,'dd') and not calls(s,'swapon');passed('opt-out prevents setup and activation')
 s=setup('busy');(s['dir']/'lock').mkdir();run(s);assert (s['dir']/'lock').exists() and not calls(s,'dd');passed('busy lock preserved; no concurrent allocation')
 s=setup('symlink');other=s['disk']/'keep';other.write_bytes(b'keep');(s['disk']/'hakux.swap').symlink_to(other);run(s);assert other.read_bytes()==b'keep' and not calls(s,'dd');passed('default symlink never followed for creation/formatting')
 s=setup('race','publish_race');run(s);assert (s['disk']/'hakux.swap').read_bytes()==b'other process data';assert not calls(s,'swapon');passed('publication cannot overwrite a concurrently created file')
 s=setup('directory_race','publish_directory_race');run(s);assert (s['disk']/'hakux.swap').is_dir() and not list((s['disk']/'hakux.swap').iterdir());passed('publication cannot write into a concurrently created directory')
 s=setup('signal','signal_after_activate');run(s);assert (s['disk']/'hakux.swap').exists() and str(s['disk']/'hakux.swap') in s['swaps'].read_text();passed('signal after activation preserves active swap')
 s=setup('kernel_unavailable');s['swaps'].unlink();run(s);assert not calls(s,'dd');passed('kernel without swap support skips setup')
print(f'PASS all {count} swap setup cases; disk/kernel commands mocked, no real swap created')
