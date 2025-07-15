/* ----------------------------------------------------------- *
 *  public/js/script.js    ❶ ES-MODULE                         *
 * ----------------------------------------------------------- */

import {
  getTransformState,
  setTransformState,
  applyZoom,
  handlePanning,
  minZoom,
  maxZoom,
}                             from './canvas_transform.js';
import { applyViewportTransform } from './syncViewport.js';

/* ---------- PDF.js worker path ---------- */
pdfjsLib.GlobalWorkerOptions.workerSrc = './public/js/pdf.worker.min.js';

/* ---------- DOM refs ---------- */
const wrapper      = document.getElementById('canvasWrapper');
const canvas       = document.getElementById('drawingCanvas');
const ctx          = canvas.getContext('2d', { willReadFrequently: true });

const drawingBtn   = document.getElementById('drawingModeBtn');
const eraserBtn    = document.getElementById('eraserModeBtn');
const undoBtn      = document.getElementById('undoBtn');

const importBtn    = document.getElementById('importButton');
const fileInput    = document.getElementById('fileInput');

const resizeHandle = document.querySelector('.resize-handle');
const container    = document.querySelector('.container');

/* --- theme toggle buttons --- */
const themeToggle  = document.getElementById('themeToggleButton'); // hamburger dropdown
const lightBtn     = document.getElementById('lightMode');
const darkBtn      = document.getElementById('darkMode');

/* ---------- viewport helper ---------- */
function updateViewport() {
  applyViewportTransform(wrapper, getTransformState());
}

/* ---------- init zoom / pan ---------- */
setTransformState(1, 0, 0);
updateViewport();
handlePanning(canvas, updateViewport);

canvas.addEventListener('wheel', e => {
  e.preventDefault();
  const pivotX = e.clientX - wrapper.offsetLeft;   // layout coords
  const pivotY = e.clientY - wrapper.offsetTop;
  applyZoom(e.deltaY * -0.001, pivotX, pivotY);
  updateViewport();
});

/* ---------- undo stack & redraw ---------- */
const eraserSize = 20;
const undoStack  = [];
function saveCanvasState() { undoStack.push(canvas.toDataURL()); if (undoStack.length>50) undoStack.shift(); }
function clearUndoStack()   { undoStack.length = 0; saveCanvasState(); }
function redrawCanvas() {
  if (!undoStack.length) return;
  const img = new Image();
  img.onload = () => { ctx.clearRect(0,0,canvas.width,canvas.height); ctx.drawImage(img,0,0); };
  img.src = undoStack[undoStack.length-1];
}

/* ---------- FileImportManager ---------- */
if (window.FileImportManager) {
  new window.FileImportManager(canvas, ctx, saveCanvasState, redrawCanvas, clearUndoStack)
      .setupFileInputHandlers(importBtn, fileInput);
}

/* ---------- canvas resize ---------- */
function resizeCanvas() {
  const { width, height } = canvas.getBoundingClientRect();
  canvas.width  = width;
  canvas.height = height;
  ctx.lineCap   = 'round';
  ctx.lineWidth = 2;
  ctx.strokeStyle='black';
  if (!undoStack.length) saveCanvasState();
  redrawCanvas();
}
resizeCanvas();
window.addEventListener('resize', () => setTimeout(resizeCanvas,100));

/* ---------- drawing / erasing ---------- */
let isDrawing=false,isDrawingMode=false,isEraserMode=false,lastX=0,lastY=0;
function map(e){ const {zoomLevel,panX,panY}=getTransformState(); return{ x:(e.offsetX-panX)/zoomLevel, y:(e.offsetY-panY)/zoomLevel }; }

drawingBtn.addEventListener('click',()=>{ isDrawingMode=!isDrawingMode; if(isDrawingMode){isEraserMode=false; eraserBtn.classList.remove('active');} drawingBtn.classList.toggle('active'); canvas.style.cursor=isDrawingMode?'crosshair':'default'; });
eraserBtn.addEventListener('click',()=>{ isEraserMode=!isEraserMode; if(isEraserMode){isDrawingMode=false; drawingBtn.classList.remove('active');} eraserBtn.classList.toggle('active'); canvas.style.cursor=isEraserMode?'cell':'default'; ctx.lineWidth=eraserSize; });

