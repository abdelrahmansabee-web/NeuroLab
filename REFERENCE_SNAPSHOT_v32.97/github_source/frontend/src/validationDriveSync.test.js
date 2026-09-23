import {
  backupValidationArtifactsToDrive,
  driveTokenHeaders,
  shouldMultipartDriveUpload,
} from "./validationDriveSync";
import { shouldPushLocalRecallToDrive } from "./driveSessionRestore";

describe("validationDriveSync upload protocol", () => {
  test("video originals always use multipart, even when they are under 28MB", () => {
    const small = new Blob([new Uint8Array(64)], { type: "video/mp4" });
    expect(shouldMultipartDriveUpload("pre_validation_original.mp4", small)).toBe(true);
    const json = new Blob([JSON.stringify({ frames: [{ t: 0 }] })], { type: "application/json" });
    expect(shouldMultipartDriveUpload("pre_validation_overlay.json", json)).toBe(false);
  });

  test("multipart headers keep the Bearer token and drop JSON content-type", () => {
    const prev = window.localStorage.getItem("neurolab_token");
    window.localStorage.setItem("neurolab_token", "tok-1");
    const headers = driveTokenHeaders();
    expect(headers["Content-Type"]).toBeUndefined();
    expect(headers.Authorization).toBe("Bearer tok-1");
    const jsonHeaders = driveTokenHeaders({ json: true });
    expect(jsonHeaders["Content-Type"]).toBe("application/json");
    if (prev == null) window.localStorage.removeItem("neurolab_token");
    else window.localStorage.setItem("neurolab_token", prev);
  });

  test("PRE original is posted to backup-file-upload as FormData, not JSON", async () => {
    const fetchMock = jest.fn(async () => ({
      ok: true,
      json: async () => ({ ok: true, fileName: "pre_validation_original.mp4" }),
    }));
    const prevFetch = global.fetch;
    global.fetch = fetchMock;
    const blob = new Blob([new Uint8Array([1, 2, 3, 4])], { type: "video/mp4" });
    await backupValidationArtifactsToDrive("101_Ada", "pre", { originalVideoBlob: blob });
    global.fetch = prevFetch;
    expect(fetchMock).toHaveBeenCalled();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/auth/backup-file-upload");
    expect(opts.body).toBeInstanceOf(FormData);
    expect(opts.headers["Content-Type"]).toBeUndefined();
    expect(opts.body.get("name")).toBe("pre_validation_original.mp4");
    expect(opts.body.get("patientKey")).toBe("101_Ada");
    expect(opts.body.get("subfolder")).toBe("videos");
  });

  test("a skipped Drive response is not treated as a successful backup", async () => {
    const fetchMock = jest.fn(async () => ({
      ok: true,
      json: async () => ({ ok: true, skipped: true, reason: "validation_videos_only" }),
    }));
    const prevFetch = global.fetch;
    global.fetch = fetchMock;
    const blob = new Blob([new Uint8Array([1, 2, 3])], { type: "video/mp4" });
    const ok = await backupValidationArtifactsToDrive("101_Ada", "pre", { originalVideoBlob: blob });
    global.fetch = prevFetch;
    expect(ok).toBe(false);
  });

  test("overlay JSON still uses the small JSON backup route", async () => {
    const fetchMock = jest.fn(async () => ({
      ok: true,
      json: async () => ({ ok: true, fileName: "pre_validation_overlay.json" }),
    }));
    const prevFetch = global.fetch;
    global.fetch = fetchMock;
    await backupValidationArtifactsToDrive("101_Ada", "pre", {
      overlay: { frames: [{ t: 0 }] },
    });
    global.fetch = prevFetch;
    expect(fetchMock.mock.calls[0][0]).toBe("/auth/backup-file");
    expect(fetchMock.mock.calls[0][1].headers["Content-Type"]).toBe("application/json");
  });
});

describe("local IDB originals must be copied to Drive", () => {
  test("Safari cache with an original is a push; a blank icon is not", () => {
    const original = new Blob([new Uint8Array([9])], { type: "video/mp4" });
    expect(shouldPushLocalRecallToDrive({ originalVideoBlob: original }, { originalVideoBlob: original })).toBe(true);
    expect(shouldPushLocalRecallToDrive({}, { originalVideoBlob: original })).toBe(false);
    expect(shouldPushLocalRecallToDrive({}, {})).toBe(false);
  });
});
