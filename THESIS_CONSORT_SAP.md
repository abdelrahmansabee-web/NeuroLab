# CONSORT Flow & Statistical Analysis Plan (SAP)
## PETTLEP-Based AOMI RCT — n = 28

*For thesis committee review — NeuroLab v6*

---

## A. CONSORT 2010 flow diagram (template)

```
                    ASSESSED FOR ELIGIBILITY (n = ___ )
                              |
              +---------------+---------------+
              |                               |
        EXCLUDED (n = ___ )              ENROLLED (n = 28 )
        • Not meeting incl. (n= )              |
        • Declined (n= )                       RANDOMIZED (n = 28 )
        • Other (n= )                    +------+------+
                                         |             |
                                  AOMI (n=14)   Control (n=14)
                                         |             |
                              Received intervention   Received control
                              (n= )                   (n= )
                              Did not receive (n= )   Did not receive (n= )
                              • Reason:               • Reason:
                                         |             |
                              POST-ASSESSMENT         POST-ASSESSMENT
                              (n= )                   (n= )
                              Lost to follow-up       Lost to follow-up
                              (n= )                   (n= )
                                         |             |
                              ANALYZED (ITT)          ANALYZED (ITT)
                              (n= )                   (n= )
```

**Fill live counts from clinic logs.** NeuroLab dashboard shows current enrolled n (AOMI / Control / kinematics complete).

---

## B. Study design summary

| Element | Specification |
|---------|---------------|
| Design | Single-blind, parallel RCT, pretest–posttest |
| Setting | Istinye University Liv Bahçeşehir Hospital, Neurorehabilitation Clinic |
| Groups | 1 = PETTLEP-AOMI (22 min); 2 = Cognitive/somatic control (22 min) |
| Randomisation | 1:1 permuted blocks, stratified by sex & MAS (0–1+ vs 2) |
| Blinding | Participants unblinded; assessor & kinematics pipeline blinded |
| Task | Reach & Wipe — affected UL, 3 trials, **mean per timepoint** |
| ITT | All randomised participants analysed; LOCF for missing Post |

---

## C. Outcomes hierarchy

### Primary (α = .05, no correction)
| Variable | SPSS columns | Direction | Test |
|----------|--------------|-----------|------|
| Pause time % | `pause_pct_Pre`, `pause_pct_Post` | Lower = smoother | 2×2 Mixed ANOVA |

**Primary inference:** Group × Time interaction on `pause_pct`.

### Secondary kinematic (12 tests — **Holm–Bonferroni** within family; all except pause_pct)
| # | Variable | Columns | Better |
|---|----------|---------|--------|
| 1 | Submovement count | nsub_Pre/Post | ↓ |
| 2 | Overall SPARC | sparc_whole_Pre/Post | ↑ |
| 3 | Sub-move SPARC | sparc_sub_Pre/Post | ↑ |
| 4 | Trunk compensation | trunk_palm_Pre/Post | ↓ |
| 5 | Wiping reach | lat_range_sw_Pre/Post | ↑ |
| 6 | Peak hand speed | peak_v_sw_Pre/Post | ↑ |
| 7 | Path efficiency | path_eff_Pre/Post | ↓ |
| 8 | Mean hand speed | mean_v_sw_Pre/Post | ↑ |
| 9 | Trunk lateral disp. | trunk_x_sw_Pre/Post | ↓ |
| 10 | Shoulder lift | shve_sw_Pre/Post | — |
| 11 | Movement time | duration_Pre/Post | ↓ |
| 12 | Hand path length | path_sw_Pre/Post | ↓ |

### Clinical secondary
WMFT-4 rating & time; VAMS-4 (Happy, Calm, Sad, Tense); VAS pain; KVIQ-10 visual & kinesthetic.

### Post-only / descriptive
MDRS motor control change; IPAQ MET-min/wk.

---

## D. Analysis decision rules

1. **Normality:** Shapiro–Wilk on Pre, Post, Δ per group (α=.05).  
2. **If normal:** GLM repeated measures, Type III SS, Group × Time interaction.  
3. **If non-normal:** Wilcoxon signed-rank (within group); Mann–Whitney on Δ (between groups).  
4. **Baseline equivalence:** Independent t-test / Mann–Whitney on Pre + demographics.  
5. **Effect sizes:** Partial η² (ANOVA); Cohen's d (pairwise); rank-biserial r (non-parametric).  
6. **Missing data:** LOCF primary; Mixed Models sensitivity.  
7. **Software:** IBM SPSS 24+; confirmatory Python via `study_analysis.py`.

---

## E. Holm–Bonferroni procedure (secondary kinematic, k=12)

1. Run 12 separate GLMs (see `neuro_study_analysis.sps` section 7).  
2. Extract Group×Time interaction **p** for each.  
3. Sort: p₁ ≤ p₂ ≤ … ≤ p₁₂.  
4. Find largest k where pₖ ≤ 0.05 / (12 − k + 1).  
5. Report uncorrected and Holm-adjusted results in Table 3.

---

## F. SAP tables for thesis

| Table | Content |
|-------|---------|
| **Table 1** | Demographics + baseline kinematics/clinical (M±SD); equivalence p |
| **Table 2** | Primary outcome: descriptives + mixed ANOVA (F, p, ηp²) + simple effects |
| **Table 3** | Secondary kinematic interactions (uncorrected + Holm-adjusted) |
| **Table 4** | Clinical outcomes |
| **Table 5** | KVIQ moderator correlations by group |
| **Figure 1** | CONSORT flow |
| **Figure 2** | Combined velocity profile (Pre/Post by group) |

---

## G. NeuroLab export workflow

1. Complete all patients in app (Group, Pre/Post kinematics, clinical scales).  
2. **Analysis Dashboard → Export** `master_study_data.csv`.  
3. **Analysis Dashboard → Export** `neuro_study_analysis.sps`.  
4. SPSS: run syntax → copy OMS to Word.  
5. Optional: `python backend/study_analysis.py master_study_data.csv`.

---

## H. Power calculation (documented)

G*Power: 2×2 RM ANOVA, f = 0.40, α = .05, power = .95, r = .50 → N = 24; +15% dropout → **N = 28** (14/group).

---
*SAP version 1.0 — NeuroLab auto-generated. Register on ClinicalTrials.gov before first enrolment.*
