#!/bin/sh
# Native hakuX for the original TrimUI Smart Pro (TG5040).
set -u
APP=/mnt/SDCARD/Data/ports/hakux
ROM=${1:-/mnt/SDCARD/Roms/XBOX/PGRAPH-Tests.iso}
if pidof hakux.aarch64 >/dev/null 2>&1; then
    echo "hakuX is already running." >&2
    exit 1
fi
if [ ! -f "$ROM" ]; then
    echo "Xbox image not found: $ROM" > "$APP/log.txt"
    exit 2
fi
cd "$APP" || exit 1
if [ -z "${HAKUX_RENDER_SCALE:-}" ] && [ -r "$APP/render-scale" ]; then
    SCALE=$(cat "$APP/render-scale")
    case "$SCALE" in 0.35|0.5|0.75|1|2|3|4) export HAKUX_RENDER_SCALE="$SCALE";; esac
fi
mkdir -p cache hdd logs
WAKE_OWNED=0
if [ ! -e /tmp/stay_awake ]; then touch /tmp/stay_awake; WAKE_OWNED=1; fi
MAINUI_OWNED=""
if [ -r "$APP/runtime-mainui.sh" ]; then . "$APP/runtime-mainui.sh"; fi
for p in $(pidof MainUI 2>/dev/null); do
    state=$(awk '/^State:/ {print $2}' "/proc/$p/status" 2>/dev/null)
    if [ "$state" != T ] && kill -STOP "$p" 2>/dev/null; then
        MAINUI_OWNED="$MAINUI_OWNED $p"
    fi
done
cleanup() {
    if command -v hakux_mainui_restore >/dev/null 2>&1; then hakux_mainui_restore; fi
    for p in $MAINUI_OWNED; do kill -CONT "$p" 2>/dev/null || :; done
    [ "$WAKE_OWNED" = 0 ] || rm -f /tmp/stay_awake
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
export HAKUX_NATIVE_BASE="$APP/cache"
export NC_TIMEOUT=0
export SDL_AUDIODRIVER=alsa
export SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1
if [ -f /mnt/SDCARD/Apps/PortMaster/PortMaster/gamecontrollerdb.txt ]; then
    export SDL_GAMECONTROLLERCONFIG_FILE=/mnt/SDCARD/Apps/PortMaster/PortMaster/gamecontrollerdb.txt
fi
# A title that relaunches itself (XLaunchNewImage: Unreal Championship after
# its setup) ends the run with 10 and leaves relaunch.bin; the emulator then
# starts again with "relaunch", which boots the XBE that file names.
rm -f "$APP/relaunch.bin" "$APP/menu-restart"
: > "$APP/log.txt"
RESULT=0
while :; do
    if command -v hakux_mainui_apply >/dev/null 2>&1; then hakux_mainui_apply; fi
    set -- "$ROM" "hdd=$APP/hdd"
    if [ "$RESULT" = 10 ]; then
        set -- "$@" relaunch
    elif [ "$RESULT" = 20 ]; then
        SCALE=$(cat "$APP/render-scale")
        case "$SCALE" in 0.35|0.5|0.75|1|2|3|4) export HAKUX_RENDER_SCALE="$SCALE";; esac
        REQUEST=$(cat "$APP/menu-restart")
        rm -f "$APP/menu-restart"
        [ "$REQUEST" = restart ] || { RESULT=2; break; }
    fi
    ./hakux.aarch64 "$@" >> "$APP/log.txt" 2>&1
    RESULT=$?
    if [ "$RESULT" = 10 ] && [ -f "$APP/relaunch.bin" ]; then continue; fi
    if [ "$RESULT" = 20 ] && [ -f "$APP/menu-restart" ]; then continue; fi
    break
done
sync
case "$RESULT" in 0|10) RESULT=0;; esac
exit "$RESULT"
