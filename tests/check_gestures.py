#!/usr/bin/env python3
"""Exercise production gestures with ZMK's native mock keyboard, using cached .build sources.

Run: python3 tests/check_gestures.py
Requires Docker and the dependencies populated by build-local.sh.
"""

from collections import Counter
from itertools import permutations
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'docs'))
from doc_model import Model, body
from generate_keymaps import KEYS, PHYSICAL

CACHE = ROOT / '.build'
FIXTURE = CACHE / 'gesture-tests'
FIXTURE.mkdir(parents=True, exist_ok=True)
model = Model(ROOT, KEYS, PHYSICAL)

# Keep actual assignments and combo definitions in a compact mock.
positions = [40, 27, 37, 38, 39, 41, 8, 17, 36, 35, 34, 26]
SYM, SHIFT, CTRL, GUI, SPACE, UPPER, W, A, ENTER, DOLLAR, M, BSPC = range(12)
events, expected, command_spans, immediate_checks = [], [], [], []


def down(key, wait=10):
    events.append(f'ZMK_MOCK_PRESS({key // 3}, {key % 3}, {wait})')


def up(key, wait=10):
    events.append(f'ZMK_MOCK_RELEASE({key // 3}, {key % 3}, {wait})')


def tap(key, wait=20, hold=10):
    down(key, hold)
    up(key, wait)


def double(key):
    tap(key, 40)
    tap(key, 20)


def output(key, code, mods, case, wait=500, hold=10):
    tap(key, wait, hold)
    expected.append((code, mods, case))


# Activation latency is measured before another key can interrupt the behavior.
for key, mask in ((SHIFT, 2), (CTRL, 1), (GUI, 8)):
    immediate_checks.append((len(events), mask, None))
    down(key, 700)
    up(key, 700)
immediate_checks.append((len(events), 0, 0x2B))
output(DOLLAR, 0x2B, 0, 'base dollar position is immediate Tab')
for dwell in (10, 80, 116, 350, 700):
    output(DOLLAR, 0x2B, 0, f'Tab remains Tab with {dwell} ms hold', hold=dwell)
output(BSPC, 0x2A, 0, 'base Backspace is unchanged')
down(CTRL, 20)
output(ENTER, 0x28, 1, 'Ctrl+Enter is an ordinary shortcut')
output(DOLLAR, 0x2B, 1, 'direct Ctrl+Tab preserves Ctrl')
up(CTRL, 300)

# Momentary, persistent, cancellation, and independent modifier lifetimes.
for key, modifier, name in [(SHIFT, 2, 'Shift'), (CTRL, 1, 'Ctrl'), (GUI, 8, 'Command')]:
    tap(key, 300)
    output(W, 0x1A, 0, f'single {name} is not locked')
    double(key)
    output(W, 0x1A, modifier, f'double {name} locks', wait=3200)
    output(A, 0x04, modifier, f'{name} lock survives keys and idle time')
    tap(key, 300)
    output(W, 0x1A, 0, f'tap unlocks {name}')
    down(key)
    output(W, 0x1A, modifier, f'held {name} works immediately', 10)
    output(A, 0x04, modifier, f'held {name} modifies multiple keys', 10)
    up(key, 100)
    output(W, 0x1A, 0, f'releasing {name} ends the hold')
    down(key, 700)
    up(key, 20)
    tap(key, 300)
    output(W, 0x1A, 0, f'a long hold followed by a tap does not lock {name}')
    tap(key, 20)
    output(W, 0x1A, 0, f'letter separates {name} taps', wait=20)
    tap(key, 20)
    output(A, 0x04, 0, f'interrupted {name} taps do not lock')
    for dwell, interval, locked in ((40, 150, True), (100, 230, True), (100, 280, False)):
        tap(key, interval - dwell, hold=dwell)
        tap(key, 300, hold=dwell)
        output(W, 0x1A, modifier if locked else 0, f'{name} double-tap interval {interval} ms')
        if locked:
            tap(key, 300)
        output(A, 0x04, 0, f'{name} timing case leaves no lock')


