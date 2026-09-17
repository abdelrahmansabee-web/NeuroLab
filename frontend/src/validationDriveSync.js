/**
 * Cross-device validation artifacts via Google Drive (team shared folder).
 * All approved users + same account on any device restore the same patient videos.
 */

import { authHeaders } from "./AuthGate";
import { blobToBase64 } from "./downloadUtils";
import { canonicalDriveName, driveNameCandidates as identityDriveNameCandidates } from "./driveDocIdentity";

const DRIVE_FILE_MAX_BYTES = 32 * 1024 * 1024;
const LARGE_UPLOAD_BYTES = 28 * 1024 * 1024;

export function validationOriginalDriveName(phase) {
  const p = phase === "baseline" ? "healthy" : phase;
  return `${p}_validation_original.mp4`;
}

export function validationOverlayDriveName(phase) {
  const p = phase === "baseline" ? "healthy" : phase;
  return `${p}_validation_overlay.json`;
}

/** Canonical Drive playback name for baked validation (overlay burned in). */
export function validationUnifiedDriveName(phase, blobOrExt) {
  const p = phase === "baseline" ? "healthy" : phase;
  void blobOrExt;
  return `${p}_validation.mp4`;
}

export function validationKinematicsDriveName(phase) {
  const p = phase === "baseline" ? "healthy" : phase;
  return `${p}_kinematics.json`;
}

/** Alternate Drive names used by older uploads / clinic_drive_filename aliases. */
function driveNameCandidates(primaryName, subfolder) {
  void subfolder;
  return identityDriveNameCandidates(primaryName);
}

export async function fetchDriveFile(patientKey, name, subfolder = "videos", opts = {}) {
  if (!patientKey || !name) return null;
  const timeoutMs = Number(opts.timeoutMs) > 0 ? Number(opts.timeoutMs) : 180000;
  for (const candidate of driveNameCandidates(name, subfolder)) {
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), timeoutMs) : null;
    try {
      const q = new URLSearchParams({
        patientKey,
        name: candidate,
        subfolder,
        scope: "auto",
      });
      const tokenHeaders = authHeaders();
      delete tokenHeaders["Content-Type"];
      const res = await fetch(`/auth/restore-file?${q.toString()}`, {
        credentials: "same-origin",
        headers: tokenHeaders,
        signal: ctrl?.signal,
      });
      if (res.status === 404 || !res.ok) continue;
      const blob = await res.blob();
      if (blob.size > 0) return blob;
    } catch (err) {
      console.warn("validationDriveSync restore failed:", candidate, err);
    } finally {
      if (timer) clearTimeout(timer);
    }
  }
  return null;
}

async function backupBlobBase64(patientKey, name, blob, subfolder) {
  const contentBase64 = await blobToBase64(blob);
  const res = await fetch("/auth/backup-file", {
    method: "POST",
    credentials: "same-origin",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      contentBase64,
      mimeType: blob.type || "application/octet-stream",
      patientKey,
      subfolder,
      scope: "team",
    }),
  });
  if (!res.ok) return false;
  try {
    const body = await res.json();
    if (body?.skipped) {
      console.warn("Drive backup skipped:", name, body.reason);
      return false;
    }
  } catch {
    /* ignore non-JSON */
  }
  return true;
}

async function backupBlobMultipart(patientKey, name, blob, subfolder) {
  const fd = new FormData();
  fd.append("file", blob, name);
  fd.append("patientKey", patientKey);
  fd.append("name", name);
  fd.append("subfolder", subfolder);
  fd.append("scope", "team");
  const res = await fetch("/auth/backup-file-upload", {
    method: "POST",
    credentials: "same-origin",
    headers: authHeaders(),
    body: fd,
  });
  if (!res.ok) return false;
  try {
    const body = await res.json();
    if (body?.skipped) {
      console.warn("Drive backup skipped:", name, body.reason);
      return false;
    }
  } catch {
    /* ignore */
  }
  return true;
}

