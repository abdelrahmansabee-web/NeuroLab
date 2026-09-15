/** Compact overlay player stays in the card. Expand uses CSS fixed on the same node. */

export const OVERLAY_PORTAL_Z_COMPACT = "auto";
export const OVERLAY_PORTAL_Z_EXPANDED = 99999;

/** Properties that create a containing block for position:fixed. Never overflow. */
const CONTAINING_BLOCK_STYLE_KEYS = [
  "filter",
  "webkitFilter",
  "backdropFilter",
  "webkitBackdropFilter",
  "transform",
  "willChange",
  "contain",
  "perspective",
  "clipPath",
  "webkitClipPath",
];

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

/** Same node for compact and expand so iPad never relocates <video>. */
export function overlayPlayerChromeStyle({ isExpanded } = {}) {
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
  return {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    zIndex: OVERLAY_PORTAL_Z_COMPACT,
    maxHeight: "none",
  };
}

/** @deprecated Use overlayPlayerChromeStyle. Compact is in-flow, not a body portal. */
export function overlayPortalStyle({ isExpanded, slot } = {}) {
  if (isExpanded) return overlayPlayerChromeStyle({ isExpanded: true });
  void slot;
  return overlayPlayerChromeStyle({ isExpanded: false });
}

function isFixedContainingBlock(cs) {
  if (!cs) return false;
  if (cs.transform && cs.transform !== "none") return true;
  if (cs.filter && cs.filter !== "none") return true;
  const backdrop = cs.backdropFilter || cs.webkitBackdropFilter;
  if (backdrop && backdrop !== "none") return true;
  if (cs.perspective && cs.perspective !== "none") return true;
  const contain = cs.contain || "";
  if (/paint|layout|strict|content/.test(contain)) return true;
  if (cs.clipPath && cs.clipPath !== "none") return true;
  if (cs.webkitClipPath && cs.webkitClipPath !== "none") return true;
  if (/transform|filter|backdrop|perspective|contain/i.test(cs.willChange || "")) return true;
  return false;
}

function hasInlineContainingBlock(node) {
  const st = node && node.style;
  if (!st) return false;
  if (st.transform && st.transform !== "none") return true;
  if (st.filter && st.filter !== "none") return true;
  if (st.backdropFilter && st.backdropFilter !== "none") return true;
  if (st.webkitBackdropFilter && st.webkitBackdropFilter !== "none") return true;
  if (st.perspective && st.perspective !== "none") return true;
  return false;
}

/**
 * Strip filter/transform containing blocks on the ancestor path only.
 * Never touch overflow — unlocking the iPad inner scroller freezes the page.
 */
export function captureContainingBlockStyles(fromEl) {
  const saved = [];
  if (typeof window === "undefined" || !fromEl || !fromEl.parentElement) return saved;
  let node = fromEl.parentElement;
  while (node && node !== document.documentElement) {
    const cs = window.getComputedStyle(node);
    if (isFixedContainingBlock(cs) || hasInlineContainingBlock(node)) {
      const target = node;
      const inline = {};
      for (let i = 0; i < CONTAINING_BLOCK_STYLE_KEYS.length; i += 1) {
        const key = CONTAINING_BLOCK_STYLE_KEYS[i];
        inline[key] = target.style[key];
      }
      saved.push({ node: target, inline });
      target.style.filter = "none";
      target.style.webkitFilter = "none";
      target.style.backdropFilter = "none";
      target.style.webkitBackdropFilter = "none";
      target.style.transform = "none";
      target.style.willChange = "auto";
      target.style.contain = "none";
      target.style.perspective = "none";
      target.style.clipPath = "none";
      target.style.webkitClipPath = "none";
    }
    node = node.parentElement;
  }
  return saved;
}

export function restoreContainingBlockStyles(saved) {
  (saved || []).forEach(({ node, inline }) => {
    if (!node || !node.style || !inline) return;
    CONTAINING_BLOCK_STYLE_KEYS.forEach((key) => {
      node.style[key] = inline[key] || "";
    });
  });
}
