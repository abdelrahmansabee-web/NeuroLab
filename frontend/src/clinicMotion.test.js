const fs = require("fs");
const path = require("path");

const app = fs.readFileSync(path.join(__dirname, "App.js"), "utf8");
const css = fs.readFileSync(path.join(__dirname, "index.css"), "utf8");
const motion = fs.readFileSync(path.join(__dirname, "motionPresets.js"), "utf8");

test("sidebar push does not animate left/width/margin-left over clinic glass", () => {
  expect(app).toMatch(/const SIDEBAR_LAYOUT_TRANSITION = "none"/);
  expect(app).toMatch(/SIDEBAR_SHELL_TRANSITION = "transform 320ms/);
  expect(motion).toMatch(/NL_LAYOUT_TRANSITION = "none"/);
});

test("open/close panes use opacity and transform instead of height auto", () => {
  expect(app).not.toMatch(/height:\s*["']auto["']/);
  expect(app).not.toMatch(/height:\s*0,\s*opacity/);
});

test("fading overlays do not composite backdrop-filter while opacity animates", () => {
  expect(app).not.toMatch(/bg-black\/50 backdrop-blur-\[3px\]/);
  expect(app).not.toMatch(/bg-black\/95 backdrop-blur-sm/);
});

test("section enter is a short transform fade and does not keep translateZ on the pane", () => {
  expect(app).toMatch(/key=\{sectionId\}/);
  expect(css).toMatch(/@keyframes nl-section-enter/);
  expect(css).toMatch(/\.section-nav-motion\s*\{[\s\S]*?animation:\s*nl-section-enter/s);
});
