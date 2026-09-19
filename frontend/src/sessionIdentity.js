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

/**
 * Space `/video/<filename>` is last-writer for the whole Space.
 * Only the file this open session just uploaded may use that path.
 */
export function shouldUseEphemeralSpaceVideo(filename, localUploadNames) {
  const name = String(filename || "").trim();
  if (!name) return false;
  if (localUploadNames instanceof Set) return localUploadNames.has(name);
  if (Array.isArray(localUploadNames)) {
    return localUploadNames.some((item) => String(item || "").trim() === name);
  }
  return false;
}

/** Recalled Drive/IDB clip for Analyze. Same blob — do not copy (iPad kills the POST). */
export function blobAsAnalyzeFile(blob, _filename) {
  if (!(blob instanceof Blob) || blob.size <= 0) return null;
  return blob;
}

export function analyzeSourceForOpenSession({ file, originalBlob, filename } = {}) {
  if (file instanceof Blob && file.size > 0) {
    if (file.name) return file;
    return blobAsAnalyzeFile(file, filename) || file;
  }
  return blobAsAnalyzeFile(originalBlob, filename);
}
