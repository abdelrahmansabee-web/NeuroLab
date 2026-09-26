/** Session flag so Drive/patient sync waits while kinematics analysis is running. */

export const KIN_ANALYZE_ACTIVE_KEY = "neuro_kin_analyze_active";
/** Staged kinematics file — Recalling must not wipe it or race Analyze. */
export const KIN_CLINIC_FILE_LOCK_KEY = "nl_clinic_file_lock";
export const KIN_ANALYZE_UI_KEY = "neuro_kin_analyze_ui";
export const ANALYZE_POLL_MS = 1400;
/** ~20 min at ANALYZE_POLL_MS — clinic pose jobs can run several minutes. */
export const ANALYZE_POLL_MAX_ATTEMPTS = 860;
export const ANALYZE_POLL_TRANSIENT_RETRIES = 8;

export function setKinAnalyzeActive(active) {
  try {
    if (active) sessionStorage.setItem(KIN_ANALYZE_ACTIVE_KEY, "1");
    else sessionStorage.removeItem(KIN_ANALYZE_ACTIVE_KEY);
  } catch { /* ignore */ }
}

export function isKinAnalyzeActive() {
  try {
    return sessionStorage.getItem(KIN_ANALYZE_ACTIVE_KEY) === "1";
  } catch {
    return false;
  }
}

export function setClinicFileLock(locked) {
  try {
    if (locked) sessionStorage.setItem(KIN_CLINIC_FILE_LOCK_KEY, "1");
    else sessionStorage.removeItem(KIN_CLINIC_FILE_LOCK_KEY);
  } catch { /* ignore */ }
}

export function isClinicFileLocked() {
  try {
    return sessionStorage.getItem(KIN_CLINIC_FILE_LOCK_KEY) === "1";
  } catch {
    return false;
  }
}

/** Recalling law: Drive recall waits while a local file is staged or Analyze is running. */
export function isRecallingBlocked() {
  return isKinAnalyzeActive() || isClinicFileLocked();
}

function fileFromInput(phase) {
  try {
    const input = typeof document !== "undefined"
      ? document.getElementById(`kin-file-${phase}`)
      : null;
    const file = input && input.files && input.files[0];
    return file && file.size > 0 ? file : null;
  } catch {
    return null;
  }
}

/** Prefer the live File over a name-only recall row so Analyze never hangs on Drive. */
export function resolveClinicVideoFile(phase, data, dataRef) {
  const key = `video_${phase}_file`;
  const fromRef = dataRef && dataRef.current ? dataRef.current[key] : null;
  const fromData = data ? data[key] : null;
  const picked = fromRef || fromData || fileFromInput(phase);
  return picked && picked.size > 0 ? picked : null;
}

export function analyzePollExceeded(attempt, max = ANALYZE_POLL_MAX_ATTEMPTS) {
  return Number(attempt) >= max;
}

/** Server JSON `{ error }` must use the same cleanup path as a thrown failure. */
export function analysisResultErrorMessage(result) {
  const msg = result && typeof result === "object" ? result.error : null;
  return msg ? String(msg) : "";
}

export function readAnalyzeUi() {
  try {
    const raw = sessionStorage.getItem(KIN_ANALYZE_UI_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw);
    return v && typeof v === "object" ? v : null;
  } catch {
    return null;
  }
}

export function writeAnalyzeUi(partial) {
  const prev = readAnalyzeUi() || {};
  const next = { ...prev, ...(partial || {}), updatedAt: Date.now() };
  try {
    sessionStorage.setItem(KIN_ANALYZE_UI_KEY, JSON.stringify(next));
  } catch { /* ignore */ }
  return next;
}

export function clearAnalyzeUi() {
  try {
    sessionStorage.removeItem(KIN_ANALYZE_UI_KEY);
  } catch { /* ignore */ }
}

export function analyzeJobIdFromRecord(record) {
  if (!record || typeof record !== "object") return "";
  return String(record.jobId || record.job_id || "").trim();
}

export function analyzeJobIdForPhase(phase, ui, analyzeJobs) {
  const ph = String(phase || "").trim();
  if (!ph) return "";
  if (ui && String(ui.phase || "") === ph) {
    const fromUi = analyzeJobIdFromRecord(ui);
    if (fromUi) return fromUi;
  }
  return analyzeJobIdFromRecord(analyzeJobs?.[ph]);
}

export function shouldResumeAnalyze(status, jobId) {
  return String(status || "") === "analyzing" && Boolean(String(jobId || "").trim());
}

/** Analyzing with no server job and no in-flight upload — leftover card, not a live run. */
export function isStaleAnalyzing(status, jobId, hasLocalController = false) {
  return String(status || "") === "analyzing"
    && !String(jobId || "").trim()
    && !hasLocalController;
}

export function resetStaleAnalyzeStatuses(data, phaseKeys, ui, hasLocalControllerForPhase) {
  const cur = data && typeof data === "object" ? data : {};
  const jobs = { ...(cur.analyzeJobs || {}) };
  const next = { ...cur, analyzeJobs: jobs };
  let changed = false;
  for (const phase of phaseKeys || []) {
    const ph = String(phase || "").trim();
    if (!ph) continue;
    const status = cur[`status_${ph}`] || "";
    const jobId = analyzeJobIdForPhase(ph, ui, cur.analyzeJobs);
    const local = Boolean(hasLocalControllerForPhase?.(ph));
    if (!isStaleAnalyzing(status, jobId, local)) continue;
    next[`status_${ph}`] = "uploaded";
    delete jobs[ph];
    changed = true;
  }
  return changed ? next : null;
}

/** Browser/background fetch drops — keep the server job, do not fail the clinic card. */
export function isTransientAnalyzePollError(err, signal) {
  if (signal?.aborted) return false;
  const name = err?.name || "";
  const msg = String(err?.message || "").toLowerCase();
  if (name === "AbortError") return true;
  if (name === "TypeError") return true;
  if (msg.includes("failed to fetch") || msg.includes("network") || msg.includes("load failed")) return true;
  if (/progress poll failed \(5\d\d\)/.test(msg)) return true;
  if (msg.includes("progress poll failed (408)") || msg.includes("progress poll failed (429)")) return true;
  return false;
}

export function isAnalyzeLeaveAbort(err, leaveFlag) {
  return Boolean(leaveFlag) && err?.name === "AbortError";
}
