# Historical keymap audit — 2026-09-21

**Archived snapshot, superseded by the September 24 changes.** The behavior descriptions and test/build status below record an earlier iteration. For current controls, use the [keyboard guide](keyboard-guide.md) and [generated keymaps](keymaps.md). In particular, modifiers now double-tap to lock, holds remain momentary, physical `$` is Tab, and right aA is UPPER.

---

**Keymap audit and preferred gestures — 2026-09-21**

This records the unusual behavior found in the original keymap and the changes implemented in the [user keymap](../config/zitaotech_q10.keymap). The original review covered all four layers, all eight original custom behaviors, both original combos, and the driver interactions that affect these keys. Some remappings are intentional; they are listed because they are easy to misinterpret.

Status: the revised gestures and shortcuts are implemented and tested in source. Both firmware targets build successfully, and native gesture checks pass. This session has not flashed the keyboard or inspected saved Studio remappings. The numbered inventory below is explicitly a **before-change snapshot**; use the [keyboard guide](keyboard-guide.md) for the current controls.

**Implemented behavior**

| Key class | Single tap | Double tap | Press and hold | How it ends |
| --- | --- | --- | --- | --- |
| Ctrl, Shift, Alt, Command / GUI | Ordinary modifier press; does not arm a sticky modifier | Apply the modifier to the next key only | Ordinary momentary modifier; active while physically held | Next-key use consumes the one-shot; releasing a held modifier ends the hold |
| SYM / layer 1 | Use SYM for the next key; tap again to exit persistent SYM | Keep SYM active across multiple keys | Enter SYM and keep it active after release | One-shot use ends after the next key; persistent use ends when SYM is pressed again |
| Right aA / Alt while SYM is persistent | Use UPPER for the next key; tap again to exit persistent UPPER | Keep UPPER active across multiple keys | Enter UPPER and keep it active after release | Return to the persistent SYM parent when UPPER ends |
| SYM + right aA / Alt chord | Use UPPER for the next key | Keep UPPER active across multiple keys | Enter persistent UPPER | Right aA exits UPPER; SYM exits both layers. Return to SYM only if it was already persistent |

Right aA acts as Alt on the base layer and during one-shot SYM. Its layer-key role starts when SYM is persistent, or when it is part of the SYM + right aA combo. Ctrl, Shift, Alt, and Command never become persistent through holding.

- **Tap SYM, then Space to send Escape.** Space is Escape on the SYM layer, so the presses can be sequential or held together. The simultaneous 50 ms combo also remains. Space in persistent SYM keeps sending Escape until SYM is exited.
- **Ctrl + $/; sends Tab. Command + Ctrl + $/; sends Command+Tab.** Ctrl is the bottom-left aA key. Command is physical `0` on DEFAULT. The Tab override works on DEFAULT, SYM, and UPPER without a combo timing window; it suppresses Ctrl while preserving other modifiers. The older SYM + Enter Tab combo remains. SYM + right aA controls UPPER, not Tab.
- Holding the physical **Alt-labeled key, now Shift**, turns trackpad motion into vertical scrolling using the existing Caps Lock scroll path. Release resumes pointer motion. Host Caps Lock still provides its original scrolling mode.
- Modifier double taps use 250 ms; layer double taps and persistent holds use 400 ms. Unused one-shot modifiers expire after 1 second; one-shot layers after 3 seconds. Modifiers do not consume one-shot layers. Device controls and mouse actions do not consume them either.
- Sticky modifiers use `quick-release` to avoid spilling into a second overlapping key. Shift, Alt, and Command use `lazy`; Ctrl has a separate eager one-shot so the Tab override recognizes it before a keycode is emitted. A single tap still sends an ordinary modifier pulse to the host.
- Tap SYM + right aA once for one-shot UPPER. Double-tap the complete chord or hold it for 400 ms for persistent UPPER. The easier sequential route is to double-tap SYM, then tap right aA for one UPPER key or double-tap it to stay in UPPER.
- The first layer press activates one-shot use immediately. A second tap within 400 ms upgrades the unused one-shot to persistent use; a later tap cancels it. Using the one-shot before the hold threshold cancels the pending hold, so it cannot unexpectedly become persistent afterward.
- Shift with SYM's N/M positions produces `<`/`>` on the tested host layout. The user confirmed this route works, so those punctuation bindings were retained.

