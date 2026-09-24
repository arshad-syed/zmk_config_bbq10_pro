"""Read the literal Devicetree subset used by this repository, without a build cache.

Not a C preprocessor: macros in binding arrays, conditional keymaps, unknown
behaviors, and invalid arities fail explicitly rather than yielding plausible maps.
"""

from pathlib import Path
import json
import re


def clean(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)


def body(text, pattern):
    match = re.search(pattern + r'\s*\{', text)
    if not match:
        raise ValueError(f"Missing node: {pattern}")
    start = match.end()
    depth = 1
    for i in range(start, len(text)):
        depth += (text[i] == '{') - (text[i] == '}')
        if not depth:
            return text[start:i]
    raise ValueError(f"Unclosed node: {pattern}")


def properties(text):
    result = {}
    for name, value in re.findall(r'([\w#-]+)\s*=\s*(.*?);', text, re.S):
        value = value.strip()
        if value.startswith('"'):
            result[name] = value.strip('"')
        elif re.fullmatch(r'<\s*\d+\s*>', value):
            result[name] = int(value.strip('<> '))
        else:
            result[name] = value
    for name in ('quick-release', 'ignore-modifiers', 'lazy'):
        if re.search(r'(?:^|;)\s*' + name + r'\s*;', text):
            result[name] = True
        if re.search(r'/delete-property/\s+' + name + r'\s*;', text):
            result[name] = False
    return result


ARITY = dict(kp=1, mt=2, lt=2, mo=1, sl=1, sk=1, kt=1, to=1, tog=1,
             trans=0, none=0, mkp=1, msc=1, bt=None, out=1, sys_reset=0,
             bootloader=0, ext_power=1, rgb_ug=1, bl=1, caps_word=0)


def local_source(path, stack=()):
    path = path.resolve()
    if path in stack:
        raise ValueError(f'Recursive local include: {path}')
    text = path.read_text(encoding='utf-8')
    return re.sub(r'^\s*#include\s+"([^"\n]+)"\s*$',
                  lambda m: local_source(path.parent / m[1], (*stack, path)), text, flags=re.M)


