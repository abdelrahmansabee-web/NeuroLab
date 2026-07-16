import React, { useRef, useState, useEffect, useCallback, useMemo } from "react";
import { Play, Pause, Maximize, ChevronLeft, ChevronRight, Download } from "lucide-react";

export function computeOverlayMetrics(overlayData) {
  if (!overlayData?.frames?.length) return null;
  const frames = overlayData.frames;
  const fps = overlayData.fps || 60;
  const win = overlayData.movement_window || { start_idx: 0, end_idx: frames.length - 1 };
  const startIdx = Math.max(0, Math.min(frames.length - 1, win.start_idx || 0));
  const endIdx = Math.max(startIdx, Math.min(frames.length - 1, win.end_idx || frames.length - 1));
  const peakFrames = overlayData.peak_frames || [];
  const cmPerPx = overlayData.metrics?.cm_per_px || 0;

  // Peak velocity = elbow angular velocity (deg/sec).
  let peakV = 0;
  for (let i = startIdx + 1; i <= endIdx; i++) {
    const a1 = frames[i - 1]?.elbow_angle;
    const a2 = frames[i]?.elbow_angle;
    if (a1 == null || a2 == null) continue;
    const dt = (frames[i]?.time != null && frames[i - 1]?.time != null)
      ? Math.max(1e-6, frames[i].time - frames[i - 1].time)
      : 1 / fps;
    const angVel = Math.abs((a2 - a1) / dt);
    if (angVel > peakV) peakV = angVel;
  }

  const t0 = frames[startIdx]?.time != null ? frames[startIdx].time : startIdx / fps;
  const t1 = frames[endIdx]?.time != null ? frames[endIdx].time : endIdx / fps;
  const movementTime = Math.max(0, t1 - t0);

  // Pause/stop detection based on hand speed (kept for movement segmentation).
  const handSpeeds = frames.map((f) => f.speed || 0);
  const handPeakV = handSpeeds.length ? Math.max(...handSpeeds) : 0;
  const speedThreshold = handPeakV > 0 ? 0.05 * handPeakV : 1.0;
  let pauseTime = 0;
  let stops = 0;
  for (let i = startIdx; i <= endIdx; i++) {
    const s = frames[i]?.speed || 0;
    if (s < speedThreshold) pauseTime += 1 / fps;
    if (i > startIdx) {
      const prevS = frames[i - 1]?.speed || 0;
      if (prevS >= speedThreshold && s < speedThreshold) stops++;
    }
  }

  let pathLength = 0;
  const startPalm = frames[startIdx]?.palm;
  for (let i = startIdx + 1; i <= endIdx; i++) {
    const prev = frames[i - 1]?.palm;
    const curr = frames[i]?.palm;
    if (prev && curr) pathLength += Math.hypot(curr[0] - prev[0], curr[1] - prev[1]);
  }
  const endPalm = frames[endIdx]?.palm;
  let straightness = 0;
  if (startPalm && endPalm && pathLength > 0) {
    const displacement = Math.hypot(endPalm[0] - startPalm[0], endPalm[1] - startPalm[1]);
    straightness = Math.min(1, displacement / pathLength);
  }

  let trunkRatio = 0;
  const trunkStart = frames[startIdx]?.trunk;
  const trunkEnd = frames[endIdx]?.trunk;
  if (trunkStart && trunkEnd && startPalm && endPalm) {
    const trunkDisp = Math.abs(trunkEnd[0] - trunkStart[0]);
    const palmDisp = Math.hypot(endPalm[0] - startPalm[0], endPalm[1] - startPalm[1]);
    if (palmDisp > 0) trunkRatio = Math.min(1, trunkDisp / palmDisp);
  }

  // Shoulder elevation = ratio of affected shoulder height above shoulder midpoint.
  let shoulderElevation = 0;
  for (let i = startIdx; i <= endIdx; i++) {
    const v = frames[i]?.shoulder_elevation_norm;
    if (v != null && !Number.isNaN(v)) {
      shoulderElevation = Math.max(shoulderElevation, v);
    }
  }

  let elbowAngleMean = 0;
  let elbowAngleCount = 0;
  for (let i = startIdx; i <= endIdx; i++) {
    const a = frames[i]?.elbow_angle;
    if (a != null && !Number.isNaN(a)) {
      elbowAngleMean += a;
      elbowAngleCount++;
    }
  }
  if (elbowAngleCount > 0) elbowAngleMean /= elbowAngleCount;

  const out = {
    nvp: peakFrames.length,
    straightness,
    pause_time_sec: pauseTime,
    number_of_stops: stops,
    trunk_ratio: trunkRatio,
    shoulder_elevation_norm: shoulderElevation,
    shoulder_vert_norm: shoulderElevation,
    elbow_angle_mean_deg: elbowAngleMean,
    movement_time_sec: movementTime,
    peak_velocity_px_s: peakV,
    peak_velocity_deg_s: peakV,
  };

  if (cmPerPx > 0) {
    out.peak_velocity_cm_s = peakV;
  }
  if (overlayData.metrics?.sparc != null) {
    out.sparc = overlayData.metrics.sparc;
  }
  if (overlayData.metrics?.hand_displacement_norm != null) {
    out.hand_displacement_norm = overlayData.metrics.hand_displacement_norm;
  }

  return out;
}

