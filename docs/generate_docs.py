#!/usr/bin/env python3
"""Rebuild the complete offline documentation set, or check it without writes.

    python3 -m pip install -r docs/requirements.txt
    python3 docs/generate_docs.py [--check]

All output is computed and validated before files are changed. No firmware,
network, build-cache, current-time, or current-working-directory dependency.
"""

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import textwrap
import xml.etree.ElementTree as ET

import generate_keymaps as maps
from doc_model import Model

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'


def table(headers, rows):
    def cell(value):
        return str(value).replace('|', '&#124;').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(map(cell, headers)) + ' |',
                       '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                      ['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows])


def code(value):
    return f'`{value}`'


def layer_actions(model, binding, gesture='Press', stack=()):
    label, *args = binding.lstrip('&').split()
    if label in stack:
        raise ValueError(f'Recursive layer action: {label}')
    if label in ('sl', 'mo', 'to', 'tog'):
        mode = dict(sl='One-shot; eligible keycode or timeout exits',
                    mo='While held; release exits', to='Switch; release does not exit',
                    tog='Toggle on/off')[label]
        return [(gesture, model.layer_name(args[0]), mode)]
    cfg = model.config(label)
    children = cfg.get('bindings', [])
    children = model.bindings(children) if isinstance(children, str) else children
    if cfg.get('compatible') == 'zmk,behavior-layer-key':
        target = model.layer_name(str(cfg['layer']).strip('<> '))
        return [('Tap / hold / double tap / active tap', target,
                 'One-shot / momentary / locked / exit')]
    if cfg.get('compatible') == 'zmk,behavior-tap-dance':
        return [entry for i, child in enumerate(children)
                for entry in layer_actions(model, child, f'{gesture}: {i+1} press(es)', (*stack, label))]
    if label in ('mt', 'lt') or cfg.get('compatible') == 'zmk,behavior-hold-tap':
        return [entry for i, child in enumerate(children)
                for entry in layer_actions(model, f'{child} {args[i]}' if model.arity(child) else child,
                                           f'{gesture}: {("Hold", "Tap")[i]}', (*stack, label))]
    return []


def diagram(title, rows, headings=('From', 'Action', 'Result')):
    """An accessible three-column flow diagram with wrapped labels and arrows."""
    width, row_height = 1260, 116
    height = 125 + row_height * len(rows)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
             f'<title id="title">{html.escape(title)}</title>',
             '<desc id="desc">Read each row from left to right. Labels and colors identify the flow.</desc>',
             f'<rect width="{width}" height="{height}" fill="white"/>',
             '<g font-family="system-ui, sans-serif" fill="#172033">',
             f'<text x="24" y="38" font-size="24" font-weight="700">{html.escape(title)}</text>']
    for col, heading in enumerate(headings):
        parts.append(f'<text x="{26+col*416}" y="78" font-size="15" font-weight="600">{html.escape(heading)}</text>')
    for i, row in enumerate(rows):
        for col, label in enumerate(row):
            x, y = 24 + col * 416, 94 + i * row_height
            fill, stroke = [('#f1f5f9', '#475569'), ('#fff4d6', '#92400e'), ('#ede9fe', '#5b21b6')][col]
            lines = textwrap.wrap(str(label), width=43)
            if len(lines) > 4:
                raise ValueError(f'Diagram label too long: {label}')
            parts.append(f'<rect x="{x}" y="{y}" width="380" height="100" rx="8" fill="{fill}" stroke="{stroke}"/>')
            for j, line in enumerate(lines):
                parts.append(f'<text x="{x+14}" y="{y+25+j*19}" font-size="14">{html.escape(line)}</text>')
            if col < 2:
                parts.append(f'<text x="{x+388}" y="{y+55}" font-size="24">→</text>')
    return '\n'.join(parts + ['</g></svg>']) + '\n'


def render_html(text, title):
    try:
        import markdown
    except ImportError as exc:
        raise ValueError('Install docs dependencies: python3 -m pip install -r docs/requirements.txt') from exc
    if markdown.__version__ != '3.8':
        raise ValueError('Use pinned Markdown==3.8: python3 -m pip install -r docs/requirements.txt')
    content = markdown.markdown(text, extensions=['tables', 'fenced_code', 'toc'])
    for stem in ('keyboard-guide', 'keymaps', 'configuration'):
        content = content.replace(f'href="{stem}.md', f'href="{stem}.html')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>
