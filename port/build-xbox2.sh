#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export ZIG="${ZIG:-$(command -v zig || true)}"
[ -n "$ZIG" ] || { echo 'Zig 0.16.0 is required.' >&2; exit 1; }
[ -f source/native/CMakeLists.txt ] || { echo 'Run python3 port/unpack-sources.py from the repository root first.' >&2; exit 1; }
[ -f deps/lib/libSDL2.so ] || { echo 'Copy the target firmware SDL2 library to port/deps/lib/libSDL2.so; see docs/BUILDING.md.' >&2; exit 1; }
STRIP_TOOL="${TRIMUI_STRIP:-$(command -v llvm-strip || command -v aarch64-linux-gnu-strip || true)}"
[ -n "$STRIP_TOOL" ] || { echo 'Set TRIMUI_STRIP to an LLVM or AArch64 strip executable.' >&2; exit 1; }
df -h .
for patch in source xbox2 halfscale menu recovery shader-compat memory objects halo2-save frame-skip scale075; do
    python3 "patch-$patch.py"
done
cmake -S source/native -B build/core -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$PWD/toolchains/trimui-xbox2.cmake" \
  -DCMAKE_BUILD_TYPE=Release -DHAKUX_LTO=ON -DHAKUX_XBOX2=ON \
  -DENABLE_LIBCXX=ON -DNC_DEPS="$PWD/deps" \
  -DOVERRIDE_HASH=52018bf46a8279b22bce738548ab3f40db467064 \
  -DOVERRIDE_VERSION=hakuX-pinned
python3 state-sizes.py
cmake --build build/core --target xboxrun -j "${JOBS:-6}"
mkdir -p dist
"$STRIP_TOOL" -s -o dist/hakux.aarch64 build/core/xboxrun
cp build/core/xboxrun dist/hakux.unstripped.aarch64
echo 'Built port/dist/hakux.aarch64; symbols remain local and are excluded from Git.'
