# RA.ED AI — full restore snapshot v32.97

**Date:** 17 Sep 2026  
**Purpose:** نسخة احتياطية كاملة من البرنامج بعد 32.97: نعومة الهيكل zero-phase على عظام الجسم، ورجوع رسم lerp 32.72.

This folder is a frozen copy of the **working** RA.ED AI / NeuroLab program at clinic UI **32.97**.

Body overlay bones use the recorded-clip centered Gaussian at paint (same constants as HL fingers: radius 3, sigma 1.2) with 32.72 linear lerp between samples. Catmull-Rom overshoot is gone. Stored palm / speed_tremor / NVP JSON are unchanged. Overlay clock is the 32.82 span map. Compact overlay stays in-card. Expand uses the same `<video>` node. Overlay version stays 44. Task phases & variables and Movement quality & joint specs cards stay gone. Drive originals upload as real multipart video.

| Where | What |
|-------|------|
| **This folder** `REFERENCE_SNAPSHOT_v32.97/` | Restore kit: GitHub source + live Hugging Face Space |
| **Git tag** `backup/2026-09-17-full-v32.97` | The GitHub repo at this point |
| **Git branch** `cursor/backup-full-v3297-f95a` | Same snapshot, easy to check out |
| **Live Space** | https://huggingface.co/spaces/AbdelrahmanSabee/raedai |
| **Live app** | https://abdelrahmansabee-raedai.hf.space/?_v=32.97 |

Integrity hashes: `MANIFEST.sha256`. Machine-readable metadata: `SNAPSHOT.json`.

---

## إيه اللي جوه المجلد؟

| جزء | المعنى |
|-----|--------|
| `hf_space/` | البرنامج الشغّال على Hugging Face (backend + Docker + build الواجهة 32.97) |
| `github_source/` | سورس GitHub (frontend CRA + backend + deploy) بنفس حالة 32.97 |

لو **الـ Space** اتكسر → رجّع من `hf_space/`.  
لو **السورس على GitHub / الجهاز** اتكسر → رجّع من `github_source/`.

---

## What is inside

| Part | What was snapshotted | Version |
|------|----------------------|---------|
| `hf_space/` | Live Hugging Face Space (FastAPI + Docker + CRA `frontend/build`) | **32.97** — JS `main.02a4dd26.js`, CSS `main.21e1d84a.css` |
| `github_source/` | GitHub source that produced this clinic UI | **32.97** |

**HF commit:** `a688d87af99d0d735b4b1583a65d3fe7cb39f3ec`  
(`32.97: Zero-phase overlay body bones; restore lerp paint`)

**GitHub source commit (parent of this snapshot):** `008a65f5fcbf14330baf6a3fcb7f1c2e89c0206f`

JavaScript **source maps** (`*.js.map`) are omitted. Stale older `main.<hash>.js` bundles on the Space are omitted; only the live 32.97 assets are kept. MediaPipe `*.task` models are omitted (the Dockerfile downloads them). Patient runtime folders (`data/`, `uploads/`, `outputs/`) and Space secrets are **not** stored here.

`kinematic_analysis/videos` and `backend/results` are **not duplicated** in this folder (they are large). They remain on the git tag `backup/2026-09-17-full-v32.97`.

Dirty local CRA stubs (`AuthGate.jsx`, `analysisPlan.js`, `index.js`, `patientImport.js`, `thesisDocs.js`) are **not** in this freeze — GitHub HEAD is the source.

---

## 1. Restore the Hugging Face Space (production)

From a machine that can push to the Space:

```bash
git clone https://huggingface.co/spaces/AbdelrahmanSabee/raedai.git hf_repo
./REFERENCE_SNAPSHOT_v32.97/restore_hf_space.sh hf_repo
cd hf_repo
git add -A
git commit -m "Restore RA.ED AI from REFERENCE_SNAPSHOT_v32.97"
git push
```

Then wait for the Hugging Face Docker rebuild. Confirm `meta name="nl-version" content="32.97"` on https://abdelrahmansabee-raedai.hf.space/

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
./REFERENCE_SNAPSHOT_v32.97/restore_github_source.sh .
cd frontend && npm ci && npm run build
```

Or copy only the clinic player / overlay files from `github_source/frontend/src/`.

Checkout the tag if you want the whole repo:

```bash
git fetch origin tag backup/2026-09-17-full-v32.97
git checkout backup/2026-09-17-full-v32.97
```
