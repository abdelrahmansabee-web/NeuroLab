import {
  detectTableSurfaceYFromRgba,
  isClinicTableCream,
  isSeatedTableY,
  tableSurfaceYFromCreamRows,
} from "./overlayCreamTable";

function setPx(data, w, x, y, r, g, b) {
  const i = (y * w + x) * 4;
  data[i] = r;
  data[i + 1] = g;
  data[i + 2] = b;
  data[i + 3] = 255;
}

/** Wall cream on top, torso/chair dip, cream table, dark apron — like the clinic clips. */
function makeClinicScene() {
  const W = 220;
  const H = 320;
  const data = new Uint8ClampedArray(W * H * 4);
  for (let y = 0; y < H; y += 1) {
    for (let x = 0; x < W; x += 1) {
      if (y < 165) setPx(data, W, x, y, 180, 160, 125);
      else if (y < 210) {
        if (x < 70) setPx(data, W, x, y, 45, 40, 35);
        else setPx(data, W, x, y, 236, 228, 218);
      } else if (y < 270) setPx(data, W, x, y, 198, 168, 128);
      else setPx(data, W, x, y, 52, 42, 34);
    }
  }
  return { data, W, H };
}

test("cream table Y is the lower band after the torso dip, not the wall", () => {
  const { data, W, H } = makeClinicScene();
  const y = detectTableSurfaceYFromRgba(data, W, H, { shoulderY: 0.36 });
  expect(y).not.toBeNull();
  expect(y).toBeGreaterThanOrEqual(210 / H - 0.03);
  expect(y).toBeLessThan(0.78);
  expect(isSeatedTableY(y)).toBe(true);
});

test("wall-only cream is not a seated table", () => {
  const W = 160;
  const H = 220;
  const data = new Uint8ClampedArray(W * H * 4);
  for (let y = 0; y < H; y += 1) {
    for (let x = 0; x < W; x += 1) setPx(data, W, x, y, 180, 160, 125);
  }
  expect(detectTableSurfaceYFromRgba(data, W, H, { shoulderY: 0.30 })).toBeNull();
});

test("clinic cream pixels match the beige table, not the black chair", () => {
  expect(isClinicTableCream(198, 168, 128)).toBe(true);
  expect(isClinicTableCream(180, 160, 125)).toBe(true);
  expect(isClinicTableCream(45, 40, 35)).toBe(false);
  expect(isClinicTableCream(236, 228, 218)).toBe(false);
});

test("row helper picks the last cream band below the shoulder", () => {
  const rows = [
    { yNorm: 0.44, cream: 0.84, dark: 0 },
    { yNorm: 0.50, cream: 0.80, dark: 0 },
    { yNorm: 0.58, cream: 0.30, dark: 0.2 },
    { yNorm: 0.62, cream: 0.28, dark: 0.18 },
    { yNorm: 0.67, cream: 0.76, dark: 0.08 },
    { yNorm: 0.74, cream: 0.72, dark: 0.16 },
    { yNorm: 0.82, cream: 0.40, dark: 0.40 },
  ];
  expect(tableSurfaceYFromCreamRows(rows, { shoulderY: 0.34 })).toBeCloseTo(0.69, 8);
});