*{{box-sizing:border-box}}body{{margin:0;padding:24px;background:#f4f5f7;color:#172033;font:16px/1.65 system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:32px;background:white;border-radius:12px}}nav{{display:flex;gap:20px;flex-wrap:wrap;max-width:1200px;margin:0 auto 20px}}a{{color:#5b21b6}}h1{{font-size:32px;line-height:1.25}}h2{{margin-top:2.5em;border-bottom:1px solid #d1d5db;padding-bottom:8px}}h3{{margin-top:2em}}p,li{{max-width:100ch}}img{{max-width:100%;height:auto}}pre{{overflow:auto;background:#f1f5f9;padding:18px;border-radius:8px}}code{{font-size:.9em;overflow-wrap:anywhere}}table{{display:block;overflow:auto;width:100%;border-collapse:collapse;font-size:14px}}td,th{{text-align:left;vertical-align:top;padding:10px;border:1px solid #d1d5db;min-width:100px}}th{{background:#f1f5f9}}a:focus-visible{{outline:3px solid #7c3aed;outline-offset:3px}}@media(max-width:600px){{body{{padding:10px}}main{{padding:16px}}h1{{font-size:26px}}}}@media print{{body,main{{padding:0;background:white}}nav{{display:none}}h2,h3{{break-after:avoid}}img,tr{{break-inside:avoid}}pre{{white-space:pre-wrap}}}}
</style></head><body><nav aria-label="Documentation"><a href="keyboard-guide.html">Complete guide</a><a href="keymaps.html">Interactive keymaps</a><a href="configuration.html">Configuration reference</a></nav><main>
{content}
</main></body></html>
'''


def generated_sections(model):
    custom = []
    for label, cfg in model.custom.items():
        children = model.bindings(cfg['bindings']) if 'bindings' in cfg else []
        kind = cfg['compatible'].removeprefix('zmk,behavior-')
        term = cfg.get('tapping-term-ms', cfg.get('release-after-ms'))
        if kind == 'tap-dance':
            actions = '; '.join(f'{i+1}: {b}' for i, b in enumerate(children))
        elif kind == 'hold-tap':
            actions = f'Hold: {children[0]}; tap: {children[1]}'
        elif kind == 'layer-key':
            actions = f"Layer {cfg['layer']}: tap once, hold momentarily, double-tap lock"
        elif kind == 'layer-modifier':
            actions = f'Held layer: {children[0]}; otherwise: {children[1]}'
        elif kind == 'mod-morph':
            actions = f'Normal: {children[0]}; with {cfg["mods"]}: {children[1]}'
        else:
            actions = '; '.join(children)
        usage = '; '.join(model.uses(label)) or 'Not assigned directly to a key'
        custom.append([code(label), kind, actions, f'{term} ms' if term is not None else 'Immediate', usage])
    transitions = []
    for layer in model.layers:
        for pos, binding in enumerate(layer['bindings']):
            for gesture, target, mode in layer_actions(model, binding):
                transitions.append([layer['name'], f'{gesture}: {model.physical[pos]} ({pos})', target, mode, code(binding)])
    current_maps = []
    for num, layer in enumerate(model.layers):
        name = layer['name']
        current_maps += [f'### Layer {num}: {name}', '', f'![{name} keymap](assets/layer-{num}-{name.lower()}.svg)', '',
                        f'{len(layer["bindings"])} positions; {layer["bindings"].count("&none")} disabled. [All exact bindings and explanations](keymaps.md).', '']
        positions = [26, 27, 35, 37, 38, 40, 41] if num == 0 else [4, 9, 26, 35, 38, 40, 41]
        current_maps += [table(['Physical position', 'Binding', 'What it does'],
            [[f'{model.physical[p]} ({p})', code(layer['bindings'][p]), model.describe(layer['bindings'][p])[2]] for p in positions]), '']
    stock = [(0, 40, 'SYM', 'Tap to enter layer 1; tap again to exit'),
             (0, 41, 'Right aA / ↑', 'Tap to enter layer 2 in the main usage section'),
             (0, 37, 'Left aA', 'Tap sticky Control; hold ordinary Control'),
             (0, 27, 'Physical Alt', 'Sticky Shift'),
             (0, 38, 'Physical 0', 'Alt'), (0, 2, 'Call', 'Caps Lock'),
             (0, 3, 'BlackBerry', 'GUI/Command'), (0, 5, 'Back', 'Tap Android Back; hold Escape'),
             (0, 6, 'End call', 'Tab'), (2, 9, 'UPPER E', 'Eject'),
             (2, 11, 'UPPER T', 'Trackpad power'), (2, 31, 'UPPER V', 'Pointer speed down'),
             (2, 33, 'UPPER N', 'Pointer speed up'), (2, 32, 'UPPER B', 'Keyboard lighting toggle')]
    stock_rows = [[name, original, code(model.layers[l]['bindings'][p]) + ': ' + model.describe(model.layers[l]['bindings'][p])[2]]
                  for l, p, name, original in stock if l < len(model.layers)]
    definitions = [
        ('kp', 'Key press', 'A normal key, released when you release the button.'),
        ('mt', 'Mod-tap', 'Hold the first keycode; tap the second.'),
        ('lt', 'Layer-tap', 'Hold for a temporary layer; tap a keycode.'),
        ('mo', 'Momentary layer', 'Use the layer while the button stays down.'),
        ('sl', 'Sticky layer', 'Tap to arm a layer for the next eligible keycode or timeout.'),
        ('sk', 'Sticky key', 'Tap a modifier, then the key it should modify.'),
        ('kt', 'Key toggle', 'Latch a key down; activate again to release it.'),
        ('to', 'Layer switch', 'Stay in the target layer; clear other nondefault layers.'),
        ('tog', 'Layer toggle', 'Toggle one layer without clearing the others.'),
        ('trans', 'Transparent', 'Look at the next active layer underneath.'),
        ('none', 'No operation', 'Do nothing; block lower-layer actions.')]
    behavior_rows = []
    for label, name, definition in definitions:
        uses = model.uses(label)
        summary = f'{len(uses)} direct positions across ' + ', '.join(l['name'] for l in model.layers if any(b.split()[0] == '&'+label for b in l['bindings'])) if uses else 'No direct key assignment; may be used by a custom behavior'
        behavior_rows.append([code('&'+label), name, definition, summary])
    timings = []
    for label in ['mt', 'lt', 'sk', 'sl', *model.custom]:
        cfg = model.config(label)
        for prop in ('tapping-term-ms', 'release-after-ms', 'flavor', 'quick-tap-ms', 'require-prior-idle-ms'):
            if prop in cfg:
                origin = 'Explicit definition / override' if prop in model.custom.get(label, {}) or prop in model.overrides.get(label, {}) else 'ZMK v0.3.0 default'
                timings.append([code('&'+label), prop, cfg[prop], origin])
    combo_rows = [[code(c['name']), ' + '.join(f'{model.physical[p]} ({p})' for p in c['positions']), code(c['binding']), f'{c["timeout"]} ms', str(c['layers'])] for c in model.combos]
    settings = []
    descriptions = {
        'CONFIG_ZMK_SLEEP': 'Deep sleep enabled/disabled.',
        'CONFIG_ZMK_IDLE_TIMEOUT': 'Idle timeout in milliseconds.',
        'CONFIG_ZMK_BACKLIGHT_BRT_STEP': 'Backlight adjustment step; custom trackpad logic uses brightness.',
        'CONFIG_A320_TRACKPAD_SCROLL_INTERVAL': 'Declared option; current custom motion handler does not read it.',
        'CONFIG_A320_TRACKPAD_SPEEDMULTIPLIER_HORIZONTAL': 'Declared option; current custom motion handler does not read it.',
        'CONFIG_A320_TRACKPAD_SPEEDMULTIPLIER_VERTICAL': 'Declared option; current custom motion handler does not read it.',
        'CONFIG_ZMK_SETTINGS_SAVE_DEBOUNCE': 'Delay before settings are saved to flash, in milliseconds.',
        'CONFIG_ZMK_STUDIO': 'Compile runtime keymap editing support.',
        'CONFIG_ZMK_USB': 'Compile USB transport.', 'CONFIG_ZMK_BLE': 'Compile Bluetooth transport.',
        'CONFIG_ZMK_HID_INDICATORS': 'Receive host indicators, including Caps Lock.',
    }
    for option, value in sorted(model.conf.items()):
        if option in descriptions or any(token in option for token in ('BACKLIGHT', 'RGB', 'DEBOUNCE', 'STUDIO')):
            settings.append([code(option), code(value), descriptions.get(option, 'User Kconfig override; see the option name and hardware notes below.')])
    sections = {
        'ZMK_VERSION': model.version,
        'BUILD_MATRIX': (ROOT / 'build.yaml').read_text(encoding='utf-8').strip(),
        'STOCK_COMPARISON': table(['Control', 'Manufacturer stock documentation', 'Current binding and meaning'], stock_rows),
        'LAYERS_TABLE': table(['Number', 'Constant', 'Node'], [[i, l['name'], code(l['node'])] for i, l in enumerate(model.layers)]),
        'CURRENT_MAPS': '\n'.join(current_maps),
        'LAYER_TRANSITIONS': table(['From', 'Physical gesture', 'Target', 'Lifetime', 'Binding'], transitions),
        'BEHAVIORS_TABLE': table(['Behavior', 'Definition', 'Plain language', 'Current direct usage'], behavior_rows),
        'CUSTOM_BEHAVIORS': table(['Label', 'Type', 'Child bindings in order', 'Threshold / interval', 'Direct usage'], custom),
        'COMBOS': table(['Name', 'Physical positions', 'Action', 'Window', 'Layer scope'], combo_rows) if combo_rows else 'No simultaneous combos are assigned. Modifier and layer chords use the held keys directly, without a combo recognition delay.',
        'TIMINGS': table(['Behavior', 'Property', 'Value', 'Source'], timings),
        'SETTINGS': table(['Configuration', 'Value', 'Meaning'], settings),
        'MODIFIER_MS': str(model.config('mod_shift')['tapping-term-ms']),
        'LAYER_MS': str(model.config('sym_key')['tapping-term-ms']),
        'ONE_SHOT_MS': str(model.config('sym_key')['release-after-ms']),
    }
    diagrams = {
        'layer-transitions': diagram('Current layer-changing bindings', [(r[0], r[1], f'{r[2]}: {r[3]}') for r in transitions]),
        'build-flow': diagram('Firmware build flow', [
            ('build.yaml', 'Choose board and reset targets', 'GitHub Actions or build-local.sh'),
            ('west.yml + keymap + .conf + board files', 'Compile with the selected ZMK version', 'Normal UF2 and settings-reset UF2'),
            ('Normal firmware UF2', 'Copy to the bootloader USB drive', 'Keyboard runs the compiled bindings')]),
        'layer-resolution': diagram('How a key position is resolved', [
            ('Physical key press', 'Check the highest active layer', 'Find the binding at that position'),
            ('Ordinary / custom binding', 'Run its behavior', 'Send keycode or perform firmware action'),
            ('Transparent binding', 'Check the next active layer underneath', 'Resolve that position again'),
            ('Disabled binding', 'Stop looking', 'No action; lower layers stay blocked')]),
        'sticky-sequence': diagram('One-shot layer: ordinary typing example', [
            ('DEFAULT', 'Tap and release SYM', 'SYM waits for an eligible keycode or timeout'),
            ('SYM armed', 'Press physical W (currently digit 1)', 'Send 1; consume the one-shot layer'),
            ('DEFAULT exposed again', 'Release W, then press W again', 'Release 1; the new press sends w')]),
        'gesture-lifetimes': diagram('Current gesture lifetimes', [
            ('Modifier pressed', 'Apply it immediately; release', 'Ordinary modifier ends on release'),
            ('Layer pressed', 'Hold while using several keys; release', 'Layer ends after held use'),
            ('Two uninterrupted short taps', 'Lock modifier or layer', 'Tap the same key to unlock')]),
    }
    return sections, diagrams


def build_outputs():
    model = Model(ROOT, maps.KEYS, maps.PHYSICAL)
    outputs = maps.build_maps(model)
    sections, diagrams = generated_sections(model)
    template = (DOCS / 'templates/keyboard-guide.md.in').read_text(encoding='utf-8')
    guide = re.sub(r'\{\{([A-Z_]+)\}\}', lambda m: sections[m[1]], template)
    if '{{' in guide:
        raise ValueError('Unexpanded guide template token')
    outputs['keyboard-guide.md'] = guide
    outputs['keyboard-guide.html'] = render_html(guide, 'BBQ10 Pro · Complete keyboard guide')
    config = ['# Current configuration reference', '', '<!-- Generated by docs/generate_docs.py. -->', '',
              '[Complete guide](keyboard-guide.md) · [Keymaps](keymaps.md)', '',
              'This snapshot records source configuration, not live device state. Inherited defaults are pinned to the selected ZMK version.', '',
              '## All user Kconfig overrides', '', table(['Option', 'Value'], [[code(k), code(v)] for k, v in sorted(model.conf.items())]), '',
              '## Effective timing properties', '', sections['TIMINGS'], '', '## Custom behavior definitions', '', sections['CUSTOM_BEHAVIORS'], '',
              '## Built-in behavior overrides', '', '```json', json.dumps(model.overrides, indent=2, sort_keys=True), '```', '']
    for title, path in [('Build targets', 'build.yaml'), ('Dependency manifest', 'config/west.yml'),
                        ('GitHub workflow', '.github/workflows/main.yml'),
                        ('Settings reset', 'config/boards/shields/settings_reset/settings_reset.conf')]:
        config += [f'## {title}', '', f'Source: `{path}`', '', '```text', (ROOT/path).read_text(encoding='utf-8').rstrip(), '```', '']
    outputs['configuration.md'] = '\n'.join(config)
    outputs['configuration.html'] = render_html(outputs['configuration.md'], 'BBQ10 Pro · Configuration reference')
    outputs.update({f'assets/{name}.svg': value for name, value in diagrams.items()})
    # Syntax/shape checks guard against partial or malformed map generation.
    for name, value in outputs.items():
        if name.endswith('.svg'):
            root = ET.fromstring(value)
            if re.match(r'assets/layer-\d+-', name):
                positions = [int(e.attrib['data-position']) for e in root.iter() if 'data-position' in e.attrib]
                if positions != list(range(len(model.physical))):
                    raise ValueError(f'Incomplete key positions in {name}')
    # Explicit encoding/newline normalization makes identical inputs byte-identical.
    outputs = {name: value.replace('\r\n', '\n').rstrip() + '\n' for name, value in outputs.items()}
    input_paths = ['build.yaml', 'config/west.yml', 'config/zitaotech_q10.keymap', 'config/gestures.dtsi', 'config/zitaotech_q10.conf',
                   'config/boards/arm/zitaotech_q10/CMakeLists.txt',
                   'config/boards/arm/zitaotech_q10/custom_driver/gestures.cmake',
                   'config/boards/arm/zitaotech_q10/custom_driver/behavior_layer_key.c',
                   'config/boards/arm/zitaotech_q10/custom_driver/behavior_layer_key.h',
                   'config/boards/arm/zitaotech_q10/custom_driver/behavior_modifier_key.c',
                   'config/boards/arm/zitaotech_q10/custom_driver/behavior_layer_modifier.c',
                   'config/boards/arm/zitaotech_q10/custom_driver/keyboard_backlight.c',
                   'config/boards/arm/zitaotech_q10/custom_driver/trackpad_led.c',
                   'config/boards/arm/zitaotech_q10/custom_driver/a320.c',
                   'config/dts/bindings/behaviors/zmk,behavior-layer-key.yaml',
                   'config/dts/bindings/behaviors/zmk,behavior-modifier-key.yaml',
                   'config/dts/bindings/behaviors/zmk,behavior-layer-modifier.yaml',
                   '.github/workflows/main.yml', 'config/boards/shields/settings_reset/settings_reset.conf',
                   'config/boards/arm/zitaotech_q10/zitaotech_q10-layouts.dtsi',
                   'docs/doc_model.py', 'docs/generate_docs.py', 'docs/generate_keymaps.py',
                   'docs/zmk-v0.3.0-defaults.json', 'docs/requirements.txt', 'docs/templates/keyboard-guide.md.in']
    digest = lambda data: hashlib.sha256(data).hexdigest()
    manifest = {'format': 1,
                'inputs': {name: digest((ROOT/name).read_bytes()) for name in sorted(input_paths)},
                'outputs': {name: digest(value.encode('utf-8')) for name, value in sorted(outputs.items())}}
    outputs['generation-manifest.json'] = json.dumps(manifest, indent=2, sort_keys=True) + '\n'
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Exit 1 for stale/missing output; never write files.')
    args = parser.parse_args()
    try:
        outputs = build_outputs()
    except (ValueError, KeyError, IndexError) as exc:
        parser.exit(2, f'Documentation generation failed: {exc}\n')
    changed = [name for name, value in sorted(outputs.items())
               if not (DOCS/name).exists() or (DOCS/name).read_bytes() != value.encode('utf-8')]
    if args.check:
        if changed:
            print('Stale or missing documentation:\n' + '\n'.join('  docs/' + name for name in changed))
            return 1
        print(f'All {len(outputs)} generated documentation files are up to date.')
        return 0
    for name in changed:
        path = DOCS/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(outputs[name].encode('utf-8'))
    print(f'Generated {len(outputs)} documentation files; updated {len(changed)}, unchanged {len(outputs)-len(changed)}.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
