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
    /html\.nl-touch \.content-shell \.content-panel-glass[\s\S]*?backdrop-filter:\s*blur\(22px\)/,
  );
});