canvas.addEventListener('mousedown',e=>{
  if(e.button!==0||(!isDrawingMode&&!isEraserMode)) return;
  isDrawing=true; const p=map(e); lastX=p.x; lastY=p.y; ctx.beginPath(); ctx.moveTo(lastX,lastY);
});
canvas.addEventListener('mousemove',e=>{
  if(!isDrawing) return;
  const p=map(e); ctx.lineTo(p.x,p.y);
  ctx.globalCompositeOperation = isEraserMode ? 'destination-out' : 'source-over';
  ctx.stroke(); lastX=p.x; lastY=p.y;
});
['mouseup','mouseleave'].forEach(evt=>canvas.addEventListener(evt,()=>{ if(!isDrawing) return; isDrawing=false; saveCanvasState(); }));

/* ---------- Undo ---------- */
undoBtn.addEventListener('click',()=>{ if(undoStack.length>1) undoStack.pop(); redrawCanvas(); });

/* ---------- sidebar resize ---------- */
let resizing = false;

resizeHandle.addEventListener('mousedown', () => { resizing = true; });

document.addEventListener('mousemove', e => {
  if (!resizing) return;
  const w = Math.min(Math.max(e.clientX, 50), 300);
  // 👇 fixed: value wrapped in a template literal
  container.style.gridTemplateColumns = `${w}px 1fr`;
  // give the canvas a moment to settle before resizing
  setTimeout(resizeCanvas, 10);
});

document.addEventListener('mouseup', () => { resizing = false; });


/* ----------------------------------------------------------- *
 *  Theme toggle & dropdown                                    *
 * ----------------------------------------------------------- */
function applyTheme(mode){                     // 'light' | 'dark'
  if(mode==='dark'){ document.body.classList.add('dark-mode'); }
  else              { document.body.classList.remove('dark-mode'); }
  localStorage.setItem('theme',mode);
}
const storedTheme = localStorage.getItem('theme') || 'light';
applyTheme(storedTheme);

lightBtn.addEventListener('click',e=>{ e.preventDefault(); applyTheme('light'); });
darkBtn .addEventListener('click',e=>{ e.preventDefault(); applyTheme('dark'); });

/* optional: close dropdown when clicked outside */
document.addEventListener('click',e=>{
  if(!themeToggle.contains(e.target)) themeToggle.parentElement.classList.remove('open');
});
themeToggle.addEventListener('click',()=> themeToggle.parentElement.classList.toggle('open'));

/* ----------------------------------------------------------- *
 *  ANALYZE Button: send SVG to backend                        *
 * ----------------------------------------------------------- */

const analyzeBtn = document.getElementById("analyzeButton");

if (analyzeBtn) {
  analyzeBtn.addEventListener("click", async () => {
    const svgElement = document.querySelector("svg"); // Adjust this if needed
    if (!svgElement) {
      alert("No SVG found to analyze.");
      return;
    }

    const svgData = new XMLSerializer().serializeToString(svgElement);

    try {
      const response = await fetch("http://127.0.0.1:8000/analyse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ svg: svgData }),      // JSON → easier to extend later
      });



      function renderTable(classes) {
        // remove any previous table
        document.getElementById("analyseTable")?.remove();

        const tbl = document.createElement("table");
        tbl.id = "analyseTable";
        Object.assign(tbl.style, {
          position: "absolute",
          bottom: "8px",
          right:  "8px",
          fontSize: "10px",
          background: "rgba(255,255,255,0.85)",
          border: "1px solid #666",
          borderCollapse: "collapse",
          zIndex: 99
        });

        const addRow = (k, v) => {
          const tr = tbl.insertRow();
          tr.insertCell().textContent = k;
          tr.insertCell().textContent = v;
        };

        addRow("── Elements ──", "");
        for (const [tag, n] of Object.entries(classes.tags).sort((a,b)=>b[1]-a[1])) {
          addRow(tag, n);
        }
        addRow("── Strokes (px) ──", "");
        for (const [w, n] of Object.entries(classes.strokes_px).sort((a,b)=>+b[0]-+a[0])) {
          addRow(`${w}px`, n);
        }

        wrapper.appendChild(tbl);
      }









      const { svg: cleanedSvg, stats, classes } = await response.json();

      // Replace the old <svg> with the cleaned one
      const parser = new DOMParser();
      const freshSvg = parser.parseFromString(cleanedSvg, "image/svg+xml").documentElement;
      svgElement.replaceWith(freshSvg);

      console.table(stats);
      renderOverlayTable(freshSvg, classes);   // ← pass the real element
      alert("Analyse complete. Hover the overlay to filter.");
    } catch (err) {
      console.error("Analysis failed:", err);
      alert("Failed to analyze SVG.");
    }
  });
}



