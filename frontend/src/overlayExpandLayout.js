/** Compact overlay player is portaled to document.body so expand never relocates <video>. */

export const OVERLAY_PORTAL_Z_COMPACT = 35;
export const OVERLAY_PORTAL_Z_EXPANDED = 99999;

export function overlaySlotAspect(overlayData, videoAspect) {
  const live = Number(videoAspect);
  if (Number.isFinite(live) && live > 0.05) return live;
  const w = Number(overlayData?.frame_width_px);
  const h = Number(overlayData?.frame_height_px);
  if (w > 0 && h > 0) return w / h;
  return 16 / 9;
}

export function overlaySlotReserveStyle(aspect) {
  const a = Number(aspect);
  return {
    width: "100%",
    aspectRatio: Number.isFinite(a) && a > 0.05 ? String(a) : "16 / 9",
    minHeight: 200,
    maxHeight: "80vh",
  };
}

export function readSlotBox(el) {
  if (!el || typeof el.getBoundingClientRect !== "function") return null;
  const r = el.getBoundingClientRect();
  if (!(r.width >= 2) || !(r.height >= 2)) return null;
  return {
    left: Math.round(r.left),
    top: Math.round(r.top),
    width: Math.round(r.width),
    height: Math.round(r.height),
  };
}

export function overlayPortalStyle({ isExpanded, slot } = {}) {
  if (isExpanded) {
    return {
      position: "fixed",
      top: 0,
      right: 0,
      bottom: 0,
      left: 0,
      zIndex: OVERLAY_PORTAL_Z_EXPANDED,
      width: "100%",
      height: "100%",
      maxWidth: "100vw",
      maxHeight: "100dvh",
    };
  }
  if (!slot || !(slot.width >= 2) || !(slot.height >= 2)) {
    return {
      position: "fixed",
      left: 0,
      top: 0,
      width: 8,
      height: 8,
      opacity: 0,
      pointerEvents: "none",
      zIndex: 0,
    };
  }
  return {
    position: "fixed",
    left: slot.left,
    top: slot.top,
    width: slot.width,
    height: slot.height,
    zIndex: OVERLAY_PORTAL_Z_COMPACT,
    maxHeight: "none",
  };
}
