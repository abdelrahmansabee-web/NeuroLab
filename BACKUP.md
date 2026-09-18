# أين النسخة الاحتياطية؟ / Where is the backup?

**Latest full backup of the working program: 17 Sep 2026 — clinic UI 32.97**

Overlay body bones use display-only zero-phase (same recorded-clip Gaussian as HL fingers) with 32.72 linear lerp. Catmull-Rom overshoot is gone. Stored palm / tremor / NVP JSON are unchanged. Overlay clock is 32.82. Compact overlay stays in-card. Overlay version stays 44. Task phases & variables and Movement quality & joint specs cards stay gone. Drive originals upload as real multipart video.

## المكان المعروف / Known location

1. **Folder in this repo (restore kit):** [`REFERENCE_SNAPSHOT_v32.97/`](REFERENCE_SNAPSHOT_v32.97/README.md)
2. **Git tag (entire repo):** `backup/2026-09-17-full-v32.97`
3. **Git branch:** `cursor/backup-full-v3297-f95a`
4. **Live Space commit that this freeze matches:** `a688d87af99d0d735b4b1583a65d3fe7cb39f3ec` on https://huggingface.co/spaces/AbdelrahmanSabee/raedai

Checkout:

```bash
git fetch origin tag backup/2026-09-17-full-v32.97
git checkout backup/2026-09-17-full-v32.97
```

Read `REFERENCE_SNAPSHOT_v32.97/README.md` for restore steps (Space vs GitHub).

Older restore points still in the repo: tag `backup/2026-09-17-full-v32.96`, `REFERENCE_SNAPSHOT_v32.84/`, `REFERENCE_SNAPSHOT_v32.82/`, `REFERENCE_SNAPSHOT_v32.72/`, `REFERENCE_SNAPSHOT_v32.52/`, `REFERENCE_SNAPSHOT_v28.81/`, overlay tags `backup/2026-09-14-validation-overlay-v4`.