class Model:
    def __init__(self, root, key_names, physical):
        self.root, self.key_names, self.physical = root, key_names, physical
        self.source = clean(local_source(root / 'config/zitaotech_q10.keymap'))
        if re.search(r'^\s*#\s*(if|ifdef|ifndef|elif|else)\b', self.source, re.M):
            raise ValueError('Conditional keymaps require preprocessing; unsupported by this generator.')
        self.defaults = json.loads((root / 'docs/zmk-v0.3.0-defaults.json').read_text(encoding='utf-8'))
        west = (root / 'config/west.yml').read_text(encoding='utf-8')
        self.version = re.search(r'revision:\s*(\S+)', west)[1]
        if self.version != self.defaults['version']:
            raise ValueError('ZMK revision changed: review and update the checked-in behavior defaults.')
        self.defines = dict(re.findall(r'^\s*#define\s+(\w+)\s+(\d+)\s*$', self.source, re.M))
        self.custom = {}
        for label, node in re.findall(r'\b(\w+)\s*:\s*(\w+)\s*\{', self.source):
            props = properties(body(self.source, rf'\b{label}\s*:\s*{node}'))
            if 'compatible' in props:
                props['node'] = node
                self.custom[label] = props
        self.overrides = {}
        for label in re.findall(r'&(\w+)\s*\{', self.source):
            self.overrides[label] = properties(body(self.source, rf'&{label}'))
        keymap = body(self.source, r'\bkeymap')
        self.layers = []
        for node in re.findall(r'(\w+)\s*\{', keymap):
            props = properties(body(keymap, rf'\b{node}'))
            if 'bindings' not in props:
                raise ValueError(f'Layer {node} has no bindings')
            num = len(self.layers)
            name = next((k for k, v in self.defines.items() if int(v) == num), node.upper())
            self.layers.append({'node': node, 'name': name, 'bindings': self.bindings(props['bindings'])})
        if not self.layers:
            raise ValueError('No layers found')
        layout = (root / 'config/boards/arm/zitaotech_q10/zitaotech_q10-layouts.dtsi').read_text(encoding='utf-8')
        self.geometry = [tuple(map(int, m)) for m in re.findall(r'<&key_physical_attrs\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', layout)]
        if len(self.geometry) != len(physical) or any(len(l['bindings']) != len(physical) for l in self.layers):
            raise ValueError('Every layer and physical layout must have exactly 42 matching positions.')
        self.combos = []
        combo_match = re.search(r'\bcombos\s*\{', self.source)
        if combo_match:
            combos = body(self.source, r'\bcombos')
            for name in re.findall(r'(\w+)\s*\{', combos):
                props = properties(body(combos, rf'\b{name}'))
                positions = [int(p) for p in str(props['key-positions']).strip('<>').split()]
                if any(p >= len(physical) for p in positions):
                    raise ValueError(f'Invalid positions in combo {name}')
                self.combos.append(dict(name=name, positions=positions,
                    binding=self.bindings(props['bindings'])[0],
                    timeout=props.get('timeout-ms', self.defaults['combo-timeout-ms']),
                    layers=props.get('layers', 'All layers')))
        conf = (root / 'config/zitaotech_q10.conf').read_text(encoding='utf-8')
        self.conf = dict(re.findall(r'^(CONFIG_\w+)=(.*?)\s*$', conf, re.M))
        # Validate every assigned binding, and nested custom bindings, before writing outputs.
        for layer in self.layers:
            for binding in layer['bindings']:
                self.describe(binding)

    def bindings(self, value):
        value = re.sub(r'[<>,]', ' ', value).strip()
        if not value.startswith('&'):
            raise ValueError(f'Expected literal behavior bindings, got {value!r}')
        result = [' '.join(b.split()) for b in re.findall(r'&[^&]+', value)]
        for binding in result:
            if not re.fullmatch(r'&\w+(?:\s+\w+)*', binding):
                raise ValueError(f'Unsupported expression in binding: {binding}')
        return result

    def layer_name(self, value):
        number = int(self.defines.get(str(value), value))
        if not 0 <= number < len(self.layers):
            raise ValueError(f'Unknown layer {value}')
        return self.layers[number]['name']

    def key(self, value):
        if value in self.key_names:
            return self.key_names[value]
        if re.fullmatch(r'N[0-9]', value):
            return value[1:]
        if re.fullmatch(r'[A-Z]|F\d+', value):
            return value
        raise ValueError(f'Add a plain-language name for keycode {value}')

    def config(self, label):
        return {**self.defaults['behaviors'].get(label, {}),
                **self.custom.get(label, {}), **self.overrides.get(label, {})}

    def describe(self, binding, stack=()):
        label, *args = binding.lstrip('&').split()
        if label in stack:
            raise ValueError(f'Recursive behavior: {binding}')
        cfg = self.config(label)
        arity = cfg.get('#binding-cells', ARITY.get(label, -1))
        if label == 'bt':
            arity = 2 if args and args[0] == 'BT_SEL' else 1
        if arity != len(args):
            raise ValueError(f'{binding}: expected {arity} arguments, got {len(args)}')
        if label in self.custom or label in ('mt', 'lt'):
            kind = cfg.get('compatible', 'zmk,behavior-hold-tap')
            children = cfg.get('bindings', [])
            children = self.bindings(children) if isinstance(children, str) else children
            if kind == 'zmk,behavior-layer-modifier':
                held, ordinary = [self.describe(b, (*stack, label)) for b in children]
                name = self.layer_name(str(cfg['layer']).strip('<> '))
                return 'HOLD/TAP', ['Held SYM: Command', 'Tapped / locked: 0'], f'While {name} is physically held: {held[2]} With a released one-shot or locked {name}: {ordinary[2]} The selected action receives its matching release even if the layer ends first.'
            if kind == 'zmk,behavior-modifier-key':
                if len(children) != 1 or not children[0].startswith('&kp '):
                    raise ValueError(f'{label} must wrap one modifier key press')
                name = self.key(children[0].split()[1])
                return 'LATCH', [name, 'Hold / 2× lock'], f'Press {name} immediately; an ordinary hold ends on release. Double-tap within {cfg["tapping-term-ms"]} ms (first press to second press) to lock it across multiple keys. Tap the same modifier again to unlock. Another key or layer change between taps cancels double-tap recognition. Locks can combine and have no unused timeout; they reset on reboot.'
            if kind == 'zmk,behavior-sticky-key':
                name = self.key(args[0])
                activation = 'just before the next key' if cfg.get('lazy') else 'when armed'
                return 'STICKY', ['One-shot', name], f'Apply {name} to the next key only; activates {activation}. Unused timeout {cfg["release-after-ms"]} ms. Other modifiers do not consume it.'
            if kind == 'zmk,behavior-mod-morph':
                normal, modified = [self.describe(b, (*stack, label)) for b in children]
                names = {'MOD_LCTL': 'left Ctrl', 'MOD_RCTL': 'right Ctrl',
                         'MOD_LSFT': 'left Shift', 'MOD_RSFT': 'right Shift',
                         'MOD_LALT': 'left Alt', 'MOD_RALT': 'right Alt',
                         'MOD_LGUI': 'left Command', 'MOD_RGUI': 'right Command'}
                mods = ' or '.join(names[m] for m in re.findall(r'MOD_\w+', cfg['mods']))
                return normal[0], [f'Ctrl: {" / ".join(modified[1])}', ' / '.join(normal[1])], f'With {mods} active: {modified[2]} Control is removed from the output; other held modifiers remain. Otherwise: {normal[2]}'
            if kind == 'zmk,behavior-tap-dance':
                described = [self.describe(b, (*stack, label)) for b in children]
                interval = cfg.get('tapping-term-ms', self.defaults['tap-dance-tapping-term-ms'])
                lines = [f'{i+1}: {" / ".join(d[1])}' for i, d in enumerate(described)]
                explanation = ' '.join(f'{i+1} press(es): {d[2]}' for i, d in enumerate(described))
                return 'DANCE', lines, f'{explanation} Dance interval: {interval} ms.'
            if kind == 'zmk,behavior-hold-tap':
                if len(children) != 2:
                    raise ValueError(f'{label} must have two hold-tap children')
                described = [self.describe(f'{b} {args[i]}' if self.arity(b) else b, (*stack, label)) for i, b in enumerate(children)]
                term = cfg.get('tapping-term-ms')
                if term is None:
                    raise ValueError(f'Missing hold threshold for {label}')
                flavor = cfg.get('flavor', self.defaults['hold-tap-flavor'])
                return 'HOLD/TAP', [f'Tap: {" / ".join(described[1][1])}', f'Hold: {" / ".join(described[0][1])}'], f'Tap: {described[1][2]} Hold: {described[0][2]} Threshold: {term} ms; flavor: {flavor}.'
            if kind == 'zmk,behavior-layer-key':
                name = self.layer_name(str(cfg['layer']).strip('<> '))
                explanation = f'Tap for one use of {name}; hold to use it for the entire chord, then release to exit. Double-tap within {cfg["tapping-term-ms"]} ms to lock it; tap again to exit it and its locked child layer. Holding never locks. An unused hold of {cfg["tapping-term-ms"]} ms or longer exits on release. A released one-shot expires unused after {cfg["release-after-ms"]} ms. Modifiers do not consume it. Another physical key between taps cancels double-tap recognition.'
                labels = [cfg.get('display-name', name), '1× once / 2× stay']
                return 'LAYER', labels, explanation
            raise ValueError(f'Unsupported custom behavior type {kind}')
        if label == 'kp':
            name = self.key(args[0])
            return 'KEY', [name], f'Press {name}; release when the physical key is released.'
        if label in ('mo', 'sl', 'to', 'tog'):
            name = self.layer_name(args[0])
            if label == 'mo':
                return 'LAYER', [f'Hold: {name}'], f'Enable {name} immediately while held; disable it on release.'
            if label == 'sl':
                timeout = cfg['release-after-ms']
                return 'STICKY', ['One-shot', name], f'Tap and release to arm {name}; unused timeout {timeout} ms. An eligible keycode consumes it; firmware-only actions may not. Can also be held.'
            if label == 'tog':
                return 'LAYER', ['Toggle', name], f'Toggle {name} on/off without clearing other layers.'
            return 'LAYER', ['Go to', name], f'Switch to {name}; clear other nondefault layers. Releasing this key does not undo the switch.'
        if label in ('sk', 'kt'):
            name = self.key(args[0])
            if label == 'sk':
                return 'STICKY', ['One-shot', name], f'Tap for {name} on the next eligible key; unused timeout {cfg["release-after-ms"]} ms. Can also be held.'
            return 'LATCH', ['Toggle', name], f'Toggle {name} down/up. It stays down after release and after typing another key.'
        if label == 'bt':
            if args[0] == 'BT_CLR':
                return 'DEVICE', ['Clear BT!'], 'Erase the selected Bluetooth profile pairing.'
            if args[0] == 'BT_SEL':
                return 'DEVICE', [f'BT profile {args[1]}'], f'Select zero-based Bluetooth profile {args[1]}; an unpaired profile is available for pairing.'
        actions = {
            '&none': ('OFF', ['Disabled'], 'No action; blocks the corresponding lower-layer key.'),
            '&trans': ('KEY', ['Transparent'], 'Use the binding from the next active layer underneath.'),
            '&mkp LCLK': ('MOUSE', ['Left click'], 'Hold the left mouse button while pressed.'),
            '&mkp RCLK': ('MOUSE', ['Right click'], 'Hold the right mouse button while pressed.'),
            '&msc SCRL_UP': ('MOUSE', ['Scroll up'], 'Send upward mouse-wheel events while held.'),
            '&msc SCRL_DOWN': ('MOUSE', ['Scroll down'], 'Send downward mouse-wheel events while held.'),
            '&sys_reset': ('DEVICE', ['Reboot!'], 'Restart firmware; do not erase settings.'),
            '&bootloader': ('DEVICE', ['Bootloader!'], 'Enter the bootloader for firmware flashing.'),
            '&out OUT_TOG': ('DEVICE', ['USB / BLE'], 'Toggle preferred USB/Bluetooth output.'),
            '&out OUT_USB': ('DEVICE', ['USB output'], 'Select preferred USB output.'),
            '&out OUT_BLE': ('DEVICE', ['BLE output'], 'Select preferred Bluetooth output.'),
            '&ext_power EP_TOG': ('DEVICE', ['Trackpad power', 'toggle'], 'Toggle external power used for trackpad on/off according to the manufacturer.'),
            '&rgb_ug RGB_BRD': ('DEVICE', ['Keyboard light', 'down'], 'Decrease RGB brightness used by the custom keyboard-light driver.'),
            '&rgb_ug RGB_BRI': ('DEVICE', ['Keyboard light', 'up'], 'Increase RGB brightness used by the custom keyboard-light driver.'),
            '&rgb_ug RGB_TOG': ('DEVICE', ['Keyboard light', 'toggle'], 'Toggle RGB state used by the custom keyboard-light driver.'),
            '&bl BL_DEC': ('DEVICE', ['Speed / LED', 'down'], f'Decrease backlight by {self.conf.get("CONFIG_ZMK_BACKLIGHT_BRT_STEP", "the configured step")}; custom trackpad indicator and pointer speed use it.'),
            '&bl BL_INC': ('DEVICE', ['Speed / LED', 'up'], f'Increase backlight by {self.conf.get("CONFIG_ZMK_BACKLIGHT_BRT_STEP", "the configured step")}; custom trackpad indicator and pointer speed use it.'),
            '&caps_word': ('KEY', ['Caps Word'], 'Capitalize letters until a noncontinuation key; this is not Caps Lock.'),
        }
        if binding not in actions:
            raise ValueError(f'Add an explanation for {binding}')
        return actions[binding]

    def arity(self, binding):
        label = binding.lstrip('&').split()[0]
        return self.config(label).get('#binding-cells', ARITY.get(label))

    def uses(self, label):
        return [f'{layer["name"]} {self.physical[p]} ({p})' for layer in self.layers
                for p, binding in enumerate(layer['bindings']) if binding.split()[0] == '&' + label]

    def combo_caption(self):
        if not self.combos:
            return 'None'
        return ' · '.join(' + '.join(f'{self.physical[p]} ({p})' for p in c['positions'])
                         + ' → ' + ' / '.join(self.describe(c['binding'])[1]) for c in self.combos)
