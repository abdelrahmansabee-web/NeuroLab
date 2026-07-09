/** Thesis-ready documents — export from Analysis Dashboard */

export const PROGRAM_GAPS = [
  { priority: "medium", item: "Phase-specific metrics in CSV", detail: "Manuscript lists forward/wipe/return segments — export as optional columns or separate sheet." },
  { priority: "medium", item: "Sync export_spss.py", detail: "Legacy per-file CSV exporter; align with master_study_data.csv schema or remove." },
  { priority: "low", item: "ClinicalTrials.gov ID field", detail: "Add registration number to demographics + report header." },
  { priority: "low", item: "Batch re-analyze all patients", detail: "Re-run kinematics pipeline after algorithm updates." },
];

export function generateLiteratureReviewMarkdown() {
  return `# Literature Review (Condensed — Manuscript Introduction)
## Immediate Effects of PETTLEP-Based AOMI on Upper Limb Kinematics in Stroke Survivors

*NeuroLab / Istinye University — ready for thesis committee & manuscript paste-up*

---

## 1. Stroke and upper limb disability

Stroke is the second leading cause of death and a major source of adult disability worldwide (Feigin et al., 2022). Approximately 70–80% of survivors present with upper-limb hemiparesis acutely, and more than two-thirds retain long-term functional limitations (Facciorusso et al., 2024; Schwarz et al., 2022). Impairment reflects not only weakness but **disordered movement quality**: fragmented velocity profiles, compensatory trunk lean, and shoulder girdle elevation (Rohrer et al., 2002; Cirstea & Levin, 2000; Massie et al., 2012).

**Relevance:** The Reach & Wipe task and kinematic outcomes (pause %, SPARC, trunk compensation) directly quantify these signatures.

---

## 2. Motor control: proximal-to-distal organization

Normal reaching depends on **anticipatory postural adjustments (APAs)** — trunk stabilisation 50–100 ms before arm movement (Massion, 1994; Hodges & Richardson, 1997). The supplementary motor area and corticoreticular pathways sequence axial control before corticospinal drive to the arm (Lemon, 2008; Matsuyama et al., 2004). After stroke, APAs are delayed and compensatory strategies dominate (Dickstein et al., 2004).

**Relevance:** The five PETTLEP-AOMI blocks mirror this hierarchy (initiation → trunk → shoulder → elbow → integrated smoothness).

---

## 3. Post-stroke neurophysiology

Lesions disrupt corticospinal fractionation and increase reliance on synergistic, stereotyped patterns (Dewald et al., 1995). **Spasticity** reflects loss of descending inhibition at the spinal level (Lance, 1980; Nielsen et al., 2007), producing co-contraction that fragments velocity profiles during elbow extension. Chronic biomechanical stiffening may superimpose on neural spasticity (Nelson et al., 2018; Wang et al., 2016).

**Relevance:** Imagery targeting "muscle quieting" and smooth elbow opening addresses reciprocal inhibition deficits hypothesised to reduce pause % and submovement count.

---

## 4. Motor imagery (MI)

MI activates premotor, SMA, parietal, cerebellar, and M1 networks overlapping with execution — **functional equivalence** (Jeannerod, 2001; Decety & Grezes, 1999; Lotze et al., 1999). TMS studies show increased corticospinal excitability during upper-limb MI (Stinear et al., 2006). H-reflex work suggests spinal reciprocal inhibition can be modulated (Morioka & Yagi, 2003). Meta-analyses support UL gains when MI is combined with conventional therapy (Machado et al., 2019; Guerra et al., 2017).

---

## 5. Action observation (AO) and AOMI

Mirror-neuron circuits in premotor and parietal cortex respond to observed and executed actions (Rizzolatti et al., 2001, 2004). **Sequential AO → MI** produces greater, more specific activation than either alone (Vogt et al., 2013; Guillot et al., 2008). Kim et al. (2022) demonstrated AOMI benefits on UL function and corticospinal excitability post-stroke.

**Gap addressed:** Prior AOMI trials interleaved physical practice; this study isolates observation + imagery only.

---

## 6. PETTLEP model

Holmes & Collins (2001) defined seven dimensions — Physical, Environment, Task, Timing, Learning, Emotion, Perspective — to maximise ecological validity of imagery. Internal, kinesthetic perspective enhances corticospinal excitability (Stinear et al., 2006; Wright et al., 2014). PETTLEP-structured AOMI without physical practice in stroke remains understudied.

---

## 7. Kinematic measurement

Ordinal scales (e.g., FMA) cannot capture subtle trajectory quality (Massie et al., 2012). **Markerless pipelines** (MediaPipe + monocular depth scaling in NeuroLab) enable clinic-feasible, objective metrics: SPARC smoothness, trunk-to-palm ratio, shoulder elevation, elbow angle, movement time, and peak velocity (Schwarz et al., 2022).

**Primary outcome:** \`sparc\` — spectral arc length of palm velocity (Balasubramanian et al., 2012/2015). More negative values indicate smoother movement.

---

## 8. Research gap summary

| Gap | This study |
|-----|------------|
| No acute single-session AOMI kinematics | Pre–post within one session |
| No PETTLEP-individualised AOMI in stroke | Mirror-reversed video + notice–name–transfer |
| AO/MI confounded with motor practice | No interleaved physical execution |
| Ordinal clinical endpoints only | NeuroLab objective kinematics + WMFT-4 |

---

## Key references (numbered for manuscript)

1. Feigin VL et al. WSO Global Stroke Fact Sheet 2022. *Int J Stroke* 2022.  
8. Rohrer B et al. Movement smoothness changes during stroke recovery. *J Neurosci* 2002.  
9. Cirstea MC, Levin MF. Compensatory strategies for reaching in stroke. *Brain* 2000.  
28–32. MI/AOMI neurophysiology and reviews (Jeannerod; Machado; Kim 2022).  
36. Holmes PS, Collins DJ. PETTLEP model. *J Applied Sport Psychol* 2001.  
Field A (2018). *Discovering Statistics Using IBM SPSS Statistics*.  
Cohen J (1988). *Statistical Power Analysis*.  
Schulz KF et al. CONSORT 2010. *BMJ* 2010.

---
*Generated by NeuroLab Analysis Dashboard — align variable names with \`analysisPlan.js\`.*
`;
}

