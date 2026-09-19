/**
 * Persistent validation artifacts per patient session (IndexedDB).
 * Survives page reload, HF ephemeral storage loss, and session reload.
 *
 * iOS Home Screen apps cannot store Blob objects in IndexedDB reliably.
 * Videos are frozen to ArrayBuffer on write and revived to Blob on read.
 */

const DB_NAME = "neurolab_validation_v1";
const STORE = "artifacts";
const DB_VERSION = 1;
export const MEDIA_BUF_MARK = "__nlArrBuf";

let dbPromise = null;
let persistAsked = false;

export function requestClinicPersistentStorage() {
  if (persistAsked) return Promise.resolve(false);
  persistAsked = true;
  try {
    if (typeof navigator !== "undefined" && navigator.storage?.persist) {
      return navigator.storage.persist().catch(() => false);
    }
  } catch { /* ignore */ }
  return Promise.resolve(false);
}

export function freezeMediaBlob(blob) {
  if (!(blob instanceof Blob) || blob.size <= 0) return Promise.resolve(blob);
  const wrap = (data) => ({
    [MEDIA_BUF_MARK]: 1,
    type: blob.type || "video/mp4",
    data,
  });
  if (typeof blob.arrayBuffer === "function") {
    return blob.arrayBuffer().then(wrap);
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(wrap(reader.result));
    reader.onerror = () => reject(reader.error || new Error("read blob failed"));
    reader.readAsArrayBuffer(blob);
  });
}

export function reviveMediaBlob(value) {
  if (value instanceof Blob) return value;
  if (value && value[MEDIA_BUF_MARK] && value.data != null) {
    return new Blob([value.data], { type: value.type || "video/mp4" });
  }
  return value;
}

function reviveRecord(record) {
  if (!record || typeof record !== "object") return record;
  return {
    ...record,
    originalVideoBlob: reviveMediaBlob(record.originalVideoBlob),
    unifiedVideoBlob: reviveMediaBlob(record.unifiedVideoBlob),
  };
}

async function freezeRecord(record) {
  const originalVideoBlob = await freezeMediaBlob(record.originalVideoBlob);
  const unifiedVideoBlob = await freezeMediaBlob(record.unifiedVideoBlob);
  return { ...record, originalVideoBlob, unifiedVideoBlob };
}

function openDb() {
  if (dbPromise) return dbPromise;
  requestClinicPersistentStorage();
  dbPromise = new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      dbPromise = null;
      reject(new Error("IndexedDB unavailable"));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => {
      dbPromise = null;
      reject(req.error || new Error("IndexedDB open failed"));
    };
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

function putRecord(db, payload) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => reject(tx.error);
    tx.objectStore(STORE).put(payload);
  });
}

export function validationCacheId(patientKey, phase) {
  const pk = String(patientKey || "anon").trim() || "anon";
  const ph = String(phase || "").trim();
  return `${pk}::${ph}`;
}

export async function loadValidationSessionArtifact(patientKey, phase) {
  try {
    const db = await openDb();
    const raw = await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).get(validationCacheId(patientKey, phase));
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
    return reviveRecord(raw);
  } catch (err) {
    console.warn("validationSessionCache load failed:", err);
    return null;
  }
}

export async function saveValidationSessionArtifact(record) {
  if (!record?.patientKey || !record?.phase) return false;
  try {
    const db = await openDb();
    const frozen = await freezeRecord(record);
    const payload = {
      ...frozen,
      id: validationCacheId(record.patientKey, record.phase),
      savedAt: record.savedAt || Date.now(),
    };
    try {
      await putRecord(db, payload);
      return true;
    } catch (err) {
      console.warn("validationSessionCache full save failed, retrying without videos:", err);
      try {
        await putRecord(db, { ...payload, unifiedVideoBlob: null });
        return true;
      } catch {
        await putRecord(db, { ...payload, unifiedVideoBlob: null, originalVideoBlob: null });
        return true;
      }
    }
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
 *  Missing csv on the live result may still restore this patient's IDB/Drive
 *  artifacts. A different csv name is another analysis — do not paint it.
 *  Space path drift is restored from the patient-scoped Drive folder instead.
 */
export function validationCacheMatchesResult(cached, result, opts = {}) {
  if (!cached) return false;
  const expectedKey = String(opts.patientKey || "").trim();
  if (expectedKey) {
    const cachedKey = String(cached.patientKey || "").trim();
    if (!cachedKey || cachedKey !== expectedKey) return false;
  }
  const relax = opts.relaxCsvMatch === true;
  const original = reviveMediaBlob(cached.originalVideoBlob);
  const unified = reviveMediaBlob(cached.unifiedVideoBlob);
  const hasArtifact =
    Boolean(cached.overlay?.frames?.length)
    || (original instanceof Blob && original.size > 0)
    || (unified instanceof Blob && unified.size > 0)
    || Boolean(cached.kinematicsSnapshot && typeof cached.kinematicsSnapshot === "object");
  if (!result?.csv_filename) {
    return relax ? hasArtifact : false;
  }
  if (cached.csvFilename && cached.csvFilename !== result.csv_filename) {
    return false;
  }
  return true;
}
