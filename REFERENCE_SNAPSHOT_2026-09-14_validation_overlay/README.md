# Snapshot — validation overlay 14 Sep 2026 (current freeze)

**Do not edit files in this folder.** Copy them out when you need to restore.

This folder was **refreshed** after the finger-chalk smoothness + drink-fingertip crop. Use this as the restore point for the next edit.

The morning freeze is still in git as tag `backup/2026-09-14-validation-overlay`. This folder is **v2**.

| Piece | What was frozen |
|---|---|
| Live player | 10 Sep bundle `main.a0625928.js` + CSS `main.23ef7b0e.css` (`nl-version` **32.43**) |
| Drawing source | `ValidationOverlayPlayer.js` + skeleton helpers |
| Analysis / overlay JSON | HF overlay **v41**, follow-moving-wrist + VIDEO distal crop + finger EMA |
| Hugging Face commit | `ed41d67` |
| GitHub commit at copy | `9c67c48` |

Patient CSV / overlay JSON for a specific visit is **not** in this folder. This restores the **program** that draws Validation Video.

---

## Restore (Hugging Face Space)

```bash
python3 REFERENCE_SNAPSHOT_2026-09-14_validation_overlay/restore.py \
  --hf-root /path/to/hf-space-checkout
```

Then in that Space checkout:

```bash
git add overlay_data.py hand_landmarker_extract.py hl_overlay_resample.py main.py \
  frontend/build/index.html \
  frontend/build/static/js/main.a0625928.js \
  frontend/build/static/css/main.23ef7b0e.css
git commit -m "Restore 2026-09-14 validation overlay snapshot v2"
git push
```

Wait for the Space rebuild. On iPad, hard-refresh so `nl-version` 32.43 loads.

## Restore from Git tags

- **GitHub (this freeze):** `git checkout backup/2026-09-14-validation-overlay-v2`
- **HF Space (this freeze):** `git checkout backup-2026-09-14-validation-overlay-v2`
- Morning freeze: `backup/2026-09-14-validation-overlay`

## After a later Analyze

Restoring this snapshot restores **how** chalk is generated and drawn. It does not undo a patient’s new Analyze by itself.
