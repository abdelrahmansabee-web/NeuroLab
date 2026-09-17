# RA.ED AI — full restore snapshot v32.96

**Date:** 17 Sep 2026  
**Purpose:** نسخة احتياطية كاملة من البرنامج بعد 32.96: حذف Task phases، إصلاح حساب الـ NVP، ونعومة الهيكل Catmull-Rom.

This folder is a frozen copy of the **working** RA.ED AI / NeuroLab program at clinic UI **32.96**.

NVP rows recount from the same overlay `peak_frames` windows so total cannot be lower than reach/drink/return. Overlay landmarks use clock-locked centripetal Catmull-Rom (hits every sample, no EMA lag). Task phases & variables and Movement quality & joint specs cards are gone. Overlay clock is the 32.82 span map. Compact overlay stays in-card. Expand uses the same `<video>` node. Overlay version stays 44. Drive originals upload as real multipart video.

| Where | What |
|-------|------|
| **This folder** `REFERENCE_SNAPSHOT_v32.96/` | Restore kit: GitHub source + live Hugging Face Space |
| **Git tag** `backup/2026-09-17-full-v32.96` | The GitHub repo at this point |
| **Git branch** `cursor/backup-full-v3296-f95a` | Same snapshot, easy to check out |
| **Live Space** | https://huggingface.co/spaces/AbdelrahmanSabee/raedai |
| **Live app** | https://abdelrahmansabee-raedai.hf.space/?_v=32.96 |

Integrity hashes: `MANIFEST.sha256`. Machine-readable metadata: `SNAPSHOT.json`.

---

## إيه اللي جوه المجلد؟

| جزء | المعنى |
|-----|--------|
| `hf_space/` | البرنامج الشغّال على Hugging Face (backend + Docker + build الواجهة 32.96) |
| `github_source/` | سورس GitHub (frontend CRA + backend + deploy) بنفس حالة 32.96 |

لو **الـ Space** اتكسر → رجّع من `hf_space/`.  
لو **السورس على GitHub / الجهاز** اتكسر → رجّع من `github_source/`.

---

## What is inside

| Part | What was snapshotted | Version |
|------|----------------------|---------|
| `hf_space/` | Live Hugging Face Space (FastAPI + Docker + CRA `frontend/build`) | **32.96** — JS `main.f4b78822.js`, CSS `main.21e1d84a.css` |
| `github_source/` | GitHub source that produced this clinic UI | **32.96** |

**HF commit:** `40fe7f1cdea950f396bc5eed672588148ae1e089`  
(`32.96: Recount NVP from overlay peaks; Catmull-Rom skeleton; drop Task phases`)

**GitHub source commit (parent of this snapshot):** `a6baf01c57c7b2631e65c1dd6d911ca1094e8a3c`

JavaScript **source maps** (`*.js.map`) are omitted. Stale older `main.<hash>.js` bundles on the Space are omitted; only the live 32.96 assets are kept. MediaPipe `*.task` models are omitted (the Dockerfile downloads them). Patient runtime folders (`data/`, `uploads/`, `outputs/`) and Space secrets are **not** stored here.

`kinematic_analysis/videos` and `backend/results` are **not duplicated** in this folder (they are large). They remain on the git tag `backup/2026-09-17-full-v32.96`.

Dirty local CRA stubs (`AuthGate.jsx`, `analysisPlan.js`, `index.js`, `patientImport.js`, `thesisDocs.js`) are **not** in this freeze — GitHub HEAD is the source.

---

## 1. Restore the Hugging Face Space (production)

From a machine that can push to the Space:

```bash
git clone https://huggingface.co/spaces/AbdelrahmanSabee/raedai.git hf_repo
./REFERENCE_SNAPSHOT_v32.96/restore_hf_space.sh hf_repo
cd hf_repo
git add -A
git commit -m "Restore RA.ED AI from REFERENCE_SNAPSHOT_v32.96"
git push
```

Then wait for the Hugging Face Docker rebuild. Confirm `meta name="nl-version" content="32.96"` on https://abdelrahmansabee-raedai.hf.space/

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
./REFERENCE_SNAPSHOT_v32.96/restore_github_source.sh .
cd frontend && npm ci && npm run build
```

Or copy only the clinic player / overlay files from `github_source/frontend/src/`.

Checkout the tag if you want the whole repo:

```bash
git fetch origin tag backup/2026-09-17-full-v32.96
git checkout backup/2026-09-17-full-v32.96
```
