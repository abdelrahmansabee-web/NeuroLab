const fs = require("fs");
const path = require("path");

const css = fs.readFileSync(path.join(__dirname, "index.css"), "utf8");
const app = fs.readFileSync(path.join(__dirname, "App.js"), "utf8");

test("lab glass does not paint an invented black fill over iPad clinic cards", () => {
  expect(css).not.toMatch(/html\.nl-touch \[data-nl-app-scroll\][^{]*\{[^}]*background-color:\s*rgba\(10,\s*14,\s*22/);
  expect(css).not.toMatch(/html\.nl-touch \[data-nl-app-scroll\][^{]*\{[^}]*background-color:\s*rgba\(16,\s*22,\s*32/);
  expect(app).not.toMatch(/html\.nl-touch \[data-nl-app-scroll\][^{]*\{[^}]*background-color:\s*rgba\(10,\s*14,\s*22/);
  expect(app).not.toMatch(/html\.nl-touch \[data-nl-app-scroll\][^{]*\{[^}]*background-color:\s*rgba\(16,\s*22,\s*32/);
});

test("iPad inner lab cards keep a light glass blur instead of a black plate", () => {
  expect(app).toMatch(
    /html\.nl-touch \.content-shell \.content-panel-glass[\s\S]*?backdrop-filter:\s*blur\(6px\)/,
  );
});

test("analysis phase cards use muted glass instead of neon sky/emerald/amber plates", () => {
  expect(app).not.toMatch(/border-t-\[3px\] bg-gradient-to-b \$\{a\.top\}/);
  expect(app).not.toMatch(/from-sky-500\/14/);
  expect(app).toMatch(/KIN_PHASE_PIP/);
  expect(app).toMatch(/rounded-\[28px\] border border-white\/\[0\.06\] bg-white\/\[0\.028\]/);
});

test("clinic chrome keeps original GitHub glass degree, not milky lens brightening", () => {
  expect(app).toMatch(
    /const GLASS_CLS = "bg-white\/\[0\.008\] backdrop-blur-md backdrop-saturate-\[2\.25\] border border-white\/\[0\.03\]"/,
  );
  expect(app).toMatch(/background-color: rgba\(255,255,255,0\.008\)/);
  expect(app).toMatch(/background-color: rgba\(255,255,255,0\.028\)/);
  expect(app).toMatch(/@keyframes nl-liquid-orbit/);
  expect(app).toMatch(/animation: nl-liquid-orbit 28s linear infinite/);
  expect(app).not.toMatch(/nl-liquid-sheen/);
  expect(app).not.toMatch(/linear-gradient\(118deg/);
  expect(app).not.toMatch(/brightness\(1\.08\)/);
  expect(app).not.toMatch(/bg-white\/70/);
  expect(app).toMatch(/\.sidebar-shell \{\s*border-radius: 36px !important;/);
  expect(app).toMatch(/\.app-topbar-glass,\s*\.section-header \{\s*border-radius: 999px !important;/);
});
