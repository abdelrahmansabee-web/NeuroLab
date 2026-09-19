/** Session flag so Drive/patient sync waits while kinematics analysis is running. */

export const KIN_ANALYZE_ACTIVE_KEY = "neuro_kin_analyze_active";
export const ANALYZE_POLL_MS = 1400;
/** ~20 min at ANALYZE_POLL_MS — clinic pose jobs can run several minutes. */
export const ANALYZE_POLL_MAX_ATTEMPTS = 860;

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
