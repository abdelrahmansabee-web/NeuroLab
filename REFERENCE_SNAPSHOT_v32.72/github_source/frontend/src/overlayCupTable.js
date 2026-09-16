/**
 * Clinic cup as a table cue: the cup sits on the table, so its base is the surface.
 * Runs on RGBA pixels (live video or a still). No overlay tracking changes.
 */

function lum(r, g, b) {
  return 0.299 * r + 0.587 * g + 0.114 * b;
}

function colorDist(r, g, b, wr, wg, wb) {
  return Math.abs(r - wr) + Math.abs(g - wg) + Math.abs(b - wb);
}

function sampleWallRgb(data, width, height) {
  const y0 = Math.max(1, Math.floor(height * 0.02));
  const y1 = Math.max(y0 + 1, Math.floor(height * 0.16));
  const x0 = Math.floor(width * 0.18);
  const x1 = Math.floor(width * 0.82);
  const rs = [];
  const gs = [];
  const bs = [];
  const stepY = Math.max(1, Math.floor((y1 - y0) / 10));
  const stepX = Math.max(1, Math.floor((x1 - x0) / 18));
  for (let y = y0; y < y1; y += stepY) {
    for (let x = x0; x < x1; x += stepX) {
      const i = (y * width + x) * 4;
      rs.push(data[i]);
      gs.push(data[i + 1]);
      bs.push(data[i + 2]);
    }
  }
  const mid = (arr) => {
    if (!arr.length) return 200;
    const s = arr.slice().sort((a, b) => a - b);
    return s[Math.floor(s.length / 2)];
  };
  return { r: mid(rs), g: mid(gs), b: mid(bs) };
}

function isPrintPixel(r, g, b) {
  const L = lum(r, g, b);
  return b > r + 6 && b >= g - 10 && L > 48 && L < 205;
}

function isCreamBody(r, g, b, wall, dWall) {
  const L = lum(r, g, b);
  const chroma = Math.max(r, g, b) - Math.min(r, g, b);
  return L >= 172 && (r - b) < 52 && chroma < 78 && dWall > 16;
}

function isCupPixel(r, g, b, wall) {
  const dWall = colorDist(r, g, b, wall.r, wall.g, wall.b);
  return isPrintPixel(r, g, b) || isCreamBody(r, g, b, wall, dWall);
}

function cupPatternScore(data, width, height, blob) {
  let n = 0;
  let print = 0;
  let cream = 0;
  let sumLum = 0;
  let sumLum2 = 0;
  const stepX = Math.max(1, Math.floor((blob.x1 - blob.x0 + 1) / 14));
  const wall = blob.wall;
  for (let y = blob.y0; y <= blob.y1; y += 2) {
    for (let x = blob.x0; x <= blob.x1; x += stepX) {
      const i = (y * width + x) * 4;
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      n += 1;
      const L = lum(r, g, b);
      sumLum += L;
      sumLum2 += L * L;
      if (isPrintPixel(r, g, b)) print += 1;
      const dWall = colorDist(r, g, b, wall.r, wall.g, wall.b);
      if (isCreamBody(r, g, b, wall, dWall)) cream += 1;
    }
  }
  const mean = sumLum / Math.max(n, 1);
  const variance = sumLum2 / Math.max(n, 1) - mean * mean;
  return {
    printFrac: print / Math.max(n, 1),
    creamFrac: cream / Math.max(n, 1),
    varScore: Math.sqrt(Math.max(0, variance)),
  };
}

function sitsOnDarkerSurface(data, width, height, blob) {
  const yBelow = Math.min(height - 1, blob.y1 + Math.max(2, Math.round(height * 0.012)));
  if (yBelow <= blob.y1) return true;
  let body = 0;
  let below = 0;
  let nB = 0;
  let nL = 0;
  const midY = Math.floor((blob.y0 + blob.y1) * 0.5);
  const x0 = blob.x0;
  const x1 = blob.x1;
  for (let x = x0; x <= x1; x += 2) {
    const ib = (midY * width + x) * 4;
    body += lum(data[ib], data[ib + 1], data[ib + 2]);
    nB += 1;
    const il = (yBelow * width + x) * 4;
    below += lum(data[il], data[il + 1], data[il + 2]);
    nL += 1;
  }
  if (!nB || !nL) return true;
  return (below / nL) < (body / nB) - 6;
}

/**
 * Find a paper cup whose base sits on the table.
 * @returns {{x:number,x0:number,x1:number,y_top:number,y_base:number}|null}
 */
