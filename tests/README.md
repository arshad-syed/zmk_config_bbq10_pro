# Keyboard gesture checks

Run `python3 tests/check_gestures.py` after `./build-local.sh` has cached the pinned ZMK sources and Docker image. The script compiles the production gesture implementation, definitions, and actual bindings in ZMK's native mock keyboard. Its fixture includes twelve physical positions and all four layers; the other positions are outside this fixture.

Production firmware and the native fixture share `custom_driver/gestures.cmake`. The native-only `native_report_sink.c` adapter captures actual keyboard reports at `zmk_endpoints_send_report`, after modifier masking. Expected HID keycodes and modifier masks are specified independently in the scenarios. Checks require balanced modifier releases, no extra keypresses, an empty final report, no firmware errors, and uninterrupted Command across repeated Command+Tab presses.

The executable runs with `--no-rt`: firmware timers observe simulated milliseconds without waiting for wall-clock time. Fixtures and detailed traces remain in `.build/gesture-tests`; native build outputs are in `.build/build/gesture-tests`.

## Coverage

| Interaction | Checks |
| --- | --- |
| Immediate modifier and Tab activation | Isolated Shift, Ctrl, Command, and Tab activate within 5 ms of the mock scan event, before another key can resolve a delayed behavior |
| Modifier lifetime | Ordinary pulse/hold, persistent double-tap lock, independent unlock, idle persistence, long hold followed by a tap, and interrupted double taps |
| Multi-modifier chords | Every two- and three-modifier press permutation on DEFAULT and UPPER; 10/80/300 ms gaps; matching and reverse releases; partial releases; combinations of locks |
| Command+Tab | Held or locked Command stays down across repeated direct Tabs; Shift reverses the chord without releasing Command |
| Layers | Single use, held multiple keys at 40–4000 ms, no hold-to-lock, unused long hold, double-tap lock, cancellation, expiry, and rapid re-entry |
| Sequential dollar/Escape | Layer press durations 40/116/250 ms and delays 20–2800 ms; SYM+$ sends dollar, UPPER+Backspace sends Escape; each consumes one-shot use |
| Command+SYM | Both press/release orders with 10/80/700 ms gaps; repeated periods; all 24 press orders of Command+Ctrl+Shift+SYM |
| Contextual physical 0 | Command on held SYM; digit 0 on tapped/locked SYM; Alt on UPPER; matching release when SYM ends first |
| Nested layers | Both hold/release orders, locked parent with one-shot/locked child, explicit parent exit, and replacement of a transient parent's old timer |
| State recovery | Layer ends before Escape is released; dollar's implicit Shift preserves explicit held Shift; all four modifiers active together; unlocking a modifier between layer taps cancels layer locking |

Modifier double taps use 250 ms and layer double taps use 400 ms, measured first key-down to second key-down. Layer taps expire unused 3000 ms after release. Timing variations are engineering stress cases, not measured human percentiles. The custom modifier/layer behavior activates on press; built-in tap dances remain only for the three device-action bindings. See the [current guide](../docs/keyboard-guide.md) for operating instructions.

## Limits

These checks run after scanning. They do not simulate the physical matrix, debounce, USB/Bluetooth transport, trackpad, or a host application's shortcuts. The manufacturer documents that the Q10 matrix has no diodes and lacks n-key rollover, so firmware passing every received chord cannot guarantee that every physical combination is detected. Sequential modifier locks and one-shot layers provide alternatives to simultaneous presses. [Manufacturer hardware description](https://github.com/ZitaoTech/BBQ10_Keyboard_Pro).

Bootloader, pairing-clear, reset, lighting, and MEDIA actions are present in the production configuration but are not invoked by the HID suite. The complete board firmware build validates those bindings. Physical testing on each flashed keyboard is still needed for matrix combinations, trackpad behavior, and host-specific shortcuts.
