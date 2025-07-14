# backend/pdf2svg_chain.py
import tempfile, subprocess, os, glob, shutil
from flask import Flask, request, Response
from flask_cors  import CORS

app = Flask(__name__)
CORS(app)

PDFTOCAIRO = "pdftocairo"    # edit if not on PATH
MUTOOL     = "mutool"        # -> mutool draw -F svg …

def run_cmd(cmd, cwd):
    """run and return (success, stdout/err text)"""
    try:
        out = subprocess.run(cmd, cwd=cwd,
                             capture_output=True, text=True, check=True)
        return True,  out.stdout + out.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout + e.stderr
    except FileNotFoundError as e:
        return False, str(e)

@app.route("/pdf2svg", methods=["POST"])
def pdf2svg():
    f    = request.files.get("file")
    page = int(request.form.get("page", 1))
    if not f or f.content_type != "application/pdf":
        return "No PDF supplied", 400

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "in.pdf")
        f.save(pdf_path)

        # ───────────────── try Poppler ─────────────────
        pop_svg = os.path.join(tmp, "pop.svg")
        ok, msg = run_cmd(
            [PDFTOCAIRO, "-svg", "-f", str(page), "-l", str(page),
             pdf_path, pop_svg], tmp)

        svg_path = None
        if ok:
            # Poppler may name file out-1.svg; glob for any svg
            svgs = glob.glob(os.path.join(tmp, "*.svg"))
            svg_path = svgs[0] if svgs else None
        else:
            print("Poppler failed, falling back → MuPDF\n", msg)

        # ───────────────── try MuPDF if needed ─────────
        if svg_path is None:
            mup_svg = os.path.join(tmp, "mup.svg")
            ok, msg = run_cmd(
                [MUTOOL, "draw", "-q", "-F", "svg",
                 "-o", mup_svg, "-f", str(page), "-l", str(page),
                 pdf_path], tmp)
            if ok and os.path.isfile(mup_svg):
                svg_path = mup_svg
            else:
                return "Both converters failed:\n" + msg, 500

        with open(svg_path, "r", encoding="utf-8") as fh:
            svg_text = fh.read()

    return Response(svg_text, mimetype="image/svg+xml")

if __name__ == "__main__":
    app.run(port=8000, debug=True)