export function ValidationOverlayPlayer({ videoUrl, overlayData, phaseLabel, autoPlay = false, autoRender = false, onEnded, onDownloadReady, onError }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const recCanvasRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [recording, setRecording] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [renderProgress, setRenderProgress] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [videoAspect, setVideoAspect] = useState(null);
  const mediaRecorderRef = useRef(null);
  const recordedChunksRef = useRef([]);
  const rafRef = useRef(null);
  const autoRenderStartedRef = useRef(false);

  const phaseColor = useMemo(() => {
    const p = (phaseLabel || "").toLowerCase();
    if (p.includes("post")) return { main: "#10b981", glow: "rgba(16,185,129,0.45)", text: "#6ee7b7" };
    if (p.includes("pre")) return { main: "#0ea5e9", glow: "rgba(14,165,233,0.45)", text: "#7dd3fc" };
    return { main: "#f59e0b", glow: "rgba(245,158,11,0.45)", text: "#fcd34d" };
  }, [phaseLabel]);

  const frames = overlayData?.frames || [];
  const fps = overlayData?.fps || 60;
  const metrics = overlayData?.metrics || {};
  const win = overlayData?.movement_window || { start_idx: 0, end_idx: frames.length - 1 };
  const startPalm = overlayData?.start_palm;
  const endPalm = overlayData?.end_palm;
  const velocityProfile = overlayData?.velocity_profile;
  const peakFrames = overlayData?.peak_frames || [];

  const getElbowAngVel = useCallback((idx) => {
    if (idx <= 0 || idx >= frames.length) return 0;
    const a1 = frames[idx - 1]?.elbow_angle;
    const a2 = frames[idx]?.elbow_angle;
    if (a1 == null || a2 == null) return 0;
    const dt = (frames[idx]?.time != null && frames[idx - 1]?.time != null)
      ? Math.max(1e-6, frames[idx].time - frames[idx - 1].time)
      : 1 / fps;
    return Math.abs((a2 - a1) / dt);
  }, [frames, fps]);

  const peakElbowAngVel = useMemo(() => {
    let maxV = 0;
    for (let i = 1; i < frames.length; i++) {
      const v = getElbowAngVel(i);
      if (v > maxV) maxV = v;
    }
    return maxV;
  }, [frames, getElbowAngVel]);
  const peakV = peakElbowAngVel || 1;
  const handPeakV = useMemo(() => {
    const speeds = frames.map((f) => f.speed || 0);
    return speeds.length ? Math.max(...speeds) : 1;
  }, [frames]);

  const getFrameIndex = useCallback((time) => {
    if (!frames.length) return 0;
    const idx = Math.floor(time * fps);
    return Math.max(0, Math.min(frames.length - 1, idx));
  }, [frames.length, fps]);

  const formatValue = (v, digits = 2) => {
    if (v == null || Number.isNaN(v)) return "—";
    if (digits === 0) return Math.round(v).toString();
    return Number(v).toFixed(digits);
  };

  const drawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const rect = canvas.getBoundingClientRect();
    const cw = Math.max(1, Math.round(rect.width * window.devicePixelRatio));
    const ch = Math.max(1, Math.round(rect.height * window.devicePixelRatio));
    if (canvas.width !== cw || canvas.height !== ch) {
      canvas.width = cw;
      canvas.height = ch;
    }
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, cw, ch);

    if (!frames.length) return;
    const idx = getFrameIndex(video.currentTime || 0);
    const f = frames[idx];
    if (!f) return;

    const color = phaseColor;

    function pt(name) {
      const p = f[name];
      if (!p || p[0] == null || p[1] == null) return null;
      return [p[0] * cw, p[1] * ch];
    }

    function toCanvas(p) {
      if (!p || p[0] == null || p[1] == null) return null;
      return [p[0] * cw, p[1] * ch];
    }

    function line(a, b, opts = {}) {
      if (!a || !b) return;
      const { color = "rgba(255,255,255,0.5)", width = 2, dash = [] } = opts;
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.setLineDash(dash);
      ctx.lineCap = "round";
      ctx.stroke();
      ctx.setLineDash([]);
    }

    function dot(p, opts = {}) {
      if (!p) return;
      const { fill = "#fff", stroke = "rgba(0,0,0,0.5)", r = 4 } = opts;
      ctx.beginPath();
      ctx.arc(p[0], p[1], r, 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    function pill(text, p, opts = {}) {
      if (!p) return;
      const {
        offsetX = 10,
        offsetY = -10,
        bg = "rgba(14,17,32,0.72)",
        border = "rgba(255,255,255,0.18)",
        color = "#fff",
        size = "10px",
        padding = 4,
      } = opts;
      ctx.font = `bold ${size} sans-serif`;
      const tm = ctx.measureText(text);
      const tw = tm.width;
      const th = 12;
      let tx = p[0] + offsetX;
      let ty = p[1] + offsetY;
      tx = Math.max(4, Math.min(cw - tw - padding * 2 - 4, tx));
      ty = Math.max(th + padding, Math.min(ch - 4, ty));
      ctx.save();
      ctx.shadowColor = "rgba(0,0,0,0.35)";
      ctx.shadowBlur = 6;
      ctx.fillStyle = bg;
      ctx.strokeStyle = border;
      ctx.lineWidth = 1;
      const r = 6;
      const x = tx - padding, y = ty - th - padding, w = tw + padding * 2, h = th + padding * 2;
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + w - r, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + r);
      ctx.lineTo(x + w, y + h - r);
      ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      ctx.lineTo(x + r, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - r);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = color;
      ctx.fillText(text, tx, ty);
    }

    function pillWithArrow(text, p, opts = {}) {
      if (!p) return;
      const {
        offsetX = 10,
        offsetY = -10,
        bg = "rgba(14,17,32,0.78)",
        border = "rgba(255,255,255,0.22)",
        color = "#fff",
        size = `${Math.round(10 * window.devicePixelRatio)}px`,
        padding = 5,
      } = opts;
      ctx.font = `bold ${size} sans-serif`;
      const tm = ctx.measureText(text);
      const tw = tm.width;
      const th = Math.round(11 * window.devicePixelRatio);
      let lx = p[0] + offsetX;
      let ly = p[1] + offsetY;
      const w = tw + padding * 2;
      const h = th + padding * 2;
      lx = Math.max(4, Math.min(cw - w - 4, lx));
      ly = Math.max(h + 4, Math.min(ch - 4, ly));
      const cx = lx + w / 2;
      const cy = ly - h / 2;
      ctx.save();
      ctx.strokeStyle = border;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([2, 2]);
      ctx.beginPath();
      ctx.moveTo(p[0], p[1]);
      ctx.lineTo(cx, cy);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
      ctx.save();
      ctx.shadowColor = "rgba(0,0,0,0.4)";
      ctx.shadowBlur = 8;
      ctx.fillStyle = bg;
      ctx.strokeStyle = border;
      ctx.lineWidth = 1;
      const rr = 6;
      const x = lx, y = ly - h, ww = w, hh = h;
      ctx.beginPath();
      ctx.moveTo(x + rr, y);
      ctx.lineTo(x + ww - rr, y);
      ctx.quadraticCurveTo(x + ww, y, x + ww, y + rr);
      ctx.lineTo(x + ww, y + hh - rr);
      ctx.quadraticCurveTo(x + ww, y + hh, x + ww - rr, y + hh);
      ctx.lineTo(x + rr, y + hh);
      ctx.quadraticCurveTo(x, y + hh, x, y + hh - rr);
      ctx.lineTo(x, y + rr);
      ctx.quadraticCurveTo(x, y, x + rr, y);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = color;
      ctx.fillText(text, x + padding, y + h - padding - 2);
    }

    const speed = getElbowAngVel(idx);

    const nose = pt("nose");
    const ls = pt("lshoulder");
    const rs = pt("rshoulder");
    const le = pt("lelbow");
    const re = pt("relbow");
    const lw = pt("lwrist");
    const rw = pt("rwrist");
    const lh = pt("lhip");
    const rh = pt("rhip");
    const lk = pt("lknee");
    const rk = pt("rknee");
    const la = pt("lankle");
    const ra = pt("rankle");
    const trunk = pt("trunk");
    const palm = pt("palm");
    const elbow = pt("elbow");
    const wrist = pt("wrist");
    const shoulder = pt("shoulder");

    const boneColor = "#f3f0d7";
    const boneOutline = "rgba(60,55,45,0.9)";
    const boneShadow = "rgba(0,0,0,0.4)";
    const jointFill = "#e8e4c9";
    const jointOutline = "rgba(40,35,28,0.95)";

    const drawBone = (a, b, opts = {}) => {
      if (!a || !b) return;
      ctx.save();
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.shadowColor = opts.shadow || boneShadow;
      ctx.shadowBlur = opts.blur || 12;
      const width = opts.width || 9;
      line(a, b, { color: boneOutline, width: width + 3 });
      line(a, b, { color: opts.color || boneColor, width });
      ctx.restore();
    };

    drawBone(ls, rs);
    drawBone(ls, lh);
    drawBone(rs, rh);
    drawBone(lh, rh);
    drawBone(ls, le);
    drawBone(rs, re);
    drawBone(le, lw);
    drawBone(re, rw);
    drawBone(nose, trunk, { width: 6, color: "rgba(243,240,215,0.85)" });
    drawBone(lh, lk);
    drawBone(rh, rk);
    drawBone(lk, la);
    drawBone(rk, ra);

    [nose, ls, rs, le, re, lw, rw, lh, rh, lk, rk, la, ra, trunk].forEach((p) => {
      if (p) dot(p, { fill: jointFill, stroke: jointOutline, r: 9 });
    });

    const drawActiveBone = (a, b, opts = {}) => {
      if (!a || !b) return;
      ctx.save();
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.shadowColor = opts.glow || color.glow;
      ctx.shadowBlur = opts.blur || 18;
      const width = opts.width || 9;
      line(a, b, { color: "rgba(14,17,32,0.7)", width: width + 2.5 });
      line(a, b, { color: opts.color || color.main, width });
      ctx.restore();
    };
    drawActiveBone(shoulder, elbow);
    drawActiveBone(elbow, wrist);
    drawActiveBone(wrist, palm, { width: 8 });

    [shoulder, elbow, wrist].forEach((p) => {
      if (p) dot(p, { fill: color.main, stroke: "#fff", r: 10 });
    });
    if (palm) dot(palm, { fill: "#facc15", stroke: "#fff", r: 11 });

    const speedThreshold = handPeakV > 0 ? 0.05 * handPeakV : 1.0;
    const inMovement = idx >= win.start_idx && idx <= win.end_idx;
    const t0 = win.start_idx < frames.length ? (frames[win.start_idx].time || win.start_idx / fps) : 0;

    const currentNVP = peakFrames.filter((pi) => pi <= idx).length;

    let currentPeakElbowAngVel = 0;
    for (let i = 1; i <= idx && i < frames.length; i++) {
      currentPeakElbowAngVel = Math.max(currentPeakElbowAngVel, getElbowAngVel(i));
    }

    let currentMovementTime = 0;
    if (inMovement && idx < frames.length) {
      const t = frames[idx].time || idx / fps;
      currentMovementTime = Math.max(0, t - t0);
    }

    let currentPauseTime = 0;
    let currentStops = 0;
    for (let i = win.start_idx; i <= idx && i < frames.length; i++) {
      const s = frames[i].speed || 0;
      if (s < speedThreshold) {
        currentPauseTime += 1 / fps;
      }
      if (i > win.start_idx) {
        const prevS = frames[i - 1].speed || 0;
        if (prevS >= speedThreshold && s < speedThreshold) {
          currentStops++;
        }
      }
    }

    let currentStraightness = 0;
    if (inMovement) {
      let pathLength = 0;
      const startP = frames[win.start_idx]?.palm;
      for (let i = win.start_idx + 1; i <= idx && i < frames.length; i++) {
        const prev = frames[i - 1]?.palm;
        const curr = frames[i]?.palm;
        if (prev && curr) {
          pathLength += Math.hypot(curr[0] - prev[0], curr[1] - prev[1]);
        }
      }
      const endP = frames[idx]?.palm;
      if (startP && endP && pathLength > 0) {
        const displacement = Math.hypot(endP[0] - startP[0], endP[1] - startP[1]);
        currentStraightness = Math.min(1, displacement / pathLength);
      }
    }

    let currentTrunkRatio = 0;
    if (inMovement) {
      const trunkStart = frames[win.start_idx]?.trunk;
      const trunkEnd = frames[idx]?.trunk;
      const palmStart = frames[win.start_idx]?.palm;
      const palmEnd = frames[idx]?.palm;
      if (trunkStart && trunkEnd && palmStart && palmEnd) {
        const trunkDisp = Math.abs(trunkEnd[0] - trunkStart[0]);
        const palmDisp = Math.hypot(palmEnd[0] - palmStart[0], palmEnd[1] - palmStart[1]);
        if (palmDisp > 0) {
          currentTrunkRatio = Math.min(1, trunkDisp / palmDisp);
        }
      }
    }

    let currentShoulderElevation = 0;
    if (f && typeof f.shoulder_elevation_norm === "number" && !Number.isNaN(f.shoulder_elevation_norm)) {
      currentShoulderElevation = f.shoulder_elevation_norm;
    }

    const currentElbowAngle = f.elbow_angle || 0;
    const currentSpeed = getElbowAngVel(idx);
    const wipingVerdict = f.wiping_verdict;
    const wiping = overlayData?.wiping || {};

    const dpr = window.devicePixelRatio;
    const labelSize = `${Math.round(10 * dpr)}px`;
    const labelPad = 5 * dpr;
    const labelH = Math.round(12 * dpr);

    function drawSimpleLabel(text, anchor, offsetX, offsetY, opts = {}) {
      if (!anchor) return;
      const align = opts.align || "left";
      ctx.font = `bold ${labelSize} sans-serif`;
      const tm = ctx.measureText(text);
      const w = tm.width + labelPad * 2;
      const h = labelH + labelPad * 2;
      let x = anchor[0] + offsetX;
      if (align === "center") x = anchor[0] + offsetX - w / 2;
      x = Math.max(4, Math.min(cw - w - 4, x));
      let y = anchor[1] + offsetY;
      y = Math.max(h + 4, Math.min(ch - 4, y));
      ctx.save();
      ctx.shadowColor = "rgba(0,0,0,0.5)";
      ctx.shadowBlur = 8;
      ctx.fillStyle = opts.bg || "rgba(14,17,32,0.85)";
      ctx.strokeStyle = opts.border || "rgba(255,255,255,0.25)";
      ctx.lineWidth = 1;
      const rr = 5;
      ctx.beginPath();
      ctx.moveTo(x + rr, y);
      ctx.lineTo(x + w - rr, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + rr);
      ctx.lineTo(x + w, y + h - rr);
      ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
      ctx.lineTo(x + rr, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - rr);
      ctx.lineTo(x, y + rr);
      ctx.quadraticCurveTo(x, y, x + rr, y);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = opts.color || "#fff";
      ctx.fillText(text, x + labelPad, y + h - labelPad - 2);
    }

    const cx = cw / 2;
    if (shoulder) {
      const shText = currentShoulderElevation > 0 ? `Sh ${currentShoulderElevation.toFixed(2)}` : "Sh";
      drawSimpleLabel(shText, shoulder, shoulder[0] > cx ? -110 : 14, -28, { color: color.text, border: color.glow });
    }
    if (elbow) {
      drawSimpleLabel(`El ${currentElbowAngle.toFixed(0)}°`, elbow, elbow[0] > cx ? -80 : 14, -22, { color: color.text, border: color.glow });
    }
    if (palm) {
      drawSimpleLabel(`Ha ${Math.round(currentSpeed)} °/s`, palm, palm[0] > cx ? -100 : 18, -24, { color: "#fde047", border: "rgba(250,204,21,0.6)" });
      drawSimpleLabel(`NVP ${currentNVP}`, palm, 0, 28, { color: color.text, border: color.glow, align: "center" });
      if (wipingVerdict) {
        drawSimpleLabel(
          `${wipingVerdict.toUpperCase()}`,
          palm,
          0,
          48,
          { color: "#fde047", border: "rgba(250,204,21,0.6)", align: "center" }
        );
      }
    }
    if (trunk) {
      drawSimpleLabel(`Tr ${(currentTrunkRatio * 100).toFixed(0)}%`, trunk, trunk[0] > cx ? -80 : -80, -52, { color: "#fde047", border: "rgba(250,204,21,0.6)" });
    }

    const startPt = toCanvas(startPalm);
    const endPt = toCanvas(endPalm);

    if (idx >= win.start_idx && idx <= win.end_idx) {
      ctx.save();
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.shadowColor = "rgba(16,185,129,0.6)";
      ctx.shadowBlur = 16;
      ctx.lineWidth = 6;
      ctx.strokeStyle = "rgba(16,185,129,0.95)";
      ctx.beginPath();
      let first = true;
      for (let i = win.start_idx; i <= idx; i++) {
        const tf = frames[i]?.palm;
        if (!tf) { continue; }
        const tx = tf[0] * cw;
        const ty = tf[1] * ch;
        if (first) {
          ctx.moveTo(tx, ty);
          first = false;
        } else {
          ctx.lineTo(tx, ty);
        }
      }
      ctx.stroke();
      ctx.restore();

      if (palm) {
        dot([palm[0], palm[1]], { fill: "#fff", stroke: "#10b981", r: 5 });
      }
    }
    if (startPt) {
      dot(startPt, { fill: "#facc15", stroke: "#fff", r: 7 });
      drawSimpleLabel("Start", startPt, startPt[0] > cx ? -52 : 20, 26, { color: "#fde047", border: "rgba(250,204,21,0.6)" });
    }
    if (endPt) {
      dot(endPt, { fill: "#10b981", stroke: "#fff", r: 7 });
      drawSimpleLabel("End", endPt, endPt[0] > cx ? -46 : 20, 26, { color: "#6ee7b7", border: "rgba(16,185,129,0.6)" });
    }

    const traceFrames = Math.max(12, Math.round(fps * 0.6));
    const traceStart = Math.max(0, idx - traceFrames);
    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.shadowColor = "rgba(250,204,21,0.40)";
    ctx.shadowBlur = 10;
    ctx.lineWidth = 5;
    let prev = null;
    for (let i = traceStart; i <= idx; i++) {
      const tf = frames[i]?.palm;
      if (!tf) { prev = null; continue; }
      const tx = tf[0] * cw;
      const ty = tf[1] * ch;
      const alpha = 0.25 + 0.7 * ((i - traceStart) / Math.max(1, idx - traceStart));
      ctx.strokeStyle = `rgba(250,204,21,${Math.min(0.95, alpha).toFixed(2)})`;
      if (prev) {
        ctx.beginPath();
        ctx.moveTo(prev[0], prev[1]);
        ctx.lineTo(tx, ty);
        ctx.stroke();
      }
      prev = [tx, ty];
    }
    ctx.restore();

    if (idx >= win.start_idx && idx <= win.end_idx) {
      ctx.save();
      ctx.strokeStyle = color.glow;
      ctx.lineWidth = 3;
      ctx.shadowColor = color.main;
      ctx.shadowBlur = 10;
      ctx.strokeRect(5, 5, cw - 10, ch - 10);
      ctx.restore();
    }

    const unscaledPad = 8 * dpr;
    const unscaledPanelW = Math.min(200 * dpr, cw * 0.45);
    const unscaledChartH = 30 * dpr;
    const unscaledRowH = 14 * dpr;
    const unscaledHeaderH = 26 * dpr;
    const unscaledPanelH = unscaledHeaderH + unscaledRowH * 8 + unscaledChartH * 3 + unscaledPad * 2 + 20;
    const maxPanelH = ch - unscaledPad * 2;
    const panelScale = unscaledPanelH > maxPanelH ? Math.max(0.65, maxPanelH / unscaledPanelH) : 1;

    const pad = unscaledPad * panelScale;
    const panelW = unscaledPanelW * panelScale;
    const chartH = unscaledChartH * panelScale;
    const rowH = unscaledRowH * panelScale;
    const headerH = unscaledHeaderH * panelScale;
    const panelH = unscaledPanelH * panelScale;

    const panelOnRight = true;
    const panelX = cw - panelW - pad;
    const panelY = pad;

    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,0.35)";
    ctx.shadowBlur = 12;
    ctx.fillStyle = "rgba(14,17,32,0.68)";
    ctx.strokeStyle = "rgba(255,255,255,0.14)";
    ctx.lineWidth = 1;
    const r = 10 * dpr * panelScale;
    const px = panelX, py = panelY, pw = panelW, ph = panelH;
    ctx.beginPath();
    ctx.moveTo(px + r, py);
    ctx.lineTo(px + pw - r, py);
    ctx.quadraticCurveTo(px + pw, py, px + pw, py + r);
    ctx.lineTo(px + pw, py + ph - r);
    ctx.quadraticCurveTo(px + pw, py + ph, px + pw - r, py + ph);
    ctx.lineTo(px + r, py + ph);
    ctx.quadraticCurveTo(px, py + ph, px, py + ph - r);
    ctx.lineTo(px, py + r);
    ctx.quadraticCurveTo(px, py, px + r, py);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = color.main;
    ctx.lineWidth = 2;
    ctx.shadowColor = color.glow;
    ctx.shadowBlur = 6;
    ctx.beginPath();
    ctx.moveTo(px + r, py + headerH - 2);
    ctx.lineTo(px + pw - r, py + headerH - 2);
    ctx.stroke();
    ctx.restore();

    const left = px + pad;
    const right = px + pw - pad;
    let cy = py + headerH + 14 * panelScale;
    const fsMain = `${Math.round(10 * dpr * panelScale)}px`;
    const fsSmall = `${Math.round(8 * dpr * panelScale)}px`;

    function row(labelText, valueText, accent = false) {
      ctx.font = `600 ${fsSmall} sans-serif`;
      ctx.fillStyle = "rgba(255,255,255,0.60)";
      ctx.fillText(labelText, left, cy);
      ctx.font = `bold ${fsMain} sans-serif`;
      ctx.fillStyle = accent ? color.text : "rgba(255,255,255,0.95)";
      ctx.textAlign = "right";
      ctx.fillText(valueText, right, cy);
      ctx.textAlign = "left";
      cy += rowH;
    }

    ctx.font = `bold ${Math.round(11 * dpr * panelScale)}px sans-serif`;
    ctx.fillStyle = "#fff";
    ctx.textAlign = "left";
    ctx.fillText(`${phaseLabel || "Trial"}`, left, py + headerH / 2 + 4);
    const nvpHeaderText = `NVP ${currentNVP}`;
    const nvpHeaderWidth = ctx.measureText(nvpHeaderText).width;
    ctx.fillStyle = color.text;
    ctx.fillText(nvpHeaderText, right - nvpHeaderWidth, py + headerH / 2 + 4);
    ctx.textAlign = "left";

    row("Straightness", currentStraightness > 0 ? formatValue(currentStraightness, 2) : "—");
    row(
      "Wiping",
      wipingVerdict
        ? `${wipingVerdict.toUpperCase()}${wiping.confidence ? ` (${wiping.confidence})` : ""}`.trim()
        : "—",
      true
    );
    if (wiping.warning) {
      ctx.font = `600 ${fsSmall} sans-serif`;
      ctx.fillStyle = "rgba(250,204,21,0.85)";
      ctx.fillText(String(wiping.warning).slice(0, 40), left, cy);
      cy += rowH;
    }
    row("Peak velocity", currentPeakElbowAngVel > 0 ? `${formatValue(currentPeakElbowAngVel, 0)} °/s` : "—", true);
    row("Movement time", currentMovementTime > 0 ? `${formatValue(currentMovementTime, 2)} s` : "—");
    row("Pause / stops", currentPauseTime > 0 || currentStops > 0 ? `${formatValue(currentPauseTime, 2)} s / ${currentStops}` : "—");
    row("Trunk ratio", currentTrunkRatio > 0 ? formatValue(currentTrunkRatio, 2) : "—");
    row("Shoulder elevation", currentShoulderElevation > 0 ? formatValue(currentShoulderElevation, 3) : "—");

    function miniChart(label, profile, colorStr) {
      if (!profile?.t?.length) return;
      const chartPad = 4 * dpr * panelScale;
      const cx = px + pad;
      const cyy = cy + chartPad;
      const cw2 = pw - pad * 2;
      const ch2 = chartH - chartPad * 2;
      ctx.fillStyle = "rgba(0,0,0,0.20)";
      ctx.fillRect(cx, cyy, cw2, ch2);
      const vals = profile.v;
      const minV = Math.min(...vals);
      const maxV = Math.max(1, Math.max(...vals));
      const range = maxV - minV || 1;
      ctx.beginPath();
      const endI = Math.min(idx, vals.length - 1);
      for (let i = 0; i <= endI; i++) {
        const v = vals[i];
        const x = cx + (i / (vals.length - 1)) * cw2;
        const y = cyy + ch2 - ((v - minV) / range) * ch2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = colorStr;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      const curX = cx + (idx / (vals.length - 1)) * cw2;
      ctx.strokeStyle = "rgba(255,255,255,0.6)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(curX, cyy);
      ctx.lineTo(curX, cyy + ch2);
      ctx.stroke();
      ctx.font = `600 ${fsSmall} sans-serif`;
      ctx.fillStyle = "rgba(255,255,255,0.55)";
      ctx.fillText(label, cx, cyy - 2);
      cy += chartH;
    }

    if (velocityProfile?.t?.length >= 2) {
      const chartPad = 5 * dpr * panelScale;
      const cx = px + pad;
      const cyy = cy + chartPad;
      const cw2 = pw - pad * 2;
      const ch2 = chartH - chartPad * 2;
      ctx.fillStyle = "rgba(0,0,0,0.25)";
      ctx.fillRect(cx, cyy, cw2, ch2);
      const vals = velocityProfile.v;
      const maxV = Math.max(1, ...vals);
      ctx.beginPath();
      const endI = Math.min(idx, vals.length - 1);
      for (let i = 0; i <= endI; i++) {
        const v = vals[i];
        const x = cx + (i / (vals.length - 1)) * cw2;
        const y = cyy + ch2 - (v / maxV) * ch2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = color.main;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      const curX = cx + (idx / (vals.length - 1)) * cw2;
      ctx.strokeStyle = "rgba(255,255,255,0.8)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(curX, cyy);
      ctx.lineTo(curX, cyy + ch2);
      ctx.stroke();
      cy += chartH;
    }

    miniChart("Elbow angle", overlayData?.elbow_angle_profile, "#7dd3fc");
    miniChart("Trunk X", overlayData?.trunk_x_profile, "#facc15");

    const gw = Math.min(170 * window.devicePixelRatio, cw * 0.42);
    const gh = 8 * window.devicePixelRatio;
    const gx = panelOnRight ? pad : cw - gw - pad;
    const gy = ch - 34 * window.devicePixelRatio;
    const speedPct = peakV > 0 ? Math.min(1, speed / peakV) : 0;

    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,0.35)";
    ctx.shadowBlur = 10;
    ctx.fillStyle = "rgba(14,17,32,0.68)";
    ctx.strokeStyle = "rgba(255,255,255,0.14)";
    ctx.lineWidth = 1;
    const gpx = gx - 6, gpy = gy - 16, gpw = gw + 12, gph = gh + 22;
    ctx.beginPath();
    ctx.moveTo(gpx + 8, gpy);
    ctx.lineTo(gpx + gpw - 8, gpy);
    ctx.quadraticCurveTo(gpx + gpw, gpy, gpx + gpw, gpy + 8);
    ctx.lineTo(gpx + gpw, gpy + gph - 8);
    ctx.quadraticCurveTo(gpx + gpw, gpy + gph, gpx + gpw - 8, gpy + gph);
    ctx.lineTo(gpx + 8, gpy + gph);
    ctx.quadraticCurveTo(gpx, gpy + gph, gpx, gpy + gph - 8);
    ctx.lineTo(gpx, gpy + 8);
    ctx.quadraticCurveTo(gpx, gpy, gpx + 8, gpy);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    ctx.fillStyle = "rgba(255,255,255,0.18)";
    ctx.fillRect(gx, gy, gw, gh);
    const grad = ctx.createLinearGradient(gx, 0, gx + gw, 0);
    grad.addColorStop(0, "rgba(16,185,129,0.95)");
    grad.addColorStop(0.5, "rgba(250,204,21,0.95)");
    grad.addColorStop(1, "rgba(244,63,94,0.95)");
    ctx.fillStyle = grad;
    ctx.fillRect(gx, gy, gw * speedPct, gh);
    ctx.fillStyle = "#fff";
    ctx.font = `bold ${fsSmall} sans-serif`;
    ctx.fillText(`Speed ${Math.round(speed)} °/s`, gx, gy - 4);

  }, [frames, fps, win, peakV, handPeakV, startPalm, endPalm, velocityProfile, phaseColor, phaseLabel, getFrameIndex, peakFrames, getElbowAngVel, overlayData?.elbow_angle_profile, overlayData?.trunk_x_profile, overlayData?.wiping]);

  const drawRecordingFrame = useCallback(() => {
    const video = videoRef.current;
    const recCanvas = recCanvasRef.current;
    const visCanvas = canvasRef.current;
    if (!video || !recCanvas || !visCanvas) return;
    const ctx = recCanvas.getContext("2d");
    if (recCanvas.width !== video.videoWidth || recCanvas.height !== video.videoHeight) {
      recCanvas.width = video.videoWidth || 640;
      recCanvas.height = video.videoHeight || 480;
    }
    ctx.drawImage(video, 0, 0, recCanvas.width, recCanvas.height);
    ctx.drawImage(visCanvas, 0, 0, recCanvas.width, recCanvas.height);
  }, []);

  const getSupportedMimeType = () => {
    const types = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"];
    return types.find((t) => MediaRecorder.isTypeSupported(t)) || "video/webm";
  };

  const startRecording = useCallback(async () => {
    const video = videoRef.current;
    const recCanvas = recCanvasRef.current;
    if (!video || !recCanvas) return;
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") return;
    const stream = recCanvas.captureStream(30);
    const mimeType = getSupportedMimeType();
    const recorder = new MediaRecorder(stream, { mimeType });
    mediaRecorderRef.current = recorder;
    recordedChunksRef.current = [];
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunksRef.current.push(e.data);
    };
    recorder.onstop = () => {
      const blob = new Blob(recordedChunksRef.current, { type: "video/webm" });
      const url = URL.createObjectURL(blob);
      setDownloadUrl(url);
      onDownloadReady?.(url);
      setRecording(false);
    };
    recorder.start(100);
    setRecording(true);
    video.playbackRate = 1;
    video.currentTime = 0;
    await video.play();
  }, [onDownloadReady]);

  const tryAutoRender = useCallback(() => {
    const video = videoRef.current;
    if (
      !autoRender ||
      autoRenderStartedRef.current ||
      mediaRecorderRef.current?.state === "recording" ||
      downloadUrl ||
      !video ||
      video.readyState < 1 ||
      !frames.length
    ) {
      return;
    }
    autoRenderStartedRef.current = true;
    startRecording();
  }, [autoRender, downloadUrl, frames.length, startRecording]);

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    const onLoadedMetadata = () => {
      const vw = video.videoWidth || 1;
      const vh = video.videoHeight || 1;
      setVideoAspect(vw / vh);
      drawOverlay();
      tryAutoRender();
    };
    const onTimeUpdate = () => {
      const pct = video.duration ? (video.currentTime / video.duration) * 100 : 0;
      setProgress(pct);
      if (recording) setRenderProgress(pct);
      drawOverlay();
    };
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onEnded = () => {
      setIsPlaying(false);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop();
      }
      onEnded?.();
    };
    const onResize = () => drawOverlay();

    video.addEventListener("loadedmetadata", onLoadedMetadata);
    video.addEventListener("timeupdate", onTimeUpdate);
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    video.addEventListener("ended", onEnded);
    window.addEventListener("resize", onResize);

    const loop = () => {
      drawOverlay();
      if (recording) drawRecordingFrame();
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      video.removeEventListener("loadedmetadata", onLoadedMetadata);
      video.removeEventListener("timeupdate", onTimeUpdate);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
      video.removeEventListener("ended", onEnded);
      window.removeEventListener("resize", onResize);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [videoUrl, drawOverlay, drawRecordingFrame, recording, onEnded, tryAutoRender]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !autoPlay) return;
    video.muted = true;
    video.play().catch(() => {});
  }, [videoUrl, autoPlay]);

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) video.play();
    else video.pause();
  };

  const handleSeek = (e) => {
    const video = videoRef.current;
    if (!video || !video.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    video.currentTime = pct * video.duration;
  };

  const requestFullscreen = () => {
    const container = containerRef.current;
    if (!container) return;
    if (container.requestFullscreen) container.requestFullscreen();
    else if (container.webkitRequestFullscreen) container.webkitRequestFullscreen();
  };

  const toggleSpeed = () => {
    const speeds = [0.5, 1, 1.5, 2];
    const idx = speeds.indexOf(playbackRate);
    const next = speeds[(idx + 1) % speeds.length];
    setPlaybackRate(next);
  };

  const stepFrame = (dir) => {
    const video = videoRef.current;
    if (!video || !video.duration) return;
    video.pause();
    const step = dir / fps;
    video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + step));
  };

  const formatTime = (s) => {
    if (!s || isNaN(s)) return "0:00";
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  useEffect(() => {
    autoRenderStartedRef.current = false;
    setDownloadUrl(null);
    setRenderProgress(0);
  }, [videoUrl]);

  useEffect(() => {
    tryAutoRender();
  }, [tryAutoRender]);

  useEffect(() => {
    const video = videoRef.current;
    if (video) video.playbackRate = playbackRate;
  }, [playbackRate]);

  return (
    <div ref={containerRef} className="relative w-full rounded-lg bg-black overflow-hidden group flex justify-center items-center">
      <div className="relative inline-block max-w-full">
        <video
          ref={videoRef}
          src={videoUrl}
          playsInline
          muted
          className="max-w-full max-h-[80vh] h-auto object-contain bg-black block"
          onError={(e) => onError?.(e?.target?.error || new Error("Video failed to load"))}
          onClick={togglePlay}
        />
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
        />
      </div>
      <canvas ref={recCanvasRef} className="hidden" />
      <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
        <div className="glass-float rounded-xl p-2 flex flex-col gap-1.5 pointer-events-auto backdrop-blur-md bg-white/[0.06] border border-white/10">
          <div className="flex items-center gap-1 flex-wrap">
            <button
              type="button"
              onClick={togglePlay}
              className="p-1 rounded-md text-white/80 hover:text-white hover:bg-white/10 transition"
              title={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <button
              type="button"
              onClick={() => stepFrame(-1)}
              className="p-1 rounded-md text-white/70 hover:text-white hover:bg-white/10 transition"
              title="Previous frame"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => stepFrame(1)}
              className="p-1 rounded-md text-white/70 hover:text-white hover:bg-white/10 transition"
              title="Next frame"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>

            <span className="text-[10px] text-white/70 font-mono tabular-nums whitespace-nowrap mx-1">
              {formatTime(videoRef.current?.currentTime)} / {formatTime(videoRef.current?.duration)}
            </span>

            <div className="flex-1 min-w-0" />

            <div className="flex items-center gap-1 flex-shrink-0">
              <button
                type="button"
                onClick={toggleSpeed}
                className="text-[10px] font-semibold text-white/80 px-1.5 py-1 rounded-md bg-white/10 hover:bg-white/20 transition min-w-[2rem]"
                title="Playback speed"
              >
                {playbackRate}x
              </button>
              <button
                type="button"
                onClick={requestFullscreen}
                className="p-1 rounded-md text-white/70 hover:text-white hover:bg-white/10 transition"
                title="Fullscreen"
              >
                <Maximize className="w-3.5 h-3.5" />
              </button>

              {recording ? (
                <div className="flex items-center justify-center gap-1 px-2 py-1 rounded-md bg-white/10 text-[10px] text-white/70 font-mono tabular-nums min-w-[4rem] whitespace-nowrap">
                  <div className="w-3 h-3 border-2 border-white/30 border-t-white/80 rounded-full animate-spin" />
                  <span>{Math.round(renderProgress)}%</span>
                </div>
              ) : downloadUrl ? (
                <a
                  href={downloadUrl}
                  download={`${phaseLabel || "validation"}_overlay.webm`}
                  className="flex items-center justify-center gap-1 px-2 py-1 rounded-md bg-emerald-500/20 text-emerald-300 text-[10px] font-semibold min-w-[4rem] whitespace-nowrap hover:bg-emerald-500/30 hover:text-emerald-200 transition"
                  title="Download rendered video"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download</span>
                </a>
              ) : null}
            </div>
          </div>

          <div
            className="h-2 bg-white/20 rounded-full cursor-pointer pointer-events-auto relative"
            onClick={handleSeek}
            title="Seek"
          >
            <div
              className="absolute top-0 left-0 h-full bg-sky-400 rounded-full"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default ValidationOverlayPlayer;
