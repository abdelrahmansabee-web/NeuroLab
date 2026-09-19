/**
 * Clinic watch: classify known live-app faults and pick a safe recovery.
 * Does not rewrite product code or change overlay paint / jitter / clock.
 */

export const CLINIC_HEAL_LS_KEY = "neuro_clinic_heal_log";
export const CLINIC_HEAL_MAX_ATTEMPTS = 2;
export const CLINIC_HEAL_LOG_MAX = 20;

export function classifyClinicFault(input = {}) {
  const err = input.err && typeof input.err === "object" ? input.err : null;
  const msg = String(input.message || err?.message || "").toLowerCase();
  const name = String(input.name || err?.name || "");
  const status = Number(input.status || 0);
  const ctx = String(input.context || "");

  if (
    ctx === "analyze-upload"
    || msg.includes("please select a file first")
    || (ctx === "analyze" && (name === "AbortError" || name === "TypeError" || msg.includes("failed to fetch")))
  ) {
    if (msg.includes("please select a file first")) {
      return {
        code: "analyze_missing_file",
        cause: "Analyze had the clip name but not the file-input File.",
        recover: "use_recalled_original",
      };
    }
    if (!input.hasJobId && (name === "AbortError" || name === "TypeError" || msg.includes("failed to fetch") || msg.includes("analysis cancelled"))) {
      return {
        code: "analyze_upload_drop",
        cause: "Video upload was cut before the server issued a job id.",
        recover: "retry_upload",
      };
    }
  }

  if (
    ctx === "overlay"
    || msg.includes("overlay data failed")
    || msg.includes("overlay-data")
    || (status === 404 && msg.includes("overlay"))
  ) {
    return {
      code: "overlay_space_csv_gone",
      cause: "Space disk lost the CSV after a rebuild.",
      recover: "hydrate_overlay",
    };
  }

  if (
    ctx === "original-video"
    || msg.includes("original video expired")
    || msg.includes("expired on server — please re-upload")
  ) {
    return {
      code: "space_video_expired",
      cause: "Ephemeral Space /video/ is gone or blocked for the wrong patient.",
      recover: "hydrate_original",
    };
  }

  if (ctx === "validation-video" || msg.includes("validation video expired")) {
    return {
      code: "space_validation_expired",
      cause: "Baked validation clip expired on Space disk.",
      recover: "hydrate_unified",
    };
  }

  return {
    code: "unknown",
    cause: String(input.message || err?.message || "Unknown clinic error"),
    recover: "report",
  };
}

export function clinicHealKey(code, phase) {
  return `${String(code || "unknown")}:${String(phase || "_")}`;
}

export function clinicHealBudgetAllows(store, code, phase, max = CLINIC_HEAL_MAX_ATTEMPTS) {
  const n = Number(store?.[clinicHealKey(code, phase)]) || 0;
  return n < max;
}

export function noteClinicHealAttempt(store, code, phase) {
  const key = clinicHealKey(code, phase);
  return { ...(store || {}), [key]: (Number(store?.[key]) || 0) + 1 };
}

export function clinicHealNotice(fault, recovered) {
  if (!fault) return "";
  if (recovered && fault.recover === "retry_upload") {
    return `${fault.cause} Clinic watch retried the upload.`;
  }
  if (recovered && fault.recover === "use_recalled_original") {
    return `${fault.cause} Clinic watch used this patient's Drive/IDB clip.`;
  }
  if (recovered && fault.recover === "hydrate_overlay") {
    return `${fault.cause} Clinic watch restored the overlay from Drive/IDB.`;
  }
  if (recovered && fault.recover === "hydrate_original") {
    return `${fault.cause} Clinic watch restored the original from Drive/IDB.`;
  }
  if (recovered && fault.recover === "hydrate_unified") {
    return `${fault.cause} Clinic watch restored the validation clip from Drive/IDB.`;
  }
  return fault.cause;
}

export function appendClinicHealLog(entry) {
  const row = {
    at: Date.now(),
    code: entry?.code || "unknown",
    cause: entry?.cause || "",
    recover: entry?.recover || "report",
    recovered: Boolean(entry?.recovered),
    phase: entry?.phase || "",
  };
  let list = [];
  try {
    list = JSON.parse(sessionStorage.getItem(CLINIC_HEAL_LS_KEY) || "[]");
  } catch { /* ignore */ }
  if (!Array.isArray(list)) list = [];
  list.unshift(row);
  list = list.slice(0, CLINIC_HEAL_LOG_MAX);
  try {
    sessionStorage.setItem(CLINIC_HEAL_LS_KEY, JSON.stringify(list));
  } catch { /* ignore */ }
  return row;
}

export function readClinicHealLog() {
  try {
    const list = JSON.parse(sessionStorage.getItem(CLINIC_HEAL_LS_KEY) || "[]");
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}
