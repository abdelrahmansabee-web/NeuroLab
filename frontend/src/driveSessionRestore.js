/**
 * Recall analyzed sessions from Google Drive into IndexedDB on program open.
 * Hugging Face has no lasting video disk; Drive is the copy that must be fetched again.
 */
import { clinicReportDriveName, documentKind, patientDriveKeyFromDemographics } from "./driveDocIdentity";
import { isRecallingBlocked } from "./kinAnalyzeGuard";
import {
  loadValidationSessionArtifact,
  saveValidationSessionArtifact,
} from "./validationSessionCache";
import {
  backupValidationArtifactsToDrive,
  driveTokenHeaders,
  fetchDriveFile,
  validationKinematicsDriveName,
  validationOriginalDriveName,
  validationOverlayDriveName,
  validationUnifiedDriveName,
} from "./validationDriveSync";

export const DRIVE_RECALL_EVENT = "neurolab-drive-recall";
export const DRIVE_RECALL_START_EVENT = "neurolab-drive-recall-start";
export const DRIVE_RECALL_LS = "nl_drive_recall_v1";
export const PATIENTS_SYNC_EVENT = "neurolab-patients-synced";
export const RECALL_COOLDOWN_MS = 45000;
export const EMPTY_RECALL_WAIT_MS = 28000;

export function isStandaloneDisplay() {
  try {
    return (typeof window !== "undefined")
      && (
        (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches)
        || window.navigator.standalone === true
      );
  } catch {
    return false;
  }
}

/** Home Screen storage is empty; wait for server restore before a no-op recall. */
export function shouldWaitForPatientsBeforeRecall(patients, opts = {}) {
  const list = Array.isArray(patients) ? patients : [];
  if (list.length) return false;
  if (opts.standalone === false) return false;
  const standalone = opts.standalone === true || isStandaloneDisplay();
  if (!standalone) return false;
  const waited = Number(opts.waitedMs);
  const maxWait = Number(opts.maxWaitMs) > 0 ? Number(opts.maxWaitMs) : EMPTY_RECALL_WAIT_MS;
  return Number.isFinite(waited) ? waited < maxWait : true;
}

export function preferPatientInRecallList(list, preferredKey) {
  const key = String(preferredKey || "").trim();
  if (!key) return Array.isArray(list) ? list : [];
  const rows = Array.isArray(list) ? list : [];
  const hit = [];
  const rest = [];
  rows.forEach((p) => {
    const k = patientDriveKeyFromDemographics(p?.demographics, p?._id);
    if (k === key) hit.push(p);
    else rest.push(p);
  });
  return hit.length ? [...hit, ...rest] : rows;
}

export function recallPoolSize(opts = {}) {
  const standalone = opts.standalone === true || isStandaloneDisplay();
  return standalone ? 1 : 2;
}

/** Blank Home Screen / new icon: wait for the signed-in email restore, do not race an empty recall. */
export function shouldDeferBootRecallUntilEmailRestore(patients) {
  return !Array.isArray(patients) || patients.length === 0;
}

const localDrivePushOnce = new Set();

/** Safari / an icon that already has the original must copy it to Drive for every other icon. */
export function shouldPushLocalRecallToDrive(existingCache, recalled) {
  return blobOk(existingCache?.originalVideoBlob) && blobOk(recalled?.originalVideoBlob);
}

/** PRE original first so a new icon can play the analyzed clip before overlay JSON finishes. */
export function recallPhaseFetchSteps(phasePlan, existingCache) {
  const cache = existingCache || {};
  const steps = [];
  if (phasePlan?.wantOriginal && !blobOk(cache.originalVideoBlob)) steps.push("original");
  if (phasePlan?.wantOverlay && !overlayOk(cache.overlay)) steps.push("overlay");
  if (phasePlan?.wantKin && !kinNumbersOk(cache.kinematicsSnapshot)) steps.push("kin");
  if (phasePlan?.wantUnified && !blobOk(cache.unifiedVideoBlob)) steps.push("unified");
  return steps;
}

