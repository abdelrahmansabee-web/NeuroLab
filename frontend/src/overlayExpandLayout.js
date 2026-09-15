/**
 * Compact overlay players stay in the card (in-flow). Never pin them with
 * position:fixed on document.body — iPad inner-div scroll pulls those clones
 * off their group. Expand uses the same <video> node (never reparent).
 */

export const OVERLAY_PORTAL_Z_COMPACT = "auto";
export const OVERLAY_PORTAL_Z_EXPANDED = 99999;
export const OVERLAY_ESCAPE_CLASS = "nl-overlay-escape";
/** Clinic sidebar is z-50 / z-100; the iPad scroller is z-20. Raise it on expand. */
export const OVERLAY_APP_SCROLL_ATTR = "data-nl-app-scroll";
export const OVERLAY_APP_SCROLL_EXPANDED_Z = 2147483000;

/** CSS names. Inline !important is required to beat App.js glass `backdrop-filter: … !important`. */
const CONTAINING_BLOCK_PROPS = [
  "filter",
  "-webkit-filter",
  "backdrop-filter",
  "-webkit-backdrop-filter",
  "transform",
  "will-change",
  "contain",
  "perspective",
  "clip-path",
  "-webkit-clip-path",
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

/** Compact must be in-card; a body-fixed slot pin is what pulls videos off the group. */
export function overlayCompactIsInCard(style) {
  return Boolean(
    style &&
      style.position === "absolute" &&
      style.inset === 0 &&
      style.left == null &&
      style.top == null,
  );
}

/** @deprecated Use overlayPlayerChromeStyle. Compact is in-flow, not a body portal. */
export function overlayPortalStyle({ isExpanded, slot } = {}) {
  if (isExpanded) return overlayPlayerChromeStyle({ isExpanded: true });
  void slot;
  return overlayPlayerChromeStyle({ isExpanded: false });
}

function propValue(prop) {
  return prop === "will-change" ? "auto" : "none";
}

/**
 * Clear filter/transform containing blocks on the ancestor path.
 * Uses inline !important so clinic glass `backdrop-filter: … !important` cannot keep
 * position:fixed trapped (video on the right, results table painted on top).
 * Never changes overflow — that froze the iPad scroller.
 */
export function captureContainingBlockStyles(fromEl) {
  const saved = [];
  if (typeof window === "undefined" || !fromEl || !fromEl.parentElement) return saved;
  let node = fromEl.parentElement;
  while (node && node !== document.documentElement) {
    const target = node;
    const inline = {};
    const priority = {};
    for (let i = 0; i < CONTAINING_BLOCK_PROPS.length; i += 1) {
      const prop = CONTAINING_BLOCK_PROPS[i];
      inline[prop] = target.style.getPropertyValue(prop);
      priority[prop] = target.style.getPropertyPriority(prop);
      target.style.setProperty(prop, propValue(prop), "important");
    }
    const addedClass = !target.classList.contains(OVERLAY_ESCAPE_CLASS);
    if (addedClass) target.classList.add(OVERLAY_ESCAPE_CLASS);
    saved.push({ node: target, inline, priority, addedClass });
    node = node.parentElement;
  }
  return saved;
}

export function restoreContainingBlockStyles(saved) {
  (saved || []).forEach(({ node, inline, priority, addedClass }) => {
    if (!node || !node.style) return;
    if (addedClass) node.classList.remove(OVERLAY_ESCAPE_CLASS);
    CONTAINING_BLOCK_PROPS.forEach((prop) => {
      const prev = inline ? inline[prop] : "";
      const pri = priority ? priority[prop] : "";
      if (prev) node.style.setProperty(prop, prev, pri || "");
      else node.style.removeProperty(prop);
    });
  });
}
