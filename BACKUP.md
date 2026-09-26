# أين النسخة الاحتياطية؟ / Where is the backup?

**Latest backup of the working program: 26 Sep 2026 — overlay 32.372o**

This is the 26 Sep backup branch, updated to the live clinic as of 32.372o.

- Home Screen boot is the 32.348 cache-bust + `MutationObserver(pin)` only.
- Clinic JS is the original `main.48f76699.js` / `main.2c1ebbfb.css`.
- Analyze card keeps the 32.372l Newton cradle and F capsules (Analyze + percent).
- AuthGate is the original `/auth/me` fetch, no timeout patch.

## المكان المعروف / Known location

1. **Git branch (this backup):** `cursor/backup-348-analyze-pin-f95a`
2. **Live Space commit this backup matches:** `eb740306893a1ef66e2824371f4acc8830f0cd1a` on https://huggingface.co/spaces/AbdelrahmanSabee/raedai
3. **Live app:** https://abdelrahmansabee-raedai.hf.space/?_v=32.372o

Checkout:

```bash
git fetch origin cursor/backup-348-analyze-pin-f95a
git checkout cursor/backup-348-analyze-pin-f95a
```

## Older restore points

The 17 Sep full freeze is still here if you need that older clinic UI:

1. **Folder:** [`REFERENCE_SNAPSHOT_v32.97/`](REFERENCE_SNAPSHOT_v32.97/README.md)
2. **Git tag:** `backup/2026-09-17-full-v32.97`
3. **Git branch:** `cursor/backup-full-v3297-f95a`
4. **Space commit:** `a688d87af99d0d735b4b1583a65d3fe7cb39f3ec`

Older still: tag `backup/2026-09-17-full-v32.96`, `REFERENCE_SNAPSHOT_v32.84/`, `REFERENCE_SNAPSHOT_v32.82/`, `REFERENCE_SNAPSHOT_v32.72/`, `REFERENCE_SNAPSHOT_v32.52/`, `REFERENCE_SNAPSHOT_v28.81/`, overlay tags `backup/2026-09-14-validation-overlay-v4`.
