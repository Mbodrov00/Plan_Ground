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

  /* ───── PDF → SVG (vector-only) ───── */
  FileImportManager.prototype.handlePDFImport = function (file) {
    const reader = new FileReader();
    reader.onload = () => {
      const PDFOPTS = {
        data: new Uint8Array(reader.result),
        fontExtraProperties: true,
        useSystemFonts: true,
        disableFontFace: true,
      };

      pdfjsLib.getDocument(PDFOPTS).promise
        .then(pdf => pdf.getPage(1))
        .then(async page => {
          const viewport = page.getViewport({ scale: 1 });
          const ops      = await page.getOperatorList();

          const makeSVG = async (embed) => {
            const gfx = new pdfjsLib.SVGGraphics(page.commonObjs, page.objs);
            gfx.embedFonts = embed;
            return gfx.getSVG(ops, viewport);
          };

          /* --------------------------------------------------------
           *  Build SVG until something drawable appears.
           *  Passes:
           *    1) fonts embedded                      (full fidelity)
           *    2) no-embed                            (lighter)
           *    3) no-embed + disablePattern           (drops pattern paint)
           *    4) no-embed + disablePattern + disableImage
           *       (drops inline images & shadings)
           * -------------------------------------------------------- */
          let svg = null;
          const passes = [
            { embedFonts: true,  opts: {} },
            { embedFonts: false, opts: {} },
            { embedFonts: false, opts: { disablePattern: true } },
            { embedFonts: false, opts: { disablePattern: true, disableImage: true } },
          ];

          for (const p of passes) {
            try {
              const opList = Object.keys(p.opts).length
                ? await page.getOperatorList(p.opts)
                : ops;                                     // ops from earlier

              const gfx = new pdfjsLib.SVGGraphics(page.commonObjs, page.objs);
              gfx.embedFonts = p.embedFonts;
              svg = await gfx.getSVG(opList, viewport);

              stripComplexFills(svg);
              if (hasDrawableContent(svg)) {
                console.log(`SVG generated on pass ${passes.indexOf(p) + 1}`);
                break;
              }
            } catch (err) {
              console.warn(`SVGGraphics failed on pass ${passes.indexOf(p)+1}`, err);
            }
          }

          if (!svg || !hasDrawableContent(svg)) {
            console.warn('All passes produced no drawable content – page skipped.');
            return;                                         // leave canvas untouched
          }

          return { svg, viewport };

        })
        .then(res => {
          if (!res) return;                                 // nothing to show
          const { svg, viewport } = res;

          /* sizing / inject */
          const parent = this.canvas.parentElement || this.canvas;
          const rect   = parent.getBoundingClientRect();
          const scale  = Math.min(rect.width / viewport.width,
                                  rect.height / viewport.height, 1);
          svg.setAttribute('viewBox', `0 0 ${viewport.width} ${viewport.height}`);
          svg.setAttribute('width',  viewport.width  * scale);
          svg.setAttribute('height', viewport.height * scale);
          Object.assign(svg.style, {
            position: 'absolute', top: 0, left: 0,
            zIndex: 2, pointerEvents: 'none'
          });
          svg.dataset.import = 'pdf';

          parent.querySelector('svg[data-import="pdf"]')?.remove();
          parent.appendChild(svg);
          console.log('PDF imported as simplified vector SVG.');
        })
        .catch(err => {
          console.error('PDF import failed', err);
          alert('Failed to import PDF: ' + err.message);
        });
    };
    reader.readAsArrayBuffer(file);
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
