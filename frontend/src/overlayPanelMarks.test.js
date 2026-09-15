import {
  overlayPauseSpeedThreshold,
} from "./validationPanelMetrics";
import {
  classifyPalmPath,
  nvpPeakIndicesOnPath,
  resolveShoulderRestY,
  straightnessEndpoints,
  trunkHorizontalDispNorm,
} from "./overlayPanelMarks";

function frame({ t, palm, speed, trunk, shoulder }) {
  return {
    time: t,
    palm,
    trunk: trunk || [palm[0] * 0.2, palm[1]],
    shoulder: shoulder || [0.3, 0.25],
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
      palm: [0.2 + i * 0.02, 0.5],
      speed: i === 8 ? 0.2 : (moving ? 20 : 0.2),
      trunk: [0.12 + (i >= 4 ? (Math.min(i, 14) - 4) * 0.004 : 0), 0.32],
    }));
  }
  return {
    fps,
    frames,
    movement_window: { start_idx: 4, end_idx: 14 },
    peak_frames: [6, 10, 18],
    table_surface_y: 0.72,
    start_palm: [0.2, 0.5],
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

test("shoulder column rest prefers table_surface_y, then palm rest", () => {
  const overlay = makeOverlay();
  expect(resolveShoulderRestY(overlay, overlay.frames, 4)).toBe(0.72);
  const noTable = { ...overlay, table_surface_y: null };
  expect(resolveShoulderRestY(noTable, overlay.frames, 4)).toBe(0.5);
});
