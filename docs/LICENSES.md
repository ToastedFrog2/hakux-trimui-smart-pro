# Licenses and attribution

This is a modified Linux handheld port of
[rfandango/hakuX](https://github.com/rfandango/hakuX), not a new independent
emulator implementation. Upstream authors and component authors retain
their copyrights and credits.

The upstream hakuX [LICENSE](../LICENSE) and full GPL version 3 text in
[COPYING](../COPYING) are retained. hakuX is GPL-3.0-or-later. Port additions
and modifications in this distribution are provided under the same terms.
Third-party components retain the licenses stated in their own source files.

The matching modified hakuX/FEX source and dependency source are included in
`sources/`. Their archive hashes, upstream URLs and pinned revisions are in
`sources/SOURCES.json`. After unpacking, original notices are available in
`port/source/licenses`, `port/source/external/fex`, and `port/deps`.
The install ZIP also includes the upstream/component license texts in
`Data/ports/hakux/licenses`.

Important components include FEX, glslang, volk, SPIRV-Reflect,
VulkanMemoryAllocator, nv2a_vsh_cpu, SDL2, zlib and the FEX dependencies.
The native APU includes xemu-derived components with their individual
GPL/LGPL/BSD notices; see upstream LICENSE and file headers for details.

SDL2 and the vendor graphics driver are loaded from the handheld firmware.
No vendor driver binary or firmware library is redistributed here. SDL2
source used for build headers is included; the target SDL2 system library
is supplied separately by the builder's device.

No retail game, BIOS, game save, prebuilt game shader cache or proprietary
SDK is included. Product names and the supplied Xbox menu artwork identify
compatibility; their respective owners are not sponsors of this port.
Preserve third-party copyright attribution in modified distributions.
