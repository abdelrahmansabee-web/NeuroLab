/**
 * Compact inventory of loaded clinic sessions: kinematics + video presence.
 * Does not fetch media; uses patient JSON that already synced from server/Drive.
 */
import { getPatientKinPhase, pickKinField, formatKinValue } from "./analysisPlan";

export const SESSION_PHASES = [
  { k: "pre", l: "Pre" },
  { k: "post", l: "Post" },
  { k: "baseline", l: "Healthy" },
];

export const SESSION_STATUS_LS = {
  noAutoOpen: "nl_session_status_no_auto_open",
};

export const SESSION_STATUS_SS = {
  autoShown: "nl_session_status_autoshown",
  chipHidden: "nl_session_status_chip_hidden",
};

const METRIC_KEYS = [
  { key: "movement_time_sec", short: "MT" },
  { key: "peak_velocity_cm_s", short: "Peak" },
  { key: "nvp", short: "NVP" },
];

function rawPhaseResult(patient, phaseKey) {
  const kin = patient?.kinematics || {};
  const key = phaseKey === "healthy" ? "baseline" : phaseKey;
  return (
    kin.analysisResults?.[key] ||
    patient?.[`result_${key}`] ||
    kin[`result_${key}`] ||
    kin[key] ||
    null
  );
}

export function summarizePhase(patient, phaseKey) {
  const raw = rawPhaseResult(patient, phaseKey);
  const normalized = (() => {
    try {
      return getPatientKinPhase(patient, phaseKey);
    } catch {
      return null;
    }
  })();
  const hasCsv = !!(raw && raw.csv_filename);
  const metrics = {};
  let metricCount = 0;
  if (normalized && typeof normalized === "object") {
    METRIC_KEYS.forEach(({ key }) => {
      const v = pickKinField(normalized, key) ?? pickKinField(raw || {}, key);
      if (v != null && Number.isFinite(Number(v))) {
        metrics[key] = Number(v);
        metricCount += 1;
      }
    });
  }
  const hasKin = hasCsv || metricCount > 0;
  const hasVideo = !!(raw && (raw.video_filename || raw.unified_validation_video));
  let tone = "empty";
  if (hasKin && hasVideo) tone = "ready";
  else if (hasKin || hasVideo) tone = "partial";
  return {
    phase: phaseKey,
    hasKin,
    hasVideo,
    hasCsv,
    videoName: raw?.video_filename || raw?.unified_validation_video || "",
    metrics,
    tone,
  };
}

export function summarizeSession(patient) {
  const phases = SESSION_PHASES.map((p) => summarizePhase(patient, p.k));
  const kinCount = phases.filter((p) => p.hasKin).length;
  const videoCount = phases.filter((p) => p.hasVideo).length;
  const readyCount = phases.filter((p) => p.tone === "ready").length;
  const partialCount = phases.filter((p) => p.tone === "partial").length;
  let bucket = "empty";
  if (readyCount > 0 && partialCount === 0 && kinCount === readyCount) bucket = "ready";
  else if (kinCount > 0 || videoCount > 0) bucket = "partial";
  const id = String(patient?.demographics?.participantId || patient?._id || "").trim();
  const name = String(patient?.demographics?.name || "").trim();
  return {
    key: id || name || patient?._id || "unknown",
    record: patient,
    id,
    name,
    savedAt: patient?._savedAt || "",
    phases,
    kinCount,
    videoCount,
    readyCount,
    bucket,
  };
}

export function summarizeInventory(patients) {
  const list = (Array.isArray(patients) ? patients : []).filter(
    (p) => p && typeof p === "object" && !p._archived,
  );
  const rows = list
    .map(summarizeSession)
    .sort((a, b) => {
      const ia = parseInt(a.id, 10);
      const ib = parseInt(b.id, 10);
      if (Number.isFinite(ia) && Number.isFinite(ib) && ia !== ib) return ia - ib;
      return String(a.id).localeCompare(String(b.id));
    });
  return {
    total: rows.length,
    ready: rows.filter((r) => r.bucket === "ready").length,
    partial: rows.filter((r) => r.bucket === "partial").length,
    empty: rows.filter((r) => r.bucket === "empty").length,
    rows,
  };
}

export function formatPhaseMetricLine(phase) {
  const parts = METRIC_KEYS.map(({ key, short }) => {
    if (phase.metrics[key] == null) return null;
    return `${short} ${formatKinValue(key, phase.metrics[key])}`;
  }).filter(Boolean);
  return parts.join(" · ");
}