/** Home Screen storage starts empty — pull the server list before giving up. */
export async function coalesceRecallPatients(seed, opts = {}) {
  const clean = (list) => (Array.isArray(list) ? list : []).filter((p) => p && typeof p === "object" && !p._archived);
  const fromSeed = clean(seed);
  if (fromSeed.length) return fromSeed;
  const fromLoaded = clean(typeof opts.loadPatients === "function" ? opts.loadPatients() : []);
  if (fromLoaded.length) return fromLoaded;
  if (typeof opts.pullRemotePatients !== "function") return [];
  const remote = clean(await opts.pullRemotePatients());
  if (!remote.length) return [];
  if (typeof opts.savePatients === "function") {
    const saved = opts.savePatients(remote);
    const fromSaved = clean(saved);
    return fromSaved.length ? fromSaved : remote;
  }
  return remote;
}

/** Empty boot recall must not block the real list that arrives a few seconds later. */
export function shouldReuseRecentRecall(lastSummary, lastRecallAt, now = Date.now(), opts = {}) {
  if (opts.force) return false;
  if (!lastSummary) return false;
  if (!Number.isFinite(Number(lastRecallAt)) || now - lastRecallAt >= RECALL_COOLDOWN_MS) return false;
  if (!lastSummary.attempted) return false;
  return true;
}

function applyStandaloneRecallPlan(plan) {
  if (!plan || !isStandaloneDisplay()) return plan;
  return {
    ...plan,
    phases: (plan.phases || []).map((ph) => ({ ...ph, wantUnified: false })),
  };
}

export const RECALL_PHASES = [
  { k: "pre", l: "Pre", drive: "pre" },
  { k: "post", l: "Post", drive: "post" },
  { k: "baseline", l: "Healthy", drive: "healthy" },
];

const LS_KEY = "stroke_rehab_patients_v6";

function blobOk(blob) {
  return blob instanceof Blob && blob.size > 0;
}

function overlayOk(overlay) {
  return Array.isArray(overlay?.frames) && overlay.frames.length > 0;
}

function kinNumbersOk(raw) {
  if (!raw || typeof raw !== "object") return false;
  if (raw.csv_filename) return true;
  const keys = ["movement_time_sec", "peak_velocity_cm_s", "nvp"];
  return keys.some((key) => raw[key] != null && Number.isFinite(Number(raw[key])));
}

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

export function driveKindsFromNames(names) {
  const kinds = new Set();
  (Array.isArray(names) ? names : []).forEach((name) => {
    const kind = documentKind(name);
    if (kind) kinds.add(kind);
  });
  return kinds;
}

export function planPatientRecall(patient, driveNames = []) {
  const kinds = driveKindsFromNames(driveNames);
  const demo = patient?.demographics || {};
  const hasDemo = !!(String(demo.participantId || "").trim() || String(demo.name || demo.fullName || "").trim());
  const phases = RECALL_PHASES.map((meta) => {
    const raw = rawPhaseResult(patient, meta.k);
    const jsonKin = kinNumbersOk(raw);
    const jsonOriginalName = !!(raw && raw.video_filename && !String(raw.video_filename).toLowerCase().endsWith(".csv"));
    const jsonUnifiedName = !!(raw && raw.unified_validation_video);
    const onDrive = {
      original: kinds.has(`${meta.drive}_validation_original`),
      overlay: kinds.has(`${meta.drive}_validation_overlay`),
      kinJson: kinds.has(`${meta.drive}_kinematics`),
      unified: kinds.has(`${meta.drive}_validation`),
    };
    const expected = !!(jsonKin || jsonOriginalName || jsonUnifiedName || onDrive.original || onDrive.overlay || onDrive.kinJson || onDrive.unified);
    return {
      phase: meta.k,
      label: meta.l,
      drivePhase: meta.drive,
      expected,
      wantOriginal: expected,
      wantOverlay: expected,
      wantKin: expected,
      wantUnified: !!(jsonUnifiedName || onDrive.unified),
      jsonKin,
    };
  });
  const anyPhase = phases.some((p) => p.expected);
  return {
    patientKey: patientDriveKeyFromDemographics(demo, patient?._id),
    id: String(demo.participantId || "").trim(),
    name: String(demo.name || demo.fullName || "").trim(),
    hasDemo,
    wantPdf: kinds.has("clinic_report"),
    anyPhase,
    phases,
  };
}

