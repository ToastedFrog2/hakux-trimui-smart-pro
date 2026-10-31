#!/usr/bin/env python3
"""Exercise ownership checks without stopping any real process or service."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='hakux-ui-owner-') as td:
 d=Path(td);helper=d/'helper.sh';owner=d/'owner';events=d/'events'
 helper.write_text((root/'platform/mainui-release.sh').read_text().replace('/tmp/hakux-ui-owner',str(owner)))
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
hakux_mainui_restore
test ! -f "$events"
test "$(cat "$owner")" = new
# Only the current owner restores services and releases ownership.
HAKUX_UI_TOKEN=new
hakux_mainui_restore
test "$(head -1 "$events")" = OSD
grep -q -- '-CONT 999999' "$events"
test ! -f "$owner"
rm "$events"
# A duplicate recovery call after normal cleanup has no effects.
hakux_mainui_restore
test ! -f "$events"
'''
 subprocess.run(['/bin/sh','-c',script,'test',str(helper),str(owner),str(events)],check=True)
print('PASS actual UI restore: stale guard cannot resume a newer session or restart its OSD; current owner restores once')
