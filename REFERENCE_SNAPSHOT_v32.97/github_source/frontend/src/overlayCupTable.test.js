import { addCupToSpan, detectCupFromRgba, tableYFromCup } from "./overlayCupTable";

function setPx(data, w, x, y, r, g, b) {
  const i = (y * w + x) * 4;
  data[i] = r;
  data[i + 1] = g;
  data[i + 2] = b;
  data[i + 3] = 255;
}

function makeScene({ withCup = true, withPerson = false } = {}) {
  const W = 200;
  const H = 300;
  const data = new Uint8ClampedArray(W * H * 4);
  for (let y = 0; y < H; y += 1) {
    for (let x = 0; x < W; x += 1) {
      if (y >= 210) setPx(data, W, x, y, 168, 148, 122);
      else setPx(data, W, x, y, 210, 198, 178);
    }
  }
  if (withPerson) {
    for (let y = 80; y < 250; y += 1) {
      for (let x = 95; x < 168; x += 1) {
        setPx(data, W, x, y, 210, 160, 130);
      }
    }
  }
  if (withCup) {
    for (let y = 155; y <= 217; y += 1) {
      for (let x = 30; x <= 54; x += 1) {
        if ((y % 8) < 3) setPx(data, W, x, y, 90, 110, 140);
        else setPx(data, W, x, y, 232, 220, 200);
      }
    }
  }
  return { data, W, H };
}

test("cup detector finds the patterned cup base on the table", () => {
  const { data, W, H } = makeScene({ withCup: true });
  const cup = detectCupFromRgba(data, W, H, { palm: [0.22, 0.82] });
  expect(cup).not.toBeNull();
  expect(cup.y_base).toBeGreaterThan(0.68);
  expect(cup.y_base).toBeLessThan(0.78);
  expect(cup.x).toBeGreaterThan(0.12);
  expect(cup.x).toBeLessThan(0.32);
  expect(cup.y_base).toBeCloseTo(217 / 300, 2);
});

test("cup detector does not invent a cup on a bare wall and table", () => {
  const { data, W, H } = makeScene({ withCup: false });
  expect(detectCupFromRgba(data, W, H)).toBeNull();
});

test("a wide skin blob is not treated as a cup", () => {
  const { data, W, H } = makeScene({ withCup: false, withPerson: true });
  expect(detectCupFromRgba(data, W, H, { palm: [0.55, 0.80] })).toBeNull();
});

test("cup still wins when a person is also in frame", () => {
  const { data, W, H } = makeScene({ withCup: true, withPerson: true });
  const cup = detectCupFromRgba(data, W, H, { palm: [0.22, 0.82] });
  expect(cup).not.toBeNull();
  expect(cup.x).toBeLessThan(0.40);
  expect(cup.y_base).toBeCloseTo(217 / 300, 2);
});

test("table Y from cup is the base, rejected if far from the arm", () => {
  expect(tableYFromCup({ y_base: 0.88 }, 0.84)).toBeCloseTo(0.88, 8);
  expect(tableYFromCup({ y_base: 0.88 }, 0.50)).toBeNull();
  expect(tableYFromCup(null, 0.84)).toBeNull();
});

test("cup x expands the table span so the mark can sit on the cup-side surface", () => {
  const span = addCupToSpan({ lo: 0.20, hi: 0.45 }, { x: 0.12, x0: 0.08, x1: 0.16 });
  expect(span.lo).toBeLessThanOrEqual(0.08);
  expect(span.hi).toBeGreaterThanOrEqual(0.45);
});