export function evaluateRecallPieces(plan, { cacheByPhase = {}, pdfOk = false, kinByPhase = {} } = {}) {
  const missing = [];
  if (!plan.hasDemo) missing.push("Patient info");
  if (plan.wantPdf && !pdfOk) missing.push("Clinic PDF");
  const phases = plan.phases.map((ph) => {
    if (!ph.expected) {
      return { ...ph, complete: false, recalled: false };
    }
    const cache = cacheByPhase[ph.phase] || {};
    const kin = kinNumbersOk(kinByPhase[ph.phase]) || kinNumbersOk(cache.kinematicsSnapshot) || ph.jsonKin;
    const original = blobOk(cache.originalVideoBlob);
    const overlay = overlayOk(cache.overlay);
    const unified = blobOk(cache.unifiedVideoBlob);
    const bits = [];
    if (ph.wantKin && !kin) bits.push(`${ph.label} analysis`);
    if (ph.wantOriginal && !original) bits.push(`${ph.label} original video`);
    if (ph.wantOverlay && !overlay) bits.push(`${ph.label} overlay`);
    if (ph.wantUnified && !unified) bits.push(`${ph.label} validation video`);
    missing.push(...bits);
    const complete = bits.length === 0;
    return {
      ...ph,
      hasKin: kin,
      hasOriginal: original,
      hasOverlay: overlay,
      hasUnified: unified,
      complete,
      recalled: complete || original || overlay || unified || kin,
    };
  });
  const expectedPhases = phases.filter((p) => p.expected);
  const completePhases = expectedPhases.filter((p) => p.complete);
  const complete = plan.anyPhase && missing.length === 0;
  return {
    ...plan,
    pdfOk,
    phases,
    missing,
    expectedPhaseCount: expectedPhases.length,
    completePhaseCount: completePhases.length,
    complete,
    expected: plan.anyPhase,
  };
}

export function formatRecallToast(summary) {
  if (!summary || !summary.attempted) return "";
  const complete = Number(summary.complete || 0);
  const incomplete = Number(summary.incomplete || 0);
  if (!complete && !incomplete) return "";
  if (!incomplete) {
    return `Recalled ${complete} session${complete === 1 ? "" : "s"} from Drive`;
  }
  const sample = (summary.rows || [])
    .filter((row) => row.expected && !row.complete)
    .slice(0, 2)
    .map((row) => {
      const who = row.id || row.name || "patient";
      const bits = (row.missing || []).slice(0, 3).join(", ");
      return bits ? `${who}: ${bits}` : who;
    })
    .join(" · ");
  const head = complete
    ? `Recalled ${complete} session${complete === 1 ? "" : "s"} from Drive`
    : "Drive recall incomplete";
  return sample ? `${head}. Missing — ${sample}` : `${head}. ${incomplete} incomplete`;
}

export function summarizeRecallRows(rows) {
  const expected = rows.filter((r) => r.expected);
  return {
    attempted: expected.length > 0,
    total: rows.length,
    complete: expected.filter((r) => r.complete).length,
    incomplete: expected.filter((r) => !r.complete).length,
    empty: rows.filter((r) => !r.expected).length,
    rows,
  };
}

async function listPatientDriveFiles(patientKey) {
  if (!patientKey) return [];
  try {
    const q = new URLSearchParams({ patientKey, scope: "auto" });
    const tokenHeaders = driveTokenHeaders();
    const res = await fetch(`/auth/list-patient-files?${q.toString()}`, {
      credentials: "same-origin",
      headers: tokenHeaders,
    });
    if (!res.ok) return [];
    const data = await res.json();
    const files = Array.isArray(data?.files) ? data.files : [];
    return files.map((f) => (typeof f === "string" ? f : f?.name)).filter(Boolean);
  } catch (err) {
    console.warn("list-patient-files failed:", err);
    return [];
  }
}

