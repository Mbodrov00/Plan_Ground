# modify_svg.py
def simplify(svg_text: str, *, keep="strokes") -> str:
    """Return simplified SVG (stub)."""
    # Very naive example – remove <text> if keep != "text"
    if "text" not in keep:
        import re
        svg_text = re.sub(r"<text.*?</text>", "", svg_text, flags=re.S)
    return svg_text
