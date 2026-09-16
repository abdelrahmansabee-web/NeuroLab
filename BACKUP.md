# أين النسخة الاحتياطية؟ / Where is the backup?

**Latest full backup of the working program: 16 Sep 2026 — clinic UI 32.72**

Videos stay in their cards while scrolling. Enlarge uses the same video node. No known clinic-player problems in this freeze.

## المكان المعروف / Known location

1. **Folder in this repo (restore kit):** [`REFERENCE_SNAPSHOT_v32.72/`](REFERENCE_SNAPSHOT_v32.72/README.md)
2. **Git tag (entire repo):** `backup/2026-09-16-full-v32.72`
3. **Git branch:** `cursor/backup-full-v3272-f95a`
4. **Live Space commit that this freeze matches:** `5a22b03961873ddcc7a83353645b7d61cd6b2e82` on https://huggingface.co/spaces/AbdelrahmanSabee/raedai

Checkout:

```bash
git fetch origin tag backup/2026-09-16-full-v32.72
git checkout backup/2026-09-16-full-v32.72
```

Read `REFERENCE_SNAPSHOT_v32.72/README.md` for restore steps (Space vs GitHub).

Older restore points still in the repo: `REFERENCE_SNAPSHOT_v32.52/`, `REFERENCE_SNAPSHOT_v28.81/`, overlay tags `backup/2026-09-14-validation-overlay-v4`.
