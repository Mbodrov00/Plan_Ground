// syncViewport.js
export function applyViewportTransform(wrapper, { zoomLevel, panX, panY }) {
  wrapper.style.transformOrigin = '0 0';                       // top-left
  wrapper.style.transform       = `translate(${panX}px, ${panY}px) scale(${zoomLevel})`;
}
