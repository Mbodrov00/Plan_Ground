#!/usr/bin/env python3
"""
convert_pdf_to_svg.py
Extracts only geometric primitives from a PDF page and produces a
clean SVG (no images / gradients / patterns).
"""

import fitz           # PyMuPDF ≥ 1.23
import sys, argparse

# ────────────────────────────────────────────────────────────
# helpers
# ────────────────────────────────────────────────────────────
def rgb_tuple_to_hex(rgb, default="#666666"):
    """
    Convert a (r, g, b) float-tuple (0-1 each) to #rrggbb.
    Gracefully handles None, empty tuples, ints, etc.
    """
    if not rgb or len(rgb) < 3:
        return default

    try:
        r, g, b = (float(c) for c in rgb[:3])
    except Exception:
        return default

    r = max(0, min(255, int(r * 255)))
    g = max(0, min(255, int(g * 255)))
    b = max(0, min(255, int(b * 255)))
    return f"#{r:02x}{g:02x}{b:02x}"


def segment_to_path(seg):
    """Convert a PyMuPDF drawing segment to SVG path command."""
    op = seg[0]
    pts = seg[1:]

    if op == "m":               # move
        x, y = pts
        return f"M {x} {y}"
    elif op == "l":             # line
        x, y = pts
        return f"L {x} {y}"
    elif op == "c":             # cubic Bézier
        return f"C {' '.join(map(str, pts))}"
    elif op == "h":             # close path
        return "Z"
    # Unsupported operators (q/Q/…) are ignored
    return ""

# ────────────────────────────────────────────────────────────
# main conversion
# ────────────────────────────────────────────────────────────
def page_to_svg(page):
    """
    Return geometry-only SVG for a PyMuPDF page.
    Handles both tuple and fitz.Point coordinate payloads.
    """
    import fitz                           # local import is fine

    W, H = page.rect.width, page.rect.height
    out  = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">']

    # helper ───────────────────────────────────────────────
    def xy(pt):
        """Return (x, y) as floats, regardless of incoming type."""
        if isinstance(pt, fitz.Point):
            return float(pt.x), float(pt.y)
        if isinstance(pt, (list, tuple)):
            return float(pt[0]), float(pt[1])
        raise TypeError("unsupported point type")

    # build paths ──────────────────────────────────────────
    for item in page.get_drawings():
        kind = item["type"]                       # stroke / fill / image …
        if kind in {"image", "shading", "clip"}:  # ignore non-geometry
            continue

        cmds = []                                 # SVG path commands here
        H = page.rect.height                      # needed for Y-flip

        for seg in item["items"]:
            op  = seg[0]
            pts = seg[1:]                         # <--  NOW always defined
            def t(p):
                """return 'x y' (floats) with Y-flip for Point or (x,y) tuple"""
                if isinstance(p, fitz.Point):
                    return f"{p.x} {H - p.y}"
                if isinstance(p, (list, tuple)) and len(p) == 2:
                    x, y = p
                    return f"{float(x)} {H - float(y)}"
                raise TypeError("unsupported point payload")



            # -----------------------------------------------------
            if op == "m":                 # move
                cmds.append(f"M {t(pts[-1])}") 

            elif op == "l":               # straight line
                cmds.append(f"L {t(pts[-1])}") 

            elif op == "c":               # cubic Bézier (3 control points)
                # pts can be 3 Points OR 6 floats in weird combinations
                flat = []
                for token in pts:
                    if isinstance(token, fitz.Point):
                        flat.extend([token.x, H - token.y])
                    elif isinstance(token, (list, tuple)) and len(token) == 2:
                        flat.extend([token[0], H - token[1]])
                    else:
                        flat.append(float(token))
                if len(flat) == 6:
                    cmds.append("C " + " ".join(map(str, flat)))

            elif op == "h":               # close path
                cmds.append("Z")
            # -----------------------------------------------------

        if not cmds:
            continue

        color = rgb_tuple_to_hex(item.get("color"))
        width = item.get("width") or 0.5

        path = " ".join(cmds)
        out.append(
            f'<path d="{path}" stroke="{color}" stroke-width="{width}" '
            f'fill="none" vector-effect="non-scaling-stroke"/>'
        )


    out.append("</svg>")
    return "\n".join(out)


# ────────────────────────────────────────────────────────────
# CLI wrapper (optional, keeps previous behaviour)
# ────────────────────────────────────────────────────────────
def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--page", type=int, default=1, help="1-based page")
    args = ap.parse_args(argv)

    doc = fitz.open(args.infile)
    if not (1 <= args.page <= doc.page_count):
        ap.error("page out of range")

    svg = page_to_svg(doc[args.page-1])
    with open(args.outfile, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print("Wrote", args.outfile)

if __name__ == "__main__":
    main(sys.argv[1:])
