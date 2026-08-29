# NeuroLab Reference Snapshot — v31.75

**Date:** 2026-08-29  
**Purpose:** نسخة احتياطية كاملة من البرنامج الشغال. لو التحليل أو الواجهة أو الـ Space اتكسر، رجّع الملفات من هنا.

This folder is a frozen copy of the **working** NeuroLab program:

| Part | What was snapshotted | Version |
|------|----------------------|---------|
| `hf_space/` | Live Hugging Face Space (complete running app: backend + auth + Vite frontend build) | frontend **31.75**, backend deploy **29.24** |
| `github_source/` | GitHub monorepo source as of `origin/master` (local/dev tree) | frontend **29.12** (Create React App) |

**HF commit:** `1b5b3469f4bf1103754e818437619ec114385691`  
(`frontend 31.75: glass capsule New/Save on top bar with session dirty glow`, 2026-08-17)

**GitHub commit:** `71d88619b682b3bac7d4842f82d574d09c595ba4` (`origin/master`)

Integrity hashes: `MANIFEST.sha256`. Metadata: `SNAPSHOT.json`.

JavaScript **source maps** (`*.js.map`) are omitted (they are not needed to restore the running app). The minified `frontend/build` bundle is included.

---

## Important: two codebases

The **complete working program on Hugging Face is newer** than GitHub:

- **HF (`hf_space/`)** — Vite + TypeScript (`frontend/src/App.tsx`), login/MFA/Google Drive (`auth.py`), overlay validation, Docker on port **7860**. This is what users open on the Space.
- **GitHub (`github_source/`)** — Create React App (`frontend/src/App.js`), FastAPI without `/auth/*`, local run on port **8000**.

If production (the Space) breaks, restore from **`hf_space/`**.  
If the GitHub/local tree breaks, restore from **`github_source/`**.

Do **not** copy HF `App.tsx` over GitHub `App.js` without a planned migration — they are different frontends.

---

## 1. Restore the Hugging Face Space (production)

From a machine that can push to the Space:

```bash
# Clone the live Space (or use your local hf_repo checkout)
git clone https://huggingface.co/spaces/AbdelrahmanSabee/neurolab.git hf_repo
cd hf_repo

# Replace tracked files with this snapshot (keeps .git)
# Run from the NeuroLab repo root:
rsync -a --delete --exclude '.git/' \
  REFERENCE_SNAPSHOT_v31.75/hf_space/ hf_repo/

cd hf_repo
git add -A
git commit -m "Restore NeuroLab from REFERENCE_SNAPSHOT_v31.75"
git push
```

If `rsync` is not available:

```powershell
Copy-Item -Recurse -Force "REFERENCE_SNAPSHOT_v31.75\hf_space\*" "hf_repo\"
```

Then wait for the Hugging Face Docker build to finish.

Space secrets are **not** in this snapshot. They must still exist in the Space settings:

- `JWT_SECRET`
- `MFA_ENCRYPTION_KEY` (optional if it falls back to JWT_SECRET)
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_DRIVE_FOLDER_ID`

The MediaPipe `.task` model is also not stored here (HF gitignores `*.task`). The Dockerfile downloads it at build time; `ensure_pose_model()` retries at runtime.

---

## 2. Restore GitHub / local development

```powershell
Copy-Item -Recurse -Force "REFERENCE_SNAPSHOT_v31.75\github_source\frontend\src" "frontend\src"
Copy-Item -Recurse -Force "REFERENCE_SNAPSHOT_v31.75\github_source\frontend\public" "frontend\public"
Copy-Item -Force "REFERENCE_SNAPSHOT_v31.75\github_source\frontend\package.json" "frontend\package.json"
Copy-Item -Recurse -Force "REFERENCE_SNAPSHOT_v31.75\github_source\backend\*" "backend\"
Copy-Item -Recurse -Force "REFERENCE_SNAPSHOT_v31.75\github_source\R_an\*" "R an\"
```

Then reinstall and run as usual (`backend/venv` + `npm install` / `npm run build`).

---

## 3. What is inside `hf_space/` (the complete app)

- `main.py` — FastAPI: `/analyze`, `/overlay-data`, `/unified-validation`, patients, PDF OCR, health
- `auth.py` + `security.py` — login, MFA, JWT, Google Drive backup
- `stroke_kinematic_pipeline.py`, `mediapipe_csv_extractor.py`, `overlay_data.py`, …
- `Dockerfile` — HF Docker Space, port 7860, CPU torch
- `frontend/src/` — Vite/React source (`App.tsx`)
- `frontend/build/` — production bundle already built (nl-version **31.75**)

---

## 4. Do not edit this folder

Copy files **out** when you need to restore. If you need a newer backup later, add a new folder (`REFERENCE_SNAPSHOT_v…`) instead of changing this one.
