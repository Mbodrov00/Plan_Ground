# backend/analyse_svg.py
#
# std-lib only – no third-party installs required
import re, xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, Tuple

FILLABLE = {
    "path", "rect", "circle", "ellipse",
    "polygon", "polyline", "line", "text"
}
STYLE_FILL_RE   = re.compile(r"\bfill\s*:[^;]+;?")
STYLE_SW_RE     = re.compile(r"\bstroke-width\s*:\s*([^;]+)")
UNIT_RE         = re.compile(r"([0-9.]+)(px|pt|mm|cm|in)?")
PX_PER_UNIT = {None:1, "px":1, "pt":1.3333, "mm":3.7795,
               "cm":37.795, "in":96}

# ──────────────────────────────────────────────────────────────────────────
def _parse_len(value: str) -> float:
    """
    "0.25px" → 0.25 ;   "2mm" → 7.559 ;   "1" → 1.0
    Anything unparseable → 1.0 (SVG default)
    """
    m = UNIT_RE.fullmatch(value.strip())
    if not m:
        return 1.0
    qty, unit = m.groups()
    return float(qty) * PX_PER_UNIT[unit]

# ──────────────────────────────────────────────────────────────────────────
def _strip_fills_and_collect(svg_text: str) -> Tuple[str, Dict]:
    """
    • remove all fills
    • build element + stroke-width histograms
    → (clean_svg,   {"tags": {...}, "strokes_px": {...}})
    """
    tree = ET.fromstring(svg_text)

    tag_counts      = defaultdict(int)
    stroke_counts   = defaultdict(int)    # key: rounded px width

    for el in tree.iter():
        tag = el.tag.split("}")[-1]

        # tally element types
        tag_counts[tag] += 1

        # -- strip fills (same as before) --
        if tag in FILLABLE:
            if "fill" in el.attrib and el.attrib["fill"].lower() != "none":
                el.attrib["fill"] = "none"

            if "style" in el.attrib:
                style = STYLE_FILL_RE.sub("", el.attrib["style"])
                style = f"{style.rstrip(';')};fill:none"
                el.attrib["style"] = style.strip(";")

        # gather stroke-width
        sw    = el.attrib.get("stroke-width")
        style = el.attrib.get("style", "")
        if not sw:
            m = STYLE_SW_RE.search(style)
            if m:
                sw = m.group(1)
        width_px = _parse_len(sw) if sw else 1.0
        stroke_counts[round(width_px, 2)] += 1

    cleaned = ET.tostring(tree, encoding="unicode")
    return cleaned, {"tags": dict(tag_counts),
                     "strokes_px": dict(stroke_counts)}

# ──────────────────────────────────────────────────────────────────────────
def analyse(svg_text: str) -> Dict:
    """Main entry called by Flask route /analyse."""
    cleaned_svg, classes = _strip_fills_and_collect(svg_text)

    stats = {
        "original_bytes": len(svg_text.encode()),
        "clean_bytes":    len(cleaned_svg.encode())
    }
    return {"svg": cleaned_svg,
            "stats": stats,
            "classes": classes}
