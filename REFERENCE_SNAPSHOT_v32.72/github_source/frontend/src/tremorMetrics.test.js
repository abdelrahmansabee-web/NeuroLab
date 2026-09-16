import {
  bandpassZeroPhase,
  buildTremorCameraTrack,
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
