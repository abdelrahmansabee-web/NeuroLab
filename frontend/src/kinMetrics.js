import { pickKinField } from "./analysisPlan";
import { computeOverlayMetrics, isPanelTableKey } from "./validationPanelMetrics";
import { getMovementProfile } from "./movementProfile";
import { enrichKinematicCompletion } from "./taskCompletion";

export { formatPanelAlignedKinValue, isPanelTableKey } from "./validationPanelMetrics";

export const KIN_RESULTS_LS_KEY = "neuro_kin_results";

function pickFromMovementProfile(phaseResult, metricKey) {
  const profile = getMovementProfile(phaseResult);
  if (!profile || profile[metricKey] == null || profile[metricKey] === "") return null;
  const v = profile[metricKey];
  if (typeof v === "number" && Number.isNaN(v)) return null;
  return v;
}

/** Same metric resolution as Kinematic Lab table — validation-video panel first. */
export function resolveKinMetricValue(phaseResult, metricKey, overlayData = null) {
  if (!phaseResult && !overlayData) return null;

  if (isPanelTableKey(metricKey)) {
    if (overlayData?.frames?.length) {
      try {
        const computed = computeOverlayMetrics(overlayData);
        if (computed) {
          const fromOverlay = pickKinField(computed, metricKey);
          if (fromOverlay !== null) return fromOverlay;
          return null;
        }
      } catch (e) {
        console.warn("computeOverlayMetrics failed:", e);
      }
    }
    for (const src of [phaseResult?.overlay_metrics, phaseResult?.validation_summary]) {
      const v = pickKinField(src, metricKey);
      if (v !== null) return v;
    }
  }

  const completionKeys = [
    "task_complete",
    "task_completion_ratio",
    "nvp_reach",
    "nvp_drink",
    "nvp_transport",
    "nvp_return",
    "nvp_total",
    "drink_lift_height_cm",
    "lift_height_cm",
    "drink_lift_height_sw",
    "lift_height_sw",
    "straightness_reach",
    "pause_time_sec_reach",
    "number_of_stops_reach",
    "sip_bout_count",
    "grasp_dwell_sec",
    "functional_hold_sec",
    "pause_time_sec_total",
    "nvp_full_task",
    "nvp",
  ];
  if (completionKeys.includes(metricKey)) {
    const enriched = enrichKinematicCompletion(phaseResult || {}, overlayData);
    const fromEnriched = enriched[metricKey];
    if (fromEnriched != null && fromEnriched !== "" && !Number.isNaN(Number(fromEnriched))) {
      return Number(fromEnriched);
    }
  }

  if (overlayData?.frames?.length && !completionKeys.includes(metricKey)) {
    const computed = computeOverlayMetrics(overlayData);
    if (computed) {
      const fromOverlay = pickKinField(computed, metricKey);
      if (fromOverlay !== null) return fromOverlay;
    }
  }

  for (const src of [phaseResult?.overlay_metrics, phaseResult?.validation_summary, phaseResult]) {
    const v = pickKinField(src, metricKey);
    if (v !== null) return v;
  }

  const fromProfile = pickFromMovementProfile(phaseResult, metricKey);
  if (fromProfile !== null) return fromProfile;

  if (metricKey.startsWith("adl_")) {
    const fromMetrics = overlayData?.metrics?.[metricKey];
    if (fromMetrics != null && fromMetrics !== "" && !Number.isNaN(Number(fromMetrics))) return Number(fromMetrics);
    const v = phaseResult?.[metricKey];
    if (v != null && v !== "" && !Number.isNaN(Number(v))) return Number(v);
  }

  if (metricKey === "side_analyzed" || metricKey === "side") {
    const side = phaseResult?.side_analyzed ?? phaseResult?.side;
    return side != null && side !== "" ? side : null;
  }

  return null;
}

export function mergeKinAnalysisResults(fdKr, lsKr) {
  const keys = new Set([...Object.keys(fdKr || {}), ...Object.keys(lsKr || {})]);
  const out = {};
  keys.forEach((k) => {
    if (k === "during") return;
    out[k] = { ...(fdKr?.[k] || {}), ...(lsKr?.[k] || {}) };
  });
  return out;
}

/** Live session kinematics from the open form only — never global neuro_kin_results. */
export function loadLiveKinResults(fd) {
  return mergeKinAnalysisResults(fd?.kinematics?.analysisResults, {});
}
