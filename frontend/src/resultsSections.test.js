const fs = require("fs");
const path = require("path");

const appSrc = fs.readFileSync(path.join(__dirname, "App.js"), "utf8");

test("results UI no longer includes the Movement quality & joint specs section", () => {
  expect(appSrc).not.toMatch(/Movement quality\s*&(?:amp;)?\s*joint specs/i);
  expect(appSrc).not.toContain("getMovementProfile(");
  expect(appSrc).not.toContain("MOVEMENT_PROFILE_GROUP_ORDER");
});

test("the study results table and later result cards stay in place", () => {
  expect(appSrc).not.toMatch(/Task phases\s*&(?:amp;)?\s*variables/i);
  expect(appSrc).toContain("Combined Velocity Profile");
});
