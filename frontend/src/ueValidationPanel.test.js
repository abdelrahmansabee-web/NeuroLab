const fs = require("fs");
const path = require("path");

const playerSrc = fs.readFileSync(path.join(__dirname, "ValidationOverlayPlayer.js"), "utf8");
const marksSrc = fs.readFileSync(path.join(__dirname, "overlayPanelMarks.js"), "utf8");

test("UE validation panel lists the eight clinic SPSS variables", () => {
  expect(playerSrc).toContain('label: "Shoulder elevation"');
  expect(playerSrc).toContain('label: "Trunk forward displacement"');
  expect(playerSrc).toContain('label: "Movement time"');
  expect(playerSrc).toContain('label: "Average hand velocity"');
  expect(playerSrc).toContain('label: "Elbow extension angle"');
  expect(playerSrc).toContain('label: "Shoulder flexion angle"');
  expect(playerSrc).toContain('label: "Shoulder abduction angle"');
  expect(playerSrc).toContain("NVP ${currentNVP}");
  expect(playerSrc).not.toContain('label: "Movement quality"');
  expect(playerSrc).not.toContain('label: "Straightness"');
  expect(playerSrc).not.toContain('label: "Peak velocity"');
  expect(playerSrc).not.toContain('label: "Pause / stops"');
  expect(playerSrc).not.toContain('label: "Trunk ratio"');
  expect(playerSrc).not.toContain('label: "Finger quality"');
  expect(playerSrc).not.toContain('label: "Tremor 8–12 Hz"');
});

test("skeleton marks keep NVP, trunk, and shoulder and drop leftover chord/pause/Ha", () => {
  expect(marksSrc).toContain("nvpPeakIndicesOnPath");
  expect(marksSrc).toContain("trunkHorizontalDispNorm");
  expect(marksSrc).toContain("tableLineUnderShoulder");
  expect(marksSrc).not.toContain("Straightness chord");
  expect(marksSrc).not.toContain("PATH_PAUSE");
  expect(playerSrc).toContain("Flex ${currentShoulderFlexion");
  expect(playerSrc).toContain("Abd ${currentShoulderAbduction");
  expect(playerSrc).toContain("El ${currentElbowAngle");
  expect(playerSrc).not.toMatch(/Ha \$\{Math\.round\(speed\)\}/);
});