export async function backupValidationArtifactsToDrive(patientKey, phase, record = {}) {
  if (!patientKey || !phase) return;
  const tasks = [];

  if (record.overlay?.frames?.length) {
    const overlayBlob = new Blob([JSON.stringify(record.overlay)], { type: "application/json" });
    if (overlayBlob.size <= DRIVE_FILE_MAX_BYTES) {
      tasks.push(
        backupBlobBase64(patientKey, validationOverlayDriveName(phase), overlayBlob, "data"),
      );
    }
  }

  if (record.kinematicsSnapshot && typeof record.kinematicsSnapshot === "object") {
    const kinBlob = new Blob([JSON.stringify(record.kinematicsSnapshot)], {
      type: "application/json",
    });
    if (kinBlob.size <= DRIVE_FILE_MAX_BYTES) {
      tasks.push(
        backupBlobBase64(patientKey, validationKinematicsDriveName(phase), kinBlob, "data"),
      );
    }
  }

  if (record.originalVideoBlob instanceof Blob && record.originalVideoBlob.size > 0) {
    const name = validationOriginalDriveName(phase);
    const blob = record.originalVideoBlob;
    if (blob.size > LARGE_UPLOAD_BYTES) {
      tasks.push(backupBlobMultipart(patientKey, name, blob, "videos"));
    } else if (blob.size <= DRIVE_FILE_MAX_BYTES) {
      tasks.push(backupBlobBase64(patientKey, name, blob, "videos"));
    }
  }

  if (record.unifiedVideoBlob instanceof Blob && record.unifiedVideoBlob.size > 0) {
    const name = validationUnifiedDriveName(phase, record.unifiedVideoBlob);
    const blob = record.unifiedVideoBlob;
    if (blob.size > LARGE_UPLOAD_BYTES) {
      tasks.push(backupBlobMultipart(patientKey, name, blob, "videos"));
    } else if (blob.size <= DRIVE_FILE_MAX_BYTES) {
      tasks.push(backupBlobBase64(patientKey, name, blob, "videos"));
    }
  }

  await Promise.allSettled(tasks);
}

/**
 * Pull validation bundle from Drive into Blobs / overlay object.
 */
export async function restoreValidationArtifactsFromDrive(patientKey, phase, needs = {}) {
  if (!patientKey || !phase) return null;
  const out = {};
  const wantOverlay = needs.overlay !== false;
  const wantOriginal = needs.original !== false;
  const wantUnified = needs.unified !== false;
  const wantKinematics = needs.kinematics === true;

  if (wantOriginal) {
    const blob = await fetchDriveFile(patientKey, validationOriginalDriveName(phase), "videos");
    if (blob) out.originalVideoBlob = blob;
  }

  if (wantOverlay) {
    const blob = await fetchDriveFile(patientKey, validationOverlayDriveName(phase), "data");
    if (blob) {
      try {
        const text = await blob.text();
        const parsed = JSON.parse(text);
        if (parsed?.frames?.length) out.overlay = parsed;
      } catch (err) {
        console.warn("validation overlay JSON parse failed:", err);
      }
    }
  }

  if (wantKinematics) {
    const blob = await fetchDriveFile(patientKey, validationKinematicsDriveName(phase), "data");
    if (blob) {
      try {
        const text = await blob.text();
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed === "object") out.kinematicsSnapshot = parsed;
      } catch (err) {
        console.warn("kinematics JSON parse failed:", err);
      }
    }
  }

  if (wantUnified) {
    const blob = await fetchDriveFile(patientKey, validationUnifiedDriveName(phase), "videos");
    if (blob) out.unifiedVideoBlob = blob;
  }

  if (
    !out.overlay
    && !out.originalVideoBlob
    && !out.unifiedVideoBlob
    && !out.kinematicsSnapshot
  ) {
    return null;
  }
  return out;
}
