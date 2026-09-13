/**
 * Overlay hand tracking helpers.
 *
 * The persistent miss at movement *onset* is not a drawing-style issue. It is a
 * source-handoff bug:
 *
 *   1. Before the reach, Hand Landmarker latches the cup. Those joints are not
 *      on the patient's fingers.
 *   2. The player used to replace them with an *open-hand* anatomy fan scaled
 *      from the forearm (~2.1× the pose index knuckle). A resting, foreshortened
 *      hand is much shorter, so the chalk overshot the nails.
 *   3. A causal EMA then blended that fake hand into the first on-hand HL
 *      frames, so the start of the movement stayed detached.
 *
 * Fix: when HL is off the pose hand, draw a *resting* pose-palm hand (index
 * knuckle = 2*palm - wrist). Do not lerp across the cup→hand switch. Smooth only
 * the pose skeleton (zero-lag), never HL finger tracks that jump from cup to
 * fingers.
 */

export const HL_OVERLAY_KEYS = new Set([
  "index", "thumb", "pinky", "middle", "ring", "hl_wrist",
]);

export function isHlOverlayKey(key) {
  if (!key) return false;
  if (key.startsWith("fj:")) return true;
  return HL_OVERLAY_KEYS.has(key);
}

export function interpPair(p, pn, alpha) {
  if (!p || p[0] == null || p[1] == null) return null;
  if (pn && pn[0] != null && pn[1] != null && alpha > 0) {
    return [p[0] + (pn[0] - p[0]) * alpha, p[1] + (pn[1] - p[1]) * alpha];
  }
  return [p[0], p[1]];
}

/**
 * Centered (zero-lag) triangular smoothing of pose landmark tracks.
 * HL finger keys are skipped: averaging cup-latched samples with on-hand
 * samples is exactly the onset "floating fingers" artefact.
 */
export function buildSmoothedTracks(frames, fps) {
  const n = frames?.length || 0;
  if (n === 0) return null;
  const names = new Set();
  frames.forEach((fr) => {
    if (!fr) return;
    Object.keys(fr).forEach((k) => {
      if (isHlOverlayKey(k)) return;
      const v = fr[k];
      if (Array.isArray(v) && v.length === 2) names.add(k);
    });
  });

  const readPair = (fr, key) => {
    if (!fr) return null;
    const p = fr[key];
    return Array.isArray(p) && p.length === 2 ? p : null;
  };

  const half = (fps || 30) >= 45 ? 3 : 2;
  const weights = [];
  for (let d = -half; d <= half; d += 1) weights.push(half + 1 - Math.abs(d));

  const tracks = new Map();
  names.forEach((key) => {
    const buf = new Float32Array(n * 2);
    for (let i = 0; i < n; i += 1) {
      const here = readPair(frames[i], key);
      if (!here || here[0] == null || here[1] == null) {
        buf[i * 2] = Number.NaN;
        buf[i * 2 + 1] = Number.NaN;
        continue;
      }
      let sx = 0;
      let sy = 0;
      let sw = 0;
      for (let d = -half; d <= half; d += 1) {
        const j = i + d;
        if (j < 0 || j >= n) continue;
        const p = readPair(frames[j], key);
        if (!p || p[0] == null || p[1] == null) continue;
        const w = weights[d + half];
        sx += p[0] * w;
        sy += p[1] * w;
        sw += w;
      }
      buf[i * 2] = sw > 0 ? sx / sw : here[0];
      buf[i * 2 + 1] = sw > 0 ? sy / sw : here[1];
    }
    tracks.set(key, buf);
  });

  return {
    count: n,
    at(key, i) {
      const buf = tracks.get(key);
      if (!buf || i < 0 || i >= n) return null;
      const x = buf[i * 2];
      const y = buf[i * 2 + 1];
      return Number.isNaN(x) || Number.isNaN(y) ? null : [x, y];
    },
  };
}

/**
 * Resting / adducted hand from pose. Overlay `palm` is always pose-based
 * (midpoint of pose wrist and pose INDEX knuckle) even when HL has latched
 * the cup, so 2*palm - wrist recovers the knuckle that sits on the real hand.
 *
 * Units are wrist → index-MCP. Tips stay ~1.5× that span (foreshortened rest),
 * not the ~2.17× open-hand length that overshoots the nails at onset.
 */
export function buildPoseRestHand(wrist, palm, elbow, trunk) {
  if (!wrist) return null;
  const poseIndex = palm
    ? [2 * palm[0] - wrist[0], 2 * palm[1] - wrist[1]]
    : null;
  const mcpLen = poseIndex
    ? Math.hypot(poseIndex[0] - wrist[0], poseIndex[1] - wrist[1])
    : 0;
  const forearm = elbow
    ? Math.hypot(wrist[0] - elbow[0], wrist[1] - elbow[1])
    : 0;
  let ux;
  let uy;
  let scale;
  if (mcpLen >= 3) {
    ux = poseIndex[0] - wrist[0];
    uy = poseIndex[1] - wrist[1];
    scale = mcpLen;
  } else if (forearm >= 8) {
    ux = wrist[0] - elbow[0];
    uy = wrist[1] - elbow[1];
    scale = forearm * 0.32;
  } else {
    return null;
  }
  const ul = Math.hypot(ux, uy);
  if (ul < 1e-3) return null;
  ux /= ul;
  uy /= ul;
  let px = -uy;
  let py = ux;
  if (trunk) {
    const mx = trunk[0] - wrist[0];
    const my = trunk[1] - wrist[1];
    if (px * mx + py * my > 0) {
      px = -px;
      py = -py;
    }
  }
  const specs = {
    thumb: { mcp: [0.42, -0.26], ip: [0.68, -0.36], tip: [0.90, -0.42] },
    index: { mcp: [1.00, 0.00], ip: [1.26, 0.00], tip: [1.50, 0.00] },
    middle: { mcp: [1.03, 0.06], ip: [1.30, 0.07], tip: [1.54, 0.08] },
    ring: { mcp: [0.97, 0.13], ip: [1.22, 0.14], tip: [1.46, 0.15] },
    pinky: { mcp: [0.86, 0.20], ip: [1.08, 0.21], tip: [1.28, 0.22] },
  };
  const out = {};
  Object.keys(specs).forEach((fid) => {
    const spec = specs[fid];
    const at = ([along, lat]) => [
      wrist[0] + (ux * along + px * lat) * scale,
      wrist[1] + (uy * along + py * lat) * scale,
    ];
    out[fid] = { mcp: at(spec.mcp), ip: at(spec.ip), tip: at(spec.tip) };
  });
  return { joints: out, scale, poseIndex, mcpLen };
}

/**
 * Hysteresis for the HL ↔ pose-hand switch.
 * Stay on the pose-rest hand until several consecutive on-hand frames, so a
 * single cup flicker cannot yank the chalk. When the source *does* change,
 * callers must clear any causal finger EMA — never blend the two models.
 */
export function resolveHandDrawSource(state, hlOffHand, { offNeed = 1, onNeed = 4 } = {}) {
  const next = {
    src: state?.src || "hl",
    offStreak: Number(state?.offStreak) || 0,
    onStreak: Number(state?.onStreak) || 0,
    switched: false,
  };
  if (hlOffHand) {
    next.offStreak += 1;
    next.onStreak = 0;
  } else {
    next.onStreak += 1;
    next.offStreak = 0;
  }
  const prev = next.src;
  if (next.src === "pose") {
    if (next.onStreak >= onNeed) next.src = "hl";
  } else if (next.offStreak >= offNeed) {
    next.src = "pose";
  }
  next.switched = next.src !== prev;
  return next;
}
