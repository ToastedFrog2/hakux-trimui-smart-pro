#!/bin/sh
# Optional manual retry of the same setup normally performed on game launch.
set -u
APP=/mnt/SDCARD/Data/ports/hakux
if pidof hakux.aarch64 >/dev/null 2>&1; then echo 'Exit the game first.' >&2; exit 1; fi
[ -r "$APP/runtime-swap.sh" ] || { echo 'Install the current Xbox package first.' >&2; exit 1; }
. "$APP/runtime-swap.sh"
tail -n 12 "$APP/log.txt"
