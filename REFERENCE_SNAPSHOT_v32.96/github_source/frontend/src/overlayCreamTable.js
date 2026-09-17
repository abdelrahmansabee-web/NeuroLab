/**
 * Clinic cream table under the shoulder.
 *
 * The wall is also beige, so color alone is not enough. In these seated
 * clips the wall cream fills the upper frame, the torso/chair cuts a dip,
 * then the table cream returns in the lower third — that second band is
 * the surface the clinician marks.
 */

export const SEATED_TABLE_Y_MIN = 0.56;
export const SEATED_TABLE_Y_MAX = 0.90;

export function isSeatedTableY(y) {
  const v = Number(y);
  return Number.isFinite(v) && v >= SEATED_TABLE_Y_MIN && v <= SEATED_TABLE_Y_MAX;
}

export function isClinicTableCream(r, g, b) {
  const L = 0.299 * r + 0.587 * g + 0.114 * b;
  const chroma = Math.max(r, g, b) - Math.min(r, g, b);
  const rb = r - b;
  return L > 145 && L < 215 && rb > 22 && rb < 95 && chroma < 95 && r >= g - 8;
}

export function isClinicDark(r, g, b) {
  return 0.299 * r + 0.587 * g + 0.114 * b < 80;
}

export function creamRowStats(data, width, height, y) {
  let cream = 0;
  let dark = 0;
  let n = 0;
  const step = Math.max(1, Math.floor(width / 80));
  const yy = Math.max(0, Math.min(height - 1, y));
  for (let x = 0; x < width; x += step) {
    const i = (yy * width + x) * 4;
    n += 1;
    if (isClinicTableCream(data[i], data[i + 1], data[i + 2])) cream += 1;
    if (isClinicDark(data[i], data[i + 1], data[i + 2])) dark += 1;
  }
  return { cream: cream / Math.max(n, 1), dark: dark / Math.max(n, 1) };
}

export function creamRowFractions(data, width, height, opts = {}) {
  if (!data || width < 24 || height < 24) return [];
  const y0 = Math.max(0, Math.floor(height * (opts.y0 ?? 0.42)));
  const y1 = Math.min(height - 1, Math.floor(height * (opts.y1 ?? 0.90)));
  const step = Math.max(1, Number(opts.step) || Math.max(1, Math.round(height / 80)));
  const rows = [];
  for (let y = y0; y <= y1; y += step) {
    rows.push({ yNorm: y / height, ...creamRowStats(data, width, height, y) });
  }
  return rows;
}

function creamBands(rows, thresh = 0.55) {
  const bands = [];
  let start = null;
  let lastY = null;
  for (const row of rows) {
    const y = row.yNorm;
    lastY = y;
    if (row.cream >= thresh) {
      if (start == null) start = y;
    } else if (start != null) {
      bands.push({ start, end: y });
      start = null;
    }
  }
  if (start != null) bands.push({ start, end: lastY != null ? Math.max(lastY, start + 0.02) : start + 0.08 });
  return bands;
}

function dipRecoveryY(rows, minY) {
  let sawHigh = false;
  let inDip = false;
  for (const row of rows) {
    if (row.yNorm < 0.48 || row.yNorm > 0.82) continue;
    if (!sawHigh && row.cream >= 0.65) {
      sawHigh = true;
      continue;
    }
    if (sawHigh && !inDip && row.cream <= 0.52) {
      inDip = true;
      continue;
    }
    if (inDip && row.cream >= 0.60 && row.yNorm >= minY - 0.02) {
      return row.yNorm;
    }
  }
  return null;
}

/** Y of the lower cream band (table), after the wall/torso dip. */
export function tableSurfaceYFromCreamRows(rows, opts = {}) {
  if (!rows?.length) return null;
  const shoulderY = Number(opts.shoulderY);
  const minY = Math.max(
    SEATED_TABLE_Y_MIN,
    Number.isFinite(shoulderY) ? shoulderY + 0.10 : SEATED_TABLE_Y_MIN,
  );
  const bands = creamBands(rows, 0.55).filter(
    (b) => b.end - b.start >= 0.035 && b.start <= SEATED_TABLE_Y_MAX,
  );
  const lower = bands.filter((b) => b.start >= minY - 0.03);
  let y = lower.length ? lower[lower.length - 1].start : null;
  if (y == null) {
    y = dipRecoveryY(rows, minY);
  }
  if (y == null && bands.length === 1 && bands[0].start < minY && bands[0].end > minY + 0.04) {
    y = dipRecoveryY(rows, minY);
  }
  if (!isSeatedTableY(y)) return null;
  if (y < minY) y = minY;
  return Math.min(SEATED_TABLE_Y_MAX, y + 0.02);
}

export function detectTableSurfaceYFromRgba(data, width, height, opts = {}) {
  const rows = creamRowFractions(data, width, height);
  return tableSurfaceYFromCreamRows(rows, opts);
}
