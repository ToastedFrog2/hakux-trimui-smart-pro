#!/bin/sh
# Read-only SquashFS containers let an intact >4 GiB Xbox ISO live on FAT32.
# First argument is the selected emulator's existing launcher.
set -u
RUNNER=$1
shift
ROM=${1:-}
case "$ROM" in
    *.sqfs|*.SQFS) ;;
    *) exec /bin/sh "$RUNNER" "$@" ;;
esac
if pidof hakux.aarch64 >/dev/null 2>&1; then
    echo "hakuX is already running." >&2
    exit 1
fi
MOUNT=$(mktemp -d /tmp/hakux-disc.XXXXXX) || exit 1
MOUNTED=0
cleanup() {
    if [ "$MOUNTED" = 1 ]; then umount "$MOUNT" || return; fi
    rmdir "$MOUNT"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
mount -t squashfs -o loop,ro "$ROM" "$MOUNT" || exit 1
MOUNTED=1
ISO=""
COUNT=0
for f in "$MOUNT"/*.iso "$MOUNT"/*.ISO; do
    [ -f "$f" ] || continue
    ISO=$f
    COUNT=$((COUNT + 1))
done
if [ "$COUNT" != 1 ]; then
    echo "Disc container must contain exactly one ISO." >&2
    exit 2
fi
shift
/bin/sh "$RUNNER" "$ISO" "$@"
RESULT=$?
exit "$RESULT"
