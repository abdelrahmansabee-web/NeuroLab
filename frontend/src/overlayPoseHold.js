/** Display-only hold: lock the drawn skeleton to a still body. Does not change overlay tracking math. */

export const OVERLAY_TRACKING_NOISE_PX = 2;
/** Rest lock in 0–1 landmark space — swallows camera/MediaPipe wander, not a reach. */
export const OVERLAY_BODY_REST_NORM = 0.016;

const TORSO_KEYS = ["trunk", "shoulder", "lshoulder", "rshoulder", "lhip", "rhip", "nose"];

const CHILD_PARENT = {
  elbow: "shoulder",
  wrist: "elbow",
  palm: "wrist",
  hl_wrist: "wrist",
  lelbow: "lshoulder",
  relbow: "rshoulder",
  lwrist: "lelbow",
  rwrist: "relbow",
  lknee: "lhip",
  rknee: "rhip",
  lankle: "lknee",
  rankle: "rknee",
  leye: "nose",
  reye: "nose",
  leye_inner: "nose",
  leye_outer: "nose",
  reye_inner: "nose",
  reye_outer: "nose",
  lear: "nose",
  rear: "nose",
  mouth_l: "nose",
  mouth_r: "nose",
  thumb: "hl_wrist",
  index: "hl_wrist",
  pinky: "hl_wrist",
  middle: "hl_wrist",
  ring: "hl_wrist",
};

export function overlayTrackingNoisePx(frameWidthPx = 0, frameHeightPx = 0) {
  const minSide = Math.min(Number(frameWidthPx) || 0, Number(frameHeightPx) || 0);
  const fromFrame = minSide > 0 ? 0.002 * minSide : 0;
  return Math.max(OVERLAY_TRACKING_NOISE_PX, fromFrame);
}

export function overlayBodyRestPx(frameWidthPx = 0, frameHeightPx = 0) {
  const minSide = Math.min(Number(frameWidthPx) || 0, Number(frameHeightPx) || 0);
  const fromFrame = minSide > 0 ? OVERLAY_BODY_REST_NORM * minSide : 0;
  return Math.max(8, fromFrame);
}

export function resetHoldIfSeek(store, idx, jump = 8) {
  if (!store) return;
  if (store._idx != null && Math.abs(idx - store._idx) > jump) {
    Object.keys(store).forEach((k) => {
      delete store[k];
    });
  }
  store._idx = idx;
}

