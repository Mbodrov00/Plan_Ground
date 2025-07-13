#!/usr/bin/env python3
"""
convert_pdf_to_svg.py

Usage:
    python convert_pdf_to_svg.py input.pdf output.svg  [--page 1]

The script keeps ONLY geometry instructions (lines / curves /
polygons / strokes). It ignores images, shadings, patterns,
gradients, clip paths and text that has no outline.
"""

import fitz           # PyMuPDF
import sys, argparse

def page_to_svg(page):
    W, H = page.rect.width, page.rect.height
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" '
           f'viewBox="0 0 {W} {H}">']

    for item in page.get_drawings():
        kind = item["type"]               # stroke / fill / image / ...
        if kind in ("image", "shading", "clip"):
            continue                      # skip un-wanted kinds

        path_data = ""
        for seg in item["items"]:
            op, pts = seg
            if op == "m":                        # move
                x, y = pts
                path_data += f'M {x} {y} '
            elif op == "l":                      # line
                x, y = pts
                path_data += f'L {x} {y} '
            elif op == "c":                      # cubic Bézier
                x1,y1,x2,y2,x3,y3 = pts
                path_data += f'C {x1} {y1} {x2} {y2} {x3} {y3} '
            elif op == "h":                      # close path
                path_data += 'Z '

        if not path_data.strip():
            continue

        # colour comes as floats 0–1
        r,g,b = item.get("color", (0,0,0))
        stroke = "#{:02x}{:02x}{:02x}".format(int(r*255),int(g*255),int(b*255))
        width  = item.get("width", 0.5)

        svg.append(
            f'<path d="{path_data.strip()}" '
            f'stroke="{stroke}" stroke-width="{width}" '
            f'fill="none" vector-effect="non-scaling-stroke" />'
        )

    svg.append('</svg>')
    return "\n".join(svg)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--page", type=int, default=1, help="1-based page number")
    args = ap.parse_args(argv)

    doc = fitz.open(args.infile)
    if args.page < 1 or args.page > doc.page_count:
        ap.error("page out of range")

    page = doc[args.page-1]
    svg  = page_to_svg(page)

    with open(args.outfile, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {args.outfile}")

if __name__ == "__main__":
    main(sys.argv[1:])
