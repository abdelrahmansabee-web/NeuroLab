/**
 * Full clinical skeleton topology — nl 31.47 baseline (stable overlay alignment).
 */
import {
  HAND_FINGER_BONES,
  HAND_FINGER_ORDER,
  buildAnatomyHandLandmarks,
  estimateHandScale,
  handAxesFromElbowPalm,
  resolveHandSkeleton,
} from "./handSkeletonTemplate";

export const CLINICAL_SKELETON_REF = "hand_skeleton_anatomy.jpeg";

export const SKELETON_PALETTE = {
  bone: "#f3f0d7",
  boneDim: "rgba(243,240,215,0.52)",
  boneOutline: "rgba(60,55,45,0.92)",
  shadow: "rgba(0,0,0,0.38)",
  joint: "#e8e4c9",
  jointDim: "rgba(232,228,201,0.65)",
  jointOutline: "rgba(40,35,28,0.95)",
  rib: "rgba(243,240,215,0.38)",
  clinical: "#faf8ef",
  handBone: "rgba(243,240,215,0.88)",
};

/** Soft blackboard chalk — white dust, no phase tint. */
export const CHALK_PALETTE = {
  fill: "rgba(255,255,252,0.10)",
  edge: "rgba(255,255,250,0.88)",
  edgeSoft: "rgba(255,255,250,0.28)",
  dust: "rgba(255,255,250,0.35)",
  jointCore: "rgba(255,255,252,0.95)",
  jointGlow: "rgba(255,255,250,0.22)",
  dimEdge: "rgba(255,255,250,0.42)",
  dimFill: "rgba(255,255,252,0.06)",
};

function chalkPerpOffsets(a, b, halfWidth) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len = Math.hypot(dx, dy) || 1;
  const px = (-dy / len) * halfWidth;
  const py = (dx / len) * halfWidth;
  return {
    aL: [a[0] + px, a[1] + py],
    aR: [a[0] - px, a[1] - py],
    bL: [b[0] + px, b[1] + py],
    bR: [b[0] - px, b[1] - py],
    nx: -dy / len,
    ny: dx / len,
    len,
  };
}

/** Single dusty chalk stroke (thin bones / fingers). */
export function drawChalkStick(ctx, a, b, opts = {}) {
  if (!a || !b || !ctx) return;
  const {
    color = CHALK_PALETTE.edge,
    soft = CHALK_PALETTE.edgeSoft,
    width = 2.2,
    blur = 4,
    curve = 0.08,
  } = opts;
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;
  const bulge = len * curve;
  const cx = (a[0] + b[0]) / 2 + nx * bulge;
  const cy = (a[1] + b[1]) / 2 + ny * bulge;
  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.shadowColor = CHALK_PALETTE.dust;
  ctx.shadowBlur = blur;
  ctx.beginPath();
  ctx.moveTo(a[0], a[1]);
  ctx.quadraticCurveTo(cx, cy, b[0], b[1]);
  ctx.strokeStyle = soft;
  ctx.lineWidth = width * 2.1;
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(a[0], a[1]);
  ctx.quadraticCurveTo(cx, cy, b[0], b[1]);
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.stroke();
  ctx.restore();
}

/**
 * Narrow chalk limb contour: two gently curved edges hugging the bone axis
 * (reads as soft body outline, not a thick yellow bar).
 */
export function drawChalkRibbon(ctx, a, b, opts = {}) {
  if (!a || !b || !ctx) return;
  const {
    halfWidth = 4.5,
    fill = CHALK_PALETTE.fill,
    edge = CHALK_PALETTE.edge,
    blur = 4,
    curve = 0.1,
  } = opts;
  const e = chalkPerpOffsets(a, b, halfWidth);
  if (e.len < 6) return;
  const bulge = e.len * curve;
  const midL = [
    (e.aL[0] + e.bL[0]) / 2 + e.nx * bulge,
    (e.aL[1] + e.bL[1]) / 2 + e.ny * bulge,
  ];
  const midR = [
    (e.aR[0] + e.bR[0]) / 2 - e.nx * bulge * 0.55,
    (e.aR[1] + e.bR[1]) / 2 - e.ny * bulge * 0.55,
  ];

  ctx.save();
  ctx.beginPath();
  ctx.moveTo(e.aL[0], e.aL[1]);
  ctx.quadraticCurveTo(midL[0], midL[1], e.bL[0], e.bL[1]);
  ctx.lineTo(e.bR[0], e.bR[1]);
  ctx.quadraticCurveTo(midR[0], midR[1], e.aR[0], e.aR[1]);
  ctx.closePath();
  ctx.fillStyle = fill;
  ctx.fill();

  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.shadowColor = CHALK_PALETTE.dust;
  ctx.shadowBlur = blur;
  [
    [e.aL, midL, e.bL],
    [e.aR, midR, e.bR],
  ].forEach(([p0, pc, p1]) => {
    ctx.beginPath();
    ctx.moveTo(p0[0], p0[1]);
    ctx.quadraticCurveTo(pc[0], pc[1], p1[0], p1[1]);
    ctx.strokeStyle = CHALK_PALETTE.edgeSoft;
    ctx.lineWidth = Math.max(2.2, halfWidth * 0.55);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(p0[0], p0[1]);
    ctx.quadraticCurveTo(pc[0], pc[1], p1[0], p1[1]);
    ctx.strokeStyle = edge;
    ctx.lineWidth = Math.max(1.35, halfWidth * 0.28);
    ctx.stroke();
  });
  ctx.restore();
}

