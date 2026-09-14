# Snapshot — validation overlay 14 Sep 2026 (~90%)

**Do not edit files in this folder.** Copy them out when you need to restore.

This is a frozen copy of the **analysis + skeleton drawing + motion tracking** that was live when the validation video looked about 90% correct.

| Piece | What was frozen |
|---|---|
| Live player | 10 Sep bundle `main.a0625928.js` + CSS `main.23ef7b0e.css` (`nl-version` **32.43**) |
| Drawing source | `ValidationOverlayPlayer.js` + skeleton helpers |
| Analysis / overlay JSON | HF `overlay_data.py` overlay **v40**, Hand Landmarker follow-moving-wrist |
| Hugging Face commit | `4f0e5b1` |
| GitHub commit at copy | `ce65e72` |

Patient CSV / overlay JSON for a specific visit is **not** in this folder (clinic login data). This snapshot restores the **program** that draws Validation Video, not one patient’s saved result.

---

## Restore (Hugging Face Space)

From this repo:

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
git commit -m "Restore 2026-09-14 validation overlay snapshot"
git push
```

Wait for the Space rebuild. On iPad, hard-refresh so `nl-version` 32.43 loads.

## Restore from Git tags

- **GitHub:** `git checkout backup/2026-09-14-validation-overlay`
- **HF Space:** `git checkout backup-2026-09-14-validation-overlay`

## After a later Analyze

Re-analyzing a video writes new CSV / overlay JSON. Restoring this snapshot restores **how** chalk is generated and drawn. It does not undo a patient’s new Analyze by itself.
