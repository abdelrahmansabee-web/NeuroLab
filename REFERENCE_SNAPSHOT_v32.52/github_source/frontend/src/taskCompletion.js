/**
 * Hierarchical task comparison: completion first, then smoothness on a shared window.
 * Incomplete Pre vs complete Post must not treat extra full-task NVP as worsening.
 */
import { clinicalTaskById } from "./clinicalTasks";

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
  return ["reach_grasp"];
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

export function deriveTaskCompletion(result) {
  if (!result || typeof result !== "object") {
    return {
      taskComplete: null,
      taskCompletionRatio: null,
      expectedPhaseIds: ["reach_grasp"],
      completedPhaseIds: [],
    };
  }
  if (result.task_complete === true || result.task_complete === false) {
    const expected = expectedPhaseIds(result);
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
    const expected = expectedPhaseIds(result);
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

  const expected = expectedPhaseIds(result);
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
}

/** 1 = complete, 0 = incomplete (SPSS-friendly). */
export function taskCompleteCode(result) {
  const { taskComplete } = deriveTaskCompletion(result);
  if (taskComplete == null) return null;
  return taskComplete ? 1 : 0;
}

export function enrichKinematicCompletion(result) {
  const c = deriveTaskCompletion(result);
  const graspDwell = num(result?.grasp_dwell_sec) ?? pickReachPhaseMetric(result, "grasp_dwell_sec");
  const functionalHold = num(result?.functional_hold_sec);
  const pauseTotal = num(result?.pause_time_sec_total);
  const transport = pickTransportPhase(result);
  const nvpReach = num(result?.nvp_reach) ?? pickReachPhaseMetric(result, "nvp");
  const nvpTransport =
    num(result?.nvp_transport)
    ?? num(result?.nvp_drink)
    ?? num(transport?.metrics?.nvp);
  const nvpReturn = num(result?.nvp_return) ?? pickPhaseMetric(result, "return", "nvp");
  const parts = [nvpReach, nvpTransport, nvpReturn].filter((v) => v != null);
  const nvpTotal = num(result?.nvp_total) ?? (parts.length ? parts.reduce((a, b) => a + b, 0) : null);
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
    nvp_drink: num(result?.nvp_drink) ?? nvpTransport,
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
