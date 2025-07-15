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
  const r = wrapper.getBoundingClientRect();
  applyZoom(e.deltaY * -0.001, e.clientX - r.left, e.clientY - r.top);
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
let resizing=false;
resizeHandle.addEventListener('mousedown',()=>{ resizing=true; });
document.addEventListener('mousemove',e=>{
  if(!resizing) return;
  const w=Math.min(Math.max(e.clientX,50),300);
  container.style.gridTemplateColumns=`${w}px 1fr`;
  setTimeout(resizeCanvas,10);
});
document.addEventListener('mouseup',()=>{ resizing=false; });

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
      const response = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ svg: svgData }),
      });

      const result = await response.json();
      console.log("Analysis result:", result);
      alert("Analysis complete. Check console.");
    } catch (err) {
      console.error("Analysis failed:", err);
      alert("Failed to analyze SVG.");
    }
  });
}
