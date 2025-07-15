// canvas_transform.js
// -------------------------------------------------------------
// Holds global zoom / pan state and basic interaction helpers.
// -------------------------------------------------------------

let zoomLevel = 1;
let panX      = 0;
let panY      = 0;

export const minZoom = 0.1;
export const maxZoom = 10;

/* ----------  state getters / setters  ---------- */
export function getTransformState() {
  return { zoomLevel, panX, panY };
}

export function setTransformState(z, x, y) {
  zoomLevel = z;
  panX      = x;
  panY      = y;
}

/* ----------  zoom helper  ---------- */
/**
 * Adjusts zoomLevel, panX, panY so that the point (pivotX, pivotY)
 * stays under the cursor while zooming.
 *
 * @param {number} delta   +0.1 to zoom in ~10 %, -0.1 to zoom out …
 * @param {number} [pivotX=0]  pivot in wrapper-coords (not canvas!)
 * @param {number} [pivotY=0]
 */
export function applyZoom(delta, pivotX = 0, pivotY = 0) {
  const oldZoom = zoomLevel;
  const newZoom = Math.max(minZoom, Math.min(maxZoom, oldZoom * (1 + delta)));
  if (newZoom === oldZoom) return;               // clamped, no change

  const factor = newZoom / oldZoom;
  panX = pivotX - (pivotX - panX) * factor;
  panY = pivotY - (pivotY - panY) * factor;
  zoomLevel = newZoom;
}

/* ----------  interactive panning  ---------- */
/**
 * Attaches Ctrl+Right-drag panning to a DOM element (usually the canvas).
 * Calls updateViewport() (provided by the caller) *throttled* via rAF.
 */
export function handlePanning(targetElement, updateViewport) {
  let isPanning   = false;
  let lastX       = 0;
  let lastY       = 0;
  let needsUpdate = false;

  function rafUpdate() {
    if (needsUpdate) {
      needsUpdate = false;
      updateViewport();
    }
    if (isPanning) requestAnimationFrame(rafUpdate);
  }

  targetElement.addEventListener('mousedown', e => {
    if (e.buttons === 2 && e.ctrlKey) {          // Ctrl + right button
      isPanning = true;
      lastX = e.clientX;
      lastY = e.clientY;
      targetElement.style.cursor = 'grabbing';
      e.preventDefault();
      requestAnimationFrame(rafUpdate);
    }
  });

  targetElement.addEventListener('mousemove', e => {
    if (!isPanning) return;
    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;
    panX += dx;
    panY += dy;
    lastX = e.clientX;
    lastY = e.clientY;
    needsUpdate = true;
  });

  const stop = () => {
    if (isPanning) {
      isPanning = false;
      targetElement.style.cursor = 'default';
    }
  };

  targetElement.addEventListener('mouseup',      stop);
  targetElement.addEventListener('mouseleave',   stop);
  targetElement.addEventListener('contextmenu',  e => e.preventDefault());
}