def modifier_chords(modifiers, code):
    for count in range(2, len(modifiers) + 1):
        for order in permutations(modifiers, count):
            names = '+'.join(modifiers[key][1] for key in order)
            for gap in (10, 80, 300):
                for release_order in (order, order[::-1]):
                    held_mods = sum(modifiers[key][0] for key in order)
                    for key in order:
                        down(key, gap)
                    output(W, code, held_mods, f'held {names}, {gap} ms spacing', 10)
                    for key in release_order:
                        up(key, gap)
                        held_mods &= ~modifiers[key][0]
                        output(W, code, held_mods, f'{names}: release {modifiers[key][1]}', 10)
                    output(W, code, 0, f'{names}: all holds released')
            for key in order:
                double(key)
            locked_mods = sum(modifiers[key][0] for key in order)
            output(W, code, locked_mods, f'locked {names} combine', 3200)
            output(W, code, locked_mods, f'locked {names} survive typing and idle')
            for key in order:
                tap(key, 20)
                locked_mods &= ~modifiers[key][0]
                output(W, code, locked_mods, f'{names}: unlock only {modifiers[key][1]}')


modifier_chords({SHIFT: (2, 'Shift'), CTRL: (1, 'Ctrl'), GUI: (8, 'Command')}, 0x1A)
for locked in (False, True):
    if locked:
        double(GUI)
    else:
        down(GUI, 120)
    command_start = len(expected)
    for _ in range(3):
        output(DOLLAR, 0x2B, 8, 'Command remains active across repeated Tabs', 80, hold=116)
    down(SHIFT, 80)
    output(DOLLAR, 0x2B, 10, 'Shift reverses Command+Tab', 80)
    up(SHIFT, 80)
    output(W, 0x1A, 8, 'releasing Shift preserves Command')
    command_spans.append((command_start, len(expected) - 1, 'held or locked Command+Tab'))
    if locked:
        tap(GUI, 300)
    else:
        up(GUI, 300)
    output(W, 0x1A, 0, 'Command ends only when released or unlocked')

# Both layer keys have the same tap / hold / double-tap contract.
for layer, code, name in ((SYM, 0x1E, 'SYM'), (UPPER, 0x52, 'UPPER')):
    tap(layer, 500)
    output(W, code, 0, f'tap {name} gives one key', 10)
    output(W, 0x1A, 0, f'one-shot {name} is consumed')
    for dwell in (40, 116, 350, 700, 4000):
        down(layer, dwell)
        output(W, code, 0, f'held {name}, {dwell} ms, first key', 10)
        output(W, code, 0, f'held {name} covers the next key too', 10)
        up(layer, 100)
        output(W, 0x1A, 0, f'held {name} exits on release without locking')
    down(layer, 700)
    up(layer, 100)
    output(W, 0x1A, 0, f'unused long {name} hold also exits')
    double(layer)
    output(W, code, 0, f'double {name} locks', 3200)
    output(W, code, 0, f'locked {name} survives expiry and keys')
    tap(layer, 100)
    output(W, 0x1A, 0, f'tap unlocks {name}')
    tap(layer, 3200)
    output(W, 0x1A, 0, f'unused {name} one-shot expires')
    tap(layer, 500)
    tap(layer, 100)
    output(W, 0x1A, 0, f'late second {name} tap cancels without locking')
    tap(layer)
    output(W, code, 0, f'{name} one-shot before rapid re-entry', 10)
    tap(layer)
    output(W, code, 0, f'consumed {name} tap does not count towards locking', 10)
    output(W, 0x1A, 0, f'rapid {name} re-entry still ends after one key')
    for dwell, interval, persistent in ((60, 150, True), (116, 250, True),
                                       (150, 390, True), (300, 390, True), (300, 450, False)):
        tap(layer, interval - dwell, hold=dwell)
        tap(layer, 120, hold=dwell)
        output(W, code if persistent else 0x1A, 0, f'{name} double-tap interval {interval} ms')
        if persistent:
            output(W, code, 0, f'{name} remains locked')
            tap(layer, 100)
        output(W, 0x1A, 0, f'{name} timing case ends on DEFAULT')

# The requested Tab / dollar / Escape mappings, both held and sequential.
for layer, key, code, mods, name in ((SYM, DOLLAR, 0x21, 2, 'dollar'),
                                    (UPPER, BSPC, 0x29, 0, 'Escape')):
    for dwell in (40, 116, 250):
        for gap in (20, 120, 500, 1500, 2800):
            tap(layer, gap, hold=dwell)
            output(key, code, mods, f'sequential {name}: dwell {dwell}, gap {gap}', 80)
            output(W, 0x1A, 0, f'{name} consumes the one-shot', 120)
    down(layer, 80)
    output(key, code, mods, f'held layer sends {name}', 20)
    output(key, code, mods, f'held layer repeats {name}', 20)
    up(layer, 100)
    output(W, 0x1A, 0, f'releasing {name} chord returns to DEFAULT')

