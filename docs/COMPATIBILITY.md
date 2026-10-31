# Compatibility and known issues

| Game | Observed result | Limits |
| --- | --- | --- |
| Smashing Drive | Race, steering and pause/resume confirmed | Variable speed; not full compatibility testing |
| NASCAR Thunder 2002 | Not working: startup stall or disc-read error | Under investigation; not the confirmed named-object blocker fixed for San Andreas |
| The Simpsons: Road Rage | Driving and controls confirmed | Long-session reliability remains unverified |
| Halo: Combat Evolved | Startup crash corrected; first campaign map loading reached on the named-directory core | Full campaign and long-session reliability unverified |
| Halo 2 | Campaign gameplay reached; swap helped pass a previous freeze point | Black/missing textures, pop-in, slowdowns and freezes remain possible |
| Grand Theft Auto: San Andreas | Named-semaphore creation fixed; gameplay and controls confirmed on the named-directory core | Full game and long-session reliability unverified |
| Grand Theft Auto III | Gameplay reached; 0.5× looked correct and smoother | Still slow |
| Chicago Enforcer | Startup exit corrected; first-person gameplay confirmed | Later missions and long sessions unverified |
| Test Drive | Loading failure observed at the Pong loading screen | Unresolved; not listed as working |

These are observations across development, not a full regression test of
every game on the final binary. Chicago Enforcer gameplay was confirmed on
the preceding core retained in `release/known-working`. Current core device checks are recorded in `release/DEVICE-VALIDATION.json`;
observations from earlier cores are not a full regression of this release.
Public packages contain no game saves or unlock profiles;
Halo 2 progression uses the player's own in-game save data.

## Black textures and shader cache

The Xbox NV2A renderer must be translated to Vulkan on a much smaller GPU.
Persistent black textures can involve texture formats, render-target/depth
handling, shader translation, synchronization or driver behavior. The exact
cause of each Halo 2 visual fault has not been isolated. Do not describe this
release as a black-texture fix or assume all missing surfaces are compilation.

First-time compilation can cause stutter and temporary missing draws. Caches
are created per game within the Xbox data directory. Different render scales
can generate different shader entries. Normal switching between 0.35× and
0.5× does not imply the cache is corrupt; restart the game through the menu
when applying scale changes. This package does not ship another user's caches.

## Memory and recovery

The original device has 1 GiB RAM. The core preloads at most 512 recent
pipelines at startup while retaining disk records for on-demand use. This
is not a hard limit on total memory consumption. The launcher now reuses existing swap or automatically creates a shared
512 MiB internal swap file when storage checks pass. This can help avoid
some out-of-memory exits; it can also add pauses.

The watchdog can exit after about 15 seconds of pending GPU work with no
reported completion. CPU loading or compilation without pending GPU work
does not trigger that timeout. Some driver/kernel stalls can prevent even
that recovery. No unattended or crash-free guarantee is made.

Lower resolution reduces some rendering cost; it cannot overcome every CPU,
GPU, memory or emulation limitation. FPS varies by scene and game. There is
no reliable across-the-board 30 FPS target on this hardware.

## Frame-skip preview

Off is the default. Skip 1 is display-only: the renderer and game still do
all their work, while alternate final display updates are omitted. It can
reduce final composition/upscale/FXAA work but may give little benefit if
guest rendering or CPU emulation dominates. It does not fix black textures,
loading blockers or memory exhaustion. No measured FPS gain is claimed.