async function parseJsonBlob(blob) {
  if (!blobOk(blob)) return null;
  try {
    const parsed = JSON.parse(await blob.text());
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function mergeKinIntoPatient(patient, phase, snap) {
  if (!snap || typeof snap !== "object") return patient;
  const key = phase === "healthy" || phase === "baseline" ? "baseline" : phase;
  const kin = patient.kinematics && typeof patient.kinematics === "object" ? patient.kinematics : {};
  const results = kin.analysisResults && typeof kin.analysisResults === "object" ? kin.analysisResults : {};
  const prev = results[key] && typeof results[key] === "object" ? results[key] : {};
  return {
    ...patient,
    kinematics: {
      ...kin,
      analysisResults: {
        ...results,
        [key]: { ...prev, ...snap },
      },
    },
  };
}

async function pullDriveBlob(patientKey, name, subfolder, timeoutMs, retries = 0) {
  let blob = await fetchDriveFile(patientKey, name, subfolder, { timeoutMs });
  if (blobOk(blob) || retries < 1) return blob;
  return fetchDriveFile(patientKey, name, subfolder, { timeoutMs });
}

async function recallOnePhase(patientKey, phasePlan, existingCache) {
  const phase = phasePlan.phase;
  const cache = existingCache || { patientKey, phase };
  const next = { ...cache, patientKey, phase };
  const timeoutMs = isStandaloneDisplay() ? 90000 : 180000;
  for (const step of recallPhaseFetchSteps(phasePlan, next)) {
    if (step === "original") {
      const blob = await pullDriveBlob(patientKey, validationOriginalDriveName(phase), "videos", timeoutMs, 1);
      if (blobOk(blob)) next.originalVideoBlob = blob;
      continue;
    }
    if (step === "overlay") {
      const blob = await pullDriveBlob(patientKey, validationOverlayDriveName(phase), "data", timeoutMs, 1);
      const parsed = await parseJsonBlob(blob);
      if (overlayOk(parsed)) next.overlay = parsed;
      continue;
    }
    if (step === "kin") {
      const blob = await pullDriveBlob(patientKey, validationKinematicsDriveName(phase), "data", timeoutMs, 1);
      const parsed = await parseJsonBlob(blob);
      if (parsed) next.kinematicsSnapshot = parsed;
      continue;
    }
    if (step === "unified") {
      const blob = await pullDriveBlob(patientKey, validationUnifiedDriveName(phase), "videos", timeoutMs, 0);
      if (blobOk(blob)) next.unifiedVideoBlob = blob;
    }
  }
  next.savedAt = Date.now();
  await saveValidationSessionArtifact(next);
  if (shouldPushLocalRecallToDrive(cache, next)) {
    const stamp = `${patientKey}:${phase}`;
    if (!localDrivePushOnce.has(stamp)) {
      localDrivePushOnce.add(stamp);
      backupValidationArtifactsToDrive(patientKey, phase, next).catch((err) => {
        localDrivePushOnce.delete(stamp);
        console.warn("Drive re-push of local recall failed:", err);
      });
    }
  }
  return next;
}

async function recallOnePatient(patient) {
  const patientKey = patientDriveKeyFromDemographics(patient?.demographics, patient?._id);
  if (!patientKey) {
    return evaluateRecallPieces(planPatientRecall(patient, []), {});
  }
  const driveNames = await listPatientDriveFiles(patientKey);
  const plan = applyStandaloneRecallPlan(planPatientRecall(patient, driveNames));
  const kinds = driveKindsFromNames(driveNames);
  let pdfOk = kinds.has("clinic_report");
  if (plan.wantPdf && !pdfOk) {
    const pdf = await fetchDriveFile(patientKey, clinicReportDriveName(patientKey), "reports");
    pdfOk = blobOk(pdf);
  }
  const cacheByPhase = {};
  const kinByPhase = {};
  let mergedPatient = patient;
  for (const ph of plan.phases) {
    if (!ph.expected) continue;
    const existing = await loadValidationSessionArtifact(patientKey, ph.phase);
    const cache = await recallOnePhase(patientKey, ph, existing);
    cacheByPhase[ph.phase] = cache;
    if (cache.kinematicsSnapshot) {
      kinByPhase[ph.phase] = cache.kinematicsSnapshot;
      mergedPatient = mergeKinIntoPatient(mergedPatient, ph.phase, cache.kinematicsSnapshot);
    }
  }
  const row = evaluateRecallPieces(plan, { cacheByPhase, pdfOk, kinByPhase });
  row.record = mergedPatient;
  row.patientKey = patientKey;
  return row;
}

async function mapPool(items, limit, fn) {
  const out = new Array(items.length);
  let cursor = 0;
  const worker = async () => {
    while (cursor < items.length) {
      const idx = cursor;
      cursor += 1;
      out[idx] = await fn(items[idx], idx);
    }
  };
  const n = Math.max(1, Math.min(limit, items.length) || 1);
  await Promise.all(Array.from({ length: n }, worker));
  return out;
}

function persistRecallSummary(summary) {
  try {
    const slim = {
      at: Date.now(),
      complete: summary.complete,
      incomplete: summary.incomplete,
      attempted: summary.attempted,
      empty: summary.empty,
      rows: (summary.rows || []).map((row) => ({
        key: row.patientKey || row.key,
        id: row.id,
        name: row.name,
        expected: row.expected,
        complete: row.complete,
        missing: row.missing || [],
        pdfOk: !!row.pdfOk,
        expectedPhaseCount: row.expectedPhaseCount,
        completePhaseCount: row.completePhaseCount,
        phases: (row.phases || []).map((ph) => ({
          phase: ph.phase,
          label: ph.label,
          expected: !!ph.expected,
          complete: !!ph.complete,
          hasKin: !!ph.hasKin,
          hasOriginal: !!ph.hasOriginal,
          hasOverlay: !!ph.hasOverlay,
          hasUnified: !!ph.hasUnified,
          wantUnified: !!ph.wantUnified,
        })),
      })),
    };
    localStorage.setItem(DRIVE_RECALL_LS, JSON.stringify(slim));
    window.__nlDriveRecall = slim;
    window.dispatchEvent(new CustomEvent(DRIVE_RECALL_EVENT, { detail: slim }));
  } catch (err) {
    console.warn("drive recall persist failed:", err);
  }
}

function saveMergedPatients(rows) {
  const changed = rows.filter((row) => row?.record);
  if (!changed.length) return;
  try {
    const current = JSON.parse(localStorage.getItem(LS_KEY) || "[]");
    if (!Array.isArray(current) || !current.length) return;
    const byKey = new Map();
    current.forEach((p) => {
      const key = patientDriveKeyFromDemographics(p?.demographics, p?._id);
      if (key) byKey.set(key, p);
    });
    let dirty = false;
    changed.forEach((row) => {
      if (!row.patientKey || !row.record) return;
      if (byKey.has(row.patientKey)) {
        byKey.set(row.patientKey, row.record);
        dirty = true;
      }
    });
    if (!dirty) return;
    const next = current.map((p) => {
      const key = patientDriveKeyFromDemographics(p?.demographics, p?._id);
      return key && byKey.get(key) ? byKey.get(key) : p;
    });
    localStorage.setItem(LS_KEY, JSON.stringify(next));
    window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, {
      detail: { count: next.length, skipDriveRecall: true },
    }));
  } catch (err) {
    console.warn("drive recall patient merge failed:", err);
  }
}