export function detectCupFromRgba(data, width, height, opts = {}) {
  if (!data || width < 24 || height < 24) return null;
  const wall = sampleWallRgb(data, width, height);
  const palm = opts.palm;
  const yScan0 = Math.floor(height * 0.26);
  const yScan1 = Math.floor(height * 0.975);
  const xScan0 = Math.floor(width * 0.015);
  const xScan1 = Math.floor(width * 0.985);
  const minRun = Math.max(6, Math.floor(height * 0.055));
  const colRuns = new Array(width);

  for (let x = xScan0; x < xScan1; x += 1) {
    let best = null;
    let runStart = -1;
    for (let y = yScan0; y <= yScan1; y += 1) {
      const i = (y * width + x) * 4;
      const ok = isCupPixel(data[i], data[i + 1], data[i + 2], wall);
      if (ok) {
        if (runStart < 0) runStart = y;
      } else if (runStart >= 0) {
        const len = y - runStart;
        if (!best || len > best.len) best = { y0: runStart, y1: y - 1, len };
        runStart = -1;
      }
    }
    if (runStart >= 0) {
      const len = yScan1 - runStart + 1;
      if (!best || len > best.len) best = { y0: runStart, y1: yScan1, len };
    }
    colRuns[x] = best && best.len >= minRun ? best : null;
  }

  const blobs = [];
  let cur = null;
  for (let x = xScan0; x < xScan1; x += 1) {
    const run = colRuns[x];
    if (!run) {
      if (cur) {
        blobs.push(cur);
        cur = null;
      }
      continue;
    }
    if (!cur) {
      cur = {
        x0: x, x1: x, y0: run.y0, y1: run.y1, cols: 1, wall,
      };
      continue;
    }
    const overlap = Math.min(cur.y1, run.y1) - Math.max(cur.y0, run.y0);
    const minH = Math.min(cur.y1 - cur.y0, run.y1 - run.y0);
    if (minH > 0 && overlap > minH * 0.42) {
      cur.x1 = x;
      cur.y0 = Math.min(cur.y0, run.y0);
      cur.y1 = Math.max(cur.y1, run.y1);
      cur.cols += 1;
    } else {
      blobs.push(cur);
      cur = {
        x0: x, x1: x, y0: run.y0, y1: run.y1, cols: 1, wall,
      };
    }
  }
  if (cur) blobs.push(cur);

  let bestBlob = null;
  let bestScore = -1;
  for (const blob of blobs) {
    const bw = blob.x1 - blob.x0 + 1;
    const bh = blob.y1 - blob.y0 + 1;
    const wn = bw / width;
    const hn = bh / height;
    if (wn < 0.028 || wn > 0.24) continue;
    if (hn < 0.065 || hn > 0.44) continue;
    const aspect = bh / bw;
    if (aspect < 1.2 || aspect > 6.8) continue;
    const yBottom = blob.y1 / height;
    const yTop = blob.y0 / height;
    if (yBottom < 0.50 || yBottom > 0.985) continue;
    if (yTop < 0.16 || yTop > 0.84) continue;

    const pattern = cupPatternScore(data, width, height, blob);
    if (pattern.creamFrac < 0.18 && pattern.printFrac < 0.04) continue;
    if (pattern.printFrac < 0.015 && pattern.varScore < 10 && pattern.creamFrac < 0.40) continue;

    let score = aspect * 6 + pattern.printFrac * 90 + pattern.creamFrac * 24 + pattern.varScore * 0.35;
    if (sitsOnDarkerSurface(data, width, height, blob)) score += 28;
    const cx = (blob.x0 + blob.x1) / 2 / width;
    const edgeBias = Math.min(cx, 1 - cx);
    score += (0.38 - Math.min(edgeBias, 0.38)) * 36;
    if (palm && palm[0] != null && Number.isFinite(Number(palm[0]))) {
      const dx = Math.abs(cx - Number(palm[0]));
      const py = palm[1] != null && Number.isFinite(Number(palm[1])) ? Number(palm[1]) : yBottom;
      const dy = Math.abs(yBottom - py);
      if (dx < 0.48) score += (0.48 - dx) * 55;
      if (dy < 0.24) score += (0.24 - dy) * 42;
    }
    if (score > bestScore) {
      bestScore = score;
      bestBlob = blob;
    }
  }
  if (!bestBlob) return null;
  return {
    x: (bestBlob.x0 + bestBlob.x1) / 2 / width,
    x0: bestBlob.x0 / width,
    x1: bestBlob.x1 / width,
    y_top: bestBlob.y0 / height,
    y_base: bestBlob.y1 / height,
  };
}

/** Table Y from a detected cup, rejected if it cannot be a supporting surface. */
export function tableYFromCup(cup, armY = null) {
  if (!cup || cup.y_base == null || !Number.isFinite(Number(cup.y_base))) return null;
  const y = Number(cup.y_base);
  if (y < 0.45 || y > 0.99) return null;
  if (armY != null && Number.isFinite(Number(armY)) && Math.abs(y - Number(armY)) > 0.22) {
    return null;
  }
  return y;
}

export function addCupToSpan(span, cup) {
  if (!cup) return span;
  const xs = [];
  if (span) {
    xs.push(span.lo, span.hi);
  }
  ["x", "x0", "x1"].forEach((k) => {
    if (cup[k] != null && Number.isFinite(Number(cup[k]))) xs.push(Number(cup[k]));
  });
  if (!xs.length) return span;
  return { lo: Math.min(...xs), hi: Math.max(...xs) };
}