# A modifier does not consume a released one-shot layer.
tap(UPPER, 100)
down(CTRL, 80)
output(BSPC, 0x29, 1, 'Ctrl+Escape through one-shot UPPER')
output(W, 0x1A, 1, 'held Ctrl survives consuming UPPER')
up(CTRL, 300)
tap(SYM, 100)
output(GUI, 0x27, 0, 'physical 0 types zero after tapping SYM')
double(SYM)
output(GUI, 0x27, 0, 'physical 0 types zero on locked SYM')
output(GUI, 0x27, 0, 'zero does not exit locked SYM')
tap(SYM, 100)

# Command+SYM works in either order and either release order. A held layer's
# physical 0 delegates to Command, while tapped/locked SYM retains digit 0.
for order in ((GUI, SYM), (SYM, GUI)):
    for release_order in (order, order[::-1]):
        for gap in (10, 80, 700):
            for key in order:
                down(key, gap)
            output(M, 0x37, 8, 'Command+SYM+M sends Command+period', 20)
            output(M, 0x37, 8, 'held SYM remains available through repeated periods', 20)
            up(release_order[0], 100)
            if release_order[0] == SYM:
                output(W, 0x1A, 8, 'releasing SYM preserves held Command', 20)
            else:
                output(M, 0x37, 0, 'releasing Command preserves held SYM', 20)
            up(release_order[1], 100)
            output(W, 0x1A, 0, 'Command+SYM releases cleanly')

for order in permutations((GUI, CTRL, SHIFT, SYM)):
    for key in order:
        down(key, 20)
    output(M, 0x37, 11, 'Command+Ctrl+Shift+SYM works in every press order', 20)
    for key in reversed(order):
        up(key, 20)
    output(W, 0x1A, 0, 'four-key symbol chord leaves no modifier or layer active')

# Layer modifiers coexist, and locked parents survive a child one-shot.
for order in ((SYM, UPPER), (UPPER, SYM)):
    for release_order in (order, order[::-1]):
        for key in order:
            down(key, 80)
        output(W, 0x52, 0, 'UPPER wins while both layer keys are held', 20)
        up(release_order[0], 100)
        output(W, 0x1E if release_order[0] == UPPER else 0x52, 0,
               'releasing one layer preserves the other held layer', 20)
        up(release_order[1], 100)
        output(W, 0x1A, 0, 'both layer releases return to DEFAULT')

double(SYM)
tap(UPPER, 500)
output(W, 0x52, 0, 'one UPPER key above locked SYM', 20)
output(W, 0x1E, 0, 'consuming UPPER returns to locked SYM')
double(UPPER)
output(W, 0x52, 0, 'locked UPPER above locked SYM')
tap(UPPER, 100)
output(W, 0x1E, 0, 'unlocking UPPER preserves locked SYM')
double(UPPER)
tap(SYM, 100)
output(W, 0x1A, 0, 'explicit SYM exit clears its locked child')
tap(SYM, 100)
double(UPPER)
output(W, 0x52, 0, 'UPPER replaces a released one-shot SYM', 3200)
output(W, 0x52, 0, 'old SYM expiry cannot cancel locked UPPER')
tap(UPPER, 100)
output(W, 0x1A, 0, 'standalone UPPER exit returns to DEFAULT')

# Alt is physical 0 on UPPER and uses the same modifier implementation.
double(UPPER)
modifier_chords({SHIFT: (2, 'Shift'), CTRL: (1, 'Ctrl'), GUI: (4, 'Alt')}, 0x52)
double(GUI)
output(W, 0x52, 4, 'double-tapped Alt locks')
tap(UPPER, 100)
for key in (SHIFT, CTRL, GUI):
    down(key, 80)
output(W, 0x1A, 15, 'locked Alt combines with held Shift+Ctrl+Command')
for key in (GUI, CTRL, SHIFT):
    up(key, 80)
output(W, 0x1A, 4, 'held modifier releases preserve locked Alt')
double(UPPER)
tap(GUI, 300)
output(W, 0x52, 0, 'tap Alt on UPPER unlocks it')
tap(UPPER, 100)
output(W, 0x1A, 0, 'all modifiers and layers finish released')

