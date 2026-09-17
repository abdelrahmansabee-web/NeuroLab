import {
  shouldHydrateMediaBlobIntoState,
  shouldHydrateOverlayIntoState,
  validationCacheMatchesResult,
  freezeMediaBlob,
  reviveMediaBlob,
  MEDIA_BUF_MARK,
} from "./validationSessionCache";

test("Drive recall does not replace an overlay that is already on screen", () => {
  const live = { frames: [{ t: 0 }], version: "v1" };
  const incoming = { frames: [{ t: 0 }, { t: 1 }], version: "v2" };
  expect(shouldHydrateOverlayIntoState(live, incoming)).toBe(false);
  expect(shouldHydrateOverlayIntoState(null, incoming)).toBe(true);
  expect(shouldHydrateOverlayIntoState({}, incoming)).toBe(true);
  expect(shouldHydrateOverlayIntoState(null, { frames: [] })).toBe(false);
});

test("Drive recall does not revoke a playing original-video blob URL", () => {
  const blob = new Blob([new Uint8Array([1, 2, 3])], { type: "video/mp4" });
  expect(shouldHydrateMediaBlobIntoState("blob:already-playing", blob)).toBe(false);
  expect(shouldHydrateMediaBlobIntoState("", blob)).toBe(true);
  expect(shouldHydrateMediaBlobIntoState(undefined, blob)).toBe(true);
  expect(shouldHydrateMediaBlobIntoState(undefined, new Blob([], { type: "video/mp4" }))).toBe(false);
});

test("cache match still requires a csv name unless relaxCsvMatch", () => {
  const cached = { overlay: { frames: [{ t: 0 }] } };
  expect(validationCacheMatchesResult(cached, {})).toBe(false);
  expect(validationCacheMatchesResult(cached, {}, { relaxCsvMatch: true })).toBe(true);
});

test("iOS Home Screen stores video blobs as ArrayBuffer and revives them", async () => {
  const blob = new Blob([new Uint8Array([9, 8, 7])], { type: "video/mp4" });
  const frozen = await freezeMediaBlob(blob);
  expect(frozen[MEDIA_BUF_MARK]).toBe(1);
  expect(frozen.data.byteLength).toBe(3);
  const revived = reviveMediaBlob(frozen);
  expect(revived).toBeInstanceOf(Blob);
  expect(revived.size).toBe(3);
  expect(revived.type).toBe("video/mp4");
  expect(validationCacheMatchesResult(
    { originalVideoBlob: frozen, overlay: { frames: [{ t: 0 }] } },
    {},
    { relaxCsvMatch: true },
  )).toBe(true);
});
