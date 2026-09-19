/**
 * Hierarchical task comparison: completion first, then smoothness on a shared window.
 * Incomplete Pre vs complete Post must not treat extra full-task NVP as worsening.
 */
import { clinicalTaskById } from "./clinicalTasks";
import {
  countNvpPeaksFromRest,
  countNvpPeaksInWindow,
  nvpPeakIndicesInWindow,
  overlayMovementWindow,
  restPathStartIdx,
} from "./validationPanelMetrics";

export const FULL_TASK_SMOOTHNESS_KEYS = ["nvp_full_task"];
export const REACH_WINDOW_SMOOTHNESS_KEYS = [
  "nvp",
  "nvp_reach",
  "nvp_drink",
  "nvp_transport",
  "nvp_return",
  "nvp_total",
  "straightness",
  "straightness_reach",
  "pause_time_sec",
  "pause_time_sec_reach",
  "number_of_stops",
  "number_of_stops_reach",
];

function num(v) {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function isDrinkOrBrushTask(result) {
  const task = String(result?.clinical_task || result?.clinicalTask || "").trim().toLowerCase();
  if (task.includes("drink") || task.includes("brush")) return true;
  const ids = listTaskPhases(result).map((p) => String(p.id || ""));
  if (ids.some((id) => id.startsWith("transport_") || id === "return")) return true;
  if (num(result?.drink_lift_height_cm) != null || num(result?.drink_lift_height_sw) != null) return true;
  if (num(result?.nvp_drink) != null || num(result?.sip_bout_count) != null) return true;
  return false;
}

function expectedPhaseIds(result) {
  const fromResult = result?.expected_phase_ids;
  if (Array.isArray(fromResult) && fromResult.length) return fromResult;
  const task = String(result?.clinical_task || result?.clinicalTask || "").trim();
  if (task) {
    const spec = clinicalTaskById(task);
    if (spec?.phaseIds?.length) return spec.phaseIds;
  }
  const ids = listTaskPhases(result).map((p) => p.id).filter(Boolean);
  if (ids.includes("transport_drink")) return ["reach_grasp", "transport_drink", "return"];
  if (ids.includes("transport_brush")) return ["reach_grasp", "transport_brush", "return"];
  if (isDrinkOrBrushTask(result)) return ["reach_grasp", "transport_drink", "return"];
  return ["reach_grasp"];
}

function overlaySource(result, overlayData) {
  if (overlayData?.frames?.length) return overlayData;
  if (result?.frames?.length) return result;
  if (result?.overlay?.frames?.length) return result.overlay;
  return null;
}

function finiteMedian(values) {
  const v = values.filter((n) => Number.isFinite(n)).slice().sort((a, b) => a - b);
  if (!v.length) return null;
  return v[Math.floor(v.length / 2)];
}

/** Reach → lift (cup to mouth) → return from overlay palm path. Image y grows downward. */
export function inferPalmTaskShape(overlayData) {
  const frames = overlayData?.frames;
  if (!Array.isArray(frames) || frames.length < 8) return null;
  const xs = [];
  const ys = [];
  frames.forEach((f) => {
    const p = f?.palm || f?.wrist;
    xs.push(Array.isArray(p) && Number.isFinite(Number(p[0])) ? Number(p[0]) : null);
    ys.push(Array.isArray(p) && Number.isFinite(Number(p[1])) ? Number(p[1]) : null);
  });
  const valid = ys.filter((v) => v != null).length;
  if (valid < 8) return null;

  let lastY = finiteMedian(ys) ?? 0.7;
  let lastX = finiteMedian(xs) ?? 0.5;
  const filledY = ys.map((v) => {
    if (v != null) lastY = v;
    return lastY;
  });
  const filledX = xs.map((v) => {
    if (v != null) lastX = v;
    return lastX;
  });

  const n = filledY.length;
  const head = filledY.slice(0, Math.max(3, Math.floor(n / 8)));
  const base = finiteMedian(head);
  if (base == null) return null;
  let minY = base;
  let minI = 0;
  for (let i = 0; i < n; i += 1) {
    if (filledY[i] < minY) {
      minY = filledY[i];
      minI = i;
    }
  }
  const lift = base - minY;
  const tail = filledY.slice(minI);
  const tailRest = finiteMedian(tail.slice(-Math.max(3, Math.floor(tail.length / 5)))) ?? minY;
  const recovery = tailRest - minY;
  let path = 0;
  for (let i = 1; i < n; i += 1) {
    path += Math.hypot(filledX[i] - filledX[i - 1], filledY[i] - filledY[i - 1]);
  }
  const reachPath = (() => {
    let p = 0;
    const end = Math.max(2, minI);
    for (let i = 1; i < end; i += 1) {
      p += Math.hypot(filledX[i] - filledX[i - 1], filledY[i] - filledY[i - 1]);
    }
    return p;
  })();

  return {
    lift,
    recovery,
    path,
    reachPath,
    peakIndex: minI,
    reach: reachPath >= 0.035 || minI >= 4,
    liftOk: lift >= 0.045,
    returnOk: lift >= 0.045 && recovery >= 0.32 * lift,
  };
}

function adlMetricEvidence(result) {
  const liftCm = num(result?.drink_lift_height_cm) ?? num(result?.lift_height_cm);
  const liftSw = num(result?.drink_lift_height_sw) ?? num(result?.lift_height_sw);
  const sip = num(result?.sip_bout_count);
  const nvpDrink = num(result?.nvp_drink) ?? num(result?.nvp_transport);
  const nvpReturn = num(result?.nvp_return);
  const phases = listTaskPhases(result).map((p) => String(p?.id || ""));
  const hasReturn = phases.includes("return") || nvpReturn != null;
  const hasTransport = phases.some((id) => id.startsWith("transport_")) || nvpDrink != null || (sip != null && sip >= 1);
  const hasLift = (liftCm != null && liftCm >= 1.5) || (liftSw != null && liftSw >= 0.05);
  const hasReach = phases.includes("reach_grasp") || num(result?.nvp_reach) != null || num(result?.nvp) != null;
  return {
    hasReach,
    hasTransport: hasTransport || hasLift,
    hasReturn,
    full: Boolean((hasReach || hasLift) && (hasTransport || hasLift) && hasReturn),
  };
}

/** Upgrade Incomplete → Complete when the clip clearly has reach, lift, and return. Never downgrade Complete. */
export function motionConfirmsAdlComplete(result, overlayData) {
  if (!isDrinkOrBrushTask(result) && expectedPhaseIds(result).length < 3) return false;
  const metrics = adlMetricEvidence(result);
  if (metrics.full) return true;
  const shape = inferPalmTaskShape(overlaySource(result, overlayData));
  if (shape?.reach && shape?.liftOk && shape?.returnOk) return true;
  if (metrics.hasLift && metrics.hasReturn) return true;
  if (shape?.liftOk && shape?.returnOk && (metrics.hasReach || shape.reach)) return true;
  return false;
}

export function listTaskPhases(result) {
  const phases = result?.task_phases;
  return Array.isArray(phases) ? phases : [];
}

export function findTaskPhase(result, phaseId = "reach_grasp") {
  return listTaskPhases(result).find((p) => p && p.id === phaseId) || null;
}

export function pickReachPhaseMetric(result, metricKey) {
  const alias = `${metricKey}_reach`;
  const fromTop = num(result?.[alias]);
  if (fromTop != null) return fromTop;
  const phase = findTaskPhase(result, "reach_grasp") || listTaskPhases(result)[0];
  const m = phase?.metrics;
  if (!m || typeof m !== "object") return null;
  return num(m[metricKey]);
}

export function pickPhaseMetric(result, phaseId, metricKey) {
  const phase = findTaskPhase(result, phaseId);
  const m = phase?.metrics;
  if (!m || typeof m !== "object") return null;
  return num(m[metricKey]);
}

export function pickTransportPhase(result) {
  return (
    findTaskPhase(result, "transport_drink")
    || findTaskPhase(result, "transport_brush")
    || listTaskPhases(result).find((p) => String(p?.id || "").startsWith("transport_"))
    || null
  );
}

function phaseFrameWindow(phase) {
  if (!phase || typeof phase !== "object") return null;
  const s = Number(
    phase.start_frame
    ?? phase.start_idx
    ?? phase.task_window?.start
    ?? phase.task_window?.start_idx,
  );
  const e = Number(
    phase.end_frame
    ?? phase.end_idx
    ?? phase.task_window?.end
    ?? phase.task_window?.end_idx,
  );
  if (!Number.isFinite(s) || !Number.isFinite(e)) return null;
  return { startIdx: Math.min(s, e), untilIdx: Math.max(s, e) };
}

function overlayPeakFrames(result, overlayData) {
  const src = overlaySource(result, overlayData);
  const peaks = src?.peak_frames;
  return Array.isArray(peaks) ? peaks : [];
}

function uniqueNvpCount(peakFrames, windows) {
  const seen = new Set();
  (windows || []).forEach((win) => {
    if (!win) return;
    nvpPeakIndicesInWindow(peakFrames, win.startIdx, win.untilIdx).forEach((pi) => {
      seen.add(Number(pi));
    });
  });
  return seen.size;
}

/** Recount NVP rows from the same peak_frames + phase windows the overlay uses. */
export function countTaskNvpFromPeaks(result, overlayData = null) {
  const peaks = overlayPeakFrames(result, overlayData);
  const reachPhase = findTaskPhase(result, "reach_grasp") || listTaskPhases(result)[0];
  const transport = pickTransportPhase(result);
  const ret = findTaskPhase(result, "return");
  const reachWin = phaseFrameWindow(reachPhase);
  const drinkWin = phaseFrameWindow(transport);
  const returnWin = phaseFrameWindow(ret);
  let fallbackReachWin = null;
  const src = overlaySource(result, overlayData);
  if (src?.frames?.length) {
    const { startIdx, endIdx } = overlayMovementWindow(src);
    const restIdx = restPathStartIdx(src);
    fallbackReachWin = { startIdx: Math.min(startIdx, restIdx), untilIdx: endIdx };
  }
  let reachCountWin = reachWin || (!drinkWin && !returnWin ? fallbackReachWin : null);
  if (reachCountWin && src?.frames?.length) {
    const restIdx = restPathStartIdx(src);
    reachCountWin = { ...reachCountWin, startIdx: Math.min(reachCountWin.startIdx, restIdx) };
  }
  const nvpReach = reachCountWin
    ? (src?.frames?.length
      ? countNvpPeaksFromRest(src, reachCountWin.untilIdx)
      : (peaks.length ? countNvpPeaksInWindow(peaks, reachCountWin.startIdx, reachCountWin.untilIdx) : null))
    : null;
  const nvpDrink = drinkWin && peaks.length
    ? countNvpPeaksInWindow(peaks, drinkWin.startIdx, drinkWin.untilIdx)
    : null;
  const nvpReturn = returnWin && peaks.length
    ? countNvpPeaksInWindow(peaks, returnWin.startIdx, returnWin.untilIdx)
    : null;
  const unionWins = [reachCountWin, drinkWin, returnWin].filter(Boolean);
  const nvpTotal = peaks.length && unionWins.length
    ? uniqueNvpCount(peaks, unionWins)
    : null;
  return {
    nvp_reach: nvpReach,
    nvp_drink: nvpDrink,
    nvp_return: nvpReturn,
    nvp_total: nvpTotal,
  };
}

function coalesceNvpTotal(fromPeaksTotal, parts, storedTotal) {
  const finite = parts.filter((v) => v != null && Number.isFinite(Number(v))).map((v) => Number(v));
  const maxPart = finite.length ? Math.max(...finite) : null;
  const stored = storedTotal != null && Number.isFinite(Number(storedTotal)) ? Number(storedTotal) : null;
  const peakTotal = fromPeaksTotal != null && Number.isFinite(Number(fromPeaksTotal)) ? Number(fromPeaksTotal) : null;
  if (peakTotal != null) return Math.max(peakTotal, maxPart ?? peakTotal);
  const candidates = [stored, maxPart].filter((v) => v != null);
  if (!candidates.length) return null;
  return Math.max(...candidates);
}

export function deriveTaskCompletion(result, overlayData = null) {
  if (!result || typeof result !== "object") {
    return {
      taskComplete: null,
      taskCompletionRatio: null,
      expectedPhaseIds: ["reach_grasp"],
      completedPhaseIds: [],
    };
  }
  const expected = expectedPhaseIds(result);
  const flagged = (() => {
    if (result.task_complete === true || result.task_complete === false) {
      const completed = Array.isArray(result.completed_phase_ids)
        ? result.completed_phase_ids
        : listTaskPhases(result).map((p) => p.id).filter(Boolean);
      const ratio = num(result.task_completion_ratio);
      return {
        taskComplete: Boolean(result.task_complete),
        taskCompletionRatio: ratio != null ? ratio : (expected.length ? completed.length / expected.length : null),
        expectedPhaseIds: expected,
        completedPhaseIds: completed,
      };
    }
    if (result.task_complete === 1 || result.task_complete === 0 || result.task_complete === "1" || result.task_complete === "0") {
      const completed = Array.isArray(result.completed_phase_ids)
        ? result.completed_phase_ids
        : listTaskPhases(result).map((p) => p.id).filter(Boolean);
      return {
        taskComplete: Number(result.task_complete) === 1,
        taskCompletionRatio: num(result.task_completion_ratio),
        expectedPhaseIds: expected,
        completedPhaseIds: completed,
      };
    }

    const phases = listTaskPhases(result);
    const completed = phases.map((p) => p.id).filter(Boolean);
    if (!phases.length && result.nvp == null && result.movement_time_sec == null) {
      return { taskComplete: null, taskCompletionRatio: null, expectedPhaseIds: expected, completedPhaseIds: [] };
    }
    const complete = expected.every((id) => completed.includes(id));
    const ratio = expected.length ? Math.min(1, completed.length / expected.length) : null;
    return {
      taskComplete: phases.length ? complete : (expected.length <= 1 ? true : false),
      taskCompletionRatio: ratio,
      expectedPhaseIds: expected,
      completedPhaseIds: completed,
    };
  })();

  if (flagged.taskComplete === true) return flagged;
  if (motionConfirmsAdlComplete(result, overlayData)) {
    return {
      taskComplete: true,
      taskCompletionRatio: 1,
      expectedPhaseIds: expected,
      completedPhaseIds: expected,
    };
  }
  return flagged;
}

/** 1 = complete, 0 = incomplete (SPSS-friendly). */
export function taskCompleteCode(result, overlayData = null) {
  const { taskComplete } = deriveTaskCompletion(result, overlayData);
  if (taskComplete == null) return null;
  return taskComplete ? 1 : 0;
}

export function enrichKinematicCompletion(result, overlayData = null) {
  const c = deriveTaskCompletion(result, overlayData);
  const graspDwell = num(result?.grasp_dwell_sec) ?? pickReachPhaseMetric(result, "grasp_dwell_sec");
  const functionalHold = num(result?.functional_hold_sec);
  const pauseTotal = num(result?.pause_time_sec_total);
  const transport = pickTransportPhase(result);
  const fromPeaks = countTaskNvpFromPeaks(result, overlayData);
  const nvpReach = fromPeaks.nvp_reach
    ?? num(result?.nvp_reach)
    ?? pickReachPhaseMetric(result, "nvp");
  const nvpTransport =
    fromPeaks.nvp_drink
    ?? num(result?.nvp_transport)
    ?? num(result?.nvp_drink)
    ?? num(transport?.metrics?.nvp);
  const nvpReturn = fromPeaks.nvp_return
    ?? num(result?.nvp_return)
    ?? pickPhaseMetric(result, "return", "nvp");
  const parts = [nvpReach, nvpTransport, nvpReturn].filter((v) => v != null);
  const nvpTotal = coalesceNvpTotal(fromPeaks.nvp_total, parts, num(result?.nvp_total));
  const liftCm =
    num(result?.drink_lift_height_cm)
    ?? num(result?.lift_height_cm)
    ?? num(transport?.metrics?.lift_height_cm);
  const liftSw =
    num(result?.drink_lift_height_sw)
    ?? num(result?.lift_height_sw)
    ?? num(transport?.metrics?.lift_height_sw);
  return {
    task_complete: c.taskComplete == null ? null : (c.taskComplete ? 1 : 0),
    task_completion_ratio: c.taskCompletionRatio == null ? null : Number(c.taskCompletionRatio),
    nvp_reach: nvpReach,
    nvp_drink: fromPeaks.nvp_drink ?? num(result?.nvp_drink) ?? nvpTransport,
    nvp_transport: nvpTransport,
    nvp_return: nvpReturn,
    nvp_total: nvpTotal,
    drink_lift_height_cm: liftCm,
    lift_height_cm: liftCm,
    drink_lift_height_sw: liftSw,
    lift_height_sw: liftSw,
    straightness_reach: pickReachPhaseMetric(result, "straightness"),
    pause_time_sec_reach: pickReachPhaseMetric(result, "pause_time_sec"),
    number_of_stops_reach: pickReachPhaseMetric(result, "number_of_stops"),
    sip_bout_count: num(result?.sip_bout_count),
    grasp_dwell_sec: graspDwell,
    functional_hold_sec: functionalHold,
    pause_time_sec_total: pauseTotal,
    nvp_full_task: num(result?.nvp_full_task) ?? nvpTotal,
    nvp: num(result?.nvp) ?? nvpReach,
  };
}

export function fullTaskSmoothnessComparable(kinematicsResults) {
  const pre = kinematicsResults?.pre;
  const post = kinematicsResults?.post;
  if (!pre || !post) return true;
  const a = deriveTaskCompletion(pre);
  const b = deriveTaskCompletion(post);
  if (a.taskComplete == null || b.taskComplete == null) return true;
  return a.taskComplete === b.taskComplete;
}

export function describeCompletionMismatch(kinematicsResults) {
  const pre = kinematicsResults?.pre;
  const post = kinematicsResults?.post;
  if (!pre || !post) return null;
  const a = deriveTaskCompletion(pre);
  const b = deriveTaskCompletion(post);
  if (a.taskComplete == null || b.taskComplete == null) return null;
  if (a.taskComplete === b.taskComplete) return null;
  if (!a.taskComplete && b.taskComplete) {
    return "Pre did not complete the full task; Post did. Compare reach-window NVP/pause (extra sips are not counted there). Full-task NVP (incl. sips) is exploratory only.";
  }
  if (a.taskComplete && !b.taskComplete) {
    return "Post did not complete the full task; Pre did. Compare reach-window NVP/pause — not full-task NVP with sips.";
  }
  return "Task completion differs between Pre and Post — use reach-window NVP/pause (sips excluded).";
}
