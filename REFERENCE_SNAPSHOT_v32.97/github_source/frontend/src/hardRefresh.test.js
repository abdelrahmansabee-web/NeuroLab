import { buildHardRefreshUrl, performHardRefresh, readDocumentNlVersion } from "./hardRefresh";

test("hard refresh URL busts the cached PWA document", () => {
  expect(buildHardRefreshUrl({ pathname: "/", hash: "" }, "32.92", 1700000000000)).toBe(
    "/?_v=32.92&_r=1700000000000",
  );
  expect(buildHardRefreshUrl({ pathname: "/app", hash: "#kin" }, "32.92", 9)).toBe(
    "/app?_v=32.92&_r=9#kin",
  );
});

test("reads nl-version from the document meta tag", () => {
  document.head.innerHTML = '<meta name="nl-version" content="32.92" />';
  expect(readDocumentNlVersion(document)).toBe("32.92");
});

test("performHardRefresh replaces the current location after cache clear skip", async () => {
  const replaced = [];
  const url = await performHardRefresh({
    location: { pathname: "/", hash: "" },
    version: "32.92",
    now: 42,
    skipCacheClear: true,
    replace: (next) => replaced.push(next),
  });
  expect(url).toBe("/?_v=32.92&_r=42");
  expect(replaced).toEqual(["/?_v=32.92&_r=42"]);
});
