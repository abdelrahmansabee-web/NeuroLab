/**
 * Open-session identity. Validation pixels and kinematics numbers stay
 * on the patient who is actually open — never the last writer of the
 * global neuro_kin_results key.
 */

export function kinematicsResultsForOpenSession(sessionResults) {
  const fd = sessionResults && typeof sessionResults === "object" ? { ...sessionResults } : {};
  delete fd.during;
  return fd;
}

/** Match the open form to one patient row. Never compare _id to Study ID. */
export function findPatientForOpenSession(patients, fd) {
  const list = Array.isArray(patients) ? patients : [];
  const loadedId = String(fd?._loadedId || "").trim();
  if (loadedId) {
    const hits = list.filter((p) => String(p?._id || "").trim() === loadedId);
    return hits.length === 1 ? hits[0] : null;
  }
  const studyId = String(fd?.demographics?.participantId || "").trim();
  if (!studyId) return null;
  const hits = list.filter(
    (p) => String(p?.demographics?.participantId || "").trim() === studyId,
  );
  return hits.length === 1 ? hits[0] : null;
}

/** Fingerprint of stored phase files — not live picker blobs. */
export function kinAnalysisResultsSig(analysisResults) {
  const r = analysisResults && typeof analysisResults === "object" ? analysisResults : {};
  return ["pre", "post", "baseline"].map((ph) => {
    const row = r[ph] || {};
    return `${ph}:${row.csv_filename || ""}:${row.video_filename || ""}`;
  }).join("|");
}

/** True when the open record actually changed (not first save assigning an id). */
export function shouldResetKinSessionMedia(prevKey, nextKey, prevSig, nextSig) {
  const prev = String(prevKey || "");
  const next = String(nextKey || "");
  if (prev === next) return false;
  if (!prev && next) {
    return String(prevSig || "") !== String(nextSig || "");
  }
  return true;
}

/** Drop async overlay/video/analysis results that finished after a patient switch. */
export function kinAsyncStillCurrent(startedKey, activeKey) {
  return String(startedKey || "") === String(activeKey || "");
}
