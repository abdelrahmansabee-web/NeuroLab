# أين النسخة الاحتياطية؟ / Where is the backup?

**Latest full backup of the working program: 16 Sep 2026 — clinic UI 32.84**

Clinician confirmed PRE overlay video picture shows after Analyze. The player keeps the live iPad file. Overlay clock is 32.82. Paint is 32.72 lerp + 32.81 RVFC. Compact overlay stays in-card.

## المكان المعروف / Known location

1. **Folder in this repo (restore kit):** [`REFERENCE_SNAPSHOT_v32.84/`](REFERENCE_SNAPSHOT_v32.84/README.md)
2. **Git tag (entire repo):** `backup/2026-09-16-full-v32.84`
3. **Git branch:** `cursor/backup-full-v3284-f95a`
4. **Live Space commit that this freeze matches:** `5484f840372fd3b5c34b481b666d05b46d4bcf8d` on https://huggingface.co/spaces/AbdelrahmanSabee/raedai

Checkout:

```bash
git fetch origin tag backup/2026-09-16-full-v32.84
git checkout backup/2026-09-16-full-v32.84
```

Read `REFERENCE_SNAPSHOT_v32.84/README.md` for restore steps (Space vs GitHub).

Older restore points still in the repo: `REFERENCE_SNAPSHOT_v32.82/`, `REFERENCE_SNAPSHOT_v32.72/`, `REFERENCE_SNAPSHOT_v32.52/`, `REFERENCE_SNAPSHOT_v28.81/`, overlay tags `backup/2026-09-14-validation-overlay-v4`.
