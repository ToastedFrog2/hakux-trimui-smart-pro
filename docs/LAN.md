# Local System Link (LAN)

Version 0.1.2 adds **LAN: Off / Connections on the network** to the Xbox
settings menu. It exposes hakuX's existing Ethernet-over-UDP backend.

1. Connect both handhelds to the same local network. Avoid a guest Wi-Fi
   network with client isolation; devices must be allowed to communicate.
2. Install v0.1.2 on both devices and use matching versions of a
   game that supports Xbox System Link.
3. Open a game and press the physical Menu button. Select **LAN**, then
   **Connections on the network**. Choose **Apply settings and restart game**
   and confirm. Save your progress first: restarting reloads the game.
4. After restarting, use the game's **System Link** menu to host on one
   device and join from the other. The LAN choice persists for this game.
5. To disable networking, select **LAN: Off**, apply and restart again.

LAN defaults to **Off** on a fresh installation. Picture settings remain live;
render scale and LAN require a restart. Saves, shader caches and button
mappings are preserved by the update. The menu scrolls to show all settings.

## Compatibility and troubleshooting

- The tunnel uses **UDP port 3075** on each device and broadcasts for discovery.
  Allow this traffic on the local network. Router port forwarding is not
  needed for devices on the same LAN.
- Both games must support System Link and use compatible game versions/updates.
  Local packet transport does not guarantee that a game's networking works in
  the emulator. Full two-console gameplay has not yet been verified.
- This is not Xbox Live/Insignia or internet matchmaking. Physical Xbox consoles
  do not speak this UDP tunnel directly. Other emulators need a compatible
  Ethernet-over-UDP tunnel configured to the same port.
- Each emulated console needs a different MAC address. Fresh installations
  generate their own identity; avoid copying `hdd/eeprom.bin` between devices.
- The log is `Data/ports/hakux/log.txt`. A line starting
  `lan: UDP port 3075` shows that the backend initialized. A successful socket
  initialization alone does not establish a working multiplayer session.

## Build and package

Build the core with the repository's normal source build instructions, then:

```sh
python3 port/verify-menu.py
python3 tools/package-menu-release.py --core port/dist/hakux.aarch64
```

This writes `release/xbox-trimui-smart-pro-v0.1.2.zip` and its checksums. It includes
one Xbox emulator, no ROMs, and no saved user settings. To test the underlying
UDP backend on a Linux host, compile `port/tests/lan.c` with `-UNDEBUG` and
`-Iport/source`, then run it; this test exchanges frames with a local UDP peer.
