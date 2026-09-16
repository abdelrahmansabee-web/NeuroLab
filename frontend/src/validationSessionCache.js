/**
 * Persistent validation artifacts per patient session (IndexedDB).
 * Survives page reload, HF ephemeral storage loss, and session reload.
 */

const DB_NAME = "neurolab_validation_v1";
const STORE = "artifacts";
const DB_VERSION = 1;

let dbPromise = null;

function openDb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB unavailable"));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => reject(req.error || new Error("IndexedDB open failed"));
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
  });
  return dbPromise;
}

export function validationCacheId(patientKey, phase) {
  const pk = String(patientKey || "anon").trim() || "anon";
  const ph = String(phase || "").trim();
  return `${pk}::${ph}`;
}

export async function loadValidationSessionArtifact(patientKey, phase) {
  try {
    const db = await openDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).get(validationCacheId(patientKey, phase));
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
  } catch (err) {
    console.warn("validationSessionCache load failed:", err);
    return null;
  }
}

export async function saveValidationSessionArtifact(record) {
  if (!record?.patientKey || !record?.phase) return false;
  try {
    const db = await openDb();
    const payload = {
      ...record,
      id: validationCacheId(record.patientKey, record.phase),
      savedAt: record.savedAt || Date.now(),
    };
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
      tx.objectStore(STORE).put(payload);
    });
    return true;
  } catch (err) {
    console.warn("validationSessionCache save failed:", err);
    return false;
  }
}

/** Merge partial updates (overlay blob, unified video, etc.) into existing cache row. */
export async function patchValidationSessionArtifact(patientKey, phase, partial) {
  const existing = (await loadValidationSessionArtifact(patientKey, phase)) || {
    patientKey,
    phase,
  };
  return saveValidationSessionArtifact({ ...existing, ...partial, patientKey, phase });
}

export async function blobFromObjectUrl(objectUrl) {
  if (!objectUrl) return null;
  try {
    const res = await fetch(objectUrl);
    if (!res.ok) return null;
    return await res.blob();
  } catch {
    return null;
  }
}

/** Don't rewrite a live overlay with the same IDB copy — that remounts the player. */
export function shouldHydrateOverlayIntoState(prevOverlay, incomingOverlay) {
  if (!incomingOverlay?.frames?.length) return false;
  if (prevOverlay?.frames?.length) return false;
  return true;
}

/** Don't revoke a playing blob URL just because Drive recall re-applied the same bytes. */
export function shouldHydrateMediaBlobIntoState(prevObjectUrl, incomingBlob) {
  if (!(incomingBlob instanceof Blob) || incomingBlob.size <= 0) return false;
  if (typeof prevObjectUrl === "string" && prevObjectUrl.length > 0) return false;
  return true;
}

/** Reject stale cache rows from a previous analyze on the same patient/phase.
 *  When HF ephemeral files are gone, allow restore if the cached row has usable
 *  overlay/video even if csv_filename no longer matches the live Space path.
 */
export function validationCacheMatchesResult(cached, result, opts = {}) {
  if (!cached) return false;
  const relax = opts.relaxCsvMatch === true;
  const hasArtifact =
    Boolean(cached.overlay?.frames?.length)
    || (cached.originalVideoBlob instanceof Blob && cached.originalVideoBlob.size > 0)
    || (cached.unifiedVideoBlob instanceof Blob && cached.unifiedVideoBlob.size > 0)
    || Boolean(cached.kinematicsSnapshot && typeof cached.kinematicsSnapshot === "object");
  if (!result?.csv_filename) {
    return relax ? hasArtifact : false;
  }
  if (cached.csvFilename && cached.csvFilename !== result.csv_filename) {
    // After Space rebuild, CSV path often changes — still reuse Drive/IDB artifacts.
    return relax ? hasArtifact : false;
  }
  return true;
}
