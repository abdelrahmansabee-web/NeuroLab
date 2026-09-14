# RA.ED AI — full restore snapshot v32.52

**Date:** 14 Sep 2026  
**Purpose:** نسخة احتياطية كاملة من البرنامج الشغّال. لو حصل أي شيء، نرجع من هنا.

This folder is a frozen copy of the **working** RA.ED AI / NeuroLab program at clinic UI **32.52**.

| Where | What |
|-------|------|
| **This folder** `REFERENCE_SNAPSHOT_v32.52/` | Restore kit: GitHub source + live Hugging Face Space |
| **Git tag** `backup/2026-09-14-full-v32.52` | The whole GitHub repo at this point, including kinematic videos |
| **Git branch** `cursor/backup-full-v3252-f95a` | Same snapshot, easy to check out |
| **Live Space** | https://huggingface.co/spaces/AbdelrahmanSabee/raedai |
| **Live app** | https://abdelrahmansabee-raedai.hf.space/?_v=32.52 |

Integrity hashes: `MANIFEST.sha256`. Machine-readable metadata: `SNAPSHOT.json`.

---

## إيه اللي جوه المجلد؟

| جزء | المعنى |
|-----|--------|
| `hf_space/` | البرنامج الشغّال على Hugging Face (backend + Docker + build الواجهة 32.52) |
| `github_source/` | سورس GitHub كامل (frontend CRA + backend + deploy + ملفات الرسالة) بنفس حالة 32.52 |

لو **الـ Space** اتكسر → رجّع من `hf_space/`.  
لو **السورس على GitHub / الجهاز** اتكسر → رجّع من `github_source/`.

---

## What is inside

| Part | What was snapshotted | Version |
|------|----------------------|---------|
| `hf_space/` | Live Hugging Face Space (FastAPI + Docker + CRA `frontend/build`) | **32.52** — JS `main.d669af20.js`, CSS `main.6977eca3.css` |
| `github_source/` | GitHub monorepo source used to produce that Space | **32.52** |

**HF commit:** `deceee5977f09e9e8e3d58521fc638d43fc83d18`  
(`v32.52: use the supplied transparent Raed logo PNG`)

**GitHub source commit (parent of this snapshot):** see `SNAPSHOT.json` → `github.source_commit`.

JavaScript **source maps** (`*.js.map`) are omitted. Stale older `main.<hash>.js` bundles on the Space are omitted; only the live 32.52 assets are kept. MediaPipe `*.task` models are omitted (the Dockerfile downloads them). Patient runtime folders (`data/`, `uploads/`, `outputs/`) and Space secrets are **not** stored here.

`kinematic_analysis/videos` and `backend/results` are **not duplicated** in this folder (they are large). They remain on the git tag `backup/2026-09-14-full-v32.52`.

---

## 1. Restore the Hugging Face Space (production)

From a machine that can push to the Space:

```bash
git clone https://huggingface.co/spaces/AbdelrahmanSabee/raedai.git hf_repo
./REFERENCE_SNAPSHOT_v32.52/restore_hf_space.sh hf_repo
cd hf_repo
git add -A
git commit -m "Restore RA.ED AI from REFERENCE_SNAPSHOT_v32.52"
git push
```

Then wait for the Hugging Face Docker rebuild. Confirm `meta name="nl-version" content="32.52"` on https://abdelrahmansabee-raedai.hf.space/

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
rsync -a REFERENCE_SNAPSHOT_v32.52/github_source/frontend/src/ frontend/src/
rsync -a REFERENCE_SNAPSHOT_v32.52/github_source/frontend/public/ frontend/public/
rsync -a REFERENCE_SNAPSHOT_v32.52/github_source/backend/ backend/
```

Or restore the whole source tree (keeps destination `.git`):

```bash
rsync -a --exclude '.git/' \
  REFERENCE_SNAPSHOT_v32.52/github_source/ ./
```

Then:

```bash
cd frontend
npm ci
npm run build
```

Copy `frontend/build` into the Space checkout before pushing, **or** keep using the already-built tree in `hf_space/frontend/build` (that is the live 32.52 bundle).

`github_source/frontend/src` includes the working copies of `AuthGate.jsx`, `analysisPlan.js`, `index.js`, `patientImport.js`, and `thesisDocs.js` that were used to compile 32.52.

---

## 3. Restore from the git tag (entire repo, including videos)

```bash
git fetch origin tag backup/2026-09-14-full-v32.52
git checkout backup/2026-09-14-full-v32.52
```

That tag is the full GitHub tree (source + kinematic videos + older snapshots still in history). This folder is the convenient restore kit for the running app.

---

## 4. After restore — checklist

1. Space `index.html` says **32.52** and loads `main.d669af20.js` + `main.6977eca3.css`.
2. Login / sidebar logo is `/raed-logo.png` (transparent astronaut + Arabic رائد). Do not flood-fill it.
3. Overlay player is still `frontend/src/ValidationOverlayPlayer.js` on original analysis clips. Overlay freeze remains v44 centered Gaussian, zero-lag `requestVideoFrameCallback`, no EMA, no `overlayFollow`.
4. iPad: hard-refresh with `?_v=32.52`. If the home-screen icon is old, remove the PWA and add it again.

---

*Do not edit the files in this folder to “fix” production. Copy them out, restore, then make new changes on a new branch.*