# Releases remain paired when the layer ends before its key does.
down(UPPER, 80)
down(BSPC, 80)
expected.append((0x29, 0, 'UPPER+Backspace presses Escape'))
up(UPPER, 80)
output(W, 0x1A, 0, 'base letter while Escape remains physically held', 20)
up(BSPC, 300)
output(W, 0x1A, 0, 'Escape releases after its layer ends')

# Dollar supplies an implicit Shift in addition to the explicit held Shift.
for key in (GUI, CTRL, SHIFT, SYM):
    down(key, 20)
output(DOLLAR, 0x21, 11, 'dollar preserves explicit Ctrl+Command+Shift', 20)
output(M, 0x37, 11, 'releasing dollar preserves all held modifiers', 20)
for key in (SYM, SHIFT, CTRL, GUI):
    up(key, 20)
output(W, 0x1A, 0, 'explicit and implicit modifier references release cleanly')

# Unlocking a modifier is a physical interruption even though it emits only
# a keycode release. It must not turn separated layer taps into a lock.
double(SHIFT)
tap(UPPER, 40)
tap(SHIFT, 40)
tap(UPPER, 500)
output(W, 0x1A, 0, 'modifier unlock between layer taps cancels double-tap locking')

layers = '\n'.join(
    f"{layer['node']} {{ bindings = <{' '.join(layer['bindings'][p] for p in positions)}>; }};"
    for layer in model.layers
)
extra_behaviors = '\n'.join(
    f"{label}: {model.custom[label]['node']} {{"
    + body(model.source, rf"\b{label}\s*:\s*{model.custom[label]['node']}") + '};'
    for label in ['tdc_to_MEDIA', 'td_boot_out']
)
combos = []
for combo in model.combos:
    if all(p in positions for p in combo['positions']):
        mapped = ' '.join(str(positions.index(p)) for p in combo['positions'])
        combos.append(f"{combo['name']} {{ bindings = <{combo['binding']}>; "
                      f"key-positions = <{mapped}>; timeout-ms = <{combo['timeout']}>; }};")
fixture = '''#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>
#include <dt-bindings/zmk/kscan_mock.h>
#include <dt-bindings/zmk/outputs.h>
#include <dt-bindings/zmk/rgb.h>
#define DEFAULT 0
#define SYM 1
#define UPPER 2
#define MEDIA 3
#include "/repo/config/gestures.dtsi"
/ {
    behaviors { EXTRA_BEHAVIORS };
    keymap { compatible = "zmk,keymap"; LAYERS };
    COMBOS_NODE
};
&kscan { rows = <4>; columns = <3>; events = <EVENTS>; };
'''.replace('EXTRA_BEHAVIORS', extra_behaviors).replace('LAYERS', layers).replace('COMBOS_NODE', 'combos { compatible = \"zmk,combos\"; ' + '\n'.join(combos) + ' };' if combos else '').replace('EVENTS', '\n'.join(events))
(FIXTURE / 'native_posix_64.keymap').write_text(fixture)
(FIXTURE / 'native_posix_64.conf').write_text('CONFIG_ASSERT=y\n')
shutil.copytree(ROOT / 'config/dts', FIXTURE / 'dts', dirs_exist_ok=True)
module = FIXTURE / 'module'
(module / 'zephyr').mkdir(parents=True, exist_ok=True)
(module / 'zephyr/module.yml').write_text('name: bbq_layer_keys\nbuild:\n  cmake: .\n')
(module / 'CMakeLists.txt').write_text(
    'zephyr_library()\nzephyr_library_include_directories(${CMAKE_SOURCE_DIR}/include)\n'
    'include(/repo/config/boards/arm/zitaotech_q10/custom_driver/gestures.cmake)\n'
    'zephyr_library_sources(/repo/tests/native_report_sink.c)\n'
    'zephyr_ld_options(-Wl,--wrap=zmk_endpoints_send_report)\n')

# Zephyr v3.5's POSIX board passes -m64, an x86-only spelling. AArch64's host
# compiler already produces 64-bit code. Filter only that redundant option;
# the production ZMK behavior sources and mock input driver remain unchanged.
compiler = FIXTURE / 'gcc'
compiler.write_text('''#!/usr/bin/env python3
import os, platform, sys
args = sys.argv[1:]
if platform.machine() == "aarch64":
    args = [arg for arg in args if arg != "-m64"]
os.execv("/usr/bin/gcc", ["gcc", *args])
''')
compiler.chmod(0o755)

