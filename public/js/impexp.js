// public/js/impexp.js
// FileImportManager – always-vector import (problematic fills stripped)
window.FileImportManager = (function () {
  'use strict';

  /* ───── constructor ───── */
  function FileImportManager(canvas, ctx, save, redraw, clearUndo) {
    this.canvas = canvas;
    this.ctx    = ctx;
    this.saveCanvasState = save;
    this.redrawCanvas    = redraw;
    this.clearUndoStack  = clearUndo;

    const BASE = 'https://unpkg.com/pdfjs-dist@3.11.174/';
    Object.assign(pdfjsLib.GlobalWorkerOptions, {
      workerSrc:           `${BASE}build/pdf.worker.js`,
      standardFontDataUrl: `${BASE}standard_fonts/`,
      cMapUrl:             `${BASE}cmaps/`,
      cMapPacked:          true
    });
  }


  /**
   * POST a File object to the backend and return the plain-text response.
   * Expects backend route `/pdf2svg` that runs convert_pdf_to_svg.py
   * and returns the SVG markup (UTF-8 text).
   */
  async function convertPdfOnBackend(file, page = 1) {
    const fd = new FormData();
    fd.append('file', file, file.name);
    fd.append('page', page);

    const res = await fetch('http://127.0.0.1:8000/pdf2svg', {
      method: 'POST',
      body:   fd,
      mode:   'cors'            // <- optional but explicit
    });
    if (!res.ok) throw new Error(await res.text());
    return await res.text();                       // <-- was missing await
  }








    /* ───── helper: remove unsupported paint & clipping ───── */
    function stripComplexFills(svg) {

    /* ----------------------------------------------------
    * 1.  Remove <defs> that cause invisibility
    * -------------------------------------------------- */
    svg.querySelectorAll(
        'pattern,linearGradient,radialGradient,image,clipPath'
    ).forEach(def => def.remove());

    /* ----------------------------------------------------
    * 2.  For every visible element, normalise style
    * -------------------------------------------------- */
    svg.querySelectorAll(
        'path,rect,circle,ellipse,polygon,polyline,line,text'
    ).forEach(el => {

        /* a) kill clip-path references  */
        if (el.hasAttribute('clip-path')) el.removeAttribute('clip-path');

        /* b) translate paint that references removed defs    */
        const fixPaintAttr = (attr, fallback) => {
        const val = el.getAttribute(attr);
        if (val && val.startsWith('url(')) {
            el.setAttribute(attr, fallback);
        }
        };

        fixPaintAttr('fill',   'none');
        fixPaintAttr('stroke', '#999');

        /* c) ensure something is visible                    */
        const f = el.getAttribute('fill');
        const s = el.getAttribute('stroke');
        if ((f === 'none' || !f) && (!s || s === 'none')) {
        el.setAttribute('stroke', '#999');
        el.setAttribute('stroke-width', '0.25');
        el.setAttribute('fill', 'none');
        }

        /* d) very low‐opacity shapes → bump up opacity      */
        const op  = parseFloat(el.getAttribute('fill-opacity') || 1);
        const sop = parseFloat(el.getAttribute('stroke-opacity') || 1);
        if (!isNaN(op)  && op  < 0.02) el.setAttribute('fill-opacity',   '0.02');
        if (!isNaN(sop) && sop < 0.02) el.setAttribute('stroke-opacity', '0.02');
    });
    }



  function hasDrawableContent(svg) {
    return svg.querySelector('path,rect,circle,ellipse,polygon,polyline,line,text');
  }

  /* ───── NEW: delegate PDF → SVG to backend (PyMuPDF) ───── */
  FileImportManager.prototype.handlePDFImport = async function (file) {
    try {
      /* ① send the PDF to backend and get clean SVG text */
      const svgText = await convertPdfOnBackend(file /* , page = 1 */);

      /* ② parse the SVG string into a DOM element */
      const parser = new DOMParser();
      const svgEl  = parser.parseFromString(svgText, 'image/svg+xml')
                          .documentElement;

      /* ③ inject into the wrapper (same as before) */
      const parent = this.canvas.parentElement || this.canvas;
      const vb   = svgEl.viewBox.baseVal;
      
      /* make the SVG stretch to the wrapper – no fiddly scale maths */
      svgEl.removeAttribute('width');
      svgEl.removeAttribute('height');
      svgEl.style.width  = '100%';
      svgEl.style.height = '100%';
      svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');
      Object.assign(svgEl.style, {
        position: 'absolute', top: 0, left: 0,
        zIndex: 2, pointerEvents: 'none'
      });
      svgEl.dataset.import = 'pdf';

      parent.querySelector('svg[data-import="pdf"]')?.remove();
      parent.appendChild(svgEl);
      console.log('PDF imported via backend (geometry-only SVG).');

    } catch (err) {
      console.error('Could not convert PDF', err);
      alert('PDF import failed: ' + err.message);
    }
  };


  /* ───── SVG + bitmap imports (unchanged) ───── */
  FileImportManager.prototype.handleSVGImport = function (file) {
    const r=new FileReader(); r.onload=e=>{
      const img=new Image(); img.onload=()=>{
        const {width:cw,height:ch}=this.canvas;
        const s=Math.min(cw/img.width,ch/img.height,1);
        this.ctx.clearRect(0,0,cw,ch);
        this.ctx.drawImage(img,(cw-img.width*s)/2,(ch-img.height*s)/2,img.width*s,img.height*s);
        this.saveCanvasState();
      }; img.src=e.target.result;
    }; r.readAsDataURL(file);
  };
  FileImportManager.prototype.handleImageImport = function (file) {
    const r=new FileReader(); r.onload=e=>{
      const img=new Image(); img.onload=()=>{
        const {width:cw,height:ch}=this.canvas;
        const s=Math.min(cw/img.width,ch/img.height,1);
        this.ctx.clearRect(0,0,cw,ch);
        this.ctx.drawImage(img,(cw-img.width*s)/2,(ch-img.height*s)/2,img.width*s,img.height*s);
        this.saveCanvasState();
      }; img.src=e.target.result;
    }; r.readAsDataURL(file);
  };

  /* ───── router & UI wiring ───── */
  FileImportManager.prototype.handleFileImport = function (f) {
    if (!f) return;
    if (f.type === 'application/pdf')        this.handlePDFImport(f);
    else if (f.type === 'image/svg+xml')     this.handleSVGImport(f);
    else if (f.type.match(/^image\//))       this.handleImageImport(f);
    else alert('Unsupported file type: ' + f.type);
  };
  FileImportManager.prototype.setupFileInputHandlers = function (btn, input) {
    btn.addEventListener('click', () => input.click());
    input.addEventListener('change', e => {
      this.handleFileImport(e.target.files[0]);
      input.value = '';
    });
  };

  return FileImportManager;
})();
