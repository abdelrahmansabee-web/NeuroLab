/**
 * Clinician-placed table surface. Color detectors cannot see a beige table
 * on a beige wall; this stores the point the clinician puts on the video.
 */

export const TABLE_USER_MARK_PREFIX = "nl-table-user-mark:";

function tableUserMarkCandidateKeys(overlayData, videoUrl) {
  const keys = [];
  const file = String(overlayData?.overlay_video_filename || overlayData?.debug_video_path || "")
    .split(/[/\\]/)
    .pop()
    .trim();
  if (file) keys.push(`${TABLE_USER_MARK_PREFIX}${file}`);
  const url = String(videoUrl || "").split("?")[0];
  if (url) keys.push(`${TABLE_USER_MARK_PREFIX}${url}`);
  if (!keys.length) keys.push(`${TABLE_USER_MARK_PREFIX}unknown`);
  return [...new Set(keys)];
}

export function tableUserMarkStorageKey(overlayData, videoUrl) {
  return tableUserMarkCandidateKeys(overlayData, videoUrl)[0];
}

export function clampTableUserMark(p) {
  if (!p) return null;
  const x = Number(p.x);
  const y = Number(p.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return {
    x: Math.max(0.01, Math.min(0.99, x)),
    y: Math.max(0.02, Math.min(0.98, y)),
    source: "user",
  };
}

export function loadTableUserMark(overlayData, videoUrl) {
  if (typeof localStorage === "undefined") return null;
  for (const key of tableUserMarkCandidateKeys(overlayData, videoUrl)) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      const parsed = clampTableUserMark(JSON.parse(raw));
      if (parsed) return parsed;
    } catch (_err) {
      /* next key */
    }
  }
  return null;
}

export function saveTableUserMark(overlayData, videoUrl, mark) {
  const next = clampTableUserMark(mark);
  if (!next || typeof localStorage === "undefined") return next;
  const payload = JSON.stringify({ x: next.x, y: next.y, source: "user" });
  for (const key of tableUserMarkCandidateKeys(overlayData, videoUrl)) {
    try {
      localStorage.setItem(key, payload);
    } catch (_err) {
      /* quota */
    }
  }
  return next;
}

export function clearTableUserMark(overlayData, videoUrl) {
  if (typeof localStorage === "undefined") return;
  for (const key of tableUserMarkCandidateKeys(overlayData, videoUrl)) {
    try {
      localStorage.removeItem(key);
    } catch (_err) {
      /* ignore */
    }
  }
}

/** Map a pointer on the overlay canvas box into 0–1 overlay coordinates. */
export function clientPointToOverlayNorm(clientX, clientY, rect, { clampToFrame = false } = {}) {
  if (!rect || rect.width < 1 || rect.height < 1) return null;
  if (!Number.isFinite(Number(clientX)) || !Number.isFinite(Number(clientY))) return null;
  const x = (Number(clientX) - rect.left) / rect.width;
  const y = (Number(clientY) - rect.top) / rect.height;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  if (clampToFrame) {
    return {
      x: Math.max(0, Math.min(1, x)),
      y: Math.max(0, Math.min(1, y)),
    };
  }
  if (x < 0 || x > 1 || y < 0 || y > 1) return null;
  return { x, y };
}

export function tableMarkHitGeom(g, cw) {
  if (!g || !(cw > 0) || g.xNorm == null || g.yNorm == null) return null;
  return {
    xNorm: Number(g.xNorm),
    yNorm: Number(g.yNorm),
    x0Norm: Number(g.x0) / cw,
    x1Norm: Number(g.x1) / cw,
  };
}

export function hitTableMark(norm, geom, { cssW, cssH, coarse = false } = {}) {
  if (!norm || !geom || !(cssW > 0) || !(cssH > 0)) return false;
  const hitR = coarse ? 28 : 16;
  const dx = (norm.x - geom.xNorm) * cssW;
  const dy = (norm.y - geom.yNorm) * cssH;
  if (dx * dx + dy * dy <= hitR * hitR) return true;
  const padX = Math.max(0.035, hitR / cssW);
  const padY = hitR / cssH;
  const lo = Math.min(geom.x0Norm, geom.x1Norm) - padX;
  const hi = Math.max(geom.x0Norm, geom.x1Norm) + padX;
  if (norm.x < lo || norm.x > hi) return false;
  return Math.abs(norm.y - geom.yNorm) <= padY;
}