export function drawChalkJoint(ctx, p, opts = {}) {
  if (!p || !ctx) return;
  const { r = 5, dim = false } = opts;
  ctx.save();
  ctx.shadowColor = CHALK_PALETTE.dust;
  ctx.shadowBlur = dim ? 2 : 5;
  ctx.fillStyle = CHALK_PALETTE.jointGlow;
  ctx.beginPath();
  ctx.arc(p[0], p[1], r * 1.25, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = dim ? "rgba(255,255,252,0.5)" : CHALK_PALETTE.jointCore;
  ctx.beginPath();
  ctx.arc(p[0], p[1], Math.max(1.8, r * 0.55), 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

/**
 * Standard MediaPipe Pose face mesh when landmarks exist.
 * Always draws a visible head: fills missing face points from nose↔shoulders
 * so older overlays (nose-only) still show a face outline.
 */
export function drawChalkHead(ctx, pts, virt, opts = {}) {
  if (!ctx) return;
  const {
    blur = 4,
    shoulderWidthPx = 0,
  } = opts;
  const ls = pts?.lshoulder;
  const rs = pts?.rshoulder;
  const shMid = midPt(ls, rs);
  const trunk = pts?.trunk;
  let nose = pts?.nose;
  if (!nose && !shMid) return;

  const sw = shoulderWidthPx > 20
    ? shoulderWidthPx
    : (ls && rs ? Math.hypot(rs[0] - ls[0], rs[1] - ls[1]) : 140);

  // Seed missing face landmarks from nose + shoulder span (older overlays).
  if (!nose && shMid) {
    nose = [shMid[0], shMid[1] - sw * 0.22];
  }
  const half = Math.max(12, Math.min(sw * 0.145, 42));
  const fillPt = (have, est) => (have || est);
  const leye = fillPt(pts?.leye, nose && [nose[0] - half * 0.42, nose[1] - half * 0.52]);
  const reye = fillPt(pts?.reye, nose && [nose[0] + half * 0.42, nose[1] - half * 0.52]);
  const leyeI = fillPt(pts?.leye_inner, leye && [leye[0] + half * 0.18, leye[1]]);
  const leyeO = fillPt(pts?.leye_outer, leye && [leye[0] - half * 0.28, leye[1] + half * 0.02]);
  const reyeI = fillPt(pts?.reye_inner, reye && [reye[0] - half * 0.18, reye[1]]);
  const reyeO = fillPt(pts?.reye_outer, reye && [reye[0] + half * 0.28, reye[1] + half * 0.02]);
  const mouthL = fillPt(pts?.mouth_l, nose && [nose[0] - half * 0.32, nose[1] + half * 0.58]);
  const mouthR = fillPt(pts?.mouth_r, nose && [nose[0] + half * 0.32, nose[1] + half * 0.58]);
  const lear = fillPt(pts?.lear, nose && [nose[0] - half * 0.98, nose[1] - half * 0.28]);
  const rear = fillPt(pts?.rear, nose && [nose[0] + half * 0.98, nose[1] - half * 0.28]);

  const hasRealFace = Boolean(
    pts?.leye || pts?.reye || pts?.mouth_l || pts?.mouth_r || pts?.lear || pts?.rear,
  );

  const neck = virt?.neck
    || (nose && shMid ? lerpPt(shMid, nose, 0.40) : shMid);
  const base = virt?.sternum || shMid || trunk;
  if (base && neck) {
    drawChalkRibbon(ctx, base, neck, {
      halfWidth: Math.max(2.8, Math.min(5.0, sw * 0.022)),
      blur,
      curve: 0.08,
    });
  }
  if (neck && nose) {
    const chinHint = midPt(mouthL, mouthR) || nose;
    drawChalkStick(ctx, neck, chinHint, { width: 1.45, blur: blur * 0.7, curve: 0.04 });
  }

  // MediaPipe Pose face topology
  const meshEdges = [
    [leyeI, leye], [leye, leyeO], [leyeO, lear],
    [reyeI, reye], [reye, reyeO], [reyeO, rear],
    [leyeI, nose], [reyeI, nose],
    [leyeI, reyeI],
    [mouthL, mouthR],
    [mouthL, nose], [mouthR, nose],
  ];
  meshEdges.forEach(([a, b]) => {
    if (!a || !b) return;
    drawChalkStick(ctx, a, b, {
      width: hasRealFace ? 1.55 : 1.35,
      blur: blur * 0.85,
      curve: 0.04,
    });
  });

  // Face oval from eyes + mouth (+ ears)
  const midEyes = midPt(leye, reye);
  const midMouth = midPt(mouthL, mouthR);
  if (midEyes && midMouth && leyeO && reyeO) {
    const upX = midEyes[0] - midMouth[0];
    const upY = midEyes[1] - midMouth[1];
    const upLen = Math.hypot(upX, upY) || 1;
    const ux = upX / upLen;
    const uy = upY / upLen;
    const forehead = [midEyes[0] + ux * upLen * 1.12, midEyes[1] + uy * upLen * 1.12];
    const chin = [midMouth[0] - ux * upLen * 0.92, midMouth[1] - uy * upLen * 0.92];
    const lJaw = [
      mouthL[0] + (lear[0] - mouthL[0]) * 0.32,
      mouthL[1] + (chin[1] - mouthL[1]) * 0.55,
    ];
    const rJaw = [
      mouthR[0] + (rear[0] - mouthR[0]) * 0.32,
      mouthR[1] + (chin[1] - mouthR[1]) * 0.55,
    ];
    const oval = [lear, leyeO, forehead, reyeO, rear, rJaw, chin, lJaw];

    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.shadowColor = CHALK_PALETTE.dust;
    ctx.shadowBlur = blur;
    const trace = () => {
      ctx.beginPath();
      ctx.moveTo(oval[0][0], oval[0][1]);
      for (let i = 1; i < oval.length; i += 1) {
        const p0 = oval[i - 1];
        const p1 = oval[i];
        const pc = [(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2];
        ctx.quadraticCurveTo(p0[0], p0[1], pc[0], pc[1]);
      }
      const last = oval[oval.length - 1];
      const first = oval[0];
      ctx.quadraticCurveTo(last[0], last[1], first[0], first[1]);
      ctx.closePath();
    };
    trace();
    ctx.fillStyle = CHALK_PALETTE.fill;
    ctx.fill();
    [
      { color: CHALK_PALETTE.edgeSoft, width: 2.5 },
      { color: CHALK_PALETTE.edge, width: 1.35 },
    ].forEach(({ color, width }) => {
      trace();
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
    });
    ctx.restore();
  }

  [
    nose, leye, reye, mouthL, mouthR, lear, rear,
  ].forEach((p, i) => {
    if (!p) return;
    drawChalkJoint(ctx, p, { r: i === 0 ? 2.6 : 2.0, dim: i > 0 });
  });
  if (neck) drawChalkJoint(ctx, neck, { r: 2.2, dim: true });
}

const FOOT_TOES = [
  { id: "big", angle: -0.42, len: 0.38 },
  { id: "mid", angle: -0.08, len: 0.44 },
  { id: "small", angle: 0.28, len: 0.36 },
];

function lerpPt(a, b, t) {
  if (!a || !b) return null;
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

function midPt(a, b) {
  return lerpPt(a, b, 0.5);
}

function rotate2(fx, fy, ang) {
  const c = Math.cos(ang);
  const s = Math.sin(ang);
  return [fx * c - fy * s, fx * s + fy * c];
}

export function buildVirtualSkeletonJoints(pts) {
  const nose = pts.nose;
  const trunk = pts.trunk;
  const ls = pts.lshoulder;
  const rs = pts.rshoulder;
  const lh = pts.lhip;
  const rh = pts.rhip;
  const pelvis = midPt(lh, rh);
  const sternum = midPt(ls, rs) && trunk ? lerpPt(midPt(ls, rs), trunk, 0.35) : midPt(ls, rs);
  const neck = nose && trunk ? lerpPt(trunk, nose, 0.42) : null;
  const crown = nose ? lerpPt(nose, neck || trunk, -0.35) : null;
  const lumbar = trunk && pelvis ? lerpPt(trunk, pelvis, 0.55) : null;
  return { pelvis, sternum, neck, crown, lumbar };
}

function footToePoints(ankle, knee, cw, ch) {
  if (!ankle || !knee) return [];
  let fx = ankle[0] - knee[0];
  let fy = ankle[1] - knee[1];
  const fl = Math.hypot(fx, fy);
  if (fl < 8) return [];
  fx /= fl;
  fy /= fl;
  const px = -fy;
  const py = fx;
  const scale = Math.min(cw, ch) * 0.045;
  return FOOT_TOES.map((t) => {
    const [dx, dy] = rotate2(fx, fy, t.angle);
    return [ankle[0] + dx * scale * t.len + px * t.angle * scale * 0.08, ankle[1] + dy * scale * t.len + py * t.angle * scale * 0.08];
  });
}

export function resolveArmSideKeys(affectedSide) {
  const aff = String(affectedSide || "").toLowerCase();
  if (aff === "left") {
    return { affPrefix: "l", ncPrefix: "r", useGenericClinical: true };
  }
  if (aff === "right") {
    return { affPrefix: "r", ncPrefix: "l", useGenericClinical: true };
  }
  return { affPrefix: null, ncPrefix: null, useGenericClinical: false };
}

/** Radius + ulna — two parallel teal forearm bars (elbow → wrist), like nl overlay reference. */
export function drawForearmRadiusUlna(drawSeg, pts, phaseColor) {
  const elbow = pts.elbow;
  if (!elbow) return;
  const wrist = pts.wrist || pts.hl_wrist || pts.palm;
  if (!wrist) return;

  const dx = wrist[0] - elbow[0];
  const dy = wrist[1] - elbow[1];
  const len = Math.hypot(dx, dy);
  if (len < 12) return;

  const px = -dy / len;
  const py = dx / len;

  let half = len * 0.028;
  half = Math.max(4.5, Math.min(half, len * 0.05));

  let sign = 1;
  const thumbSide = pts.thumb || pts.index;
  const pinkySide = pts.pinky;
  if (thumbSide && pinkySide) {
    const thumbProj = (thumbSide[0] - elbow[0]) * px + (thumbSide[1] - elbow[1]) * py;
    const pinkyProj = (pinkySide[0] - elbow[0]) * px + (pinkySide[1] - elbow[1]) * py;
    sign = thumbProj >= pinkyProj ? 1 : -1;
  } else if (thumbSide) {
    sign = ((thumbSide[0] - elbow[0]) * px + (thumbSide[1] - elbow[1]) * py) >= 0 ? 1 : -1;
  }

  const green = phaseColor?.bone || "#10b981";
  const radiusElbow = [elbow[0] + px * half * sign, elbow[1] + py * half * sign];
  const radiusWrist = [wrist[0] + px * half * sign, wrist[1] + py * half * sign];
  const ulnaElbow = [elbow[0] - px * half * sign, elbow[1] - py * half * sign];
  const ulnaWrist = [wrist[0] - px * half * sign, wrist[1] - py * half * sign];

  const boneOpts = { width: 8, color: green, blur: 14 };
  drawSeg(radiusElbow, radiusWrist, boneOpts);
  drawSeg(ulnaElbow, ulnaWrist, boneOpts);
}

export {
  HAND_FINGER_BONES,
  HAND_FINGER_ORDER,
  buildAnatomyHandLandmarks,
  estimateHandScale,
  handAxesFromElbowPalm,
  resolveHandSkeleton,
};

export function drawClinicalSkeleton(ctx, helpers, spec) {
  const {
    pt,
    cw,
    ch,
    drawBone,
    dot,
    line,
    shadowOff,
    affectedSide,
    useHandHl,
    phaseColor,
    overlayStyle = "clinical",
    shoulderWidthPx = 0,
  } = spec;
  const pal = SKELETON_PALETTE;
  const chalkMode = overlayStyle === "chalk";

  const keys = [
    "nose", "lear", "rear",
    "leye", "reye", "leye_inner", "leye_outer", "reye_inner", "reye_outer",
    "mouth_l", "mouth_r",
    "trunk", "lshoulder", "rshoulder", "lelbow", "relbow",
    "lwrist", "rwrist", "lhip", "rhip", "lknee", "rknee", "lankle", "rankle",
    "shoulder", "elbow", "palm", "wrist", "hl_wrist", "thumb", "index", "pinky",
  ];
  const pts = {};
  keys.forEach((k) => { pts[k] = pt(k); });

  const virt = buildVirtualSkeletonJoints(pts);
  const { ncPrefix, affPrefix } = resolveArmSideKeys(affectedSide);
  const upperLimbOnly = Boolean(affPrefix);

  const ribbonHalfFor = (a, b, widthHint = 8) => {
    const len = (a && b) ? Math.hypot(b[0] - a[0], b[1] - a[1]) : 80;
    const fromShoulder = shoulderWidthPx > 20 ? shoulderWidthPx * 0.038 : 0;
    const fromLen = len * 0.028;
    const base = fromShoulder || fromLen || 4.2;
    const scale = Math.max(0.7, Math.min(1.15, (widthHint || 8) / 9));
    // Keep ribbons narrow so they hug the limb instead of looking like yellow bars.
    return Math.max(3.2, Math.min(7.5, base * scale));
  };

  // Always white chalk — never tint with Pre/Post/Healthy phase colors.
  const chalkEdge = CHALK_PALETTE.edge;

  const drawSeg = (a, b, opts = {}) => {
    if (!a || !b) return;
    if (chalkMode) {
      const thin = Boolean(opts.thin) || (opts.width != null && opts.width < 4);
      if (thin) {
        drawChalkStick(ctx, a, b, {
          color: opts.dim ? CHALK_PALETTE.dimEdge : chalkEdge,
          width: Math.max(1.4, (opts.width || 3) * 0.45),
          blur: shadowOff != null ? 0 : 3.5,
          curve: 0.07,
        });
      } else {
        drawChalkRibbon(ctx, a, b, {
          halfWidth: ribbonHalfFor(a, b, opts.width),
          fill: opts.dim ? CHALK_PALETTE.dimFill : CHALK_PALETTE.fill,
          edge: opts.dim ? CHALK_PALETTE.dimEdge : chalkEdge,
          blur: shadowOff != null ? 0 : 4,
          curve: 0.14,
        });
      }
      return;
    }
    drawBone(a, b, {
      width: opts.width ?? 6,
      color: opts.color ?? pal.bone,
      shadow: pal.shadow,
      blur: shadowOff != null ? shadowOff : 10,
    });
  };

  if (!upperLimbOnly) {
    drawSeg(pts.lhip, pts.rhip, { width: 7, color: pal.boneDim, dim: true });
    if (virt.pelvis && pts.trunk) drawSeg(pts.trunk, virt.pelvis, { width: 6, color: pal.boneDim, dim: true });
    if (virt.lumbar && virt.pelvis) drawSeg(virt.lumbar, virt.pelvis, { width: 5, color: pal.boneDim, dim: true });
    if (virt.lumbar && pts.trunk) drawSeg(pts.trunk, virt.lumbar, { width: 5, color: pal.boneDim, dim: true });
    if (!chalkMode) {
      if (virt.neck && pts.trunk) drawSeg(pts.trunk, virt.neck, { width: 5, color: pal.boneDim, dim: true });
      if (virt.crown && virt.neck) drawSeg(virt.neck, virt.crown, { width: 4, color: pal.boneDim, dim: true });
      if (pts.nose && virt.neck) drawSeg(virt.neck, pts.nose, { width: 3, color: pal.boneDim, thin: true, dim: true });
    }

    drawSeg(pts.lhip, pts.lknee, { width: 7, color: pal.boneDim, dim: true });
    drawSeg(pts.lknee, pts.lankle, { width: 6, color: pal.boneDim, dim: true });
    drawSeg(pts.rhip, pts.rknee, { width: 7, color: pal.boneDim, dim: true });
    drawSeg(pts.rknee, pts.rankle, { width: 6, color: pal.boneDim, dim: true });

    [["lankle", "lknee"], ["rankle", "rknee"]].forEach(([ankleK, kneeK]) => {
      const toes = footToePoints(pts[ankleK], pts[kneeK], cw, ch);
      toes.forEach((tip) => drawSeg(pts[ankleK], tip, { width: 2.5, color: pal.boneDim, thin: true, dim: true }));
    });
  }

  drawSeg(pts.lshoulder, pts.rshoulder, { width: 6, color: pal.bone, dim: !upperLimbOnly });

  if (chalkMode) {
    drawChalkHead(ctx, pts, virt, {
      shoulderWidthPx,
      blur: shadowOff != null ? 0 : 4,
    });
  } else if (upperLimbOnly) {
    const neckBase = virt.sternum || pts.trunk;
    if (virt.neck && neckBase) drawSeg(neckBase, virt.neck, { width: 5, color: pal.boneDim, dim: true });
    if (virt.crown && virt.neck) drawSeg(virt.neck, virt.crown, { width: 4, color: pal.boneDim, dim: true });
    if (pts.nose && virt.neck) drawSeg(virt.neck, pts.nose, { width: 3, color: pal.boneDim, thin: true, dim: true });
  }

  if (!upperLimbOnly && virt.sternum && pts.lshoulder) {
    if (chalkMode) {
      drawChalkStick(ctx, virt.sternum, pts.lshoulder, { color: CHALK_PALETTE.dimEdge, width: 1.4, blur: 3 });
      drawChalkStick(ctx, virt.sternum, pts.rshoulder, { color: CHALK_PALETTE.dimEdge, width: 1.4, blur: 3 });
    } else {
      line(virt.sternum, pts.lshoulder, { color: pal.rib, width: 1.5, dash: [4, 5] });
      line(virt.sternum, pts.rshoulder, { color: pal.rib, width: 1.5, dash: [4, 5] });
    }
  }
  if (!upperLimbOnly && virt.sternum && pts.trunk) {
    if (chalkMode) {
      drawChalkStick(ctx, virt.sternum, pts.trunk, { color: CHALK_PALETTE.dimEdge, width: 1.4, blur: 3 });
    } else {
      line(virt.sternum, pts.trunk, { color: pal.rib, width: 1.5, dash: [4, 5] });
    }
  }

  if (ncPrefix && !upperLimbOnly) {
    const sh = pts[`${ncPrefix}shoulder`];
    const el = pts[`${ncPrefix}elbow`];
    const wr = pts[`${ncPrefix}wrist`];
    drawSeg(sh, el, { width: 6, color: pal.boneDim, dim: true });
    drawSeg(el, wr, { width: 5, color: pal.boneDim, dim: true });
  }

  const forearmEnd = pts.wrist || pts.hl_wrist || pts.palm;

  // Affected upper arm + forearm as chalk body-boundary ribbons
  if (pts.shoulder && pts.elbow) {
    drawSeg(pts.shoulder, pts.elbow, { width: 10, color: pal.clinical });
  }
  if (chalkMode) {
    if (pts.elbow && forearmEnd) {
      drawSeg(pts.elbow, forearmEnd, { width: 9, color: pal.clinical });
    }
  } else {
    drawForearmRadiusUlna(drawSeg, pts, phaseColor);
  }
  if (!useHandHl && pts.wrist && pts.palm) {
    drawSeg(pts.wrist, pts.palm, { width: 5, color: pal.bone, thin: chalkMode });
  }

  const dimJoints = upperLimbOnly
    ? [pts.trunk, pts.lshoulder, pts.rshoulder].filter(Boolean)
    : [
      ...(chalkMode ? [] : [pts.nose, virt.neck, virt.crown]),
      pts.trunk, virt.lumbar, virt.pelvis, virt.sternum,
      pts.lshoulder, pts.rshoulder,
      pts.lelbow, pts.relbow, pts.lwrist, pts.rwrist,
      pts.lhip, pts.rhip, pts.lknee, pts.rknee, pts.lankle, pts.rankle,
    ];
  dimJoints.forEach((p) => {
    if (!p) return;
    if (chalkMode) drawChalkJoint(ctx, p, { r: 3.2, dim: true });
    else dot(p, { fill: pal.jointDim, stroke: pal.jointOutline, r: 5 });
  });

  [pts.shoulder, pts.elbow, forearmEnd].forEach((p, i) => {
    if (!p) return;
    if (chalkMode) {
      drawChalkJoint(ctx, p, { r: i === 2 && useHandHl ? 4.2 : 5.5 });
    } else {
      dot(p, { fill: pal.joint, stroke: pal.jointOutline, r: i === 2 && useHandHl ? 5 : 9 });
    }
  });

  return { pts, virt, forearmEnd, palmPt: pts.palm || forearmEnd, overlayStyle };
}