function asXy(p) {
  if (!p || p[0] == null || p[1] == null) return null;
  const x = Number(p[0]);
  const y = Number(p[1]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return [x, y];
}

function toCanvas(p, cw, ch) {
  if (!p) return null;
  const x = Number(p[0]) * cw;
  const y = Number(p[1]) * ch;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return [x, y];
}

function median(vals) {
  if (!vals.length) return 0;
  const sorted = vals.slice().sort((a, b) => a - b);
  const mid = (sorted.length - 1) / 2;
  return (sorted[Math.floor(mid)] + sorted[Math.ceil(mid)]) / 2;
}

function parentDepth(key) {
  let depth = 0;
  let parent = CHILD_PARENT[key];
  const seen = new Set();
  while (parent && !seen.has(parent)) {
    seen.add(parent);
    depth += 1;
    parent = CHILD_PARENT[parent];
  }
  return depth;
}

function normStore(store) {
  if (!store._norm) store._norm = {};
  return store._norm;
}

/**
 * Hold the whole pose in 0–1 space, then scale to canvas.
 * Independent detector jitter stays frozen. A real limb change updates that limb.
 * A shared camera/body shift moves the figure together so it stays on the person.
 */
export function holdBodyDisplay(store, rawPts, cw, ch, idx) {
  const out = {};
  const keys = Object.keys(rawPts || {});
  if (!store) {
    keys.forEach((key) => {
      out[key] = toCanvas(asXy(rawPts[key]), cw, ch);
    });
    return out;
  }
  resetHoldIfSeek(store, idx);
  const held = normStore(store);
  const floor = OVERLAY_BODY_REST_NORM;
  const incoming = {};
  keys.forEach((key) => {
    incoming[key] = asXy(rawPts[key]);
    if (incoming[key] && !held[key]) held[key] = [incoming[key][0], incoming[key][1]];
  });

  const dxs = [];
  const dys = [];
  TORSO_KEYS.forEach((key) => {
    if (incoming[key] && held[key]) {
      dxs.push(incoming[key][0] - held[key][0]);
      dys.push(incoming[key][1] - held[key][1]);
    }
  });
  const mx = median(dxs);
  const my = median(dys);
  const shift = Math.hypot(mx, my);
  let coherent = false;
  if (dxs.length >= 2 && shift >= floor) {
    let agree = 0;
    for (let i = 0; i < dxs.length; i += 1) {
      if (Math.hypot(dxs[i] - mx, dys[i] - my) < floor) agree += 1;
    }
    coherent = agree >= Math.ceil(dxs.length * 0.6);
  }
  if (coherent) {
    Object.keys(held).forEach((key) => {
      const p = held[key];
      if (!p) return;
      held[key] = [p[0] + mx, p[1] + my];
    });
  }

  const snap = {};
  Object.keys(held).forEach((key) => {
    const p = held[key];
    if (p) snap[key] = [p[0], p[1]];
  });

  keys
    .slice()
    .sort((a, b) => parentDepth(a) - parentDepth(b))
    .forEach((key) => {
      const next = incoming[key];
      if (!next) return;
      const parentKey = CHILD_PARENT[key];
      const parentHeld = parentKey ? held[parentKey] : null;
      const parentRaw = parentKey ? incoming[parentKey] : null;
      const childSnap = snap[key];
      const parentSnap = parentKey ? snap[parentKey] : null;
      if (parentHeld && parentRaw && childSnap && parentSnap) {
        const heldOff = [childSnap[0] - parentSnap[0], childSnap[1] - parentSnap[1]];
        const rawOff = [next[0] - parentRaw[0], next[1] - parentRaw[1]];
        const dOff = Math.hypot(rawOff[0] - heldOff[0], rawOff[1] - heldOff[1]);
        const abs = Math.hypot(next[0] - childSnap[0], next[1] - childSnap[1]);
        if (dOff < floor || abs < floor) {
          held[key] = [parentHeld[0] + heldOff[0], parentHeld[1] + heldOff[1]];
        } else {
          held[key] = [parentHeld[0] + rawOff[0], parentHeld[1] + rawOff[1]];
        }
        return;
      }
      const prev = held[key];
      if (!prev) {
        held[key] = [next[0], next[1]];
        return;
      }
      if (Math.hypot(next[0] - prev[0], next[1] - prev[1]) >= floor) {
        held[key] = [next[0], next[1]];
      }
    });

  if (!store._canvas) store._canvas = {};
  keys.forEach((key) => {
    if (!incoming[key]) {
      out[key] = null;
      return;
    }
    const next = toCanvas(held[key] || incoming[key], cw, ch);
    const prevC = store._canvas[key];
    if (prevC && next && prevC[0] === next[0] && prevC[1] === next[1]) {
      out[key] = prevC;
      return;
    }
    store._canvas[key] = next;
    out[key] = next;
  });
  return out;
}

/** Canvas point from a 0–1 landmark, held until motion beats rest noise. */
export function holdDisplayLandmark(store, key, blended, cw, ch, idx) {
  if (!blended) return null;
  const held = holdBodyDisplay(store, { [key]: blended }, cw, ch, idx);
  return held[key] || null;
}

/** Keep last drawn point until canvas motion exceeds tracking noise. */
export function holdTrackingNoise(store, key, next, pxFloor = OVERLAY_TRACKING_NOISE_PX) {
  if (!next) return null;
  if (!store) return next;
  const prev = store[key];
  if (!prev) {
    store[key] = [next[0], next[1]];
    return store[key];
  }
  const d = Math.hypot(next[0] - prev[0], next[1] - prev[1]);
  if (d < pxFloor) return prev;
  store[key] = [next[0], next[1]];
  return store[key];
}

/** Hold a finger dot relative to the wrist so the hand does not shimmer at rest. */
export function holdFingerCanvas(store, key, cpt, origin, cw, ch, idx) {
  if (!cpt) return null;
  if (!store) return cpt;
  resetHoldIfSeek(store, idx);
  const floor = overlayBodyRestPx(cw, ch);
  const originKey = `${key}__o`;
  const prev = store[key];
  const prevOrigin = store[originKey];
  if (prev && origin && prevOrigin) {
    const heldOff = [prev[0] - prevOrigin[0], prev[1] - prevOrigin[1]];
    const rawOff = [cpt[0] - origin[0], cpt[1] - origin[1]];
    if (Math.hypot(rawOff[0] - heldOff[0], rawOff[1] - heldOff[1]) < floor) {
      store[originKey] = [origin[0], origin[1]];
      store[key] = [origin[0] + heldOff[0], origin[1] + heldOff[1]];
      return store[key];
    }
  }
  if (origin) store[originKey] = [origin[0], origin[1]];
  store[key] = [cpt[0], cpt[1]];
  return store[key];
}
