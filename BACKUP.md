# أين النسخة الاحتياطية؟ / Where is the backup?

**Latest full backup of the working program: 16 Sep 2026 — clinic UI 32.82**

Videos stay in their cards while scrolling. Enlarge uses the same video node. Overlay paint uses the presented video frame. Tremor mark draw is the 32.72 freeze.

## المكان المعروف / Known location

1. **Folder in this repo (restore kit):** [`REFERENCE_SNAPSHOT_v32.82/`](REFERENCE_SNAPSHOT_v32.82/README.md)
2. **Git tag (entire repo):** `backup/2026-09-16-full-v32.82`
3. **Git branch:** `cursor/backup-full-v3282-f95a`
4. **Live Space commit that this freeze matches:** `5573042d3c9c7adf2e60d7836f5167f3fc0042cf` on https://huggingface.co/spaces/AbdelrahmanSabee/raedai

Checkout:

```bash
git fetch origin tag backup/2026-09-16-full-v32.82
git checkout backup/2026-09-16-full-v32.82
```

Read `REFERENCE_SNAPSHOT_v32.82/README.md` for restore steps (Space vs GitHub).

Older restore points still in the repo: `REFERENCE_SNAPSHOT_v32.72/`, `REFERENCE_SNAPSHOT_v32.52/`, `REFERENCE_SNAPSHOT_v28.81/`, overlay tags `backup/2026-09-14-validation-overlay-v4`.