command = [
    'docker', 'run', '--rm',
    '--mount', f'type=bind,source={ROOT},target=/repo,readonly',
    '--mount', f'type=bind,source={CACHE},target=/workspace',
    '--workdir', '/workspace', '--entrypoint', '/bin/bash',
    'zmkfirmware/zmk-build-arm:stable', '-lc',
    'west zephyr-export && '
    'west build -s /workspace/zmk/app -d /workspace/build/gesture-tests '
    '-b native_posix_64 -- -DZMK_CONFIG=/workspace/gesture-tests '
    '-DZMK_EXTRA_MODULES=/workspace/gesture-tests/module '
    '-DZEPHYR_TOOLCHAIN_VARIANT=host -DCMAKE_C_COMPILER=/workspace/gesture-tests/gcc && '
    '/workspace/build/gesture-tests/zephyr/zmk.exe --no-rt',
]
log = FIXTURE / 'run.log'
with log.open('w') as out:
    result = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT)
if result.returncode:
    print(log.read_text()[-8000:])
    raise SystemExit(f'Native gesture build/run failed; see {log}')

text = log.read_text()
pattern = re.compile(r'hid_listener_keycode_(pressed|released): usage_page 0x07 '
                     r'keycode 0x([0-9a-f]+) implicit_mods 0x([0-9a-f]+) explicit_mods 0x([0-9a-f]+)', re.I)
held = Counter()
for event, key, implicit, explicit in pattern.findall(text):
    key, implicit, explicit = int(key, 16), int(implicit, 16), int(explicit, 16)
    if 0xE0 <= key <= 0xE7:
        held[key] += 1 if event == 'pressed' else -1
        if held[key] < 0:
            raise SystemExit(f'Unmatched modifier release for {key}; see {log}')

# Read host-visible reports, rather than inferring modifiers from behavior events.
# Reports include the complete set of held/locked modifiers.
actual, previous_keys, last_mods, keypress_reports = [], set(), 0, []
reports = re.findall(r'TEST_HID t=\d+ mods=([0-9a-f]+) keys=([0-9a-f ]*)', text, re.I)
if not reports:
    raise SystemExit(f'No HID reports captured; see {log}')
for report_index, (mods, keys) in enumerate(reports):
    last_mods = int(mods, 16)
    current_keys = {int(key, 16) for key in keys.split()}
    actual.extend((key, last_mods) for key in sorted(current_keys - previous_keys))
    keypress_reports.extend([report_index] * len(current_keys - previous_keys))
    previous_keys = current_keys
for i, (key, mods, case) in enumerate(expected):
    if i >= len(actual) or actual[i] != (key, mods):
        got = actual[i] if i < len(actual) else 'no event'
        raise SystemExit(f'FAIL {case}: expected {(key, mods)}, got {got}; see {log}')
if len(actual) != len(expected) or any(held.values()) or previous_keys or last_mods:
    raise SystemExit(f'Unexpected extra events or held modifiers: {actual[len(expected):]}, {held}; see {log}')
for start, end, case in command_spans:
    for mods, _ in reports[keypress_reports[start]:keypress_reports[end] + 1]:
        if not int(mods, 16) & 8:
            raise SystemExit(f'Command was released during {case}; see {log}')
if re.search(r'<err>|ASSERTION FAIL|FATAL ERROR', text):
    raise SystemExit(f'Unexpected firmware error; see {log}')
# Compare real host-report time against the scanner event, before another key
# can interrupt a deferred modifier. This catches the former 250 ms delay.
physical_times = [((int(h) * 60 + int(m)) * 60 + int(sec)) * 1000 + int(ms)
                  for h, m, sec, ms in re.findall(
                      r'\[(\d+):(\d+):(\d+)\.(\d+),\d+\].*zmk_physical_layouts_kscan_process_msgq:.*pressed:', text)]
timed_reports = [(int(t), int(mods, 16), {int(k, 16) for k in keys.split()})
                 for t, mods, keys in re.findall(r'TEST_HID t=(\d+) mods=([0-9a-f]+) keys=([0-9a-f ]*)', text)]
for event_index, mods, key in immediate_checks:
    pressed_at = physical_times[event_index]
    report_at = next(t for t, m, keys in timed_reports
                     if t >= pressed_at and m == mods and (key is None or key in keys))
    if report_at - pressed_at > 5:
        raise SystemExit(f'Modifier/Tab activation delayed {report_at - pressed_at} ms; see {log}')
print(f'PASS: {len(expected)} HID keypress outcomes, modifier release checks, and no firmware errors.')
print(f'Native ZMK trace: {log}')
