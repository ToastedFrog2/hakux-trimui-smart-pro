# Per-game settings

Version 0.1.2 stores controller mapping, picture settings, display frame
skip, render scale and LAN mode separately for each title and XBE certificate
version. The menu shows **Game settings: TITLEID.VERSION** so you can see
which profile you are editing. Game identity comes from the original disc's
certificate; renaming a disc image or using a temporary SquashFS mount does
not change it.

Profiles live on the SD card under:

```text
Data/ports/hakux/profiles/TITLEID.VERSION/
  controller-map
  menu-settings
  render-scale
  network-mode
```

Existing global settings files remain the starting defaults for any setting
without a per-game override. New menu changes write only to the current game
profile. A fresh install starts with the original controller layout, 0.5×
scale, frame skip Off and LAN Off. No personal profiles are included in the
installer. The runtime still pauses music and closes/restores MainUI and the
OSD for every game; that behavior is not a per-game option.

Picture settings, frame skip and controller mapping apply when resuming.
Scale and LAN mode require **Apply settings and restart game**, with the
existing confirmation. Save in-game first. Profiles load before renderer and
network initialization. The launcher's shared restart signal stays separate
from the per-game files.

To reset a game's overrides, close the game and remove just that game's
`profiles/TITLEID.VERSION` folder. Its next launch inherits the installation
defaults. This does not remove saves or the game's separate mods/cheat choices.

Host regressions use synthetic Xbox discs with matching title IDs and
different certificate versions to check isolation, inheritance, early scale
and LAN loading, validation and descriptor ownership. Menu tests also check
that changing one game's controls and picture settings preserves another
game's settings and the shared defaults.