/* ---------- multi-select filter state ---------- */
let selectedTags    = new Set();   // e.g. {"path","circle"}
let selectedStrokes = new Set();   // e.g. {1, 2}

function updateVisibility(svg) {
  // Nothing ticked ➜ show everything
  const tagFilterOn    = selectedTags.size    > 0;
  const strokeFilterOn = selectedStrokes.size > 0;

  const px = el => {
    const sw = el.getAttribute("stroke-width") ||
               (el.style && el.style.strokeWidth);
    return sw ? Math.round(parseFloat(sw) * 100) / 100 : 1;
  };

  svg.querySelectorAll("*").forEach(el => {
    const tag    = el.tagName.toLowerCase();
    const stroke = px(el);

    const tagOK    = !tagFilterOn    || selectedTags.has(tag);
    const strokeOK = !strokeFilterOn || selectedStrokes.has(stroke);

    el.style.display = (tagOK && strokeOK) ? "" : "none";
  });
}


function renderOverlayTable(svg, classes) {
  document.getElementById("analyseOverlay")?.remove();      // wipe old

  const box = document.createElement("div");
  Object.assign(box, {
    id: "analyseOverlay",
    style: `
      position:fixed; bottom:12px; right:12px;
      background:rgba(255,255,255,0.9); border:1px solid #666;
      border-radius:4px; font:11px/1.4 monospace; z-index:2000;
      padding:4px 6px;
    `
  });

  const tbl = document.createElement("table");
  tbl.style.borderCollapse = "collapse";

  const makeRow = (label, count, type, value) => {
    const tr = tbl.insertRow();
    const c0 = tr.insertCell();           // checkbox + label
    const c1 = tr.insertCell();           // count
    c1.textContent = count;
    [c0,c1].forEach(c=>c.style.border="1px solid #999");

    if (type) {   // data row
      const id = `chk_${type}_${value}`.replace(/[^a-z0-9_]/gi,"");
      c0.innerHTML =
        `<label style="cursor:pointer">
           <input type="checkbox" id="${id}"
                  data-type="${type}" data-value="${value}">
           ${label}
         </label>`;
    } else {      // header row
      c0.colSpan = 2;
      c0.style.background="#eee";
      c0.style.textAlign="center";
    }
  };

  makeRow("─ elements ─", "", null, null);
  for (const [tag,n] of Object.entries(classes.tags).sort((a,b)=>b[1]-a[1])) {
    makeRow(tag, n, "tag", tag);
  }
  makeRow("─ strokes(px) ─", "", null, null);
  for (const [w,n] of Object.entries(classes.strokes_px).sort((a,b)=>+b[0]-+a[0])) {
    makeRow(w, n, "stroke", +w);
  }

  tbl.addEventListener("change", e => {
    const cb    = e.target;
    const type  = cb.dataset.type;
    const value = cb.dataset.value;
    if (!type) return;            // header row

    const set = (type === "tag") ? selectedTags : selectedStrokes;
    if (cb.checked) set.add(type === "stroke" ? +value : value);
    else            set.delete(type === "stroke" ? +value : value);

    updateVisibility(svg);
  });

  box.appendChild(tbl);
  document.body.appendChild(box);
}
