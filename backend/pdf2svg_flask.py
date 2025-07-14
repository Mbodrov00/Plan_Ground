# backend/pdf2svg_flask.py
from flask import Flask, request, Response
from flask_cors import CORS
import fitz, io, tempfile, subprocess, os, sys, json

# import the page_to_svg helper directly from your script
from convert_pdf_to_svg import page_to_svg

app = Flask(__name__)
CORS(app)      

@app.route('/pdf2svg', methods=['POST'])
def pdf2svg():
    f = request.files.get('file')
    page = int(request.form.get('page', 1))
    if not f or f.content_type != 'application/pdf':
        return 'No PDF supplied', 400

    data = f.read()
    doc  = fitz.open(stream=data, filetype='pdf')
    if page < 1 or page > doc.page_count:
        return 'Page out of range', 400

    svg = page_to_svg(doc[page-1])
    return Response(svg, mimetype='image/svg+xml')

if __name__ == '__main__':
    app.run(port=8000, debug=True)

