#!/usr/bin/env python3
"""Render this project's literal keymap as SVG, HTML, and Markdown (stdlib only).

Run from any directory: python3 docs/generate_docs.py
This deliberately parses this repository's simple binding format, not arbitrary DTS.
Legacy entry point: running this file regenerates the complete documentation set.
"""

from pathlib import Path
import html
import re

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
COLORS = {
    "KEY": ("#f1f5f9", "#475569", "Ordinary key / modifier"),
    "HOLD/TAP": ("#fff4d6", "#92400e", "Different hold and tap actions"),
    "STICKY": ("#dcfce7", "#166534", "One-shot key / layer"),
    "LATCH": ("#ffedd5", "#9a3412", "Key stays pressed until toggled"),
    "LAYER": ("#ede9fe", "#5b21b6", "Layer activation / switch"),
    "DANCE": ("#fce7f3", "#9d174d", "Single / double press"),
    "MOUSE": ("#cffafe", "#155e75", "Mouse button / wheel"),
    "DEVICE": ("#fee2e2", "#991b1b", "Connection / power / lighting"),
    "OFF": ("#e5e7eb", "#4b5563", "Disabled; no fall-through"),
}
KEYS = {
    "LEFT": "Left arrow", "UP_ARROW": "Up arrow", "UP": "Up arrow",
    "DOWN_ARROW": "Down arrow", "DOWN": "Down arrow", "RIGHT_ARROW": "Right arrow",
    "RIGHT": "Right arrow", "BSPC": "Backspace", "ENTER": "Enter", "SPACE": "Space",
    "LEFT_CONTROL": "Control", "LCTRL": "Control", "LEFT_COMMAND": "Command / GUI",
    "LEFT_ALT": "Alt", "LALT": "Alt", "LSHFT": "Shift", "SEMI": ";", "DLLR": "$",
    "HASH": "#", "LBKT": "[", "RBKT": "]", "LPAR": "(", "RPAR": ")",
    "UNDER": "_", "MINUS": "-", "PLUS": "+", "AT": "@", "STAR": "*",
    "SLASH": "/", "COLON": ":", "APOS": "'", "DQT": '"', "DEL": "Delete",
    "QMARK": "?", "EXCL": "!", "COMMA": ",", "DOT": ".", "LT": "<", "GT": ">",
    "PIPE": "|", "KP_EQUAL": "Keypad =", "BSLH": "\\", "AMPS": "&",
    "LBRC": "{", "RBRC": "}", "CARET": "^", "PSCRN": "Print Screen",
    "C_AC_SEARCH": "Search", "C_VOL_UP": "Volume up", "C_VOL_DN": "Volume down",
    "C_MUTE": "Mute", "TAB": "Tab", "ESC": "Escape",
    "CAPSLOCK": "Caps Lock", "C_EJECT": "Eject",
}
PHYSICAL = ["Shoulder L", "Shoulder R", "Call", "BlackBerry", "Trackpad", "Back", "End call"]
PHYSICAL += list("QWERTYUIOP") + list("ASDFGHJKL") + ["Backspace"]
PHYSICAL += ["Alt"] + list("ZXCVBNM") + ["$", "Enter"]
PHYSICAL += ["aA left", "0", "Space", "SYM", "aA right"]
def svg(model, layer_num, name, subtitle, bindings, geometry):
    esc = html.escape
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1320" height="980" viewBox="0 0 1320 980" role="img" aria-labelledby="title desc">',
           f'<title id="title">Layer {layer_num}: {name}</title>',
           '<desc id="desc">42 physical keys, colored by behavior. Each key shows its position, physical label, action, and behavior category. See the accompanying text table for exact bindings.</desc>',
           '<rect width="1320" height="980" fill="#ffffff"/>',
           '<g font-family="system-ui, sans-serif" fill="#172033">',
           f'<text x="38" y="42" font-size="27" font-weight="700">{layer_num} / {name}</text>',
           f'<text x="38" y="72" font-size="16">{esc(subtitle)} · Current configuration</text>']
    for i, (category, (fill, stroke, label)) in enumerate(COLORS.items()):
        x, y = 38 + (i % 3) * 420, 96 + (i // 3) * 27
        out += [f'<rect x="{x}" y="{y}" width="12" height="12" rx="3" fill="{fill}" stroke="{stroke}"/>',
                f'<text x="{x+21}" y="{y+11}" font-size="12">{category} · {esc(label)}</text>']
    out.append('<text x="38" y="200" font-size="14">Top label = physical key + position · 1 / 2 = single / double press · ! = reset or pairing action</text>')
    for pos, (binding, (w, h, x, y)) in enumerate(zip(bindings, geometry)):
        category, labels, explanation = model.describe(binding)
        fill, stroke, _ = COLORS[category]
        sx, sy, sw = 38 + x * 1.24, 220 + y * 1.12, w * 1.24 - 8
        out += [f'<g data-position="{pos}" data-binding="{esc(binding, quote=True)}">',
                f'<title>{esc(PHYSICAL[pos])} (position {pos}): {esc(binding)}. {esc(explanation)}</title>',
                f'<rect x="{sx}" y="{sy}" width="{sw}" height="103" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>',
                f'<text x="{sx+sw/2}" y="{sy+19}" text-anchor="middle" font-size="11" fill="#374151">{esc(PHYSICAL[pos])} · {pos}</text>']
        for j, label in enumerate(labels):
            font_size = min(13, (sw - 12) / max(1, len(label) * .58))
            out.append(f'<text x="{sx+sw/2}" y="{sy+45+j*19}" text-anchor="middle" font-size="{font_size:.1f}" font-weight="650">{esc(label)}</text>')
        out += [f'<text x="{sx+sw/2}" y="{sy+89}" text-anchor="middle" font-size="10" font-weight="700" fill="{stroke}">{category}</text>', '</g>']
    out += [f'<text x="38" y="920" font-size="12">Combos (scope in guide): {esc(model.combo_caption())}</text>',
            '<text x="38" y="948" font-size="12">Source: config/zitaotech_q10.keymap · Colors classify behavior, not hardware LED colors · Symbols assume a US host layout</text>', '</g></svg>']
    return "\n".join(out) + "\n"


def build_maps(model):
    geometry = model.geometry
    outputs = {}
    md = ["# Current keymaps", "", "Generated from `config/zitaotech_q10.keymap`. Do not edit the generated maps by hand.", "", "[Read the behavior guide](keyboard-guide.md) · [Open the interactive map](keymaps.html)", "", "Positions are zero-based. Physical labels identify the keycap, not its current action. Symbols assume a US host keyboard layout. Color and text badges describe interaction type, not the keyboard's LEDs.", ""]
    sections, buttons = [], []
    for num, layer in enumerate(model.layers):
        name = layer['name']
        bindings = layer['bindings']
        disabled = bindings.count('&none')
        subtitle = f"{len(bindings)} positions · {disabled} disabled"
        drawing = svg(model, num, name, subtitle, bindings, geometry)
        outputs[f"assets/layer-{num}-{name.lower()}.svg"] = drawing
        md += [f"## {num}: {name}", "", subtitle, "", f"![Layer {num}: {name}](assets/layer-{num}-{name.lower()}.svg)", "", "| Position | Physical key | Exact binding | Type | Plain-language action |", "|---|---|---|---|---|", ]
        rows = []
        for pos, binding in enumerate(bindings):
            category, _, explanation = model.describe(binding)
            values = [str(pos), PHYSICAL[pos], binding, category, explanation]
            md.append("| " + " | ".join(v.replace("|", "&#124;").replace("\\", "&#92;") if i != 2 else f"`{v}`" for i, v in enumerate(values)) + " |")
            rows.append("<tr>" + "".join(f"<td>{html.escape(v)}</td>" for v in values) + "</tr>")
        md.append("")
        buttons.append(f'<button type="button" data-layer="{num}" aria-pressed="{str(num == 0).lower()}" aria-controls="layer-{num}">{num} · {name}</button>')
        sections.append(f'<section id="layer-{num}" {"hidden" if num else ""}><h2>{num}: {name}</h2><img src="assets/layer-{num}-{name.lower()}.svg" alt="Color-coded {name} layer; full text follows in the binding table."><details><summary>All 42 bindings and explanations</summary><div class="table-wrap"><table><thead><tr><th>Position</th><th>Physical key</th><th>Exact binding</th><th>Type</th><th>Action</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></details></section>')
    outputs["keymaps.md"] = "\n".join(md)
    page = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>BBQ10 Pro · Current keymaps</title>
<style>
*{box-sizing:border-box}body{font:16px/1.6 system-ui,sans-serif;color:#172033;background:#f4f5f7;margin:0;padding:28px}main{max-width:1320px;margin:auto}h1{margin:0;font-size:30px}p{max-width:85ch}nav{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}button{font:inherit;padding:10px 20px;border:1px solid #64748b;border-radius:7px;background:white;color:#172033;cursor:pointer}button[aria-pressed=true]{background:#172033;color:white}button:focus-visible,summary:focus-visible{outline:3px solid #7c3aed;outline-offset:4px}section{background:white;border-radius:12px;padding:18px}section[hidden]{display:none}h2{margin:0 16px}img{width:100%;height:auto}summary{cursor:pointer;font-weight:600;padding:16px}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:10px;border-bottom:1px solid #d1d5db}td:nth-child(3){font-family:monospace;white-space:nowrap}footer{margin-top:24px;color:#475569}@media(max-width:600px){body{padding:12px}section{padding:4px}img{min-width:850px}section{overflow:auto}}@media print{body{background:white;padding:0}nav,footer,details{display:none}section[hidden]{display:block}section{break-before:page;padding:0}section:first-of-type{break-before:auto}img{min-width:0}}
</style></head><body><main><h1>BBQ10 Pro: current keymaps</h1><p>Select a layer. Key colors identify behavior; text badges carry the same information. Top labels identify the physical key and its zero-based position. These maps show the current source configuration.</p><p><a href="keyboard-guide.html">Behavior and configuration guide</a> · <a href="keymaps.md">Markdown maps and binding tables</a> · Print this page for all four maps.</p>
<nav aria-label="Choose layer">BUTTONS</nav>SECTIONS
<footer>Generated from config/zitaotech_q10.keymap. Update with: python3 docs/generate_docs.py. No network requests or external assets.</footer></main><script>
const buttons = [...document.querySelectorAll('button[data-layer]')];
function selectLayer(value) { const id = buttons.some(b => b.dataset.layer === value) ? value : '0'; buttons.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.layer === id))); document.querySelectorAll('section').forEach(s => s.hidden = s.id !== 'layer-' + id); }
buttons.forEach(b => b.addEventListener('click', () => { location.hash = b.dataset.layer; selectLayer(b.dataset.layer); }));
window.addEventListener('hashchange', () => selectLayer(location.hash.slice(1)));
selectLayer(location.hash.slice(1));
</script></body></html>
'''
    outputs["keymaps.html"] = page.replace("BUTTONS", "".join(buttons)).replace("SECTIONS", "".join(sections))
    return outputs


if __name__ == "__main__":
    import sys
    from generate_docs import main
    sys.exit(main())
