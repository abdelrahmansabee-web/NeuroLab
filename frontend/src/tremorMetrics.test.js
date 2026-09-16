import {
  bandpassZeroPhase,
  buildTremorCameraTrack,
  computeTremorFromOverlay,
  formatTremorAmplitude,
  resolveTremorMetrics,
  tremorBandAbsRmsPx,
  tremorPeakFreqHz,
  zeroCrossingHz,
} from "./tremorMetrics";

function rms(y, a, b) {
  let s = 0;
  let n = 0;
  for (let i = a; i < b; i += 1) {
    s += (y[i] || 0) * (y[i] || 0);
    n += 1;
  }
  return n ? Math.sqrt(s / n) : 0;
}

function makeTremorOverlay({ ampPx, hz, n = 180, fps = 60, fw = 1280, fh = 720, sw = 400, backend = null }) {
  const frames = Array.from({ length: n }, (_, i) => {
    const t = i / fps;
    const shake = ampPx * Math.sin((2 * Math.PI * hz * t));
    return {
      palm: [0.5 + shake / fw, 0.5],
      speed_tremor: Math.abs(2 * Math.PI * hz * ampPx * Math.cos((2 * Math.PI * hz * t))),
      speed: 1,
    };
  });
  return {
    fps,
    frames,
    frame_width_px: fw,
    frame_height_px: fh,
    shoulder_width_px: sw,
    movement_window: { start_idx: 0, end_idx: n - 1 },
    metrics: backend || {},
  };
}

test("8–12 Hz bandpass keeps 10 Hz camera shake and rejects slow reach", () => {
  const fs = 60;
  const n = 240;
  const tremor = Array.from({ length: n }, (_, i) => Math.sin((2 * Math.PI * 10 * i) / fs));
  const reach = Array.from({ length: n }, (_, i) => Math.sin((2 * Math.PI * 1.5 * i) / fs));
  const kept = bandpassZeroPhase(tremor, fs);
  const rejected = bandpassZeroPhase(reach, fs);
  const mid0 = Math.floor(n * 0.25);
  const mid1 = Math.floor(n * 0.75);
  expect(rms(kept, mid0, mid1)).toBeGreaterThan(0.2);
  expect(rms(rejected, mid0, mid1)).toBeLessThan(0.12);
  expect(rms(kept, mid0, mid1)).toBeGreaterThan(rms(rejected, mid0, mid1) * 2);
});

test("zero-crossing Hz on 10 Hz sine is near 10", () => {
  const fs = 60;
  const n = 120;
  const y = Array.from({ length: n }, (_, i) => Math.sin((2 * Math.PI * 10 * i) / fs));
  const hz = zeroCrossingHz(y, fs);
  expect(hz).toBeGreaterThan(8);
  expect(hz).toBeLessThan(12);
});

test("camera track band-passes overlay palm + speed_tremor", () => {
  const fs = 60;
  const frames = Array.from({ length: 90 }, (_, i) => ({
    palm: [0.4 + 0.002 * Math.sin((2 * Math.PI * 10 * i) / fs), 0.5],
    speed_tremor: 4 + 3 * Math.sin((2 * Math.PI * 10 * i) / fs),
    speed: 20,
  }));
  const track = buildTremorCameraTrack({ frames, fps: fs });
  expect(track).not.toBeNull();
  expect(track.bandSpeed.length).toBe(90);
  const mid = rms(track.dx, 20, 70);
  expect(mid).toBeGreaterThan(0.0002);
});

test("rest tracking noise under 2 px RMS is not tremor", () => {
  const overlay = makeTremorOverlay({ ampPx: 1.2, hz: 10 });
  const out = computeTremorFromOverlay(overlay);
  expect(out.tremor_present).toBe(false);
  expect(out.tremor_8_12hz_power).toBe(0);
  expect(out.tremor_peak_freq_hz).toBeNull();
  expect(out.tremor_index).toBe(100);
  expect(out.tremor_abs_rms_px).toBeLessThan(2);
  expect(formatTremorAmplitude(out.tremor_abs_rms_px, overlay.shoulder_width_px, out.tremor_present)).toBe("0");
});

test("10 Hz 6 px palm sine is present with peak near 10 Hz", () => {
  const overlay = makeTremorOverlay({ ampPx: 6, hz: 10 });
  const out = computeTremorFromOverlay(overlay);
  expect(out.tremor_present).toBe(true);
  expect(out.tremor_abs_rms_px).toBeGreaterThan(2);
  expect(out.tremor_peak_freq_hz).toBeGreaterThan(8);
  expect(out.tremor_peak_freq_hz).toBeLessThan(12);
  expect(formatTremorAmplitude(out.tremor_abs_rms_px, overlay.shoulder_width_px, true)).toMatch(/px/);
});

test("resolveTremorMetrics zeros backend relative power when rest is below the floor", () => {
  const overlay = makeTremorOverlay({
    ampPx: 1.2,
    hz: 10,
    backend: { tremor_8_12hz_power: 0.42, tremor_peak_freq_hz: 9.4, tremor_index: 12 },
  });
  const out = resolveTremorMetrics(overlay);
  expect(out.tremor_present).toBe(false);
  expect(out.tremor_8_12hz_power).toBe(0);
  expect(out.tremor_peak_freq_hz).toBeNull();
  expect(out.tremor_index).toBe(100);
});

test("peak Hz needs SNR so flat in-band energy has no peak", () => {
  const fs = 60;
  const n = 180;
  const y = Array.from({ length: n }, (_, i) => (
    Math.sin((2 * Math.PI * 8.2 * i) / fs)
    + Math.sin((2 * Math.PI * 9.1 * i) / fs)
    + Math.sin((2 * Math.PI * 10.3 * i) / fs)
    + Math.sin((2 * Math.PI * 11.4 * i) / fs)
  ));
  expect(tremorPeakFreqHz(y, fs, 8, 12, 0.75, { requireSnr: true })).toBeNull();
});

test("abs RMS uses pixel series when palm is already in px", () => {
  const fs = 60;
  const n = 180;
  const px = Array.from({ length: n }, (_, i) => 6 * Math.sin((2 * Math.PI * 10 * i) / fs));
  const py = Array.from({ length: n }, () => 0);
  const abs = tremorBandAbsRmsPx(px, py, fs, 0, 0);
  expect(abs).toBeGreaterThan(2);
});
