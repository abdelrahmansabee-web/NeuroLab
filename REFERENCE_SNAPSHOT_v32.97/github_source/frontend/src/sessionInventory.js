/**
 * Compact inventory of clinic sessions.
 * When a Drive recall snapshot is passed, counts reflect bytes actually
 * pulled onto the device — not just filenames on the patient JSON.
 */
import { getPatientKinPhase, pickKinField, formatKinValue } from "./analysisPlan";
import { patientDriveKeyFromDemographics } from "./driveDocIdentity";

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

export function summarizeSession(patient, recallRow) {
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
  const key = patientDriveKeyFromDemographics(patient?.demographics, patient?._id) || id || name || patient?._id || "unknown";
  const base = {
    key,
    record: patient,
    id,
    name,
    savedAt: patient?._savedAt || "",
    phases,
    kinCount,
    videoCount,
    readyCount,
    bucket,
    missing: [],
    recalled: false,
    pdfOk: false,
  };
  return applyRecallRow(base, recallRow);
}

export function findRecallRow(patient, recall) {
  const rows = Array.isArray(recall?.rows) ? recall.rows : [];
  if (!rows.length || !patient) return null;
  const id = String(patient?.demographics?.participantId || "").trim();
  const key = patientDriveKeyFromDemographics(patient?.demographics, patient?._id);
  return (
    rows.find((r) => key && (r.key === key || r.patientKey === key))
    || rows.find((r) => id && String(r.id || "").trim() === id)
    || null
  );
}

export function applyRecallRow(session, recallRow) {
  if (!recallRow) return session;
  if (!recallRow.expected) {
    return {
      ...session,
      bucket: "empty",
      missing: [],
      recalled: false,
      pdfOk: !!recallRow.pdfOk,
    };
  }
  const phases = SESSION_PHASES.map((meta, i) => {
    const jsonPh = session.phases[i];
    const recPh = (recallRow.phases || []).find((p) => p.phase === meta.k) || {};
    const expected = recPh.expected != null ? !!recPh.expected : jsonPh.tone !== "empty";
    const hasKin = recPh.hasKin != null ? !!recPh.hasKin : jsonPh.hasKin;
    const hasOriginal = !!recPh.hasOriginal;
    const hasOverlay = !!recPh.hasOverlay;
    const hasUnified = !!recPh.hasUnified;
    const hasVideo = hasOriginal || hasUnified;
    let tone = "empty";
    if (expected) tone = recPh.complete || (hasKin && hasOriginal && hasOverlay && (!recPh.wantUnified || hasUnified))
      ? "ready"
      : "partial";
    return {
      ...jsonPh,
      expected,
      hasKin,
      hasOriginal,
      hasOverlay,
      hasUnified,
      hasVideo,
      tone,
      videoName: hasOriginal
        ? "Original video recalled"
        : hasUnified
          ? "Validation video recalled"
          : jsonPh.videoName,
    };
  });
  const kinCount = phases.filter((p) => p.hasKin).length;
  const videoCount = phases.filter((p) => p.hasOriginal || p.hasUnified).length;
  const readyCount = phases.filter((p) => p.tone === "ready").length;
  return {
    ...session,
    phases,
    kinCount,
    videoCount,
    readyCount,
    bucket: recallRow.complete ? "ready" : "partial",
    missing: Array.isArray(recallRow.missing) ? recallRow.missing : [],
    recalled: true,
    pdfOk: !!recallRow.pdfOk,
    expectedPhaseCount: recallRow.expectedPhaseCount,
    completePhaseCount: recallRow.completePhaseCount,
  };
}

export function summarizeInventory(patients, recall) {
  const list = (Array.isArray(patients) ? patients : []).filter(
    (p) => p && typeof p === "object" && !p._archived,
  );
  const useRecall = Boolean(recall && (recall.attempted || (recall.rows && recall.rows.length)));
  const rows = list
    .map((p) => summarizeSession(p, useRecall ? findRecallRow(p, recall) : null))
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
    fromDrive: useRecall,
    complete: useRecall ? rows.filter((r) => r.recalled && r.bucket === "ready").length : rows.filter((r) => r.bucket === "ready").length,
    incomplete: useRecall ? rows.filter((r) => r.recalled && r.bucket === "partial").length : rows.filter((r) => r.bucket === "partial").length,
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
