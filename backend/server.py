# backend/server.py
from flask import Flask, request, Response, jsonify
from flask_cors import CORS

from poppler_convert import pdf_page_to_svg, PopplerError
import analyse_svg, modify_svg   # your stub modules (can stay empty)

app = Flask(__name__)
CORS(app)

# ─────────────────────────────── 1. PDF → SVG
@app.route("/pdf2svg", methods=["POST"])
def pdf2svg_route():
    upload = request.files.get("file")
    page   = int(request.form.get("page", 1))

    if not upload or upload.content_type != "application/pdf":
        return "No PDF uploaded", 400

    try:
        svg_text = pdf_page_to_svg(upload.read(), page)
    except PopplerError as err:
        # 500 so the front-end still enters the “failed to fetch” branch
        return str(err), 500

    return Response(svg_text, mimetype="image/svg+xml")


# ─────────────────────────────── 2. Analyse (stub demo)
@app.route("/analyse", methods=["POST"])
def analyse_route():
    data = request.get_json(force=True)  # { "svg": "<svg …>" }
    svg_text = data.get("svg", "")
    return jsonify(analyse_svg.analyse(svg_text))


# ─────────────────────────────── 3. Modify  (stub demo)
@app.route("/modify", methods=["POST"])
def modify_route():
    svg_text = request.get_data(as_text=True)
    keep     = request.args.get("keep", "strokes")
    new_svg  = modify_svg.simplify(svg_text, keep=keep)
    return Response(new_svg, mimetype="image/svg+xml")


# ─────────────────────────────── run
if __name__ == "__main__":
    # one backend process for *all* features
    app.run(port=8000, debug=True)




import identify_rooms          # new helper

# ─────────────────────────────── 4. Identify Rooms
@app.route("/identify_rooms", methods=["POST"])
def identify_rooms_route():
    data     = request.get_json(force=True)      # { "svg": "<svg …>" }
    svg_text = data.get("svg", "")
    rooms    = identify_rooms.identify(svg_text)
    return jsonify({"rooms": rooms})
