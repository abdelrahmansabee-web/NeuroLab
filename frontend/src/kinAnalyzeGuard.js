/** Session flag so Drive/patient sync waits while kinematics analysis is running. */

export const KIN_ANALYZE_ACTIVE_KEY = "neuro_kin_analyze_active";
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
