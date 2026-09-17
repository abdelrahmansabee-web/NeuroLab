/**
 * Video-derived WMFT-4 inference from kinematic analysis (Pre/Post + optional baseline).
 * Labels outputs as vWMFT-4 — manual WMFT administration remains the clinical gold standard.
 */

import { pickKinField } from "./analysisPlan";
import { clinicalTaskById } from "./clinicalTasks";
import { getMovementProfile } from "./movementProfile";

const WMFT_INFERENCE_SPECS = {
  1: {
    title: "Hand to Table",
    phasePriority: ["return", "reach_grasp"],
    preferTasks: ["reach_grasp_drink_return", "reach_grasp_brush_return", "study_reach_grasp"],
  },
  2: {
    title: "Hand to Box",
    phasePriority: ["reach_grasp"],
    preferTasks: ["study_reach_grasp", "reach_grasp_drink_return", "reach_grasp_brush_return"],
  },
  3: {
    title: "Extend Elbow",
    phasePriority: ["reach_grasp"],
    preferTasks: ["study_reach_grasp", "reach_grasp_drink_return", "reach_grasp_brush_return"],
  },
  4: {
    title: "Lift Can",
    phasePriority: ["transport_drink", "transport_brush", "reach_grasp"],
    preferTasks: ["reach_grasp_drink_return", "reach_grasp_brush_return", "study_reach_grasp"],
  },
};

const ITEM_METRIC_KEYS = {
  1: ["movement_quality_index", "straightness", "trunk_ratio", "number_of_stops"],
  2: ["pinch_grasp_quality_index", "fine_motor_quality_index", "movement_quality_index"],
  3: ["elbow_rom_deg", "peak_elbow_ang_vel_deg_s"],
  4: ["pinch_grasp_quality_index", "shoulder_abduction_quality_index", "shoulder_elevation_palm_ratio"],
};

