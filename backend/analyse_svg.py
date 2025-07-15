# analyse_svg.py
def analyse(svg_text: str) -> dict:
    """Return JSON-serialisable analysis (stub)."""
    return {"num_paths": svg_text.count("<path")}
