/**
 * Overlay hand tracking helpers.
 *
 * PRE vs POST use the same player. PRE looks locked because Hand Landmarker
 * sits on the real fingers. POST looks wrong because the server stores HL
 * INDEX as overlay `palm` / `index` — and on POST that INDEX is the cup.
 *
 * Two POST-only failure modes from that one data lie:
 *
 *   1. Off-hand detection used palmReach*2 as the hand size. Wrist→cup then
 *      becomes a "giant hand", so cup tips look on-hand and the chalk is
 *      drawn on the cup (PRE never hits this: its INDEX is on the fingers).
 *   2. The pose-rest fallback did 2*palm - wrist. If palm is the cup, that
 *      reconstructed knuckle is on/past the cup, so even "don't draw HL"
 *      still puts sticks on the cup.
 *
 * Fix: size the pose hand from the forearm, not from overlay palm, unless
 * that palm is close enough to be a real pose knuckle. If HL MCPs sit far
 * from the pose wrist they are a cup cluster, not a hand. Pose-rest ignores
 * a cup-distance palm and falls back to the forearm axis. Never lerp across
 * the cup→hand switch. Smooth only the pose skeleton.
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
 * Overlay `palm` is the affected INDEX after HL overwrite, not the kinematic
 * midpoint. Trust it only when it sits on the pose hand (PRE). A cup-distance
 * value (POST rest) must not define the hand size or the rest-hand axis.
 */
export function overlayPalmIsTrusted(palmReachPx, forearmPx, handSpan = 1) {
  if (!(palmReachPx > 3)) return false;
  if (forearmPx > 8) return palmReachPx <= forearmPx * 0.48;
  return palmReachPx <= Math.max(24, handSpan * 0.08);
}

/**
 * Resting / adducted hand from pose.
 *
 * When overlay palm is a real pose knuckle / midpoint, 2*palm - wrist recovers
 * the index MCP. When overlay palm is the cup, ignore it and aim along the
 * forearm. Tips stay ~1.5× MCP (foreshortened rest), not the ~2.17× open-hand
 * length that overshoots the nails at onset.
 */
export function buildPoseRestHand(wrist, palm, elbow, trunk) {
  if (!wrist) return null;
  const forearm = elbow
    ? Math.hypot(wrist[0] - elbow[0], wrist[1] - elbow[1])
    : 0;
  const palmReach = palm
    ? Math.hypot(palm[0] - wrist[0], palm[1] - wrist[1])
    : 0;
  const palmOk = overlayPalmIsTrusted(palmReach, forearm, 640);
  const poseIndex = palmOk && palm
    ? [2 * palm[0] - wrist[0], 2 * palm[1] - wrist[1]]
    : null;
  const mcpLen = poseIndex
    ? Math.hypot(poseIndex[0] - wrist[0], poseIndex[1] - wrist[1])
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
export function hlTipsOffPoseHand({
  poseWrist,
  hlWrist,
  tips = [],
  mcps = [],
  forearmPx = 0,
  palmReachPx = 0,
  handSpan = 1,
} = {}) {
  const hypot = (a, b) => {
    if (!a || !b) return null;
    return Math.hypot(a[0] - b[0], a[1] - b[1]);
  };
  // Do not let a cup-distance overlay palm inflate the hand. PRE overlay palm
  // is on the fingers (trusted or not, tips stay near the pose wrist). POST
  // overlay palm is the cup: sizing from it makes the cup look on-hand.
  const palmOk = overlayPalmIsTrusted(palmReachPx, forearmPx, handSpan);
  const mcpFromPalm = palmOk ? palmReachPx * 2 : 0;
  const mcpFromForearm = forearmPx > 8 ? forearmPx * 0.32 : 0;
  const poseMcp = mcpFromPalm >= 3 ? mcpFromPalm : mcpFromForearm;
  const handPx = poseMcp > 0
    ? poseMcp * 1.65
    : Math.max(1, handSpan) * 0.10;
  const wristDrift = (hypot(poseWrist, hlWrist) || 0) > Math.max(
    (forearmPx > 8 ? forearmPx * 0.28 : handPx * 0.85),
    handSpan * 0.08,
  );
  const farLimit = Math.max(handPx * 1.20, forearmPx > 8 ? forearmPx * 1.05 : 0);
  let n = 0;
  let far = 0;
  let maxD = 0;
  tips.forEach((tip) => {
    const d = hypot(poseWrist, tip) || 0;
    n += 1;
    maxD = Math.max(maxD, d);
    if (d > farLimit) far += 1;
  });
  const tipsMajorityFar = n >= 2 && far >= Math.ceil(n * 0.5);
  const tipsStretched = handPx > 0 && maxD > Math.max(handPx * 1.35, forearmPx * 1.15);
  // Cup latch: every HL knuckle sits on the cup, far from the pose wrist.
  // A real reaching hand still has MCPs next to the wrist.
  const mcpLimit = forearmPx > 8 ? forearmPx * 0.55 : Math.max(1, handSpan) * 0.10;
  let mcpN = 0;
  let mcpFar = 0;
  mcps.forEach((mcp) => {
    const d = hypot(poseWrist, mcp) || 0;
    mcpN += 1;
    if (d > mcpLimit) mcpFar += 1;
  });
  const mcpsMajorityFar = mcpN >= 2 && mcpFar >= Math.ceil(mcpN * 0.5);
  return Boolean(wristDrift || tipsMajorityFar || tipsStretched || mcpsMajorityFar || n === 0);
}

/** HL joints are drawn only after they sit on the pose hand. Never draw the cup. */
export function shouldDrawHlFingers(hlOffHand, src) {
  return !hlOffHand && src === "hl";
}

export function resolveHandDrawSource(state, hlOffHand, { offNeed = 1, onNeed = 4 } = {}) {
  const next = {
    src: state?.src || "pose",
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
