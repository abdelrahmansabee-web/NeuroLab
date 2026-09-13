/**
 * Cross-device validation artifacts via Google Drive (team shared folder).
 * All approved users + same account on any device restore the same patient videos.
 */

import { authHeaders } from "./AuthGate";
import { blobToBase64 } from "./downloadUtils";

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
  let ext = "mp4";
  if (typeof blobOrExt === "string") {
    ext = blobOrExt.replace(/^\./, "") || "mp4";
  } else if (blobOrExt && typeof blobOrExt === "object" && blobOrExt.type) {
    if (String(blobOrExt.type).includes("webm")) ext = "webm";
  }
  return `${p}_validation.${ext}`;
}

export function validationKinematicsDriveName(phase) {
  const p = phase === "baseline" ? "healthy" : phase;
  return `${p}_kinematics.json`;
}

/** Alternate Drive names used by older uploads / clinic_drive_filename aliases. */
function driveNameCandidates(primaryName, subfolder) {
  const names = [primaryName];
  const lower = String(primaryName || "").toLowerCase();
  if (lower.endsWith("_validation_original.mp4")) {
    const phase = primaryName.slice(0, -"_validation_original.mp4".length);
    names.push(`${phase}_original.mp4`, `${phase}_validation_original.mp4`);
  }
  if (/^(pre|post|healthy|baseline)_validation\.(mp4|webm)$/i.test(lower)) {
    const m = lower.match(/^(pre|post|healthy|baseline)_validation\.(mp4|webm)$/i);
    if (m) {
      const phase = m[1] === "baseline" ? "healthy" : m[1];
      const ext = m[2];
      names.push(
        `${phase}_validation.${ext}`,
        `${phase}_validation_unified.${ext}`,
        `${phase}_validation.mp4`,
        `${phase}_validation.webm`,
        `${phase}_validation_unified.mp4`,
        `${phase}_validation_unified.webm`,
      );
    }
  }
  if (lower.endsWith("_validation_unified.mp4") || lower.endsWith("_validation_unified.webm")) {
    const phase = primaryName.replace(/_validation_unified\.(mp4|webm)$/i, "");
    const short = phase === "baseline" || phase === "healthy" ? "healthy" : phase;
    names.push(`${short}_validation.mp4`, `${short}_validation.webm`);
  }
  return [...new Set(names.filter(Boolean))];
}

async function fetchDriveFile(patientKey, name, subfolder = "videos") {
  if (!patientKey || !name) return null;
  for (const candidate of driveNameCandidates(name, subfolder)) {
    try {
      const q = new URLSearchParams({
        patientKey,
        name: candidate,
        subfolder,
        scope: "auto",
      });
      const res = await fetch(`/auth/restore-file?${q.toString()}`, {
        credentials: "same-origin",
        headers: authHeaders(),
      });
      if (res.status === 404 || !res.ok) continue;
      const blob = await res.blob();
      if (blob.size > 0) return blob;
    } catch (err) {
      console.warn("validationDriveSync restore failed:", candidate, err);
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

  if (wantOriginal) {
    const blob = await fetchDriveFile(patientKey, validationOriginalDriveName(phase), "videos");
    if (blob) out.originalVideoBlob = blob;
  }

  if (wantUnified) {
    const blob = await fetchDriveFile(patientKey, validationUnifiedDriveName(phase, "mp4"), "videos")
      || await fetchDriveFile(patientKey, validationUnifiedDriveName(phase, "webm"), "videos");
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
