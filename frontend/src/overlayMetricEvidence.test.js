import { buildTremorEvidenceLines } from "./overlayMetricEvidence";

test("tremor evidence lines match the 32.72 freeze band-power label", () => {
  const lines = buildTremorEvidenceLines(
    { metrics: { tremor_8_12hz_power: 0.12, tremor_peak_freq_hz: 9.5 } },
    0.12,
    9.5,
  );
  expect(lines[0]).toMatch(/Tremor 8–12 Hz/);
  expect(lines.some((line) => line.includes("9.5"))).toBe(true);
  expect(lines[lines.length - 1]).toBe("Source: palm speed FFT (not clinical IMU)");
});
