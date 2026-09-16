# RA.ED AI — full restore snapshot v32.82

**Date:** 16 Sep 2026  
**Purpose:** نسخة احتياطية كاملة من البرنامج الشغّال حالياً. لو حصل خطأ في تعديلات جاية، نرجع من هنا.

This folder is a frozen copy of the **working** RA.ED AI / NeuroLab program at clinic UI **32.82**.

Videos stay in their cards while scrolling. Enlarge uses the same `<video>` node. Overlay paint uses the presented video frame clock. Tremor mark draw is the 32.72 freeze.

| Where | What |
|-------|------|
| **This folder** `REFERENCE_SNAPSHOT_v32.82/` | Restore kit: GitHub source + live Hugging Face Space |
| **Git tag** `backup/2026-09-16-full-v32.82` | The GitHub repo at this point |
| **Git branch** `cursor/backup-full-v3282-f95a` | Same snapshot, easy to check out |
| **Live Space** | https://huggingface.co/spaces/AbdelrahmanSabee/raedai |
| **Live app** | https://abdelrahmansabee-raedai.hf.space/?_v=32.82 |

Integrity hashes: `MANIFEST.sha256`. Machine-readable metadata: `SNAPSHOT.json`.

---

## إيه اللي جوه المجلد؟

| جزء | المعنى |
|-----|--------|
| `hf_space/` | البرنامج الشغّال على Hugging Face (backend + Docker + build الواجهة 32.82) |
| `github_source/` | سورس GitHub (frontend CRA + backend + deploy) بنفس حالة 32.82 |

لو **الـ Space** اتكسر → رجّع من `hf_space/`.  
لو **السورس على GitHub / الجهاز** اتكسر → رجّع من `github_source/`.

---

## What is inside

| Part | What was snapshotted | Version |
|------|----------------------|---------|
| `hf_space/` | Live Hugging Face Space (FastAPI + Docker + CRA `frontend/build`) | **32.82** — JS `main.72cb8383.js`, CSS `main.46e6a924.css` |
| `github_source/` | GitHub source that produced this clinic UI | **32.82** |

**HF commit:** `5573042d3c9c7adf2e60d7836f5167f3fc0042cf`  
(`32.82: restore 32.72 overlay blend between stored frames`)

**GitHub source commit (parent of this snapshot):** `9fc9cef0f5e997af4433bdfaf699db64ff1ffad1`

JavaScript **source maps** (`*.js.map`) are omitted. Stale older `main.<hash>.js` bundles on the Space are omitted; only the live 32.82 assets are kept. MediaPipe `*.task` models are omitted (the Dockerfile downloads them). Patient runtime folders (`data/`, `uploads/`, `outputs/`) and Space secrets are **not** stored here.

`kinematic_analysis/videos` and `backend/results` are **not duplicated** in this folder (they are large). They remain on the git tag `backup/2026-09-16-full-v32.82`.

Dirty local CRA stubs (`AuthGate.jsx`, `analysisPlan.js`, `index.js`, `patientImport.js`, `thesisDocs.js`) are **not** in this freeze — GitHub HEAD is the good source.

---

## 1. Restore the Hugging Face Space (production)

From a machine that can push to the Space:

```bash
git clone https://huggingface.co/spaces/AbdelrahmanSabee/raedai.git hf_repo
./REFERENCE_SNAPSHOT_v32.82/restore_hf_space.sh hf_repo
cd hf_repo
git add -A
git commit -m "Restore RA.ED AI from REFERENCE_SNAPSHOT_v32.82"
git push
```

Then wait for the Hugging Face Docker rebuild. Confirm `meta name="nl-version" content="32.82"` on https://abdelrahmansabee-raedai.hf.space/

Space secrets are **not** in this snapshot. They must still exist in the Space settings:

- `JWT_SECRET`
- `MFA_ENCRYPTION_KEY` (optional if it falls back to JWT_SECRET)
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_DRIVE_FOLDER_ID`

The MediaPipe `.task` model is not stored here. The Dockerfile downloads it at build time.

---

## 2. Restore GitHub / local development

```bash
# from the NeuroLab repo root
./REFERENCE_SNAPSHOT_v32.82/restore_github_source.sh .
cd frontend && npm ci && npm run build
```

Or copy only the clinic player / overlay files from `github_source/frontend/src/`.

Checkout the tag if you want the whole repo:

```bash
git fetch origin tag backup/2026-09-16-full-v32.82
git checkout backup/2026-09-16-full-v32.82
```
