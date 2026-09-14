# أين النسخة الاحتياطية؟ / Where is the backup?

**Latest full backup of the working program: 14 Sep 2026 — clinic UI 32.52**

## المكان المعروف / Known location

1. **Folder in this repo (restore kit):** [`REFERENCE_SNAPSHOT_v32.52/`](REFERENCE_SNAPSHOT_v32.52/README.md)
2. **Git tag (entire repo, including videos):** `backup/2026-09-14-full-v32.52`
3. **Git branch:** `cursor/backup-full-v3252-f95a`
4. **Live Space commit that this freeze matches:** `deceee5977f09e9e8e3d58521fc638d43fc83d18` on https://huggingface.co/spaces/AbdelrahmanSabee/raedai

Checkout:

```bash
git fetch origin tag backup/2026-09-14-full-v32.52
git checkout backup/2026-09-14-full-v32.52
```

Read `REFERENCE_SNAPSHOT_v32.52/README.md` for restore steps (Space vs GitHub).

Older restore points still in the repo: `REFERENCE_SNAPSHOT_v28.81/`, overlay tags `backup/2026-09-14-validation-overlay-v4`.
