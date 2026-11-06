# Mods, cheats and screenshots

These features are included in v0.1.2.
Open the physical Menu button, then scroll down to **Mods and Cheats** or
**Take Screenshot**. Press B to go back, or Menu to resume the game.

## Screenshots

**Take Screenshot** saves a PNG of the displayed game to
`Screenshots/XBOX` on the SD card. The filename contains the title ID,
certificate version, date and a unique suffix. The settings overlay is
temporarily hidden. The unused framebuffer alpha byte is removed so PNGs
appear correctly in ordinary image viewers; RGB pixels are preserved and
PNG metadata is discarded. This uses the original TrimUI firmware's
`/usr/trimui/bin/fbscreencap` utility; firmware without that utility needs a
compatible capture implementation. It captures only when requested.

## Installing mods and cheats

The submenu displays the current game's key, for example `12345678.1`:
eight hexadecimal title-ID digits, a dot, and the decimal XBE certificate
version. Use that key for a folder under `Data/ports/hakux/mods`:

```text
Data/ports/hakux/mods/
  12345678.1/
    cheats.txt                 # optional native runtime codes
    example-mod/
      mod.txt                  # name and optional guarded XBE patches
      files/                   # optional replacement disc files
```

Exit the game before adding or replacing these files. The next launch
loads the matching catalog. The menu is available for every game, but
there is no universal cheat database: codes and patches must match that
particular game version. No game-specific mod pack, game files or enabled
choices are included in the installer. New entries default to **Off**.

No game-specific cheat or mod packs are distributed with the release or as
release downloads. Supply files you are authorized to use for your exact version.

**MOD** toggles are saved for the next launch. Save in-game, return to
settings and select **Apply settings and restart game**, then confirm.
File overlays and executable patches cannot safely be removed live.

**CHEAT** toggles take effect when gameplay resumes and persist between
launches. **Disable all cheats** stops future writes. It does not undo
changes a cheat already made to memory or saves; reloading may be needed.
`once` cheats execute once each time they are enabled. Use one potentially
conflicting mod at a time when testing, especially gravity and speed mods.
User-supplied codes can use **toggle8** to restore a flag on disable, while
ordinary writes retain their upstream behavior. No code can undo gameplay
events or save changes that happened while it was enabled.

## File formats

`mod.txt` follows the upstream Android mod format: `name:` gives the menu
label; `[default.xbe]` starts executable patches. A patch line has the form
`0xADDRESS: OLD_HEX_BYTES -> NEW_HEX_BYTES`, using a guest virtual address.
The expected old bytes are checked, and mismatches are skipped and logged.
The `files` directory mirrors paths inside the disc. Enabled mod folders
are processed in alphabetical order; overlapping mods can conflict.

`cheats.txt` uses `[Cheat name]` sections followed by native code lines.
Supported commands include `w8`, `w16`, `w32` and `wf` writes, conditional
`if8`/`if16`/`if32`/`iff`, `else`, `end`, and pointer-based addresses.
An optional `once` line selects one-time execution. Numbers are decimal
unless prefixed with `0x`. These are hakuX native codes, not an automatic
importer for unrelated trainer or Action Replay formats. The full grammar
and examples are in `source/mods/README.md` after unpacking the bundled
source snapshots.

The code engine supports `toggle8 ADDRESS VALUE` for a reversible single-byte flag
at a fixed address. It captures the original value on first use and restores
it when disabled; pointer addresses are intentionally unsupported for this
operation. Use build checks before a toggle to avoid writing to a different
executable layout. Existing `w8` codes keep their original behavior.

The menu accepts up to 64 mod folders and 256 cheat entries per game.
Keep labels short so they fit the handheld screen. Stored selections live
in each mod's `enabled` file and the game folder's `enabled-cheats` file;
omit these when sharing a pack so it starts disabled.

## Validation and limits

Host checks exercise the real native cheat/mod engine, guarded patches,
file overlays, version isolation, persistence, menu input and screenshot
requests. On an original TrimUI Smart Pro, Halo 2 boots, a title-specific
catalog displays, and the screenshot action saves a valid
1280×720 image without the overlay. The final screenshot normalization
correction passes host tests; this exact rebuilt release core has not been
gameplay-tested. Long-session stability and individual game mods need further testing.

The core also restores coarse-clock expiry, common MMIO housekeeping and
copied-buffer ordering protections removed by an earlier optimization.
It retains MMIO decoding improvements and the stereo audio default.
These corrections do not eliminate first-use guest-code translation or
shader-compilation pauses, and are not a promise of higher FPS.

To run the host regressions after unpacking source and applying the build
patches, use `python3 port/verify-vcpu-safe.py`,
`python3 port/verify-extras.py` and `python3 port/verify-menu.py`.
Also run `python3 port/verify-profiles.py`,
`python3 port/verify-cheat-toggle.py` and `python3 port/verify-png.py`.
The PNG checks cover RGB and RGBA input, all five row filters, transparent
framebuffer bytes, exact RGB preservation and metadata removal.

To package the rebuilt core:

```sh
python3 tools/package-menu-release.py --core port/dist/hakux.aarch64
```

The output is `release/xbox-trimui-smart-pro-v0.1.2.zip`. Copy its
`Data` and `Emus` directories to the SD card root, merging folders with the
game closed. Existing settings, saves and user-supplied files are preserved.
Keep a known working build available while testing.
