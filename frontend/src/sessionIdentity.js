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
