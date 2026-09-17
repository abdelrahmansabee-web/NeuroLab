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

/**
 * iPad clinic scroll is `fixed inset-0 overflow-y-auto`, not document.body.
 * Expand already sets body overflow hidden (no-op on that scroller). Lock the
 * same node App.js uses for the actions sheet. Do not change ancestor overflow
 * inside captureContainingBlockStyles — that froze the page.
 */
export function lockOverlayAppScroller() {
  if (typeof document === "undefined") return null;
  const el = document.querySelector(`[${OVERLAY_APP_SCROLL_ATTR}]`);
  if (!el) return null;
  const prev = {
    overflow: el.style.overflow,
    touchAction: el.style.touchAction,
  };
  el.style.overflow = "hidden";
  el.style.touchAction = "none";
  return { el, prev };
}

export function unlockOverlayAppScroller(saved) {
  if (!saved?.el) return;
  saved.el.style.overflow = saved.prev?.overflow || "";
  saved.el.style.touchAction = saved.prev?.touchAction || "";
}

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

/** Clinic glass / layer classes that create a containing block for position:fixed. */
const CONTAINING_BLOCK_CLASS_RE =
  /(?:^|\s)(?:glass-float|content-shell|content-panel-glass|sidebar-shell|section-pane|section-header|app-topbar-glass|gselect-trigger-shell|gselect-menu-portal|section-nav-motion)(?:\s|$)/;

export const OVERLAY_FLIP_MS = 180;
export const OVERLAY_FLIP_EASE = "cubic-bezier(0.33, 1, 0.68, 1)";

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

function computedCreatesContainingBlock(value, prop) {
  const v = String(value || "").trim().toLowerCase();
  if (!v) return false;
  if (v === "none") return false;
  if (prop === "will-change" && (v === "auto" || v === "scroll-position")) return false;
  if (prop === "contain" && (v === "none" || v === "strict" || v === "content")) {
    return v === "strict" || v === "content" || /\b(?:layout|paint|size)\b/.test(v);
  }
  return true;
}

/** Skip empty wrappers / html / body so expand does not restyle the whole clinic. */
export function ancestorNeedsContainingBlockUnlock(node) {
  if (!node || node === document.documentElement || node === document.body) return false;
  const className = typeof node.className === "string" ? node.className : "";
  if (CONTAINING_BLOCK_CLASS_RE.test(className)) return true;
  if (node.style) {
    for (let i = 0; i < CONTAINING_BLOCK_PROPS.length; i += 1) {
      const prop = CONTAINING_BLOCK_PROPS[i];
      if (computedCreatesContainingBlock(node.style.getPropertyValue(prop), prop)) return true;
    }
  }
  if (typeof window === "undefined" || typeof window.getComputedStyle !== "function") return false;
  const cs = window.getComputedStyle(node);
  for (let i = 0; i < CONTAINING_BLOCK_PROPS.length; i += 1) {
    const prop = CONTAINING_BLOCK_PROPS[i];
    if (computedCreatesContainingBlock(cs.getPropertyValue(prop), prop)) return true;
  }
  return false;
}

export function overlayFlipEnabled() {
  if (typeof window === "undefined") return false;
  return !window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
}

export function overlayFlipInvert(fromBox, toBox) {
  if (!fromBox || !toBox) return null;
  if (!(fromBox.width >= 2) || !(fromBox.height >= 2)) return null;
  if (!(toBox.width >= 2) || !(toBox.height >= 2)) return null;
  const dx = fromBox.left - toBox.left;
  const dy = fromBox.top - toBox.top;
  const sx = fromBox.width / toBox.width;
  const sy = fromBox.height / toBox.height;
  if (
    Math.abs(dx) < 1 &&
    Math.abs(dy) < 1 &&
    Math.abs(sx - 1) < 0.02 &&
    Math.abs(sy - 1) < 0.02
  ) {
    return null;
  }
  return { dx, dy, sx, sy };
}

export function applyOverlayFlipInvert(el, invert) {
  if (!el || !el.style || !invert) return;
  el.style.transition = "none";
  el.style.willChange = "transform";
  el.style.transformOrigin = "top left";
  el.style.transform = `translate3d(${invert.dx}px, ${invert.dy}px, 0) scale(${invert.sx}, ${invert.sy})`;
}

export function playOverlayFlip(el) {
  if (!el || !el.style) return;
  el.style.transition = `transform ${OVERLAY_FLIP_MS}ms ${OVERLAY_FLIP_EASE}`;
  el.style.transform = "none";
}

export function clearOverlayFlip(el) {
  if (!el || !el.style) return;
  el.style.transition = "";
  el.style.transform = "";
  el.style.transformOrigin = "";
  el.style.willChange = "";
}

/**
 * Clear filter/transform containing blocks on the ancestor path.
 * Uses inline !important so clinic glass `backdrop-filter: … !important` cannot keep
 * position:fixed trapped (video on the right, results table painted on top).
 * Never changes overflow — that froze the iPad scroller.
 * Skips ancestors that are not containing blocks so expand does not restyle the page.
 */
export function captureContainingBlockStyles(fromEl) {
  const saved = [];
  if (typeof window === "undefined" || !fromEl || !fromEl.parentElement) return saved;
  let node = fromEl.parentElement;
  while (node && node !== document.documentElement) {
    const target = node;
    node = node.parentElement;
    if (!ancestorNeedsContainingBlockUnlock(target)) continue;
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