These rules live in [gestures.dtsi](../config/gestures.dtsi) and the [custom layer behavior](../config/boards/arm/zitaotech_q10/custom_driver/behavior_layer_key.c). A shared state machine handles one-shot expiry, persistent entry, cancellation, and returning to the correct parent. Entering persistent UPPER from one-shot SYM also clears the old SYM timer.

These are two different lifetimes: a **one-shot** applies to the next key, while a **persistent layer** remains active until explicitly exited. ZMK calls the former [sticky keys](https://github.com/zmkfirmware/zmk/blob/v0.3.0/docs/docs/keymaps/behaviors/sticky-key.md) and [sticky layers](https://github.com/zmkfirmware/zmk/blob/v0.3.0/docs/docs/keymaps/behaviors/sticky-layer.md). A persistent layer is not saved as the startup layer across reboots.

**Original modifier and layer mismatches — before the changes**

Physical positions below are zero-based. The physical Alt key is position 27; bottom-left aA is 37; physical 0 is 38; SYM is 40; right aA / ↑ is 41. See the [full maps](keymaps.md) for every position.

| # | Location | Original behavior | Why it was surprising or conflicted with the requested rules |
| --- | --- | --- | --- |
| 1 | Shift, Ctrl, Command, Alt wherever assigned | Ordinary `&kp` modifiers; holding is momentary | No assigned modifier supports double-tap one-shot operation. |
| 2 | DEFAULT SYM (40) | `&sl 1`: one tap immediately activates SYM and leaves it armed after release | Single-tap one-shot entry now matches the revised preference, but the original binding did not support double-tap persistent entry. |
| 3 | DEFAULT SYM held | If another eligible key is used while SYM is held, releasing SYM exits the layer. If no eligible key is used, release arms the one-shot timeout | There is no long-press-to-persist gesture. Even an unused long hold can leave a temporary one-shot after release. |
| 4 | SYM right aA (41) | `&sl 2`: one tap arms UPPER | UPPER used single-tap one-shot entry. The final rules give UPPER the same double-tap/hold semantics as SYM. |
| 5 | DEFAULT right aA (41) | Plain Tab | UPPER has no direct entry from the base layer. Its normal route is SYM, then right aA. |
| 6 | SYM pressed again while SYM is active | `&mo 1`: enable SYM while held, deactivate on release | The same physical key changes from sticky entry to momentary control. It is not an explicit persistent-mode exit and does not count double taps. |
| 7 | Double-tapping original layer keys | No active `td1` or `td2` binding | Their double-tap definitions existed but were unused. After the first press changed layers, the second press could encounter a different binding: SYM had `&mo 1`, and UPPER right aA had `&to DEFAULT`. |
| 8 | UPPER SYM (40) | `&to SYM`: one press switches to SYM and clears other nondefault layers | This is single-press persistent entry, unlike the one-shot entry from DEFAULT. The SYM hold/double-tap rule needs to cover this route too if applied consistently. |
| 9 | UPPER right aA; MEDIA $, SYM, right aA | `&to DEFAULT` | These are explicit exits to the base layer, not “go back one layer.” |
| 10 | Sticky layer timeout | Both sticky layers share `release-after-ms = <3000>` | A forgotten layer can affect a key up to three seconds after release. This does not set a double-tap or long-press threshold. |
| 11 | Sticky layer followed by a modifier | Original `&sl` did not ignore modifier keycode events | Tapping SYM and then Shift or Ctrl could consume SYM before the intended symbol key was pressed. |
| 12 | Sticky layer followed by a device or mouse action | Bluetooth selection, lighting, mouse clicks, and wheel actions do not generate the keycode events that consume the sticky layer | “One next key” is not literally any physical button in this configuration. The layer can remain active until its timer or a qualifying keycode ends it. |
| 13 | Mixing `&sl`, `&mo`, and `&to` | v0.3.0 sticky timers and momentary releases can still deactivate the layer they enabled | For example, entering SYM with `&sl`, proceeding to UPPER, then using `&to SYM` can leave an earlier SYM timeout pending. A persistent switch is not protected from that earlier timeout. |

The layer lifetime observations above were checked against the pinned [v0.3.0 sticky behavior implementation](https://github.com/zmkfirmware/zmk/blob/v0.3.0/app/src/behaviors/behavior_sticky_key.c) and [layer definitions](https://github.com/zmkfirmware/zmk/blob/v0.3.0/docs/docs/keymaps/behaviors/layers.md). Newer ZMK documentation describes layer-locking features that should not be assumed to exist in this pinned version.

**Other original surprises — before the changes**

Most of these bindings remain. Exceptions: finding 23's Caps Word combo was replaced with the UPPER gesture chord; there are now four global combos (24); base-layer Alt is available (25); and Escape has a new shortcut (29). Modifier and layer gesture timings now follow the table above (31).

| # | Location | Original behavior | Consequence |
| --- | --- | --- | --- |
| 14 | UPPER trackpad click (4), `td0` | One press = left mouse click; two presses within 400 ms = `BT_CLR` | A double-click gesture clears the selected Bluetooth profile's pairing. A lone click can wait for the dance to resolve. This applies on UPPER, not DEFAULT. |
| 15 | UPPER $ (35), `td_boot_out` | One press = bootloader; two presses within 400 ms = USB/Bluetooth output toggle | The ordinary single-press action leaves normal keyboard operation for flashing. A slow attempted double press can select bootloader instead of output switching. Another keypress can resolve the single action early. |
| 16 | UPPER R (10) and T (11) | Single-press normal reboot and external-power toggle respectively | These familiar letter positions become immediate device controls. Reboot does not clear settings; the external-power control is used for the trackpad. |
| 17 | SYM $ (35), `tdc_to_MEDIA` | One press = audio mute; double press = persistent MEDIA | Repeating mute quickly switches layers instead of sending two mute presses. A lone mute press can wait up to the 400 ms dance interval. |
| 18 | MEDIA | 39 of 42 positions are `&none`; the remaining three return to DEFAULT | The “media” layer has no assigned media controls. Ordinary typing, modifiers, and mouse-button keys are mostly disabled there. Global combos still operate. |
| 19 | DEFAULT $ (35) | `&mt DLLR SEMI`: tap semicolon, hold dollar | A key named mod-tap chooses between two punctuation characters here. It is not a modifier or a layer key. |
| 20 | SYM T/Y (11/12) | Tap `(`/`)`; hold `[`/`]` | The same punctuation-versus-punctuation hold-tap pattern is used for brackets. |
| 21 | All three assigned `&mt` punctuation keys | Built-in 200 ms, `hold-preferred` | Pressing another key before releasing the punctuation key can choose its hold character even before 200 ms. Rolling `;` into the next key can therefore produce `$`. |
| 22 | Enter (36) + bottom-left aA / Ctrl (37) | `alt_enter_tab` emits Tab when the presses form a combo within 50 ms | This is physically Enter + Ctrl in the current map, despite its name. Near-simultaneous Ctrl+Enter can become Tab. The physical Alt key is not part of it. |
| 23 | SYM (40) + right aA (41) | `CAPS_SCROLL` emits Caps Word within a 50 ms combo window | Pressing the two layer-navigation positions together can activate Caps Word instead of entering UPPER. Caps Word capitalizes a word; it is neither Caps Lock nor scrolling. |
| 24 | Both combos | No `layers` restriction, no explicit timeout, no prior-idle guard | They use the default 50 ms window on every layer, including MEDIA. Changing or disabling a layer's individual bindings does not disable these combos. |
| 25 | Physical Alt (27), left aA (37), physical 0 (38) | Alt is Shift; left aA is Ctrl; 0 is Command on DEFAULT, digit 0 on SYM, Alt on UPPER | Keycap labels and modifier availability vary across layers. There is no ordinary Alt on DEFAULT and no Command on SYM or UPPER. |
| 26 | DEFAULT navigation row | Call = Left, BlackBerry = Up, Back = Down, End call = Right; middle click remains left mouse | The physical labels no longer describe their actions. DEFAULT also has a second left-click on the left shoulder. |
| 27 | Shoulder keys | DEFAULT: left/right click; SYM: volume up/down; UPPER: scroll up/down | Mouse, volume, and scrolling share the same physical controls depending on the active layer. |
| 28 | UPPER navigation row | Four positions select Bluetooth profiles 0–3 | Positions used for base arrows become host-selection controls. A single press changes the selected profile. |
| 29 | Escape, Delete, Caps Lock, function/navigation keys | Escape and Delete are on SYM; no assigned Caps Lock, F1–F12, Home/End, or Page Up/Down | These common controls have limited or no direct access. In particular, Caps Word cannot replace Caps Lock for the trackpad's scroll mode. |
| 30 | UPPER disabled keys; every layer | Six UPPER positions use `&none`; there are no `&trans` bindings anywhere | Disabled keys block the corresponding base key instead of passing through. Higher layers spell out every available action. |
| 31 | Gesture timing | Active tap dances use 400 ms; active punctuation hold-taps use 200 ms; unused helpers use 400 or 500 ms | There is no single global gesture interval. Editing an unused helper's timing will not change the active keys. |

These behaviors follow the actual bindings, [tap-dance resolution](https://github.com/zmkfirmware/zmk/blob/v0.3.0/docs/docs/keymaps/behaviors/tap-dance.mdx), [hold-tap rules](https://github.com/zmkfirmware/zmk/blob/v0.3.0/docs/docs/keymaps/behaviors/hold-tap.mdx), and [combo scope](https://github.com/zmkfirmware/zmk/blob/v0.3.0/docs/docs/keymaps/combos.md). A tap dance resolves on timeout or interruption; a two-action dance chooses its second action on the second press.

**Definitions that look active but are not assigned**

Of the original eight custom behaviors, only `td0`, `td_boot_out`, and `tdc_to_MEDIA` were assigned to positions. They remain in use; the latter two are now the non-Ctrl fallbacks of the Tab overrides. The five old helpers and macro below remain unused; the new modifier and layer gestures are defined separately in `gestures.dtsi`.

| Definition | What it actually says | Why it is misleading |
| --- | --- | --- |
| `td1` | One tap = sticky SYM; double tap = persistent SYM | Not used by the SYM key. Its tap actions resemble the revised preference, but it does not provide the current hold, exit, and timer management. |
| `td2` | One tap = sticky UPPER; double tap = persistent UPPER | Not used by right aA. Current UPPER gestures come from `upper_key`, not this helper. |
| `sk_kp` | Hold = normal key press; single tap = sticky key | Unused and uses single-tap stickiness, whereas the requested modifier gesture is double tap. |
| `tdc_to_SYM`, node `td_comma_to_layer` | Single action is `&mt DLLR SEMI`; double is `&to SYM` | Unused; despite the node's name, its ordinary character is semicolon, not comma. |
| `hm`, node `homerow_mods` | Hold = output selection (`&out`); tap = key press | Unused; it does not implement home-row modifiers. |
| `SL_TO(layer)` | Expands to `&sl_to layer layer` | Unused and references a nonexistent `sl_to` behavior. Using the macro would require defining that behavior or changing the macro. |

**Related driver and configuration surprises**

These are outside the keymap file but explain the visible effects of its controls.

| Finding | Source and effect |
| --- | --- |
| Ctrl changes trackpad speed | [a320.c](../config/boards/arm/zitaotech_q10/custom_driver/a320.c) halves raw movement while Ctrl is active, before subsequent scaling. A held Ctrl chord can therefore affect pointer movement too. |
| Caps Lock changes pointer motion into scrolling | The driver still checks the host Caps Lock indicator and emits vertical scroll instead of pointer motion. There is no Caps Lock binding. The old `CAPS_SCROLL` combo emitted Caps Word, not Caps Lock; it has now been replaced with the UPPER gesture chord. Holding physical Shift now also enables the driver's scroll path. |
| Physical Shift scrolling also sends keyboard Shift | Some applications reinterpret Shift + vertical wheel as horizontal scrolling. The firmware emits vertical wheel reports, but this host behavior needs a device check. UPPER's shoulder scroll keys provide wheel actions without requiring a held Shift. |
| “Backlight” controls also influence pointer speed | UPPER V/N use `&bl BL_DEC` / `BL_INC`. [trackpad_led.c](../config/boards/arm/zitaotech_q10/custom_driver/trackpad_led.c) reads that brightness state; the motion driver uses remembered indicator brightness to scale movement. |
| Keyboard lighting is controlled through RGB state and layers | UPPER C/M/B change RGB brightness/on-state. [keyboard_backlight.c](../config/boards/arm/zitaotech_q10/custom_driver/keyboard_backlight.c) uses this state for base lighting and selects blinking/breathing patterns by layer. Layer animations are not simple reflections of the RGB on/off setting. |
| Trackpad tuning names can promise more than the driver implements | The declared scroll-interval and horizontal/vertical speed-multiplier settings in [the user configuration](../config/zitaotech_q10.conf) are not read by the current motion handler; its scaling and scroll division are implemented directly. |
| There are two different keymap files | [The board fallback](../config/boards/arm/zitaotech_q10/zitaotech_q10.keymap) retains different assignments. The normal user-config build uses `config/zitaotech_q10.keymap`; inspecting or editing only the fallback can give the wrong picture. |
| Saved mappings can differ from source | Studio is enabled in the user configuration. This audit does not inspect any runtime remapping stored on the physical device. |

**Remaining usability suggestions**

- Move pairing clear away from a trackpad double-click and bootloader away from a single tap. These are the two most disruptive remaining accidental actions (14–15).
- Remove or populate MEDIA: double-tapping mute currently enters a layer with almost every key disabled (17–18).
- Consider removing the old Ctrl + Enter → Tab combo now that Ctrl + $/; provides Tab. The old combo still intercepts a near-simultaneous Ctrl + Enter (22).
- Release $/; before starting another Ctrl shortcut. ZMK's modifier-dependent behavior suppresses Ctrl until that key is released, so another letter rolled into the same hold also loses Ctrl. The host-report tests verify restoration after release and continuous Command during repeated Tabs.
- If simultaneous shortcuts feel hard to trigger, tune the 50 ms combo window after physical testing. A larger window also makes accidental combos more likely.
- If punctuation changes unexpectedly during fast typing, revisit the three 200 ms hold-preferred punctuation keys (19–21). Their overlap behavior is independent of the new layer gestures.
- Prefer persistent SYM followed by right aA for UPPER if double-tapping the complete two-key chord feels cumbersome. The two routes have the same resulting layer lifetime.

These suggestions are recorded for review; they have not been remapped by this change.

**Validation**

The source checkout matches the `v0.3.0` pin in [west.yml](../config/west.yml), commit `edf5c0814fd3ea202e43aad2d68fd32e882a518c`. [The native gesture checks](../tests/check_gestures.py) exercise the production bindings across all four layers and capture actual HID reports. They cover single-tap one-shots, double-tap persistence, modifier release balance, overlapping keys, one-shot expiry, sequential Escape, Ctrl+$ Tab across the three typing layers, continuous Command during repeated Tabs, both modifier and release orders, and stale timer replacement. [The test notes](../tests/README.md) document the timing ranges and research sources. Both firmware targets build successfully. Documentation generation and freshness checks are also run. This session has not flashed firmware; physical scanning, Bluetooth/USB delivery, and host behavior still need a device check.
