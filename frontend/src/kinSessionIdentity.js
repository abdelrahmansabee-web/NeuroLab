/** Fingerprint of stored phase files — not live picker blobs. */
export function kinAnalysisResultsSig(analysisResults) {
  const r = analysisResults && typeof analysisResults === "object" ? analysisResults : {};
  return ["pre", "post", "baseline"].map((ph) => {
    const row = r[ph] || {};
    return `${ph}:${row.csv_filename || ""}:${row.video_filename || ""}`;
  }).join("|");
}

/** True when the open kinematics record actually changed (not first save assigning an id). */
export function shouldResetKinSessionMedia(prevKey, nextKey, prevSig, nextSig) {
  const prev = String(prevKey || "");
  const next = String(nextKey || "");
  if (prev === next) return false;
  if (!prev && next) {
    // Blank → id: keep live overlay on first save; clear when another record's files appear.
    return String(prevSig || "") !== String(nextSig || "");
  }
  return true;
}

/** Drop async overlay/video/analysis results that finished after a patient switch. */
export function kinAsyncStillCurrent(startedKey, activeKey) {
  return String(startedKey || "") === String(activeKey || "");
}
