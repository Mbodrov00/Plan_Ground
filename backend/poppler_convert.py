# backend/poppler_convert.py
"""
Pure helper – **no** Flask code.
Turns one PDF page (bytes) into an SVG string via Poppler (pdftocairo).
"""

import subprocess, tempfile, shutil
from pathlib import Path

# ---------------------------------------------------------------------- #
# Config – point to pdftocairo.  If it’s on PATH, auto-detect via which().
# ---------------------------------------------------------------------- #
PDFTOCAIRO = shutil.which("pdftocairo") or "pdftocairo"


class PopplerError(RuntimeError):
    """Raised when pdftocairo cannot produce the expected SVG."""


# ---------------------------------------------------------------------- #
# Public helper
# ---------------------------------------------------------------------- #
def pdf_page_to_svg(pdf_bytes: bytes, page: int = 1) -> str:
    """
    Convert *page* (1-based) of a PDF (supplied as raw bytes) to SVG.
    Returns the SVG markup as a UTF-8 string or raises ``PopplerError``.
    """
    if page < 1:
        raise ValueError("page number must be ≥ 1")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        # ① write incoming PDF to disk
        pdf_path = tmp / "in.pdf"
        pdf_path.write_bytes(pdf_bytes)

        # ② run Poppler – use an explicit output file name so we know it
        svg_target = tmp / "out.svg"
        cmd = [
            PDFTOCAIRO, "-svg",
            "-f", str(page), "-l", str(page),
            str(pdf_path), str(svg_target)          # explicit output
        ]

        try:
            res = subprocess.run(
                cmd, cwd=tmp,
                capture_output=True, text=True, check=True
            )
            if res.stderr.strip():                  # log warnings, not an error
                print("pdftocairo stderr:\n", res.stderr)
        except FileNotFoundError:
            raise PopplerError(
                f"pdftocairo executable not found – adjust PDFTOCAIRO ({PDFTOCAIRO})"
            )
        except subprocess.CalledProcessError as e:
            raise PopplerError(
                f"Poppler failed (exit {e.returncode}):\n{e.stderr or e.stdout}"
            )

        # ③ locate the SVG (three places, like the old script)
        candidates = [
            svg_target,                             # out.svg (explicit name)
            *tmp.glob("out-*.svg"),                 # out-1.svg / out-000001.svg
        ]
        out_dir = tmp / "out"
        if out_dir.is_dir():
            candidates.extend(out_dir.glob("*.svg"))  # inside sub-dir “out”

        svg_path = next((p for p in candidates if p.is_file()), None)
        if not svg_path:
            raise PopplerError(
                "Poppler ran but no SVG produced. Temp dir contained: "
                f"{[p.name for p in tmp.iterdir()]}"
            )

        # ④ return the SVG text
        return svg_path.read_text(encoding="utf-8")
