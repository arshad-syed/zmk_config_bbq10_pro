# zmk_config_bbq10_pro
This page contains zmk firmware config for bbq10 keyboard pro

## Current controls

- Physical `$`: **Tab**. **SYM + `$`** types `$`.
- Bottom-right aA / ↑: **UPPER**. **UPPER + Backspace** sends Escape; tap UPPER, then Backspace also works with one finger.
- Shift, Ctrl, Alt, and Command: hold for ordinary chords; double-tap to lock; tap again to unlock.
- SYM and UPPER: tap for one use, hold for a chord, double-tap to lock. Holding never locks.
- Command + SYM + M sends Command + period. On held SYM, physical `0` remains Command; tapped or locked SYM gives digit `0`.
- UPPER + `$` keeps bootloader/output switching. Mute/MEDIA moved to UPPER + E.

## Keyboard documentation

- [Historical keymap audit](docs/keymap-audit.md): the September 21 snapshot, retained as history; current controls are in the guide below.
- [Complete behavior and configuration guide](docs/keyboard-guide.md): plain-language definitions, tap/hold/one-shot/double-tap recipes, timing, combos, and interaction diagrams.
- [Complete HTML guide](docs/keyboard-guide.html): open locally in a browser; includes offline diagrams and the manufacturer comparison.
- [Color-coded keymaps for all four layers](docs/keymaps.md): every physical position, exact binding, and explanation.
- [Interactive keymap viewer](docs/keymaps.html): open locally in a browser to switch layers, expand binding tables, or print all four maps.

The documentation describes the current user keymap. Regenerate the entire documentation set (Markdown, HTML, configuration reference, and SVG diagrams) with:

```sh
python3 -m pip install -r docs/requirements.txt
python3 docs/generate_docs.py
```

Check that generated files are current without rewriting them:

```sh
python3 docs/generate_docs.py --check
```

The renderer version is pinned; generation is offline and deterministic. Edit `docs/templates/keyboard-guide.md.in` for narrative changes. Bindings, timing, combo definitions, and settings are read directly from configuration. The old `docs/generate_keymaps.py` command remains an alias for full generation.

<p align="center">
<img width="800" alt="image" src="https://github.com/user-attachments/assets/e1e959c9-8ee6-4ef4-9ea9-cb80f5779503" />
</p>

### Use this repo to generate your own ZMK keymap for the bbq10 Pro keyboard.  
## Get started  
```Option1```   
**0. Register a github account if you don't have one.**  
**1. Fork this repo.**  

<p align="center">
<img width="600" alt="image" src="https://github.com/user-attachments/assets/e576fd0b-678e-4323-a580-c01299bf4f5f" />
</p>

**2. Open up `config/zitaotech_q10.keymap` and edit the keymap to your liking.**  
**3. After editing the keymap, choose commit changes.**  
**and then check the ```Github Actions``` section.**  

<p align="center">
<img width="600" alt="image" src="https://github.com/user-attachments/assets/4da91dd7-5766-4a3d-8edc-27eb10ade472" />
</p>

**Your new firmware file should be available for download.**  
**5. Unzip the firmware.zip file. You should see files: `zitaotech_q10-zmk.uf2` and  `settings_reset-zitaotech_q10-zmk.uf2`**  
**6. Flash the keyboard with your new firmware:`zitaotech_q10-zmk.uf2.`**  

```Option2```  
**0. Register a github account if you don't have one.**  
**1. Fork this repo.**  
**2. Access the [keymap editor web](https://nickcoutsos.github.io/keymap-editor/)**  
**3. Login with your Github Account on the web**  
**4. Choose the right repository and you can edit the keymap more intuitivly**  

<p align="center">
<img width="800"  alt="image" src="https://github.com/user-attachments/assets/f0cb0fee-396a-4f53-b64d-b29fb8883069" />
</p>

**5. After editting the keymap there will be another github action compiling and you will have the firmware.zip file**  
**6. Flash the keyboard with your new firmware.**  

**More Info about the web app please access this [github page](https://github.com/nickcoutsos/keymap-editor)**  

## Build your own driver
You can change the source code under the ```/config/boards/arm/zitaotech_q10/custom_driver```

For example if you want to change the scroll direction when capslock is activated:
Go to this [line](https://github.com/ZitaoTech/zmk_config_bbq10_pro/blob/main/config/boards/arm/zitaotech_q10/custom_driver/a320.c#L241) and change ```dy``` to ```-dy```

## Build locally

Start Docker (for example, Docker Desktop or OrbStack), then run:

```sh
./build-local.sh
```

The script reads the targets from `build.yaml` and builds the current local config
using the official ZMK container and the ZMK version pinned in `config/west.yml`.
The first run downloads the container and source dependencies. Build files and
cached dependencies are kept in `.build/`.

The resulting files are:

- `firmware/zitaotech_q10-zmk.uf2` — keyboard firmware to flash.
- `firmware/settings_reset-zitaotech_q10-zmk.uf2` — firmware for clearing stored settings.

Both output directories are ignored by Git.

After the build dependencies are cached, run the modifier and layer gesture checks with:

```sh
python3 tests/check_gestures.py
```

These checks run the production gesture definitions in ZMK's native mock keyboard through Docker and verify actual HID reports across varied press timings and release orders. [Test coverage and limitations](tests/README.md) explain the checks and their limits. Physical trackpad behavior and host-specific shortcuts still need a device check.
