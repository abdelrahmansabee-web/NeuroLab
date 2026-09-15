import {
  overlayPauseSpeedThreshold,
} from "./validationPanelMetrics";
import {
  classifyPalmPath,
  nvpPeakIndicesOnPath,
  resolveShoulderRestY,
  robustShoulderNorm,
  snapTableYToRestArm,
  straightnessEndpoints,
  tableLineUnderShoulder,
  tablePointUnderShoulder,
  tableSurfaceYAtX,
  trunkHorizontalDispNorm,
} from "./overlayPanelMarks";

function frame({ t, palm, speed, trunk, shoulder, lshoulder, rshoulder }) {
  return {
    time: t,
    palm,
    trunk: trunk || [palm[0] * 0.2, palm[1]],
    shoulder: shoulder || [0.3, 0.25],
    lshoulder: lshoulder || [0.22, 0.26],
    rshoulder: rshoulder || [0.38, 0.24],
    speed,
  };
}

function makeOverlay() {
  const fps = 60;
  const frames = [];
  for (let i = 0; i < 20; i += 1) {
    const moving = i >= 4 && i <= 14;
    frames.push(frame({
      t: i / fps,
      palm: [0.2 + i * 0.02, 0.72],
      speed: i === 8 ? 0.2 : (moving ? 20 : 0.2),
      trunk: [0.12 + (i >= 4 ? (Math.min(i, 14) - 4) * 0.004 : 0), 0.32],
    }));
  }
  return {
    fps,
    frames,
    affected_side: "right",
    movement_window: { start_idx: 4, end_idx: 14 },
    peak_frames: [6, 10, 18],
    table_surface_y: 0.72,
    start_palm: [0.2, 0.72],
  };
}

test("pause threshold is 5% of whole-clip peak hand speed", () => {
  const overlay = makeOverlay();
  expect(overlayPauseSpeedThreshold(overlay.frames)).toBeCloseTo(1, 8);
});

test("path marks pause only on frames below the panel speed gate", () => {
  const overlay = makeOverlay();
  const thresh = overlayPauseSpeedThreshold(overlay.frames);
  const pts = classifyPalmPath(overlay.frames, 4, 14, thresh);
  const paused = pts.filter((p) => p.paused).map((p) => p.i);
  expect(paused).toEqual([8]);
});

test("NVP dots are peak_frames on the path up to now, not after the window", () => {
  expect(nvpPeakIndicesOnPath([6, 10, 18], 4, 14)).toEqual([6, 10]);
  expect(nvpPeakIndicesOnPath([6, 10, 18], 4, 6)).toEqual([6]);
});

test("straightness chord uses window start palm to current palm", () => {
  const overlay = makeOverlay();
  const chord = straightnessEndpoints(overlay.frames, 4, 14);
  expect(chord.start).toEqual(overlay.frames[4].palm);
  expect(chord.end).toEqual(overlay.frames[14].palm);
});

test("trunk arrow length is horizontal Δx only (same as panel trunkDisp)", () => {
  const overlay = makeOverlay();
  const t = trunkHorizontalDispNorm(overlay.frames, 4, 14);
  expect(t.dx).toBeCloseTo(overlay.frames[14].trunk[0] - overlay.frames[4].trunk[0], 8);
});

test("table line sits under the rest shoulder x in overlay coordinates", () => {
  const overlay = makeOverlay();
  const line = tableLineUnderShoulder(overlay, {
    shoulder: [0.3 * 200, 0.25 * 100],
    frames: overlay.frames,
    startIdx: 4,
    cw: 200,
    ch: 100,
    shoulderWidthPx: 40,
  });
  expect(line.y).toBeCloseTo(0.72 * 100, 8);
  expect(line.x).toBeCloseTo(0.3 * 200, 8);
  expect(line.x0).toBeLessThan(line.x);
  expect(line.x1).toBeGreaterThan(line.x);
});

test("table_edge_y is sampled at the shoulder x, not a full-frame median", () => {
  const overlay = {
    table_edge_y: [0.50, 0.55, 0.60, 0.70, 0.80],
    table_surface_y: 0.99,
  };
  expect(tableSurfaceYAtX(overlay, 0)).toBeCloseTo(0.50, 8);
  expect(tableSurfaceYAtX(overlay, 1)).toBeCloseTo(0.80, 8);
  expect(tableSurfaceYAtX(overlay, 0.5)).toBeCloseTo(0.60, 8);
});

test("without a table edge, rest y falls back to start palm", () => {
  const overlay = makeOverlay();
  expect(resolveShoulderRestY(overlay, overlay.frames, 4)).toBe(0.72);
  const noTable = { ...overlay, table_surface_y: null };
  expect(resolveShoulderRestY(noTable, overlay.frames, 4)).toBe(0.72);
});

test("a table edge on the chest snaps down to the resting palm", () => {
  expect(snapTableYToRestArm(0.50, 0.82, 0.32)).toBeCloseTo(0.82, 8);
  expect(snapTableYToRestArm(0.83, 0.82, 0.32)).toBeCloseTo(0.83, 8);
  const overlay = makeOverlay();
  overlay.table_surface_y = 0.48;
  overlay.start_palm = [0.22, 0.82];
  overlay.frames[4].palm = [0.22, 0.82];
  overlay.frames[4].shoulder = [0.30, 0.32];
  const pt = tablePointUnderShoulder(overlay, overlay.frames, 4);
  expect(pt.y).toBeCloseTo(0.82, 8);
  expect(pt.x).toBeCloseTo(0.30, 8);
});

test("table point stays at rest shoulder even if the live shoulder moves", () => {
  const overlay = makeOverlay();
  overlay.table_under_shoulder = { x: 0.30, y: 0.72 };
  const live = tableLineUnderShoulder(overlay, {
    shoulder: [0.55 * 200, 0.20 * 100],
    frames: overlay.frames,
    startIdx: 4,
    idx: 10,
    cw: 200,
    ch: 100,
  });
  expect(live.x).toBeCloseTo(0.30 * 200, 8);
  expect(live.y).toBeCloseTo(0.72 * 100, 8);
});

test("drink occlusion does not drop the shoulder height mark", () => {
  const overlay = makeOverlay();
  overlay.frames[4].shoulder = [0.30, 0.32];
  overlay.frames[4].lshoulder = [0.22, 0.33];
  overlay.frames[4].palm = [0.22, 0.82];
  overlay.start_palm = [0.22, 0.82];
  overlay.frames[12].shoulder = [0.31, 0.55];
  overlay.frames[12].lshoulder = [0.22, 0.31];
  overlay.frames[12].palm = [0.40, 0.38];
  const y = robustShoulderNorm(overlay, overlay.frames, 12, 4)[1];
  expect(y).toBeLessThanOrEqual(0.32 + 0.015);
});