let recallPromise = null;
let lastRecallAt = 0;
let lastSummary = null;
let recallWaiters = [];

export async function recallAnalyzedSessionsFromDrive(patients, opts = {}) {
  if (typeof opts === "function") opts = { onDone: opts };
  if (isRecallingBlocked()) {
    const waiters = recallWaiters.splice(0);
    waiters.forEach((fn) => {
      try { fn(lastSummary); } catch { /* ignore */ }
    });
    return lastSummary;
  }
  if (opts.onDone) recallWaiters.push(opts.onDone);
  if (recallPromise) return recallPromise;
  if (shouldReuseRecentRecall(lastSummary, lastRecallAt, Date.now(), opts)) {
    const waiters = recallWaiters.splice(0);
    waiters.forEach((fn) => {
      try { fn(lastSummary); } catch { /* ignore */ }
    });
    return lastSummary;
  }
  const list = (Array.isArray(patients) ? patients : []).filter(
    (p) => p && typeof p === "object" && !p._archived,
  );
  recallPromise = (async () => {
    try {
      window.dispatchEvent(new Event(DRIVE_RECALL_START_EVENT));
    } catch { /* ignore */ }
    let summary;
    try {
      const rows = await mapPool(list, recallPoolSize(), async (patient) => {
        try {
          return await recallOnePatient(patient);
        } catch (err) {
          console.warn("drive recall patient failed:", err);
          return evaluateRecallPieces(planPatientRecall(patient, []), {});
        }
      });
      summary = summarizeRecallRows(rows);
      saveMergedPatients(rows);
    } catch (err) {
      console.warn("drive recall failed:", err);
      summary = summarizeRecallRows([]);
    }
    lastRecallAt = Date.now();
    lastSummary = summary;
    persistRecallSummary(summary);
    const waiters = recallWaiters.splice(0);
    waiters.forEach((fn) => {
      try { fn(summary); } catch { /* ignore */ }
    });
    return summary;
  })().finally(() => {
    recallPromise = null;
  });
  return recallPromise;
}

export function isDriveRecallRunning() {
  return Boolean(recallPromise);
}

export function readLastDriveRecall() {
  if (window.__nlDriveRecall) return window.__nlDriveRecall;
  try {
    const raw = localStorage.getItem(DRIVE_RECALL_LS);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
