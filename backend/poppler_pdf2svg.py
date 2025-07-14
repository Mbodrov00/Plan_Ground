# backend/poppler_pdf2svg.py
import tempfile, subprocess, os, glob
from flask import Flask, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PDFTOCAIRO = "pdftocairo"                 # update with full path if needed

@app.route("/pdf2svg", methods=["POST"])
def pdf2svg():
    f    = request.files.get("file")
    page = int(request.form.get("page", 1))

    if not f or f.content_type != "application/pdf":
        return "No PDF supplied", 400

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "in.pdf")
        f.save(pdf_path)

        # ---------- run Poppler ---------------------------------------
        svg_target = os.path.join(tmp, "out.svg")   # explicit .svg
        cmd = [
            PDFTOCAIRO, "-svg",
            "-f", str(page), "-l", str(page),
            pdf_path, svg_target                    # <── output path
        ]
        try:
            res = subprocess.run(
                cmd, cwd=tmp,
                capture_output=True, text=True, check=True
            )
            if res.stderr.strip():
                print("pdftocairo stderr:\n", res.stderr)
        except FileNotFoundError:
            return "pdftocairo executable not found – adjust PDFTOCAIRO", 500
        except subprocess.CalledProcessError as e:
            return f"POPPLER_ERROR:\n{e.stderr or e.stdout}", 500

        # ---------- locate the SVG (3 possible places) ----------------
        candidates = [
            svg_target,                              # ① exact path
            *glob.glob(os.path.join(tmp, "out-*.svg")),          # ② out-1.svg / out-000001.svg …
            *glob.glob(os.path.join(tmp, "out", "*.svg")),       # ③ inside an 'out' dir
        ]
        svg_path = next((p for p in candidates if os.path.isfile(p)), None)
        if not svg_path:
            return ("Poppler ran but no SVG found.\n"
                    f"tmp contents: {os.listdir(tmp)}"), 500

        with open(svg_path, "r", encoding="utf-8") as fh:
            svg_text = fh.read()

    return Response(svg_text, mimetype="image/svg+xml")

if __name__ == "__main__":
    app.run(port=8000, debug=True)