const PHASE_LABELS = {
  reach_grasp: "Reach & grasp",
  transport_drink: "Transport (drink)",
  transport_brush: "Transport (brush)",
  return: "Return to rest",
};

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function num(v) {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function round(v, d = 2) {
  if (v == null) return null;
  const f = 10 ** d;
  return Math.round(v * f) / f;
}

function avg(...vals) {
  const xs = vals.filter((v) => v != null);
  if (!xs.length) return null;
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function collectMetrics(kinResult, tp) {
  const m = {};
  if (tp?.metrics && typeof tp.metrics === "object") Object.assign(m, tp.metrics);
  if (tp?.movement_profile && typeof tp.movement_profile === "object") Object.assign(m, tp.movement_profile);

  if (!tp) {
    const profile = getMovementProfile(kinResult);
    if (profile && typeof profile === "object") Object.assign(m, profile);
  }

  const globalProfile = getMovementProfile(kinResult);
  const globalOnlyKeys = [
    "nvp",
    "straightness",
    "pause_time_sec",
    "number_of_stops",
    "trunk_ratio",
    "compensation_index",
    "tremor_index",
  ];
  if (tp && globalProfile) {
    for (const k of globalOnlyKeys) {
      if (m[k] == null && globalProfile[k] != null) m[k] = globalProfile[k];
    }
  }

  for (const src of [kinResult?.overlay_metrics, kinResult?.validation_summary]) {
    if (!src) continue;
    for (const k of [
      ...Object.values(ITEM_METRIC_KEYS).flat(),
      "movement_time_sec",
      "hl_index_coverage_pct",
      "hl_finger_track_pct",
      "mean_elbow_ang_vel_deg_s",
      "shoulder_abduction_rom_deg",
      "peak_shoulder_abduction_vel_deg_s",
    ]) {
      const v = pickKinField(src, k);
      if (v != null && m[k] == null) m[k] = v;
    }
  }
  return m;
}

function phaseDurationSec(block) {
  if (!block) return null;
  return (
    num(block.duration_sec) ??
    num(block.metrics?.movement_time_sec) ??
    num(block.movement_profile?.movement_time_sec)
  );
}

/** WMFT item time — never reuse one bout duration for items 2–4. */
function resolveWmftItemTime(itemId, block, m) {
  const base = phaseDurationSec(block);
  if (base == null || base <= 0) return null;

  const phaseId = block.phaseId;

  if (itemId === 1) {
    return round(base, 2);
  }

  if (itemId === 2) {
    if (phaseId === "return") return round(base * 0.88, 2);
    return round(base, 2);
  }

  if (itemId === 3) {
    const rom = num(m.elbow_rom_deg);
    const meanVel = num(m.mean_elbow_ang_vel_deg_s);
    const peakVel = num(m.peak_elbow_ang_vel_deg_s);
    if (rom != null && meanVel != null && meanVel > 8) {
      return round(clamp(rom / meanVel, 0.85, base * 0.9), 2);
    }
    if (rom != null && peakVel != null && peakVel > 12) {
      return round(clamp(rom / (peakVel * 0.62), 0.85, base * 0.88), 2);
    }
    const frac = phaseId === "reach_grasp" ? 0.36 : 0.44;
    return round(base * frac, 2);
  }

  if (itemId === 4) {
    if (phaseId === "transport_drink" || phaseId === "transport_brush") {
      return round(base, 2);
    }
    const abRom = num(m.shoulder_abduction_rom_deg);
    const peakAb = num(m.peak_shoulder_abduction_vel_deg_s);
    if (abRom != null && peakAb != null && peakAb > 4) {
      return round(clamp(abRom / peakAb, 1.0, 10.5), 2);
    }
    const meanAb = num(m.shoulder_abduction_mean_deg);
    if (meanAb != null && peakAb != null && peakAb > 4) {
      return round(clamp(meanAb / (peakAb * 0.55), 1.0, 10.5), 2);
    }
    return round(base * 0.4, 2);
  }

  return round(base, 2);
}

function buildPhaseLookup(kinResult) {
  const lookup = {};
  if (!kinResult) return lookup;

  const primaryTime =
    pickKinField(kinResult, "movement_time_sec") ??
    num(kinResult.movement_time_sec);

  lookup._primary = {
    id: "reach_grasp",
    label: PHASE_LABELS.reach_grasp,
    metrics: collectMetrics(kinResult, null),
    duration_sec: primaryTime,
    sourceTask: kinResult.clinical_task || "study_reach_grasp",
  };

  for (const tp of kinResult.task_phases || []) {
    if (!tp?.id) continue;
    const phaseMetrics = collectMetrics(kinResult, tp);
    lookup[tp.id] = {
      id: tp.id,
      label: tp.label || PHASE_LABELS[tp.id] || tp.id,
      metrics: phaseMetrics,
      duration_sec:
        num(tp.duration_sec) ??
        num(tp.metrics?.movement_time_sec) ??
        num(phaseMetrics.movement_time_sec),
      sourceTask: kinResult.clinical_task || "study_reach_grasp",
    };
  }
  return lookup;
}

function pickPhaseBlock(lookup, priorityIds) {
  for (const id of priorityIds) {
    if (lookup[id]) return { ...lookup[id], phaseId: id };
  }
  if (lookup._primary) return { ...lookup._primary, phaseId: "reach_grasp" };
  return null;
}

function computeSmoothness(m) {
  const nvp = num(m.nvp);
  const stops = num(m.number_of_stops) ?? 0;
  const pause = num(m.pause_time_sec) ?? 0;
  const tremorIdx = num(m.tremor_index);
  let score = 68;
  if (nvp != null) score += clamp(nvp * 2.5, 0, 18);
  score -= clamp(stops * 7, 0, 28);
  score -= clamp(pause * 3.5, 0, 22);
  const straight = num(m.straightness);
  if (straight != null) score += clamp(straight * 12, 0, 12);
  if (tremorIdx != null) score = score * 0.45 + tremorIdx * 0.55;
  return clamp(score, 0, 100);
}

function computeCompensation(m) {
  const comp = num(m.compensation_index);
  const trunk = num(m.trunk_ratio);
  const head = num(m.head_forward_flexion_compensation_index);
  let penalty = 0;
  if (comp != null) penalty += comp * 45;
  if (trunk != null) penalty += trunk * 28;
  if (head != null) penalty += head * 18;
  return clamp(100 - penalty, 0, 100);
}

function shoulderElevScore(m) {
  const ratio = num(m.shoulder_elevation_palm_ratio);
  if (ratio != null) return clamp(100 - ratio * 220, 0, 100);
  const abq = num(m.shoulder_abduction_quality_index);
  if (abq != null) return abq;
  return null;
}

function computeTaskSpecific(itemId, m, baselineM) {
  switch (itemId) {
    case 1:
      return (
        avg(
          num(m.shoulder_flexion_quality_index),
          num(m.movement_quality_index),
          num(m.straightness) != null ? num(m.straightness) * 100 : null
        ) ?? 58
      );
    case 2: {
      const pinch = num(m.pinch_grasp_quality_index);
      const fine = num(m.fine_motor_quality_index);
      const hlCov = num(m.hl_index_coverage_pct);
      let base = avg(pinch, fine, num(m.movement_quality_index)) ?? 52;
      if (hlCov != null && hlCov < 35) base *= 0.85;
      return clamp(base, 0, 100);
    }
    case 3: {
      const rom = num(m.elbow_rom_deg);
      const baseRom = num(baselineM?.elbow_rom_deg);
      if (rom != null && baseRom != null && baseRom > 20) {
        return clamp((rom / baseRom) * 100, 0, 100);
      }
      if (rom != null) return clamp((rom / 135) * 100, 0, 100);
      const peak = num(m.peak_elbow_ang_vel_deg_s);
      if (peak != null) return clamp(peak / 2.2, 0, 100);
      const ext = num(m.elbow_extension_at_peak_reach_deg);
      if (ext != null) return clamp((ext / 150) * 100, 0, 100);
      return 48;
    }
    case 4: {
      return (
        avg(
          num(m.pinch_grasp_quality_index),
          num(m.shoulder_abduction_quality_index),
          num(m.movement_quality_index),
          shoulderElevScore(m)
        ) ?? 54
      );
    }
    default:
      return 50;
  }
}

function computeConfidence(itemId, m, block, kinResult, timeMeta) {
  let score = 0.38;
  const hasTime = timeMeta?.time != null && timeMeta.time > 0;
  if (hasTime) score += 0.12;

  const spec = WMFT_INFERENCE_SPECS[itemId];
  const task = kinResult?.clinical_task || "study_reach_grasp";
  const taskRank = spec.preferTasks.indexOf(task);
  if (taskRank === 0) score += 0.16;
  else if (taskRank === 1) score += 0.09;
  else if (taskRank >= 0) score += 0.04;

  if (spec.phasePriority[0] === block.phaseId) score += 0.12;
  else if (spec.phasePriority.includes(block.phaseId)) score += 0.06;
  else score -= 0.08;

  const keys = ITEM_METRIC_KEYS[itemId] || [];
  const present = keys.filter((k) => num(m[k]) != null).length;
  score += (present / Math.max(keys.length, 1)) * 0.16;

  if ((kinResult?.task_phases || []).length > 0) score += 0.03;
  if (timeMeta?.estimated) score -= 0.14;
  if (timeMeta?.deduped) score -= 0.1;
  return clamp(score, 0, 0.92);
}

function scoreToRating(itemScore, confidence) {
  if (confidence < 0.32) return { rating: null, capped: true };
  let r = 0;
  if (itemScore >= 86) r = 5;
  else if (itemScore >= 72) r = 4;
  else if (itemScore >= 56) r = 3;
  else if (itemScore >= 38) r = 2;
  else if (itemScore >= 14) r = 1;
  else r = 0;
  const capped = confidence < 0.58 && r > 3;
  if (capped) r = 3;
  return { rating: r, capped };
}

function formatSource(block, kinResult, sessionPhase) {
  const taskId = block.sourceTask || kinResult?.clinical_task || "study_reach_grasp";
  const taskLabel =
    kinResult?.clinical_task_label ||
    clinicalTaskById(taskId).label ||
    taskId;
  const phaseLabel = block.label || PHASE_LABELS[block.phaseId] || block.phaseId;
  const ph = sessionPhase === "post" ? "Post" : "Pre";
  return `Item ← ${phaseLabel} · ${taskLabel} (${ph})`;
}

function inferItem(itemId, kinResult, baselineResult, sessionPhase) {
  const spec = WMFT_INFERENCE_SPECS[itemId];
  if (!spec || !kinResult) return null;

  const lookup = buildPhaseLookup(kinResult);
  const block = pickPhaseBlock(lookup, spec.phasePriority);
  if (!block) return null;

  const m = { ...block.metrics };
  const baselineBlock = pickPhaseBlock(buildPhaseLookup(baselineResult), spec.phasePriority);
  const baselineM = baselineBlock?.metrics || {};

  const rawPhaseTime = phaseDurationSec(block);
  let time = resolveWmftItemTime(itemId, block, m);
  let timeEstimated = time != null && rawPhaseTime != null && Math.abs(time - rawPhaseTime) > 0.08;
  if (itemId === 4 && block.phaseId === "reach_grasp") timeEstimated = true;
  if (itemId === 3 && block.phaseId === "reach_grasp") timeEstimated = true;
  if (time == null || time <= 0) return null;

  const smoothness = computeSmoothness(m);
  const quality = num(m.movement_quality_index) ?? smoothness;
  const compensation = computeCompensation(m);
  const taskSpec = computeTaskSpecific(itemId, m, baselineM);
  const itemScore = 0.3 * smoothness + 0.25 * quality + 0.2 * compensation + 0.25 * taskSpec;
  const timeMeta = { time, estimated: timeEstimated, deduped: false };
  const confidence = computeConfidence(itemId, m, block, kinResult, timeMeta);
  const { rating, capped } = scoreToRating(itemScore, confidence);

  return {
    time: round(time, 2),
    rating,
    confidence: round(confidence, 2),
    capped,
    source: formatSource(block, kinResult, sessionPhase),
    itemScore: round(itemScore, 1),
    phaseId: block.phaseId,
    clinicalTask: block.sourceTask,
    _timeEstimated: timeEstimated,
  };
}

function harmonizeWmftTimesForPhase(items, ph) {
  const t2 = items[2]?.[ph]?.time;
  const t3 = items[3]?.[ph]?.time;
  const t4 = items[4]?.[ph]?.time;
  if (t2 != null && t3 != null && Math.abs(t2 - t3) < 0.06 && items[3]?.[ph]) {
    items[3][ph] = {
      ...items[3][ph],
      time: round(t2 * 0.38, 2),
      _timeEstimated: true,
      confidence: Math.min(items[3][ph].confidence ?? 0.9, 0.74),
      source: `${items[3][ph].source || ""} · elbow subset`.trim(),
    };
  }
  if (t4 != null && t2 != null && Math.abs(t4 - t2) < 0.06 && items[4]?.[ph]?.phaseId === "reach_grasp") {
    items[4][ph] = {
      ...items[4][ph],
      time: round(t2 * 0.41, 2),
      _timeEstimated: true,
      confidence: Math.min(items[4][ph].confidence ?? 0.9, 0.68),
      source: `${items[4][ph].source || ""} · lift estimate`.trim(),
    };
  } else if (t4 != null && t3 != null && Math.abs(t4 - t3) < 0.06 && items[4]?.[ph]) {
    items[4][ph] = {
      ...items[4][ph],
      time: round(Math.max(t3 * 1.08, t4 * 0.95), 2),
      _timeEstimated: true,
      confidence: Math.min(items[4][ph].confidence ?? 0.9, 0.7),
    };
  }
}

/** Infer WMFT-4 time + rating for Pre/Post from kinematic analysis results. */
export function inferWmftFromKinematics(kinResults, { baselineKey = "baseline" } = {}) {
  const baseline = kinResults?.[baselineKey];
  const out = { items: {}, warnings: [], filledCount: 0 };

  for (const itemId of [1, 2, 3, 4]) {
    out.items[itemId] = { pre: null, post: null };
    for (const ph of ["pre", "post"]) {
      const kr = kinResults?.[ph];
      if (!kr) {
        out.warnings.push(`WMFT ${itemId} ${ph}: no kinematic analysis`);
        continue;
      }
      const inf = inferItem(itemId, kr, baseline, ph);
      if (inf && inf.rating != null) {
        out.items[itemId][ph] = inf;
        out.filledCount += 1;
      } else {
        out.warnings.push(`WMFT ${itemId} ${ph}: insufficient phase/metrics`);
      }
    }
  }
  for (const ph of ["pre", "post"]) {
    harmonizeWmftTimesForPhase(out.items, ph);
  }
  return out;
}

/** Merge inferred values into wmft form state; skips occupied cells unless overwrite. */
export function applyWmftInference(currentWmft, inference, { overwrite = false } = {}) {
  const next = { ...(currentWmft || {}) };
  let applied = 0;

  for (const id of [1, 2, 3, 4]) {
    const phases = inference.items[id];
    if (!phases) continue;
    next[id] = { ...(next[id] || {}) };

    for (const ph of ["pre", "post"]) {
      const inf = phases[ph];
      if (!inf || inf.rating == null) continue;
      const existing = next[id][ph] || {};
      const hasManual =
        (existing.time != null && String(existing.time).trim() !== "") ||
        (existing.rating != null && String(existing.rating).trim() !== "");
      if (!overwrite && hasManual && !existing._inferred) continue;

      next[id][ph] = {
        ...existing,
        time: String(inf.time),
        rating: inf.rating,
        _inferred: true,
        _source: inf.source,
        _confidence: inf.confidence,
        _itemScore: inf.itemScore,
        _capped: inf.capped,
        _timeEstimated: inf._timeEstimated,
      };
      applied += 1;
    }
  }

  next._inferenceMeta = {
    at: new Date().toISOString(),
    videoDerived: true,
    label: "vWMFT-4 (video-derived)",
    warnings: inference.warnings,
    applied,
  };
  return next;
}

export { WMFT_INFERENCE_SPECS };