export function generateConsortSapMarkdown() {
  return `# CONSORT Flow & Statistical Analysis Plan (SAP)
## PETTLEP-Based AOMI RCT — n = 28

*For thesis committee review — NeuroLab v6*

---

## A. CONSORT 2010 flow diagram (template)

\`\`\`
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
\`\`\`

**Fill live counts from Analysis Dashboard → CONSORT Flow panel.**

---

## B. Study design summary

| Element | Specification |
|---------|---------------|
| Design | Single-blind, parallel RCT, pretest–posttest |
| Setting | Istinye University Liv Bahçeşehir Hospital, Neurorehabilitation Clinic |
| Groups | 1 = PETTLEP-AOMI (22 min); 2 = Cognitive/somatic control (22 min) |
| Randomisation | 1:1 permuted blocks, stratified by sex & MAS (0–1+ vs 2) |
| Blinding | Participants unblinded; assessor & kinematics pipeline blinded |
| Task | Reach & Return — affected UL, 3 trials, **mean per timepoint** |
| ITT | All randomised participants analysed; LOCF for missing Post |

---

## C. Outcomes hierarchy

### Primary (α = .05, no correction)
| Variable | SPSS columns | Direction | Test |
|----------|--------------|-----------|------|
| SPARC | \`sparc_Pre\`, \`sparc_Post\` | More negative = smoother | 2×2 Mixed ANOVA |

### Secondary kinematic (5 tests — **Holm–Bonferroni**, k=5)
| # | Variable | Columns | Better |
|---|----------|---------|--------|
| 1 | Trunk ratio | trunk_ratio_Pre/Post | ↓ |
| 2 | Shoulder elevation (norm) | shoulder_vert_norm_Pre/Post | ↓ |
| 3 | Elbow angle (mean) | elbow_angle_mean_Pre/Post | ↑ |
| 4 | Movement time | movement_time_sec_Pre/Post | ↓ |
| 5 | Peak velocity | peak_velocity_px_s_Pre/Post | ↑ |

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
6. **Missing data:** LOCF primary (export checkbox in NeuroLab); Mixed Models sensitivity.  
7. **Software:** IBM SPSS 24+; confirmatory Python via \`study_analysis.py\`.

---

## E. Holm–Bonferroni procedure (secondary kinematic, k=8)

1. Run 8 separate GLMs (see \`neuro_study_analysis.sps\` section 7).  
2. Extract Group×Time interaction **p** for each.  
3. Sort: p₁ ≤ p₂ ≤ … ≤ p₈.  
4. Find largest k where pₖ ≤ 0.05 / (8 − k + 1).  
5. Report uncorrected and Holm-adjusted results in Table 3.

---

## F. NeuroLab export workflow

1. Complete all patients (Group, Pre/Post kinematics, clinical scales).  
2. **Analysis Dashboard → Export** \`master_study_data.csv\` (optional LOCF).  
3. **Analysis Dashboard → Export** \`neuro_study_analysis.sps\`.  
4. SPSS: run syntax → copy OMS to Word.  
5. Optional: \`python backend/study_analysis.py master_study_data.csv\`.

---
*SAP version 1.1 — NeuroLab auto-generated.*
`;
}
