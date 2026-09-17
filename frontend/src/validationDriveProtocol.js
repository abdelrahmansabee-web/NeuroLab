/**
 * Drive validation protocol: what the eye sees is original video bytes + overlay JSON.
 * Never store a re-encoded MediaRecorder bake as the Drive validation video.
 */

export function blobOk(blob) {
  return blob instanceof Blob && blob.size > 0;
}

export function overlayOk(overlay) {
  return Array.isArray(overlay?.frames) && overlay.frames.length > 0;
}

function blobName(blob) {
  return String(blob?.name || "").toLowerCase();
}

function blobType(blob) {
  return String(blob?.type || "").toLowerCase();
}

/** CSV / JSON must never be written as the original validation clip. */
export function isVideoOriginalBlob(blob) {
  if (!blobOk(blob)) return false;
  const name = blobName(blob);
  const type = blobType(blob);
  if (name.endsWith(".csv") || name.endsWith(".json")) return false;
  if (type.includes("csv") || type.includes("json") || type.startsWith("text/")) return false;
  if (type.startsWith("video/")) return true;
  if (/\.(mp4|mov|m4v|webm)$/i.test(name)) return true;
  return type === "" || type === "application/octet-stream";
}

/**
 * MediaRecorder canvas capture is not the on-screen original.
 * Original camera/file webm is still an original when it is the source clip.
 */
export function isReencodedValidationBake(blob, name) {
  if (!blobOk(blob)) return false;
  const type = blobType(blob);
  const n = String(name || blobName(blob) || "").toLowerCase();
  if (n.includes("_validation_original")) return false;
  if (
    type.includes("webm")
    && (n.endsWith(".mp4") || (n.includes("_validation") && !n.includes("_original")))
  ) {
    return true;
  }
  if (n.endsWith(".webm") && n.includes("_validation") && !n.includes("_original")) return true;
  return false;
}

/** Drive never receives a bake as *_validation.mp4. Playback is original + overlay canvas. */
export function shouldUploadUnifiedValidationToDrive(blob, name) {
  void blob;
  void name;
  return false;
}

export function pickOriginalVideoBlob(...candidates) {
  for (const candidate of candidates) {
    if (!isVideoOriginalBlob(candidate)) continue;
    if (isReencodedValidationBake(candidate, candidate?.name)) continue;
    return candidate;
  }
  return null;
}

export function mergeSeenValidationRecord(existing, partial = {}, liveOriginal) {
  const prev = existing && typeof existing === "object" ? existing : {};
  const next = partial && typeof partial === "object" ? partial : {};
  const original = pickOriginalVideoBlob(
    next.originalVideoBlob,
    liveOriginal,
    prev.originalVideoBlob,
  );
  const overlay = overlayOk(next.overlay) ? next.overlay : prev.overlay;
  return {
    ...prev,
    ...next,
    overlay,
    originalVideoBlob: original || prev.originalVideoBlob,
    unifiedVideoBlob: blobOk(next.unifiedVideoBlob) ? next.unifiedVideoBlob : prev.unifiedVideoBlob,
  };
}

export function validationDriveUploadPlan(record = {}) {
  return {
    overlay: overlayOk(record.overlay),
    kinematics: !!(record.kinematicsSnapshot && typeof record.kinematicsSnapshot === "object"),
    original: isVideoOriginalBlob(record.originalVideoBlob),
    unified: shouldUploadUnifiedValidationToDrive(record.unifiedVideoBlob, record.unifiedVideoFilename),
  };
}

/** OAuth ticket path must stay on the real Space origin, not the huggingface.co iframe. */
export function connectDriveHref(origin, connectPath) {
  const base = String(origin || "").replace(/\/$/, "");
  const path = String(connectPath || "/connect-drive");
  if (/^https?:\/\//i.test(path)) return path;
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}
