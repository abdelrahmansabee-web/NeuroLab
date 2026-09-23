/**
 * iPad/coarse must use the same 32.97 laptop chalk fork, not the lite path.
 */
import { readFileSync } from "fs";
import { join } from "path";

const src = readFileSync(join(__dirname, "ValidationOverlayPlayer.js"), "utf8");

test("laptop fork paint stays 32.97 chalk (1.55 / blur 3 / curve 0.08 / dpr 2)", () => {
  expect(src).toContain("fingerWidth: 1.55");
  expect(src).toContain("fingerBlur: 3");
  expect(src).toContain("fingerCurve: 0.08");
  expect(src).toContain("dprCap: 2");
  expect(src).toContain("function clinicValidationPaint()");
  expect(src).toMatch(/function clinicValidationPaint\(\) \{\s*return false;/);
});

test("iPad schedulePaint does not take the coarse live early-return", () => {
  expect(src).not.toMatch(/touchLive && !videoRef\.current\.paused/);
  expect(src).toContain("Same paint turn as laptop");
});
