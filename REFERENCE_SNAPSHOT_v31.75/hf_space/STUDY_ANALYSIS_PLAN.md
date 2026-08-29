# PETTLEP AOMI RCT — Statistical Analysis Plan (SAP)

**Study:** Immediate Effects of a Single Session of PETTLEP-Based AOMI on Upper Limb Kinematics in Stroke Survivors  
**Design:** Single-blind, pretest–posttest, parallel RCT (CONSORT 2010)  
**Groups:** AOMI (n=14) vs Cognitive/Somatic Control (n=14)  
**Target N:** 28 (G*Power: f=0.40, α=.05, power=.95, r=.50)

---

## 1. Primary Outcome

| Variable | SPSS columns | Direction | Analysis |
|----------|--------------|-----------|----------|
| **pause_pct** | `pause_pct_Pre`, `pause_pct_Post` (+ alias `smoothness_pause_pct_*`) | Lower = smoother | **2×2 Mixed ANOVA** (α=.05, no correction) |

---

## 2. Secondary Kinematic (8 tests — Holm–Bonferroni k=8)

| Variable | Columns | Better |
|----------|---------|--------|
| trunk_palm | `_Pre`, `_Post` | ↓ |
| shve_sw / total_depression_cm | `_Pre`, `_Post`, `_Healthy` | ↓ |
| duration / total_duration_s | `_Pre`, `_Post` | ↓ |
| peak_v_sw | `_Pre`, `_Post` | ↑ |
| mean_v_sw | `_Pre`, `_Post` | ↑ |
| path_sw | `_Pre`, `_Post` | ↓ |
| lat_range_sw | `_Pre`, `_Post` | ↑ |
| elbow_max / total_max_elbow_deg | `_Pre`, `_Post` | — |

---

## 3. Exploratory Kinematic (5 — no correction)

nsub, sparc_whole, sparc_sub, path_eff, trunk_x_sw

---

## 4. Clinical / PRO

WMFT-4, VAMS-4×4, VAS, KVIQ-10, MDRS (post-only Mann–Whitney)

---

## 5. Export features (NeuroLab v6)

- **3-trial mean:** backend auto-detects movement bouts in one recording; mean metrics (velocity profile from best SPARC trial)
- **Healthy baseline:** `{var}_Healthy` + manuscript alias columns in CSV
- **LOCF:** checkbox on Export tab → imputes missing Post from Pre + `LOCF_imputed` flag
- **CONSORT counts:** editable in Analysis Dashboard

---

## 6. SPSS Workflow

Export `neuro_study_analysis.sps` from Analysis Dashboard (12 steps).

CLI: `python backend/study_analysis.py master_study_data.csv`

---

*Aligned with `frontend/src/analysisPlan.js` and `backend/study_analysis.py`.*
