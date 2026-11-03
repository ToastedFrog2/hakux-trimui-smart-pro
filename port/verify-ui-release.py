#!/usr/bin/env python3
"""Exercise ownership checks without stopping any real process or service."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='hakux-ui-owner-') as td:
 d=Path(td);helper=d/'helper.sh';owner=d/'owner';events=d/'events'
 helper.write_text((root/'platform/mainui-release.sh').read_text().replace('/tmp/hakux-ui-owner',str(owner)).replace('/proc/',str(d/'proc')+'/'))
 (d/'proc/999999').mkdir(parents=True)
 (d/'proc/999999/cmdline').write_bytes(b'/bin/sh\0/usr/trimui/bin/runtrimui.sh\0')
 app=d/'app';app.mkdir()
 (app/'runtime-mainui.sh').write_text('#!/bin/sh\nexit 0\n')
 script=r'''
set +e
. "$1"
set -e
owner=$2; events=$3
hakux_process_start() { echo 42; }
hakux_osd_alive() { echo OSD >> "$events"; return 0; }
kill() { echo "$*" >> "$events"; }
HAKUX_MAINUI_SUPERVISOR=999999; HAKUX_MAINUI_SUPERVISOR_START=42
HAKUX_OSD_CLOSED=1; HAKUX_OSD_EXE=/never/execute
HAKUX_UI_TOKEN=old
# A delayed guard from an old game must not touch a newer owner or its OSD.
echo new > "$owner"
printf '%s\n' 777:42 778:41 > "$owner.music"
hakux_mainui_restore
test ! -f "$events"
test "$(cat "$owner")" = new
test -f "$owner.music"
# Only the current owner restores services and releases ownership.
HAKUX_UI_TOKEN=new
hakux_mainui_restore
test "$(head -1 "$events")" = OSD
grep -q -- '-CONT 999999' "$events"
test ! -f "$owner"
# Its paused musicserver resumes; a reused pid (another start time) does not
grep -q -- '-CONT 777$' "$events"
if grep -q -- '-CONT 778' "$events"; then exit 1; fi
test ! -f "$owner.music"
rm "$events"
# A duplicate recovery call after normal cleanup has no effects.
hakux_mainui_restore
test ! -f "$events"
# Exercise actual service acquisition with fake processes, never real signals.
APP=$4
pidof() {
    case "$1" in
        runtrimui.sh) echo 999999;;
        MainUI) echo 901;;
        trimui_osdd) echo 900;;
        musicserver) echo '777 888';;
    esac
}
awk() {
    case "$1:$2" in
        '/^State:/'*'/888/status') echo T;;
        '/^State:/'*) echo S;;
        '/^PPid:/'*) echo 999999;;
        *) return 1;;
    esac
}
readlink() { echo /usr/trimui/osd/trimui_osdd; }
HAKUX_MAINUI_SUPERVISOR=''; HAKUX_UI_TOKEN=active
hakux_mainui_apply
grep -q -- '-STOP 777$' "$events"
if grep -q -- '-STOP 888$' "$events"; then exit 1; fi
test "$(cat "$owner.music")" = 777:42
# An already-paused musicserver belongs to someone else and remains paused.
hakux_mainui_restore
grep -q -- '-CONT 777$' "$events"
if grep -q -- '-CONT 888$' "$events"; then exit 1; fi
test ! -f "$owner.music"
test ! -f "$owner"
'''
 subprocess.run(['/bin/sh','-c',script,'test',str(helper),str(owner),str(events),str(app)],check=True)
print('PASS actual UI lifecycle: owned musicserver pauses/resumes; pre-paused and reused PIDs stay untouched; stale/duplicate recovery is inert')
