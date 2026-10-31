#!/bin/sh
# Automatic MainUI + OSD release for an Xbox launch; no firmware edits.
hakux_process_start() { awk '{print $22}' "/proc/$1/stat" 2>/dev/null; }
hakux_osd_alive() {
    for osd_check in $(pidof trimui_osdd 2>/dev/null); do
        case "$(awk '/^State:/ {print $2}' "/proc/$osd_check/status" 2>/dev/null)" in Z|X|'') continue;; esac
        return 0
    done
    return 1
}
hakux_mainui_restore() {
    # A previous game's delayed guard must not restore a newer game's UI.
    [ "$(cat /tmp/hakux-ui-owner 2>/dev/null)" = "${HAKUX_UI_TOKEN:-}" ] && [ -n "${HAKUX_UI_TOKEN:-}" ] || return 0
    if [ "${HAKUX_OSD_CLOSED:-0}" = 1 ] && [ -n "${HAKUX_OSD_EXE:-}" ]; then
        if ! hakux_osd_alive; then
            (
                cd "$(dirname "$HAKUX_OSD_EXE")" || exit
                export LD_LIBRARY_PATH="${HAKUX_OSD_LIB}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
                exec "$HAKUX_OSD_EXE"
            ) </dev/null >/dev/null 2>&1 &
            for attempt in 1 2 3 4 5 6 7 8 9 10; do
                hakux_osd_alive && break
                sleep .1
            done
        fi
    fi
    if [ -n "${HAKUX_MAINUI_SUPERVISOR:-}" ] &&
       [ "$(cat /tmp/hakux-ui-owner 2>/dev/null)" = "$HAKUX_UI_TOKEN" ] &&
       [ "$(hakux_process_start "$HAKUX_MAINUI_SUPERVISOR")" = "$HAKUX_MAINUI_SUPERVISOR_START" ]; then
        rm -f /tmp/hakux-ui-owner
        kill -CONT "$HAKUX_MAINUI_SUPERVISOR" 2>/dev/null || :
    fi
}
if [ "${1:-}" = --guard ]; then
    watched=$2; watched_start=$3
    HAKUX_UI_TOKEN="$watched:$watched_start"
    HAKUX_MAINUI_SUPERVISOR=$4; HAKUX_MAINUI_SUPERVISOR_START=$5
    HAKUX_OSD_EXE=$6; HAKUX_OSD_LIB=$7; HAKUX_OSD_CLOSED=$8
    while [ "$(hakux_process_start "$watched")" = "$watched_start" ]; do
        case "$(awk '/^State:/ {print $2}' "/proc/$watched/status" 2>/dev/null)" in Z|X|'') break;; esac
        sleep 1
    done
    hakux_mainui_restore
    exit 0
fi
HAKUX_MAINUI_SUPERVISOR=""
HAKUX_MAINUI_SUPERVISOR_START=""
HAKUX_OSD_EXE=""
HAKUX_OSD_LIB=""
HAKUX_OSD_CLOSED=0
HAKUX_UI_TOKEN="$$:$(hakux_process_start "$$")"
hakux_mainui_apply() {
    [ -z "$HAKUX_MAINUI_SUPERVISOR" ] || return 0
    # The supervisor also exists when MainUI already exited to launch a game.
    for supervisor in $(pidof runtrimui.sh 2>/dev/null); do
        case "$supervisor" in ''|0|1) continue;; esac
        tr '\000' ' ' < "/proc/$supervisor/cmdline" 2>/dev/null | grep -q '/usr/trimui/bin/runtrimui.sh' || continue
        # Allow an earlier launcher's EXIT cleanup to finish before taking over.
        for retry in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
            state=$(awk '/^State:/ {print $2}' "/proc/$supervisor/status" 2>/dev/null)
            [ "$state" = T ] || break
            sleep .1
        done
        [ "$state" != T ] || continue
        HAKUX_MAINUI_SUPERVISOR=$supervisor
        HAKUX_MAINUI_SUPERVISOR_START=$(hakux_process_start "$supervisor")
        [ -n "$HAKUX_MAINUI_SUPERVISOR_START" ] || { HAKUX_MAINUI_SUPERVISOR=""; continue; }
        for osd_pid in $(pidof trimui_osdd 2>/dev/null); do
            osd_exe=$(readlink "/proc/$osd_pid/exe" 2>/dev/null)
            case "$osd_exe" in
                /usr/trimui/osd/trimui_osdd|/mnt/UDISK/trimui/osd/trimui_osdd|/mnt/SDCARD/trimui/osd/trimui_osdd)
                    HAKUX_OSD_EXE=$osd_exe
                    HAKUX_OSD_LIB="${osd_exe%/osd/trimui_osdd}/lib"
                    HAKUX_OSD_CLOSED=1
                    break;;
            esac
        done
        printf '%s\n' "$HAKUX_UI_TOKEN" > "/tmp/hakux-ui-owner.$$"
        mv "/tmp/hakux-ui-owner.$$" /tmp/hakux-ui-owner
        /bin/sh "$APP/runtime-mainui.sh" --guard "$$" "$(hakux_process_start "$$")" "$supervisor" "$HAKUX_MAINUI_SUPERVISOR_START" "$HAKUX_OSD_EXE" "$HAKUX_OSD_LIB" "$HAKUX_OSD_CLOSED" </dev/null >/dev/null 2>&1 &
        if ! kill -STOP "$supervisor" 2>/dev/null; then HAKUX_MAINUI_SUPERVISOR=""; HAKUX_OSD_CLOSED=0; continue; fi
        echo "hakuX RAM: automatic MainUI + OSD release; supervisor $supervisor resumes after exit" >> "$APP/log.txt"
        for candidate in $(pidof MainUI 2>/dev/null); do
            parent=$(awk '/^PPid:/ {print $2}' "/proc/$candidate/status" 2>/dev/null)
            [ "$parent" != "$supervisor" ] || kill -KILL "$candidate" 2>/dev/null || :
        done
        if [ "$HAKUX_OSD_CLOSED" = 1 ]; then
            for candidate in $(pidof trimui_osdd 2>/dev/null); do
                [ "$(readlink "/proc/$candidate/exe" 2>/dev/null)" != "$HAKUX_OSD_EXE" ] || kill -KILL "$candidate" 2>/dev/null || :
            done
        fi
        return 0
    done
    echo 'hakuX RAM: unsupported or already-paused UI supervisor; retaining normal pause behavior' >> "$APP/log.txt"
    return 0
}
