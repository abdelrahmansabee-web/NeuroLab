import {
  overlayPalmChordResidual,
  overlayPalmPathSpeeds,
  overlayPalmPathStats,
} from "./overlayPalmPath";

test("straight overlay palm path has straightness 1 and zero chord residual", () => {
  const frames = Array.from({ length: 11 }, (_, i) => ({ palm: [0.2 + i * 0.05, 0.5] }));
  const stats = overlayPalmPathStats(frames, 0, 10);
  expect(stats.straightness).toBeCloseTo(1, 8);
  const { rx, ry } = overlayPalmChordResidual(stats.px, stats.py);
  for (let i = 0; i < rx.length; i += 1) {
    expect(Math.abs(rx[i])).toBeLessThan(1e-12);
    expect(Math.abs(ry[i])).toBeLessThan(1e-12);
  }
});

test("path speeds are the same hypot segments as pathLength", () => {
  const frames = [
    { palm: [0, 0] },
    { palm: [3, 4] },
    { palm: [3, 4] },
  ];
  const stats = overlayPalmPathStats(frames, 0, 2);
  expect(stats.pathLength).toBeCloseTo(5, 8);
  const spd = overlayPalmPathSpeeds(stats.px, stats.py, 10);
  expect(spd[1]).toBeCloseTo(50, 8);
  expect(spd[2]).toBeCloseTo(0, 8);
});

test("missing palm is not a jump through 0,0", () => {
  const frames = [
    { palm: [0.2, 0.2] },
    { palm: null },
    { palm: [0.4, 0.2] },
  ];
  const stats = overlayPalmPathStats(frames, 0, 2);
  expect(stats.pathLength).toBeCloseTo(0.2, 8);
  expect(stats.straightness).toBeCloseTo(1, 8);
});
