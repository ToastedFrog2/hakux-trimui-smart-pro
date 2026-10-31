#!/bin/sh
# Shared by every game. Subshell traps cannot replace launcher cleanup traps.
hakux_prepare_swap() (
    HAKUX_SWAP_FILE=/mnt/UDISK/hakux.swap
    HAKUX_SWAP_LOCK=/tmp/hakux-swap-setup.lock
    HAKUX_SWAP_STAGE=""
    HAKUX_SWAP_CONFIG_TMP=""
    HAKUX_SWAP_CREATED=0
    HAKUX_SWAP_LOCKED=0
    hakux_swap_active() {
        awk -v target="$1" 'NR>1 && $1==target {found=1} END {exit !found}' /proc/swaps
    }
    hakux_swap_cleanup() {
        [ -z "$HAKUX_SWAP_STAGE" ] || rm -f "$HAKUX_SWAP_STAGE"
        [ -z "$HAKUX_SWAP_CONFIG_TMP" ] || rm -f "$HAKUX_SWAP_CONFIG_TMP"
        if [ "$HAKUX_SWAP_CREATED" = 1 ] && [ -r /proc/swaps ]; then
            # Never unlink active swap, including a signal just after swapon.
            if ! hakux_swap_active "$HAKUX_SWAP_FILE"; then rm -f "$HAKUX_SWAP_FILE"; fi
        fi
        [ "$HAKUX_SWAP_LOCKED" = 0 ] || rmdir "$HAKUX_SWAP_LOCK" 2>/dev/null || :
    }
    hakux_swap_activate() {
        if hakux_swap_active "$1"; then
            echo 'hakuX RAM: configured swap already active'
            return 0
        fi
        if swapon -p 10 "$1"; then
            echo 'hakuX RAM: swap enabled (shared by all games until reboot)'
            return 0
        fi
        echo 'hakuX RAM: swap activation failed; continuing without changing the file'
        return 1
    }
    hakux_swap_save_config() {
        [ ! -e "$APP/swap-file" ] && [ ! -L "$APP/swap-file" ] || return 0
        HAKUX_SWAP_CONFIG_TMP=$(mktemp "$APP/.swap-config.XXXXXX") || return 1
        printf '%s\n' "$HAKUX_SWAP_FILE" > "$HAKUX_SWAP_CONFIG_TMP" || return 1
        mv "$HAKUX_SWAP_CONFIG_TMP" "$APP/swap-file" || return 1
        HAKUX_SWAP_CONFIG_TMP=""
    }
    trap hakux_swap_cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP
    [ ! -e "$APP/disable-swap" ] || { echo 'hakuX RAM: automatic swap setup disabled'; return 0; }
    [ -r /proc/swaps ] || { echo 'hakuX RAM: kernel swap support unavailable'; return 0; }
    for tool in awk head swapon id; do
        command -v "$tool" >/dev/null 2>&1 || { echo "hakuX RAM: missing $tool; swap setup skipped"; return 0; }
    done
    [ "$(id -u)" = 0 ] || { echo 'hakuX RAM: root required for swap activation'; return 0; }
    if [ -e "$APP/swap-file" ] || [ -L "$APP/swap-file" ]; then
        HAKUX_SWAP_PATH=$(head -n 1 "$APP/swap-file") || return 0
        case "$HAKUX_SWAP_PATH" in
            /mnt/UDISK/*|/mnt/SDCARD/*) ;;
            *) echo 'hakuX RAM: existing swap configuration invalid; retained without replacement'; return 0;;
        esac
        [ -f "$HAKUX_SWAP_PATH" ] || { echo 'hakuX RAM: configured swap file missing; configuration retained'; return 0; }
        hakux_swap_activate "$HAKUX_SWAP_PATH" || :
        return 0
    fi
    if awk 'NR>1 {found=1} END {exit !found}' /proc/swaps; then
        echo 'hakuX RAM: existing system swap available to all games; no extra file created'
        return 0
    fi
    # Only create on writable internal ext4, never on the FAT32 ROM card.
    for tool in mkdir rmdir rm df mktemp chmod dd mkswap sync ln mv; do
        command -v "$tool" >/dev/null 2>&1 || { echo "hakuX RAM: missing $tool; automatic creation skipped"; return 0; }
    done
    awk '$2=="/mnt/UDISK" && $3=="ext4" && $4 ~ /(^|,)rw(,|$)/ {ok=1} END {exit !ok}' /proc/mounts || {
        echo 'hakuX RAM: writable internal ext4 storage unavailable; automatic creation skipped'; return 0;
    }
    if ! mkdir "$HAKUX_SWAP_LOCK" 2>/dev/null; then
        echo 'hakuX RAM: another swap setup is in progress; continuing'
        return 0
    fi
    HAKUX_SWAP_LOCKED=1
    # Only our orphaned allocation stages are eligible for cleanup.
    for HAKUX_SWAP_OLD in /mnt/UDISK/.hakux-swap-new.*; do
        if [ -f "$HAKUX_SWAP_OLD" ] && [ ! -L "$HAKUX_SWAP_OLD" ] && ! hakux_swap_active "$HAKUX_SWAP_OLD"; then
            rm -f "$HAKUX_SWAP_OLD"
        fi
    done
    if [ -e "$HAKUX_SWAP_FILE" ] || [ -L "$HAKUX_SWAP_FILE" ]; then
        if [ -f "$HAKUX_SWAP_FILE" ] && [ ! -L "$HAKUX_SWAP_FILE" ]; then
            if hakux_swap_activate "$HAKUX_SWAP_FILE"; then hakux_swap_save_config || :; fi
        else
            echo 'hakuX RAM: default swap path is not a regular file; retained without replacement'
        fi
        return 0
    fi
    HAKUX_SWAP_FREE=$(df -Pk /mnt/UDISK | awk 'NR==2 {print $4}')
    case "$HAKUX_SWAP_FREE" in ''|*[!0-9]*) echo 'hakuX RAM: cannot determine free space; creation skipped'; return 0;; esac
    [ "$HAKUX_SWAP_FREE" -ge 1048576 ] || { echo 'hakuX RAM: less than 1 GiB free internally; creation skipped'; return 0; }
    HAKUX_SWAP_STAGE=$(mktemp /mnt/UDISK/.hakux-swap-new.XXXXXX) || return 0
    chmod 600 "$HAKUX_SWAP_STAGE" || return 0
    echo 'hakuX RAM: first launch preparing 512 MiB internal swap; please wait'
    dd if=/dev/zero of="$HAKUX_SWAP_STAGE" bs=1048576 count=512 || { echo 'hakuX RAM: swap allocation failed; continuing'; return 0; }
    mkswap "$HAKUX_SWAP_STAGE" || { echo 'hakuX RAM: swap initialization failed; continuing'; return 0; }
    sync || return 0
    # Atomic no-clobber publication on internal ext4. The SD config uses rename.
    ln -T "$HAKUX_SWAP_STAGE" "$HAKUX_SWAP_FILE" || { echo 'hakuX RAM: safe publication failed; existing destination retained'; return 0; }
    HAKUX_SWAP_CREATED=1
    rm -f "$HAKUX_SWAP_STAGE"
    HAKUX_SWAP_STAGE=""
    if hakux_swap_activate "$HAKUX_SWAP_FILE"; then
        HAKUX_SWAP_CREATED=0
        if ! hakux_swap_save_config; then echo 'hakuX RAM: swap active; configuration could not be saved'; fi
        echo 'hakuX RAM: first-launch swap setup complete'
    fi
    return 0
)
hakux_prepare_swap >> "$APP/log.txt" 2>&1
