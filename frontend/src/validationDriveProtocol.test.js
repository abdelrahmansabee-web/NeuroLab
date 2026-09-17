import {
  connectDriveHref,
  isReencodedValidationBake,
  isVideoOriginalBlob,
  mergeSeenValidationRecord,
  pickOriginalVideoBlob,
  shouldUploadUnifiedValidationToDrive,
  validationDriveUploadPlan,
} from "./validationDriveProtocol";

describe("Drive seen-validation protocol", () => {
  test("on-screen playback pieces are original bytes plus overlay JSON", () => {
    const original = new Blob([new Uint8Array([1, 2, 3, 4])], { type: "video/mp4" });
    original.name = "drink_pre.mp4";
    const overlay = { frames: [{ t: 0 }] };
    const bake = new Blob([new Uint8Array([9, 9, 9])], { type: "video/webm" });
    bake.name = "pre_validation.mp4";
    const record = mergeSeenValidationRecord(
      { overlay: { frames: [] } },
      { overlay, unifiedVideoBlob: bake },
      original,
    );
    const plan = validationDriveUploadPlan(record);
    expect(plan.original).toBe(true);
    expect(plan.overlay).toBe(true);
    expect(plan.unified).toBe(false);
    expect(shouldUploadUnifiedValidationToDrive(bake, "pre_validation.mp4")).toBe(false);
    expect(isReencodedValidationBake(bake, "pre_validation.mp4")).toBe(true);
    expect(pickOriginalVideoBlob(bake, original)).toBe(original);
  });

  test("a live camera file is kept when overlay persist forgot the original", () => {
    const live = new Blob([new Uint8Array([7, 7])], { type: "video/mp4" });
    live.name = "IMG_001.MOV";
    const merged = mergeSeenValidationRecord(
      null,
      { overlay: { frames: [{ t: 1 }] } },
      live,
    );
    expect(merged.originalVideoBlob).toBe(live);
    expect(validationDriveUploadPlan(merged).original).toBe(true);
  });

  test("CSV analysis is not uploaded as the original clip", () => {
    const csv = new Blob(["a,b"], { type: "text/csv" });
    csv.name = "pre.csv";
    expect(isVideoOriginalBlob(csv)).toBe(false);
    expect(pickOriginalVideoBlob(csv)).toBe(null);
  });

  test("Connect Drive ticket stays on the Space origin", () => {
    expect(connectDriveHref(
      "https://abdelrahmansabee-raedai.hf.space",
      "/auth/drive/connect?ticket=abc",
    )).toBe("https://abdelrahmansabee-raedai.hf.space/auth/drive/connect?ticket=abc");
  });
});
