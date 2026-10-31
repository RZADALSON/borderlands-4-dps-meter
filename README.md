# Borderlands 4 DPS Meter

Shows your damage per second in a small window while you play. Comes with an installer, so you don't need to set up the Python SDK yourself.

[Polski opis](README.pl.md)

## Install

1. Get `Borderlands4DpsMeter-Setup-*-EN.msi` from [Releases](../../releases). There's a `-PL` one too, the only difference is the installer's language.
2. Close the game and run it. Check the game folder it found, or point it at the one with `Borderlands4.exe` in it.
3. Start the game. The meter works straight away. The in-game mod menu (F7) needs one restart of the game the first time.

Windows SmartScreen may warn you, because the installer isn't signed. The SHA-256 of each file is in the release notes.

It's fine to have [Borderlands 4 Loot Filter](https://github.com/RZADALSON/borderlands-4-loot-filter) installed as well. They share the SDK, and removing one leaves it in place for the other.

## What it shows

Your DPS, total damage, fight time, share of crit damage, best hit, kills and how your last fight went.

F6 resets it. F7 opens the settings.

## Settings

**How DPS is counted**

- Whole fight (default): damage divided by the time from your first hit to your last.
- Whole fight with pauses: the clock keeps running, so the number drops when you stop hitting things.
- Only time spent hitting: gaps longer than a second don't count.
- Last few seconds: only the damage from the last 1 to 60 seconds.

**When it resets**

By default, after 5 seconds without hitting an enemy. You can set that from 1 to 60 seconds, or only reset it yourself. "Out of combat" only means you haven't hit anything for that long. The game isn't asked if enemies are nearby.

**What counts**

Full damage by default, the same as the numbers on screen, including damage over time and companions. Each of those can be turned off. `Only health removed` counts just the health an enemy really lost. With it on, a training dummy that has run out of health counts as next to nothing.

**The window**

Four styles: like the game's UI (default), compact, text only and neon. You can also move it and change its size.

**Language**

Polish or English, following the language Steam runs the game in. If you pick one in the menu, that's saved. On Epic it starts in English.

## Limits

- It only counts your own damage.
- It works solo and when you're hosting. The game doesn't tell co-op guests about damage, so for a guest it stays at zero and says why.

## Uninstall

Windows Settings, Installed apps, Borderlands 4 DPS Meter.

If a game patch breaks the SDK and the game won't start, uninstall this or delete `OakGame\Binaries\Win64\dsound.dll`.

## Building it

You need Python with Pillow, the .NET SDK and the .NET Framework 4.7.2 Targeting Pack.

```bash
dotnet tool install wix --tool-path installer/tools --version 5.0.2
python installer/build.py
```

`installer/vendor/` needs the same files as the [loot filter's build](https://github.com/RZADALSON/borderlands-4-loot-filter#building-it).

The tests load the mod through the real `mods_base` with the engine faked:

```bash
python tests/test_dps.py . <folder with mods_base> <temp folder>
```

Keep the component IDs in `installer/src/Package.wxs` as they are. They match the loot filter's installer, which is how Windows knows the two share the SDK.

## Credits

GPL-3.0. The way it hears about damage (`native.py`) comes from Carnage Meter in [bl4-fix](https://github.com/flameaway/bl4-fix) by flameaway, GPL-3.0.

The installer also carries [Oak2 Mod Manager](https://github.com/bl-sdk/oak2-mod-manager), unrealsdk and pyunrealsdk (bl-sdk, LGPL-3.0), BL4 Mod Menu (flameaway, GPL-3.0), Python (PSF licence) and the Microsoft Visual C++ Redistributable (Microsoft's terms).

Not affiliated with Gearbox or 2K. No warranty.
