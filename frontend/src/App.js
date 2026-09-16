// ============================================================
// Stroke Rehabilitation Platform ? Frontend v6.5
// ============================================================
/* eslint-disable no-undef */

import React, { useState, useRef, useCallback, useEffect, useLayoutEffect, useMemo, startTransition } from "react";
import ReactDOM from "react-dom";
import { motion, AnimatePresence, animate, useMotionValue, useReducedMotion } from "framer-motion";
import {
  NL_SPRING_TOAST,
  NL_TWEEN_MENU,
} from "./motionPresets";
import {
  User, Activity, Sliders, TrendingUp, Heart, Timer, Cpu, FileText,
  Menu, X, ChevronRight, Play, Square, RotateCcw, Copy, Check,
  Info, Save, BarChart3, Brain, Image as ImageIcon,
  RefreshCw, FileSpreadsheet, Upload, FileUp,
  Database, Search, Edit3, Trash2, Archive, PlusCircle, Activity as ActivityIcon, Video, FileCheck, Sparkles, Users, LogOut, MoreHorizontal, Download, HardDrive,
} from "lucide-react";
import * as XLSX from "xlsx";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import {
  STUDY_DESIGN, SPSS_WORKFLOW, KINEMATIC_VARS, orderedKinematicVars, orderedKinematicResultsTableVars, CLINICAL_VARS,
  buildMasterDataset, buildMasterRow, generateStudySPSSSyntax, analyzeAllOutcomes,
  DEMO_SPSS_KEYS, exportDemographicsForSpss,
  fmtP, sigStars,   getPatientKinPhase, pickKinField,
  calcImprovement, calcGap, formatKinPrePostPct, formatKinPrePostAbsDelta, formatKinPostHealthyPct, formatKinValue,
  kinCrossPhaseComparable, kinCrossPhaseDeltaStatus,
} from "./analysisPlan";
import {
  PROGRAM_GAPS, generateLiteratureReviewMarkdown, generateConsortSapMarkdown,
} from "./thesisDocs";
import { importPatientFile, buildImportRecord } from "./patientImport";
import { ValidationOverlayPlayer, computeOverlayMetrics } from "./ValidationOverlayPlayer";
import { overlayPlayerMountDelayMs } from "./overlayVideoPlayback";
import { clinicTrialRoleFromPhase, summarizeOverlayClock } from "./analysisPhaseCompare";
import SessionStatusBar, { revealSessionStatusBar } from "./SessionStatusBar";
import PtrIosSpinner from "./PtrIosSpinner";
import AuthGate, { authHeaders, clearAuthToken, rememberLoginEmail } from "./AuthGate";
import { downloadBlob as downloadBlobUtil, blobToBase64 } from "./downloadUtils";
import {
  loadValidationSessionArtifact,
  saveValidationSessionArtifact,
  shouldHydrateMediaBlobIntoState,
  shouldHydrateOverlayIntoState,
  validationCacheMatchesResult,
} from "./validationSessionCache";
import {
  backupValidationArtifactsToDrive,
  restoreValidationArtifactsFromDrive,
  validationUnifiedDriveName,
} from "./validationDriveSync";
import { canonicalDriveName, clinicReportDriveName } from "./driveDocIdentity";
import {
  DRIVE_RECALL_EVENT,
  formatRecallToast,
  recallAnalyzedSessionsFromDrive,
} from "./driveSessionRestore";
import {
  analysisResultErrorMessage,
  ANALYZE_POLL_MS,
  analyzePollExceeded,
  isKinAnalyzeActive,
  setKinAnalyzeActive,
} from "./kinAnalyzeGuard";
import {
  resolveKinMetricValue,
  loadLiveKinResults,
  KIN_RESULTS_LS_KEY,
  formatPanelAlignedKinValue,
  isPanelTableKey,
} from "./kinMetrics";
import { inferWmftFromKinematics, applyWmftInference } from "./wmftInference";
import { MOVEMENT_PROFILE_FIELDS, MOVEMENT_PROFILE_GROUP_LABELS, MOVEMENT_PROFILE_GROUP_ORDER, resolveProfileMetric, formatProfileValue, getMovementProfile } from "./movementProfile";
import {
  CLINICAL_MOVEMENT_TASKS,
  CLINICAL_DOMAIN_LABELS,
  TASK_PHASE_METRIC_KEYS,
  TASK_PHASE_NOTES,
  clinicalTaskById,
  clinicalTaskDomain,
  clinicalTasksForDomain,
} from "./clinicalTasks";
import { describeCompletionMismatch } from "./taskCompletion";
import {
  buildAllTaskExcelFiles,
  patientTaskKinSheetRows,
} from "./clinicExcelExport";

const SAFE_TOP = "calc(env(safe-area-inset-top, 0px) + 8px)";

const NA = "\u2014";
const isMissing = (x) => x == null || x === "" || x === "?" || x === NA;
const showVal = (x) => (isMissing(x) ? NA : String(x));

const BG = "/bg.jpg";

/* ?? Uniform liquid glass ? sidebar and all panels share the same near-clear token ?? */
const GLASS_CLS = "bg-white/[0.008] backdrop-blur-md backdrop-saturate-[2.25] border border-white/[0.03]";
const GLASS_PANEL_CLS = "bg-white/[0.028] backdrop-blur-lg backdrop-saturate-[1.85] border border-white/[0.05]";
const SIDEBAR_CLS = "bg-white/[0.008] backdrop-blur-md backdrop-saturate-[2.25] border border-white/[0.03]";
const INPUT_CLS = "bg-[rgba(220,235,255,0.04)] border border-white/[0.03]";

const GSELECT_MENU_BOX = {
  borderRadius: "12px",
};

/** Same class stack as DesktopUnifiedTopBar / app top chrome */
const GLASS_TOPBAR_SHELL = `relative overflow-hidden app-topbar-glass glass-float ${GLASS_CLS}`;

const BG_FILTER = "blur(24px) brightness(0.55) saturate(0.80)";
const BG_SCALE = "scale(1.08)";
const BG_OVERLAY = "rgba(8, 8, 8, 0.18)";

function isIOSDevice() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function isStandalonePWA() {
  return window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true;
}

const RAED_APP_ORIGIN = "https://abdelrahmansabee-raedai.hf.space";

/** Google OAuth cannot finish inside the huggingface.co Spaces iframe. */
function openConnectDrive() {
  const dest = `${RAED_APP_ORIGIN}/connect-drive`;
  try {
    if (window.top && window.top !== window.self) {
      window.top.location.href = dest;
      return;
    }
  } catch (e) { /* ignore */ }
  if (typeof window !== "undefined" && /huggingface\.co$/i.test(window.location.hostname)) {
    window.location.href = dest;
    return;
  }
  window.location.href = "/connect-drive";
}

/** iPad / iPhone / coarse pointer ? lighter glass & no Framer tap springs. */
function isTouchUi() {
  if (typeof window === "undefined") return false;
  if (isIOSDevice() || isStandalonePWA()) return true;
  try {
    return window.matchMedia("(pointer: coarse)").matches;
  } catch {
    return false;
  }
}

function nlMotionTap(scale = 0.97) {
  return isTouchUi() ? undefined : { scale };
}

function nlMotionHover(scale = 1.02) {
  return isTouchUi() ? undefined : { scale };
}

const SIDEBAR_W = 255;
const SIDEBAR_X_HIDDEN = -280;
const MOBILE_SIDEBAR_W = "75%";
/** Sidebar aside slide (transform); main/top bar use width + inset for centered content. */
const SIDEBAR_SHELL_TRANSITION = "transform 320ms cubic-bezier(0.32, 0.72, 0, 1)";
const SIDEBAR_LAYOUT_TRANSITION = "left 320ms cubic-bezier(0.32, 0.72, 0, 1), width 320ms cubic-bezier(0.32, 0.72, 0, 1), margin-left 320ms cubic-bezier(0.32, 0.72, 0, 1)";
function sidebarPushWidth() {
  if (typeof window === "undefined") return SIDEBAR_W;
  if (window.matchMedia("(min-width: 768px)").matches) return SIDEBAR_W;
  return window.innerWidth;
}

const MOBILE_TOPBAR_PT = "4.75rem";
const PTR_THRESHOLD = 72;
const PTR_MAX_PULL = 118;

const FLOAT_L = "0 36px 90px -40px rgba(0,0,0,0.20)";
const FLOAT_M = "0 24px 60px -30px rgba(0,0,0,0.18)";

const TOPBAR_ROW_H = 52;
const TOPBAR_FILLET_R = 18;
const TOPBAR_CORNER_R = 12;

/** L-shaped outline; menuLeft = px from shell left to right column. */
function buildTopBarClipPath(w, rowH, menuLeft, menuExtraH, maxFillet = TOPBAR_FILLET_R, stretching = false) {
  const r = TOPBAR_CORNER_R;
  if (!w || w <= 0) return "none";
  if (!stretching && menuExtraH <= 0) {
    return `path('M ${r} 0 H ${w - r} Q ${w} 0 ${w} ${r} V ${rowH - r} Q ${w} ${rowH} ${w - r} ${rowH} H ${r} Q 0 ${rowH} 0 ${rowH - r} V ${r} Q 0 0 ${r} 0 Z')`;
  }

  const h = Math.max(menuExtraH, 0);
  const totalH = rowH + h;
  const ml = Math.min(Math.max(menuLeft, r + 1), w - r - 1);
  const filletR = Math.min(maxFillet, maxFillet * Math.min(1, h / maxFillet));
  const bl = Math.min(TOPBAR_CORNER_R, Math.max(0, h * 0.5));
  const parts = [
    `M ${r} 0`,
    `H ${w - r}`,
    `Q ${w} 0 ${w} ${r}`,
    `V ${totalH - r}`,
    `Q ${w} ${totalH} ${w - r} ${totalH}`,
    `H ${ml + bl}`,
  ];

  if (bl > 0.5) {
    parts.push(`Q ${ml} ${totalH} ${ml} ${totalH - bl}`);
  } else {
    parts.push(`V ${totalH}`, `H ${ml}`);
  }

  parts.push(`V ${rowH + filletR}`);

  if (filletR > 0.5) {
    parts.push(`A ${filletR} ${filletR} 0 0 0 ${ml - filletR} ${rowH}`);
  } else {
    parts.push(`V ${rowH}`, `H ${ml}`);
  }

  parts.push(`H ${r}`, `Q 0 ${rowH} 0 ${rowH - r}`, `V ${r}`, `Q 0 0 ${r} 0`, "Z");
  return `path('${parts.join(" ")}')`;
}

const GLASS_FIELD = {
  backgroundColor: "rgba(220,235,255,0.04)",
  border: "1px solid rgba(255,255,255,0.03)",
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.02)",
  backdropFilter: "blur(12px) saturate(2.25)",
  WebkitBackdropFilter: "blur(12px) saturate(2.25)",
};

const SLIDER_GRAD = {
  sky:     ["rgba(14,165,233,0.8)",  "rgba(56,189,248,0.5)"],
  emerald: ["rgba(16,185,129,0.8)",  "rgba(52,211,153,0.5)"],
  amber:   ["rgba(245,158,11,0.8)",  "rgba(251,191,36,0.5)"],
  violet:  ["rgba(139,92,246,0.8)",  "rgba(167,139,250,0.5)"],
  rose:    ["rgba(244,63,94,0.8)",   "rgba(251,113,133,0.5)"],
  cyan:    ["rgba(6,182,212,0.8)",   "rgba(34,211,238,0.5)"],
};

const IPAQ_ACTS = [
  { id:"high", en:"High intensity (running, heavy work)", tr:"Yüksek yoğunluklu (koşma, ağır iş)", met:8 },
  { id:"medium", en:"Moderate intensity (brisk walking, housework)", tr:"Orta yoğunluklu (hızlı yürüyüş, ev işi)", met:4 },
  { id:"light", en:"Light activity (slow walking, daily movements)", tr:"Hafif aktivite (yavaş yürüyüş)", met:3.3 },
  { id:"sitting", en:"Total daily sitting time", tr:"Günlük oturma süresi", met:0 },
  { id:"extra", en:"Additional (cycling, swimming, etc.)", tr:"Ek aktiviteler (bisiklet, yüzme)", met:4 },
];

const MOTOR_ITEMS = [
  { key:"control", en:"How much do you feel you can control your muscles?", tr:"Kaslarınızı ne kadar kontrol edebildiğinizi hissediyorsunuz?", phase:"pre" },
  { key:"difference", en:"How much do you feel a difference in muscle control?", tr:"Kas kontrolünde ne kadar fark hissediyorsunuz?", phase:"post" },
];



const KGIA_MOVEMENTS = [
  { en:"Neck flexion/extension", tr:"Boyun fleksiyonu/ekstansiyonu", ue:false },
  { en:"Shoulder shrugging", tr:"Omuz silkme", ue:true },
  { en:"Forward shoulder flexion", tr:"Öne omuz fleksiyonu", ue:true },
  { en:"Elbow flexion", tr:"Dirsek fleksiyonu", ue:true },
  { en:"Thumb to finger tips", tr:"Başparmak ile parmak uçlarına dokunma", ue:true },
];

const KGIA_TYPES = [
  {
    key:"gorsel", en:"Visual", tr:"Görsel",
    qEN:"How clearly do you see this movement in your mind?", qTR:"Bu hareketi zihninizde ne kadar net görüyorsunuz?",
    labels:[
      { val:1, en:"No image at all", tr:"Hiç görüntü yok" },
      { val:2, en:"Blurry & incomplete", tr:"Bulanık ve eksik" },
      { val:3, en:"Moderately clear", tr:"Orta düzeyde net" },
      { val:4, en:"Clear image", tr:"Net görüntü" },
      { val:5, en:"As clear as seeing", tr:"Gerçek gibi net" },
    ]
  },
  {
    key:"kinestetik", en:"Kinesthetic", tr:"Kinestetik",
    qEN:"How strongly do you feel as if you are performing this movement?", qTR:"Bu hareketi yapıyormuş gibi ne kadar hissediyorsunuz?",
    labels:[
      { val:1, en:"No sensation", tr:"Hiç his yok" },
      { val:2, en:"Vague sensation", tr:"Belirsiz his" },
      { val:3, en:"Moderate sensation", tr:"Orta düzeyde his" },
      { val:4, en:"Strong sensation", tr:"Güçlü his" },
      { val:5, en:"As intense as doing", tr:"Gerçek gibi yoğun" },
    ]
  },
];

const WMFT_ITEMS = [
  // WMFT-4: 4-item short form (Kim et al., 2026) ? R=0.98 with full WMFT
  { id:1, en:"Hand to Table (front)", tr:"Eli masaya koyma (ön)" },
  { id:2, en:"Hand to Box (front)", tr:"Eli kutuya koyma (ön)" },
  { id:3, en:"Extend Elbow (no weight)", tr:"Dirsek uzatma (ağırlıksız)" },
  { id:4, en:"Lift Can (front)", tr:"Kutu kaldırma (ön)" },
];

/** Standard BBT administration time (Mathiowetz et al., 1985). */
const BBT_TEST_SECONDS = 60;

const COMORBIDITIES = [
  { value:"hypertension", label:"Hypertension" },
  { value:"hypotension", label:"Hypotension" },
  { value:"diabetes", label:"Diabetes" },
  { value:"cardiovascular", label:"Cardiovascular" },
  { value:"copd", label:"COPD" },
  { value:"arthritis", label:"Arthritis" },
  { value:"osteoporosis", label:"Osteoporosis" },
  { value:"depression", label:"Depression" },
  { value:"other", label:"Other" },
];

const VAS_FACES = [
  { val:0, emoji:"😀", en:"No hurt", tr:"Acı yok" },
  { val:2, emoji:"🙂", en:"Hurts little bit", tr:"Biraz acıyor" },
  { val:4, emoji:"😐", en:"Hurts little more", tr:"Biraz daha acıyor" },
  { val:6, emoji:"🙁", en:"Hurts even more", tr:"Daha çok acıyor" },
  { val:8, emoji:"😣", en:"Hurts whole lot", tr:"Çok acıyor" },
  { val:10, emoji:"😫", en:"Hurts worst", tr:"En kötü acı" },
];

const VAMS_FACES = [
  { val:0, emoji:"😐", en:"Neutral", tr:"Nötr" },
  { val:2, emoji:"🙂", en:"A little", tr:"Biraz" },
  { val:4, emoji:"😊", en:"Somewhat", tr:"Oldukça" },
  { val:6, emoji:"😄", en:"Moderately", tr:"Orta" },
  { val:8, emoji:"😁", en:"Very", tr:"Çok" },
  { val:10, emoji:"🤩", en:"Extremely", tr:"Aşırı" },
];

const NAV_ITEMS = [
  { id:"demographics", icon:User, en:"Demographics", tr:"Demografik Bilgiler" },
  { id:"ipaq", icon:Activity, en:"Physical Activity", tr:"Fiziksel Aktivite (IPAQ)" },
  { id:"vas", icon:Sliders, en:"Pain Scale (VAS)", tr:"Ağrı Skalası" },
  { id:"vams", icon:Heart, en:"Mood (VAMS-4)", tr:"Ruh Hali (VAMS-4)" },
  { id:"motorchange", icon:TrendingUp, en:"Muscle Control Scale", tr:"Kas Kontrol Ölçeği" },

  { id:"kgia", icon:Brain, en:"Imagery Questionnaire", tr:"Motor İmgeleme (KVIQ)" },
  { id:"wmft", icon:Timer, en:"Wolf Motor Function", tr:"Motor Fonksiyon (WMFT)" },
  { id:"kinematics", icon:Cpu, en:"Kinematics AI Lab", tr:"Kinematik AI Laboratuvarı" },
  { id:"report", icon:FileText, en:"Export Report", tr:"Rapor Dışa Aktarma" },
  { id:"analysis", icon:BarChart3, en:"Analysis Dashboard", tr:"Analiz Paneli", topBarOnly:true },
  { id:"users", icon:Users, en:"Users", tr:"Kullanıcılar", adminOnly:true, topBarOnly:true },
];

const ACTIVE_SECTION_LS_KEY = "neurolab_active_section";
const ACTIVE_SECTION_IDS = new Set([...NAV_ITEMS.map((n) => n.id), "database"]);

function loadStoredActiveSection() {
  try {
    const id = localStorage.getItem(ACTIVE_SECTION_LS_KEY);
    if (id && ACTIVE_SECTION_IDS.has(id)) return id;
  } catch {}
  return "demographics";
}

const LS_KEY = "stroke_rehab_patients_v6";

function loadPatients() {
  try {
    const raw = JSON.parse(localStorage.getItem(LS_KEY) || "[]");
    return Array.isArray(raw) ? dedupePatientList(raw) : [];
  } catch {
    return [];
  }
}
function savePatients(list) {
  const cleaned = dedupePatientList(Array.isArray(list) ? list : []);
  localStorage.setItem(LS_KEY, JSON.stringify(cleaned));
  return cleaned;
}

function isArchivedPatient(p) {
  return !!(p && p._archived);
}
function activePatients(list) {
  return (list || loadPatients()).filter((p) => !isArchivedPatient(p));
}
function studyIdNumber(p) {
  const n = parseInt(p?.demographics?.participantId, 10);
  return Number.isFinite(n) ? n : 1e9;
}
function reorderStudyIds(list, start = 101) {
  const src = Array.isArray(list) ? list : [];
  const active = src.filter((p) => p && typeof p === "object" && !isArchivedPatient(p));
  const archived = src.filter((p) => p && typeof p === "object" && isArchivedPatient(p));
  active.sort((a, b) => {
    const ia = studyIdNumber(a);
    const ib = studyIdNumber(b);
    if (ia !== ib) return ia - ib;
    return String(a._savedAt || "").localeCompare(String(b._savedAt || ""));
  });
  const renumbered = active.map((p, i) => ({
    ...p,
    demographics: { ...(p.demographics || {}), participantId: String(start + i) },
  }));
  return [...renumbered, ...archived];
}


/** Drop heavy kinematic arrays before server sync (keep summary metrics). */
function stripKinPhaseForSync(phase) {
  if (!phase || typeof phase !== "object") return phase;
  const { velocity_profile, phases, movement_profile, intermediate_files, ...rest } = phase;
  let mp = movement_profile;
  if (mp && typeof mp === "object") {
    const {
      elbow_angle_series,
      shoulder_flexion_series,
      trunk_x_series,
      hand_speed_series,
      ...mpLight
    } = mp;
    mp = mpLight;
  }
  return { ...rest, ...(mp ? { movement_profile: mp } : {}) };
}
function stripKinResultsForSync(kin) {
  if (!kin || typeof kin !== "object") return kin;
  return Object.fromEntries(
    Object.entries(kin).map(([k, v]) => [k, stripKinPhaseForSync(v)])
  );
}
const stripKinResultsForStorage = stripKinResultsForSync;
/** Prefer the validation-video panel snapshot whenever overlay frames exist. */
function resolveOverlayMetrics(overlay) {
  if (!overlay) return null;
  const server = overlay.metrics;
  if (overlay.frames?.length) {
    try {
      const computed = computeOverlayMetrics(overlay);
      if (computed) return { ...(server || {}), ...computed };
    } catch (e) {
      console.warn("computeOverlayMetrics failed:", e);
    }
  }
  return server || null;
}
function patientsForServerSync(list) {
  return list.map((p) => {
    if (!p?.kinematics?.analysisResults) return p;
    return {
      ...p,
      kinematics: {
        ...p.kinematics,
        analysisResults: stripKinResultsForSync(p.kinematics.analysisResults),
      },
    };
  });
}
async function postPatientsSync(patients) {
  return fetch("/api/patients", {
    method: "POST",
    credentials: "same-origin",
    headers: authHeaders(),
    body: JSON.stringify({ patients: patientsForServerSync(patients) }),
  });
}

async function backupToDrive(patients) {
  try {
    const r = await fetch("/auth/backup", {
      method: "POST",
      credentials: "same-origin",
      headers: authHeaders(),
      body: JSON.stringify({ patients: patientsForServerSync(patients) }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `HTTP ${r.status}`;
      console.warn("Drive backup failed:", detail);
      return { ok: false, detail };
    }
    return { ok: true, ...data };
  } catch (e) {
    console.warn("Drive backup failed:", e);
    return { ok: false, detail: String(e?.message || e) };
  }
}

/** Slim patient rows for Drive rebuild (keys + program sections; drop heavy kin series). */
function patientsForDriveRebuild(list) {
  return (Array.isArray(list) ? list : []).map((p) => {
    if (!p || typeof p !== "object") return p;
    const row = {
      _id: p._id,
      _archived: p._archived,
      _savedAt: p._savedAt,
      _hasPre: p._hasPre,
      _hasPost: p._hasPost,
      demographics: p.demographics || {},
    };
    for (const key of ["ipaq", "vas", "vams", "motorchange", "kgia", "wmft"]) {
      if (p[key] != null) row[key] = p[key];
    }
    if (p.kinematics && typeof p.kinematics === "object") {
      row.kinematics = {
        ...p.kinematics,
        analysisResults: p.kinematics.analysisResults
          ? stripKinResultsForSync(p.kinematics.analysisResults)
          : p.kinematics.analysisResults,
      };
    }
    return row;
  });
}

function driveRebuildErrorText(payload) {
  if (!payload || typeof payload !== "object") return "unknown error";
  const detail = payload.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  if (payload.error) return String(payload.error);
  if (payload.reason === "drive_unset") {
    return "Drive not connected - open Connect Drive, then retry Rebuild";
  }
  if (payload.reason === "drive_init_failed") {
    return "Drive OAuth token invalid - reconnect Drive, then retry Rebuild";
  }
  if (payload.reason) return String(payload.reason);
  return "unknown error";
}

/** Authoritative Drive rebuild: one folder per canonical patient; merge alias folders safely. */
async function rebuildDriveFromDatabase(patients, { showToast, waitMs = 180000 } = {}) {
  try {
    const oauth = await fetch("/auth/drive/oauth-status", {
      credentials: "same-origin",
      headers: authHeaders(),
    })
      .then((r) => r.json())
      .catch(() => ({}));
    if (oauth?.clientConfigured && (!oauth.ready || oauth.staleTokenHint || oauth.needsReconnect)) {
      // Soft warn only - server probe is authoritative; stale env token may still work.
      if (!oauth.ready) {
        showToast?.(
          "Drive not connected - open Connect Drive, sign in with clinic Gmail, then retry Rebuild",
          "error"
        );
        return { ok: false, detail: "drive_not_connected" };
      }
    }

    const start = await fetch("/auth/drive/reconcile", {
      method: "POST",
      credentials: "same-origin",
      headers: authHeaders(),
      body: JSON.stringify({ patients: patientsForDriveRebuild(patients) }),
    });
    const startData = await start.json().catch(() => ({}));
    if (!start.ok) {
      const detail = driveRebuildErrorText(startData) || `HTTP ${start.status}`;
      showToast?.(`Drive rebuild failed — ${detail}`, "error");
      return { ok: false, detail };
    }
    const jobId = startData.jobId || null;
    showToast?.("Rebuilding Drive folders from database…", "info");
    const deadline = Date.now() + Math.max(15000, waitMs);
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 2500));
      const st = await fetch("/auth/drive/reconcile-status", {
        credentials: "same-origin",
        headers: authHeaders(),
      });
      if (!st.ok) {
        // Auth blip ? keep polling until deadline.
        continue;
      }
      const status = await st.json().catch(() => ({}));
      if (jobId && status.jobId && status.jobId !== jobId) {
        continue;
      }
      if (!status.running && status.started) {
        const result = status.result || {};
        if (status.error || result.ok === false) {
          const err = driveRebuildErrorText({ ...result, error: status.error || result.error });
          showToast?.(`Drive rebuild error — ${err}`, "warning");
          return { ok: false, ...status };
        }
        const before = result.beforeCount ?? NA;
        const after = result.afterCount ?? NA;
        const trashed = Array.isArray(result.trashedAliases) ? result.trashedAliases.length : 0;
        const merged = Array.isArray(result.mergedAliases) ? result.mergedAliases.length : 0;
        showToast?.(
          `Drive rebuilt — folders ${before}→${after}, merged ${merged}, trashed aliases ${trashed}`,
          "success"
        );
        // Refresh per-task Excel under RAED_AI_Backups/Excel/ (active patients only).
        syncTaskExcelsToDrive(patients).then((ex) => {
          if (ex?.count) {
            showToast?.(
              `Excel synced — ${ex.uploaded}/${ex.count} task file(s) on Drive/Excel`,
              "success"
            );
          }
        }).catch(() => {});
        return { ok: true, ...result, status };
      }
    }
    showToast?.("Drive rebuild still running in background — check Drive in a few minutes", "info");
    return { ok: true, running: true, ...startData };
  } catch (e) {
    console.warn("Drive reconcile failed:", e);
    showToast?.(`Drive rebuild failed — ${e?.message || e}`, "error");
    return { ok: false, detail: String(e?.message || e) };
  }
}

const DRIVE_FILE_MAX_BYTES = 32 * 1024 * 1024;

const driveFileBackupDone = new Set();
const driveFileBackupQueue = [];
let driveFileBackupRunning = false;

function driveBackupDedupeKey(name, opts = {}) {
  return `${opts.patientKey || "_"}|${opts.subfolder || "_"}|${name}`;
}

function pumpDriveFileBackupQueue() {
  if (driveFileBackupRunning) return;
  driveFileBackupRunning = true;
  const run = async () => {
    while (driveFileBackupQueue.length) {
      if (isKinAnalyzeActive()) {
        await new Promise((r) => setTimeout(r, 2500));
        continue;
      }
      const job = driveFileBackupQueue.shift();
      try {
        await backupFileToDrive(job.name, job.blob, job.opts);
      } catch {
        driveFileBackupDone.delete(job.key);
      }
      await new Promise((r) => setTimeout(r, 400));
    }
    driveFileBackupRunning = false;
  };
  if (typeof requestIdleCallback === "function") {
    requestIdleCallback(() => { run(); }, { timeout: 8000 });
  } else {
    setTimeout(run, 50);
  }
}

function scheduleDriveFileBackup(name, blob, opts = {}) {
  if (!blob || !(blob instanceof Blob)) return;
  if (blob.size > DRIVE_FILE_MAX_BYTES) {
    console.warn("Drive backup skipped (file too large):", name, blob.size);
    return;
  }
  const key = driveBackupDedupeKey(name, opts);
  if (opts.force) driveFileBackupDone.delete(key);
  if (driveFileBackupDone.has(key)) return;
  driveFileBackupDone.add(key);
  driveFileBackupQueue.push({ name, blob, opts, key });
  pumpDriveFileBackupQueue();
}

function patientDriveKeyFromDemographics(demographics, fallbackId) {
  const d = demographics || {};
  const id = String(d.participantId || fallbackId || "").trim();
  const name = String(d.name || d.fullName || "").trim();
  if (!id && !name) return "";
  const slug = (s) => String(s).replace(/[^\w.\-]/g, "_").slice(0, 100);
  if (id && name) return slug(`${id}_${name}`);
  return slug(id || name);
}

function patientDriveKeyFromRecord(p) {
  return patientDriveKeyFromDemographics(p?.demographics, p?._id);
}

async function backupPatientVideoToDrive(demographics, phase, blobOrFile, filename) {
  const patientKey = patientDriveKeyFromDemographics(demographics);
  if (!patientKey || !blobOrFile) return false;
  const blob = blobOrFile instanceof Blob ? blobOrFile : blobOrFile;
  const base = filename || `${phase}_video`;
  const safeName = String(base).replace(/[^\w.\-]/g, "_").slice(0, 160);
  const driveName = canonicalDriveName(safeName, patientKey) || canonicalDriveName(`${phase}_validation_original.mp4`, patientKey) || safeName;
  scheduleDriveFileBackup(driveName, blob, { patientKey, subfolder: "videos", force: true });
  return true;
}

function backupSessionKinematicsVideosToDrive(kinematicsData, demographics) {
  if (!kinematicsData || typeof kinematicsData !== "object") return;
  ["pre", "post", "baseline"].forEach((phase) => {
    const file = kinematicsData[`video_${phase}_file`];
    if (!(file instanceof Blob)) return;
    const name = kinematicsData[`video_${phase}`] || file.name || `${phase}_original.mp4`;
    backupPatientVideoToDrive(demographics, phase, file, name);
  });
}

async function backupFileToDrive(name, blob, opts = {}) {
  try {
    const contentBase64 = await blobToBase64(blob);
    const { patientKey, subfolder, scope } = opts;
    const r = await fetch("/auth/backup-file", {
      method: "POST",
      credentials: "same-origin",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        contentBase64,
        mimeType: blob.type || "application/octet-stream",
        patientKey: patientKey || undefined,
        subfolder: subfolder || undefined,
        scope: scope || undefined,
      }),
    });
    return r.ok;
  } catch (e) {
    console.warn("Drive file backup failed:", e);
    return false;
  }
}

/** Upload one Excel workbook per clinical task to RAED_AI_Backups/Excel/. */
async function syncTaskExcelsToDrive(patients, { showToast, downloadLocal = false } = {}) {
  const files = buildAllTaskExcelFiles(patients);
  if (!files.length) {
    if (downloadLocal) showToast?.("No active task data for Excel export", "error");
    return { ok: false, count: 0 };
  }
  let uploaded = 0;
  for (let i = 0; i < files.length; i += 1) {
    const f = files[i];
    if (downloadLocal) {
      setTimeout(() => downloadBlobUtil(f.blob, f.fileName), i * 350);
    }
    const ok = await backupFileToDrive(f.fileName, f.blob, {
      subfolder: "excel",
      scope: "clinic_excel",
    });
    if (ok) uploaded += 1;
  }
  return { ok: uploaded > 0, count: files.length, uploaded, files };
}

async function restoreFromDrive() {
  try {
    // Folder/PDF/Excel rebuild can take a while on a cold Space.
    const r = await fetchWithTimeout("/auth/restore", {}, 240000);
    if (!r.ok) return [];
    const data = await r.json();
    const pts = Array.isArray(data.patients) ? data.patients : [];
    // Stash restore diagnostics for the explicit Restore button toast.
    try {
      window.__nlLastDriveRestoreMeta = {
        source: data.source || "",
        folderCount: data.folderCount,
        pdfParsed: data.pdfParsed,
        jsonSnapshots: data.jsonSnapshots,
        excelPatients: data.excelPatients,
        count: pts.length,
      };
    } catch {}
    return pts;
  } catch {
    return [];
  }
}

function startDriveSessionRecall(patients, { showToast, force = false } = {}) {
  const list = Array.isArray(patients) && patients.length ? patients : loadPatients();
  if (!list.length) return Promise.resolve(null);
  return recallAnalyzedSessionsFromDrive(list, {
    force,
    onDone: (summary) => {
      const msg = formatRecallToast(summary);
      if (msg) showToast?.(msg, summary.incomplete ? "warning" : "success");
    },
  }).catch((err) => {
    console.warn("Drive session recall failed:", err);
    return null;
  });
}

const PATIENTS_SYNC_EVENT = "neurolab-patients-synced";
const SYNC_FETCH_MS = 90000;

async function fetchWithTimeout(url, options = {}, ms = SYNC_FETCH_MS) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, {
      credentials: "same-origin",
      signal: ctrl.signal,
      ...options,
      headers: { ...authHeaders(), ...(options.headers || {}) },
    });
  } finally {
    clearTimeout(timer);
  }
}

/** Canonical in-app identity: Study ID. _id alone caused duplicate rows for the same person. */
function patientStudyId(p) {
  const raw = p?.demographics?.participantId;
  if (raw == null || raw === "") return "";
  const n = parseInt(String(raw).trim(), 10);
  if (Number.isFinite(n) && String(n) === String(raw).trim()) return String(n);
  return String(raw).trim();
}

function patientMergeKey(p) {
  return patientStudyId(p) || String(p?._id || "").trim();
}

/** Normalize display name for soft duplicate detection (not a hard identity key). */
function normalizePatientName(name) {
  return String(name || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function patientDisplayName(p) {
  const d = p?.demographics || {};
  return String(d.name || d.fullName || "").trim();
}

function findActiveByNormalizedName(list, name, { excludeStudyId = "" } = {}) {
  const needle = normalizePatientName(name);
  if (!needle) return [];
  const ex = String(excludeStudyId || "").trim();
  return (list || []).filter((p) => {
    if (!p || isArchivedPatient(p)) return false;
    if (normalizePatientName(patientDisplayName(p)) !== needle) return false;
    if (ex && patientStudyId(p) === ex) return false;
    return true;
  });
}

/** Prefer clinic 101+ Study IDs, then richer/newer record. */
function preferNameMergeTarget(a, b) {
  if (!a) return b;
  if (!b) return a;
  const ia = studyIdNumber(a);
  const ib = studyIdNumber(b);
  const a101 = Number.isFinite(ia) && ia >= 101 && ia < 1e8;
  const b101 = Number.isFinite(ib) && ib >= 101 && ib < 1e8;
  if (a101 !== b101) return a101 ? a : b;
  if (a101 && b101 && ia !== ib) return ia <= ib ? a : b;
  return patientRecordScore(a) >= patientRecordScore(b) ? a : b;
}

/** Collapse same-name active rows into one Study ID (keeps preferred ID + richer sections). */
function mergeSameNameDuplicates(list) {
  const src = Array.isArray(list) ? list : [];
  const archived = src.filter((p) => p && isArchivedPatient(p));
  const active = src.filter((p) => p && !isArchivedPatient(p));
  const groups = new Map();
  const noName = [];
  for (const p of active) {
    const key = normalizePatientName(patientDisplayName(p));
    if (!key) {
      noName.push(p);
      continue;
    }
    const arr = groups.get(key) || [];
    arr.push(p);
    groups.set(key, arr);
  }
  const out = [...noName];
  for (const group of groups.values()) {
    if (group.length === 1) {
      out.push(group[0]);
      continue;
    }
    let keep = group[0];
    for (let i = 1; i < group.length; i++) keep = preferNameMergeTarget(keep, group[i]);
    let merged = keep;
    for (const other of group) {
      if (other === keep) continue;
      merged = mergeTwoPatientRecords(merged, other);
    }
    const keepSid = patientStudyId(keep);
    merged = {
      ...merged,
      _id: keep._id || merged._id,
      demographics: {
        ...(merged.demographics || {}),
        ...(keepSid ? { participantId: keepSid } : {}),
        ...(patientDisplayName(keep) ? { name: patientDisplayName(keep) } : {}),
      },
    };
    out.push(merged);
  }
  return [...out, ...archived];
}

function nameDuplicateGroups(list) {
  const groups = new Map();
  for (const p of list || []) {
    if (!p || isArchivedPatient(p)) continue;
    const key = normalizePatientName(patientDisplayName(p));
    if (!key) continue;
    const arr = groups.get(key) || [];
    arr.push(p);
    groups.set(key, arr);
  }
  return Array.from(groups.entries())
    .filter(([, arr]) => arr.length > 1)
    .map(([key, arr]) => ({
      key,
      name: patientDisplayName(arr[0]) || key,
      ids: arr.map((p) => patientStudyId(p) || NA).sort((a, b) => Number(a) - Number(b) || String(a).localeCompare(String(b))),
      count: arr.length,
    }));
}

function readNlVersion() {
  try {
    return document.querySelector('meta[name="nl-version"]')?.content || "";
  } catch {
    return "";
  }
}

const PATIENT_MERGE_SECTIONS = [
  "demographics",
  "ipaq",
  "vas",
  "vams",
  "motorchange",
  "kgia",
  "wmft",
  "bbt",
  "kinematics",
];

function sectionFilled(obj) {
  return !!(obj && typeof obj === "object" && Object.keys(obj).length > 0);
}

function patientRecordScore(p) {
  if (!p || typeof p !== "object") return 0;
  const ts = Date.parse(p._savedAt || 0) || 0;
  let filled = 0;
  for (const key of PATIENT_MERGE_SECTIONS) {
    if (sectionFilled(p[key])) filled += 1;
  }
  if (p._hasPre) filled += 0.25;
  if (p._hasPost) filled += 0.25;
  return filled * 1e13 + ts;
}

function mergeTwoPatientRecords(a, b) {
  if (!a) return b;
  if (!b) return a;
  const keep = patientRecordScore(a) >= patientRecordScore(b) ? a : b;
  const other = keep === a ? b : a;
  const out = { ...other, ...keep };
  out.demographics = { ...(other.demographics || {}), ...(keep.demographics || {}) };
  for (const key of PATIENT_MERGE_SECTIONS) {
    if (key === "demographics") continue;
    if (key === "kinematics") {
      out.kinematics = mergeKinematicsSections(keep.kinematics, other.kinematics);
      continue;
    }
    const kSec = keep[key];
    const oSec = other[key];
    if (sectionFilled(kSec)) out[key] = kSec;
    else if (sectionFilled(oSec)) out[key] = oSec;
  }
  out._id = keep._id || other._id;
  const keepTs = Date.parse(keep._savedAt || 0) || 0;
  const otherTs = Date.parse(other._savedAt || 0) || 0;
  if (keepTs || otherTs) {
    out._savedAt = keepTs >= otherTs ? keep._savedAt : other._savedAt;
  } else {
    out._savedAt = keep._savedAt || other._savedAt || new Date().toISOString();
  }
  out._hasPre = !!(keep._hasPre || other._hasPre || patientHasPhaseData(out, "pre"));
  out._hasPost = !!(keep._hasPost || other._hasPost || patientHasPhaseData(out, "post"));
  if (keep._driveArtifacts || other._driveArtifacts) {
    out._driveArtifacts = { ...(other._driveArtifacts || {}), ...(keep._driveArtifacts || {}) };
  }
  if (keep._archived || other._archived) out._archived = !!(keep._archived && other._archived);
  return out;
}

function mergeKinematicsSections(a, b) {
  const ka = a && typeof a === "object" ? a : {};
  const kb = b && typeof b === "object" ? b : {};
  const out = { ...kb, ...ka };
  const arA = ka.analysisResults && typeof ka.analysisResults === "object" ? ka.analysisResults : {};
  const arB = kb.analysisResults && typeof kb.analysisResults === "object" ? kb.analysisResults : {};
  const phases = new Set([...Object.keys(arA), ...Object.keys(arB)]);
  if (phases.size) {
    const merged = {};
    for (const phase of phases) {
      const pa = arA[phase] && typeof arA[phase] === "object" ? arA[phase] : {};
      const pb = arB[phase] && typeof arB[phase] === "object" ? arB[phase] : {};
      merged[phase] = Object.keys(pa).length >= Object.keys(pb).length ? { ...pb, ...pa } : { ...pa, ...pb };
    }
    out.analysisResults = merged;
  }
  return out;
}

function patientHasPhaseData(p, phase) {
  if (!p) return false;
  if (phase === "pre") {
    if (p._hasPre) return true;
    if (p.vas?.rest?.pre || p.motorchange?.control || p.vams?.happy?.pre) return true;
  }
  if (phase === "post") {
    if (p._hasPost) return true;
    if (p.vas?.rest?.post || p.motorchange?.difference || p.vams?.happy?.post) return true;
  }
  try {
    return !!getPatientKinPhase(p, phase);
  } catch {
    const kin = p.kinematics || {};
    return !!(kin.analysisResults?.[phase] || kin[`result_${phase}`]);
  }
}

function formatPatientSavedAt(raw) {
  const ts = Date.parse(raw || "");
  if (!Number.isFinite(ts) || ts <= 0) return NA;
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return NA;
  }
}

function mergePatientLists(...lists) {
  const byId = new Map();
  for (const list of lists) {
    if (!Array.isArray(list)) continue;
    for (const p of list) {
      if (!p || typeof p !== "object") continue;
      const id = patientMergeKey(p);
      if (!id) continue;
      const existing = byId.get(id);
      byId.set(id, existing ? mergeTwoPatientRecords(existing, p) : p);
    }
  }
  return Array.from(byId.values());
}

function dedupePatientList(list) {
  return mergePatientLists(list);
}

let patientsSyncPromise = null;
let lastSilentDriveRestoreAt = 0;
const SILENT_DRIVE_RESTORE_MS = 10 * 60 * 1000;

/** Push local patients to server, pull merge, persist to localStorage. */
async function syncPatientsWithServer({ showToast, silent = false, skipDrive = false } = {}) {
  if (patientsSyncPromise) {
    return patientsSyncPromise;
  }
  patientsSyncPromise = syncPatientsWithServerInner({ showToast, silent, skipDrive }).finally(() => {
    patientsSyncPromise = null;
  });
  return patientsSyncPromise;
}

async function syncPatientsWithServerInner({ showToast, silent = false, skipDrive = false } = {}) {
  const localPts = loadPatients();
  if (isKinAnalyzeActive()) {
    console.log("Patient/Drive sync deferred — video analysis in progress");
    return { ok: false, patients: localPts, skipped: true, reason: "analyze" };
  }
  try {
    const now = Date.now();
    const localEmpty = !Array.isArray(localPts) || localPts.length === 0;
    // Silent boot skips Drive for speed ? EXCEPT when this origin has no patients
    // (Space rename / new Home Screen): then Drive folder+PDF restore is required.
    const skipDriveRestore =
      !localEmpty &&
      (skipDrive || silent || now - lastSilentDriveRestoreAt < SILENT_DRIVE_RESTORE_MS);
    const driveRestoreP = skipDriveRestore
      ? Promise.resolve([])
      : restoreFromDrive().then((pts) => {
          lastSilentDriveRestoreAt = Date.now();
          return pts;
        });
    const [drivePts, serverPullR] = await Promise.all([
      driveRestoreP,
      fetchWithTimeout("/api/patients", {}, silent && !localEmpty ? 20000 : SYNC_FETCH_MS),
    ]);
    const serverPull = serverPullR.ok ? await serverPullR.json() : [];
    const preMerged = mergePatientLists(serverPull, drivePts, localPts);

    // Never push an empty list over a non-empty server (rename race).
    if (preMerged.length === 0 && Array.isArray(serverPull) && serverPull.length > 0) {
      savePatients(serverPull);
      return { ok: true, patients: serverPull, pushed: false, preservedServer: true };
    }

    const push = await fetchWithTimeout(
      "/api/patients",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patients: patientsForServerSync(preMerged) }),
      },
      silent && !localEmpty ? 20000 : SYNC_FETCH_MS
    );
    if (!push.ok) {
      const detail = await push.text().catch(() => "");
      if (!silent) showToast?.(`Server save failed (${push.status})`, "error");
      console.warn("Patient push sync failed:", push.status, detail);
      if (preMerged.length > 0) {
        savePatients(preMerged);
        return { ok: true, patients: preMerged, pushed: false };
      }
      return { ok: false, patients: localPts, pushed: false };
    }

    const r = await fetchWithTimeout("/api/patients", {}, silent ? 20000 : SYNC_FETCH_MS);
    if (!r.ok) {
      if (!silent) showToast?.(`Could not load server records (${r.status})`, "error");
      return { ok: false, patients: localPts, pushed: true };
    }

    const serverPts = r.ok ? await r.json() : preMerged;
    const merged = mergePatientLists(serverPts, preMerged);
    savePatients(merged);
    window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count: merged.length } }));

    // Explicit Sync: await full JSON ? Drive + iPad localStorage snapshot before rebuild.
    // Silent boot/PTR stays snappy (no Drive wait).
    let driveBackupOk = false;
    if (!silent && !isKinAnalyzeActive()) {
      try {
        if (typeof window.__nlForceIpadPatientsUpload === "function") {
          await window.__nlForceIpadPatientsUpload();
        }
      } catch (e) {
        console.warn("iPad localStorage upload skipped:", e);
      }
      const backupR = await backupToDrive(merged);
      driveBackupOk = !!backupR?.ok;
      if (backupR?.ok) {
        console.log("Drive backup OK", backupR?.fileName || "");
      } else {
        console.warn("Drive backup skipped or failed", backupR?.detail);
        if (backupR?.detail) {
          showToast?.(`Drive backup failed — ${backupR.detail}`, "warning");
        }
      }
      // Rebuild folders after JSON snapshot is on Drive (non-blocking).
      setTimeout(() => {
        if (isKinAnalyzeActive()) return;
        rebuildDriveFromDatabase(merged, { showToast, waitMs: 120000 }).catch(() => {});
      }, 500);
    }

    if (!silent) {
      if (merged.length === 0) {
        showToast?.("Sync OK — no records yet. Save a session first.", "info");
      } else if (driveBackupOk) {
        showToast?.(
          `Synced — ${merged.length} record(s) — neurolab_patients JSON on Drive`,
          "success"
        );
      } else {
        showToast?.(
          `Synced — ${merged.length} record(s) on server — Connect Drive then Sync again`,
          "success"
        );
      }
    }
    return { ok: true, patients: merged, pushed: true, driveBackupOk };
  } catch (err) {
    const timedOut = err?.name === "AbortError";
    if (!silent) {
      showToast?.(
        timedOut
          ? "Sync timed out — server may be waking up. Wait ~1 min and retry."
          : "Sync failed — data kept on this device only",
        "error"
      );
    }
    console.warn("Patient sync error:", err);
    return { ok: false, patients: localPts, pushed: false, timedOut };
  }
}

const RAED_ORIGIN_RESTORE_DONE_KEY = "raed_origin_restore_v1";
const RAED_ORIGIN_RESTORE_PENDING_KEY = "raed_origin_restore_pending";

/** Pull Home Screen / iPad localStorage backup into this origin (merge, never wipe). */
async function applyIpadLocalStorageBackup() {
  try {
    const r = await fetchWithTimeout("/api/ipad-localstorage", {}, 45000);
    if (!r.ok) return { ok: false, applied: false, patients: loadPatients() };
    const data = await r.json().catch(() => ({}));
    const storage = data?.storage && typeof data.storage === "object" ? data.storage : {};
    let applied = false;

    const parseMaybeJson = (raw) => {
      if (raw == null || raw === "") return null;
      if (typeof raw === "object") return raw;
      try {
        return JSON.parse(raw);
      } catch {
        return null;
      }
    };

    const remotePatients = parseMaybeJson(storage.stroke_rehab_patients_v6);
    if (Array.isArray(remotePatients) && remotePatients.length > 0) {
      const merged = mergePatientLists(loadPatients(), remotePatients);
      savePatients(merged);
      applied = true;
    }

    const localKin = (() => {
      try {
        const v = localStorage.getItem("neuro_kin_results");
        return v && v !== "{}" && v !== "null";
      } catch {
        return true;
      }
    })();
    if (!localKin && storage.neuro_kin_results) {
      try {
        localStorage.setItem("neuro_kin_results", String(storage.neuro_kin_results));
        applied = true;
      } catch {}
    }

    const localFd = (() => {
      try {
        const v = localStorage.getItem("neuro_fd_data");
        return v && v !== "{}" && v !== "null";
      } catch {
        return true;
      }
    })();
    if (!localFd && storage.neuro_fd_data) {
      try {
        localStorage.setItem("neuro_fd_data", String(storage.neuro_fd_data));
        applied = true;
      } catch {}
    }

    return { ok: true, applied, patients: loadPatients() };
  } catch (err) {
    console.warn("iPad localStorage restore failed:", err);
    return { ok: false, applied: false, patients: loadPatients() };
  }
}

/** One-time strong restore after Space rename / empty new-origin PWA. */
async function restoreStudyDataFromServer({ showToast } = {}) {
  await applyIpadLocalStorageBackup();
  // Prefer server + Drive merge; empty local must not wipe server records.
  const result = await syncPatientsWithServer({ showToast, silent: false, skipDrive: false });
  if (result?.patients?.length) {
    startDriveSessionRecall(result.patients, { force: true });
  }
  return result;
}

/** Explicit Database action: pull Drive folders/PDFs/Excel into app + server. */
async function restorePatientsFromDriveNow({ showToast } = {}) {
  try {
    showToast?.("Restoring from Drive JSON snapshot (not PDF)…", "info");
    const drivePts = await restoreFromDrive();
    if (!drivePts.length) {
      showToast?.(
        "Drive restore found no patient folders/PDFs. Open Connect Drive, then retry.",
        "warning"
      );
      return { ok: false, patients: loadPatients() };
    }
    // Prefer non-empty local kinematics/assessments over empty Drive shells.
    const merged = mergePatientLists(loadPatients(), drivePts).map((p) => {
      const next = { ...p };
      if (!Date.parse(next._savedAt || "")) next._savedAt = new Date().toISOString();
      next._hasPre = !!(next._hasPre || patientHasPhaseData(next, "pre"));
      next._hasPost = !!(next._hasPost || patientHasPhaseData(next, "post"));
      return next;
    });
    savePatients(merged);
    const push = await fetchWithTimeout(
      "/api/patients",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patients: patientsForServerSync(merged) }),
      },
      SYNC_FETCH_MS
    );
    const meta = window.__nlLastDriveRestoreMeta || {};
    const detailBits = [
      meta.pdfParsed != null ? `${meta.pdfParsed} PDF` : null,
      meta.excelPatients != null && meta.excelPatients > 0 ? `${meta.excelPatients} Excel` : null,
      meta.jsonSnapshots ? "JSON snapshot" : null,
    ].filter(Boolean);
    const detail = detailBits.length ? ` (${detailBits.join(", ")})` : "";
    if (!push.ok) {
      showToast?.(`Restored ${merged.length} on device${detail} — server save failed (${push.status})`, "warning");
      window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count: merged.length } }));
      return { ok: true, patients: merged, pushed: false };
    }
    showToast?.(`Restored ${merged.length} patient(s) from Drive${detail}`, "success");
    window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count: merged.length } }));
    startDriveSessionRecall(merged, { showToast, force: true });
    return { ok: true, patients: merged, pushed: true };
  } catch (err) {
    console.warn("Restore from Drive failed:", err);
    showToast?.("Drive restore failed — check Connect Drive / Space awake", "error");
    return { ok: false, patients: loadPatients() };
  }
}

// ??? Shared UI ????????????????????????????????????????????????????????????????

const Glass = ({ children, className = "", style = {}, soft = false, ...r }) => (
  <div
    className={`glass-float content-panel-glass rounded-2xl ${GLASS_PANEL_CLS} ${className}`}
    style={{ overflow: "visible", boxShadow: soft ? FLOAT_M : FLOAT_M, ...style }}
    {...r}
  >
    {children}
  </div>
);

const BL = ({ en, tr, className = "" }) => (
  <div className={className}>
    <span className="block font-extrabold text-white leading-snug">{en}</span>
  </div>
);

const SH = ({ icon: Icon, en, tr, badge }) => (
  <div className="flex flex-col sm:flex-row sm:items-center gap-2.5 sm:gap-3 mb-5 sm:mb-6 rounded-2xl p-4 glass-float section-header">
    <div className="flex items-start sm:items-center gap-3 min-w-0 flex-1">
      <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl flex items-center justify-center flex-shrink-0" style={GLASS_FIELD}>
      <Icon className="w-5 h-5 text-white/80" />
    </div>
    <div className="min-w-0 flex-1">
        <h2 className="text-base sm:text-xl font-extrabold text-white leading-snug">{en}</h2>
      </div>
    </div>
    {badge && (
      <span className="sm:ml-auto flex-shrink-0 self-start sm:self-center px-3 py-1 rounded-full text-xs font-semibold text-white/50" style={GLASS_FIELD}>
        {badge}
      </span>
    )}
  </div>
);

const GI = ({ en, tr, type = "text", value, onChange, placeholder = "", className = "", ...r }) => (
  <div className={`flex flex-col gap-1.5 ${className}`}>
    {en && <BL en={en} tr={tr} />}
    <input
      type={type}
      value={value ?? ""}
      onChange={onChange}
      placeholder={placeholder}
      className={`glass-field w-full px-3 py-2.5 rounded-xl text-white placeholder-white/30 text-sm font-light focus:outline-none transition-all ${INPUT_CLS}`}
      style={GLASS_FIELD}
      {...r}
    />
  </div>
);

const GSelect = ({ en, tr, value, onChange, options, className = "" }) => {
  const [open, setOpen] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState(null);
  const ref = useRef(null);
  const btnRef = useRef(null);
  const reduceMotion = useReducedMotion();

  useLayoutEffect(() => {
    if (!open) {
      setMenuAnchor(null);
      return undefined;
    }
    const btn = btnRef.current;
    if (!btn) return undefined;
    const sync = () => {
      const r = btn.getBoundingClientRect();
      setMenuAnchor({
        top: r.bottom + 4,
        left: r.left,
        width: r.width,
      });
    };
    sync();
    window.addEventListener("resize", sync);
    return () => window.removeEventListener("resize", sync);
  }, [open]);

  useEffect(() => {
    const h = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        // Also check if click is inside a portal dropdown
        const portals = document.querySelectorAll("[data-gselect-portal]");
        let inPortal = false;
        portals.forEach((el) => { if (el.contains(e.target)) inPortal = true; });
        if (!inPortal) setOpen(false);
      }
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  useEffect(() => {
    if (!open) return;
    const closeOnMove = () => setOpen(false);
    window.addEventListener("scroll", closeOnMove, true);
    window.addEventListener("resize", closeOnMove);
    return () => {
      window.removeEventListener("scroll", closeOnMove, true);
      window.removeEventListener("resize", closeOnMove);
    };
  }, [open]);

  const sel = options.find((o) => o.value === value);

  return (
    <div className={`flex flex-col gap-1.5 ${className}`} ref={ref}>
      {en && <BL en={en} tr={tr} />}
      <div style={{ position: "relative" }}>
        <button
          ref={btnRef}
          type="button"
          onClick={() => setOpen((p) => !p)}
          aria-expanded={open}
          className={`gselect-trigger-shell w-full px-3 py-2.5 rounded-xl text-white text-sm font-light text-left flex items-center justify-between gap-2 ${GLASS_TOPBAR_SHELL}`}
          style={{ ...GLASS_FIELD, boxShadow: "inset 0 1px 0 rgba(255,255,255,0.02), 0 4px 14px rgba(0,0,0,0.08)" }}
        >
          <span className={`truncate ${sel ? "text-white" : "text-white/30"}`}>
            {sel ? sel.label : "Select\u2026"}
          </span>
          <span className="text-white/40 flex-shrink-0 flex items-center justify-center w-4 h-4">
            <span className={`gselect-chevron flex items-center justify-center ${open ? "gselect-chevron-open" : ""}`}>
              <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
                <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </span>
        </button>

        {typeof document !== "undefined" && open && menuAnchor && ReactDOM.createPortal(
          <div
            data-gselect-portal="true"
            className={`gselect-menu-portal ${GLASS_TOPBAR_SHELL}`}
            style={{
              position: "fixed",
              top: menuAnchor.top,
              left: menuAnchor.left,
              width: menuAnchor.width,
              zIndex: 999999,
              borderRadius: GSELECT_MENU_BOX.borderRadius,
              boxShadow: FLOAT_M,
              transform: "translateZ(0)",
              WebkitTransform: "translateZ(0)",
              isolation: "isolate",
            }}
          >
            <div
              className={`gselect-menu-body relative z-[1] py-1 overflow-hidden${reduceMotion ? "" : " gselect-menu-body--animate"}`}
            >
              {options.map((o) => {
                const selected = value === o.value;
                const optStyle = {
                  backgroundColor: selected ? "rgba(255,255,255,0.08)" : "transparent",
                  color: selected ? "#ffffff" : "rgba(255,255,255,0.75)",
                  fontWeight: selected ? 700 : 400,
                  transition: "background-color 0.15s, color 0.15s",
                };
                return (
                    <button
                      key={o.value}
                      type="button"
                      onClick={() => { onChange({ target: { value: o.value } }); setOpen(false); }}
                      className="w-full text-left px-3 py-2.5 text-sm block gselect-option"
                      style={optStyle}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.10)";
                        e.currentTarget.style.color = "#ffffff";
                        e.currentTarget.style.fontWeight = "700";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = selected ? "rgba(255,255,255,0.08)" : "transparent";
                        e.currentTarget.style.color = selected ? "#ffffff" : "rgba(255,255,255,0.75)";
                        e.currentTarget.style.fontWeight = selected ? "700" : "400";
                      }}
                    >
                    {o.label}
                  </button>
                );
              })}
            </div>
          </div>,
          document.body
        )}
      </div>
    </div>
  );
};

const GBtn = ({ children, onClick, disabled, className = "", variant = "default" }) => {
  const v = {
    default: "bg-white/10 border-white/20 text-white hover:bg-white/15",
    sky: "bg-sky-500/20 border-sky-400/30 text-sky-200 hover:bg-sky-500/30",
    emerald: "bg-emerald-500/20 border-emerald-400/30 text-emerald-200 hover:bg-emerald-500/30",
    amber: "bg-amber-500/20 border-amber-400/30 text-amber-200 hover:bg-amber-500/30",
    violet: "bg-violet-500/20 border-violet-400/30 text-violet-200 hover:bg-violet-500/30",
    rose: "bg-rose-500/20 border-rose-400/30 text-rose-200 hover:bg-rose-500/30",
    danger: "bg-rose-500/20 border-rose-400/30 text-rose-200 hover:bg-rose-500/30",
  };

  return (
    <motion.button
      whileHover={nlMotionHover(1.02)}
      whileTap={nlMotionTap(0.97)}
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-md border font-semibold text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed ${v[variant]} ${className}`}
    >
      {children}
    </motion.button>
  );
};

function TopBarSessionCapsule({ onNew, onSave, dirty }) {
  return (
    <div
      className="flex items-stretch rounded-xl overflow-hidden border border-white/[0.06] bg-white/[0.04] backdrop-blur-sm flex-shrink-0"
      style={GLASS_FIELD}
      role="group"
      aria-label="Session actions"
    >
      <motion.button
        type="button"
        whileTap={nlMotionTap(0.98)}
        onClick={onNew}
        className="flex items-center justify-center gap-1.5 px-2.5 sm:px-3 py-1.5 min-h-[36px] min-w-[36px] text-teal-300/90 hover:bg-white/[0.06] active:bg-white/[0.08] transition-colors border-r border-white/[0.06]"
        title="New Session"
        aria-label="New Session"
      >
        <PlusCircle className="w-4 h-4 text-teal-300/85 flex-shrink-0" />
        <span className="hidden sm:inline text-xs font-semibold text-white/75">New</span>
      </motion.button>
      <motion.button
        type="button"
        whileTap={nlMotionTap(0.98)}
        onClick={onSave}
        className={`flex items-center justify-center gap-1.5 px-2.5 sm:px-3 py-1.5 min-h-[36px] min-w-[36px] transition-colors hover:bg-white/[0.06] active:bg-white/[0.08] ${
          dirty
            ? "text-sky-200/95 shadow-[inset_0_0_0_1px_rgba(56,189,248,0.32)]"
            : "text-white/70"
        }`}
        title={dirty ? "Save Session (unsaved changes)" : "Save Session"}
        aria-label="Save Session"
      >
        <Save className={`w-4 h-4 flex-shrink-0 ${dirty ? "text-sky-300/90" : "text-white/55"}`} />
        <span className={`hidden sm:inline text-xs font-semibold ${dirty ? "text-sky-100/90" : "text-white/75"}`}>
          Save
        </span>
      </motion.button>
    </div>
  );
}

const PullToRefresh = ({ scrollRef, spinnerAnchorRef, onRefresh, disabled = false }) => {
  const pullRef = useRef(0);
  const tracking = useRef(false);
  const refreshingRef = useRef(false);
  const startY = useRef(0);
  const startX = useRef(0);
  const pullIntent = useRef(false);
  const rafRef = useRef(0);
  const pendingYRef = useRef(0);
  const nodesRef = useRef({ inner: null, content: null });
  const enabled = isIOSDevice() || isStandalonePWA();

  const resolveNodes = useCallback((el) => {
    if (!el) return nodesRef.current;
    const inner = el.querySelector(".ptr-inner");
    if (!inner) return nodesRef.current;
    if (nodesRef.current.inner !== inner) {
      nodesRef.current = {
        inner,
        content: inner.querySelector(".ptr-pull-content"),
      };
    }
    return nodesRef.current;
  }, []);

  const paint = useCallback((el, y, state) => {
    pullRef.current = y;
    const { content } = resolveNodes(el);
    const ty = y > 0 || state === "refreshing" ? y : 0;

    if (content) {
      content.style.transform = ty ? `translate3d(0, ${ty}px, 0)` : "";
      content.style.transition = state === "idle"
        ? "transform 0.28s cubic-bezier(0.25, 0.46, 0.45, 0.94)"
        : "none";
      content.style.willChange = ty ? "transform" : "auto";
    }

    const spinner = spinnerAnchorRef?.current;
    const ios = spinner?.querySelector(".ptr-ios-spinner");
    if (!spinner || !ios) return;
    const show = y >= 4 || state === "refreshing";
    const fade = state === "refreshing" ? 1 : Math.min((y - 2) / 14, 1);
    spinner.style.opacity = show ? String(Math.max(fade, 0.2)) : "0";
    const spinSize = ios.offsetHeight || 22;
    const slotY = ty > 0 ? Math.max(0, ty * 0.5 - spinSize * 0.5) : 0;
    spinner.style.transform = slotY ? `translate3d(0, ${slotY}px, 0)` : "";

    if (state === "refreshing") {
      ios.classList.add("ptr-spinning");
      ios.style.setProperty("--ptr-scale", "1");
    } else if (y > 0) {
      const p = Math.min(y / PTR_THRESHOLD, 1);
      if (y >= 10) ios.classList.add("ptr-spinning");
      else ios.classList.remove("ptr-spinning");
      ios.style.setProperty("--ptr-scale", String(0.45 + p * 0.55));
    } else {
      ios.classList.remove("ptr-spinning");
      ios.style.setProperty("--ptr-scale", "0.45");
    }
  }, [resolveNodes, spinnerAnchorRef]);

  const schedulePaint = useCallback((el, y, state) => {
    pendingYRef.current = y;
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      paint(el, pendingYRef.current, state);
    });
  }, [paint]);

  useEffect(() => {
    if (!enabled) return;
    const el = scrollRef?.current;
    if (!el) return;
    resolveNodes(el);

    const onStart = (e) => {
      if (disabled || refreshingRef.current) return;
      if (el.scrollTop > 8) return;
      if (!e.touches?.length) return;
      startY.current = e.touches[0].clientY;
      startX.current = e.touches[0].clientX;
      pullIntent.current = false;
      tracking.current = true;
    };

    const onMove = (e) => {
      if (disabled || !tracking.current || refreshingRef.current) return;
      if (!e.touches?.length) return;
      const dy = e.touches[0].clientY - startY.current;
      const dx = e.touches[0].clientX - startX.current;

      if (el.scrollTop > 8) {
        tracking.current = false;
        schedulePaint(el, 0, "idle");
        return;
      }

      if (Math.abs(dx) > Math.abs(dy) + 6) {
        tracking.current = false;
        schedulePaint(el, 0, "idle");
        return;
      }

      if (dy > 0) {
        pullIntent.current = true;
        const y = Math.min(dy * 0.78, PTR_MAX_PULL);
        schedulePaint(el, y, "pulling");
        if (y > 18 && e.cancelable) e.preventDefault();
        return;
      }

      if (!pullIntent.current) {
        tracking.current = false;
      }
      schedulePaint(el, 0, "idle");
    };

    const finish = () => {
      pullIntent.current = false;
      if (!tracking.current) return;
      tracking.current = false;
      if (pullRef.current >= PTR_THRESHOLD && !refreshingRef.current) {
        refreshingRef.current = true;
        paint(el, 52, "refreshing");
        // Never leave the iPad spinner stuck on Drive/server cold-start.
        Promise.race([
          Promise.resolve(typeof onRefresh === "function" ? onRefresh() : undefined),
          new Promise((resolve) => setTimeout(resolve, 6000)),
        ])
          .catch(() => {})
          .finally(() => {
            refreshingRef.current = false;
            paint(el, 0, "idle");
          });
      } else {
        paint(el, 0, "idle");
      }
    };

    el.addEventListener("touchstart", onStart, { passive: true });
    el.addEventListener("touchmove", onMove, { passive: false });
    el.addEventListener("touchend", finish, { passive: true });
    el.addEventListener("touchcancel", finish, { passive: true });
    return () => {
      el.removeEventListener("touchstart", onStart);
      el.removeEventListener("touchmove", onMove);
      el.removeEventListener("touchend", finish);
      el.removeEventListener("touchcancel", finish);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = 0;
      nodesRef.current = { inner: null, content: null };
    };
  }, [enabled, scrollRef, paint, schedulePaint, resolveNodes, onRefresh, disabled, spinnerAnchorRef]);

  useEffect(() => {
    if (!disabled) return;
    const el = scrollRef?.current;
    if (!el) return;
    tracking.current = false;
    paint(el, 0, "idle");
  }, [disabled, scrollRef, paint]);

  return null;
};

/** Never pass DOM MediaError / Error objects into React text (React #31). */
function formatUserMessage(msg) {
  if (msg == null || msg === "") return "";
  if (typeof msg === "string") return msg;
  if (typeof msg === "number" || typeof msg === "boolean") return String(msg);
  if (msg instanceof Error) return msg.message || msg.name || "Error";
  if (typeof msg === "object") {
    const code = msg.code;
    if (code != null && typeof code === "number") {
      const labels = { 1: "aborted", 2: "network", 3: "decode", 4: "format not supported" };
      return `Video error (${labels[code] || code})`;
    }
    if (typeof msg.message === "string" && msg.message) return msg.message;
  }
  return "Something went wrong";
}

const Toast = ({ msg, visible, variant = "success" }) => (
  <AnimatePresence>
    {visible && (
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -8, scale: 0.98 }}
        transition={NL_SPRING_TOAST}
        className={`fixed bottom-8 right-8 z-[99999] flex items-center gap-2.5 px-5 py-3 rounded-2xl backdrop-blur-2xl border text-sm font-semibold shadow-2xl ${
          variant === "success"
            ? "bg-emerald-500/20 border-emerald-400/30 text-emerald-200"
            : variant === "info"
            ? "bg-sky-500/20 border-sky-400/30 text-sky-200"
            : "bg-rose-500/20 border-rose-400/30 text-rose-200"
        }`}
      >
        <Check className="w-4 h-4" /> {formatUserMessage(msg)}
      </motion.div>
    )}
  </AnimatePresence>
);

const calculateClinicalDelta = (pre, post, direction) => {
  if (pre === undefined || post === undefined || pre === "" || post === "")
    return { text: "\u2014", colorClass: "text-slate-500 bg-slate-500/10" };

  const preNum = parseFloat(String(pre));
  const postNum = parseFloat(String(post));
  if (isNaN(preNum) || isNaN(postNum))
    return { text: "\u2014", colorClass: "text-slate-500 bg-slate-500/10" };

  const delta = postNum - preNum;
  if (Math.abs(delta) < 0.0001)
    return { text: "0.0%", colorClass: "text-slate-400 bg-slate-400/10 border-slate-400/20" };

  const pct = preNum !== 0 ? Math.abs(delta / preNum) * 100 : 0;
  const sign = delta > 0 ? "+" : "-";
  const text = `${sign}${pct.toFixed(1)}%`;

  const lowerIsBetter = direction === "lower";
  const isImprovement = lowerIsBetter ? delta < 0 : delta > 0;

  return {
    text,
    colorClass: isImprovement
      ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
      : "text-rose-400 bg-rose-400/10 border-rose-400/20",
  };
};

const kinPrePostBadge = (pre, post, direction) => {
  const pct = calcImprovement(pre, post, direction);
  let text = formatKinPrePostPct(pct);
  let improved = pct != null && Number.isFinite(pct) ? pct > 0 : null;
  let stable = pct === 0;

  // Pre ? 0 ? show absolute ? instead of Infinity%
  if (text == null) {
    const preN = Number(pre);
    const postN = Number(post);
    if (!Number.isNaN(preN) && !Number.isNaN(postN) && Math.abs(preN) < 1e-12) {
      text = formatKinPrePostAbsDelta(pre, post);
      if (text) {
        if (direction === "higher") improved = postN > preN;
        else if (direction === "lower") improved = postN < preN;
        else improved = null;
        stable = Math.abs(postN - preN) < 1e-12;
      }
    }
  }
  if (!text) return null;

  if (direction === "none" && !stable) {
    return {
      text,
      colorClass: "text-white/70 bg-white/[0.06] border-white/[0.12]",
    };
  }

  return {
    text,
    colorClass: stable
      ? "text-white/60 bg-white/[0.06] border-white/[0.12]"
      : improved
        ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
        : improved === false
          ? "text-rose-400 bg-rose-400/10 border-rose-400/20"
          : "text-white/60 bg-white/[0.06] border-white/[0.12]",
  };
};

const kinNcBadge = (reason) => ({
  text: reason || "n/c",
  colorClass: "text-amber-200/80 bg-amber-400/10 border-amber-400/25",
  nc: true,
});

/** Resolve Pre?Post cell: % / ? / n/c reason / empty dash only when values missing. */
const resolveKinPrePostCell = (preVal, postVal, direction, metricKey, kinematicsResults, armForPhase) => {
  if (metricKey === "pause_stops_panel") {
    return kinNcBadge("n/c — compound row");
  }
  if (isMissing(preVal) || isMissing(postVal)) {
    return null; // true missing data
  }
  if (typeof preVal === "string" || typeof postVal === "string") {
    return kinNcBadge("n/c — non-numeric");
  }
  const status = kinCrossPhaseDeltaStatus(kinematicsResults, metricKey, armForPhase);
  if (!status.comparable) {
    return kinNcBadge(status.reason || "n/c");
  }
  return kinPrePostBadge(preVal, postVal, direction);
};

const kinPostHealthyBadge = (pre, post, healthy, direction) => {
  const pct = calcGap(post, healthy, direction);
  const text = formatKinPostHealthyPct(pct, direction);
  if (!text) return null;

  // Prefer a relative improvement check when Pre is available:
  // green if Post moved closer to Healthy compared with Pre,
  // amber if Post is within 5% of Healthy but not improving,
  // rose if Post moved away from Healthy.
  const preN = Number(pre);
  const postN = Number(post);
  const helN = Number(healthy);
  if (!Number.isNaN(preN) && !Number.isNaN(postN) && !Number.isNaN(helN)) {
    const preGap = Math.abs(preN - helN);
    const postGap = Math.abs(postN - helN);
    if (postGap < preGap) {
      return { text, colorClass: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20" };
    }
    if (postGap > preGap) {
      return { text, colorClass: "text-rose-400 bg-rose-400/10 border-rose-400/20" };
    }
  }

  const absPct = Math.abs(pct);
  const healthyZero = Number(healthy) === 0;
  const nearZero = healthyZero ? absPct < 1e-9 : absPct <= 5;
  return {
    text,
    colorClass: nearZero
      ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
      : "text-amber-300/90 bg-amber-400/10 border-amber-400/25",
  };
};

const ThickSlider = ({ value, min = 0, max = 10, step = 0.5, color = "sky", onChange, label, formatLabel }) => {
  const trackRef = useRef(null);
  const fillRef = useRef(null);
  const dragging = useRef(false);
  const rafId = useRef(null);
  const pendingX = useRef(null);
  const displayRef = useRef(parseFloat(value) || min);

  const decimals = Math.max(0, (String(step).split(".")[1] || "").length);
  const clamp = (n) => Math.min(max, Math.max(min, n));
  const snap = (raw) => Number((Math.round((raw - min) / step) * step + min).toFixed(decimals));
  const toPct = (v) => Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100));

  const [display, setDisplay] = useState(() => clamp(snap(parseFloat(value) || min)));

  useEffect(() => {
    if (!dragging.current) {
      const v = clamp(snap(parseFloat(value) || min));
      setDisplay(v);
    }
  }, [value, min, max, step]);

  const paint = useCallback((v) => {
    if (fillRef.current) fillRef.current.style.width = `${toPct(v)}%`;
  }, [min, max]);

  useEffect(() => {
    paint(display);
  }, [display, paint]);

  const valueFromClientX = useCallback((clientX) => {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0) return displayRef.current;
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return clamp(snap(min + ratio * (max - min)));
  }, [min, max, step, clamp, snap]);

  const applyClientX = useCallback((clientX, commit) => {
    const v = valueFromClientX(clientX);
    displayRef.current = v;
    paint(v);
    setDisplay(v);
    if (commit) onChange(String(v));
  }, [valueFromClientX, paint, onChange]);

  const scheduleApply = useCallback((clientX, commit = false) => {
    pendingX.current = { x: clientX, commit };
    if (rafId.current != null) return;
    rafId.current = requestAnimationFrame(() => {
      rafId.current = null;
      const p = pendingX.current;
      if (p) applyClientX(p.x, p.commit);
    });
  }, [applyClientX]);

  const onPointerDown = (e) => {
    e.preventDefault();
    dragging.current = true;
    trackRef.current?.classList.add("is-dragging");
    e.currentTarget.setPointerCapture?.(e.pointerId);
    scheduleApply(e.clientX, false);
  };

  const onPointerMove = (e) => {
    if (!dragging.current) return;
    e.preventDefault();
    scheduleApply(e.clientX, false);
  };

  const endDrag = (e) => {
    if (!dragging.current) return;
    dragging.current = false;
    trackRef.current?.classList.remove("is-dragging");
    if (rafId.current != null) { cancelAnimationFrame(rafId.current); rafId.current = null; }
    const x = e.clientX || pendingX.current?.x;
    if (x != null) applyClientX(x, true);
    else onChange(String(displayRef.current));
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  };

  const onKeyDown = (e) => {
    let next = display;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") next = display + step;
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = display - step;
    else if (e.key === "Home") next = min;
    else if (e.key === "End") next = max;
    else return;
    e.preventDefault();
    const v = clamp(snap(next));
    setDisplay(v);
    onChange(String(v));
  };

  const grad = SLIDER_GRAD[color] || SLIDER_GRAD.sky;
  const [gradFrom, gradTo] = grad;
  const pct = toPct(display);

  return (
    <div style={{ touchAction: "none" }}>
      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={display}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
        className="glass-slider-track relative h-8 rounded-full cursor-pointer focus:outline-none select-none bg-white/[0.08] border border-white/12"
        style={{ touchAction: "none", userSelect: "none", WebkitUserSelect: "none" }}
      >
        <div
          ref={fillRef}
          className="glass-slider-fill absolute inset-y-0 left-0 rounded-full"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${gradFrom}, ${gradTo})`,
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.28)",
          }}
        />
      </div>
      {(formatLabel || label) && (
        <div className="text-center mt-2">
          <span className="text-xs font-bold text-white/60">{formatLabel ? formatLabel(display) : label}</span>
        </div>
      )}
    </div>
  );
};

const VASSlider = ({ value, onChange, color = "sky" }) => {
  const n = parseFloat(value) || 0;
  const closestFace = VAS_FACES.reduce((prev, curr) =>
    Math.abs(curr.val - n) < Math.abs(prev.val - n) ? curr : prev
  );

  const c = color === "sky" ? "sky" : "emerald";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-between items-end px-1">
        {VAS_FACES.map((face) => {
          const active = face.val === closestFace.val;
          return (
            <motion.div
              key={face.val}
              animate={{ scale: active ? 1.3 : 1, opacity: active ? 1 : 0.3 }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
              className="flex flex-col items-center gap-1"
            >
              <span className="text-2xl">{face.emoji}</span>
              {active && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="text-[9px] font-bold text-center"
                  style={{ color: color === "sky" ? "#7dd3fc" : "#6ee7b7" }}
                >
                  {face.val}
                </motion.div>
              )}
            </motion.div>
          );
        })}
      </div>

      <ThickSlider
        value={n}
        min={0}
        max={10}
        step={0.5}
        color={c}
        onChange={onChange}
        formatLabel={(v) => {
          const face = VAS_FACES.reduce((prev, curr) =>
            Math.abs(curr.val - v) < Math.abs(prev.val - v) ? curr : prev
          );
          return `${v.toFixed(1)} / 10 — ${face.en}`;
        }}
      />
    </div>
  );
};

const VAMSSlider = ({ value, onChange, color = "sky" }) => {
  const n = parseFloat(value) || 0;
  const closestFace = VAMS_FACES.reduce((prev, curr) =>
    Math.abs(curr.val - n) < Math.abs(prev.val - n) ? curr : prev
  );

  const c = color === "sky" ? "sky" : "emerald";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-between items-end px-1">
        {VAMS_FACES.map((face) => {
          const active = face.val === closestFace.val;
          return (
            <motion.div
              key={face.val}
              animate={{ scale: active ? 1.3 : 1, opacity: active ? 1 : 0.3 }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
              className="flex flex-col items-center gap-1"
            >
              <span className="text-2xl">{face.emoji}</span>
              {active && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="text-[9px] font-bold text-center"
                  style={{ color: color === "sky" ? "#7dd3fc" : "#6ee7b7" }}
                >
                  {face.val}
                </motion.div>
              )}
            </motion.div>
          );
        })}
      </div>

      <ThickSlider
        value={n}
        min={0}
        max={10}
        step={0.5}
        color={c}
        onChange={onChange}
        formatLabel={(v) => {
          const face = VAMS_FACES.reduce((prev, curr) =>
            Math.abs(curr.val - v) < Math.abs(prev.val - v) ? curr : prev
          );
          return `${v.toFixed(1)} / 10 — ${face.en}`;
        }}
      />
    </div>
  );
};

const MotorSlider = ({ value, onChange, color = "sky" }) => {
  const n = parseFloat(value) || 0;

  const getLabel = (v) => {
    if (v === 0) return "No control";
    if (v <= 2) return "Very limited";
    if (v <= 4) return "Limited";
    if (v <= 6) return "Moderate";
    if (v <= 8) return "Good";
    return "Full control";
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-white/30">0</span>
        <span className="text-[10px] text-white/30">10</span>
      </div>
      <ThickSlider
        value={n}
        min={0}
        max={10}
        step={0.5}
        color={color}
        onChange={onChange}
        formatLabel={(v) => `${v.toFixed(1)} / 10 — ${getLabel(v)}`}
      />
    </div>
  );
};

const KVIQSlider = ({ value, onChange, labels, color = "cyan" }) => {
  const n = parseInt(value) || 1;
  const curr = labels.find((l) => l.val === n);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between px-1 mb-1">
        {[1,2,3,4,5].map((v) => (
          <span
            key={v}
            className={`text-[9px] font-bold ${
              n === v
                ? color === "cyan"
                  ? "text-cyan-300"
                  : color === "violet"
                  ? "text-violet-300"
                  : "text-emerald-300"
                : "text-white/25"
            }`}
          >
            {v}
          </span>
        ))}
      </div>

      <ThickSlider
        value={n}
        min={1}
        max={5}
        step={1}
        color={color}
        onChange={onChange}
        formatLabel={(v) => {
          const item = labels.find((l) => l.val === v);
          return item ? `${v} — ${item.en}` : "Select";
        }}
      />
    </div>
  );
};

function useSW() {
  const [ms, setMs] = useState(0);
  const [running, setRunning] = useState(false);
  const iRef = useRef(null);
  const t0 = useRef(0);
  const acc = useRef(0);
  const rRef = useRef(false);

  useEffect(() => {
    rRef.current = running;
  }, [running]);

  const start = useCallback(() => {
    if (rRef.current) return;
    t0.current = Date.now();
    rRef.current = true;
    setRunning(true);
    iRef.current = setInterval(() => setMs(acc.current + Date.now() - t0.current), 10);
  }, []);

  const stop = useCallback(() => {
    if (!rRef.current) return;
    clearInterval(iRef.current);
    acc.current += Date.now() - t0.current;
    rRef.current = false;
    setRunning(false);
    setMs(acc.current);
  }, []);

  const reset = useCallback(() => {
    clearInterval(iRef.current);
    acc.current = 0;
    t0.current = 0;
    rRef.current = false;
    setMs(0);
    setRunning(false);
  }, []);

  useEffect(() => () => {
    clearInterval(iRef.current);
  }, []);

  const fmt = (t) =>
    `${String(Math.floor(t / 60000)).padStart(2, "0")}:${String(Math.floor((t % 60000) / 1000)).padStart(2, "0")}.${String(Math.floor((t % 1000) / 10)).padStart(2, "0")}`;

  return { ms, running, start, stop, reset, fmt };
}

const SWBlock = ({ phase, taskData, onUpdate, showInferenceBadge = true }) => {
  const sw = useSW();
  const [copied, setCopied] = useState(false);
  const isPost = phase === "post";

  const copyTime = () => {
    const sec = (sw.ms / 1000).toFixed(2);
    navigator.clipboard?.writeText(sec).catch(() => {});
    onUpdate("time", sec);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const ratingLabels = [
    "Does not attempt",
    "Tries but fails",
    "Requires assistance",
    "Completes with difficulty",
    "Mild difficulty",
    "Normal movement"
  ];

  const rv = parseInt(taskData?.rating) || 0;

  return (
    <div className={`p-4 rounded-xl border ${isPost ? "bg-emerald-400/[0.05] border-emerald-400/15" : "bg-sky-400/[0.05] border-sky-400/15"}`}>
      <p className={`text-[10px] font-extrabold uppercase tracking-widest mb-3 ${isPost ? "text-emerald-300" : "text-sky-300"}`}>
        {isPost ? "Post" : "Pre"}
      </p>

      {showInferenceBadge && taskData?._inferred && (
        <div className="mb-3 px-2.5 py-2 rounded-lg bg-amber-500/10 border border-amber-400/20">
          <p className="text-[9px] font-bold text-amber-200/90 leading-snug">
            vWMFT — {Math.round((taskData._confidence ?? 0) * 100)}% confidence
            {taskData._timeEstimated ? " — time estimated" : ""}
            {taskData._capped ? " — capped" : ""}
          </p>
          {taskData._source && (
            <p className="text-[9px] text-amber-100/45 mt-0.5 leading-snug">{taskData._source}</p>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 mb-3">
        <div className="flex-1 text-center py-2 rounded-xl bg-black/30 border border-white/[0.08]">
          <span className="text-xl font-extrabold text-white font-mono tabular-nums">{sw.fmt(sw.ms)}</span>
        </div>

        <div className="flex gap-1.5">
          {[
            {
              Icon: Play,
              fn: sw.start,
              dis: sw.running,
              cls: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30",
              disCls: "bg-emerald-500/10 border-emerald-400/20 text-emerald-300/40"
            },
            {
              Icon: Square,
              fn: sw.stop,
              dis: !sw.running,
              cls: "bg-rose-500/20 border-rose-400/30 text-rose-300 hover:bg-rose-500/30",
              disCls: "bg-white/[0.04] border-white/[0.04] text-white/20"
            },
            {
              Icon: RotateCcw,
              fn: sw.reset,
              dis: false,
              cls: "bg-white/[0.05] border-white/[0.04] text-white/40 hover:text-white/70 hover:bg-white/[0.08]",
              disCls: ""
            }
          ].map(({ Icon, fn, dis, cls, disCls }, i) => (
            <motion.button
              key={i}
              whileTap={nlMotionTap(0.88)}
              onClick={fn}
              disabled={dis}
              className={`w-9 h-9 rounded-xl border flex items-center justify-center transition-all ${dis ? `${disCls} cursor-not-allowed` : cls}`}
            >
              <Icon className="w-3.5 h-3.5" />
            </motion.button>
          ))}

          <motion.button
            whileTap={nlMotionTap(0.88)}
            onClick={copyTime}
            className={`w-9 h-9 rounded-xl border flex items-center justify-center transition-all ${
              copied
                ? "bg-emerald-500/20 border-emerald-400/30 text-emerald-300"
                : "bg-white/[0.06] border-white/[0.04] text-white/50 hover:text-white"
            }`}
          >
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          </motion.button>
        </div>
      </div>

      <GI en="Time (sec)" type="number" value={taskData?.time ?? ""} onChange={(e) => onUpdate("time", e.target.value)} />

      <div className="mt-3">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10px] font-extrabold uppercase tracking-widest text-white/40">Ability Rating (0–5)</p>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-lg border ${isPost ? "bg-emerald-500/20 border-emerald-400/30 text-emerald-300" : "bg-sky-500/20 border-sky-400/30 text-sky-300"}`}>
            {rv}/5
          </span>
        </div>

        <ThickSlider
          value={rv}
          min={0}
          max={5}
          step={1}
          color={isPost ? "emerald" : "sky"}
          onChange={(v) => onUpdate("rating", v)}
          formatLabel={(v) => `${v} — ${ratingLabels[v]}`}
        />
      </div>
    </div>
  );
};

// ??? Demographics ?????????????????????????????????????????????????????????????

const DemoSection = ({ data, onChange, onBulkUpdate }) => {
  const s = (k, v) => onChange({ ...data, [k]: v });

  const validate = () => {
    const errs = [];
    if (!data.participantId) errs.push("Study ID required");
    if (data.group !== "1" && data.group !== "2") errs.push("Group must be 1 (AOMI) or 2 (Control)");
    if (data.age) { const a = parseInt(data.age); if (a < 40 || a > 80) errs.push("Age must be 40–80"); }
    if (data.sex !== "1" && data.sex !== "2") errs.push("Gender must be 1 (Male) or 2 (Female)");
    if (data.strokeType !== "1" && data.strokeType !== "2") errs.push("Stroke type must be 1 (Ischemic) or 2 (Hemorrhagic)");
    if (data.side !== "1" && data.side !== "2") errs.push("Affected side must be 1 (Left) or 2 (Right)");
    if (data.mas && !["0","1","1+","2","3","4"].includes(data.mas)) errs.push("MAS must be 0, 1, 1+, 2, 3, or 4");
    if (data.mrc && !["2","3","4","5"].includes(data.mrc)) errs.push("MRC must be 2, 3, 4, or 5");
    return errs;
  };
  const errors = validate();

  return (
    <div className="space-y-5">
      <SH icon={User} en="Participant Demographics" tr="Demografik Bilgiler" badge="Section 1" />

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Identification</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <GI en="Full Name" tr="Ad Soyad" value={data.name} onChange={(e) => s("name", e.target.value)} />
          <GI en="Study ID" tr="Study ID" type="number" min="101" value={data.participantId} onChange={(e) => s("participantId", e.target.value)} placeholder="Auto" />
          <GSelect en="Group" tr="Grup" value={data.group} onChange={(e) => s("group", e.target.value)} options={[{ value:"1",label:"1 = AOMI (Intervention)" },{ value:"2",label:"2 = Control" }]} />
          <GI en="Age (years)" tr="Age (years)" type="number" min="40" max="80" value={data.age} onChange={(e) => s("age", e.target.value)} placeholder="40–80" />
          <GSelect en="Gender" tr="Cinsiyet" value={data.sex} onChange={(e) => s("sex", e.target.value)} options={[{ value:"1",label:"1 = Male" },{ value:"2",label:"2 = Female" }]} />
          <GI en="Time Since Stroke (months)" tr="Time since stroke (months)" type="number" min="1" value={data.timeSinceStroke} onChange={(e) => s("timeSinceStroke", e.target.value)} placeholder="months" />
        </div>
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Clinical</p>

        <p className="text-[10px] font-bold text-white/30 uppercase tracking-wider mb-3">Side &amp; Hemisphere</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <GSelect en="Dominant Hand" tr="Dominant El" value={data.dominantHand} onChange={(e) => s("dominantHand", e.target.value)} options={[{ value:"right",label:"Right" },{ value:"left",label:"Left" },{ value:"both",label:"Both" }]} />
          <GSelect en="Affected Hemisphere" tr="Etkilenen Hemisfer" value={data.hemisphere} onChange={(e) => s("hemisphere", e.target.value)} options={[{ value:"left",label:"Left" },{ value:"right",label:"Right" },{ value:"bilateral",label:"Bilateral" }]} />
          <GSelect en="Stroke Type" tr="Stroke type" value={data.strokeType} onChange={(e) => s("strokeType", e.target.value)} options={[{ value:"1",label:"1 = Ischemic" },{ value:"2",label:"2 = Hemorrhagic" }]} />
          <GSelect en="Affected Side" tr="Etkilenen Taraf" value={data.side} onChange={(e) => s("side", e.target.value)} options={[{ value:"1",label:"1 = Left" },{ value:"2",label:"2 = Right" }]} />
        </div>

        <p className="text-[10px] font-bold text-white/30 uppercase tracking-wider mb-3">Anthropometrics</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <GI en="Height (cm)" tr="Boy (cm)" type="number" value={data.height} onChange={(e) => s("height", e.target.value)} placeholder="170" />
          <GI en="Weight (kg)" tr="Kilo (kg)" type="number" value={data.weight} onChange={(e) => s("weight", e.target.value)} placeholder="70" />
          <div className="flex flex-col gap-1.5">
            <BL en="BMI (auto)" tr="BMI (auto)" />
            <div className={`w-full px-3 py-2.5 rounded-xl border text-sm font-extrabold text-center ${(() => { const h=parseFloat(data.height), w=parseFloat(data.weight); if(!h||!w) return "bg-white/[0.05] border-white/[0.04] text-white/25"; const b=(w/((h/100)**2)).toFixed(1); if(b<18.5) return "bg-sky-400/10 border-sky-400/20 text-sky-300"; if(b<25) return "bg-emerald-400/10 border-emerald-400/20 text-emerald-300"; if(b<30) return "bg-amber-400/10 border-amber-400/20 text-amber-300"; return "bg-rose-400/10 border-rose-400/20 text-rose-300"; })()}`}>
              {(() => { const h=parseFloat(data.height), w=parseFloat(data.weight); return h&&w ? `${(w/((h/100)**2)).toFixed(1)} kg/m²` : NA; })()}
            </div>
          </div>
        </div>

        <p className="text-[10px] font-bold text-white/30 uppercase tracking-wider mb-3">Dates</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <GI en="Assessment Date" tr="Assessment date" type="date" value={data.assessDate} onChange={(e) => s("assessDate", e.target.value)} />
          <GI en="Stroke Date" tr="Stroke date" type="date" value={data.strokeDate} onChange={(e) => s("strokeDate", e.target.value)} />
        </div>

        <p className="text-[10px] font-bold text-white/30 uppercase tracking-wider mb-3">Clinical Assessment</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
          <GSelect en="MAS (Modified Ashworth)" tr="MAS" value={data.mas} onChange={(e) => s("mas", e.target.value)} options={[{ value:"0",label:"0 — No increase" },{ value:"1",label:"1 — Slight catch" },{ value:"1+",label:"1+ — Catch + minimal resistance" },{ value:"2",label:"2 — More marked" },{ value:"3",label:"3 — Considerable" },{ value:"4",label:"4 — Rigid" }]} />
          <GSelect en="MRC Muscle Strength" tr="MRC muscle strength" value={data.mrc} onChange={(e) => s("mrc", e.target.value)} options={[{ value:"2",label:"2 — Active, gravity eliminated" },{ value:"3",label:"3 — Against gravity" },{ value:"4",label:"4 — Against some resistance" },{ value:"5",label:"5 — Normal power" }]} />
        </div>
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Medical History</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <GSelect en="Disease Stage" tr="Disease stage" value={data.diseaseStage} onChange={(e) => s("diseaseStage", e.target.value)} options={[{ value:"acute",label:"Acute (<1 month)" },{ value:"subacute",label:"Subacute (1–6 months)" },{ value:"chronic",label:"Chronic (>6 months)" }]} />
          <div className="flex flex-col gap-1.5">
            <BL en="Treatment Duration" tr="Treatment duration" />
            <div className="flex gap-2">
              <input type="number" value={data.treatValue ?? ""} onChange={(e) => s("treatValue", e.target.value)} placeholder="0" className="flex-1 min-w-0 px-3 py-2.5 rounded-xl bg-white/[0.09] border border-white/12 text-white text-sm font-light focus:outline-none transition-all" />
              <GSelect
                value={data.treatUnit ?? "week"}
                onChange={(e) => s("treatUnit", e.target.value)}
                options={["day", "week", "month", "year"].map((u) => ({ value: u, label: u }))}
                className="w-28 flex-shrink-0"
              />
            </div>
          </div>
        </div>
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-1">Comorbidities</p>
        <p className="text-xs text-white/30 mb-4">Select all that apply</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
          {COMORBIDITIES.map((opt) => {
            const active = (data.comorbidities || []).includes(opt.value);
            return (
              <motion.button key={opt.value} whileTap={nlMotionTap(0.95)} onClick={() => { const cur = data.comorbidities || []; s("comorbidities", cur.includes(opt.value) ? cur.filter((c) => c !== opt.value) : [...cur, opt.value]); }}
                className={`text-left px-3 py-2.5 rounded-xl border text-xs font-semibold transition-all ${active ? "bg-violet-500/25 border-violet-400/40 text-violet-200" : "bg-white/[0.05] border-white/[0.04] text-white/50 hover:bg-white/[0.08]"}`}>
                <div className="flex items-center gap-2 min-w-0">
                  <div className={`w-3.5 h-3.5 rounded-sm border flex-shrink-0 flex items-center justify-center ${active ? "bg-violet-500 border-violet-400" : "border-white/20"}`}>{active && <Check className="w-2.5 h-2.5 text-white" />}</div>
                  <span className="leading-snug">{opt.label}</span>
                </div>
              </motion.button>
            );
          })}
        </div>
        {(data.comorbidities || []).includes("other") && (
          <motion.div initial={{ opacity:0, height:0 }} animate={{ opacity:1, height:"auto" }} className="mt-3">
            <GI en="Specify other" tr="Specify other" value={data.otherComorbidity} onChange={(e) => s("otherComorbidity", e.target.value)} placeholder="Other conditions?" />
          </motion.div>
        )}
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Clinical Notes</p>
        <div className="flex flex-col gap-3">
          <textarea rows={2} value={data.notes ?? ""} onChange={(e) => s("notes", e.target.value)} placeholder="Medical history, comorbidities, assessment context?" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.09] border border-white/12 text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none transition-all" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <textarea rows={2} value={data.antispasticDrugs ?? ""} onChange={(e) => s("antispasticDrugs", e.target.value)} placeholder="Antispastic drugs: Baclofen, Tizanidine?" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.09] border border-white/12 text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none transition-all" />
            <textarea rows={2} value={data.otherDrugs ?? ""} onChange={(e) => s("otherDrugs", e.target.value)} placeholder="Other medications: Aspirin, Warfarin?" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.09] border border-white/12 text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none transition-all" />
          </div>
        </div>
      </Glass>
    </div>
  );
};

// ??? IPAQ Section ?????????????????????????????????????????????????????????????

const IPAQSection = ({ data, onChange }) => {
  const sv = (id, f, v) => onChange({ ...data, [id]: { ...(data[id] || {}), [f]: v } });
  const tot = (id) => ((parseFloat(data[id]?.sure) || 0) * (parseFloat(data[id]?.gun) || 0)).toFixed(0);
  const ic = `glass-field w-full px-2 py-1.5 rounded-lg text-white text-sm font-bold text-center placeholder-white/15 focus:outline-none transition-all ${INPUT_CLS}`;

  const totalMET = IPAQ_ACTS.reduce((sum, a) => sum + ((parseFloat(tot(a.id)) || 0) * a.met), 0);

  const getClass = () => {
    const highDays = parseFloat(data.high?.gun) || 0;
    const medDays = parseFloat(data.medium?.gun) || 0;
    const lightDays = parseFloat(data.light?.gun) || 0;
    const med = parseFloat(tot("medium")) || 0;
    const light = parseFloat(tot("light")) || 0;

    if (highDays >= 3 && totalMET >= 1500) {
      return { level:"High", color:"emerald", text:"Vigorous activity ≥3 days and ≥1500 MET-min/week" };
    }
    if ((medDays + lightDays) >= 7 && totalMET >= 3000) {
      return { level:"High", color:"emerald", text:"Mixed activities 7 days and ≥3000 MET-min/week" };
    }
    if (totalMET >= 600 || (medDays + lightDays >= 5 && (med + light) >= 150)) {
      return { level:"Moderate", color:"amber", text:"≥600 MET-min/week or 5+ days moderate/walking" };
    }
    return { level:"Low", color:"rose", text:"Not meeting moderate or high criteria" };
  };

  const cls = getClass();

  return (
    <div className="space-y-5">
      <SH icon={Activity} en="International Physical Activity Questionnaire (IPAQ)" tr="IPAQ" />

      <Glass className="p-4 sm:p-5">
        {/* Mobile ? stacked cards (no horizontal squeeze) */}
        <div className="md:hidden space-y-3">
          {IPAQ_ACTS.map((a) => (
            <div key={a.id} className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3 space-y-3">
              <div>
                <p className="text-sm font-extrabold text-white/90 leading-snug">{a.en}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[10px] font-extrabold text-sky-300/90 uppercase mb-1.5">Min/day</p>
                  <input type="number" min="0" value={data[a.id]?.sure ?? ""} onChange={(e) => sv(a.id, "sure", e.target.value)} className={ic} placeholder="" />
                </div>
                <div>
                  <p className="text-[10px] font-extrabold text-violet-300/90 uppercase mb-1.5">Days/wk</p>
                  <input type="number" min="0" max="7" value={data[a.id]?.gun ?? ""} onChange={(e) => sv(a.id, "gun", e.target.value)} className={ic} placeholder="" />
                </div>
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-white/[0.06]">
                <span className="text-[10px] font-extrabold text-emerald-300/80 uppercase">Total min/wk</span>
                <div className="px-3 py-1.5 rounded-lg bg-emerald-400/10 border border-emerald-400/20 text-emerald-300 font-extrabold text-sm min-w-[3rem] text-center">{tot(a.id)}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Desktop ? table */}
        <div className="hidden md:block glass-float overflow-x-auto rounded-xl border border-white/[0.08]">
          <table className="w-full text-sm min-w-[580px]">
            <thead>
              <tr className="bg-white/[0.06] border-b border-white/[0.04]">
                <th className="text-left px-3 py-3 font-extrabold text-white/70 text-xs uppercase w-1/2">Activity</th>
                <th className="text-center px-3 py-3 text-sky-300 text-xs font-extrabold uppercase">Min/day</th>
                <th className="text-center px-3 py-3 text-violet-300 text-xs font-extrabold uppercase">Days/week</th>
                <th className="text-center px-3 py-3 text-emerald-300 text-xs font-extrabold uppercase">Total min/wk</th>
              </tr>
            </thead>

            <tbody>
              {IPAQ_ACTS.map((a, i) => (
                <tr key={a.id} className={`border-b border-white/[0.06] hover:bg-white/[0.03] ${i % 2 === 0 ? "" : "bg-white/[0.02]"}`}>
                  <td className="px-3 py-3 text-xs text-white/80">
                    <span className="block">{a.en}</span>
                  </td>
                  <td className="px-2 py-2">
                    <input type="number" min="0" value={data[a.id]?.sure ?? ""} onChange={(e) => sv(a.id, "sure", e.target.value)} className={ic} placeholder="" />
                  </td>
                  <td className="px-2 py-2">
                    <input type="number" min="0" max="7" value={data[a.id]?.gun ?? ""} onChange={(e) => sv(a.id, "gun", e.target.value)} className={ic} placeholder="" />
                  </td>
                  <td className="px-3 py-3 text-center">
                    <div className="px-3 py-1.5 rounded-lg bg-emerald-400/10 border border-emerald-400/20 text-emerald-300 font-extrabold">{tot(a.id)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Glass>

      <Glass className="p-4 sm:p-5 border-l-2 border-amber-400/40">
        <div className="flex items-start gap-3 mb-4">
          <BarChart3 className="w-5 h-5 text-amber-300 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-extrabold text-white/90">Physical Activity Level Interpretation</p>
            <p className="text-xs font-light text-white/40 mt-0.5">Based on IPAQ scoring guidelines</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="glass-float px-4 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08]">
            <p className="text-[10px] font-extrabold text-white/40 uppercase mb-1">Total MET-minutes/week</p>
            <p className="text-2xl font-extrabold text-white">{totalMET.toFixed(0)}</p>
            <p className="text-xs text-white/50 mt-1">Metabolic Equivalent of Task</p>
          </div>

          <div className={`px-4 py-3 rounded-xl border ${
            cls.color === "emerald"
              ? "bg-emerald-400/10 border-emerald-400/20"
              : cls.color === "amber"
              ? "bg-amber-400/10 border-amber-400/20"
              : "bg-rose-400/10 border-rose-400/20"
          }`}>
            <p className="text-[10px] font-extrabold text-white/40 uppercase mb-1">Activity Classification</p>
            <p className={`text-2xl font-extrabold ${
              cls.color === "emerald"
                ? "text-emerald-300"
                : cls.color === "amber"
                ? "text-amber-300"
                : "text-rose-300"
            }`}>
              {cls.level}
            </p>
            <p className="text-xs text-white/50 mt-1">{cls.text}</p>
          </div>
        </div>
      </Glass>
    </div>
  );
};

// ??? VAS Section ??????????????????????????????????????????????????????????????

const VASSection = ({ data, onChange }) => {
  const s = (k, ph, v) => onChange({ ...data, [k]: { ...data[k], [ph]: v } });
  const items = [
    { k:"rest", en:"Pain at Rest", tr:"İstirahat Ağrısı" },
    { k:"activity", en:"Pain During Activity", tr:"Aktivite Sırasında Ağrı" },
  ];

  return (
    <div className="space-y-5">
      <SH icon={Sliders} en="Visual Analogue Scale (VAS)" tr="VAS" badge="0–10 with faces" />

      {items.map((item) => (
        <Glass key={item.k} className="p-5">
          <BL en={item.en} tr={item.tr} className="mb-4" />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {["pre","post"].map((ph) => (
              <div key={ph} className={`p-4 rounded-xl border ${ph === "pre" ? "bg-sky-400/[0.05] border-sky-400/15" : "bg-emerald-400/[0.05] border-emerald-400/15"}`}>
                <p className={`text-[10px] font-extrabold uppercase tracking-widest mb-3 ${ph === "pre" ? "text-sky-300" : "text-emerald-300"}`}>
                  {ph === "pre" ? "Pre" : "Post"}
                </p>
                <VASSlider value={data[item.k]?.[ph] ?? "0"} onChange={(v) => s(item.k, ph, v)} color={ph === "pre" ? "sky" : "emerald"} />
              </div>
            ))}
          </div>
        </Glass>
      ))}

      <Glass className="p-5 border-l-2 border-amber-400/40">
        <div className="flex items-center gap-2 mb-3">
          <Edit3 className="w-4 h-4 text-amber-300" />
          <p className="text-xs font-extrabold text-white/70 uppercase tracking-widest">Session Notes</p>
        </div>

        <div className="flex flex-wrap gap-1.5 mb-3">
          {[
            { label:"Baclofen", val:"MED=baclofen 10mg 1h before" },
            { label:"Tizanidine", val:"MED=tizanidine 4mg" },
            { label:"Fatigue+", val:"FATIGUE=high" },
            { label:"Fatigue~", val:"FATIGUE=moderate" },
            { label:"Morning", val:"SESSION=morning" },
            { label:"Afternoon", val:"SESSION=afternoon" },
            { label:"Evening", val:"SESSION=evening" },
            { label:"Pain+", val:"PAIN=increased during session" },
            { label:"Motivated", val:"NOTES=patient motivated, good effort" },
            { label:"Tired", val:"NOTES=patient tired, low energy" },
          ].map((btn) => {
            const exists = (data?.notes || "").split("\n").includes(btn.val);
            return (
              <button
                key={btn.val}
                type="button"
                onClick={() => {
                  const lines = (data?.notes || "").split("\n").filter(Boolean);
                  if (exists) {
                    onChange({ ...data, notes: lines.filter(l => l !== btn.val).join("\n") });
                  } else {
                    onChange({ ...data, notes: [...lines, btn.val].join("\n") });
                  }
                }}
                className={`text-[9px] font-bold px-2 py-1 rounded-lg border transition-all whitespace-nowrap ${
                  exists
                    ? "bg-amber-400/20 border-amber-400/30 text-amber-200"
                    : "bg-amber-400/10 border-amber-400/20 text-amber-300 hover:bg-amber-400/20"
                }`}
              >
                {exists ? "✓ " : "+ "}{btn.label}
              </button>
            );
          })}
        </div>

        <textarea
          rows={3}
          value={data?.notes ?? ""}
          onChange={(e) => onChange({ ...data, notes: e.target.value })}
          placeholder={`Quick shorthand:
  MED=baclofen 10mg 1h before
  FATIGUE=moderate
  SESSION=afternoon, quiet room
  TIME=14:30
  NOTES=patient anxious today, slow responses`}
          className="w-full px-3 py-2.5 rounded-xl bg-amber-500/[0.06] border border-amber-400/15 text-white text-sm font-light placeholder-white/20 resize-none focus:outline-none focus:border-amber-400/30 transition-all"
        />
      </Glass>
    </div>
  );
};

// ??? VAMS-4 Section ??????????????????????????????????????????????????????????????

const VAMSSection = ({ data, onChange }) => {
  const s = (k, ph, v) => onChange({ ...data, [k]: { ...data[k], [ph]: v } });
  const items = [
    { k:"happy", en:"Happy", tr:"Mutlu", qEN:"How happy do you feel right now?", qTR:"Şu anda ne kadar mutlusunuz?" },
    { k:"sad", en:"Sad", tr:"Üzgün", qEN:"How sad do you feel right now?", qTR:"Şu anda ne kadar üzgünsünüz?" },
    { k:"calm", en:"Calm", tr:"Sakin", qEN:"How calm do you feel right now?", qTR:"Şu anda ne kadar sakinsiniz?" },
    { k:"tense", en:"Tense", tr:"Gergin", qEN:"How tense do you feel right now?", qTR:"Şu anda ne kadar gerginsiniz?" },
  ];

  return (
    <div className="space-y-5">
      <SH icon={Heart} en="Mood Scale (VAMS-4)" tr="VAMS-4" badge="0–10" />

      <Glass className="p-5 border-l-2 border-violet-400/40">
        <div className="flex gap-3">
          <Heart className="w-5 h-5 text-violet-300 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-light text-white/75">
              Rate your current mood from <span className="font-bold text-white">0 (not at all)</span> to <span className="font-bold text-white">10 (extremely)</span>
            </p>
            <p className="text-xs text-white/50 mt-1">VAMS-4 (Machado et al. 2019) — Validated in stroke (Stern 1999, Barrows 2018)</p>
          </div>
        </div>
      </Glass>

      {items.map((item) => (
        <Glass key={item.k} className="p-5">
          <BL en={item.en} tr={item.tr} className="mb-1" />
          <p className="text-xs text-white/55 italic mb-4">{item.qEN}</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {["pre","post"].map((ph) => (
              <div key={ph} className={`p-4 rounded-xl border ${ph === "pre" ? "bg-sky-400/[0.05] border-sky-400/15" : "bg-emerald-400/[0.05] border-emerald-400/15"}`}>
                <p className={`text-[10px] font-extrabold uppercase tracking-widest mb-3 ${ph === "pre" ? "text-sky-300" : "text-emerald-300"}`}>
                  {ph === "pre" ? "Pre" : "Post"}
                </p>
                <VAMSSlider value={data[item.k]?.[ph] ?? "0"} onChange={(v) => s(item.k, ph, v)} color={ph === "pre" ? "sky" : "emerald"} />
              </div>
            ))}
          </div>
        </Glass>
      ))}
    </div>
  );
};

// ??? Motor Section ????????????????????????????????????????????????????????????

const MotorSection = ({ data, onChange }) => {
  const s = (k, v) => onChange({ ...data, [k]: v });

  return (
    <div className="space-y-5">
      <SH icon={TrendingUp} en="Patient Perceived Muscle Control Change Scale" tr="Muscle control" />

      <Glass className="p-5 border-l-2 border-amber-400/40">
        <div className="flex gap-3">
          <Info className="w-5 h-5 text-amber-300 flex-shrink-0 mt-0.5" />
          <p className="text-sm font-light text-white/75 italic">0 = no control, 10 = full normal control.</p>
        </div>
      </Glass>

      {MOTOR_ITEMS.map((item) => (
        <Glass key={item.key} className="p-5">
          <p className="font-extrabold text-white/90 text-sm mb-0.5">{item.en}</p>

          <div className={`p-4 rounded-xl border ${item.phase === "pre" ? "bg-sky-400/[0.05] border-sky-400/15" : "bg-emerald-400/[0.05] border-emerald-400/15"}`}>
            <p className={`text-[10px] font-extrabold uppercase tracking-widest mb-3 ${item.phase === "pre" ? "text-sky-300" : "text-emerald-300"}`}>
              {item.phase === "pre" ? "Pre-Test" : "Post-Test"}
            </p>
            <MotorSlider value={data[item.key] ?? ""} onChange={(v) => s(item.key, v)} color={item.phase === "pre" ? "sky" : "emerald"} />
          </div>
        </Glass>
      ))}
    </div>
  );
};

// ??? KVIQ Section ?????????????????????????????????????????????????????????????

const KGIASection = ({ data, onChange }) => {
  const s = (mi, type, f, v) => {
    const k = `${mi}_${type}`;
    onChange({ ...data, [k]: { ...(data[k] || {}), [f]: v } });
  };

  return (
    <div className="space-y-5">
      <SH icon={Brain} en="Kinesthetic & Visual Imagery Questionnaire (KVIQ-10)" tr="KVIQ" badge="5 movements · 2 types" />

      <div className="flex gap-3 flex-wrap">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-400/10 border border-amber-400/20">
          <span className="w-3 h-3 rounded-full bg-amber-400 flex-shrink-0" />
          <span className="text-xs font-bold text-amber-300">Upper Extremity</span>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.04]">
          <span className="w-3 h-3 rounded-full bg-white/30 flex-shrink-0" />
          <span className="text-xs font-bold text-white/50">Other</span>
        </div>
      </div>

      <div className="space-y-4">
        {KGIA_MOVEMENTS.map((mov, mi) => (
          <Glass key={mi} className={`p-5 ${mov.ue ? "border-amber-400/20" : ""}`}>
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-8 h-8 rounded-xl border flex items-center justify-center flex-shrink-0 ${
                mov.ue ? "bg-amber-500/20 border-amber-400/25" : "bg-white/10 border-white/[0.08]"
              }`}>
                <span className={`text-sm font-extrabold ${mov.ue ? "text-amber-300" : "text-white/70"}`}>{mi + 1}</span>
              </div>

              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-extrabold text-white/90 text-sm">{mov.en}</p>
                  {mov.ue && (
                    <span className="px-2 py-0.5 rounded-full text-[9px] font-extrabold bg-amber-400/20 border border-amber-400/30 text-amber-300 uppercase">
                      UPPER EXT
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {KGIA_TYPES.map((t) => (
                <div
                  key={t.key}
                  className={`p-4 rounded-xl border ${t.key === "gorsel" ? "bg-cyan-400/[0.04] border-cyan-400/20" : "bg-violet-400/[0.04] border-violet-400/20"}`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`px-2.5 py-1 rounded-lg text-xs font-bold border ${
                      t.key === "gorsel"
                        ? "bg-cyan-400/15 border-cyan-400/25 text-cyan-300"
                        : "bg-violet-400/15 border-violet-400/25 text-violet-300"
                    }`}>
                      {t.en}
                    </span>
                  </div>

                  <p className="text-xs font-semibold text-white/65 mb-4">{t.qEN}</p>

                  {["once","sonra"].map((f, fi) => (
                    <div key={f} className={fi === 1 ? "mt-4" : ""}>
                      <p className={`text-[10px] font-extrabold uppercase tracking-widest mb-2 ${fi === 0 ? "text-sky-300" : "text-emerald-300"}`}>
                        {fi === 0 ? "Pre (1–5)" : "Post (1–5)"}
                      </p>

                      <KVIQSlider
                        value={data[`${mi}_${t.key}`]?.[f] ?? "1"}
                        onChange={(v) => s(mi, t.key, f, v)}
                        labels={t.labels}
                        color={fi === 0 ? (t.key === "gorsel" ? "cyan" : "violet") : "emerald"}
                      />
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </Glass>
        ))}
      </div>
    </div>
  );
};

// ??? Box & Block Test (BBT) ? separate from Kinematics Lab ???????????????????

const BBTPhaseBlock = ({ phase, phaseData, onUpdate }) => {
  const sw = useSW();
  const isPost = phase === "post";
  const limitMs = BBT_TEST_SECONDS * 1000;

  useEffect(() => {
    if (sw.ms >= limitMs && sw.running) sw.stop();
  }, [sw.ms, sw.running, sw, limitMs]);

  const ic = `glass-field w-full px-3 py-2.5 rounded-xl text-white text-sm font-light placeholder-white/30 focus:outline-none transition-all ${INPUT_CLS}`;

  return (
    <div className={`p-4 rounded-xl border ${isPost ? "bg-emerald-400/[0.05] border-emerald-400/15" : "bg-sky-400/[0.05] border-sky-400/15"}`}>
      <p className={`text-[10px] font-extrabold uppercase tracking-widest mb-3 ${isPost ? "text-emerald-300" : "text-sky-300"}`}>
        {isPost ? "Post" : "Pre"}
      </p>

      <p className="text-[10px] text-white/45 mb-2">
        {BBT_TEST_SECONDS}s timer — count blocks transferred over the partition (paretic hand primary).
      </p>

      <div className="flex items-center gap-2 mb-4">
        <div className={`flex-1 text-center py-2 rounded-xl border ${sw.ms >= limitMs ? "border-amber-400/40 bg-amber-500/10" : "bg-black/30 border-white/[0.08]"}`}>
          <span className="text-xl font-extrabold text-white font-mono tabular-nums">{sw.fmt(Math.min(sw.ms, limitMs))}</span>
          <span className="block text-[9px] text-white/35 mt-0.5">/ {BBT_TEST_SECONDS}:00</span>
        </div>
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={sw.start}
            disabled={sw.running || sw.ms >= limitMs}
            className={`w-10 h-10 rounded-lg border flex items-center justify-center transition-all ${sw.running || sw.ms >= limitMs ? "bg-emerald-500/10 border-emerald-400/20 text-emerald-300/40" : "bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30"}`}
            aria-label="Start timer"
          >
            <Play className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={sw.stop}
            disabled={!sw.running}
            className={`w-10 h-10 rounded-lg border flex items-center justify-center transition-all ${!sw.running ? "bg-white/[0.04] border-white/[0.04] text-white/20" : "bg-rose-500/20 border-rose-400/30 text-rose-300 hover:bg-rose-500/30"}`}
            aria-label="Stop timer"
          >
            <Square className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={sw.reset}
            className="w-10 h-10 rounded-lg border bg-white/[0.06] border-white/12 text-white/60 hover:text-white flex items-center justify-center transition-all"
            aria-label="Reset timer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
        <div className="flex flex-col gap-1.5">
          <BL en="Paretic hand — blocks" tr="Paretic hand" />
          <input
            type="number"
            min="0"
            inputMode="numeric"
            value={phaseData?.pareticBlocks ?? ""}
            onChange={(e) => onUpdate("pareticBlocks", e.target.value)}
            placeholder="0"
            className={ic}
            style={GLASS_FIELD}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <BL en="Unaffected hand — blocks (optional)" tr="Unaffected hand" />
          <input
            type="number"
            min="0"
            inputMode="numeric"
            value={phaseData?.unaffectedBlocks ?? ""}
            onChange={(e) => onUpdate("unaffectedBlocks", e.target.value)}
            placeholder=""
            className={ic}
            style={GLASS_FIELD}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <BL en="Notes" tr="Notlar" />
        <textarea
          value={phaseData?.notes ?? ""}
          onChange={(e) => onUpdate("notes", e.target.value)}
          rows={2}
          placeholder="Setup, fatigue, assistance?"
          className={`${ic} min-h-[72px] resize-y`}
          style={GLASS_FIELD}
        />
      </div>
    </div>
  );
};

const BBTSection = ({ data, onChange, demographics }) => {
  const up = (ph, f, v) =>
    onChange({ ...data, [ph]: { ...(data[ph] || {}), [f]: v } });

  const side = demographics?.side === "1" ? "left" : demographics?.side === "2" ? "right" : null;

  return (
    <div className="space-y-5">
      <SH
        icon={Boxes}
        en="Box and Block Test (BBT)"
        tr="Kutu ve Blok Testi"
        badge={`${BBT_TEST_SECONDS}s`}
      />

      <Glass className="p-4 sm:p-5">
        <p className="text-xs text-white/60 leading-relaxed">
          <span className="font-bold text-white/75">Protocol:</span>{" "}
          Participant sits at a table; transfer as many blocks as possible across the partition in{" "}
          {BBT_TEST_SECONDS} seconds. Record the <strong className="text-white/80">paretic hand</strong> count for the study outcome
          {side ? ` (affected side: ${side})` : ""}. Unaffected-hand count is optional for reference norms.
        </p>
      </Glass>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BBTPhaseBlock phase="pre" phaseData={data?.pre} onUpdate={(f, v) => up("pre", f, v)} />
        <BBTPhaseBlock phase="post" phaseData={data?.post} onUpdate={(f, v) => up("post", f, v)} />
      </div>
    </div>
  );
};

// ??? WMFT Section ?????????????????????????????????????????????????????????????

const WMFTSection = ({ data, onChange, kinematics, showToast }) => {
  const up = (id, ph, f, v) => {
    const cur = data?.[id]?.[ph] || {};
    const nextPh = { ...cur, [f]: v };
    if (f === "time" || f === "rating") {
      delete nextPh._inferred;
      delete nextPh._source;
      delete nextPh._confidence;
      delete nextPh._itemScore;
      delete nextPh._capped;
    }
    onChange({ ...data, [id]: { ...data[id], [ph]: nextPh } });
  };

  const kinResultsLive = loadLiveKinResults({ kinematics });
  const hasKin = !!(kinResultsLive.pre || kinResultsLive.post);

  const runInference = (overwrite) => {
    const kinResults = kinResultsLive;
    if (!kinResults.pre && !kinResults.post) {
      showToast?.("Analyze Pre and/or Post kinematics first", "error");
      return;
    }
    const inference = inferWmftFromKinematics(kinResults);
    const next = applyWmftInference(data, inference, { overwrite });
    const applied = next._inferenceMeta?.applied ?? 0;
    onChange(next);
    if (applied === 0) {
      showToast?.("No WMFT fields filled — check ADL phases or re-analyze", "error");
    } else {
      showToast?.(`WMFT-4: filled ${applied} field${applied === 1 ? "" : "s"} from kinematics`);
    }
  };

  return (
    <div className="space-y-5">
      <SH icon={Timer} en="Wolf Motor Function Test (WMFT-4)" tr="WMFT-4" badge="4 Tasks" />

      <Glass className="p-4 border border-violet-400/15 bg-violet-500/[0.06]">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-extrabold text-violet-200/90">Video-derived WMFT (vWMFT-4)</p>
            <p className="text-[10px] text-white/40 mt-1 leading-relaxed">
              Maps analyzed reach / ADL phases to WMFT items. Drink ADL improves items 1 &amp; 4; study reach covers 2 &amp; 3. Manual edits override inference.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 flex-shrink-0">
            <motion.button
              type="button"
              whileTap={nlMotionTap(0.97)}
              disabled={!hasKin}
              onClick={() => runInference(false)}
              className={`px-3 py-2 rounded-xl text-[11px] font-bold border flex items-center gap-1.5 ${
                hasKin
                  ? "bg-violet-500/20 border-violet-400/30 text-violet-200 hover:bg-violet-500/28"
                  : "bg-white/[0.03] border-white/[0.06] text-white/25 cursor-not-allowed"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              Fill empty fields
            </motion.button>
            <motion.button
              type="button"
              whileTap={nlMotionTap(0.97)}
              disabled={!hasKin}
              onClick={() => runInference(true)}
              className={`px-3 py-2 rounded-xl text-[11px] font-bold border ${
                hasKin
                  ? "bg-white/[0.06] border-white/[0.08] text-white/55 hover:text-white/80"
                  : "bg-white/[0.03] border-white/[0.06] text-white/25 cursor-not-allowed"
              }`}
            >
              Overwrite all
            </motion.button>
          </div>
        </div>
      </Glass>

      {WMFT_ITEMS.map((t) => (
        <Glass key={t.id} className="p-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-xl bg-amber-500/20 border border-amber-400/20 flex items-center justify-center text-amber-300 font-extrabold text-sm flex-shrink-0">
              {t.id}
            </div>
            <div>
              <p className="font-extrabold text-white/90 text-sm">{t.en}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SWBlock phase="pre" taskData={data[t.id]?.pre} onUpdate={(f, v) => up(t.id, "pre", f, v)} />
            <SWBlock phase="post" taskData={data[t.id]?.post} onUpdate={(f, v) => up(t.id, "post", f, v)} />
          </div>
        </Glass>
      ))}
    </div>
  );
};

// ??? Form data persistence ????????????????????????????????????????????????????

const FD_LS_KEY = "neuro_fd_data";
const NEXT_ID_LS_KEY = "neuro_next_id";
const API_BASE = "";

// Cross-platform file download ? never window.open on iOS PWA (no back button)
function downloadBlob(blob, filename) {
  downloadBlobUtil(blob, filename);
}

function nextStudyId() {
  const patients = activePatients();
  let maxId = 100;
  patients.forEach((p) => {
    const id = parseInt(p.demographics?.participantId);
    if (!isNaN(id) && id > maxId) maxId = id;
  });
  return maxId + 1;
}

function smoothVelPath(pts, xFn, yFn) {
  if (pts.length < 2) return "";
  if (pts.length === 2)
    return `M${xFn(pts[0].t).toFixed(1)},${yFn(pts[0].v).toFixed(1)}L${xFn(pts[1].t).toFixed(1)},${yFn(pts[1].v).toFixed(1)}`;
  let d = `M${xFn(pts[0].t).toFixed(1)},${yFn(pts[0].v).toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i === 0 ? 0 : i - 1];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2 >= pts.length ? pts.length - 1 : i + 2];
    const cp1x = xFn(p1.t) + (xFn(p2.t) - xFn(p0.t)) / 6;
    const cp1y = yFn(p1.v) + (yFn(p2.v) - yFn(p0.v)) / 6;
    const cp2x = xFn(p2.t) - (xFn(p3.t) - xFn(p1.t)) / 6;
    const cp2y = yFn(p2.v) - (yFn(p3.v) - yFn(p1.v)) / 6;
    d += `C${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${xFn(p2.t).toFixed(1)},${yFn(p2.v).toFixed(1)}`;
  }
  return d;
}

function buildCombinedVelChart(profiles, isPdf, compact) {
  const colors = { pre:"#38bdf8", during:"#a78bfa", post:"#34d399", baseline:"#fbbf24" };
  const labels = { pre:"Pre", during:"During", post:"Post", baseline:"Healthy side" };
  const entries = Object.entries(profiles)
    .map(([key, p]) => [key, { t: p?.t ?? p?.time, v: p?.v ?? p?.speed }])
    .filter(([_, p]) => p.t?.length >= 2);
  if (!entries.length) return "";
  const normalized = entries.map(([key, p]) => {
    const t0 = p.t[0];
    return [key, { t: p.t.map((ti) => +(ti - t0).toFixed(3)), v: p.v }];
  });
  const allT = normalized.flatMap(([_, p]) => p.t);
  const allV = normalized.flatMap(([_, p]) => p.v);
  const tMin = Math.min(...allT), tMax = Math.max(...allT);
  const vMax = Math.max(...allV, 0.01);

  const isPrint = !!isPdf && !compact;
  const cfg = compact
    ? { w: 320, h: 140, pad: 28, topPad: 14, bottomPad: 24, fs: 9, sw: 2, dotR: 3, dotSw: 1.5, bg: false, legend: false, theme: "dark" }
    : isPrint
    ? { w: 900, h: 300, pad: 62, topPad: 52, bottomPad: 38, fs: 12, sw: 2.5, dotR: 4.5, dotSw: 2, bg: true, legend: entries.length > 1, theme: "print" }
    : { w: 900, h: 260, pad: 56, topPad: entries.length > 1 ? 44 : 28, bottomPad: 34, fs: 11, sw: 2.5, dotR: 4, dotSw: 2, bg: false, legend: entries.length > 1, theme: "dark" };

  const { w, h, pad, topPad, bottomPad, fs, sw, dotR, dotSw, bg, legend, theme } = cfg;
  const plotW = w - 2 * pad;
  const plotH = h - topPad - bottomPad;
  const xp = (t) => pad + ((t - tMin) / (tMax - tMin || 1)) * plotW;
  const yp = (v) => topPad + plotH - (v / vMax) * plotH;
  const lines = normalized.map(([key, prof]) => {
    const pts = prof.t.map((t, i) => ({ t, v: prof.v[i] }));
    const path = smoothVelPath(pts, xp, yp);
    const peak = pts.reduce((a, b) => a.v > b.v ? a : b);
    const color = colors[key] || "#94a3b8";
    return { key, path, peak, color, label: labels[key] || key };
  });

  const labelFill = theme === "print" ? "#64748b" : "#64748b";
  const axisStroke = theme === "print" ? "#94a3b8" : "#334155";
  const legendFill = theme === "print" ? "#475569" : "#94a3b8";
  const peakStroke = theme === "print" ? "#ffffff" : "#ffffff";
  const svgSize = isPrint
    ? ` width="${w}" height="${h}"`
    : compact
    ? ' width="100%" height="100%" preserveAspectRatio="xMidYMid meet"'
    : ' width="100%"';
  let svg = `<svg viewBox="0 0 ${w} ${h}"${svgSize} xmlns="http://www.w3.org/2000/svg">`;

  if (bg && theme === "print") {
    svg += `<rect width="${w}" height="${h}" fill="#f8fafc" rx="10"/>`;
    svg += `<rect x="0.5" y="0.5" width="${w - 1}" height="${h - 1}" fill="none" stroke="#e2e8f0" stroke-width="1" rx="10"/>`;
  } else if (bg) {
    svg += `<rect width="${w}" height="${h}" fill="#1e2433" rx="10"/>`;
  }

  if (legend) {
    const itemW = isPrint ? 132 : 118;
    const legendW = lines.length * itemW - 8;
    const legendStart = (w - legendW) / 2;
    lines.forEach((l, i) => {
      const lx = legendStart + i * itemW;
      const ly = topPad - (isPrint ? 26 : 22);
      svg += `<circle cx="${lx + 5}" cy="${ly}" r="${isPrint ? 5 : 4}" fill="${l.color}"/>`;
      svg += `<text x="${lx + 16}" y="${ly + (isPrint ? 5 : 4)}" font-family="Arial,Helvetica,sans-serif" font-size="${fs}" fill="${legendFill}" font-weight="600">${l.label}</text>`;
    });
  }

  svg += `<text x="${pad + plotW / 2}" y="${h - (isPrint ? 12 : 8)}" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="${fs}" fill="${labelFill}">Time (s)</text>`;
  svg += `<text x="${compact ? 10 : isPrint ? 18 : 14}" y="${topPad + plotH / 2}" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="${fs}" fill="${labelFill}" transform="rotate(-90,${compact ? 10 : isPrint ? 18 : 14},${topPad + plotH / 2})">Velocity (SW/s)</text>`;
  svg += `<line x1="${pad}" y1="${topPad}" x2="${pad}" y2="${topPad + plotH}" stroke="${axisStroke}" stroke-width="${isPrint ? 1.2 : 1}"/>`;
  svg += `<line x1="${pad}" y1="${topPad + plotH}" x2="${pad + plotW}" y2="${topPad + plotH}" stroke="${axisStroke}" stroke-width="${isPrint ? 1.2 : 1}"/>`;
  if (theme === "print") {
    for (let i = 1; i <= 4; i++) {
      const gy = topPad + (plotH * i) / 5;
      svg += `<line x1="${pad}" y1="${gy}" x2="${pad + plotW}" y2="${gy}" stroke="#e2e8f0" stroke-width="0.8"/>`;
    }
  }
  lines.forEach((l) => {
    svg += `<path d="${l.path}" fill="none" stroke="${l.color}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"/>`;
    svg += `<circle cx="${xp(l.peak.t)}" cy="${yp(l.peak.v)}" r="${dotR}" fill="${l.color}" stroke="${peakStroke}" stroke-width="${dotSw}"/>`;
  });
  svg += `</svg>`;
  return svg;
}

function svgToDataUrl(svg) {
  const xml = svg.includes("xmlns=") ? svg : svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
}


// ??? Kinematics AI Lab Section ????????????????????????????????????????????????

const KIN_LS_KEY = KIN_RESULTS_LS_KEY;
const KIN_LS_EXP_KEY = "neuro_kin_expanded";

const KIN_PHASE_ACCENT = {
  sky: { bar: "bg-sky-400", ring: "border-t-sky-400", glow: "shadow-sky-500/10", top: "border-t-sky-400/80 from-sky-500/14" },
  emerald: { bar: "bg-emerald-400", ring: "border-t-emerald-400", glow: "shadow-emerald-500/10", top: "border-t-emerald-400/80 from-emerald-500/14" },
  amber: { bar: "bg-amber-400", ring: "border-t-amber-400", glow: "shadow-amber-500/10", top: "border-t-amber-400/80 from-amber-500/14" },
};

const KIN_FILM_ACCENT = {
  sky: { stroke: "#38bdf8", glow: "rgba(56,189,248,0.45)" },
  emerald: { stroke: "#34d399", glow: "rgba(52,211,153,0.45)" },
  amber: { stroke: "#fbbf24", glow: "rgba(251,191,36,0.45)" },
};

function kinBone(stroke, w = 1.35) {
  return { stroke, strokeWidth: w, strokeLinecap: "round", strokeLinejoin: "round", fill: "none" };
}

function KinSkeletonJoint({ cx, cy, stroke, r = 0.85 }) {
  return <circle cx={cx} cy={cy} r={r} fill={stroke} opacity="0.88" />;
}

const KIN_SKELETON_VIEWS = ["front", "posterior"];

function KinSkeletonFront({ stroke }) {
  const b = kinBone(stroke);
  const bThin = kinBone(stroke, 1.05);
  return (
    <g>
      <circle cx="16" cy="4.2" r="2.35" {...b} />
      <line x1="16" y1="6.5" x2="16" y2="8" {...b} />
      <line x1="11" y1="8.6" x2="21" y2="8.6" {...b} />
      <line x1="16" y1="8" x2="16" y2="13.6" {...b} />
      <line x1="13.2" y1="10.2" x2="18.8" y2="10.2" {...bThin} />
      <line x1="13.2" y1="11.8" x2="18.8" y2="11.8" {...bThin} />
      <line x1="11" y1="8.6" x2="9.2" y2="12.2" {...b} />
      <line x1="21" y1="8.6" x2="22.8" y2="12.2" {...b} />
      <KinSkeletonJoint cx={9.2} cy={12.2} stroke={stroke} r={0.72} />
      <KinSkeletonJoint cx={22.8} cy={12.2} stroke={stroke} r={0.72} />
      <line x1="13.2" y1="13.6" x2="18.8" y2="13.6" {...b} />
      <line x1="14" y1="13.6" x2="13.2" y2="19.8" {...b} />
      <line x1="18" y1="13.6" x2="18.8" y2="19.8" {...b} />
      <KinSkeletonJoint cx={13.2} cy={19.8} stroke={stroke} r={0.68} />
      <KinSkeletonJoint cx={18.8} cy={19.8} stroke={stroke} r={0.68} />
    </g>
  );
}

function KinSkeletonPosterior({ stroke }) {
  const b = kinBone(stroke);
  const bThin = kinBone(stroke, 1.05);
  return (
    <g>
      <circle cx="16" cy="4.2" r="2.35" {...b} />
      <line x1="16" y1="6.5" x2="16" y2="8" {...b} />
      <line x1="11" y1="8.6" x2="21" y2="8.6" {...b} />
      <line x1="16" y1="8" x2="16" y2="13.6" {...b} strokeWidth="1.55" />
      <line x1="13.2" y1="10.2" x2="18.8" y2="10.2" {...bThin} />
      <line x1="13.2" y1="11.8" x2="18.8" y2="11.8" {...bThin} />
      <line x1="16" y1="9.4" x2="10.6" y2="8.2" {...bThin} />
      <line x1="16" y1="9.4" x2="21.4" y2="8.2" {...bThin} />
      <line x1="11" y1="8.6" x2="9.2" y2="12.2" {...b} />
      <line x1="21" y1="8.6" x2="22.8" y2="12.2" {...b} />
      <KinSkeletonJoint cx={9.2} cy={12.2} stroke={stroke} r={0.72} />
      <KinSkeletonJoint cx={22.8} cy={12.2} stroke={stroke} r={0.72} />
      <line x1="13.2" y1="13.6" x2="18.8" y2="13.6" {...b} />
      <line x1="14" y1="13.6" x2="13.2" y2="19.8" {...b} />
      <line x1="18" y1="13.6" x2="18.8" y2="19.8" {...b} />
      <KinSkeletonJoint cx={13.2} cy={19.8} stroke={stroke} r={0.68} />
      <KinSkeletonJoint cx={18.8} cy={19.8} stroke={stroke} r={0.68} />
    </g>
  );
}

function KinSkeletonProfile({ stroke, facing = "right" }) {
  const b = kinBone(stroke);
  const bThin = kinBone(stroke, 1.05);
  const body = (
    <g>
      <circle cx="12.5" cy="4.2" r="2.35" {...b} />
      <line x1="12.3" y1="6.5" x2="11.8" y2="8" {...b} />
      <line x1="11.8" y1="8" x2="11.4" y2="13.6" {...b} />
      <line x1="11.6" y1="10.2" x2="15.4" y2="10.5" {...bThin} />
      <line x1="11.5" y1="11.8" x2="15.5" y2="11.3" {...bThin} />
      <line x1="11.8" y1="8.6" x2="9" y2="9.4" {...b} />
      <line x1="11.8" y1="8.8" x2="14.6" y2="8.2" {...b} />
      <line x1="11.8" y1="9" x2="15.4" y2="8.4" {...b} />
      <line x1="15.4" y1="8.4" x2="19" y2="9.2" {...b} />
      <KinSkeletonJoint cx={19} cy={9.2} stroke={stroke} r={0.72} />
      <line x1="11.6" y1="9.2" x2="8.2" y2="11.4" {...b} />
      <line x1="8.2" y1="11.4" x2="7.2" y2="13.2" {...b} />
      <KinSkeletonJoint cx={7.2} cy={13.2} stroke={stroke} r={0.68} />
      <line x1="12" y1="13.6" x2="14.4" y2="13.8" {...b} />
      <line x1="12.2" y1="13.8" x2="11.5" y2="16.4" {...b} />
      <line x1="11.5" y1="16.4" x2="12.2" y2="19.8" {...b} />
      <KinSkeletonJoint cx={12.2} cy={19.8} stroke={stroke} r={0.68} />
      <line x1="13.6" y1="13.8" x2="14.4" y2="16.4" {...b} />
      <line x1="14.4" y1="16.4" x2="15.2" y2="19.8" {...b} />
      <KinSkeletonJoint cx={15.2} cy={19.8} stroke={stroke} r={0.68} />
    </g>
  );
  if (facing === "left") {
    return <g transform="translate(32,0) scale(-1,1)">{body}</g>;
  }
  return body;
}

function KinSkeletonFigure({ view, stroke }) {
  if (view === "posterior") return <KinSkeletonPosterior stroke={stroke} />;
  if (view === "right") return <KinSkeletonProfile stroke={stroke} facing="right" />;
  if (view === "left") return <KinSkeletonProfile stroke={stroke} facing="left" />;
  return <KinSkeletonFront stroke={stroke} />;
}

function KinFilmFrame({ viewIndex, accent = "amber" }) {
  const col = KIN_FILM_ACCENT[accent] || KIN_FILM_ACCENT.amber;
  const view = KIN_SKELETON_VIEWS[viewIndex % KIN_SKELETON_VIEWS.length];
  return (
    <div className="kin-film-frame">
      <svg viewBox="0 0 32 24" aria-hidden>
        <KinSkeletonFigure view={view} stroke={col.stroke} />
      </svg>
    </div>
  );
}

function KinFilmStripLoop({ accent = "amber" }) {
  // Keep 8 frames (4? front/back pairs) so scroll distance matches the original 4-view strip speed.
  const frameCount = 8;
  const holes = Array.from({ length: 11 });

  return (
    <div className="kin-film-strip" aria-hidden>
      <div className="kin-film-strip__holes">
        {holes.map((_, i) => (
          <span key={`t-${i}`} className="kin-film-strip__hole" />
        ))}
      </div>
      <div className="kin-film-strip__body">
        <div className="kin-film-strip__track">
          {Array.from({ length: frameCount }, (_, i) => (
            <KinFilmFrame key={i} viewIndex={i} accent={accent} />
          ))}
        </div>
      </div>
      <div className="kin-film-strip__holes">
        {holes.map((_, i) => (
          <span key={`b-${i}`} className="kin-film-strip__hole" />
        ))}
      </div>
    </div>
  );
}

function InlineValidationVideo({ src, phaseLabel, autoPlay = false, onEnded, onError }) {
  const ref = useRef(null);
  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    const handleTimeUpdate = () => {
      const pct = video.duration ? (video.currentTime / video.duration) * 100 : 0;
      setProgress(pct);
    };
    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => {
      setIsPlaying(false);
      onEnded?.();
    };
    const handleError = () => {
      onError?.();
    };
    video.addEventListener("timeupdate", handleTimeUpdate);
    video.addEventListener("play", handlePlay);
    video.addEventListener("pause", handlePause);
    video.addEventListener("ended", handleEnded);
    video.addEventListener("error", handleError);
    if (autoPlay) {
      video.muted = true;
      video.play().catch(() => setIsPlaying(false));
    }
    return () => {
      video.removeEventListener("timeupdate", handleTimeUpdate);
      video.removeEventListener("play", handlePlay);
      video.removeEventListener("pause", handlePause);
      video.removeEventListener("ended", handleEnded);
      video.removeEventListener("error", handleError);
    };
  }, [src, autoPlay, onEnded, onError]);

  const togglePlay = () => {
    const video = ref.current;
    if (!video) return;
    if (video.paused) video.play();
    else video.pause();
  };

  const handleSeek = (e) => {
    const video = ref.current;
    if (!video || !video.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    video.currentTime = pct * video.duration;
  };

  const requestFullscreen = () => {
    const video = ref.current;
    if (!video) return;
    if (video.requestFullscreen) video.requestFullscreen();
    else if (video.webkitRequestFullscreen) video.webkitRequestFullscreen();
  };

  return (
    <div className="relative w-full rounded-lg bg-black overflow-hidden group">
      <video
        ref={ref}
        src={src}
        playsInline
        muted
        className="w-full rounded-lg bg-black block"
        onClick={togglePlay}
      />
      <div className="absolute inset-x-0 bottom-0 p-2 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
        <div className="flex items-center gap-2 pointer-events-auto">
          <button
            type="button"
            onClick={togglePlay}
            className="text-white/90 hover:text-white text-xs font-bold px-2 py-1 rounded bg-white/10 hover:bg-white/20"
          >
            {isPlaying ? "Pause" : "Play"}
          </button>
          <button
            type="button"
            onClick={requestFullscreen}
            className="text-white/90 hover:text-white text-xs font-bold px-2 py-1 rounded bg-white/10 hover:bg-white/20"
          >
            Full
          </button>
        </div>
        <div
          className="mt-1 h-1 bg-white/20 rounded cursor-pointer pointer-events-auto"
          onClick={handleSeek}
        >
          <div
            className="h-full bg-sky-400 rounded"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function KinAnalyzeProgressGlyph({
  pct,
  stroke,
  glow,
  sizeClass = "w-14 h-14",
  labelClass = "text-[10px]",
  indeterminate = false,
}) {
  const pctRounded = pct != null && !Number.isNaN(Number(pct)) ? Math.round(Number(pct)) : null;
  const pctClamped = pctRounded != null ? Math.max(0, Math.min(100, pctRounded)) : null;
  const ringPct = pctClamped != null ? pctClamped : 0;
  const r = 15;
  const circumference = 2 * Math.PI * r;
  const dash = (ringPct / 100) * circumference;

  return (
    <div className={`relative ${sizeClass} flex items-center justify-center shrink-0`}>
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 36 36" aria-hidden>
        <circle cx="18" cy="18" r={r} fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
        <circle cx="18" cy="18" r={r} fill="none" stroke="rgba(255,255,255,0.14)" strokeWidth="2.25" />
        <circle
          cx="18"
          cy="18"
          r={r}
          fill="none"
          stroke={stroke}
          strokeWidth="2.75"
          strokeLinecap="round"
          strokeDasharray={`${Math.max(0.5, dash)} ${circumference}`}
          className={`kin-analyze-glyph-ring transition-[stroke-dasharray] duration-700 ease-out ${
            indeterminate && pctClamped == null ? "is-indeterminate" : ""
          }`}
          style={{ filter: `drop-shadow(0 0 10px ${glow})` }}
        />
      </svg>
      <span className={`relative z-[1] ${labelClass} font-extrabold tabular-nums text-white tracking-tight`}>
        {pctClamped != null ? `${pctClamped}%` : NA}
      </span>
    </div>
  );
}

function KinPhaseAnalyzeProgressBar({ accent = "sky", pct = null, step = "Analyzing video…" }) {
  const a = KIN_PHASE_ACCENT[accent] || KIN_PHASE_ACCENT.sky;
  const film = KIN_FILM_ACCENT[accent] || KIN_FILM_ACCENT.sky;
  const pctRounded = pct != null && !Number.isNaN(Number(pct)) ? Math.round(Number(pct)) : null;
  const barPct = pctRounded != null ? Math.max(0, Math.min(100, pctRounded)) : 8;

  return (
    <div className={`w-full rounded-xl kin-analyze-panel px-3 py-2.5 flex items-center gap-2.5 border-t-[2px] ${a.ring}`}>
      <KinAnalyzeProgressGlyph
        pct={pct}
        stroke={film.stroke}
        glow={film.glow}
        sizeClass="w-10 h-10 shrink-0"
        labelClass="text-[9px]"
      />
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold text-white/90 truncate">{step}</p>
        <div className="mt-1.5 kin-analyze-track">
          <motion.div
            className={`kin-analyze-track-fill ${a.bar}`}
            initial={false}
            animate={{ width: `${Math.max(5, barPct)}%` }}
            transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
            style={{ boxShadow: `0 0 10px ${film.glow}` }}
          />
        </div>
        <p className="text-[8px] text-white/35 mt-1">Server processing — keep tab open</p>
      </div>
    </div>
  );
}

const kinPhaseCardCls = (c, status, hasResult) => {
  const a = KIN_PHASE_ACCENT[c] || KIN_PHASE_ACCENT.amber;
  const base = `relative flex flex-col rounded-2xl border border-t-[3px] bg-gradient-to-b ${a.top} to-white/[0.02] min-h-[240px] transition-all duration-300 overflow-hidden`;
  if (status === "analyzing") return `${base} border-white/[0.12] ring-1 ring-white/[0.06]`;
  if (hasResult) return `${base} border-emerald-400/35 ring-1 ring-emerald-400/20`;
  return `${base} border-white/[0.07] hover:border-white/12`;
};

const kinUploadZoneCls = (c, hasFile) => {
  const base = "group relative flex flex-col items-center justify-center gap-1.5 rounded-2xl border border-dashed px-3 py-5 cursor-pointer transition-all duration-200";
  if (hasFile) {
    if (c === "sky") return `${base} border-sky-400/30 bg-sky-400/[0.06] hover:bg-sky-400/10`;
    if (c === "emerald") return `${base} border-emerald-400/30 bg-emerald-400/[0.06] hover:bg-emerald-400/10`;
    return `${base} border-amber-400/30 bg-amber-400/[0.06] hover:bg-amber-400/10`;
  }
  return `${base} border-white/10 bg-white/[0.02] hover:border-white/18 hover:bg-white/[0.04]`;
};

const kinShortFileName = (name, max = 22) => {
  if (!name) return "";
  if (name.length <= max) return name;
  const ext = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";
  const stem = ext ? name.slice(0, name.length - ext.length) : name;
  const keep = Math.max(6, max - ext.length - 1);
  return `${stem.slice(0, keep)}…${ext}`;
};

const armSideLabel = (side) => (side === "left" ? "Left" : side === "right" ? "Right" : "\u2014");

const analyzedArmForPhase = (kinematicsResults, phaseKey) => {
  const s = (kinematicsResults[phaseKey]?.side_analyzed || kinematicsResults[phaseKey]?.side || "").toString().toLowerCase();
  return s === "left" || s === "right" ? s : null;
};

const KinOverlayErrorBoundary = class extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(err, info) {
    console.error("Validation overlay player:", err, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="aspect-video rounded-lg bg-black/50 flex flex-col items-center justify-center text-center p-3 gap-2">
          <p className="text-[11px] text-rose-200/90 max-w-[90%]">Validation preview could not render (memory or browser limit).</p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="text-[10px] px-2 py-1 rounded-md bg-white/10 hover:bg-white/20 text-white/80 transition-colors"
          >
            Retry preview
          </button>
        </div>
      );
    }
    return this.props.children;
  }
};

const KinSection = React.memo(function KinSection({ data, demographics, onChange, showToast, sessionKey }) {
  const [kinematicsResults, setKinematicsResults] = useState(() => {
    try {
      const ls = JSON.parse(localStorage.getItem(KIN_LS_KEY)) || {};
      const fd = data?.analysisResults || {};
      // Current form/session data takes precedence over stale localStorage.
      const merged = { ...ls, ...fd };
      delete merged.during;
      return merged;
    } catch {
      return data?.analysisResults || {};
    }
  });
  const [settings, setSettings] = useState({
    cutoffFrequency: 4.0,
    filterOrder: 4,
  });
  const [clinicalMovementTask, setClinicalMovementTask] = useState(() => {
    try {
      const s = localStorage.getItem("neuro_clinical_movement_task");
      if (s && CLINICAL_MOVEMENT_TASKS.some((t) => t.id === s)) return s;
    } catch { /* ignore */ }
    return "study_reach_grasp";
  });
  const [kinematicDomain, setKinematicDomain] = useState(() => clinicalTaskDomain(
    (() => {
      try {
        const s = localStorage.getItem("neuro_clinical_movement_task");
        if (s && CLINICAL_MOVEMENT_TASKS.some((t) => t.id === s)) return s;
      } catch { /* ignore */ }
      return "study_reach_grasp";
    })()
  ));
  useEffect(() => {
    try {
      localStorage.setItem("neuro_clinical_movement_task", clinicalMovementTask);
    } catch { /* ignore */ }
  }, [clinicalMovementTask]);
  useEffect(() => {
    const domain = clinicalTaskDomain(clinicalMovementTask);
    if (domain !== kinematicDomain) setKinematicDomain(domain);
  }, [clinicalMovementTask]); // eslint-disable-line react-hooks/exhaustive-deps
  const domainTasks = clinicalTasksForDomain(kinematicDomain);
  const selectKinematicDomain = (domain) => {
    const next = String(domain || "ue").toLowerCase() === "le" ? "le" : "ue";
    setKinematicDomain(next);
    const list = clinicalTasksForDomain(next);
    if (!list.some((t) => t.id === clinicalMovementTask)) {
      setClinicalMovementTask(list[0]?.id || (next === "le" ? "sts_stand" : "study_reach_grasp"));
    }
  };
  const [expandedResults, setExpandedResults] = useState(() => {
    try { return JSON.parse(localStorage.getItem(KIN_LS_EXP_KEY)) || {}; } catch { return {}; }
  });
  const [kinResultsTab, setKinResultsTab] = useState("compare");
  const [showAllKinMetrics, setShowAllKinMetrics] = useState(false);
  const [mediaPreview, setMediaPreview] = useState(null);
  const [analysisStatus, setAnalysisStatus] = useState({});
  const [analysisProgress, setAnalysisProgress] = useState({});
  const [showResultsTable, setShowResultsTable] = useState(false);
  const [videoBlobs, setVideoBlobs] = useState({});
  const [videoLoading, setVideoLoading] = useState({});
  const [videoAttempts, setVideoAttempts] = useState({});
  const [overlayData, setOverlayData] = useState({});
  const [overlayMountReady, setOverlayMountReady] = useState({});
  const [originalVideoBlobs, setOriginalVideoBlobs] = useState({});
  const [driveBakeDone, setDriveBakeDone] = useState({});
  /** Phases whose loaded clip does not match the overlay analysis (baked composite). */
  const [overlaySourceBad, setOverlaySourceBad] = useState({});
  const overlaySourceRetryRef = useRef({});
  const driveBakeToastRef = useRef({});
  const videoBlobsRef = useRef(videoBlobs);
  const videoLoadingRef = useRef(videoLoading);
  const originalVideoBlobsRef = useRef(originalVideoBlobs);
  useEffect(() => { videoBlobsRef.current = videoBlobs; }, [videoBlobs]);
  useEffect(() => { videoLoadingRef.current = videoLoading; }, [videoLoading]);
  useEffect(() => { originalVideoBlobsRef.current = originalVideoBlobs; }, [originalVideoBlobs]);

  const patientCacheKey = useMemo(
    () => patientDriveKeyFromDemographics(demographics, sessionKey),
    [demographics, sessionKey],
  );

  const applyValidationCacheToState = useCallback((phase, cached) => {
    if (!cached) return false;
    let applied = false;
    if (cached.overlay?.frames?.length) {
      startTransition(() => {
        setOverlayData((prev) => (
          shouldHydrateOverlayIntoState(prev[phase], cached.overlay)
            ? { ...prev, [phase]: cached.overlay }
            : prev
        ));
      });
      applied = true;
    }
    if (cached.originalVideoBlob instanceof Blob && cached.originalVideoBlob.size > 0) {
      setOriginalVideoBlobs((prev) => {
        if (!shouldHydrateMediaBlobIntoState(prev[phase], cached.originalVideoBlob)) return prev;
        const objectUrl = URL.createObjectURL(cached.originalVideoBlob);
        const next = { ...prev, [phase]: objectUrl };
        originalVideoBlobsRef.current = next;
        return next;
      });
      applied = true;
    }
    if (cached.unifiedVideoBlob instanceof Blob && cached.unifiedVideoBlob.size > 0) {
      setVideoBlobs((prev) => {
        if (!shouldHydrateMediaBlobIntoState(prev[phase], cached.unifiedVideoBlob)) return prev;
        const objectUrl = URL.createObjectURL(cached.unifiedVideoBlob);
        const next = { ...prev, [phase]: objectUrl };
        videoBlobsRef.current = next;
        return next;
      });
      setDriveBakeDone((prev) => ({
        ...prev,
        [phase]: Boolean(cached.compositedOverlay) && Number(cached.compositedOverlayQuality || 0) >= 2,
      }));
      applied = true;
    }
    return applied;
  }, []);

  const persistValidationPhase = useCallback(async (phase, partial = {}) => {
    if (!patientCacheKey) return;
    try {
      const existing = await loadValidationSessionArtifact(patientCacheKey, phase);
      const snap = partial.kinematicsSnapshot ?? kinematicsResults[phase];
      const record = {
        patientKey: patientCacheKey,
        phase,
        csvFilename: partial.csvFilename ?? existing?.csvFilename ?? snap?.csv_filename,
        videoFilename: partial.videoFilename ?? existing?.videoFilename ?? snap?.video_filename,
        unifiedVideoFilename:
          partial.unifiedVideoFilename ?? existing?.unifiedVideoFilename ?? snap?.unified_validation_video,
        overlay: partial.overlay ?? existing?.overlay,
        originalVideoBlob: partial.originalVideoBlob ?? existing?.originalVideoBlob,
        unifiedVideoBlob: partial.unifiedVideoBlob ?? existing?.unifiedVideoBlob,
        compositedOverlay:
          partial.compositedOverlay != null
            ? Boolean(partial.compositedOverlay)
            : Boolean(existing?.compositedOverlay),
        compositedOverlayQuality:
          partial.compositedOverlayQuality != null
            ? Number(partial.compositedOverlayQuality)
            : Number(existing?.compositedOverlayQuality || 0),
        kinematicsSnapshot: snap ? stripKinPhaseForSync(snap) : existing?.kinematicsSnapshot,
        savedAt: Date.now(),
      };
      await saveValidationSessionArtifact(record);
      backupValidationArtifactsToDrive(patientCacheKey, phase, record).catch((err) => {
        console.warn("Drive validation backup failed:", err);
      });
    } catch (err) {
      console.warn("persistValidationPhase failed:", err);
    }
  }, [patientCacheKey, kinematicsResults]);

  const hydrateValidationFromCloud = useCallback(async (phase, needs = {}) => {
    if (!patientCacheKey) return null;
    const phaseResult = kinematicsResults[phase];
    const existing = await loadValidationSessionArtifact(patientCacheKey, phase);
    const existingValid = validationCacheMatchesResult(existing, phaseResult, { relaxCsvMatch: true })
      ? existing
      : null;
    const wantOverlay = needs.overlay !== false && !existingValid?.overlay?.frames?.length;
    const wantOriginal = needs.original !== false && !(existingValid?.originalVideoBlob?.size > 0);
    const wantUnified = needs.unified !== false && !(existingValid?.unifiedVideoBlob?.size > 0);
    const wantKinematics = needs.kinematics === true && !existingValid?.kinematicsSnapshot;
    if (!wantOverlay && !wantOriginal && !wantUnified && !wantKinematics) {
      if (existingValid) applyValidationCacheToState(phase, existingValid);
      return existingValid;
    }
    const fromDrive = await restoreValidationArtifactsFromDrive(patientCacheKey, phase, {
      overlay: wantOverlay,
      original: wantOriginal,
      unified: wantUnified,
      kinematics: wantKinematics,
    });
    if (!fromDrive && !existingValid) return null;
    const merged = {
      ...(existingValid || {}),
      ...fromDrive,
      patientKey: patientCacheKey,
      phase,
      csvFilename: phaseResult?.csv_filename ?? existingValid?.csvFilename,
      videoFilename: phaseResult?.video_filename ?? existingValid?.videoFilename,
      unifiedVideoFilename:
        phaseResult?.unified_validation_video ?? existingValid?.unifiedVideoFilename,
      savedAt: Date.now(),
    };
    const matched = validationCacheMatchesResult(merged, phaseResult, { relaxCsvMatch: true });
    if (!matched && !(needs.kinematics && merged.kinematicsSnapshot)) return existingValid;
    await saveValidationSessionArtifact(merged);
    applyValidationCacheToState(phase, merged);
    return merged;
  }, [patientCacheKey, kinematicsResults, applyValidationCacheToState]);

  const abortRef = useRef({});
  const overlayVideoSyncedRef = useRef({});

  useEffect(() => {
    try {
      localStorage.setItem(KIN_LS_KEY, JSON.stringify(stripKinResultsForStorage(kinematicsResults)));
    } catch (e) {
      console.warn("Could not persist kinematics to localStorage (quota or size):", e);
    }
  }, [kinematicsResults]);

  // Revoke object URLs for cached validation videos on unmount
  useEffect(() => {
    return () => {
      Object.values(videoBlobsRef.current).forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  // Revoke object URLs for cached original videos on unmount
  useEffect(() => {
    return () => {
      Object.values(originalVideoBlobsRef.current).forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  // Reload kinematics when switching patient session
  useEffect(() => {
    if (!sessionKey) return;
    const fromFd = data?.analysisResults;
    if (fromFd && typeof fromFd === "object" && Object.keys(fromFd).length > 0) {
      const cleaned = { ...fromFd };
      delete cleaned.during;
      setKinematicsResults(cleaned);
      localStorage.setItem(KIN_LS_KEY, JSON.stringify(cleaned));
    } else {
      setKinematicsResults({});
      localStorage.removeItem(KIN_LS_KEY);
    }
  }, [sessionKey]);

  useEffect(() => {
    localStorage.setItem(KIN_LS_EXP_KEY, JSON.stringify(expandedResults));
  }, [expandedResults]);

  // Import parsed kinematics data (from PDF/CSV) into kinematicsResults
  useEffect(() => {
    if (!data || Object.keys(kinematicsResults).length > 0) return;
    const kinMap = {
      nvp: "nvp",
      straightness: "straightness",
      pauseTimeSec: "pause_time_sec",
      numberOfStops: "number_of_stops",
      trunkRatio: "trunk_ratio",
      elbowAngleMeanDeg: "elbow_angle_mean_deg",
      movementTimeSec: "movement_time_sec",
      peakElbowAngVelDegS: "peak_elbow_ang_vel_deg_s",
      shoulderFlexionMeanDeg: "shoulder_flexion_mean_deg",
      peakShoulderFlexionVelDegS: "peak_shoulder_flexion_vel_deg_s",
      duration: "movement_time_sec",
    };
    const converted = {};
    const phaseMap = { pre: "pre", post: "post", healthy: "baseline" };
    for (const [src, dst] of Object.entries(phaseMap)) {
      const srcData = data[src];
      if (!srcData || Object.keys(srcData).length === 0) continue;
      const phaseObj = {};
      for (const [camel, snake] of Object.entries(kinMap)) {
        if (srcData[camel]) phaseObj[snake] = srcData[camel];
      }
      if (Object.keys(phaseObj).length > 0) converted[dst] = phaseObj;
    }
    if (Object.keys(converted).length > 0) setKinematicsResults(converted);
  }, [data]);

  const phases = [
    { k:"pre", l:"Pre", c:"sky" },
    { k:"post", l:"Post", c:"emerald" },
    { k:"baseline", l:"Healthy side", c:"amber" },
  ];

  const vidKey = (phase) => `video_${phase}`;
  const resultKey = (phase) => `result_${phase}`;
  const statusKey = (phase) => `status_${phase}`;

  const handleFile = (phase, file) => {
    if (!file) return;
    const isVideo = !file.name.toLowerCase().endsWith(".csv");
    let upd;
    if (isVideo) {
      const lower = file.name.toLowerCase();
      const browserNativeVideo = lower.endsWith(".mp4") || lower.endsWith(".webm");
      let videoUrl;
      if (browserNativeVideo) {
        videoUrl = URL.createObjectURL(file);
        setOriginalVideoBlobs((prev) => {
          if (prev[phase]) URL.revokeObjectURL(prev[phase]);
          const next = { ...prev, [phase]: videoUrl };
          originalVideoBlobsRef.current = next;
          return next;
        });
      } else {
        setOriginalVideoBlobs((prev) => {
          if (prev[phase]) URL.revokeObjectURL(prev[phase]);
          const next = { ...prev };
          delete next[phase];
          originalVideoBlobsRef.current = next;
          return next;
        });
        setOverlayMountReady((prev) => ({ ...prev, [phase]: false }));
      }
      upd = {
        ...data,
        [vidKey(phase)]: file.name,
        [`${vidKey(phase)}_file`]: file,
        [`${vidKey(phase)}_url`]: videoUrl,
        [`${vidKey(phase)}_isVideo`]: true,
      };
    } else {
      upd = { ...data, [vidKey(phase)]: file.name, [`${vidKey(phase)}_file`]: file, [`${vidKey(phase)}_isVideo`]: false };
    }
    // Clear old result when new video selected
    if (kinematicsResults[phase]) {
      delete upd[resultKey(phase)];
      const nextResults = { ...kinematicsResults };
      delete nextResults[phase];
      setKinematicsResults(nextResults);
      upd.analysisResults = nextResults;
    }
    upd[statusKey(phase)] = "uploaded";
    onChange(upd);
    showToast(`\u2713 File uploaded for ${phase}`);
  };

  const clearPhase = (phase) => {
    const status = data[statusKey(phase)];
    if (abortRef.current[phase]) {
      abortRef.current[phase].abort();
      delete abortRef.current[phase];
    }
    if (status === "analyzing") {
      onChange({ ...data, [statusKey(phase)]: "uploaded" });
      showToast(`Analysis cancelled for ${phase}`);
      return;
    }
    const upd = { ...data };
    delete upd[vidKey(phase)];
    delete upd[`${vidKey(phase)}_file`];
    delete upd[`${vidKey(phase)}_url`];
    delete upd[`${vidKey(phase)}_isVideo`];
    delete upd[resultKey(phase)];
    upd[statusKey(phase)] = "idle";
    const nextResults = { ...kinematicsResults };
    delete nextResults[phase];
    setKinematicsResults(nextResults);
    setOverlayData((prev) => { const n = { ...prev }; delete n[phase]; return n; });
    setOriginalVideoBlobs((prev) => {
      if (prev[phase]) URL.revokeObjectURL(prev[phase]);
      const n = { ...prev }; delete n[phase]; return n;
    });
    onChange({ ...upd, analysisResults: nextResults });
    setExpandedResults((prev) => { const n = { ...prev }; delete n[phase]; return n; });
    showToast(`Cleared ${phase}`);
  };

  const clearAllKin = () => {
    phases.forEach((ph) => {
      if (abortRef.current[ph.k]) {
        abortRef.current[ph.k].abort();
        delete abortRef.current[ph.k];
      }
    });
    const upd = { ...data };
    phases.forEach((ph) => {
      delete upd[vidKey(ph.k)];
      delete upd[`${vidKey(ph.k)}_file`];
      delete upd[`${vidKey(ph.k)}_url`];
      delete upd[`${vidKey(ph.k)}_isVideo`];
      delete upd[resultKey(ph.k)];
      upd[statusKey(ph.k)] = "idle";
    });
    upd.analysisResults = {};
    setKinematicsResults({});
    setExpandedResults({});
    setOverlayData({});
    setOverlayMountReady({});
    setOriginalVideoBlobs((prev) => {
      Object.values(prev).forEach((url) => URL.revokeObjectURL(url));
      return {};
    });
    setKinResultsTab("compare");
    localStorage.removeItem(KIN_LS_KEY);
    localStorage.removeItem(KIN_LS_EXP_KEY);
    onChange(upd);
    showToast("All kinematics cleared");
  };

  const fetchOverlayData = useCallback(async (phase, csvFilename, { syncResults = true } = {}) => {
    if (!csvFilename) return null;
    const phaseResult = kinematicsResults[phase];

    try {
      const res = await fetch(`${API_BASE}/overlay-data/${encodeURIComponent(csvFilename)}?v=${Date.now()}`);
      if (!res.ok) throw new Error(`Failed to load overlay data (${res.status})`);
      const overlay = await res.json();
      console.log("overlay-debug", csvFilename, {
        phase,
        ...summarizeOverlayClock(overlay),
        table_surface_y: overlay.table_surface_y,
        table_surface_fallback: overlay.table_surface_fallback,
        table_under_shoulder: overlay.table_under_shoulder,
        shoulder_palm_anchor: overlay.shoulder_palm_anchor,
        debug_video_path: overlay.debug_video_path,
        debug_table_edge_found: overlay.debug_table_edge_found,
        coord_transform: overlay.coord_transform,
        hl_coord_transform: overlay.hl_coord_transform,
        overlay_version: overlay.overlay_version,
        version: overlay.version,
      });
      if (overlay.error) throw new Error(overlay.error);
      startTransition(() => {
        setOverlayData((prev) => ({ ...prev, [phase]: overlay }));
      });
      const metrics = resolveOverlayMetrics(overlay);
      if (syncResults) {
        setKinematicsResults((prev) => {
          const existing = prev[phase] || {};
          const next = {
            ...prev,
            [phase]: {
              ...existing,
              overlay_metrics: metrics,
              validation_summary: metrics,
            },
          };
          onChange({ ...data, analysisResults: stripKinResultsForStorage(next) });
          return next;
        });
      }
      setAnalysisProgress((prev) => ({ ...prev, [phase]: { pct: 100, step: "Done" } }));
      persistValidationPhase(phase, { csvFilename, overlay, kinematicsSnapshot: phaseResult });
      return { overlay, metrics };
    } catch (err) {
      let cachedOverlay = null;
      if (patientCacheKey) {
        const cached = await loadValidationSessionArtifact(patientCacheKey, phase);
        if (validationCacheMatchesResult(cached, { csv_filename: csvFilename }, { relaxCsvMatch: true }) && cached?.overlay?.frames?.length) {
          cachedOverlay = cached.overlay;
          applyValidationCacheToState(phase, { overlay: cached.overlay });
        } else {
          const cloud = await hydrateValidationFromCloud(phase, { overlay: true, original: false, unified: false });
          if (validationCacheMatchesResult(cloud, { csv_filename: csvFilename }, { relaxCsvMatch: true }) && cloud?.overlay?.frames?.length) {
            cachedOverlay = cloud.overlay;
          }
        }
      }
      if (cachedOverlay?.frames?.length) {
        const metrics = resolveOverlayMetrics(cachedOverlay);
        if (syncResults) {
          setKinematicsResults((prev) => {
            const existing = prev[phase] || {};
            const next = {
              ...prev,
              [phase]: {
                ...existing,
                overlay_metrics: metrics,
                validation_summary: metrics,
              },
            };
            onChange({ ...data, analysisResults: stripKinResultsForStorage(next) });
            return next;
          });
        }
        setAnalysisProgress((prev) => ({ ...prev, [phase]: { pct: 100, step: "Restored from session cache" } }));
        return { overlay: cachedOverlay, metrics };
      }
      console.error(`Overlay data error for ${phase}:`, err);
      showToast(`Overlay data failed for ${phase}`, "error");
      return null;
    }
  }, [showToast, onChange, data, kinematicsResults, patientCacheKey, applyValidationCacheToState, persistValidationPhase, hydrateValidationFromCloud]);

  const fetchOverlayDataWithRetry = useCallback(async (phase, csvFilename, opts = {}, maxAttempts = 5) => {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const prefetched = await fetchOverlayData(phase, csvFilename, opts);
      if (prefetched?.overlay?.frames?.length) return prefetched;
      if (attempt < maxAttempts - 1) {
        await new Promise((resolve) => setTimeout(resolve, 350 * (attempt + 1)));
      }
    }
    return null;
  }, [fetchOverlayData]);

  const loadOriginalVideoBlob = useCallback(async (phase, filename, options = {}) => {
    const { force = false } = options;
    if (!filename) return;
    if (!force && originalVideoBlobsRef.current[phase]) return;
    if (force) {
      setOriginalVideoBlobs((prev) => {
        if (prev[phase]) URL.revokeObjectURL(prev[phase]);
        const next = { ...prev };
        delete next[phase];
        originalVideoBlobsRef.current = next;
        return next;
      });
      setOverlayMountReady((prev) => ({ ...prev, [phase]: false }));
    }

    const phaseResult = kinematicsResults[phase];

    const applyCachedOriginal = async () => {
      if (!patientCacheKey) return false;
      const cached = await loadValidationSessionArtifact(patientCacheKey, phase);
      if (!validationCacheMatchesResult(cached, phaseResult, { relaxCsvMatch: true })) return false;
      const blob = cached?.originalVideoBlob;
      if (!(blob instanceof Blob) || blob.size <= 0) return false;
      applyValidationCacheToState(phase, { originalVideoBlob: blob });
      return true;
    };

    try {
      if (await applyCachedOriginal()) return;

      const candidates = [];
      const add = (name) => {
        if (name && !candidates.includes(name)) candidates.push(name);
      };
      add(filename);
      if (filename && !filename.includes("_rotated")) {
        const m = filename.match(/^(.+)(\.[a-zA-Z0-9]+)$/);
        if (m) add(`${m[1]}_rotated${m[2]}`);
      }
      let loaded = null;
      let loadedName = null;
      for (const name of candidates) {
        const url = `${API_BASE}/video/${encodeURIComponent(name)}`;
        const res = await fetch(url);
        if (res.status === 404) continue;
        if (!res.ok) throw new Error(`Failed (${res.status})`);
        const blob = await res.blob();
        if (!blob.size) continue;
        loaded = blob;
        loadedName = name;
        break;
      }
      if (!loaded) {
        if (await applyCachedOriginal()) return;
        const cloud = await hydrateValidationFromCloud(phase, { overlay: false, original: true, unified: false });
        if (validationCacheMatchesResult(cloud, phaseResult, { relaxCsvMatch: true }) && cloud?.originalVideoBlob?.size) return;
        showToast("Original video expired on server — please re-upload", "error");
        return;
      }
      const objectUrl = URL.createObjectURL(loaded);
      setOriginalVideoBlobs((prev) => {
        if (prev[phase]) URL.revokeObjectURL(prev[phase]);
        const next = { ...prev, [phase]: objectUrl };
        originalVideoBlobsRef.current = next;
        return next;
      });
      persistValidationPhase(phase, {
        csvFilename: phaseResult?.csv_filename,
        videoFilename: loadedName || filename,
        originalVideoBlob: loaded,
        kinematicsSnapshot: phaseResult,
      });
    } catch (err) {
      console.error(`Failed to cache original video for ${phase}:`, err);
      if (await applyCachedOriginal()) return;
      const cloud = await hydrateValidationFromCloud(phase, { overlay: false, original: true, unified: false });
      if (validationCacheMatchesResult(cloud, phaseResult, { relaxCsvMatch: true }) && cloud?.originalVideoBlob?.size) return;
      showToast("Original video could not be loaded for overlay", "error");
    }
  }, [showToast, patientCacheKey, kinematicsResults, applyValidationCacheToState, persistValidationPhase, hydrateValidationFromCloud]);

  const ensureOriginalVideoBlob = useCallback(async (phase, file, serverFilename) => {
    const fileLower = file?.name?.toLowerCase() || "";
    const fileIsCsv = fileLower.endsWith(".csv");
    const browserNative = fileLower.endsWith(".mp4") || fileLower.endsWith(".webm");

    // Always play the same file the server analyzed (incl. *_rotated.mp4). Local iPhone
    // blobs can disagree with Safari rotation vs OpenCV overlay coordinates.
    if (serverFilename) {
      await loadOriginalVideoBlob(phase, serverFilename, { force: true });
      if (originalVideoBlobsRef.current[phase]) return true;
    }
    if (originalVideoBlobsRef.current[phase]) return true;
    if (file && !fileIsCsv && browserNative) {
      const objectUrl = URL.createObjectURL(file);
      setOriginalVideoBlobs((prev) => {
        if (prev[phase]) {
          URL.revokeObjectURL(objectUrl);
          return prev;
        }
        const next = { ...prev, [phase]: objectUrl };
        originalVideoBlobsRef.current = next;
        return next;
      });
      return true;
    }
    if (serverFilename) {
      await loadOriginalVideoBlob(phase, serverFilename);
      return Boolean(originalVideoBlobsRef.current[phase]);
    }
    return false;
  }, [loadOriginalVideoBlob]);

  // Auto-restore program truth (overlay + original + kinematics) and Drive view-copy from cloud/IDB.
  useEffect(() => {
    if (!patientCacheKey) return;
    let cancelled = false;
    (async () => {
      for (const ph of phases) {
        if (cancelled) break;
        const result = kinematicsResults[ph.k];
        if (!result) continue;
        const hasOverlay = Boolean(overlayData[ph.k]?.frames?.length);
        const hasOriginal = Boolean(originalVideoBlobsRef.current[ph.k]);
        const hasUnified = Boolean(videoBlobsRef.current[ph.k]);
        if (hasOverlay && hasOriginal && hasUnified) continue;
        const merged = await hydrateValidationFromCloud(ph.k, {
          overlay: !hasOverlay,
          original: !hasOriginal,
          unified: !hasUnified,
          kinematics: !result.csv_filename,
        });
        if (cancelled) break;
        if (merged?.kinematicsSnapshot && !result.csv_filename) {
          setKinematicsResults((prev) => ({
            ...prev,
            [ph.k]: { ...(prev[ph.k] || {}), ...merged.kinematicsSnapshot },
          }));
        }
      }
    })();
    return () => { cancelled = true; };
  }, [patientCacheKey, kinematicsResults, overlayData, hydrateValidationFromCloud]);

  useEffect(() => {
    if (!patientCacheKey) return undefined;
    const onRecall = () => {
      phases.forEach((ph) => {
        hydrateValidationFromCloud(ph.k, {
          overlay: true,
          original: true,
          unified: true,
          kinematics: true,
        }).catch(() => {});
      });
    };
    window.addEventListener(DRIVE_RECALL_EVENT, onRecall);
    return () => window.removeEventListener(DRIVE_RECALL_EVENT, onRecall);
  }, [patientCacheKey, hydrateValidationFromCloud]);

  // Load original video blobs for analyzed phases that don't have one yet.
  // This handles persisted sessions where the object URL was lost on reload.
  useEffect(() => {
    phases.forEach((ph) => {
      const result = kinematicsResults[ph.k];
      if (!result || originalVideoBlobsRef.current[ph.k]) return;
      const filename = result.video_filename;
      if (!filename) return;
      // Only load if it is a video file (not CSV-only analysis).
      if (filename.toLowerCase().endsWith(".csv")) return;
      loadOriginalVideoBlob(ph.k, filename);
    });
  }, [kinematicsResults, loadOriginalVideoBlob]);

  useEffect(() => {
    phases.forEach((ph) => {
      const name = overlayData[ph.k]?.overlay_video_filename;
      if (!name) return;
      const prev = overlayVideoSyncedRef.current[ph.k];
      if (prev === name && originalVideoBlobsRef.current[ph.k]) return;
      overlayVideoSyncedRef.current[ph.k] = name;
      loadOriginalVideoBlob(ph.k, name, { force: Boolean(prev && prev !== name) });
    });
  }, [overlayData, loadOriginalVideoBlob]);

  const overlayMountFingerprint = phases
    .map((ph) => `${ph.k}:${overlayData[ph.k] ? 1 : 0}${originalVideoBlobs[ph.k] ? 1 : 0}${overlayMountReady[ph.k] ? 1 : 0}`)
    .join("|");

  useEffect(() => {
    const next = phases.find((ph) => overlayData[ph.k] && originalVideoBlobs[ph.k] && !overlayMountReady[ph.k]);
    if (!next) return undefined;
    const already = phases.filter((ph) => overlayMountReady[ph.k]).length;
    const delay = overlayPlayerMountDelayMs(already);
    const t = window.setTimeout(() => {
      setOverlayMountReady((prev) => (prev[next.k] ? prev : { ...prev, [next.k]: true }));
    }, delay);
    return () => window.clearTimeout(t);
    // Ready flags only — overlay object identity churn from Drive recall must not reset the stagger.
  }, [overlayMountFingerprint]); // eslint-disable-line react-hooks/exhaustive-deps

  // The player loaded a clip that does not match the analysis (usually a cached baked
  // composite). Pull the analyzed original straight from the server once; if that fails,
  // play the baked video plainly instead of drawing chalk on the wrong frames.
  const handleOverlaySourceMismatch = useCallback(async (phase) => {
    const tries = overlaySourceRetryRef.current[phase] || 0;
    const name = overlayData[phase]?.overlay_video_filename
      || kinematicsResults[phase]?.video_filename;
    const giveUp = () => {
      setOverlaySourceBad((prev) => (prev[phase] ? prev : { ...prev, [phase]: true }));
      showToast("Playing video without overlay — clip did not match the analysis", "warning");
    };
    if (tries >= 1 || !name) {
      giveUp();
      return;
    }
    overlaySourceRetryRef.current[phase] = tries + 1;
    // Fetch before swapping: a failed refetch must not drop the clip we already play.
    let fresh = null;
    try {
      const res = await fetch(`${API_BASE}/video/${encodeURIComponent(name)}`);
      if (res.ok) {
        const blob = await res.blob();
        const kind = String(blob.type || "").toLowerCase();
        if (blob.size > 0 && !kind.startsWith("text/") && kind !== "application/json") {
          fresh = blob;
        }
      }
    } catch (err) {
      console.warn("overlay source refetch failed:", err);
    }
    if (!fresh) {
      giveUp();
      return;
    }
    const objectUrl = URL.createObjectURL(fresh);
    setOriginalVideoBlobs((prev) => {
      if (prev[phase]) URL.revokeObjectURL(prev[phase]);
      const next = { ...prev, [phase]: objectUrl };
      originalVideoBlobsRef.current = next;
      return next;
    });
    persistValidationPhase(phase, {
      csvFilename: kinematicsResults[phase]?.csv_filename,
      videoFilename: name,
      originalVideoBlob: fresh,
      kinematicsSnapshot: kinematicsResults[phase],
    });
  }, [overlayData, kinematicsResults, persistValidationPhase, showToast]);

  // A freshly loaded clip gets a new verdict from the player.
  useEffect(() => {
    phases.forEach((ph) => {
      if (!originalVideoBlobs[ph.k]) return;
      setOverlaySourceBad((prev) => {
        if (!prev[ph.k]) return prev;
        const next = { ...prev };
        delete next[ph.k];
        return next;
      });
    });
  }, [originalVideoBlobs]);

  const analyzeVideo = async (phase) => {
    const file = data[`${vidKey(phase)}_file`];
    if (!file) {
      showToast("Please select a file first", "error");
      return;
    }

    const controller = new AbortController();
    abortRef.current[phase] = controller;
    setKinAnalyzeActive(true);
    setOverlayMountReady((prev) => ({ ...prev, [phase]: false }));
    setDriveBakeDone((prev) => ({ ...prev, [phase]: false }));
    setOverlaySourceBad((prev) => {
      if (!prev[phase]) return prev;
      const next = { ...prev };
      delete next[phase];
      return next;
    });
    overlaySourceRetryRef.current[phase] = 0;
    driveBakeToastRef.current[phase] = false;
    driveBakeToastRef.current[`${phase}-nopatient`] = false;
    setOverlayData((prev) => {
      if (!prev[phase]) return prev;
      const next = { ...prev };
      delete next[phase];
      return next;
    });
    onChange({ ...data, [statusKey(phase)]: "analyzing" });
    setAnalysisProgress((prev) => ({ ...prev, [phase]: { pct: 5, step: "Uploading…" } }));
    try {
      sessionStorage.setItem(
        "neuro_kin_analyze_ui",
        JSON.stringify({ phase, pct: 5, step: "Uploading…" }),
      );
    } catch { /* ignore */ }

    const isCsv = file.name.endsWith(".csv");

    const demoSide = demographics?.side;
    const strokeSideHint =
      demoSide === "1" || demoSide === 1 ? "left"
      : demoSide === "2" || demoSide === 2 ? "right"
      : "auto";

    try {
      const fd = new FormData();
      fd.append(isCsv ? "csv" : "video", file);
      fd.append("phase", phase);
      fd.append("trial_role", clinicTrialRoleFromPhase(phase));
      // Use demographics paretic side when set; otherwise auto-detect from kinematics.
      fd.append("stroke_side", strokeSideHint);
      fd.append("affected_side", strokeSideHint);
      fd.append("cutoff_frequency", settings.cutoffFrequency.toString());
      fd.append("filter_order", settings.filterOrder.toString());
      fd.append("clinical_task", clinicalMovementTask);
      fd.append("patient_height_cm", demographics?.height || "auto");
      fd.append("save_intermediates", "false");
      const sexRaw = (demographics?.sex || demographics?.gender || "unknown").toString().toLowerCase();
      fd.append("patient_sex", sexRaw.includes("female") || sexRaw === "2" ? "female" : sexRaw.includes("male") || sexRaw === "1" ? "male" : "unknown");
      if (!isCsv) {
        fd.append("arm_type", "paretic");
        fd.append("trial_count", "1");
        fd.append("best_trial_metric", "nvp_reach");
        fd.append("clinical_task", clinicalMovementTask);
      }

      const endpoint = isCsv ? "/analyze-csv" : "/analyze";
      const res = await fetch(`${API_BASE}${endpoint}`, { method: "POST", body: fd, signal: controller.signal });
      if (!res.ok) {
        let detail = `Server error ${res.status}`;
        try { const e = await res.json(); if (e.error || e.detail) detail += `: ${e.error || e.detail}`; } catch (_) {}
        throw new Error(detail);
      }

      let result = await res.json();

      if (result.job_id && result.async && !isCsv) {
        const jobId = result.job_id;
        const pollMs = ANALYZE_POLL_MS;
        let attempts = 0;
        for (;;) {
          attempts += 1;
          if (analyzePollExceeded(attempts)) {
            throw new Error("Analysis is taking too long. Please retry.");
          }
          if (controller.signal.aborted) {
            const abortErr = new Error("Analysis cancelled");
            abortErr.name = "AbortError";
            throw abortErr;
          }
          const pr = await fetch(`${API_BASE}/analyze-progress/${encodeURIComponent(jobId)}`, {
            signal: controller.signal,
          });
          if (!pr.ok) throw new Error(`Progress poll failed (${pr.status})`);
          const prog = await pr.json();
          startTransition(() => {
            setAnalysisProgress((prev) => ({
              ...prev,
              [phase]: {
                pct: typeof prog.pct === "number" ? prog.pct : 5,
                step: prog.step || "Analyzing…",
              },
            }));
          });
          try {
            sessionStorage.setItem(
              "neuro_kin_analyze_ui",
              JSON.stringify({
                phase,
                pct: prog.pct,
                step: prog.step || "Analyzing…",
              }),
            );
          } catch { /* ignore */ }
          if (prog.done) {
            if (prog.error) throw new Error(prog.error);
            break;
          }
          await new Promise((resolve) => setTimeout(resolve, pollMs));
        }
        const rr = await fetch(`${API_BASE}/analyze-result/${encodeURIComponent(jobId)}`, {
          signal: controller.signal,
        });
        if (!rr.ok) {
          let detail = `Server error ${rr.status}`;
          try { const e = await rr.json(); if (e.error) detail += `: ${e.error}`; } catch (_) {}
          throw new Error(detail);
        }
        result = await rr.json();
      }

      const resultError = analysisResultErrorMessage(result);
      if (resultError) {
        throw new Error(resultError);
      }

      // Strip the huge base64 payload before persisting; keep only the filename.
      const { unified_validation_video_b64: _, ...resultWithoutB64 } = result;
      const videoFilename = result.video_filename || file.name;

      if (!isCsv && videoFilename) {
        await ensureOriginalVideoBlob(phase, file, videoFilename);
      }

      const phasePayload = {
        ...resultWithoutB64,
        video_filename: videoFilename,
      };

      const nextResults = { ...kinematicsResults, [phase]: phasePayload };
      setKinematicsResults(nextResults);
      onChange({
        ...data,
        analysisResults: stripKinResultsForStorage(nextResults),
        [resultKey(phase)]: stripKinPhaseForSync(resultWithoutB64),
        [statusKey(phase)]: "completed",
      });
      showToast(`Analysis complete for ${phase}${result.trials_detected > 1 ? ` (${result.trials_detected} trials — mean)` : ""}${(result.warnings || []).length ? " — see warnings" : ""}`);
      setAnalysisProgress((prev) => ({ ...prev, [phase]: { pct: 100, step: "Done" } }));
      try {
        sessionStorage.removeItem("neuro_kin_analyze_ui");
      } catch { /* ignore */ }

      if (!isCsv && result.csv_filename) {
        setAnalysisProgress((prev) => ({ ...prev, [phase]: { pct: 100, step: "Loading validation overlay…" } }));
        fetchOverlayDataWithRetry(phase, result.csv_filename, { syncResults: true }, 8).catch(() => {
          showToast("Validation overlay could not be loaded", "error");
        });
      }
    } catch (err) {
      if (err.name === "AbortError") {
        showToast(`Analysis cancelled for ${phase}`, "info");
      } else {
        const errorMsg = err.message || "Analysis failed";
        showToast(errorMsg, "error");
        console.error("ANALYSIS ERROR:", err);
      }
      onChange({ ...data, [statusKey(phase)]: "uploaded" });
    } finally {
      delete abortRef.current[phase];
      setKinAnalyzeActive(false);
      try {
        sessionStorage.removeItem("neuro_kin_analyze_ui");
      } catch { /* ignore */ }
    }
  };

  const downloadFile = async (phase, type) => {
    const result = kinematicsResults[phase];
    if (!result) return;

    let filename = "";
    if (type === "csv") filename = result.csv_filename;
    if (type === "mot") filename = result.mot_filename;
    if (type === "video") filename = result.validation_video;
    if (type === "unified" || type === "unified-download") filename = result.unified_validation_video;
    if (type === "trc") {
      showToast("TRC export removed — use CSV or MOT", "info");
      return;
    }
    if (!filename) {
      if (type === "video") showToast("Skeleton validation video not available — re-analyze the video file", "error");
      if (type === "unified" || type === "unified-download") showToast("Unified validation video not available — generate it first", "error");
      return;
    }

    const url = `${API_BASE}/download/${encodeURIComponent(filename)}`;

    if (type === "unified-download") {
      // Prefer already-cached blob to avoid a second server round-trip and 404s
      // when the ephemeral HF Space has discarded the file.
      const blobUrl = videoBlobs[phase];
      if (blobUrl) {
        try {
          const res = await fetch(blobUrl);
          if (!res.ok) throw new Error(`Blob read failed (${res.status})`);
          const blob = await res.blob();
          const baseName = filename.includes("/") ? filename.split("/").pop() : filename;
          const typed =
            blob.type && blob.type !== "application/octet-stream"
              ? blob
              : new Blob([blob], { type: "video/mp4" });
          await downloadBlob(typed, baseName || "validation.mp4");
          showToast("Validation video downloaded", "success");
          const patientKey = patientDriveKeyFromDemographics(demographics);
          const driveName = canonicalDriveName(baseName, patientKey) || validationUnifiedDriveName(phase, typed);
          scheduleDriveFileBackup(driveName, typed, {
            patientKey,
            subfolder: "videos",
            force: true,
          });
        } catch (err) {
          console.error("Download from blob error:", err);
          showToast("Failed to download validation video", "error");
        }
        return;
      }
      try {
        const res = await fetch(url);
        if (res.status === 404) {
          showToast("Validation video expired on server — please re-analyze the video", "error");
          return;
        }
        if (!res.ok) throw new Error(`Download failed (${res.status})`);
        const blob = await res.blob();
        const baseName = filename.includes("/") ? filename.split("/").pop() : filename;
        const typed =
          blob.type && blob.type !== "application/octet-stream"
            ? blob
            : new Blob([blob], { type: "video/mp4" });
        await downloadBlob(typed, baseName || "validation.mp4");
        showToast("Validation video downloaded", "success");
        const patientKey = patientDriveKeyFromDemographics(demographics);
        const driveName = canonicalDriveName(baseName, patientKey) || validationUnifiedDriveName(phase, typed);
        scheduleDriveFileBackup(driveName, typed, {
          patientKey,
          subfolder: "videos",
          force: true,
        });
      } catch (err) {
        console.error("Download error:", err);
        showToast("Failed to download validation video", "error");
      }
      return;
    }

    // Play video inside app ? iOS PWA has no back button if we navigate away
    if (type === "video" || type === "unified") {
      const title = type === "unified" ? "Unified Validation Video" : "Skeleton Video";
      const blobUrl = videoBlobs[phase];
      if (blobUrl) {
        setMediaPreview({
          phase,
          url: blobUrl,
          title: `${phases.find((p) => p.k === phase)?.l || phase} — ${title}`,
          filename,
        });
      } else {
        const uv = kinematicsResults[phase]?.unified_validation_video;
        if (uv) loadVideoBlob(phase, uv);
        showToast("Loading validation video — try again in a moment", "info");
      }
      return;
    }

    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Download failed (${res.status})`);
      const blob = await res.blob();
      downloadBlob(blob, filename);
    } catch (err) {
      console.error("Download error:", err);
    }
  };

  // Fetch a validation video as a blob object URL so it plays reliably even when
  // the hosting proxy blocks HEAD/range requests (e.g. some browsers/PWAs).
  const loadVideoBlob = useCallback(async (phase, filename, { silent = false } = {}) => {
    if (!filename || videoLoadingRef.current[phase]) return;
    videoLoadingRef.current[phase] = true;
    setVideoLoading((prev) => ({ ...prev, [phase]: true }));
    const phaseResult = kinematicsResults[phase];

    const applyCachedUnified = async () => {
      if (!patientCacheKey) return false;
      const cached = await loadValidationSessionArtifact(patientCacheKey, phase);
      if (!validationCacheMatchesResult(cached, phaseResult, { relaxCsvMatch: true })) return false;
      const blob = cached?.unifiedVideoBlob;
      if (!(blob instanceof Blob) || blob.size <= 0) return false;
      if (cached.unifiedVideoFilename && cached.unifiedVideoFilename !== filename) return false;
      applyValidationCacheToState(phase, { unifiedVideoBlob: blob });
      return true;
    };

    try {
      const url = `${API_BASE}/video/${encodeURIComponent(filename)}`;
      const res = await fetch(url);
      if (res.status === 404) {
        if (await applyCachedUnified()) return;
        const cloud = await hydrateValidationFromCloud(phase, { overlay: false, original: false, unified: true });
        if (validationCacheMatchesResult(cloud, phaseResult, { relaxCsvMatch: true }) && cloud?.unifiedVideoBlob?.size) return;
        if (!silent) showToast("Validation video expired on server — please re-analyze", "error");
        setVideoBlobs((prev) => {
          if (prev[phase]) URL.revokeObjectURL(prev[phase]);
          return { ...prev, [phase]: null };
        });
        return;
      }
      if (!res.ok) throw new Error(`Failed (${res.status})`);
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      setVideoBlobs((prev) => {
        if (prev[phase]) URL.revokeObjectURL(prev[phase]);
        return { ...prev, [phase]: objectUrl };
      });
      persistValidationPhase(phase, {
        csvFilename: phaseResult?.csv_filename,
        unifiedVideoFilename: filename,
        unifiedVideoBlob: blob,
        kinematicsSnapshot: phaseResult,
      });
    } catch (err) {
      console.error("Failed to cache validation video:", err);
      if (await applyCachedUnified()) return;
      const cloud = await hydrateValidationFromCloud(phase, { overlay: false, original: false, unified: true });
      if (validationCacheMatchesResult(cloud, phaseResult, { relaxCsvMatch: true }) && cloud?.unifiedVideoBlob?.size) return;
      if (!silent) showToast("Validation video could not be loaded — try expanding it", "error");
      setVideoBlobs((prev) => {
        if (prev[phase]) URL.revokeObjectURL(prev[phase]);
        return { ...prev, [phase]: null };
      });
    } finally {
      videoLoadingRef.current[phase] = false;
      setVideoLoading((prev) => ({ ...prev, [phase]: false }));
      setVideoAttempts((prev) => ({ ...prev, [phase]: (prev[phase] || 0) + 1 }));
    }
  }, [showToast, patientCacheKey, kinematicsResults, applyValidationCacheToState, persistValidationPhase, hydrateValidationFromCloud, demographics, sessionKey]);


  const [uvErrors, setUvErrors] = useState({});

  // Auto-load validation video blobs as soon as they are referenced.
  // We fetch the full file once as a blob object URL and play from that because
  // the Space proxy does not stream range requests reliably for our binary files.
  useEffect(() => {
    phases.forEach((ph) => {
      const uv = kinematicsResults[ph.k]?.unified_validation_video;
      const attempts = videoAttempts[ph.k] || 0;
      if (uv && !videoBlobsRef.current[ph.k] && !videoLoadingRef.current[ph.k] && attempts < 5) {
        setTimeout(() => loadVideoBlob(ph.k, uv, { silent: true }), 0);
      }
    });
  }, [kinematicsResults, loadVideoBlob, videoAttempts]);

  const generateUnifiedValidation = async (phase, { isRetry = false, result: explicitResult = null } = {}) => {
    const result = explicitResult || kinematicsResults[phase];
    if (!result || !result.csv_filename || !result.video_filename) {
      showToast("Analyze the video first", "error");
      return;
    }
    setUvErrors((prev) => ({ ...prev, [phase]: null }));
    setAnalysisStatus((prev) => ({ ...prev, [phase]: "generating_unified" }));

    // Hide the results table while any analyzed phase is still waiting for its
    // unified validation video.
    setShowResultsTable(false);

    try {
      const formData = new FormData();
      formData.append("csv_filename", result.csv_filename);
      formData.append("video_filename", result.video_filename);
      console.log(`[UV] queueing for ${phase}: csv=${result.csv_filename} video=${result.video_filename}`);
      const res = await fetch(`${API_BASE}/unified-validation`, { method: "POST", body: formData });
      const data = await res.json();
      console.log(`[UV] queue response for ${phase}:`, data);
      if (!res.ok || data.error) throw new Error(data.error || `Failed (${res.status})`);
      const jobId = data.job_id;
      if (!jobId) throw new Error("No job id returned");

      let attempts = 0;
      const maxAttempts = 80; // ~3.5 minutes

      const poll = async () => {
        try {
          attempts += 1;
          if (attempts > maxAttempts) {
            throw new Error("Video generation is taking too long. Please retry.");
          }
          const statusRes = await fetch(`${API_BASE}/unified-validation-status/${jobId}`);
          const status = await statusRes.json();
          console.log(`[UV] status for ${phase} attempt ${attempts}:`, status);
          if (!statusRes.ok || status.error) throw new Error(status.error || "Status check failed");
          if (status.done) {
            if (status.unified_validation_video) {
              setKinematicsResults((prev) => ({
                ...prev,
                [phase]: { ...prev[phase], unified_validation_video: status.unified_validation_video, validation_summary: status.validation_summary },
              }));
              loadVideoBlob(phase, status.unified_validation_video);
              showToast("Unified validation video ready", "success");
              setShowResultsTable(false);
            } else {
              throw new Error(status.error || "Video generation failed");
            }
            setAnalysisStatus((prev) => ({ ...prev, [phase]: "idle" }));
            return;
          }
          setTimeout(poll, 2500);
        } catch (err) {
          console.error(err);
          setUvErrors((prev) => ({ ...prev, [phase]: err.message || "Failed to generate unified validation video" }));
          setAnalysisStatus((prev) => ({ ...prev, [phase]: "idle" }));
        }
      };
      setTimeout(poll, 1000);
    } catch (err) {
      console.error(err);
      const msg = err.message || "Failed to generate unified validation video";
      setUvErrors((prev) => ({ ...prev, [phase]: msg }));
      showToast(msg, "error");
      setAnalysisStatus((prev) => ({ ...prev, [phase]: "idle" }));
    }
  };

  // Show the kinematic results table only when every analyzed phase has a ready
  // client-side overlay. This guarantees the table numbers are always derived from
  // the actual video frames used by the validation overlay, not from server-side
  // analysis that may differ from the video.
  useEffect(() => {
    const analyzedPhases = phases.filter((ph) => kinematicsResults[ph.k]);
    if (analyzedPhases.length === 0) {
      setShowResultsTable(false);
      return;
    }
    const anyPending = analyzedPhases.some((ph) => !overlayData[ph.k] && !uvErrors[ph.k]);
    setShowResultsTable(!anyPending);
  }, [kinematicsResults, uvErrors, overlayData]);

  // Re-fetch overlay data for persisted sessions (page reload, saved report, etc.)
  // where the in-memory overlay state was lost but the backend CSV still exists.
  useEffect(() => {
    phases.forEach((ph) => {
      const result = kinematicsResults[ph.k];
      if (!result || overlayData[ph.k] || uvErrors[ph.k]) return;
      if (result.csv_filename) {
        fetchOverlayData(ph.k, result.csv_filename);
      }
    });
  }, [kinematicsResults, fetchOverlayData, overlayData, uvErrors]);

  const toggleResult = (phase) => {
    setExpandedResults((prev) => ({ ...prev, [phase]: !prev[phase] }));
  };

  const KIN_EMPTY = "\u2014";

  const getMetricValue = (phase, key) => {
    const result = kinematicsResults[phase];
    if (!result) return KIN_EMPTY;
    const overlay = overlayData?.[phase];
    const om = overlay?.frames?.length
      ? (() => { try { return computeOverlayMetrics(overlay); } catch { return result.overlay_metrics || null; } })()
      : (result.overlay_metrics || result.validation_summary || null);
    if (key === "pause_stops_panel") {
      return formatPanelAlignedKinValue("pause_stops_panel", null, om);
    }
    const metricKey = key === "peak_velocity_panel" ? "peak_velocity_cm_s" : key;
    const val = resolveKinMetricValue(result, metricKey, overlay);
    if (val === null) return KIN_EMPTY;
    if (key === "side_analyzed" || key === "side") return val;
    return val;
  };

  const displayMetricValue = (phase, key) => {
    const overlay = overlayData?.[phase];
    const om = overlay?.frames?.length
      ? (() => { try { return computeOverlayMetrics(overlay); } catch { return kinematicsResults[phase]?.overlay_metrics || null; } })()
      : (kinematicsResults[phase]?.overlay_metrics || kinematicsResults[phase]?.validation_summary || null);
    if (key === "pause_stops_panel") {
      return formatPanelAlignedKinValue("pause_stops_panel", null, om);
    }
    const val = getMetricValue(phase, key);
    const formatKey = key === "peak_velocity_panel" ? "peak_velocity_cm_s" : key;
    if (isPanelTableKey(formatKey) || formatKey === "pause_stops_panel") {
      const raw = val === KIN_EMPTY ? null : val;
      return formatPanelAlignedKinValue(formatKey, raw, om);
    }
    if (val === KIN_EMPTY || typeof val === "string") return val;
    return formatKinValue(formatKey, val);
  };

  const KIN_TIPS = {
    task_complete: "Did the patient finish the expected phases (reach, lift/transport, return)? Higher = completed.",
    task_completion_ratio: "Share of expected task phases detected. Compare this before full-task smoothness.",
    nvp_reach: "Same as the NVP chip on the validation-video panel (peaks counted up to movement-window end).",
    nvp_drink: "Velocity peaks while lifting the cup from the table to the highest point achieved.",
    nvp_transport: "Velocity peaks during the transport / drink-lift phase (same as NVP drink for drink task).",
    nvp_return: "Velocity peaks while returning the cup/hand to the table.",
    nvp_total: "Sum of NVP across reach + drink/transport + return phases.",
    drink_lift_height_cm: "How high the palm rose during drink (table → peak), in cm using the 85 cm table width scale. Higher = greater lift.",
    lift_height_cm: "Peak vertical lift during transport, in cm (85 cm table scale).",
    drink_lift_height_sw: "Drink lift height in shoulder-width units (secondary / normalized).",
    lift_height_sw: "Peak vertical lift during transport, in shoulder-width units.",
    straightness_reach: "Path straightness on the reach window only.",
    pause_time_sec_reach: "Path pauses during reach only — excludes grasp fixation and drink sips.",
    number_of_stops_reach: "Path stops during reach only (sips excluded).",
    sip_bout_count: "How many times the cup approached the mouth during drink. Descriptive only — does not make NVP worse.",
    grasp_dwell_sec: "Terminal low-speed time at the end of reach (cup grasp fixation). Functional — not counted as path pause.",
    functional_hold_sec: "Grasp dwell + mouth/face hold during transport. Functional time, not path pause.",
    pause_time_sec_total: "All low-speed time including grasp/mouth dwell (exploratory).",
    nvp: "NVP on the validation-video panel (peaks up to movement end). Same number as the NVP chip on the overlay.",
    nvp_reach: "Same as the NVP chip on the validation-video panel (peaks up to movement-window end).",
    straightness: "Path straightness from the validation-video panel (same formula and 2 decimals).",
    pause_time_sec: "Pause time from the validation-video panel: every frame below 5% of peak hand speed (no min-run / dwell split).",
    number_of_stops: "Stops from the validation-video panel: speed threshold crossings (same as Pause / stops).",
    trunk_ratio: "Trunk / palm displacement ratio from the validation-video panel (0–1, not percent).",
    movement_time_sec: "Movement time from the validation-video panel (onset to window end).",
    peak_velocity_cm_s: "Peak velocity from the validation-video panel (cm/s when calibrated, else elbow °/s).",
    peak_elbow_ang_vel_deg_s: "Peak elbow angular velocity from the validation-video panel (max from clip start through movement end).",
    shoulder_elevation_cm: "Shoulder elevation from the validation-video panel (cm when calibrated, else the panel ratio).",
    tremor_8_12hz_power: "Tremor 8–12 Hz from the validation-video panel (same as Tremor 8–12 Hz on the overlay).",
    nvp_full_task: "NVP on the whole recording including all sip approaches — exploratory only; do not treat higher values from extra sips as worse movement.",
    trunk_ratio: "Trunk displacement / palm displacement. Lower = less trunk compensation.",
    shoulder_elevation_cm: "How much the affected shoulder rose (rest → peak), in cm using the 85 cm table scale. Lower = less shoulder hike.",
    shoulder_elevation_palm_ratio: "Shoulder elevation as a unitless palm-anchor ratio (exploratory).",
    elbow_angle_mean_deg: "Mean elbow flexion angle during the movement window.",
    shoulder_flexion_mean_deg: "Mean shoulder flexion angle (trunk–shoulder–elbow) during the movement window.",
    movement_time_sec: "Active movement duration (onset to offset).",
    peak_velocity_cm_s: "Peak hand speed during reach (cm/s), scaled with the 85 cm table width. Higher = faster reach.",
    peak_elbow_ang_vel_deg_s: "Peak elbow angular velocity during the reach (deg/s).",
    peak_shoulder_flexion_vel_deg_s: "Peak shoulder flexion angular velocity during the reach (deg/s).",
    peak_velocity_panel: "Peak hand velocity (cm/s) from table calibration.",
    tremor_8_12hz_power: "Hand-speed power in 8–12 Hz from the validation video overlay (same as Tremor 8–12 Hz on the skeleton). Lower = less tremor. Index/ADL tremor stay under Show all.",
    fine_motor_quality_index: "Hand / finger quality 0–100 from the validation overlay: index-tip smoothness (fewer peaks/micro-stops, lower speed CV) plus pinch opening when available. Higher = better.",
    shoulder_abduction_rom_deg: "Shoulder abduction range during the reach (validation overlay).",
    forearm_pronation_supination_rom_deg: "Forearm pronation/supination ROM (validation overlay).",
    fine_motor_quality_index: "Fine motor quality index 0–100 (validation overlay).",
    adl_shoulder_abduction_mean_deg: "Mean shoulder abduction during drink transport (lower = less compensatory lift).",
    adl_shoulder_abduction_rom_deg: "Shoulder abduction ROM during ADL transport phase (lower = better for drink).",
    adl_finger_flex_ext_quality_index: "Finger open/close smoothness and ROM during drink (0–100; higher = better).",
    adl_head_forward_flexion_compensation_index: "Head lean toward cup + neck flexion during drink (0–1; lower = more stable head).",
    finger_flex_ext_quality_index: "Finger open/close quality index from movement profile (0–100).",
    head_forward_flexion_compensation_index: "Combined head forward displacement and flexion compensation (0–1; lower = better).",
    adl_tremor_8_12hz_power: "Tremor 8–12 Hz during ADL phase (relative power).",
    pause_stops_panel: "Same Pause / stops row as the validation-video panel.",
  };

  const CARD_PREVIEW_KEYS = ["task_complete", "nvp_reach", "nvp_drink", "nvp_total", "drink_lift_height_cm"];

  const variables = orderedKinematicResultsTableVars({
    includeExtended: showAllKinMetrics,
    clinicalTask: clinicalMovementTask,
    kinematicsResults,
  }).map((v) => ({
    group: v.group,
    name: v.name,
    key: v.key,
    unit: v.unit || "",
    direction: v.direction,
    tip: KIN_TIPS[v.key] || "",
  }));

  const activeResultPhases = phases.filter((ph) => kinematicsResults[ph.k]);
  const kinViewWarning = (() => {
    const mismatch = describeCompletionMismatch(kinematicsResults);
    if (mismatch) return mismatch;
    const lowAmp = activeResultPhases.filter((ph) => kinematicsResults[ph.k]?.sparc_comparable === false);
    if (lowAmp.length) {
      return `Reach amplitude low in ${lowAmp.map((ph) => ph.label).join(", ")}  — kinematic smoothness metrics may be less reliable`;
    }
    return null;
  })();
  const hasKinTriple =
    kinematicsResults.pre && kinematicsResults.post && kinematicsResults.baseline;
  const phaseChipCls = (c, on) => {
    if (c === "sky") return on ? "bg-sky-400/20 border-sky-400/40 text-sky-200" : "bg-white/[0.04] border-white/[0.08] text-white/50";
    if (c === "violet") return on ? "bg-violet-400/20 border-violet-400/40 text-violet-200" : "bg-white/[0.04] border-white/[0.08] text-white/50";
    if (c === "emerald") return on ? "bg-emerald-400/20 border-emerald-400/40 text-emerald-200" : "bg-white/[0.04] border-white/[0.08] text-white/50";
    return on ? "bg-amber-400/20 border-amber-400/40 text-amber-200" : "bg-white/[0.04] border-white/[0.08] text-white/50";
  };
  const phaseValueCls = (c) =>
    c === "sky" ? "border-sky-400/25 bg-sky-400/10" :
    c === "violet" ? "border-violet-400/25 bg-violet-400/10" :
    c === "emerald" ? "border-emerald-400/25 bg-emerald-400/10" :
    "border-amber-400/25 bg-amber-400/10";
  const phaseLabelCls = (c) =>
    c === "sky" ? "text-sky-300" : c === "violet" ? "text-violet-300" :
    c === "emerald" ? "text-emerald-300" : "text-amber-300";

  const kinDirArrow = (dir) => {
    if (dir === "higher") return { sym: "\u2191", tip: "Higher is better" };
    if (dir === "lower") return { sym: "\u2193", tip: "Lower is better" };
    return null;
  };

  const renderKinMetricRow = (metric, idx, prevGroup) => {
    const showGroupHeader = metric.group !== prevGroup;
    const preVal = getMetricValue("pre", metric.key);
    const postVal = getMetricValue("post", metric.key);
    const baselineVal = getMetricValue("baseline", metric.key);
    const kinComparable = kinCrossPhaseComparable(kinematicsResults, metric.key, analyzedArmForPhase);
    const deltaPrePost = resolveKinPrePostCell(
      preVal, postVal, metric.direction, metric.key, kinematicsResults, analyzedArmForPhase,
    );
    const deltaPostHealthy = kinComparable && postVal !== KIN_EMPTY && baselineVal !== KIN_EMPTY
      ? kinPostHealthyBadge(preVal, postVal, baselineVal, metric.direction) : null;
    const arrow = kinDirArrow(metric.direction);

    return (
      <React.Fragment key={metric.key}>
        {showGroupHeader && (
          <p className={`text-[10px] font-extrabold uppercase tracking-widest text-white/30 ${idx === 0 ? "mt-0" : "mt-4"} mb-2`}>
            {metric.group}
          </p>
        )}
        <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="min-w-0">
              <p className="text-sm font-extrabold text-white/90 whitespace-nowrap flex items-center gap-1">
                {metric.name}
                {arrow && (
                  <span className="text-emerald-400/90 text-xs font-bold" title={arrow.tip}>{arrow.sym}</span>
                )}
              </p>
              <p className="text-[10px] text-white/35 mt-0.5">{metric.unit}</p>
            </div>
            {metric.tip && (
              <span className="text-[10px] text-white/25 leading-snug max-w-[40%] text-right hidden sm:block">{metric.tip}</span>
            )}
          </div>
          {kinResultsTab === "compare" ? (
            <div className={`grid gap-2 ${activeResultPhases.length <= 2 ? "grid-cols-2" : "grid-cols-2"}`}>
              {activeResultPhases.map((ph) => (
                <div key={ph.k} className={`rounded-lg border px-2.5 py-2 ${phaseValueCls(ph.c)}`}>
                  <p className={`text-[10px] font-extrabold uppercase ${phaseLabelCls(ph.c)}`}>{ph.l}</p>
                  <p className="text-base font-mono font-bold text-white/90 mt-0.5">
                    {displayMetricValue(ph.k, metric.key)}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-2xl font-mono font-extrabold text-white/90">
              {displayMetricValue(kinResultsTab, metric.key)}
            </p>
          )}
          {kinResultsTab === "compare" && (deltaPrePost || deltaPostHealthy) && (
            <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-white/[0.06]">
              {deltaPrePost && (
                <span className={`px-2 py-0.5 text-[10px] font-bold rounded-md border ${deltaPrePost.colorClass}`}>
                  Pre → Post: {deltaPrePost.text}
                </span>
              )}
              {deltaPostHealthy && (
                <span className={`px-2 py-0.5 text-[10px] font-bold rounded-md border ${deltaPostHealthy.colorClass}`}>
                  Post ? Healthy: {deltaPostHealthy.text}
                </span>
              )}
            </div>
          )}
        </div>
      </React.Fragment>
    );
  };



  return (
    <div className="space-y-5">
      <SH icon={Cpu} en="Kinematics AI Laboratory" tr="Kinematik Yapay Zeka Laboratuvarı" badge="Pre · Post · Healthy side" />

      <Glass className="p-5 sm:p-6">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-extrabold text-white/80 text-center sm:text-left">Video Upload &amp; Analysis</p>
          {Object.keys(kinematicsResults).length > 0 && (
            <button
              type="button"
              onClick={clearAllKin}
              className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1.5 rounded-md bg-red-500/10 text-red-300 hover:bg-red-500/20 border border-red-400/20 transition-colors"
              title="Remove all results"
            >
              <X className="w-3 h-3" />
              Clear All
            </button>
          )}
        </div>
        <div className="mb-4 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2.5 text-[11px] text-white/55">
          {kinematicDomain === "le" ? (
            <>
              <span className="font-bold text-white/70">Lower extremity:</span>{" "}
              Full body must stay in frame. Use sit-to-stand, squat, gait, or quiet stance — UE reach tasks stay under Upper Extremity.
            </>
          ) : (
            <>
              <span className="font-bold text-white/70">Auto arm:</span>{" "}
              The more active arm during the reach is detected and analyzed automatically for each video.
            </>
          )}
        </div>
        <div className="mb-4 max-w-xl mx-auto space-y-3">
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-widest text-white/40 mb-2 text-center sm:text-left">
              Extremity
            </p>
            <div className="grid grid-cols-2 gap-2">
              {(["ue", "le"]).map((domain) => {
                const active = kinematicDomain === domain;
                const meta = CLINICAL_DOMAIN_LABELS[domain];
                return (
                  <button
                    key={domain}
                    type="button"
                    onClick={() => selectKinematicDomain(domain)}
                    className={`rounded-xl border px-3 py-2.5 text-left transition-colors ${
                      active
                        ? domain === "ue"
                          ? "bg-sky-500/20 border-sky-400/40 text-sky-100"
                          : "bg-violet-500/20 border-violet-400/40 text-violet-100"
                        : "bg-white/[0.03] border-white/[0.08] text-white/55 hover:bg-white/[0.06]"
                    }`}
                  >
                    <span className="block text-xs font-extrabold tracking-wide">{meta.en}</span>
                  </button>
                );
              })}
            </div>
          </div>
          <GSelect
            en={`${CLINICAL_DOMAIN_LABELS[kinematicDomain].short} movement task`}
            tr=""
            value={clinicalMovementTask}
            onChange={(e) => setClinicalMovementTask(e.target.value)}
            options={domainTasks.map((t) => ({ value: t.id, label: t.label }))}
          />
          <p className="text-[10px] text-white/40 mt-1.5 text-center sm:text-left">
            {clinicalTaskById(clinicalMovementTask).hint}
          </p>
        </div>
        <div className="flex justify-center">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 w-full max-w-3xl">
          {phases.map((ph) => {
            const status = data[statusKey(ph.k)] || "idle";
            const hasResult = !!kinematicsResults[ph.k];

            return (
              <div key={ph.k} className={kinPhaseCardCls(ph.c, status, hasResult)}>
                <div className="px-4 pt-4 pb-2 flex items-center justify-between gap-2">
                  <span className={`text-xs font-extrabold uppercase tracking-widest ${phaseLabelCls(ph.c)}`}>{ph.l}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    {(hasResult || status === "analyzing") && (
                      <button
                        type="button"
                        onClick={() => clearPhase(ph.k)}
                        className="inline-flex items-center justify-center w-7 h-7 rounded-md text-white/40 hover:text-red-300 hover:bg-red-500/10 border border-transparent hover:border-red-400/20 transition-colors"
                        title={status === "analyzing" ? "Cancel analysis" : "Remove"}
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="px-4 py-2 flex flex-col flex-1 min-h-0">
                  <label htmlFor={`kin-file-${ph.k}`} className={`${kinUploadZoneCls(ph.c, !!data[vidKey(ph.k)])} relative mb-3 min-h-[130px] overflow-hidden ${status === "analyzing" ? "pointer-events-none" : ""}`}>
                  <div className="flex flex-col items-center justify-center gap-1.5 w-full">
                  <input
                      id={`kin-file-${ph.k}`}
                    type="file"
                    accept="video/*,.csv"
                    onChange={(e) => handleFile(ph.k, e.target.files?.[0])}
                      disabled={status === "analyzing"}
                      className="sr-only"
                    />
                    {status === "analyzing" ? (
                      <>
                        <KinFilmStripLoop accent={ph.c} />
                        {data[vidKey(ph.k)] && (
                          <span className="text-[10px] font-medium text-white/55 truncate max-w-full px-1" title={data[vidKey(ph.k)]}>
                            {kinShortFileName(data[vidKey(ph.k)])}
                          </span>
                        )}
                      </>
                    ) : (
                      <>
                    <Upload className={`w-5 h-5 transition-colors ${data[vidKey(ph.k)] ? "text-white/55" : "text-white/30 group-hover:text-white/50"}`} />
                    {data[vidKey(ph.k)] ? (
                      <>
                        <span className="text-[11px] font-semibold text-white/80 truncate max-w-full px-1" title={data[vidKey(ph.k)]}>
                          {kinShortFileName(data[vidKey(ph.k)])}
                        </span>
                        <span className="text-[9px] text-white/35">Tap to replace</span>
                      </>
                    ) : (
                      <>
                        <span className="text-[11px] font-semibold text-white/55 group-hover:text-white/70">Video or CSV</span>
                        <span className="text-[9px] text-white/30">Browse files</span>
                      </>
                    )}
                      </>
                    )}
                </div>
                  </label>

                  <div className="mt-auto flex flex-col gap-2">
                    {status === "analyzing" ? (
                      <KinPhaseAnalyzeProgressBar
                        accent={ph.c}
                        pct={analysisProgress[ph.k]?.pct}
                        step={analysisProgress[ph.k]?.step || "Analyzing video…"}
                      />
                    ) : (
                    <GBtn variant={ph.c} onClick={() => analyzeVideo(ph.k)} disabled={!data[vidKey(ph.k)]} className="w-full text-xs py-2.5" title="Analyze">
                        <Play className="w-4 h-4 mx-auto" />
                  </GBtn>
                    )}

                  {hasResult && (
                      <div className="flex justify-center gap-1">
                        <GBtn variant="default" onClick={() => downloadFile(ph.k, "csv")} className="!py-1.5 !px-2 min-w-[2.25rem] shrink-0" title="CSV data">
                        <FileSpreadsheet className="w-3.5 h-3.5" />
                      </GBtn>
                        <GBtn variant="default" onClick={() => downloadFile(ph.k, "mot")} className="!py-1.5 !px-2 min-w-[2.25rem] shrink-0" title="OpenSim MOT (IK)">
                        <Activity className="w-3.5 h-3.5" />
                      </GBtn>
                        <GBtn variant="default" onClick={() => kinematicsResults[ph.k]?.unified_validation_video ? downloadFile(ph.k, "unified") : generateUnifiedValidation(ph.k)} disabled={analysisStatus[ph.k] === "generating_unified"} className="!py-1.5 !px-2 min-w-[2.25rem] shrink-0" title={kinematicsResults[ph.k]?.unified_validation_video ? "Unified Validation Video" : "Generate Unified Validation Video"}>
                          {analysisStatus[ph.k] === "generating_unified" ? (
                            <span className="text-[10px] font-bold leading-none">…</span>
                          ) : (
                            <span className="text-[10px] font-bold leading-none">UV</span>
                          )}
                      </GBtn>
                    </div>
                  )}

                  {hasResult && (
                      <div className="sm:hidden grid grid-cols-2 gap-1.5">
                        {CARD_PREVIEW_KEYS.map((key) => {
                          const meta = KINEMATIC_VARS.find((v) => v.key === key);
                          if (!meta) return null;
                          return (
                            <div key={key} className={`rounded-lg border px-2 py-1.5 ${phaseValueCls(ph.c)}`}>
                              <p className="text-[9px] font-bold text-white/45 leading-tight">{meta.label}</p>
                              <p className="text-sm font-mono font-extrabold text-white/90 mt-0.5">
                                {displayMetricValue(ph.k, key)}
                                <span className="text-[9px] font-normal text-white/35 ml-0.5">{meta.unit}</span>
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {hasResult && kinematicsResults[ph.k]?.velocity_profile && (
                      <>
                        <button
                          type="button"
                          onClick={() => toggleResult(ph.k)}
                          className="w-full text-[11px] text-white/45 hover:text-white/75 py-1.5 font-medium tracking-wide border border-white/[0.06] rounded-lg bg-white/[0.03] hover:bg-white/[0.06] transition-colors"
                          title={expandedResults[ph.k] ? "Hide chart" : "Show movement chart"}
                        >
                          {expandedResults[ph.k] ? "Hide chart" : "Movement chart"}
                  </button>

                        <AnimatePresence>
                          {expandedResults[ph.k] && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: "auto", opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.25 }}
                              className="overflow-hidden"
                            >
                              <div className="rounded-xl border border-white/[0.08] bg-black/30 overflow-hidden">
                                <div
                                  className="w-full h-[140px] p-2 kin-phase-chart"
                                  dangerouslySetInnerHTML={{
                                    __html: buildCombinedVelChart({ [ph.k]: kinematicsResults[ph.k].velocity_profile }, false, true),
                                  }}
                                />
                  </div>
                            </motion.div>
                )}
                        </AnimatePresence>
                      </>
                    )}
                  </div>
                </div>

              </div>
            );
          })}
          </div>
        </div>
      </Glass>

      {Object.keys(kinematicsResults).length > 0 && (
        <Glass className="p-4 sm:p-5">
          <div className="flex items-center justify-between mb-3 gap-2">
            <p className="text-sm font-extrabold text-white/80">Validation Video</p>
            <p className="text-[10px] text-white/40 hidden sm:block">Re-analyze after overlay v36 deploy</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {phases.filter((ph) => kinematicsResults[ph.k]).map((ph) => (
              <div key={ph.k} className="rounded-xl border border-white/10 bg-black/20 p-3 overflow-hidden">
                <div className="flex items-center justify-between mb-2 gap-2">
                  <p className={`text-[10px] font-extrabold uppercase ${phaseLabelCls(ph.c)}`}>{`${ph.l} \u00b7 Validation`}</p>
                </div>
                {overlaySourceBad[ph.k] && originalVideoBlobs[ph.k] ? (
                    <InlineValidationVideo
                      src={originalVideoBlobs[ph.k]}
                      phaseLabel={ph.l}
                      autoPlay={false}
                    />
                ) : overlayData[ph.k] ? (
                  originalVideoBlobs[ph.k] ? (
                    overlayMountReady[ph.k] ? (
                    <KinOverlayErrorBoundary key={`ov-${ph.k}-${overlayData[ph.k]?.version || "v"}`}>
                    <ValidationOverlayPlayer
                      videoUrl={originalVideoBlobs[ph.k]}
                      overlayData={overlayData[ph.k]}
                      clinicalTask={kinematicsResults[ph.k]?.clinical_task || clinicalMovementTask}
                      phaseLabel={ph.l}
                      autoPlay={false}
                      autoRender={Boolean(
                        overlayData[ph.k]?.frames?.length
                        && originalVideoBlobs[ph.k]
                        && !driveBakeDone[ph.k],
                      )}
                      serverExportFilename={
                        kinematicsResults[ph.k]?.unified_validation_video || null
                      }
                      onRequestServerExport={async () => {
                        const r = kinematicsResults[ph.k];
                        if (r?.unified_validation_video) {
                          await downloadFile(ph.k, "unified-download");
                          return;
                        }
                        showToast("Generating validation video on server…", "info");
                        await generateUnifiedValidation(ph.k);
                      }}
                      onDownloadReady={(_url, blob) => {
                        if (!blob || !(blob instanceof Blob) || blob.size < 1000) return;
                        setDriveBakeDone((prev) => ({ ...prev, [ph.k]: true }));
                        persistValidationPhase(ph.k, {
                          unifiedVideoBlob: blob,
                          compositedOverlay: true,
                          compositedOverlayQuality: 2,
                          kinematicsSnapshot: kinematicsResults[ph.k],
                        });
                        const patientKey = patientDriveKeyFromDemographics(demographics);
                        if (!patientKey) {
                          if (!driveBakeToastRef.current[`${ph.k}-nopatient`]) {
                            driveBakeToastRef.current[`${ph.k}-nopatient`] = true;
                            showToast("Validation ready — set patient ID/name to auto-save on Drive", "info");
                          }
                          return;
                        }
                        // persistValidationPhase already uploads original+overlay+kinematics+view-copy (multipart OK).
                        if (!driveBakeToastRef.current[ph.k]) {
                          driveBakeToastRef.current[ph.k] = true;
                          showToast(`${ph.l}: screen recording saved to patient Drive`, "success");
                        }
                      }}
                      onError={(msg) => showToast(msg || `${ph.l} overlay error`, "error")}
                    />
                    </KinOverlayErrorBoundary>
                    ) : (
                    <div className="aspect-video rounded-lg bg-black/50 flex flex-col items-center justify-center text-center p-3">
                      <p className="text-[11px] text-white/50 mb-2">{"Starting validation preview\u2026"}</p>
                      <div className="w-8 h-8 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
                    </div>
                    )
                  ) : (
                    <div className="aspect-video rounded-lg bg-black/50 flex flex-col items-center justify-center text-center p-3">
                      <p className="text-[11px] text-white/50 mb-2">{"Loading original video\u2026"}</p>
                      <div className="w-8 h-8 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
                    </div>
                  )
                ) : kinematicsResults[ph.k]?.unified_validation_video ? (
                  videoBlobs[ph.k] ? (
                    <InlineValidationVideo
                      src={videoBlobs[ph.k]}
                      phaseLabel={ph.l}
                      autoPlay={false}
                      onEnded={() => setShowResultsTable(true)}
                      onError={() => {
                        showToast(`${ph.l} validation video could not be played`, "error");
                        setShowResultsTable(true);
                      }}
                    />
                  ) : videoLoading[ph.k] ? (
                    <div className="aspect-video rounded-lg bg-black/50 flex flex-col items-center justify-center text-center p-3">
                      <p className="text-[11px] text-white/50 mb-2">{"Loading validation video\u2026"}</p>
                      <div className="w-8 h-8 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
                    </div>
                  ) : (
                    <div className="aspect-video rounded-lg bg-black/50 flex flex-col items-center justify-center text-center p-3 gap-2">
                      <p className="text-[11px] text-white/50">Validation video could not be loaded.</p>
                      <button
                        type="button"
                        onClick={() => loadVideoBlob(ph.k, kinematicsResults[ph.k].unified_validation_video)}
                        className="text-[10px] px-2 py-1 rounded-md bg-white/10 hover:bg-white/20 text-white/80 transition-colors"
                      >
                        Retry
                      </button>
                    </div>
                  )
                ) : uvErrors[ph.k] ? (
                  <div className="aspect-video rounded-lg bg-black/50 flex flex-col items-center justify-center text-center p-3 gap-2">
                    <p className="text-[11px] text-rose-300/90 max-w-[90%]">{uvErrors[ph.k]}</p>
                    <button
                      type="button"
                      onClick={() => generateUnifiedValidation(ph.k, { isRetry: true })}
                      disabled={analysisStatus[ph.k] === "generating_unified"}
                      className="text-[10px] px-2 py-1 rounded-md bg-white/10 hover:bg-white/20 text-white/80 transition-colors disabled:opacity-50"
                    >
                      Retry
                    </button>
                  </div>
                ) : (
                  <div className="aspect-video rounded-lg bg-black/50 flex flex-col items-center justify-center text-center p-3">
                    <p className="text-[11px] text-white/50 mb-2">{"Preparing validation overlay\u2026"}</p>
                    <div className="w-8 h-8 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </Glass>
      )}

      {Object.keys(kinematicsResults).length > 0 && showResultsTable && (
        <Glass className="p-4 sm:p-5">
          <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
            <div className="min-w-0">
              <p className="text-sm font-extrabold text-white/80">Kinematic Results</p>
              <p className="text-[10px] text-white/40 mt-0.5">
                {showAllKinMetrics ? "All stored metrics" : "Core movement quality (15)"}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                type="button"
                onClick={() => setShowAllKinMetrics((v) => !v)}
                className={`px-2.5 py-1.5 rounded-lg border text-[10px] font-bold transition-all ${
                  showAllKinMetrics
                    ? "bg-white/12 border-white/25 text-white"
                    : "bg-white/[0.04] border-white/[0.1] text-white/60 hover:text-white/85"
                }`}
                title={showAllKinMetrics ? "Show core quality metrics only" : "Show every stored metric"}
              >
                {showAllKinMetrics ? "Core only" : "Show all"}
              </button>
              <GBtn variant="danger" onClick={clearAllKin} className="text-[10px] py-1.5 px-3" title="Remove all results">
                <X className="w-3 h-3 mr-1" />
                Clear All
              </GBtn>
            </div>
          </div>
          {kinViewWarning && (
            <div className="mb-3 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2.5 text-[11px] text-amber-100/90">
              {kinViewWarning}
            </div>
          )}

          {/* Mobile / tablet ? tabs + vertical cards (no horizontal swipe) */}
          <div className="lg:hidden">
            <div className="flex flex-wrap gap-1.5 mb-4">
              <button
                type="button"
                onClick={() => setKinResultsTab("compare")}
                className={`px-3 py-1.5 rounded-lg border text-xs font-bold transition-all ${
                  kinResultsTab === "compare" ? "bg-white/12 border-white/20 text-white" : "bg-white/[0.04] border-white/[0.08] text-white/50"
                }`}
              >
                Compare All
              </button>
              {activeResultPhases.map((ph) => (
                <button
                  key={ph.k}
                  type="button"
                  onClick={() => setKinResultsTab(ph.k)}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-bold transition-all ${phaseChipCls(ph.c, kinResultsTab === ph.k)}`}
                >
                  {ph.l}
                </button>
              ))}
            </div>
            <div className="space-y-2">
              {variables.map((metric, idx) =>
                renderKinMetricRow(metric, idx, idx > 0 ? variables[idx - 1].group : null)
              )}
              {activeResultPhases.length > 0 && (
                <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-3 mt-4">
                  <p className="text-sm font-extrabold text-white/70 mb-2">Analyzed arm</p>
                  <div className={`grid gap-2 ${activeResultPhases.length <= 2 ? "grid-cols-2" : "grid-cols-2"}`}>
                    {activeResultPhases.map((ph) => (
                      <div key={ph.k} className={`rounded-lg border px-2.5 py-2 ${phaseValueCls(ph.c)}`}>
                        <p className={`text-[10px] font-extrabold uppercase ${phaseLabelCls(ph.c)}`}>{ph.l}</p>
                        <p className="text-base font-mono font-bold text-white/90 mt-0.5">
                          {armSideLabel(analyzedArmForPhase(kinematicsResults, ph.k))}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Desktop ? full comparison table */}
          <div className="hidden lg:block glass-float rounded-xl border border-white/[0.08] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.08] bg-white/[0.04]">
                  <th className="text-left px-3 py-3 font-extrabold text-white/40 text-[10px] uppercase w-16">Group</th>
                  <th className="text-left px-4 py-3 font-extrabold text-white/60 text-xs uppercase whitespace-nowrap">Variable</th>
                  <th className="text-left px-3 py-3 font-extrabold text-white/60 text-xs uppercase w-16 whitespace-nowrap">Unit</th>
                  {phases.filter((ph) => kinematicsResults[ph.k]).map((ph) => (
                    <th
                      key={ph.k}
                      className={`text-center px-2 py-3 font-extrabold text-[10px] uppercase whitespace-nowrap ${
                        ph.c === "sky"
                          ? "text-sky-300"
                          : ph.c === "violet"
                          ? "text-violet-300"
                          : ph.c === "emerald"
                          ? "text-emerald-300"
                          : "text-amber-300"
                      }`}
                    >
                      {ph.l}
                    </th>
                  ))}
                  {kinematicsResults.pre && kinematicsResults.post && (
                    <th className="text-center px-2 py-3 font-extrabold text-[10px] uppercase whitespace-nowrap">
                      <span className="text-sky-300">Pre</span> <span className="text-white/60">→</span> <span className="text-emerald-300">Post</span>
                    </th>
                  )}
                  {kinematicsResults.post && kinematicsResults.baseline && (
                    <th className="text-center px-2 py-3 font-extrabold text-[10px] uppercase whitespace-nowrap">
                      <span className="text-emerald-300">Post</span> <span className="text-white/60">→</span> <span className="text-amber-300">Healthy</span>
                    </th>
                  )}
                </tr>
              </thead>

              <tbody>
                {variables.map((metric, idx) => {
                  // Group header row
                  const prevGroup = idx > 0 ? variables[idx - 1].group : null;
                  const showGroupHeader = metric.group !== prevGroup;

                  const preVal      = getMetricValue("pre",      metric.key);
                  const postVal     = getMetricValue("post",     metric.key);
                  const baselineVal = getMetricValue("baseline", metric.key);
                  const kinComparable = kinCrossPhaseComparable(kinematicsResults, metric.key, analyzedArmForPhase);

                  const deltaPrePost = resolveKinPrePostCell(
                    preVal, postVal, metric.direction, metric.key, kinematicsResults, analyzedArmForPhase,
                  );

                  const deltaPostHealthy = kinComparable && postVal !== KIN_EMPTY && baselineVal !== KIN_EMPTY
                    ? kinPostHealthyBadge(preVal, postVal, baselineVal, metric.direction)
                    : null;

                  return (
                    <React.Fragment key={metric.key}>
                      {showGroupHeader && (
                        <tr>
                          <td
                            colSpan={
                              3 +
                              phases.filter((ph) => kinematicsResults[ph.k]).length +
                              (kinematicsResults.pre && kinematicsResults.post ? 1 : 0) +
                              (kinematicsResults.post && kinematicsResults.baseline ? 1 : 0)
                            }
                            className="px-4 pt-5 pb-1"
                          >
                            <span className="text-[10px] font-extrabold uppercase tracking-widest text-white/30">
                              {metric.group}
                            </span>
                          </td>
                        </tr>
                      )}

                      <tr className="border-b border-white/[0.05] hover:bg-white/[0.03]">
                        <td className="px-3 py-2.5" />
                        <td className="px-4 py-2.5 font-bold text-white/80 text-sm whitespace-nowrap">
                          <span className="inline-flex items-center gap-1">
                          {metric.name}
                            {kinDirArrow(metric.direction) && (
                              <span className="text-emerald-400/90 text-xs font-bold" title={kinDirArrow(metric.direction).tip}>
                                {kinDirArrow(metric.direction).sym}
                              </span>
                            )}
                          </span>
                          {metric.tip && (
                            <span className="group relative inline-flex ml-1.5 align-middle cursor-help">
                              <Info className="w-3 h-3 text-white/30 hover:text-white/60 transition-colors" />
                              <span className="absolute left-0 bottom-full mb-2 hidden group-hover:block z-50 w-72 px-3 py-2 text-[11px] leading-relaxed text-white bg-slate-800/95 border border-white/[0.04] rounded-lg shadow-xl pointer-events-none">
                                {metric.direction === "higher" && <span className="text-emerald-400 font-bold block mb-1">\u2191 Higher = Better</span>}
                                {metric.direction === "lower" && <span className="text-emerald-400 font-bold block mb-1">\u2193 Lower = Better</span>}
                                {metric.tip}
                              </span>
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 font-light text-white/40 text-xs whitespace-nowrap">{metric.unit}</td>

                        {phases.filter((ph) => kinematicsResults[ph.k]).map((ph) => (
                          <td key={ph.k} className="px-2 py-2.5 text-center whitespace-nowrap">
                            <span className="text-white/80 font-mono text-xs">
                              {displayMetricValue(ph.k, metric.key)}
                            </span>
                          </td>
                        ))}

                        {kinematicsResults.pre && kinematicsResults.post && (
                          <td className="px-2 py-2.5 text-center whitespace-nowrap">
                            {deltaPrePost ? (
                              <span
                                className={`px-2.5 py-1 text-xs font-bold rounded-lg border ${deltaPrePost.colorClass}`}
                                title={deltaPrePost.nc ? deltaPrePost.text : undefined}
                              >
                                {deltaPrePost.text}
                              </span>
                            ) : (
                              <span className="text-white/20 text-xs">{NA}</span>
                            )}
                          </td>
                        )}

                        {kinematicsResults.post && kinematicsResults.baseline && (
                          <td className="px-2 py-2.5 text-center whitespace-nowrap">
                            {deltaPostHealthy ? (
                              <span className={`px-2.5 py-1 text-xs font-bold rounded-lg border ${deltaPostHealthy.colorClass}`}>
                                {deltaPostHealthy.text}
                              </span>
                            ) : (
                              <span className="text-white/20 text-xs">{NA}</span>
                            )}
                          </td>
                        )}
                      </tr>
                    </React.Fragment>
                  );
                })}
                {activeResultPhases.length > 0 && (
                  <tr className="border-t border-white/[0.12] bg-white/[0.02]">
                    <td className="px-3 py-2.5" />
                    <td className="px-4 py-2.5 font-bold text-white/60 text-sm whitespace-nowrap">Analyzed arm</td>
                    <td className="px-3 py-2.5 font-light text-white/40 text-xs whitespace-nowrap">side</td>
                    {phases.filter((ph) => kinematicsResults[ph.k]).map((ph) => (
                      <td key={ph.k} className="px-2 py-2.5 text-center whitespace-nowrap">
                        <span className="text-white/75 font-mono text-xs font-semibold">
                          {armSideLabel(analyzedArmForPhase(kinematicsResults, ph.k))}
                        </span>
                      </td>
                    ))}
                    {kinematicsResults.pre && kinematicsResults.baseline && (
                      <td className="px-2 py-2.5 text-center text-white/20 text-xs">{NA}</td>
                    )}
                    {kinematicsResults.pre && kinematicsResults.post && (
                      <td className="px-2 py-2.5 text-center text-white/20 text-xs">{NA}</td>
                    )}
                    {hasKinTriple && (
                      <td className="px-2 py-2.5 text-center text-white/20 text-xs">{NA}</td>
                    )}
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Glass>
      )}

      {showResultsTable && activeResultPhases.some((ph) => getMovementProfile(kinematicsResults[ph.k]) || kinematicsResults[ph.k]?.movement_quality_index != null) && (
        <Glass className="p-4 sm:p-5">
          <p className="text-sm font-extrabold text-white/80 mb-1">Movement quality &amp; joint specs</p>
          <p className="text-[11px] text-white/45 mb-4 leading-relaxed">
            Fine motor (index path, micro-stops, pinch), forearm pronation/supination (3D palm normal or index–pinky 2D), shoulder abduction (both shoulders visible), plus flexion/elbow ? and ?/s. Re-analyze after updates. Side-only camera: abduction/rotation flags may show low reliability ? use oblique/frontal clips for rotation tasks.
          </p>
          <div className="space-y-4">
            {activeResultPhases.map((ph) => {
              const prof = getMovementProfile(kinematicsResults[ph.k]);
              if (!prof && kinematicsResults[ph.k]?.movement_quality_index == null) return null;
              const reliabilityNotes = [];
              if (prof?.shoulder_abduction_reliable === false) {
                reliabilityNotes.push("Shoulder abduction: limited (shoulders not well separated in view)");
              }
              if (prof?.forearm_rotation_reliable === false) {
                reliabilityNotes.push("Forearm rotation: limited (need index+pinky / 3D landmarks)");
              }
              return (
                <div key={ph.k} className={`rounded-xl border p-3 sm:p-4 ${phaseValueCls(ph.c)}`}>
                  <p className={`text-xs font-extrabold uppercase mb-3 ${phaseLabelCls(ph.c)}`}>{ph.l}</p>
                  {reliabilityNotes.length > 0 && (
                    <p className="text-[10px] text-amber-200/70 mb-3 leading-snug">{reliabilityNotes.join(" — ")}</p>
                  )}
                  <div className="space-y-4">
                    {MOVEMENT_PROFILE_GROUP_ORDER.map((groupId) => {
                      const fields = MOVEMENT_PROFILE_FIELDS.filter((f) => f.group === groupId);
                      const cells = fields
                        .map((f) => {
                          const val = resolveProfileMetric(kinematicsResults[ph.k], f.key, overlayData?.[ph.k]);
                          if (val == null && f.key !== "task_pattern") return null;
                          return (
                            <div key={f.key} className="rounded-lg border border-white/[0.06] bg-black/20 px-2.5 py-2">
                              <p className="text-[9px] font-bold text-white/45 leading-tight">{f.label}</p>
                              <p className="text-sm font-mono font-extrabold text-white/90 mt-0.5">
                                {formatProfileValue(f.key, val ?? NA)}
                                {f.unit ? <span className="text-[9px] font-normal text-white/35 ml-0.5">{f.unit}</span> : null}
                              </p>
                            </div>
                          );
                        })
                        .filter(Boolean);
                      if (!cells.length) return null;
                      return (
                        <div key={groupId}>
                          <p className="text-[10px] font-extrabold uppercase tracking-wide text-white/50 mb-2">
                            {MOVEMENT_PROFILE_GROUP_LABELS[groupId] || groupId}
                          </p>
                          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">{cells}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </Glass>
      )}

      {showResultsTable && activeResultPhases.some((ph) => (kinematicsResults[ph.k]?.task_phases || []).length > 0) && (
        <Glass className="p-4 sm:p-5">
          <p className="text-sm font-extrabold text-white/80 mb-1">Task phases &amp; variables</p>
          <p className="text-[11px] text-white/45 mb-4">
            Per-phase kinematics from detected movement bouts (reach, transport, return). Study table above still uses the primary reach window for Pre/Post/Healthy comparison.
          </p>
          <div className="space-y-5">
            {activeResultPhases.map((ph) => {
              const phases = kinematicsResults[ph.k]?.task_phases || [];
              if (!phases.length) return null;
              const taskLabel = kinematicsResults[ph.k]?.clinical_task_label || clinicalTaskById(kinematicsResults[ph.k]?.clinical_task).label;
              return (
                <div key={ph.k} className={`rounded-xl border p-3 sm:p-4 ${phaseValueCls(ph.c)}`}>
                  <p className={`text-xs font-extrabold uppercase mb-1 ${phaseLabelCls(ph.c)}`}>{ph.l}</p>
                  <p className="text-[11px] text-white/55 mb-3">{taskLabel}</p>
                  {phases.map((tp) => (
                    <div key={`${ph.k}-${tp.id}`} className="mb-4 last:mb-0">
                      <p className="text-[11px] font-bold text-white/75 mb-2">
                        {tp.label}
                        {tp.duration_sec != null ? (
                          <span className="text-white/40 font-normal ml-2">{tp.duration_sec}s</span>
                        ) : null}
                        {tp.task_window?.rom != null ? (
                          <span className="text-white/40 font-normal ml-2">ROM {tp.task_window.rom}</span>
                        ) : null}
                        {tp.expected_rom_ok === true ? (
                          <span className="text-emerald-400/80 font-normal ml-2">within expected ROM</span>
                        ) : null}
                        {tp.expected_rom_ok === false ? (
                          <span className="text-amber-300/80 font-normal ml-2">ROM outside expected range</span>
                        ) : null}
                      </p>
                      {TASK_PHASE_NOTES[tp.id] ? (
                        <p className="text-[10px] text-white/50 mb-2 leading-snug">{TASK_PHASE_NOTES[tp.id]}</p>
                      ) : null}
                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                        {TASK_PHASE_METRIC_KEYS.map((mk) => {
                          const val = tp.metrics?.[mk.key];
                          if (val == null) return null;
                          return (
                            <div key={mk.key} className="rounded-lg border border-white/[0.06] bg-black/20 px-2 py-1.5">
                              <p className="text-[9px] text-white/45">{mk.label}</p>
                              <p className="text-xs font-mono font-bold text-white/90">
                                {formatProfileValue(mk.key, val)}
                                {mk.unit ? <span className="text-[9px] text-white/35 ml-0.5">{mk.unit}</span> : null}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </Glass>
      )}

      {Object.keys(kinematicsResults).filter(k => kinematicsResults[k]?.velocity_profile).length >= 1 && (
        <Glass className="p-4 sm:p-5">
          <p className="text-sm font-extrabold text-white/80 mb-3">Combined Velocity Profile</p>
          <div
            className="w-full overflow-hidden rounded-xl border border-white/[0.08] bg-black/30 p-3 kin-phase-chart"
            dangerouslySetInnerHTML={{ __html: buildCombinedVelChart({
              pre: kinematicsResults.pre?.velocity_profile,
              post: kinematicsResults.post?.velocity_profile,
              baseline: kinematicsResults.baseline?.velocity_profile,
            }) }}
          />
        </Glass>
      )}

      {/* In-app video viewer ? stay inside PWA on iOS/iPad */}
      <AnimatePresence>
        {mediaPreview && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[99998] flex flex-col bg-black/95 backdrop-blur-sm"
            onClick={() => setMediaPreview(null)}
          >
            <div className="flex items-center justify-between px-4 py-3 flex-shrink-0 gap-2" onClick={(e) => e.stopPropagation()}>
              <p className="text-sm font-bold text-white/80 truncate">{mediaPreview.title}</p>
              <div className="flex items-center gap-2 shrink-0">
                <GBtn
                  variant="default"
                  onClick={() => downloadFile(mediaPreview.phase, "unified-download")}
                  className="!py-1.5 !px-3 text-xs"
                >
                  <Download className="w-4 h-4 mr-1" /> Save
                </GBtn>
                <GBtn variant="default" onClick={() => setMediaPreview(null)} className="!py-1.5 !px-3 text-xs">
                  <X className="w-4 h-4 mr-1" /> Close
                </GBtn>
              </div>
            </div>
            <div className="flex-1 flex items-center justify-center px-3 pb-6 min-h-0" onClick={(e) => e.stopPropagation()}>
              <video
                key={videoBlobs[mediaPreview.phase] || mediaPreview.url}
                src={videoBlobs[mediaPreview.phase] || mediaPreview.url}
                controls
                playsInline
                autoPlay
                preload="auto"
                className="w-full max-h-full rounded-xl bg-black"
                style={{ maxHeight: "calc(100dvh - 5rem)" }}
                onError={() => {
                  showToast("Validation video expired on server — please re-analyze", "error");
                  setMediaPreview(null);
                }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
});

// ??? Patient Database ?????????????????????????????????????????????????????????

const DatabaseSection = ({ fd, setFd, onLoadSession, showToast, isActive }) => {
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState("");
  const [confirm, setConfirm] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);

  const refreshPatients = useCallback(() => setPatients(loadPatients()), []);

  useEffect(() => {
    refreshPatients();
  }, [refreshPatients]);

  useEffect(() => {
    if (isActive) refreshPatients();
  }, [isActive, refreshPatients]);

  useEffect(() => {
    const onSynced = () => refreshPatients();
    window.addEventListener(PATIENTS_SYNC_EVENT, onSynced);
    return () => window.removeEventListener(PATIENTS_SYNC_EVENT, onSynced);
  }, [refreshPatients]);

  const persistList = useCallback((updated, message) => {
    const cleaned = savePatients(updated);
    setPatients(cleaned);
    setConfirm(null);
    if (message) showToast(message);
    postPatientsSync(cleaned).catch(() => {});
    backupToDrive(cleaned);
  }, [showToast]);

  const filtered = patients.filter((p) => {
    const q = search.toLowerCase();
    return (
      (p.demographics?.name || "").toLowerCase().includes(q) ||
      (p.demographics?.participantId || "").toLowerCase().includes(q)
    );
  });
  const intervention = filtered.filter((p) => !isArchivedPatient(p) && p.demographics?.group === "1");
  const control = filtered.filter((p) => !isArchivedPatient(p) && p.demographics?.group === "2");
  const ungrouped = filtered.filter((p) => !isArchivedPatient(p) && p.demographics?.group !== "1" && p.demographics?.group !== "2");
  const archived = filtered.filter(isArchivedPatient);
  const activeCount = patients.filter((p) => !isArchivedPatient(p)).length;

  const deletePatient = (id) => {
    persistList(patients.filter((p) => p._id !== id), "Patient record deleted");
  };

  const setArchived = (id, archivedFlag) => {
    const updated = patients.map((p) => (
      p._id === id
        ? { ...p, _archived: archivedFlag, _archivedAt: archivedFlag ? new Date().toISOString() : undefined }
        : p
    ));
    persistList(
      updated,
      archivedFlag ? "Moved to Archive" : "Restored from Archive"
    );
    // Drive: move patient folder under Archive/ (or restore); refresh Excel without archived rows.
    setTimeout(() => {
      rebuildDriveFromDatabase(updated, { showToast, waitMs: 120000 }).catch(() => {});
    }, 600);
  };

  const setGroup = (id, group) => {
    const updated = patients.map((p) => (
      p._id === id ? { ...p, demographics: { ...(p.demographics || {}), group } } : p
    ));
    persistList(updated, group === "1" ? "Moved to Intervention" : "Moved to Control");
    if (fd._loadedId === id) {
      setFd((prev) => ({ ...prev, demographics: { ...(prev.demographics || {}), group } }));
    }
  };

  const applyReorder = () => {
    const updated = reorderStudyIds(patients); // default start=101 (clinic convention)
    persistList(updated, "Study IDs reordered from 101");
    const curId = fd._loadedId;
    if (curId) {
      const cur = updated.find((p) => p._id === curId);
      if (cur?.demographics?.participantId) {
        setFd((prev) => ({
          ...prev,
          demographics: { ...(prev.demographics || {}), participantId: cur.demographics.participantId },
        }));
      }
    }
  };

  const nameDupes = nameDuplicateGroups(patients);
  const [rebuildingDrive, setRebuildingDrive] = useState(false);
  const applyMergeSameNames = () => {
    const before = patients.length;
    const updated = mergeSameNameDuplicates(patients);
    const removed = before - updated.length;
    persistList(
      updated,
      removed > 0
        ? `Merged ${removed} same-name duplicate(s) — kept preferred Study ID`
        : "No same-name duplicates to merge"
    );
    const curId = fd._loadedId || fd.demographics?.participantId;
    if (curId) {
      const cur = updated.find(
        (p) => p._id === curId || patientStudyId(p) === String(curId).trim()
      );
      if (cur) {
        setFd((prev) => ({
          ...prev,
          ...cur,
          _loadedId: cur._id,
          demographics: { ...(prev.demographics || {}), ...(cur.demographics || {}) },
        }));
      }
    }
    if (removed > 0) {
      setTimeout(() => {
        rebuildDriveFromDatabase(updated, { showToast }).catch(() => {});
      }, 800);
    }
  };

  const applyRebuildDrive = async () => {
    setConfirm(null);
    setRebuildingDrive(true);
    try {
      await rebuildDriveFromDatabase(patients, { showToast, waitMs: 180000 });
    } finally {
      setRebuildingDrive(false);
    }
  };

  const renderCard = (p, mode) => {
    const d = p.demographics || {};
    const hasPre = !!(p._hasPre || patientHasPhaseData(p, "pre"));
    const hasPost = !!(p._hasPost || patientHasPhaseData(p, "post"));
    return (
      <Glass key={patientStudyId(p) || p._id} className="p-4">
        <div className="flex items-start gap-4 flex-wrap">
          <div className={`w-10 h-10 rounded-xl border flex items-center justify-center flex-shrink-0 ${
            mode === "archive"
              ? "bg-white/[0.06] border-white/[0.08]"
              : mode === "control"
                ? "bg-rose-500/20 border-rose-400/20"
                : "bg-teal-500/20 border-teal-400/20"
          }`}>
            {mode === "archive" ? <Archive className="w-5 h-5 text-white/50" /> : <User className="w-5 h-5 text-white/80" />}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <p className="font-extrabold text-white text-sm">{d.name || "Unnamed Patient"}</p>
              <span className="text-xs font-mono text-white/40 bg-white/[0.06] px-2 py-0.5 rounded-lg border border-white/[0.04] truncate">
                {d.participantId || "No ID"}
              </span>
            </div>

            <div className="flex flex-wrap gap-2 text-[10px] text-white/40 mb-2">
              {d.age && <span>Age: {d.age}</span>}
              {d.sex && <span>{d.sex === "1" ? "Male" : "Female"}</span>}
              {d.strokeType && <span>{d.strokeType === "1" ? "Ischemic" : "Hemorrhagic"}</span>}
              {d.side && <span>{d.side === "1" ? "Left" : "Right"} side</span>}
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-[9px] font-bold px-2 py-1 rounded-full border ${
                hasPre ? "bg-sky-500/20 border-sky-400/30 text-sky-300" : "bg-white/[0.05] border-white/[0.04] text-white/25"
              }`}>
                {hasPre ? "Pre-Assessment" : "Pre missing"}
              </span>
              <span className={`text-[9px] font-bold px-2 py-1 rounded-full border ${
                hasPost ? "bg-emerald-500/20 border-emerald-400/30 text-emerald-300" : "bg-white/[0.05] border-white/[0.04] text-white/25"
              }`}>
                {hasPost ? "Post-Assessment" : "Post missing"}
              </span>
              <span className="text-[9px] text-white/25 ml-auto">Saved: {formatPatientSavedAt(p._savedAt)}</span>
            </div>

            {mode !== "archive" && (
              <div className="mt-2">
                <select
                  value={d.group === "1" || d.group === "2" ? d.group : ""}
                  onChange={(e) => e.target.value && setGroup(p._id, e.target.value)}
                  className="text-[11px] px-2 py-1.5 rounded-lg bg-white/[0.09] border border-white/[0.08] text-white/80"
                >
                  <option value="">Set group</option>
                  <option value="1">Intervention / AOMI</option>
                  <option value="2">Control</option>
                </select>
              </div>
            )}

            <div className="flex items-center gap-2 flex-shrink-0 flex-wrap mt-3">
              <GBtn variant="sky" onClick={() => onLoadSession(p)} className="text-xs px-3 py-2">
                <Edit3 className="w-3.5 h-3.5" /> Load
              </GBtn>
              {mode === "archive" ? (
                <GBtn variant="default" onClick={() => setArchived(p._id, false)} className="text-xs px-3 py-2">
                  <RotateCcw className="w-3.5 h-3.5" /> Restore
                </GBtn>
              ) : (
                <GBtn variant="default" onClick={() => setArchived(p._id, true)} className="text-xs px-3 py-2">
                  <Archive className="w-3.5 h-3.5" /> Archive
                </GBtn>
              )}
              {confirm === p._id ? (
                <div className="flex items-center gap-1.5">
                  <GBtn variant="rose" onClick={() => deletePatient(p._id)} className="text-xs px-3 py-2">
                    <Check className="w-3.5 h-3.5" /> Confirm Delete
                  </GBtn>
                  <GBtn variant="default" onClick={() => setConfirm(null)} className="text-xs px-3 py-2">
                    <X className="w-3.5 h-3.5" />
                  </GBtn>
                </div>
              ) : (
                <GBtn variant="default" onClick={() => setConfirm(p._id)} className="text-xs px-3 py-2">
                  <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                </GBtn>
              )}
            </div>
          </div>
        </div>
      </Glass>
    );
  };

  const section = (title, items, mode, emptyHint) => (
    <div className="space-y-3 min-w-0">
      <div className="flex items-center gap-2 px-1">
        <p className={`text-xs font-extrabold uppercase tracking-widest ${
          mode === "control" ? "text-rose-300" : mode === "archive" ? "text-white/45" : "text-teal-300"
        }`}>{title}</p>
        <span className="text-[10px] font-bold text-white/35">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="text-[11px] text-white/25 px-1">{emptyHint}</p>
      ) : items.map((p) => renderCard(p, mode))}
    </div>
  );

  return (
    <div className="space-y-5">
      <SH icon={Database} en={archiveOpen ? "Archive" : "Patient Database"} tr="" badge={archiveOpen ? `${archived.length}` : `${activeCount} Records`} />

      <Glass className="p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex-1 min-w-0 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or Participant ID"
              className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-white/[0.09] border border-white/[0.06] text-white placeholder-white/15 text-sm font-light focus:outline-none focus:bg-white/[0.06] transition-all"
            />
            {search && (
              <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/70 transition-all">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <GBtn variant="default" disabled={syncing} onClick={async () => {
            setSyncing(true);
            try {
              const { ok, patients: merged } = await syncPatientsWithServer({ showToast });
              if (ok) {
                setPatients(merged);
                const curId = fd._loadedId || fd.demographics?.participantId;
                if (curId) {
                  const cur = merged.find((p) => (p._id || p.demographics?.participantId) === curId);
                  if (cur) {
                    setFd((prev) => {
                      const next = { ...prev, ...cur };
                      const incoming = cur.kinematics?.analysisResults;
                      const local = prev.kinematics?.analysisResults;
                      const incomingEmpty = !incoming || typeof incoming !== "object" || Object.keys(incoming).length === 0;
                      if (incomingEmpty && local && typeof local === "object" && Object.keys(local).length > 0) {
                        next.kinematics = { ...(cur.kinematics || prev.kinematics || {}), analysisResults: local };
                      }
                      return next;
                    });
                    if (cur.kinematics?.analysisResults) {
                      localStorage.setItem(KIN_LS_KEY, JSON.stringify(cur.kinematics.analysisResults));
                    }
                  }
                }
              } else {
                refreshPatients();
              }
            } finally {
            setSyncing(false);
            }
          }}>
            <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} /> {syncing ? "Syncing..." : "Sync"}
          </GBtn>
          <GBtn
            variant="sky"
            disabled={syncing}
            onClick={async () => {
              setSyncing(true);
              try {
                const { ok, patients: merged } = await restorePatientsFromDriveNow({ showToast });
                if (ok) setPatients(merged);
                else refreshPatients();
              } finally {
                setSyncing(false);
              }
            }}
          >
            <HardDrive className={`w-4 h-4 ${syncing ? "animate-pulse" : ""}`} /> Restore from Drive
          </GBtn>
          {confirm === "reorder" ? (
            <div className="flex items-center gap-1.5">
              <GBtn variant="sky" onClick={applyReorder} className="text-xs px-3 py-2">
                <Check className="w-3.5 h-3.5" /> Confirm reorder 101+
              </GBtn>
              <GBtn variant="default" onClick={() => setConfirm(null)} className="text-xs px-3 py-2">
                <X className="w-3.5 h-3.5" />
              </GBtn>
            </div>
          ) : (
            <GBtn variant="default" disabled={activeCount === 0} onClick={() => setConfirm("reorder")}>
              Reorder Study IDs
            </GBtn>
          )}
          {confirm === "mergeNames" ? (
            <div className="flex items-center gap-1.5">
              <GBtn variant="sky" onClick={applyMergeSameNames} className="text-xs px-3 py-2">
                <Check className="w-3.5 h-3.5" /> Confirm merge names
              </GBtn>
              <GBtn variant="default" onClick={() => setConfirm(null)} className="text-xs px-3 py-2">
                <X className="w-3.5 h-3.5" />
              </GBtn>
            </div>
          ) : (
            <GBtn
              variant="default"
              disabled={nameDupes.length === 0}
              onClick={() => setConfirm("mergeNames")}
              title={nameDupes.length ? "Merge rows that share the same full name" : "No same-name duplicates"}
            >
              Merge same names{nameDupes.length ? ` (${nameDupes.length})` : ""}
            </GBtn>
          )}
          <GBtn
            variant="default"
            onClick={() => { openConnectDrive(); }}
            title="Reconnect Google Drive (same window — keeps PWA session)"
          >
            <HardDrive className="w-4 h-4" />
            Connect Drive
          </GBtn>
          {confirm === "rebuildDrive" ? (
            <div className="flex items-center gap-1.5">
              <GBtn variant="sky" onClick={applyRebuildDrive} className="text-xs px-3 py-2">
                <Check className="w-3.5 h-3.5" /> Confirm rebuild Drive
              </GBtn>
              <GBtn variant="default" onClick={() => setConfirm(null)} className="text-xs px-3 py-2">
                <X className="w-3.5 h-3.5" />
              </GBtn>
            </div>
          ) : (
            <GBtn
              variant="default"
              disabled={rebuildingDrive || activeCount === 0}
              onClick={() => setConfirm("rebuildDrive")}
              title="Align Google Drive folders 1:1 with this patient list (merge alias folders, keep files)"
            >
              <RefreshCw className={`w-4 h-4 ${rebuildingDrive ? "animate-spin" : ""}`} />
              {rebuildingDrive ? "Rebuilding Drive…" : "Rebuild Drive from Database"}
            </GBtn>
          )}
          <button
            type="button"
            onClick={() => setArchiveOpen((v) => !v)}
            className={`relative w-11 h-11 rounded-xl border flex items-center justify-center flex-shrink-0 ${
              archiveOpen ? "bg-amber-400/20 border-amber-300/40" : "bg-white/[0.09] border-white/[0.08]"
            }`}
            aria-label="Archive"
          >
            <Archive className={`w-5 h-5 ${archiveOpen ? "text-amber-200" : "text-white/70"}`} />
            {patients.filter(isArchivedPatient).length > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-amber-400 text-[9px] font-extrabold text-slate-900 flex items-center justify-center">
                {patients.filter(isArchivedPatient).length}
              </span>
            )}
          </button>
        </div>
        {nameDupes.length > 0 && (
          <div className="mt-3 rounded-xl border border-amber-400/25 bg-amber-400/10 px-3 py-2.5 text-[11px] text-amber-100/90 leading-relaxed">
            <p className="font-semibold text-amber-100 mb-1">
              Same name, different Study IDs (legacy duplicates) — {nameDupes.length} name(s)
            </p>
            <p className="text-amber-100/70 mb-1">
              Use Merge same names (prefers 101+), then Sync or Rebuild Drive from Database to merge alias folders on Google Drive (files moved first; empty aliases trashed).
            </p>
            <ul className="list-disc pl-4 space-y-0.5 text-amber-50/80">
              {nameDupes.slice(0, 8).map((g) => (
                <li key={g.key}>{g.name}: Study IDs {g.ids.join(", ")}</li>
              ))}
              {nameDupes.length > 8 && <li>and {nameDupes.length - 8} more</li>}
            </ul>
          </div>
        )}
      </Glass>

      {archiveOpen ? (
        <div className="space-y-3">
          {archived.length === 0 ? (
            <Glass className="p-12 text-center">
              <Archive className="w-16 h-16 text-white/10 mx-auto mb-4" />
              <p className="text-white/50 font-semibold text-lg mb-2">No archived sessions</p>
              <p className="text-white/25 text-sm">Archive a session from the database to keep it without counting it in the study.</p>
            </Glass>
          ) : archived.map((p) => renderCard(p, "archive"))}
        </div>
      ) : filtered.filter((p) => !isArchivedPatient(p)).length === 0 ? (
        <Glass className="p-12 text-center">
          <Database className="w-16 h-16 text-white/10 mx-auto mb-4" />
          <p className="text-white/50 font-semibold text-lg mb-2">
            {search ? "No patients match your search" : "No patient records yet"}
          </p>
          <p className="text-white/25 text-sm">Save a session from any assessment tab, then tap Sync to share across devices.</p>
        </Glass>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 items-start">
            {section("Intervention / AOMI", intervention, "intervention", "No intervention sessions")}
            {section("Control", control, "control", "No control sessions")}
          </div>
          {ungrouped.length > 0 && section("Ungrouped", ungrouped, "ungrouped", "")}
        </div>
      )}
    </div>
  );
};


// ??? Report Helpers ???????????????????????????????????????????????????????????

function buildSummaryRows(fd) {
  const rows = [];

  const lowerIsBetter = (name) => {
    const n = (name || "").toLowerCase();
    return n.includes("pain") || n.includes("anxiety") || n.includes("distress")
      || n.includes("fear") || n.includes("confusion") || n.includes("sad")
      || n.includes("fatigue") || n.includes("tension") || n.includes("tense");
  };

  const calcDelta = (pre, post, metricName) => {
    const p = parseFloat(pre);
    const q = parseFloat(post);
    if (isNaN(p) || isNaN(q)) return NA;
    const d = q - p;
    if (d === 0) return "0.00";
    return (d > 0 ? "+" : "") + d.toFixed(2);
  };

  const v = (x) => (x !== undefined && x !== null && x !== "" ? String(x) : NA);

  // VAS
  const vas = fd.vas || {};
  [
    { k:"rest", en:"Pain at Rest" },
    { k:"activity", en:"Pain During Activity" },
  ].forEach((item) => {
    const pre = v(vas[item.k]?.pre);
    const post = v(vas[item.k]?.post);
    const pNum = parseFloat(pre), qNum = parseFloat(post);
    const improving = (!isMissing(pre) && !isMissing(post))
      ? (pNum === qNum ? null : (lowerIsBetter(item.en) ? pNum > qNum : qNum > pNum))
      : null;
    rows.push({ tool:"VAS", metric:item.en, pre, post, delta:calcDelta(pre, post, item.en), improving });
  });

  // VAMS-4
  const vams = fd.vams || {};
  [
    { k:"happy", en:"VAMS Happy" },
    { k:"sad", en:"VAMS Sad" },
    { k:"calm", en:"VAMS Calm" },
    { k:"tense", en:"VAMS Tense" },
  ].forEach((item) => {
    const pre = v(vams[item.k]?.pre);
    const post = v(vams[item.k]?.post);
    const pNum = parseFloat(pre), qNum = parseFloat(post);
    const improving = (!isMissing(pre) && !isMissing(post))
      ? (pNum === qNum ? null : (lowerIsBetter(item.en) ? pNum > qNum : qNum > pNum))
      : null;
    rows.push({ tool:"VAMS", metric:item.en, pre, post, delta:calcDelta(pre, post, item.en), improving });
  });

  // Motor Change
  const mc = fd.motorchange || {};
  MOTOR_ITEMS.forEach((item) => {
    const val = v(mc[item.key]);
    rows.push({
      tool:"Muscle Control",
      metric:item.en,
      pre: item.phase === "pre" ? val : NA,
      post: item.phase === "post" ? val : NA,
      delta: NA
    });
  });

  // KVIQ
  const kgia = fd.kgia || {};
  KGIA_MOVEMENTS.forEach((mov, mi) =>
    KGIA_TYPES.forEach((t) => {
      const pre = v(kgia[`${mi}_${t.key}`]?.once);
      const post = v(kgia[`${mi}_${t.key}`]?.sonra);
      const improving = (!isMissing(pre) && !isMissing(post)) ? (parseFloat(pre) === parseFloat(post) ? null : parseFloat(post) > parseFloat(pre)) : null;
      rows.push({ tool:"KVIQ", metric:`${t.en}: ${mov.en}`, pre, post, delta:calcDelta(pre, post), improving });
    })
  );

  // WMFT
  const wmft = fd.wmft || {};
  WMFT_ITEMS.forEach((t) => {
    const preT = v(wmft[t.id]?.pre?.time);
    const postT = v(wmft[t.id]?.post?.time);
    const preR = v(wmft[t.id]?.pre?.rating);
    const postR = v(wmft[t.id]?.post?.rating);

    const improvingT = (!isMissing(preT) && !isMissing(postT)) ? (parseFloat(preT) === parseFloat(postT) ? null : parseFloat(preT) > parseFloat(postT)) : null;
    const improvingR = (!isMissing(preR) && !isMissing(postR)) ? (parseFloat(preR) === parseFloat(postR) ? null : parseFloat(postR) > parseFloat(preR)) : null;
    rows.push({ tool:"WMFT", metric:`${t.en} — Time (sec)`, pre:preT, post:postT, delta:calcDelta(preT, postT), improving: improvingT });
    rows.push({ tool:"WMFT", metric:`${t.en} — Ability Rating (0–5)`, pre:preR, post:postR, delta:calcDelta(preR, postR), improving: improvingR });
  });

  const bbt = fd.bbt || {};
  const bbtPreP = v(bbt.pre?.pareticBlocks);
  const bbtPostP = v(bbt.post?.pareticBlocks);
  const bbtPreU = v(bbt.pre?.unaffectedBlocks);
  const bbtPostU = v(bbt.post?.unaffectedBlocks);
  const bbtImpP = (!isMissing(bbtPreP) && !isMissing(bbtPostP))
    ? (parseFloat(bbtPreP) === parseFloat(bbtPostP) ? null : parseFloat(bbtPostP) > parseFloat(bbtPreP))
    : null;
  rows.push({ tool:"BBT", metric:"Paretic hand — blocks / 60s", pre:bbtPreP, post:bbtPostP, delta:calcDelta(bbtPreP, bbtPostP), improving: bbtImpP });
  if (!isMissing(bbtPreU) || !isMissing(bbtPostU)) {
    const bbtImpU = (!isMissing(bbtPreU) && !isMissing(bbtPostU))
      ? (parseFloat(bbtPreU) === parseFloat(bbtPostU) ? null : parseFloat(bbtPostU) > parseFloat(bbtPreU))
      : null;
    rows.push({ tool:"BBT", metric:"Unaffected hand — blocks / 60s (optional)", pre:bbtPreU, post:bbtPostU, delta:calcDelta(bbtPreU, bbtPostU), improving: bbtImpU });
  }

  // Kinematics (video overlay metrics ? same source as Kinematic Lab)
  const krLive = loadLiveKinResults(fd);
  const kinDisplay = orderedKinematicVars().map((v) => ({
    k: v.key,
    en: v.label,
    dir: v.dir,
  }));
  kinDisplay.forEach((item) => {
    const preRaw = resolveKinMetricValue(krLive.pre, item.k);
    const postRaw = resolveKinMetricValue(krLive.post, item.k);
    const pre = isPanelTableKey(item.k)
      ? formatPanelAlignedKinValue(item.k, preRaw, krLive.pre?.overlay_metrics)
      : (preRaw != null ? formatKinValue(item.k, preRaw) : NA);
    const post = isPanelTableKey(item.k)
      ? formatPanelAlignedKinValue(item.k, postRaw, krLive.post?.overlay_metrics)
      : (postRaw != null ? formatKinValue(item.k, postRaw) : NA);
    const pNum = parseFloat(pre), qNum = parseFloat(post);
    const improving = (!isMissing(pre) && !isMissing(post))
      ? (pNum === qNum ? null : (item.dir === "lower" ? pNum > qNum : qNum > pNum))
      : null;
    rows.push({ tool:"Kinematics", metric:item.en, pre, post, delta:calcDelta(pre, post, item.en), improving });
  });

  return rows;
}

// ??? SPSS Export Helper ???????????????????????????????????????????????????????

function buildSPSSData(fd) {
  const row = buildMasterRow(fd, WMFT_ITEMS, KGIA_MOVEMENTS, IPAQ_ACTS);
  return row ? [row] : [];
}

// ??? Report Section ???????????????????????????????????????????????????????????

const ReportSection = ({ fd, onChange, showToast }) => {
  const d = fd.demographics || {};
  const rows = buildSummaryRows(fd);
  const tools = Array.from(new Set(rows.map((r) => r.tool)));
  const kinRows = Array.isArray(fd.kinematics?.uploadedData) ? fd.kinematics.uploadedData : [];
  const kinCharts = Array.isArray(fd.kinematics?.chartImages) ? fd.kinematics.chartImages : [];

  // Build kinematics data from video analysis results (same source as Kinematic Lab)
  const buildVideoKinRows = () => {
    const kr = loadLiveKinResults(fd);
    if (Object.keys(kr).length === 0) return null;
    const phaseLabels = { pre: "Pre", post: "Post", baseline: "Healthy side" };
    const vars = orderedKinematicVars().map((v) => ({
      key: v.key,
      label: `${v.label}${v.dir === "higher" ? " \u2191" : v.dir === "lower" ? " \u2193" : ""}`,
      unit: v.unit === "count" ? "" : v.unit,
      dir: v.dir,
    }));
    const phases = ["pre", "post", "baseline"].filter((p) => kr[p]);
    if (phases.length === 0) return null;

    const headers = ["Variable", "Unit", ...phases.map((p) => phaseLabels[p] || p)];
    const body = vars.map((v) => {
      const row = [v.label, v.unit];
      phases.forEach((p) => {
        const raw = resolveKinMetricValue(kr[p], v.key);
        row.push(
          isPanelTableKey(v.key)
            ? formatPanelAlignedKinValue(v.key, raw, kr[p]?.overlay_metrics)
            : formatKinValue(v.key, raw),
        );
      });
      return row;
    });
    return { headers, body, varMeta: vars, phases, kr };
  };

  const kinDirectionMap = (name) => {
    const n = (name || "").toLowerCase();
    if (n.includes("pause")) return "lower";
    if (n.includes("nsub")) return "lower";

    if (n.includes("trunk") && !n.includes("palm")) return "lower";
    if (n.includes("trunk") && n.includes("palm")) return "lower";
    if (n.includes("path") && n.includes("eff")) return "lower";
    if (n.includes("duration")) return "lower";
    if (n.includes("shoulder")) return "none";
    if (n.includes("lateral")) return "higher";
    if (n.includes("peak")) return "higher";
    if (n.includes("mean")) return "higher";
    if (n.includes("elbow")) return "higher";
    if (n.includes("range")) return "higher";
    return "higher";
  };
  
  const calcKinDelta = (pre, post) => {
    const p = parseFloat(pre);
    const q = parseFloat(post);
    if (isNaN(p) || isNaN(q)) return NA;
    const delta = q - p;
    return (delta >= 0 ? "+" : "") + delta.toFixed(2);
  };

  const toolColor = {
    VAS: "text-sky-300 bg-sky-500/10 border-sky-400/20",
    VAMS: "text-indigo-300 bg-indigo-500/10 border-indigo-400/20",
    "Muscle Control": "text-teal-300 bg-teal-500/10 border-teal-400/20",

    KVIQ: "text-cyan-300 bg-cyan-500/10 border-cyan-400/20",
    WMFT: "text-amber-300 bg-amber-500/10 border-amber-400/20",
    BBT: "text-orange-300 bg-orange-500/10 border-orange-400/20",
    Kinematics: "text-rose-300 bg-rose-500/10 border-rose-400/20",
  };

  // ?? Glassmorphism HTML Report (print ? PDF) ??
  const exportGlassReport = () => {
    try {
    const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;" }[c]));

    const buildToolInterp = (tool, trows) => {
      const items = trows.filter((r) => r.delta !== "\u2014");
      const en = []; const tr = [];
      if (tool === "VAS") {
        const imp = items.filter((r) => r.improving === true).length;
        const wors = items.filter((r) => r.improving === false).length;
        if (imp && !wors) { en.push("Pain decreased"); tr.push("Ağrı azaldı"); }
        else if (wors && !imp) { en.push("Pain increased"); tr.push("Ağrı arttı"); }
        else if (imp && wors) { en.push("Mixed pain results"); tr.push("Karışık ağrı sonuçları"); }
        else { en.push("Pain stable"); tr.push("Ağrı sabit"); }
      } else if (tool === "VAMS") {
        const pos = ["Happy","Calm"]; const neg = ["Sad","Tense"];
        const posUp = items.filter((r) => pos.some((n) => r.metric.includes(n)) && r.improving).length;
        const negDown = items.filter((r) => neg.some((n) => r.metric.includes(n)) && r.improving).length;
        if (posUp) { en.push("Positive mood improved"); tr.push("Olumlu ruh hali iyileşti"); }
        if (negDown) { en.push("Negative mood decreased"); tr.push("Olumsuz ruh hali azaldı"); }
        if (!en.length) { en.push("Mood stable"); tr.push("Ruh hali sabit"); }
      } else if (tool === "Muscle Control") {
        const preVal = trows.find(r => !isMissing(r.pre))?.pre;
        const postVal = trows.find(r => !isMissing(r.post))?.post;
        if (preVal && postVal && parseFloat(postVal) > parseFloat(preVal)) { en.push("Muscle control improved"); tr.push("Kas kontrolü iyileşti"); }
        else if (preVal && postVal && parseFloat(postVal) < parseFloat(preVal)) { en.push("Muscle control declined"); tr.push("Kas kontrolü azaldı"); }
        else if (preVal || postVal) { en.push("Muscle control stable"); tr.push("Kas kontrolü sabit"); }
      } else if (tool === "KVIQ") {
        const imp = items.filter((r) => r.improving).length;
        const tot = items.length;
        if (imp > tot / 2) { en.push("Imagery improved in most items"); tr.push("Çoğu öğede imgeleme iyileşti"); }
        else if (imp > 0) { en.push("Imagery improved in some items"); tr.push("Bazı öğelerde imgeleme iyileşti"); }
        else { en.push("Imagery stable"); tr.push("İmgeleme sabit"); }
      } else if (tool === "WMFT") {
        const time = items.filter((r) => r.metric.includes("Time"));
        const rate = items.filter((r) => r.metric.includes("Rating"));
        if (time.some((r) => r.improving)) { en.push("Faster task time"); tr.push("Daha hızlı görev süresi"); }
        if (time.some((r) => r.improving === false)) { en.push("Slower task time"); tr.push("Daha yavaş görev süresi"); }
        if (rate.some((r) => r.improving)) { en.push("Functional ability improved"); tr.push("Fonksiyonel yetenek iyileşti"); }
        if (rate.some((r) => r.improving === false)) { en.push("Functional ability declined"); tr.push("Fonksiyonel yetenek azaldı"); }
        if (!en.length && items.length) { en.push("No notable change in WMFT"); tr.push("WMFT'de kayda değer değişiklik yok"); }
      } else if (tool === "BBT") {
        const paretic = items.find((r) => r.metric.includes("Paretic"));
        if (paretic?.improving === true) { en.push("More blocks transferred (paretic hand)"); tr.push("Etkilenen elde daha fazla blok"); }
        else if (paretic?.improving === false) { en.push("Fewer blocks transferred (paretic hand)"); tr.push("Etkilenen elde daha az blok"); }
        else if (paretic) { en.push("BBT count stable"); tr.push("BBT skoru sabit"); }
      } else if (tool === "Kinematics") {
        const imp = items.filter((r) => r.improving).length;
        const tot = items.length;
        if (imp > tot / 2) { en.push("Kinematics improved"); tr.push("Kinematik iyileşti"); }
        else if (imp > 0) { en.push("Kinematics partially improved"); tr.push("Kinematik kısmen iyileşti"); }
        else if (tot > 0) { en.push("Kinematics stable"); tr.push("Kinematik sabit"); }
      }
      if (!en.length) return "";
      return `<div class="tool-interp">${en.join(", ")} / ${tr.join(", ")}</div>`;
    };

    const toolMeta = {
      "VAS":            { label: "Pain Scale (VAS) / Ağrı Skalası",            color: "#800020", bg: "#fdf2f4" },
      "VAMS":           { label: "Mood Scale (VAMS-4) / Ruh Hali",             color: "#0ea5e9", bg: "#f0f9ff" },
      "Muscle Control": { label: "Muscle Control Scale / Kas Kontrolü",        color: "#10b981", bg: "#ecfdf5" },
      "KVIQ":           { label: "Motor Imagery (KVIQ) / Motor İmgeleme",      color: "#0d9488", bg: "#f0fdfa" },
      "WMFT":           { label: "Wolf Motor Function (WMFT) / Motor Fonksiyon",color: "#0ea5e9", bg: "#ecfeff" },
      "BBT":            { label: "Box & Block Test (BBT) / Kutu Blok Testi",     color: "#ea580c", bg: "#fff7ed" },
      "Kinematics":     { label: "Kinematic Analysis / Kinematik Analiz",        color: "#f43f5e", bg: "#fff1f2" },
    };

    // group rows
    const grouped = {};
    rows.forEach((r) => { (grouped[r.tool] = grouped[r.tool] || []).push(r); });

    const buildSummaryInterp = () => {
      const all = [];
      Object.entries(grouped).forEach(([tool, trows]) => {
        const text = buildToolInterp(tool, trows);
        if (text) all.push(`<p class="sum-item"><span class="sum-badge" style="background:${(toolMeta[tool] || toolMeta.VAS).color}88">${esc(tool)}</span> ${text.replace(/<\/?div[^>]*>/g, "").trim()}</p>`);
      });
      if (!all.length) return "";
      return `<div class="singlecol pagebreak"><div class="card" style="border-left:6px solid #0d9488"><div class="badge" style="background:#0d948888;font-size:11px;padding:5px 18px">Summary / Özet</div>${all.join("")}</div></div>`;
    };

    const buildNarrativeSummary = () => {
      const sections = [];
      const trendWord = (v, better, worse) => v > 0 ? better : v < 0 ? worse : "remained stable";

      Object.entries(grouped).forEach(([tool, trows]) => {
        if (tool === "VAS") {
          const items = trows.filter(r => !isMissing(r.delta) && r.delta !== "\u2014" && !isMissing(r.pre) && !isMissing(r.post));
          if (!items.length) return;
          const parts = items.map(r => {
            const p = parseFloat(r.pre), q = parseFloat(r.post);
            const d = q - p;
            const trend = trendWord(-d, "decreased (improvement)", "increased (worsening)");
            return `${esc(r.metric)} went from ${r.pre} to ${r.post} (Δ ${r.delta}), indicating pain ${trend}`;
          });
          sections.push(`<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0"><strong style="color:#0d9488">Pain Scale (VAS):</strong> ${parts.join("; ")}.</p>`);
          return;
        }

        if (tool === "VAMS") {
          const items = trows.filter(r => !isMissing(r.delta) && r.delta !== "\u2014" && !isMissing(r.pre) && !isMissing(r.post));
          if (!items.length) return;
          const positive = ["Happy","Calm"]; const negative = ["Sad","Tense"];
          const posItems = items.filter(r => positive.some(n => r.metric.includes(n)));
          const negItems = items.filter(r => negative.some(n => r.metric.includes(n)));
          const parts = [];
          if (posItems.length) {
            const trends = posItems.map(r => `${r.pre}→${r.post} (Δ ${r.delta})`).join(", ");
            parts.push(`positive moods (${trends})`);
          }
          if (negItems.length) {
            const trends = negItems.map(r => `${r.pre}→${r.post} (Δ ${r.delta})`).join(", ");
            parts.push(`negative moods (${trends})`);
          }
          sections.push(`<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0"><strong style="color:#0ea5e9">Mood Scale (VAMS-4):</strong> ${parts.join("; ")}.</p>`);
          return;
        }

        if (tool === "Muscle Control") {
          const preRow = trows.find(r => !isMissing(r.pre));
          const postRow = trows.find(r => !isMissing(r.post));
          const preVal = preRow?.pre, postVal = postRow?.post;
          if (!preVal || !postVal) return;
          const d = parseFloat(postVal) - parseFloat(preVal);
          const trend = trendWord(d, "improved", "declined");
          sections.push(`<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0"><strong style="color:#10b981">Muscle Control:</strong> The participant's perceived muscle control changed from ${preVal} to ${postVal} (Δ ${d > 0 ? "+" : ""}${d.toFixed(2)}), indicating the feeling of control has ${trend}.</p>`);
          return;
        }

        if (tool === "KVIQ") {
          const items = trows.filter(r => !isMissing(r.delta) && r.delta !== "\u2014" && !isMissing(r.pre) && !isMissing(r.post));
          if (!items.length) return;
          const imp = items.filter(r => r.improving === true).length;
          const wors = items.filter(r => r.improving === false).length;
          const total = items.length;
          let summary;
          if (imp > total / 2) summary = `Most imagery items improved`;
          else if (imp > 0 && wors > 0) summary = `Mixed imagery results`;
          else summary = `Imagery remained stable`;
          const vis = items.filter(r => r.metric.startsWith("Visual"));
          const kin = items.filter(r => r.metric.startsWith("Kinesthetic"));
          const visImp = vis.filter(r => r.improving === true).length;
          const kinImp = kin.filter(r => r.improving === true).length;
          const details = [];
          if (vis.length) details.push(`visual imagery: ${visImp}/${vis.length} items improved`);
          if (kin.length) details.push(`kinesthetic imagery: ${kinImp}/${kin.length} items improved`);
          sections.push(`<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0"><strong style="color:#0d9488">Motor Imagery (KVIQ):</strong> ${summary}. In detail, ${details.join("; ")}.</p>`);
          return;
        }

        if (tool === "WMFT") {
          const items = trows.filter(r => !isMissing(r.delta) && r.delta !== "\u2014" && !isMissing(r.pre) && !isMissing(r.post));
          if (!items.length) return;
          const timeItems = items.filter(r => r.metric.includes("Time"));
          const rateItems = items.filter(r => r.metric.includes("Rating"));
          const parts = [];
          if (timeItems.length) {
            const faster = timeItems.filter(r => r.improving === true).length;
            const slower = timeItems.filter(r => r.improving === false).length;
            parts.push(`task time: ${faster} faster, ${slower} slower`);
          }
          if (rateItems.length) {
            const up = rateItems.filter(r => r.improving === true).length;
            const down = rateItems.filter(r => r.improving === false).length;
            parts.push(`functional rating: ${up} improved, ${down} declined`);
          }
          sections.push(`<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0"><strong style="color:#0ea5e9">Wolf Motor Function (WMFT):</strong> ${parts.join("; ")}.</p>`);
          return;
        }

        if (tool === "BBT") {
          const paretic = trows.find(r => r.metric.includes("Paretic") && !isMissing(r.pre) && !isMissing(r.post));
          if (!paretic) return;
          const preN = parseFloat(paretic.pre);
          const postN = parseFloat(paretic.post);
          if (isNaN(preN) || isNaN(postN)) return;
          const dir = postN > preN ? "increased" : postN < preN ? "decreased" : "was unchanged";
          sections.push(`<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0"><strong style="color:#ea580c">Box & Block Test (BBT):</strong> Paretic-hand blocks ${dir} from ${preN} to ${postN} in ${BBT_TEST_SECONDS} seconds.</p>`);
          return;
        }

        if (tool === "Kinematics") {
          const items = trows.filter(r => !isMissing(r.delta) && r.delta !== "\u2014" && !isMissing(r.pre) && !isMissing(r.post));
          if (!items.length) return;
          const improved = items.filter(r => r.improving === true).map(r => r.metric);
          const worsened = items.filter(r => r.improving === false).map(r => r.metric);
          const parts = [];
          if (improved.length) parts.push(`improved metrics: ${improved.join(", ")}`);
          if (worsened.length) parts.push(`declining metrics: ${worsened.join(", ")}`);
          sections.push(`<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0"><strong style="color:#f43f5e">Kinematic Analysis:</strong> ${improved.length} of ${items.length} kinematic variables showed improvement. ${parts.join("; ")}.</p>`);
          return;
        }
      });

      if (!sections.length) return "";
      return `<div class="singlecol pagebreak"><div class="card" style="border-left:6px solid #0d9488"><div class="badge" style="background:#0d948888;font-size:11px;padding:5px 18px">Clinical Narrative / Klinik Anlatım</div><div style="padding:4px 0">${sections.join("")}</div></div></div>`;
    };
    const deltaCell = (r) => {
      if (!r.delta || r.delta === "\u2014") return `<span class="delta neutral">\u2014</span>`;
      const cls = r.improving === true ? "up" : r.improving === false ? "down" : "neutral";
      return `<span class="delta ${cls}">${esc(r.delta)}</span>`;
    };

    let toolSections = "";
    Object.entries(grouped).filter(([tool]) => tool !== "Kinematics").forEach(([tool, trows]) => {
      const hasData = trows.some(r => !isMissing(r.pre) || !isMissing(r.post));
      if (!hasData) return;
      const meta = toolMeta[tool] || { label: tool, color: "#0d9488" };
      const interp = buildToolInterp(tool, trows);
      let body;
      if (tool === "Muscle Control") {
        const preRow = trows.find(r => !isMissing(r.pre));
        const postRow = trows.find(r => !isMissing(r.post));
        const preVal = preRow ? preRow.pre : NA;
        const postVal = postRow ? postRow.post : NA;
        const delta = !isMissing(preVal) && !isMissing(postVal)
          ? (parseFloat(postVal) - parseFloat(preVal)).toFixed(2)
          : NA;
        body = `<tr><td class="metric">Felt Difference</td><td class="num">${preVal}</td><td class="num">${postVal}</td><td class="num">${delta}</td></tr>`;
      } else {
        body = trows.map((r) => `
        <tr>
          <td class="metric">${esc(r.metric)}</td>
          <td class="num">${esc(r.pre)}</td>
          <td class="num">${esc(r.post)}</td>
          <td class="num">${deltaCell(r)}</td>
        </tr>`).join("");
      }
      toolSections += `
        <div class="card" style="background:${meta.bg}cc;backdrop-filter:blur(40px) saturate(180%);-webkit-backdrop-filter:blur(40px) saturate(180%);border:1px solid rgba(255,255,255,0.3);border-radius:1rem;box-shadow:0 20px 40px -8px rgba(0,0,0,0.08);padding:18px 22px;margin-bottom:20px;">
          <div class="badge" style="background:${meta.color}88">${esc(meta.label)}</div>
          <div class="tblwrap">
          <table>
            <thead><tr style="background:${meta.color}88;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)">
              <th>Metric / Task</th><th>Pre</th><th>Post</th><th>Change</th>
            </tr></thead>
            <tbody>${body}</tbody>
          </table>
          </div>
          ${interp}
        </div>`;
    });

    // combined velocity profile chart
    const kr2 = loadLiveKinResults(fd);
    const velChart = buildCombinedVelChart({
      pre: kr2.pre?.velocity_profile,
      post: kr2.post?.velocity_profile,
      baseline: kr2.baseline?.velocity_profile,
    }, true);
    let velSection = velChart ? `<div class="singlecol"><div class="card vel-chart-card"><div class="badge" style="background:#0d948888">Combined Velocity Profile</div><div class="vel-chart-wrap">${velChart}</div></div></div>` : "";

    // video kinematics
    const videoKin = buildVideoKinRows();
    let videoSection = "";
    if (videoKin) {
      const fBody = videoKin.body.filter((row) => !String(row[0]).toLowerCase().includes("shoulder width"));
      const preIdx = videoKin.headers.indexOf("Pre");
      const postIdx = videoKin.headers.indexOf("Post");
      const healthyIdx = videoKin.headers.indexOf("Healthy side");
      const head = videoKin.headers.map((h) => `<th>${esc(h)}</th>`).join("")
        + (preIdx >= 0 && postIdx >= 0 ? '<th style="text-align:center">Pre → Post</th>' : "")
        + (postIdx >= 0 && healthyIdx >= 0 ? '<th style="text-align:center">Post → Healthy</th>' : "");
      const body = fBody.map((row, ri) => {
        const dir = videoKin.varMeta?.[ri]?.dir || kinDirectionMap(row[0]);
        let prePostHtml = "";
        let postHealthyHtml = "";
        if (preIdx >= 0 && postIdx >= 0) {
          const preVal = parseFloat(row[preIdx]);
          const postVal = parseFloat(row[postIdx]);
          if (!isNaN(preVal) && !isNaN(postVal)) {
            const metricKey = videoKin.varMeta?.[ri]?.key;
            const badge = resolveKinPrePostCell(
              preVal, postVal, dir, metricKey || "unknown", videoKin.kr, null,
            );
            prePostHtml = `<td class="num">${esc(badge?.text || NA)}</td>`;
          } else {
            prePostHtml = `<td class="num">${NA}</td>`;
          }
        }
        if (postIdx >= 0 && healthyIdx >= 0) {
          const postVal = parseFloat(row[postIdx]);
          const helVal = parseFloat(row[healthyIdx]);
          if (!isNaN(postVal) && !isNaN(helVal)) {
            const badge = kinPostHealthyBadge(null, postVal, helVal, dir);
            postHealthyHtml = `<td class="num">${esc(badge?.text || NA)}</td>`;
          } else {
            postHealthyHtml = `<td class="num">${NA}</td>`;
          }
        }
        return `<tr>${row.map((c, i) => `<td class="${i < 2 ? "metric" : "num"}">${esc(c)}</td>`).join("")}${prePostHtml}${postHealthyHtml}</tr>`;
      }).join("");
      let videoInterp = "";
      if (preIdx >= 0 && postIdx >= 0) {
        const imp = fBody.filter((row, ri) => {
          const preVal = parseFloat(row[preIdx]), postVal = parseFloat(row[postIdx]);
          if (isNaN(preVal) || isNaN(postVal)) return false;
          const dir = videoKin.varMeta?.[ri]?.dir || kinDirectionMap(row[0]);
          const pct = calcImprovement(preVal, postVal, dir);
          return pct != null && pct > 0;
        }).length;
        const wors = fBody.filter((row, ri) => {
          const preVal = parseFloat(row[preIdx]), postVal = parseFloat(row[postIdx]);
          if (isNaN(preVal) || isNaN(postVal)) return false;
          const dir = videoKin.varMeta?.[ri]?.dir || kinDirectionMap(row[0]);
          const pct = calcImprovement(preVal, postVal, dir);
          return pct != null && pct < 0;
        }).length;
        const total = fBody.filter((row) => {
          const preVal = parseFloat(row[preIdx]), postVal = parseFloat(row[postIdx]);
          return !isNaN(preVal) && !isNaN(postVal);
        }).length;
        if (total > 0) {
          const impLabel = imp > total / 2 ? "Most metrics changed favorably" : imp > 0 ? "Some metrics changed favorably" : "No favorable change";
          videoInterp = `<div class="tool-interp">${impLabel} (${imp} better, ${wors} worse, ${total - imp - wors} stable)</div>`;
        }
      }
      videoSection = `
        <div class="singlecol">
        <div class="card">
          <div class="badge" style="background:#0d948888">Video Kinematic Analysis</div>
          <div class="tblwrap">
          <table><thead><tr style="background:#0d948888;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)">${head}</tr></thead><tbody>${body}</tbody></table>
          </div>
          ${videoInterp}
        </div>
        </div>`;
    }

    const demoItems = [
      ["Age / Yaş", d.age ? `${d.age} yrs` : "\u2014"],
      ["Sex", d.sex === "1" ? "Male" : d.sex === "2" ? "Female" : "\u2014"],
      ["Stroke Type", d.strokeType === "1" ? "Ischemic" : d.strokeType === "2" ? "Hemorrhagic" : "\u2014"],
      ["Affected Side", d.side === "1" ? "Left" : d.side === "2" ? "Right" : "\u2014"],
      ["Time Since Stroke", d.timeSinceStroke ? `${d.timeSinceStroke} months` : "\u2014"],
      ["MAS", d.mas || "\u2014"],
      ["MRC", d.mrc || "\u2014"],
    ].map(([k, v]) => `<div class="demoitem"><span class="demok">${esc(k)}</span><span class="demov">${esc(v)}</span></div>`).join("");

    const ipaq = fd.ipaq || {};
    const ipaqRows = IPAQ_ACTS.filter(a => ipaq[a.id]?.gun || ipaq[a.id]?.sure).map(a => {
      const gun = ipaq[a.id]?.gun || "0";
      const sure = ipaq[a.id]?.sure || "0";
      const totMin = (parseFloat(gun) * parseFloat(sure)) || 0;
      const metVal = totMin * a.met;
      return `<tr><td class="metric">${esc(a.en)}</td><td class="num">${esc(gun)}</td><td class="num">${esc(sure)}</td><td class="num">${totMin.toFixed(0)}</td><td class="num">${a.met}</td><td class="num">${metVal.toFixed(0)}</td></tr>`;
    }).join("");
    const ipaqTotalMET = IPAQ_ACTS.reduce((s, a) => {
      const gun = parseFloat(ipaq[a.id]?.gun) || 0;
      const sure = parseFloat(ipaq[a.id]?.sure) || 0;
      return s + gun * sure * a.met;
    }, 0);
    let ipaqSection = "";
    if (ipaqRows) {
      const highDays = parseInt(ipaq.high?.gun) || 0;
      const medDays = parseInt(ipaq.medium?.gun) || 0;
      const lightDays = parseInt(ipaq.light?.gun) || 0;
      const medTotal = ((parseFloat(ipaq.medium?.sure)||0)*(parseFloat(ipaq.medium?.gun)||0)) || 0;
      const lightTotal = ((parseFloat(ipaq.light?.sure)||0)*(parseFloat(ipaq.light?.gun)||0)) || 0;
      let clsLevel, clsColor, clsText;
      if (highDays >= 3 && ipaqTotalMET >= 1500) { clsLevel="High"; clsColor="#10b981"; clsText="Vigorous activity ≥3 days and ≥1500 MET-min/week"; }
      else if ((medDays+lightDays) >= 7 && ipaqTotalMET >= 3000) { clsLevel="High"; clsColor="#10b981"; clsText="Mixed activities 7 days and ≥3000 MET-min/week"; }
      else if (ipaqTotalMET >= 600 || (medDays+lightDays >= 5 && (medTotal+lightTotal) >= 150)) { clsLevel="Moderate"; clsColor="#f59e0b"; clsText="≥600 MET-min/week or 5+ days moderate/walking"; }
      else { clsLevel="Low"; clsColor="#f43f5e"; clsText="Not meeting moderate or high criteria"; }
      ipaqSection = '<div class="singlecol"><div class="card"><div class="badge" style="background:#0ea5e988">Physical Activity (IPAQ) / Fiziksel Aktivite</div><div class="tblwrap"><table><thead><tr style="background:#0ea5e988;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)"><th>Activity</th><th>Days/wk</th><th>Min/day</th><th>Total min/wk</th><th>MET</th><th>MET-min/wk</th></tr></thead><tbody>' + ipaqRows + '</tbody></table></div>'
        + '<hr style="border:none;border-top:1px solid rgba(0,0,0,0.06);margin:14px 0">'
        + '<p style="font-size:9px;color:#94a3b8;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 2px">Physical Activity Level Interpretation</p>'
        + '<p style="font-size:11px;color:#64748b;margin:0 0 10px">Based on IPAQ scoring guidelines</p>'
        + '<div style="display:flex;gap:10px">'
        + '<div style="flex:1;padding:10px 14px;background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.3);border-radius:0.75rem">'
        + '<p style="font-size:9px;color:#94a3b8;font-weight:800;text-transform:uppercase;margin:0 0 2px">Total MET-minutes/week</p>'
        + '<p style="font-size:22px;font-weight:800;color:#1e293b;margin:0">' + ipaqTotalMET.toFixed(0) + '</p>'
        + '<p style="font-size:11px;color:#64748b;margin:4px 0 0">Metabolic Equivalent of Task</p>'
        + '</div>'
        + '<div style="flex:1;padding:10px 14px;border-radius:0.75rem;border:1px solid;background:' + clsColor + '15;border-color:' + clsColor + '30">'
        + '<p style="font-size:9px;color:#94a3b8;font-weight:800;text-transform:uppercase;margin:0 0 2px">Activity Classification</p>'
        + '<p style="font-size:22px;font-weight:800;color:' + clsColor + ';margin:0">' + clsLevel + '</p>'
        + '<p style="font-size:11px;color:' + clsColor + ';margin:4px 0 0;opacity:0.7">' + clsText + '</p>'
        + '</div></div></div></div>';
    }

    const notesSrc = (d.notes || "").trim();
    const fmtNotes = notesSrc ? esc(notesSrc) : "";
    const notesHtml = d.antispasticDrugs || d.otherDrugs || notesSrc ? '<div style="margin-top:14px;padding-top:14px;border-top:1px solid rgba(255,255,255,0.3)">' +
      (d.antispasticDrugs ? '<p style="font-size:11px;color:#334155;margin:0 0 4px"><strong style="color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">Antispastic Drugs / Antispastik İlaçlar:</strong><br>' + esc(d.antispasticDrugs) + '</p>' : "") +
      (d.otherDrugs ? '<p style="font-size:11px;color:#334155;margin:0 0 4px"><strong style="color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">Other Medications / Diğer İlaçlar:</strong><br>' + esc(d.otherDrugs) + '</p>' : "") +
      (fmtNotes ? '<p style="font-size:11px;color:#334155;margin:0 0 4px"><strong style="color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">Clinical Notes:</strong><br><div style="margin-top:4px;white-space:pre-wrap">' + fmtNotes + '</div></p>' : "") +
    '</div>' : "";

    const html = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Clinical Report - ${esc(d.name || "Participant")}</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',system-ui,-apple-system,sans-serif; }
  body { background:#f5f0eb; color:#1e293b; padding:28px; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  body::before { content:""; position:fixed; inset:0; background:url("data:image/svg+xml,%3Csvg viewBox='0 0 300 300' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E"); pointer-events:none; z-index:9999; }
  .wrap { max-width:920px; margin:0 auto; }
  .header { backdrop-filter:blur(40px) saturate(180%); -webkit-backdrop-filter:blur(40px) saturate(180%); border:1px solid rgba(255,255,255,0.3); border-radius:1rem; box-shadow:0 25px 50px -8px rgba(0,0,0,0.10); padding:22px 30px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center; }
  .header h1 { font-size:20px; color:#1e293b; font-weight:800; }
  .header .sub { font-size:12px; color:#64748b; margin-top:3px; }
  .header .meta { text-align:right; font-size:11px; color:#64748b; }
  .patient { background:rgba(204,251,241,0.35); backdrop-filter:blur(40px) saturate(180%); -webkit-backdrop-filter:blur(40px) saturate(180%); border:1px solid rgba(255,255,255,0.3); border-radius:1rem; box-shadow:0 25px 50px -8px rgba(0,0,0,0.10); padding:20px 28px; margin-bottom:20px; }
  .patient .name { font-size:22px; font-weight:800; color:#1e293b; }
  .patient .pid { font-size:12px; color:#64748b; margin:3px 0 14px; }
  .demogrid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }
  .demoitem { display:flex; flex-direction:column; }
  .demok { font-size:9px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.05em; font-weight:700; }
  .demov { font-size:13px; color:#334155; font-weight:700; margin-top:1px; }

  tr { break-inside:avoid; page-break-inside:avoid; }
  .tool-interp { margin-top:14px; padding:10px 14px; background:rgba(255,255,255,0.5); border:1px solid rgba(255,255,255,0.3); border-radius:0.75rem; display:inline-block; backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); font-size:11px; color:#334155; font-weight:600; }
  .sum-item { display:flex; align-items:center; gap:10px; padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.3); font-size:12px; color:#334155; }
  .sum-item:last-child { border-bottom:none; }
  .sum-badge { display:inline-block; font-size:9px; font-weight:800; padding:3px 12px; border-radius:0.75rem; flex-shrink:0; background:rgba(255,255,255,0.25); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border:1px solid rgba(255,255,255,0.3); }

  .badge { display:inline-block; color:#fff; font-size:10px; font-weight:800; padding:5px 16px; border-radius:1rem; margin-bottom:12px; letter-spacing:0.02em; backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border:1px solid rgba(255,255,255,0.3); }
  .tblwrap { border-radius:0.75rem; overflow:hidden; border:1px solid rgba(255,255,255,0.3); box-shadow:0 8px 25px -6px rgba(0,0,0,0.06); background:rgba(255,255,255,0.4); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); }
  table { width:100%; border-collapse:collapse; }
  thead th { color:#fff; font-size:10px; font-weight:700; padding:9px 14px; text-align:left; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  thead th:not(:first-child) { text-align:center; }
  tbody td { padding:9px 14px; font-size:11px; color:#475569; border-top:1px solid rgba(255,255,255,0.3); }
  tbody tr:nth-child(even) { background:rgba(255,255,255,0.2); }
  td.metric { font-weight:500; }
  td.num { text-align:center; }
  .delta { font-weight:800; }
  .delta.up { color:#16a34a; } .delta.down { color:#dc2626; } .delta.neutral { color:#94a3b8; }

  .velrow { display:flex; gap:16px; flex-wrap:wrap; }
  .velrow .velcard { flex:1; min-width:240px; margin-top:12px; background:rgba(255,255,255,0.4); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); border:1px solid rgba(255,255,255,0.3); border-radius:0.75rem; padding:14px; box-shadow:0 6px 20px -4px rgba(0,0,0,0.06); }
  .vellabel { font-size:12px; font-weight:800; color:#0d9488; margin-bottom:4px; }

  .vel-chart-card { padding-bottom:16px; }
  .vel-chart-wrap { border-radius:0.75rem; overflow:hidden; border:1px solid #e2e8f0; background:#f8fafc; padding:6px 6px 2px; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  .vel-chart-wrap svg { display:block; width:100%; height:auto; max-height:300px; }

  .singlecol .card { break-inside:avoid; page-break-inside:avoid; background:rgba(255,255,255,0.65); backdrop-filter:blur(40px) saturate(180%); -webkit-backdrop-filter:blur(40px) saturate(180%); border:1px solid rgba(255,255,255,0.3); border-radius:1rem; box-shadow:0 25px 50px -8px rgba(0,0,0,0.10); padding:18px 22px; margin-bottom:20px; }
  .pagebreak { break-before:page; page-break-before:always; }

  .interp { font-size:12px; line-height:1.8; color:#334155; }
  @media print {
    body { -webkit-print-color-adjust:exact !important; print-color-adjust:exact !important; background:#f5f0eb !important; padding:16px; }
    body::before { background:url("data:image/svg+xml,%3Csvg viewBox='0 0 300 300' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E") !important; }
    .card, .header, .patient { box-shadow:0 10px 30px -6px rgba(0,0,0,0.08) !important; page-break-inside:avoid; break-inside:avoid; -webkit-print-color-adjust:exact !important; print-color-adjust:exact !important; }
    tr { page-break-inside:avoid; break-inside:avoid; }
    .badge, thead th, .tblwrap { -webkit-print-color-adjust:exact !important; print-color-adjust:exact !important; }
    .pagebreak { break-before:page; page-break-before:always; }
    @page { margin:12mm; }
  }
</style></head><body><div class="wrap">
  <div class="header" style="background:${d.group === "1" ? "rgba(167,243,208,0.3)" : "rgba(251,207,232,0.4)"}">
    <div style="display:flex;align-items:center;gap:14px"><img src="/raed-logo.png?v=32.88" alt="RA.ED AI" style="height:56px;width:auto"/><div><h1>${d.group === "1" ? "AOMI Group / AOMI Grubu" : "Control Group / Kontrol Grubu"}</h1><div class="sub">Clinical Assessment Report / Klinik Değerlendirme Raporu</div></div></div>
    <div class="meta">${new Date().toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric"})}<br>${esc(d.name || "Participant")}</div>
  </div>
  <div class="patient">
    <div class="name">${esc(d.name || "\u2014")}</div>
    <div class="pid">${d.participantId ? "ID: " + esc(d.participantId) : ""}</div>
    <div class="demogrid">${demoItems}</div>
    ${notesHtml}
  </div>
  ${ipaqSection}
  <div class="tools">${toolSections}</div>
  ${videoSection}
  ${velSection}
  ${buildSummaryInterp()}
  ${buildNarrativeSummary()}
</div>
<script>window.onload = () => { setTimeout(() => window.print(), 400); };</script>
</body></html>`;

    const blob = new Blob([html], { type: "text/html" });
    const isMobile = /Android|iPhone|iPad|iPod|webOS|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    if (isMobile) {
      downloadBlob(blob, `report_${d.participantId || d.name || "participant"}.html`);
      alert("Report downloaded — open the file and print to PDF");
    } else {
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    }
    } catch (e) { alert("Report error: " + e.message); } };

  // ?? PDF Export (jsPDF fallback) ??
  const exportPDF = () => {
    const doc = new jsPDF({ orientation:"portrait", unit:"mm", format:"a4" });

    // ?? Design tokens (GlassCard style) ????????????????????????????
    const W = 210, M = 12, CW = W - 2 * M, R = 6, R2 = 4, R3 = 3;
    const C = {
      teal:    [13,  148, 136],
      tealDim: [204, 235, 232],
      tealBg:  [240, 253, 250],
      green:   [22,  163, 74 ],
      red:     [220, 38,  38 ],
      gray900: [15,  23,  42 ],
      gray700: [51,  65,  85 ],
      gray500: [100, 116, 139],
      gray300: [203, 213, 225],
      gray200: [226, 232, 240],
      gray100: [241, 245, 249],
      gray50:  [248, 250, 252],
      white:   [255, 255, 255],
      violet:  [124, 58,  237],
      amber:   [180, 83,  9  ],
      cyan:    [8,   145, 178],
      rose:    [225, 29,  72 ],
    };

    const B_R = R; // card border radius

    // ?? Helpers ????????????????????????????????????????????????????
    const rr = (x, y, w, h, r, fill, stroke, lw = 0.3) => {
      if (fill)   doc.setFillColor(...fill);
      if (stroke) { doc.setDrawColor(...stroke); doc.setLineWidth(lw); }
      doc.roundedRect(x, y, w, h, r || B_R, r || B_R, fill && stroke ? "FD" : fill ? "F" : "D");
    };

    const txt = (text, x, y, size, bold, color, align) => {
      doc.setFontSize(size || 9);
      doc.setFont("helvetica", bold ? "bold" : "normal");
      doc.setTextColor(...(color || C.gray900));
      doc.text(String(text ?? ""), x, y, align ? { align } : undefined);
    };

    const sectionBadge = (label, x, y, bg) => {
      const bw = label.length * 2.2 + 6, bh = 6, br = 40;
      rr(x, y - 4.5, bw, bh, br, bg || C.teal, null);
      txt(label, x + bw / 2, y - 0.5, 7.5, true, C.white, "center");
      return y + 3;
    };

    const checkPage = (curY, needed = 30) => {
      if (curY + needed > 282) { doc.addPage(); drawPageBg(); return 18; }
      return curY;
    };

    const drawPageBg = () => {
      rr(6, 6, W - 12, 285, R, C.tealBg, null); // soft teal background card
      doc.setFillColor(...C.white);
      doc.rect(0, 0, W, 297, "F");
    };

    // ?? Page 1: background ????????????????????????????????????????
    drawPageBg();

    // Glass header card
    let y = 14;
    rr(M, y, CW, 22, R, C.white, C.gray200);
    rr(M + 2, y + 2, 4, 18, 2, C.teal, null);
    txt("Stroke Rehabilitation Research Platform", M + 10, y + 8, 12, true, C.gray900);
    txt("Clinical Assessment Report", M + 10, y + 14, 8, false, C.gray500);
    txt(new Date().toLocaleDateString("en-GB", {day:"2-digit",month:"short",year:"numeric"}), W - M - 10, y + 8, 7.5, false, C.gray500, "right");
    txt(d.name || "Participant", W - M - 10, y + 14, 7.5, false, C.gray500, "right");

    // ?? Patient Card (GlassCard style) ?????????????????????????????
    y = 42;
    rr(M, y, CW, 32, R, C.white, C.gray200);
    rr(M + 2, y + 2, 4, 28, 2, C.teal, null);

    txt(d.name || NA, M + 10, y + 9, 13, true, C.gray900);
    txt(d.participantId ? `ID: ${d.participantId}` : "", M + 10, y + 15, 7.5, false, C.gray500);

    const demoGrid = [
      ["Age",        d.age ? `${d.age} yrs` : NA],
      ["Sex",        d.sex === "1" ? "Male" : d.sex === "2" ? "Female" : NA],
      ["Stroke",     d.strokeType === "1" ? "Ischemic" : d.strokeType === "2" ? "Hemorrhagic" : NA],
      ["Side",       d.side === "1" ? "Left" : d.side === "2" ? "Right" : NA],
      ["TSS",        d.timeSinceStroke ? `${d.timeSinceStroke}m` : NA],
      ["MAS",        d.mas || NA],
      ["MRC",        d.mrc || NA],
    ];
    const colW = CW / 4;
    demoGrid.forEach((item, i) => {
      const cx = M + 5 + (i % 4) * colW;
      const cy = y + (i < 4 ? 21 : 28);
      txt(item[0], cx, cy, 6, false, C.gray500);
      txt(item[1], cx, cy + 4, 7, true, C.gray700);
    });

    y = 80;

    // ?? Per-tool sections (GlassCard style) ???????????????????????
    const toolConfig = {
      "VAS":          { label: "Pain Scale (VAS)",          color: C.rose  },
      "VAMS":         { label: "Mood Scale (VAMS-4)",        color: C.violet},
      "Muscle Control":{ label: "Muscle Control Scale",      color: C.amber },
      "KVIQ":         { label: "Motor Imagery (KVIQ)",       color: C.teal  },
      "WMFT":         { label: "Wolf Motor Function (WMFT)", color: C.cyan  },
      "BBT":          { label: "Box & Block Test (BBT)",     color: C.amber },
    };

    const groupedRows = {};
    rows.forEach((r) => {
      if (!groupedRows[r.tool]) groupedRows[r.tool] = [];
      groupedRows[r.tool].push(r);
    });

    Object.entries(groupedRows).forEach(([tool, toolRows]) => {
      const cfg = toolConfig[tool] || { label: tool, color: C.teal };
      y = checkPage(y, 24 + toolRows.length * 7);

      // Glass card for this section
      rr(M, y, CW, 0.1, R, null, C.gray300); y += 1.5;

      // Section badge
      sectionBadge(cfg.label, M + 4, y + 3, cfg.color);
      y += 7;

      autoTable(doc, {
        startY: y,
        margin: { left: M + 4, right: M + 4 },
        head: [["Metric / Task", "Pre", "Post", "Change"]],
        body: toolRows.map((r) => [r.metric, r.pre, r.post, r.delta, r.improving]),
        styles: {
          fontSize: 7.5, cellPadding: { top: 3, bottom: 3, left: 5, right: 5 },
          overflow: "linebreak", lineColor: C.gray200, lineWidth: 0.2,
          textColor: C.gray700,
        },
        headStyles: {
          fillColor: cfg.color, textColor: C.white, fontStyle: "bold",
          fontSize: 7, cellPadding: { top: 2.5, bottom: 2.5, left: 5, right: 5 },
        },
        alternateRowStyles: { fillColor: C.gray50 },
        tableLineColor: C.gray200, tableLineWidth: 0.2,
        columnStyles: {
          0: { cellWidth: "auto" },
          1: { cellWidth: 18, halign: "center" },
          2: { cellWidth: 18, halign: "center" },
          3: { cellWidth: 22, halign: "center", fontStyle: "bold" },
          4: { cellWidth: 0 },
        },
        didParseCell: (data) => {
          if (data.column.index === 4) { data.cell.text = []; }
          if (data.column.index === 3 && data.section === "body") {
            const delta = data.row.raw[3];
            const imp   = data.row.raw[4];
            if (delta && !isMissing(delta)) {
              data.cell.styles.textColor = imp === true ? C.green : imp === false ? C.red : C.gray700;
            }
          }
        },
        didDrawPage: (hookData) => {
          if (hookData.pageNumber > 1) drawPageBg();
        },
      });

      y = (doc.lastAutoTable?.finalY || y) + 5;
    });

    // ?? Video Kinematics ??????????????????????????????????????????
    const videoKin = buildVideoKinRows();
    if (videoKin) {
      y = checkPage(y, 40);
      rr(M, y, CW, 0.1, R, null, C.gray300); y += 1.5;
      sectionBadge("Video Kinematic Analysis", M + 4, y + 3, C.teal);
      y += 7;

      const filteredBody = videoKin.body.filter(
        (row) => !String(row[0]).toLowerCase().includes("shoulder width")
      );

      autoTable(doc, {
        startY: y,
        margin: { left: M + 4, right: M + 4 },
        head: [videoKin.headers],
        body: filteredBody,
        styles: {
          fontSize: 7.5, cellPadding: { top: 3, bottom: 3, left: 5, right: 5 },
          overflow: "linebreak", lineColor: C.gray200, lineWidth: 0.2,
          textColor: C.gray700,
        },
        headStyles: { fillColor: C.teal, textColor: C.white, fontStyle: "bold", fontSize: 7 },
        alternateRowStyles: { fillColor: C.gray50 },
        tableLineColor: C.gray200, tableLineWidth: 0.2,
        didDrawPage: () => drawPageBg(),
      });
      y = (doc.lastAutoTable?.finalY || y) + 4;
    }

    // ?? Velocity profiles (combined chart) ????????????????????????
    const kr2 = loadLiveKinResults(fd);
    const kinPhases = ["pre","post","baseline"].filter((p) => kr2[p]?.velocity_profile);
    if (kinPhases.length > 0) {
      const combinedSvg = buildCombinedVelChart({
        pre: kr2.pre?.velocity_profile,
        post: kr2.post?.velocity_profile,
        baseline: kr2.baseline?.velocity_profile,
      }, true);
      if (combinedSvg) {
        const img = svgToDataUrl(combinedSvg);
        y = checkPage(y, 78);
        rr(M, y, CW, 0.1, R, null, C.gray300); y += 1.5;
        sectionBadge("Combined Velocity Profile", M + 4, y + 3, C.teal);
        y += 8;
        rr(M + 4, y, CW - 8, 62, R2, C.gray50, C.gray200);
        try { doc.addImage(img, "SVG", M + 6, y + 2, CW - 12, 58); y += 64; } catch {}
      }
    }

    // ?? Footer on each page ???????????????????????????????????????
    const totalPages = doc.getNumberOfPages();
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i);
      doc.setDrawColor(...C.gray300); doc.setLineWidth(0.3);
      doc.line(M, 285, W - M, 285);
      txt(`Stroke Rehab Platform  |  Confidential  |  Page ${i} of ${totalPages}`, W / 2, 290, 6.5, false, C.gray500, "center");
    }

    const pdfName = `report_${d.participantId || d.name || "participant"}.pdf`;
    const pdfBlob = doc.output("blob");
    downloadBlob(pdfBlob, pdfName);
    const patientKey = patientDriveKeyFromDemographics(d);
    scheduleDriveFileBackup(clinicReportDriveName(patientKey), pdfBlob, {
      patientKey,
      force: true,
    });
  };

  // ?? Excel Export (per clinical task; archived excluded) ??
  const exportExcel = () => {
    if (fd?._archived) {
      showToast("Archived sessions are excluded from Excel export", "error");
      return;
    }
    const wb = XLSX.utils.book_new();

    // Sheet 1: Demographics
    const demoData = [
      ["Field", "Value"],
      ["Name", d.name || ""],
      ["Study ID", d.participantId || ""],
      ["Group", d.group === "1" ? "AOMI" : d.group === "2" ? "Control" : ""],
      ["Age", d.age || ""],
      ["Sex", d.sex === "1" ? "Male" : d.sex === "2" ? "Female" : ""],
      ["Time Since Stroke (months)", d.timeSinceStroke || ""],
      ["Stroke Type", d.strokeType === "1" ? "Ischemic" : d.strokeType === "2" ? "Hemorrhagic" : ""],
      ["Affected Side", d.side === "1" ? "Left" : d.side === "2" ? "Right" : ""],
      ["MAS", d.mas || ""],
      ["MRC", d.mrc || ""],
    ];
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(demoData), "Demographics");

    // Sheet 2: Clinical Summary
    const ws2 = XLSX.utils.aoa_to_sheet([
      ["Tool", "Metric / Task", "Pre-Assessment", "Post-Assessment", "Change"],
      ...rows.map((r) => [
        r.tool,
        r.metric,
        isMissing(r.pre) ? "" : r.pre,
        isMissing(r.post) ? "" : r.post,
        isMissing(r.delta) ? "" : r.delta,
      ]),
    ]);
    ws2["!cols"] = [{ wch: 20 }, { wch: 55 }, { wch: 18 }, { wch: 18 }, { wch: 12 }];
    XLSX.utils.book_append_sheet(wb, ws2, "Clinical Summary");

    // Sheet 3: VAS
    const vas = fd.vas || {};
    const vasSheet = [["Metric", "Pre (0-10)", "Post (0-10)", "Change"]];
    [
      { k:"rest", en:"Pain at Rest" },
      { k:"activity", en:"Pain During Activity" },
    ].forEach((item) => vasSheet.push([item.en, vas[item.k]?.pre || "", vas[item.k]?.post || "", ""]));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(vasSheet), "VAS");

    // Sheet 4: VAMS-4
    const vams = fd.vams || {};
    const vamsSheet = [["Metric", "Pre (0-10)", "Post (0-10)", "Change"]];
    [
      { k:"happy", en:"Happy" },
      { k:"sad", en:"Sad" },
      { k:"calm", en:"Calm" },
      { k:"tense", en:"Tense" },
    ].forEach((item) => vamsSheet.push([item.en, vams[item.k]?.pre || "", vams[item.k]?.post || "", ""]));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(vamsSheet), "VAMS-4");

    // Sheet 5: KVIQ
    const kgia = fd.kgia || {};
    const kviqSheet = [["#", "Movement", "Type", "Pre (1-5)", "Post (1-5)", "Change"]];
    KGIA_MOVEMENTS.forEach((mov, mi) =>
      KGIA_TYPES.forEach((t) =>
        kviqSheet.push([
          mi + 1, mov.en, t.en,
          kgia[`${mi}_${t.key}`]?.once || "",
          kgia[`${mi}_${t.key}`]?.sonra || "",
          ""
        ])
      )
    );
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(kviqSheet), "KVIQ");

    // Sheet 6: WMFT
    const wmft = fd.wmft || {};
    const wmftSheet = [["#", "Task", "Pre Time (sec)", "Pre Rating (0-5)", "Post Time (sec)", "Post Rating (0-5)"]];
    WMFT_ITEMS.forEach((t) =>
      wmftSheet.push([
        t.id, t.en,
        wmft[t.id]?.pre?.time || "",
        wmft[t.id]?.pre?.rating || "",
        wmft[t.id]?.post?.time || "",
        wmft[t.id]?.post?.rating || "",
      ])
    );
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(wmftSheet), "WMFT");

    const bbt = fd.bbt || {};
    const bbtSheet = [
      ["Phase", "Paretic hand (blocks/60s)", "Unaffected hand (optional)", "Notes"],
      ["Pre", bbt.pre?.pareticBlocks || "", bbt.pre?.unaffectedBlocks || "", bbt.pre?.notes || ""],
      ["Post", bbt.post?.pareticBlocks || "", bbt.post?.unaffectedBlocks || "", bbt.post?.notes || ""],
    ];
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(bbtSheet), "BBT");

    // Kinematics: only this patient's clinical-task core variables (never mix tasks).
    const taskKinRows = patientTaskKinSheetRows(fd);
    if (taskKinRows.length > 0) {
      XLSX.utils.book_append_sheet(
        wb,
        XLSX.utils.aoa_to_sheet([
          ["Task", "Variable", "Unit", "Pre", "Post", "Healthy", "Δ Pre→Post"],
          ...taskKinRows.map((r) => [
            r.taskId || "",
            r.name || "",
            r.unit || "",
            r.pre || "",
            r.post || "",
            r.healthy || "",
            calcKinDelta(r.pre, r.post),
          ]),
        ]),
        "Kinematics"
      );
    } else if (kinRows.length > 0) {
      // Legacy uploadedData fallback ? still label as uploaded, not mixed KINEMATIC_VARS dump.
      XLSX.utils.book_append_sheet(
        wb,
        XLSX.utils.aoa_to_sheet([
          ["Variable", "Unit", "Pre", "Post", "Change"],
          ...kinRows.map((r) => [r.name || "", r.unit || "", r.pre || "", r.post || "", calcKinDelta(r.pre, r.post)]),
        ]),
        "Kinematics"
      );
    }

    XLSX.writeFile(wb, `research_data_${d.participantId || "participant"}_${new Date().toISOString().split("T")[0]}.xlsx`);
  };

  const exportTaskExcels = async () => {
    const allPts = activePatients();
    if (!allPts.length) {
      showToast("No active patients to export", "error");
      return;
    }
    const result = await syncTaskExcelsToDrive(allPts, { showToast, downloadLocal: true });
    if (result.count) {
      showToast(`Excel — ${result.count} task file(s); Drive ${result.uploaded}/${result.count}`, "success");
    }
  };

  // ?? SPSS Export (all patients, split by group + demo/assess/full) ??
  const exportSPSS = () => {
    const allPts = activePatients();
    if (allPts.length === 0) { showToast("No patients to export", "error"); return; }

    const masterRows = buildMasterDataset(allPts, WMFT_ITEMS, KGIA_MOVEMENTS, IPAQ_ACTS);
    if (masterRows.length === 0) { showToast("No valid data rows", "error"); return; }

    let count = 0;
    const toCsv = (name, rows) => {
      const blob = new Blob(["\uFEFF" + XLSX.utils.sheet_to_csv(XLSX.utils.json_to_sheet(rows))], { type:"text/csv;charset=utf-8" });
      setTimeout(() => downloadBlob(blob, name), count * 400);
      count++;
    };

    toCsv("master_study_data.csv", masterRows);

    const groupIsAomi = (r) => String(r.Group) === "1" || r.Group === 1;
    const groupIsCtrl = (r) => String(r.Group) === "2" || r.Group === 2;
    const aomi = masterRows.filter(groupIsAomi);
    const ctrl = masterRows.filter(groupIsCtrl);
    const demoKeys = DEMO_SPSS_KEYS;
    const assessKeys = Object.keys(masterRows[0]).filter((k) => k !== "ID" && !demoKeys.includes(k));
    const pick = (row, keys) => keys.reduce((o, k) => ({ ...o, [k]: row[k] }), {});

    toCsv("aomi_full.csv", aomi.map((r) => pick(r, ["ID", ...demoKeys.slice(1), ...assessKeys])));
    toCsv("control_full.csv", ctrl.map((r) => pick(r, ["ID", ...demoKeys.slice(1), ...assessKeys])));

    // eslint-disable-next-line no-undef
    setTimeout(() => downloadBlob(
      new Blob(["\uFEFF" + generateStudySPSSyntax("master_study_data.csv", masterRows[0])], { type: "text/plain;charset=utf-8" }),
      "neuro_study_analysis.sps"
    ), count * 400);

    showToast("Exported master + group CSVs + SPSS syntax");
  };

  // ?? JSON Export (all patients) ??
  const exportJSON = () => {
    const allPts = activePatients();
    if (allPts.length === 0) { return; }
    const clean = allPts.map(({ _id, _savedAt, _hasPre, _hasPost, ...rest }) => rest);
    const blob = new Blob([JSON.stringify(clean, null, 2)], { type: "application/json" });
    downloadBlob(blob, `neuro_data_${allPts.length}patients_${new Date().toISOString().split("T")[0]}.json`);
  };

  // ?? SPSS Syntax (.sps) export ? full study analysis workflow ??
  const exportSPSSyntax = () => {
    const allPts = activePatients();
    const masterRows = buildMasterDataset(allPts, WMFT_ITEMS, KGIA_MOVEMENTS, IPAQ_ACTS);
    if (masterRows.length === 0) {
      showToast("No patient data for SPSS syntax", "error");
      return;
    }
    // eslint-disable-next-line no-undef
    const syn = generateStudySPSSyntax("master_study_data.csv", masterRows[0]);
    const blob = new Blob(["\uFEFF" + syn], { type: "text/plain;charset=utf-8" });
    downloadBlob(blob, "neuro_study_analysis.sps");
    showToast("SPSS syntax downloaded (neuro_study_analysis.sps)");
  };

  return (
    <div className="space-y-5">
      <SH icon={FileText} en="Clinical Report & Export" tr="Export" />

      {d.name && (
        <Glass className="p-4 border-l-2 border-violet-400/40">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="w-10 h-10 rounded-xl bg-violet-500/20 border border-violet-400/20 flex items-center justify-center flex-shrink-0">
              <User className="w-5 h-5 text-violet-300" />
            </div>

            <div className="min-w-0">
              <p className="font-extrabold text-white text-sm">{d.name}</p>
              <p className="text-xs text-white/40 truncate">
                {d.participantId} — {d.age} yrs — {d.strokeType} — {d.side} side
              </p>
            </div>

            <div className="ml-auto flex gap-2 flex-wrap">
              {d.assessDate && (
                <span className="text-[10px] px-2 py-1 rounded-lg bg-white/[0.06] border border-white/[0.04] text-white/50">
                  Assessed: {d.assessDate}
                </span>
              )}
            </div>
          </div>
        </Glass>
      )}

      {/* Clinical Notes */}
      {(d.notes || d.antispasticDrugs || d.otherDrugs) && (
        <Glass className="p-5 border-l-2 border-violet-400/40">
          <div className="flex items-start gap-3 mb-4">
            <FileText className="w-5 h-5 text-violet-300 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-extrabold text-white/90">Clinical Notes</p>
              <p className="text-xs font-light text-white/40 mt-0.5">Medical history, medications, and clinician observations</p>
            </div>
          </div>
          <div className="space-y-3">
            {d.antispasticDrugs && (
              <div className="glass-float bg-white/[0.09] border border-white/12 rounded-xl px-4 py-2.5">
                <p className="text-[10px] font-extrabold text-white/40 uppercase tracking-widest mb-1">Antispastic Drugs</p>
                <p className="text-sm text-white/80 font-medium">{d.antispasticDrugs}</p>
              </div>
            )}
            {d.otherDrugs && (
              <div className="glass-float bg-white/[0.09] border border-white/12 rounded-xl px-4 py-2.5">
                <p className="text-[10px] font-extrabold text-white/40 uppercase tracking-widest mb-1">Other Medications</p>
                <p className="text-sm text-white/80 font-medium">{d.otherDrugs}</p>
              </div>
            )}
            {d.notes && <div className="glass-float bg-white/[0.09] border border-white/12 rounded-xl px-4 py-2.5"><p className="text-sm text-white/80 font-medium whitespace-pre-wrap">{d.notes}</p></div>}
          </div>
        </Glass>
      )}

      {/* IPAQ Section */}
      {(() => {
        const ipaqData = fd.ipaq || {};
        const hasIpaq = IPAQ_ACTS.some(a => ipaqData[a.id]?.gun || ipaqData[a.id]?.sure);
        if (!hasIpaq) return null;
        const totMin = (a) => ((parseFloat(ipaqData[a.id]?.sure) || 0) * (parseFloat(ipaqData[a.id]?.gun) || 0));
        const totalMET = IPAQ_ACTS.reduce((s, a) => s + totMin(a) * a.met, 0);
        return (
          <Glass className="p-5 border-l-2 border-sky-400/40">
            <div className="flex items-start gap-3 mb-4">
              <Activity className="w-5 h-5 text-sky-300 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-extrabold text-white/90">International Physical Activity Questionnaire (IPAQ)</p>
              </div>
            </div>
            <div className="glass-float overflow-x-auto rounded-xl border border-white/[0.08]">
              <table className="w-full text-sm min-w-[580px]">
                <thead>
                  <tr className="bg-white/[0.06] border-b border-white/[0.04]">
                    <th className="text-left px-3 py-3 font-extrabold text-white/70 text-xs uppercase">Activity</th>
                    <th className="text-center px-3 py-3 text-xs font-extrabold text-white/50 uppercase">Min/day</th>
                    <th className="text-center px-3 py-3 text-xs font-extrabold text-white/50 uppercase">Days/wk</th>
                    <th className="text-center px-3 py-3 text-xs font-extrabold text-white/50 uppercase">Total min/wk</th>
                    <th className="text-center px-3 py-3 text-xs font-extrabold text-white/50 uppercase">MET</th>
                    <th className="text-center px-3 py-3 text-xs font-extrabold text-white/50 uppercase">MET-min/wk</th>
                  </tr>
                </thead>
                <tbody>
                  {IPAQ_ACTS.filter(a => ipaqData[a.id]?.gun || ipaqData[a.id]?.sure).map((a, i) => {
                    const t = totMin(a);
                    return (
                      <tr key={a.id} className={`border-b border-white/[0.06] hover:bg-white/[0.03] ${i % 2 === 0 ? "" : "bg-white/[0.02]"}`}>
                        <td className="px-3 py-3 text-xs text-white/80">{a.en}</td>
                        <td className="px-3 py-3 text-center text-xs text-white/70 font-bold">{ipaqData[a.id]?.sure || "0"}</td>
                        <td className="px-3 py-3 text-center text-xs text-white/70 font-bold">{ipaqData[a.id]?.gun || "0"}</td>
                        <td className="px-3 py-3 text-center text-xs text-white/70 font-bold">{t.toFixed(0)}</td>
                        <td className="px-3 py-3 text-center text-xs text-white/70 font-bold">{a.met}</td>
                        <td className="px-3 py-3 text-center text-xs text-emerald-300 font-extrabold">{(t * a.met).toFixed(0)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {(() => {
              const highDays = parseFloat(ipaqData.high?.gun) || 0;
              const medDays = parseFloat(ipaqData.medium?.gun) || 0;
              const lightDays = parseFloat(ipaqData.light?.gun) || 0;
              const med = totMin(IPAQ_ACTS.find(a=>a.id==="medium")) || 0;
              const light = totMin(IPAQ_ACTS.find(a=>a.id==="light")) || 0;
              let cls;
              if (highDays >= 3 && totalMET >= 1500) cls = { level:"High", color:"emerald", text:"Vigorous activity ≥3 days and ≥1500 MET-min/week" };
              else if ((medDays + lightDays) >= 7 && totalMET >= 3000) cls = { level:"High", color:"emerald", text:"Mixed activities 7 days and ≥3000 MET-min/week" };
              else if (totalMET >= 600 || (medDays + lightDays >= 5 && (med + light) >= 150)) cls = { level:"Moderate", color:"amber", text:"≥600 MET-min/week or 5+ days moderate/walking" };
              else cls = { level:"Low", color:"rose", text:"Not meeting moderate or high criteria" };
              return (
                <><div className="my-4 border-t border-white/[0.06]" />
                <p className="text-[10px] font-extrabold text-white/40 uppercase tracking-widest mb-3">Physical Activity Level Interpretation</p>
                <p className="text-xs text-white/50 mb-3">Based on IPAQ scoring guidelines</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="glass-float px-4 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08]">
                    <p className="text-[10px] font-extrabold text-white/40 uppercase mb-1">Total MET-minutes/week</p>
                    <p className="text-2xl font-extrabold text-white">{totalMET.toFixed(0)}</p>
                    <p className="text-xs text-white/50 mt-1">Metabolic Equivalent of Task</p>
                  </div>
                  <div className={`px-4 py-3 rounded-xl border ${cls.color === "emerald" ? "bg-emerald-400/10 border-emerald-400/20" : cls.color === "amber" ? "bg-amber-400/10 border-amber-400/20" : "bg-rose-400/10 border-rose-400/20"}`}>
                    <p className="text-[10px] font-extrabold text-white/40 uppercase mb-1">Activity Classification</p>
                    <p className={`text-2xl font-extrabold ${cls.color === "emerald" ? "text-emerald-300" : cls.color === "amber" ? "text-amber-300" : "text-rose-300"}`}>{cls.level}</p>
                    <p className={`text-xs mt-1 ${cls.color === "emerald" ? "text-emerald-300/70" : cls.color === "amber" ? "text-amber-300/70" : "text-rose-300/70"}`}>{cls.text}</p>
                  </div>
                </div></>
              );
            })()}
          </Glass>
        );
      })()}

      {/* Clinical Summary Dashboard */}
      <Glass className="p-5">
        <div className="flex items-start gap-3 mb-5">
          <BarChart3 className="w-5 h-5 text-amber-300 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-extrabold text-white/90">Clinical Summary Dashboard</p>
            <p className="text-xs font-light text-white/40 mt-0.5">All assessment tools — Pre vs Post results — auto-calculated</p>
          </div>
        </div>

        {tools.filter(t => t !== "Kinematics").map((tool, idx) => {
          const toolRows = rows.filter((r) => r.tool === tool);
          const tc = toolColor[tool] || "text-white/60 bg-white/[0.05] border-white/[0.04]";

          return (
            <div key={tool} className="mb-6">
              <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border mb-3 text-xs font-bold ${tc}`}>
                {tool}
              </div>

              <div className="glass-float overflow-x-auto rounded-xl border border-white/[0.08]">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-white/[0.04] border-b border-white/[0.08]">
                      <th className="text-left px-4 py-2.5 text-xs font-extrabold text-white/50 uppercase">Metric / Task</th>
                      <th className="text-center px-3 py-2.5 text-xs font-extrabold text-sky-300 uppercase">Pre</th>
                      <th className="text-center px-3 py-2.5 text-xs font-extrabold text-emerald-300 uppercase">Post</th>
                      <th className="text-center px-3 py-2.5 text-xs font-extrabold text-amber-300 uppercase">Change</th>
                    </tr>
                  </thead>

                  <tbody>
                    {tool === "Muscle Control" ? (() => {
                      const preRow = toolRows.find(r => !isMissing(r.pre));
                      const postRow = toolRows.find(r => !isMissing(r.post));
                      const preVal = preRow ? preRow.pre : NA;
                      const postVal = postRow ? postRow.post : NA;
                      const delta = !isMissing(preVal) && !isMissing(postVal) ? (parseFloat(postVal) - parseFloat(preVal)).toFixed(2) : NA;
                      const imp = !isMissing(preVal) && !isMissing(postVal) ? (parseFloat(postVal) > parseFloat(preVal) ? true : parseFloat(postVal) < parseFloat(preVal) ? false : null) : null;
                      return (
                        <tr className="border-b border-white/[0.05] bg-white/[0.02]">
                          <td className="px-4 py-2.5 text-xs text-white/75 font-medium">Felt Difference</td>
                          <td className="px-3 py-2.5 text-center"><span className="px-2.5 py-1 rounded-lg border bg-sky-500/10 border-sky-400/20 text-sky-200 text-xs font-bold">{preVal}</span></td>
                          <td className="px-3 py-2.5 text-center"><span className="px-2.5 py-1 rounded-lg border bg-emerald-500/10 border-emerald-400/20 text-emerald-200 text-xs font-bold">{postVal}</span></td>
                          <td className="px-3 py-2.5 text-center"><span className={`px-2.5 py-1 rounded-lg text-xs font-extrabold border ${isMissing(delta) ? "text-white/25 bg-white/[0.03] border-white/[0.06]" : imp === true ? "text-emerald-300 bg-emerald-500/20 border-emerald-400/30" : imp === false ? "text-rose-300 bg-rose-500/20 border-rose-400/30" : "text-white/40 bg-white/[0.05] border-white/[0.08]"}`}>{delta}</span></td>
                        </tr>
                      );
                    })() : (
                      toolRows.map((row, i) => {
                        const dVal = row.delta;
                        const imp = row.improving;
                        return (
                          <tr key={i} className={`border-b border-white/[0.05] hover:bg-white/[0.03] ${i % 2 === 0 ? "" : "bg-white/[0.02]"}`}>
                            <td className="px-4 py-2.5 text-xs text-white/75 font-medium">{row.metric}</td>
                            <td className="px-3 py-2.5 text-center"><span className="px-2.5 py-1 rounded-lg border bg-sky-500/10 border-sky-400/20 text-sky-200 text-xs font-bold">{row.pre}</span></td>
                            <td className="px-3 py-2.5 text-center"><span className="px-2.5 py-1 rounded-lg border bg-emerald-500/10 border-emerald-400/20 text-emerald-200 text-xs font-bold">{row.post}</span></td>
                            <td className="px-3 py-2.5 text-center"><span className={`px-2.5 py-1 rounded-lg text-xs font-extrabold border ${isMissing(dVal) ? "text-white/25 bg-white/[0.03] border-white/[0.06]" : imp === true ? "text-emerald-300 bg-emerald-500/20 border-emerald-400/30" : imp === false ? "text-rose-300 bg-rose-500/20 border-rose-400/30" : "text-white/40 bg-white/[0.05] border-white/[0.08]"}`}>{dVal}</span></td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {tool === "VAS" && fd.vas?.notes && (
                <div className="mt-5 pt-4 border-t border-white/[0.08]">
                  <p className="text-[10px] font-extrabold text-white/40 uppercase tracking-widest mb-3">Pain Characteristics</p>
                  {(() => {
                    const nm = { MED:"Medication", FATIGUE:"Fatigue", SESSION:"Session", PAIN:"Pain", NOTES:"Note" };
                    return <div className="flex flex-wrap gap-1.5">{fd.vas.notes.split("\n").filter(Boolean).map((l, i) => { const e = l.indexOf("="); if (e > 0) return <span key={i} className="text-[10px] px-2 py-1 rounded-md bg-amber-400/10 border border-amber-400/15 text-amber-200 font-semibold">{(nm[l.slice(0,e)]||l.slice(0,e))+": "+l.slice(e+1)}</span>; return <span key={i} className="text-[10px] text-white/60 bg-white/[0.05] px-2 py-1 rounded-md">{l}</span>; })}</div>;
                  })()}
                </div>
              )}
            </div>
          );
        })}

        {rows.length === 0 && (
          <div className="text-center py-12">
            <FileText className="w-12 h-12 text-white/10 mx-auto mb-3" />
            <p className="text-white/40 text-sm">No assessment data yet. Fill in the assessment tabs first.</p>
          </div>
        )}
      </Glass>

      {/* Kinematics Summary (if any data) */}
      {(kinRows.length > 0 || kinCharts.length > 0) && (
        <Glass className="p-5 border-l-2 border-cyan-400/40">
          <div className="flex items-start gap-3 mb-5">
            <Cpu className="w-5 h-5 text-cyan-300 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-extrabold text-white/90">Kinematics AI Lab Summary</p>
              <p className="text-xs font-light text-white/40 mt-0.5">Generated kinematic table and movement charts</p>
            </div>
          </div>

          {kinRows.length > 0 && (
            <div className="glass-float overflow-x-auto rounded-xl border border-white/[0.08] mb-5">
              <table className="w-full text-sm min-w-[560px]">
                <thead>
                  <tr className="bg-white/[0.04] border-b border-white/[0.08]">
                    <th className="text-left px-4 py-2.5 text-xs font-extrabold text-white/50 uppercase">Variable</th>
                    <th className="text-left px-3 py-2.5 text-xs font-extrabold text-white/50 uppercase">Unit</th>
                    <th className="text-center px-3 py-2.5 text-sky-300 uppercase">Pre</th>
                    <th className="text-center px-3 py-2.5 text-emerald-300 uppercase">Post</th>
                    <th className="text-center px-3 py-2.5 text-amber-300 uppercase">Δ</th>
                  </tr>
                </thead>

                <tbody>
                  {kinRows.map((r, i) => (
                    <tr key={r.id || i} className={`border-b border-white/[0.05] hover:bg-white/[0.03] ${i % 2 === 0 ? "" : "bg-white/[0.02]"}`}>
                      <td className="px-4 py-2.5 text-xs text-white/75 font-bold">{r.name}</td>
                      <td className="px-3 py-2.5 text-center text-xs text-white/40">{r.unit || NA}</td>

                      <td className="px-3 py-2.5 text-center">
                        <span className="px-2.5 py-1 rounded-lg border bg-sky-500/10 border-sky-400/20 text-sky-200 text-xs font-bold">
                          {showVal(r.pre)}
                        </span>
                      </td>

                      <td className="px-3 py-2.5 text-center">
                        <span className="px-2.5 py-1 rounded-lg border bg-emerald-500/10 border-emerald-400/20 text-emerald-200 text-xs font-bold">
                          {showVal(r.post)}
                        </span>
                      </td>

                      <td className="px-3 py-2.5 text-center">
                        <span
                          className={`px-2.5 py-1 rounded-lg text-xs font-extrabold border ${
                            (() => {
                              const d = calcKinDelta(r.pre, r.post);
                              if (isMissing(d)) return "text-white/25 bg-white/[0.03] border-white/[0.06]";
                              const dir = kinDirectionMap(r.name);
                              const isImprovement = dir === "lower" ? d.startsWith("-") : d.startsWith("+");
                              return isImprovement
                                ? "text-emerald-300 bg-emerald-500/20 border-emerald-400/30"
                                : "text-rose-300 bg-rose-500/20 border-rose-400/30";
                            })()
                          }`}
                        >
                          {calcKinDelta(r.pre, r.post)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {kinCharts.length > 0 && (
            <div>
              <p className="text-xs font-extrabold text-white/50 uppercase mb-3 flex items-center gap-2">
                <ImageIcon className="w-3 h-3" />
                Movement Charts ({kinCharts.length})
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {kinCharts.map((src, i) => (
                  <div key={i} className="rounded-xl overflow-hidden border border-white/[0.04] bg-black/20">
                    <img src={src} alt={`Kinematic chart ${i + 1}`} className="w-full h-auto" />
                  </div>
                ))}
              </div>
            </div>
          )}
        </Glass>
      )}

      {/* Video Kinematic Analysis Results */}
      {(() => {
        const videoKin = buildVideoKinRows();
        if (!videoKin) return null;
        const preIdx = videoKin.headers.indexOf("Pre");
        const postIdx = videoKin.headers.indexOf("Post");
        const healthyIdx = videoKin.headers.indexOf("Healthy side");
        return (
          <Glass className="p-5 border-l-2 border-blue-400/40">
            <div className="flex items-start gap-3 mb-5">
              <Activity className="w-5 h-5 text-blue-300 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-extrabold text-white/90">Video Kinematic Analysis</p>
                <p className="text-xs font-light text-white/40 mt-0.5">Per-video kinematic metrics from pose estimation</p>
              </div>
            </div>
            <div className="glass-float overflow-x-auto rounded-xl border border-white/[0.08]">
              <table className="w-full text-sm min-w-[640px]">
                <thead>
                  <tr className="bg-white/[0.04] border-b border-white/[0.08]">
                    <th className="text-left px-4 py-2.5 text-xs font-extrabold text-white/50 uppercase">Variable</th>
                    <th className="text-left px-3 py-2.5 text-xs font-extrabold text-white/50 uppercase">Unit</th>
                    {videoKin.headers.slice(2).map((h, i) => (
                      <th key={i} className="text-center px-3 py-2.5 uppercase text-xs font-extrabold" style={{ color: h === "Pre" ? "#7dd3fc" : h === "Post" ? "#6ee7b7" : h === "Healthy side" ? "#fcd34d" : "#c4b5fd" }}>
                        {h}
                      </th>
                    ))}
                    {preIdx >= 0 && postIdx >= 0 && <th className="text-center px-3 py-2.5 text-xs font-extrabold text-white/50 uppercase">Pre → Post</th>}
                    {postIdx >= 0 && healthyIdx >= 0 && <th className="text-center px-3 py-2.5 text-xs font-extrabold text-white/50 uppercase">Post → Healthy</th>}
                  </tr>
                </thead>
                <tbody>
                  {videoKin.body.map((row, i) => {
                    const dir = videoKin.varMeta?.[i]?.dir || kinDirectionMap(row[0]);
                    let prePostHtml = null;
                    let postHealthyHtml = null;
                    if (preIdx >= 0 && postIdx >= 0) {
                      const preVal = parseFloat(row[preIdx]);
                      const postVal = parseFloat(row[postIdx]);
                      if (!isNaN(preVal) && !isNaN(postVal)) {
                        const metricKey = videoKin.varMeta?.[i]?.key;
                        const badge = resolveKinPrePostCell(
                          preVal, postVal, dir, metricKey || "unknown", videoKin.kr, null,
                        );
                        prePostHtml = (
                          <span className={`px-2.5 py-1 rounded-lg border text-xs font-extrabold ${badge?.colorClass || "text-white/40 bg-white/[0.05] border-white/[0.08]"}`}>
                            {badge?.text || NA}
                          </span>
                        );
                      }
                    }
                    if (postIdx >= 0 && healthyIdx >= 0) {
                      const postVal = parseFloat(row[postIdx]);
                      const helVal = parseFloat(row[healthyIdx]);
                      if (!isNaN(postVal) && !isNaN(helVal)) {
                        const badge = kinPostHealthyBadge(null, postVal, helVal, dir);
                        postHealthyHtml = (
                          <span className={`px-2.5 py-1 rounded-lg border text-xs font-extrabold ${badge?.colorClass || "text-white/40 bg-white/[0.05] border-white/[0.08]"}`}>
                            {badge?.text || NA}
                          </span>
                        );
                      }
                    }
                    return (
                      <tr key={i} className={`border-b border-white/[0.05] hover:bg-white/[0.03] ${i % 2 === 0 ? "" : "bg-white/[0.02]"}`}>
                        <td className="px-4 py-2.5 text-xs text-white/75 font-bold">{row[0]}</td>
                        <td className="px-3 py-2.5 text-center text-xs text-white/40">{row[1]}</td>
                        {row.slice(2).map((val, j) => (
                          <td key={j} className="px-3 py-2.5 text-center">
                            <span className="px-2.5 py-1 rounded-lg border bg-white/[0.06] border-white/[0.08] text-white/70 text-xs font-bold">
                              {val}
                            </span>
                          </td>
                        ))}
                        {preIdx >= 0 && postIdx >= 0 && (
                          <td className="px-3 py-2.5 text-center">{prePostHtml || <span className="text-white/25 text-xs">{NA}</span>}</td>
                        )}
                        {postIdx >= 0 && healthyIdx >= 0 && (
                          <td className="px-3 py-2.5 text-center">{postHealthyHtml || <span className="text-white/25 text-xs">{NA}</span>}</td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Glass>
        );
      })()}

      {/* Export Buttons */}
      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Professional Export Options</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* PDF */}
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={nlMotionTap(0.98)}
            onClick={exportGlassReport}
            className="flex flex-col gap-3 p-5 rounded-xl bg-rose-500/10 border border-rose-400/25 hover:bg-rose-500/15 hover:border-rose-400/40 transition-all text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-400/30 flex items-center justify-center flex-shrink-0">
                <FileText className="w-5 h-5 text-rose-300" />
              </div>
              <div>
                <p className="font-extrabold text-rose-200 text-sm">Download PDF</p>
                <p className="text-[10px] text-rose-300/60">Glassmorphism Report — Print/Save PDF</p>
              </div>
            </div>
            <p className="text-xs text-white/45 leading-relaxed">
              Opens a styled report; use the print dialog to Save as PDF (enable "Background graphics").
            </p>
          </motion.button>

          {/* Per-task Excel (clinic study) */}
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={nlMotionTap(0.98)}
            onClick={exportTaskExcels}
            className="flex flex-col gap-3 p-5 rounded-xl bg-teal-500/10 border border-teal-400/25 hover:bg-teal-500/15 hover:border-teal-400/40 transition-all text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-teal-500/20 border border-teal-400/30 flex items-center justify-center flex-shrink-0">
                <FileSpreadsheet className="w-5 h-5 text-teal-300" />
              </div>
              <div>
                <p className="font-extrabold text-teal-200 text-sm">Export Excel (per task)</p>
                <p className="text-[10px] text-teal-300/60">One file / clinical task — Drive/Excel</p>
              </div>
            </div>
            <p className="text-xs text-white/45 leading-relaxed">
              Active patients only. Each workbook has <strong className="text-white/60">one task</strong> and that task's kinematic columns (no archive, no mixed tasks).
            </p>
          </motion.button>

          {/* Current-patient Excel */}
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={nlMotionTap(0.98)}
            onClick={exportExcel}
            className="flex flex-col gap-3 p-5 rounded-xl bg-sky-500/10 border border-sky-400/25 hover:bg-sky-500/15 hover:border-sky-400/40 transition-all text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-sky-500/20 border border-sky-400/30 flex items-center justify-center flex-shrink-0">
                <FileSpreadsheet className="w-5 h-5 text-sky-300" />
              </div>
              <div>
                <p className="font-extrabold text-sky-200 text-sm">This patient Excel</p>
                <p className="text-[10px] text-sky-300/60">Clinical sheets + this task's kinematics</p>
              </div>
            </div>
            <p className="text-xs text-white/45 leading-relaxed">
              Single-patient workbook. Kinematics sheet uses only the recorded clinical task variables.
            </p>
          </motion.button>

          {/* SPSS */}
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={nlMotionTap(0.98)}
            onClick={exportSPSS}
            className="flex flex-col gap-3 p-5 rounded-xl bg-violet-500/10 border border-violet-400/25 hover:bg-violet-500/15 hover:border-violet-400/40 transition-all text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-violet-500/20 border border-violet-400/30 flex items-center justify-center flex-shrink-0">
                <Database className="w-5 h-5 text-violet-300" />
              </div>
              <div>
                <p className="font-extrabold text-violet-200 text-sm">Export SPSS CSVs</p>
                <p className="text-[10px] text-violet-300/60">Master + AOMI / Control full datasets</p>
              </div>
            </div>
            <p className="text-xs text-white/45 leading-relaxed">
              Downloads <strong className="text-white/60">master_study_data.csv</strong>, optional group splits, and <strong className="text-white/60">neuro_study_analysis.sps</strong> (use the master file in SPSS).
            </p>
          </motion.button>

          {/* JSON */}
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={nlMotionTap(0.98)}
            onClick={exportJSON}
            className="flex flex-col gap-3 p-5 rounded-xl bg-emerald-500/10 border border-emerald-400/25 hover:bg-emerald-500/15 hover:border-emerald-400/40 transition-all text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-400/30 flex items-center justify-center flex-shrink-0">
                <Database className="w-5 h-5 text-emerald-300" />
              </div>
              <div>
                <p className="font-extrabold text-emerald-200 text-sm">Export JSON</p>
                <p className="text-[10px] text-emerald-300/60">R / Python Ready</p>
              </div>
            </div>
            <p className="text-xs text-white/45 leading-relaxed">
              Full dataset as JSON for external analysis in R or Python.
            </p>
          </motion.button>

          {/* SPSS Syntax */}
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={nlMotionTap(0.98)}
            onClick={exportSPSSyntax}
            className="flex flex-col gap-3 p-5 rounded-xl bg-indigo-500/10 border border-indigo-400/25 hover:bg-indigo-500/15 hover:border-indigo-400/40 transition-all text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center flex-shrink-0">
                <FileText className="w-5 h-5 text-indigo-300" />
              </div>
              <div>
                <p className="font-extrabold text-indigo-200 text-sm">SPSS Syntax (.sps)</p>
                <p className="text-[10px] text-indigo-300/60">Variable Labels + Values + Measure</p>
              </div>
            </div>
            <p className="text-xs text-white/45 leading-relaxed">
              Run this syntax before analysis — auto-defines all variable labels, value labels, and measure levels.
            </p>
          </motion.button>
        </div>
      </Glass>
    </div>
  );
};

// ??? Analysis Dashboard ???????????????????????????????????????????????????????????

function _mean(arr) { return arr.reduce((a, b) => a + b, 0) / arr.length; }
function _sd(arr) { const m = _mean(arr); return Math.sqrt(arr.reduce((s, x) => s + (x - m) ** 2, 0) / (arr.length - 1)); }

function _ttestWelch(a, b) {
  const na = a.length, nb = b.length;
  const ma = _mean(a), mb = _mean(b);
  const va = a.reduce((s, x) => s + (x - ma) ** 2, 0) / (na - 1);
  const vb = b.reduce((s, x) => s + (x - mb) ** 2, 0) / (nb - 1);
  const se = Math.sqrt(va / na + vb / nb);
  if (se === 0) return { t: 0, df: 0, p: 1 };
  const t = (ma - mb) / se;
  const df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1));
  const p = 2 * (1 - _tcdf(Math.abs(t), df));
  const d = (ma - mb) / Math.sqrt((va * (na - 1) + vb * (nb - 1)) / (na + nb - 2));
  return { t, df: Math.round(df), p, d, m1: ma, m2: mb };
}
function _ttestPaired(a, b) {
  const d = a.map((x, i) => x - b[i]);
  const m = _mean(d), s = _sd(d), n = d.length;
  const se = s / Math.sqrt(n);
  if (se === 0) return { t: 0, df: n - 1, p: 1, d: 0 };
  const t = m / se;
  const p = 2 * (1 - _tcdf(Math.abs(t), n - 1));
  const dz = m / s;
  return { t, df: n - 1, p, dz, m, sd: s };
}
function _tcdf(x, df) {
  // Approximation of Student's t CDF
  const a = df / 2, b = 0.5, z = df / (df + x * x);
  return _betainc(z, a, b);
}
function _betainc(x, a, b) {
  // Continued fraction approximation for regularized incomplete beta
  if (x < 0 || x > 1) return 0;
  if (x === 0 || x === 1) return x;
  const bt = Math.exp(_lgamma(a + b) - _lgamma(a) - _lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
  if (x < (a + 1) / (a + b + 2)) return bt * _betacf(x, a, b) / a;
  return 1 - bt * _betacf(1 - x, b, a) / b;
}
function _betacf(x, a, b) {
  const qab = a + b, qap = a + 1, qam = a - 1;
  let c = 1, d = 1 - qab * x / qap;
  if (Math.abs(d) < 1e-20) d = 1e-20;
  d = 1 / d; let h = d;
  for (let m = 1; m <= 200; m++) {
    const m2 = 2 * m;
    const aa = m * (b - m) * x / ((qam + m2) * (a + m2));
    d = 1 + aa * d; if (Math.abs(d) < 1e-20) d = 1e-20;
    c = 1 + aa / c; if (Math.abs(c) < 1e-20) c = 1e-20;
    d = 1 / d; h *= d * c;
    const aa2 = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
    d = 1 + aa2 * d; if (Math.abs(d) < 1e-20) d = 1e-20;
    c = 1 + aa2 / c; if (Math.abs(c) < 1e-20) c = 1e-20;
    d = 1 / d; const del = d * c; h *= del;
    if (Math.abs(del - 1) < 1e-10) break;
  }
  return h;
}
function _lgamma(z) {
  // Stirling's approximation for log-gamma
  if (z < 0.5) return Math.PI > 0 ? Math.log(Math.PI / Math.sin(Math.PI * z)) - _lgamma(1 - z) : 0;
  z -= 1;
  const g = 7, c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  let x = c[0];
  for (let i = 1; i < g + 2; i++) x += c[i] / (z + i);
  const t = z + g + 0.5;
  return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
}

function _mannWhitney(a, b) {
  const all = a.map((v) => ({ v, g: 0 })).concat(b.map((v) => ({ v, g: 1 })));
  all.sort((x, y) => x.v - y.v);
  let r1 = 0;
  for (let i = 0; i < all.length; i++) {
    let j = i;
    while (j < all.length - 1 && all[j + 1].v === all[i].v) j++;
    const rank = (i + j + 2) / 2;
    for (let k = i; k <= j; k++) if (all[k].g === 0) r1 += rank;
    i = j;
  }
  const n1 = a.length, n2 = b.length;
  const u = r1 - n1 * (n1 + 1) / 2;
  const mu = n1 * n2 / 2;
  const su = Math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12);
  const z = (u - mu) / (su || 1);
  const p = 2 * (1 - _pnorm(Math.abs(z)));
  const rb = z / Math.sqrt(n1 + n2);
  return { u, z, p, rb };
}
function _pnorm(z) {
  // Standard normal CDF approximation
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const sign = z < 0 ? -1 : 1; z = Math.abs(z);
  const t = 1 / (1 + p * z);
  const y = 1 - (((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-z * z / 2));
  return 0.5 * (1 + sign * y);
}

function _skewness(arr) {
  const m = _mean(arr), n = arr.length;
  const s2 = arr.reduce((s, x) => s + (x - m) ** 2, 0) / n;
  const s3 = arr.reduce((s, x) => s + (x - m) ** 3, 0) / n;
  return s2 > 0 ? s3 / (s2 ** 1.5) : 0;
}
function _kurtosis(arr) {
  const m = _mean(arr), n = arr.length;
  const s2 = arr.reduce((s, x) => s + (x - m) ** 2, 0) / n;
  const s4 = arr.reduce((s, x) => s + (x - m) ** 4, 0) / n;
  return s2 > 0 ? s4 / (s2 ** 2) - 3 : 0;
}
function _normalityCheck(arr) {
  if (arr.length < 3) return null;
  const skew = _skewness(arr), kurt = _kurtosis(arr);
  // D'Agostino-Pearson heuristic: |skew| < 2 AND |kurt| < 7
  const normal = Math.abs(skew) < 2 && Math.abs(kurt) < 7;
  return { normal, skew: skew.toFixed(3), kurt: kurt.toFixed(3) };
}

const CONSORT_LS_KEY = "neurolab_consort_v1";

const AnalysisDashboard = () => {
  const [tab, setTab] = useState("plan");
  const [backendReport, setBackendReport] = useState(null);
  const [runningBackend, setRunningBackend] = useState(false);
  const [locfExport, setLocfExport] = useState(false);
  const [consort, setConsort] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(CONSORT_LS_KEY) || "{}");
    } catch {
      return {};
    }
  });

  const saveConsort = (patch) => {
    setConsort((prev) => {
      const next = { ...prev, ...patch };
      localStorage.setItem(CONSORT_LS_KEY, JSON.stringify(next));
      return next;
    });
  };

  const pts = activePatients();
  const n = pts.length;
  const aomi = pts.filter((p) => p.demographics?.group === "1");
  const ctrl = pts.filter((p) => p.demographics?.group === "2");
  const rawRows = buildMasterDataset(pts, WMFT_ITEMS, KGIA_MOVEMENTS, IPAQ_ACTS, { locf: locfExport });
  const rows = rawRows;
  const outcomes = analyzeAllOutcomes(rows);

  const kinComplete = pts.filter((p) => getPatientKinPhase(p, "pre") && getPatientKinPhase(p, "post")).length;
  const healthyComplete = pts.filter((p) => getPatientKinPhase(p, "baseline")).length;
  const randomized = pts.filter((p) => p.demographics?.group === "1" || p.demographics?.group === "2").length;

  const normalityForOutcome = (r) => {
    if (!r?.pre || !r?.post) return null;
    const vals = rows.flatMap((row) => [parseFloat(row[r.pre]), parseFloat(row[r.post])]).filter((v) => !isNaN(v));
    return _normalityCheck(vals);
  };

  const missingFields = [];
  pts.forEach((pt) => {
    const d = pt.demographics || {};
    const id = d.participantId || NA;
    if (!d.participantId) missingFields.push({ id, field: "Study ID" });
    if (!d.group) missingFields.push({ id, field: "Group" });
    if (!getPatientKinPhase(pt, "pre")) missingFields.push({ id, field: "Kinematics Pre" });
    if (!getPatientKinPhase(pt, "post")) missingFields.push({ id, field: "Kinematics Post" });
  });

  const downloadMasterCsv = () => {
    if (!rows.length) { alert("No patient data to export"); return; }
    const csv = XLSX.utils.sheet_to_csv(XLSX.utils.json_to_sheet(rows));
    downloadBlob(new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" }), "master_study_data.csv");
  };

  const downloadTaskExcels = async () => {
    const result = await syncTaskExcelsToDrive(pts, { downloadLocal: true });
    if (!result.count) {
      alert("No active task kinematics for Excel export (archived sessions are excluded)");
      return;
    }
    alert(`Exported ${result.count} task Excel file(s). Drive upload: ${result.uploaded}/${result.count} — RAED_AI_Backups/Excel/`);
  };

  const downloadSpssSyntax = () => {
    // eslint-disable-next-line no-undef
    downloadBlob(
      new Blob(["\uFEFF" + generateStudySPSSyntax("master_study_data.csv", rows[0])], { type: "text/plain;charset=utf-8" }),
      "neuro_study_analysis.sps"
    );
  };

  const runBackendAnalysis = async () => {
    if (!rows.length) return;
    setRunningBackend(true);
    try {
      const res = await fetch(`${API_BASE}/study-analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rows }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setBackendReport(data);
      setTab("results");
    } catch (e) {
      alert(`Backend analysis unavailable (${e.message}). Use preliminary table or run: python study_analysis.py master_study_data.csv`);
    }
    setRunningBackend(false);
  };

  const TabBtn = ({ id, label }) => (
    <button
      type="button"
      onClick={() => setTab(id)}
      className={`px-4 py-2 rounded-xl text-xs font-extrabold transition-all ${tab === id ? "bg-violet-500/30 border border-violet-400/40 text-violet-100" : "bg-white/[0.06] border border-white/10 text-white/50 hover:text-white/80"}`}
    >
      {label}
    </button>
  );

  return (
    <div className="space-y-5">
      <SH icon={BarChart3} en="Analysis Dashboard" tr="Analysis" badge="RCT v6" />

      <div className="flex flex-wrap gap-2">
        <TabBtn id="plan" label="Analysis Plan" />
        <TabBtn id="results" label="Results Preview" />
        <TabBtn id="export" label="SPSS Export" />
        <TabBtn id="thesis" label="Thesis Docs" />
      </div>

      {/* Enrollment ? always visible */}
      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Enrollment (target n={STUDY_DESIGN.targetN})</p>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[
            { label: "Total", val: n, color: "text-white" },
            { label: "AOMI", val: aomi.length, color: "text-teal-300" },
            { label: "Control", val: ctrl.length, color: "text-rose-300" },
            { label: "Kin complete", val: kinComplete, color: "text-sky-300" },
            { label: "Ready for ANOVA", val: rows.length >= 8 && aomi.length >= 2 && ctrl.length >= 2 ? "Yes" : "No", color: "text-amber-300" },
          ].map((item) => (
            <div key={item.label} className="glass-float p-3 rounded-xl bg-white/[0.09] border border-white/12 text-center">
              <p className={`text-xl font-black ${item.color}`}>{item.val}</p>
              <p className="text-[9px] text-white/40 font-bold uppercase tracking-widest mt-1">{item.label}</p>
            </div>
          ))}
        </div>
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">CONSORT Flow (live + editable)</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          {[
            { k: "screened", label: "Screened", val: consort.screened ?? "", auto: null },
            { k: "excluded", label: "Excluded", val: consort.excluded ?? "", auto: null },
            { k: "randomized", label: "Randomized", val: consort.randomized ?? randomized, auto: randomized },
            { k: "analyzed", label: "Analyzed (ITT)", val: consort.analyzed ?? kinComplete, auto: kinComplete },
          ].map(({ k, label, val, auto }) => (
            <div key={k} className="glass-float p-3 rounded-xl bg-white/[0.06] border border-white/10">
              <label className="text-[9px] text-white/40 font-bold uppercase tracking-widest">{label}</label>
              <input
                type="number"
                min="0"
                className="mt-1 w-full bg-transparent text-lg font-black text-white outline-none"
                value={val}
                placeholder={auto != null ? String(auto) : ""}
                onChange={(e) => saveConsort({ [k]: e.target.value === "" ? "" : parseInt(e.target.value, 10) })}
              />
              {auto != null && <p className="text-[9px] text-white/30 mt-1">Auto: {auto}</p>}
            </div>
          ))}
        </div>
        <p className="text-[10px] text-white/35">Healthy side collected: {healthyComplete} — LOCF export: {locfExport ? "on" : "off"}</p>
      </Glass>

      {tab === "plan" && (
        <>
          <Glass className="p-5">
            <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-3">Study Design</p>
            <p className="text-sm text-white/70 leading-relaxed mb-4">{STUDY_DESIGN.design} — Primary: <strong className="text-violet-300">{STUDY_DESIGN.primaryOutcome}</strong> — α={STUDY_DESIGN.alpha}</p>
            <div className="grid md:grid-cols-2 gap-4 text-xs">
              <div>
                <p className="font-bold text-teal-300 mb-2">Kinematic ({KINEMATIC_VARS.length} vars — manuscript tiers)</p>
                <ul className="space-y-1 text-white/60">
                  {KINEMATIC_VARS.map((k) => (
                    <li key={k.key}>
                      • {k.label} ({k.key}) — {k.tier}
                      {k.dir === "lower" ? " ↓" : k.dir === "higher" ? " ↑" : ""}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="font-bold text-amber-300 mb-2">Clinical & moderators</p>
                <ul className="space-y-1 text-white/60">
                  {CLINICAL_VARS.map((c) => (
                    <li key={c.label}>• {c.label} ({c.tier})</li>
                  ))}
                </ul>
              </div>
            </div>
          </Glass>

          <Glass className="p-5">
            <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">SPSS Workflow (12 steps)</p>
            <div className="space-y-2">
              {SPSS_WORKFLOW.map((s) => (
                <div key={s.step} className="flex gap-3 text-xs border-b border-white/[0.06] pb-2">
                  <span className="w-6 h-6 rounded-lg bg-violet-500/20 text-violet-300 font-black flex items-center justify-center flex-shrink-0">{s.step}</span>
                  <div>
                    <p className="font-bold text-white/80">{s.title}</p>
                    <p className="text-white/45 font-mono text-[10px] mt-0.5">{s.spss}</p>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-white/35 mt-4">Full document: STUDY_ANALYSIS_PLAN.md in RA.ED AI folder</p>
          </Glass>
        </>
      )}

      {tab === "results" && (
        <>
          <Glass className="p-5">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div>
                <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest">Preliminary 2×2 Analysis</p>
                <p className="text-[10px] text-amber-400/80 font-bold mt-1">Δ between groups — Group×Time interaction — confirm in SPSS GLM</p>
              </div>
              <button type="button" onClick={runBackendAnalysis} disabled={runningBackend || rows.length < 4}
                className="px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-400/30 text-emerald-200 text-xs font-extrabold disabled:opacity-40">
                {runningBackend ? "Running…" : "Run Python ANOVA (backend)"}
              </button>
            </div>

            <div className="glass-float overflow-x-auto rounded-xl border border-white/[0.08]">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-white/[0.04] border-b border-white/[0.08]">
                    <th className="text-left px-3 py-2 font-extrabold text-white/50">Outcome</th>
                    <th className="text-center px-2 py-2 text-emerald-200">Normal</th>
                    <th className="text-center px-2 py-2 text-sky-300">AOMI Pre</th>
                    <th className="text-center px-2 py-2 text-emerald-300">AOMI Post</th>
                    <th className="text-center px-2 py-2 text-rose-300">Ctrl Pre</th>
                    <th className="text-center px-2 py-2 text-amber-300">Ctrl Post</th>
                    <th className="text-center px-2 py-2 text-violet-300">AOMI Δ p</th>
                    <th className="text-center px-2 py-2 text-violet-300">Ctrl Δ p</th>
                    <th className="text-center px-2 py-2 font-extrabold text-white">Group Δ p</th>
                    <th className="text-center px-2 py-2">d</th>
              </tr>
            </thead>
            <tbody>
                  {outcomes.map((r) => {
                    const fmtM = (s) => s ? `${s.mean}±${s.sd}` : NA;
                    const norm = normalityForOutcome(r);
                return (
                      <tr key={r.label} className={`border-b border-white/[0.04] ${r.isPrimary ? "bg-violet-500/10" : ""}`}>
                        <td className="px-3 py-2 text-white/70 font-medium">
                          {r.isPrimary ? "★ " : ""}{r.label}
                          {r.pre?.includes("_Pre") && r.label && (
                            <span className="block text-[9px] text-white/30 font-normal">{r.pre?.replace("_Pre", "")}</span>
                          )}
                        </td>
                        <td className="px-2 py-2 text-center text-[10px]">
                          {norm ? (norm.normal ? <span className="text-emerald-400" title={`skew=${norm.skew} kurt=${norm.kurt}`}>Yes</span> : <span className="text-amber-400" title={`skew=${norm.skew} kurt=${norm.kurt}`}>NP</span>) : NA}
                        </td>
                        <td className="px-2 py-2 text-center text-white/55">{fmtM(r.aomiPre)}</td>
                        <td className="px-2 py-2 text-center text-white/55">{fmtM(r.aomiPost)}</td>
                        <td className="px-2 py-2 text-center text-white/55">{fmtM(r.ctrlPre)}</td>
                        <td className="px-2 py-2 text-center text-white/55">{fmtM(r.ctrlPost)}</td>
                        <td className="px-2 py-2 text-center">{fmtP(r.withinAomi?.p)}{sigStars(r.withinAomi?.p)}</td>
                        <td className="px-2 py-2 text-center">{fmtP(r.withinCtrl?.p)}{sigStars(r.withinCtrl?.p)}</td>
                        <td className="px-2 py-2 text-center font-bold text-white">{fmtP(r.betweenDelta?.p)}{sigStars(r.betweenDelta?.p)}</td>
                        <td className="px-2 py-2 text-center text-white/50">{r.betweenDelta?.es != null ? Math.abs(r.betweenDelta.es).toFixed(2) : NA}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Glass>

          {backendReport?.outcomes && (
            <>
        <Glass className="p-5">
              <p className="text-xs font-extrabold text-emerald-300 uppercase tracking-widest mb-4">Backend Mixed ANOVA (Group × Time)</p>
              <div className="overflow-x-auto rounded-xl border border-emerald-500/20">
            <table className="w-full text-xs">
              <thead>
                    <tr className="bg-emerald-500/10">
                      <th className="text-left px-3 py-2 text-emerald-200">Outcome</th>
                      <th className="text-center px-3 py-2">F (interaction)</th>
                      <th className="text-center px-3 py-2">p</th>
                      <th className="text-center px-3 py-2">ηp²</th>
                </tr>
              </thead>
              <tbody>
                    {backendReport.outcomes.map((o) => {
                      const ix = o.mixed_anova?.interaction;
                  return (
                        <tr key={o.base} className="border-b border-white/[0.04]">
                          <td className="px-3 py-2 text-white/70">{o.label}</td>
                          <td className="px-3 py-2 text-center text-white/60">{ix ? ix.F.toFixed(3) : NA}</td>
                          <td className="px-3 py-2 text-center font-bold">{ix ? fmtP(ix.p) : NA}</td>
                          <td className="px-3 py-2 text-center text-white/50">{ix ? ix.eta_p2 : NA}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Glass>
          {backendReport?.holm_secondary_kinematic && (
        <Glass className="p-5">
              <p className="text-xs font-extrabold text-amber-300 uppercase tracking-widest mb-4">Holm–Bonferroni (secondary kinematic, k={KINEMATIC_VARS.filter((k) => k.tier === "secondary").length})</p>
              <div className="overflow-x-auto rounded-xl border border-amber-500/20">
            <table className="w-full text-xs">
              <thead>
                    <tr className="bg-amber-500/10">
                      <th className="text-left px-3 py-2 text-amber-200">Variable</th>
                      <th className="text-center px-3 py-2">p (interaction)</th>
                      <th className="text-center px-3 py-2">Holm α</th>
                      <th className="text-center px-3 py-2">Sig</th>
                </tr>
              </thead>
              <tbody>
                    {backendReport.holm_secondary_kinematic.map((h) => (
                      <tr key={h.name} className="border-b border-white/[0.04]">
                        <td className="px-3 py-2 text-white/70">{h.name}</td>
                        <td className="px-3 py-2 text-center">{fmtP(h.p)}</td>
                        <td className="px-3 py-2 text-center text-white/50">{h.holm_alpha}</td>
                        <td className="px-3 py-2 text-center font-bold">{h.significant ? "Yes" : "No"}</td>
                    </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </Glass>
          )}
            </>
          )}
        </>
      )}

      {tab === "thesis" && (
        <>
        <Glass className="p-5">
            <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Thesis Documents</p>
            <p className="text-sm text-white/60 mb-4">Literature review (condensed Introduction) and CONSORT + SAP for committee review.</p>
            <div className="flex flex-wrap gap-3">
              <button type="button" onClick={() => downloadBlob(new Blob(["\uFEFF" + generateLiteratureReviewMarkdown()], { type: "text/markdown;charset=utf-8" }), "THESIS_LITERATURE_REVIEW.md")} className="px-5 py-2.5 rounded-xl bg-teal-500/20 border border-teal-400/30 text-teal-200 text-xs font-extrabold">
                Literature Review
              </button>
              <button type="button" onClick={() => downloadBlob(new Blob(["\uFEFF" + generateConsortSapMarkdown()], { type: "text/markdown;charset=utf-8" }), "THESIS_CONSORT_SAP.md")} className="px-5 py-2.5 rounded-xl bg-violet-500/20 border border-violet-400/30 text-violet-200 text-xs font-extrabold">
                CONSORT + SAP
              </button>
          </div>
        </Glass>

          <Glass className="p-5">
            <p className="text-xs font-extrabold text-rose-300 uppercase tracking-widest mb-4">Program Roadmap (what RA.ED AI still needs)</p>
            <div className="space-y-2">
              {PROGRAM_GAPS.map((g) => (
                <div key={g.item} className="flex gap-3 text-xs border-b border-white/[0.06] pb-2">
                  <span className={`shrink-0 px-2 py-0.5 rounded-md font-bold uppercase text-[9px] ${g.priority === "high" ? "bg-rose-500/20 text-rose-300" : g.priority === "medium" ? "bg-amber-500/20 text-amber-300" : "bg-white/10 text-white/40"}`}>{g.priority}</span>
                  <div>
                    <p className="font-bold text-white/80">{g.item}</p>
                    <p className="text-white/45 mt-0.5">{g.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </Glass>
        </>
      )}

      {tab === "export" && (
      <Glass className="p-5">
          <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Post-Study Export Package</p>
          <p className="text-sm text-white/60 mb-4">After data collection: export master CSV → open in SPSS → run syntax → copy GLM tables to manuscript.</p>
          <label className="flex items-center gap-2 text-xs text-white/60 mb-4 cursor-pointer">
            <input type="checkbox" checked={locfExport} onChange={(e) => setLocfExport(e.target.checked)} className="rounded" />
            Apply LOCF imputation (missing Post → Pre) for ITT export
          </label>
        <div className="flex flex-wrap gap-3">
            <button type="button" onClick={downloadTaskExcels} className="px-5 py-2.5 rounded-xl bg-teal-500/20 border border-teal-400/30 text-teal-200 text-xs font-extrabold hover:bg-teal-500/30">
              Excel per task — Drive/Excel
            </button>
            <button type="button" onClick={downloadMasterCsv} className="px-5 py-2.5 rounded-xl bg-violet-500/20 border border-violet-400/30 text-violet-200 text-xs font-extrabold hover:bg-violet-500/30">
              master_study_data.csv
            </button>
            <button type="button" onClick={downloadSpssSyntax} className="px-5 py-2.5 rounded-xl bg-sky-500/20 border border-sky-400/30 text-sky-200 text-xs font-extrabold hover:bg-sky-500/30">
              neuro_study_analysis.sps
            </button>
            <button type="button" onClick={() => {
            const allPts = activePatients();
              downloadBlob(new Blob([JSON.stringify(allPts, null, 2)], { type: "application/json" }), `neuro_backup_${allPts.length}pts.json`);
            }} className="px-5 py-2.5 rounded-xl bg-emerald-500/20 border border-emerald-400/30 text-emerald-200 text-xs font-extrabold">
              JSON backup
            </button>
          </div>
          <p className="text-[10px] text-white/35 mt-4 font-mono">Excel: one file per clinical task (task variables only; archive excluded). Path: RAED_AI_Backups/Excel/</p>
        </Glass>
      )}

      {missingFields.length > 0 && (
        <Glass className="p-5">
          <p className="text-xs font-extrabold text-rose-300 uppercase tracking-widest mb-3">Missing Data ({missingFields.length})</p>
          <div className="max-h-40 overflow-y-auto text-xs text-white/50 space-y-1">
            {missingFields.slice(0, 20).map((m, i) => (
              <p key={i}>{m.id}: {m.field}</p>
            ))}
            {missingFields.length > 20 && <p>and {missingFields.length - 20} more</p>}
        </div>
      </Glass>
      )}
    </div>
  );
};

// ??? Root App ?????????????????????????????????????????????????????????????????

const getTodayDate = () => new Date().toISOString().split("T")[0];

const SECTION_NAV_ORDER = [
  ...NAV_ITEMS.filter((n) => !n.topBarOnly).map((n) => n.id),
  "analysis",
  "database",
  "users",
];
const BOUNCE_OUT_MS = 150;
const BOUNCE_IN_MS = 280;
const BOUNCE_OUT_FALLBACK_MS = BOUNCE_OUT_MS + 60;

const StableSectionView = React.memo(
  function StableSectionView({ sectionId, renderSection }) {
    return renderSection(sectionId);
  },
  (prev, next) =>
    prev.sectionId === next.sectionId && prev.renderSection === next.renderSection,
);

function SectionTransition({
  sectionId,
  renderSection,
  navPhase,
  contentRef,
  mobileNav,
  onExitComplete,
  onBeginEnter,
  onEnterComplete,
}) {
  const reduceMotion = useReducedMotion();
  const exiting = navPhase === "exiting" && !reduceMotion;
  const mounting = navPhase === "mounting" && !reduceMotion;
  const entering = navPhase === "entering" && !reduceMotion;
  const animating = exiting || mounting || entering;
  const mobileFade = mobileNav && !reduceMotion;
  const beginEnterRef = useRef(onBeginEnter);
  beginEnterRef.current = onBeginEnter;

  useLayoutEffect(() => {
    if (!mounting || reduceMotion) return;
    let cancelled = false;
    const startEnter = () => {
      if (cancelled) return;
      beginEnterRef.current?.();
    };

    let raf2 = 0;
    const raf1 = requestAnimationFrame(() => {
      if (cancelled) return;
      raf2 = requestAnimationFrame(startEnter);
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf1);
      if (raf2) cancelAnimationFrame(raf2);
    };
  }, [mounting, reduceMotion, sectionId]);

  const handleAnimEnd = (e) => {
    if (e.target !== e.currentTarget) return;
    const name = e.animationName || "";
    if (exiting && (name.startsWith("nl-bounce-out") || name.startsWith("nl-mobile-fade-out"))) {
      onExitComplete?.();
    }
    if (entering && (name.startsWith("nl-bounce-in") || name.startsWith("nl-mobile-fade-in"))) {
      onEnterComplete?.();
    }
  };

  const paneAnimClass = mobileFade
    ? `${exiting ? " section-fade-out" : ""}${mounting ? " section-fade-mount" : ""}${
        entering ? " section-fade-in" : ""
      }`
    : `${exiting ? " section-bounce-out" : ""}${mounting ? " section-bounce-mount" : ""}${
        entering ? " section-bounce-mount section-bounce-in" : ""
      }`;

  return (
    <div
      className={`section-transition-host min-h-[420px]${
        mobileNav ? " section-transition-host-mobile" : ""
      }${animating ? " section-transition-animating" : ""}`}
      aria-busy={animating}
    >
      <div ref={contentRef} className="section-pane section-content-root">
        <div
          onAnimationEnd={handleAnimEnd}
          className={`section-nav-motion${paneAnimClass}`}
        >
          <StableSectionView sectionId={sectionId} renderSection={renderSection} />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [active, setActive] = useState(loadStoredActiveSection);
  const [sidebarActiveId, setSidebarActiveId] = useState(loadStoredActiveSection);
  const [navPhase, setNavPhase] = useState("idle");
  const navPhaseRef = useRef("idle");
  navPhaseRef.current = navPhase;
  const [sectionNavLocked, setSectionNavLocked] = useState(false);
  const sectionContentRef = useRef(null);
  const isDesktopNavRef = useRef(
    typeof window !== "undefined" ? window.matchMedia("(min-width: 768px)").matches : true,
  );
  const slideOutFallbackRef = useRef(null);
  const slideInFallbackRef = useRef(null);
  const mountEnterFallbackRef = useRef(null);
  const slideTargetRef = useRef(null);
  const outgoingDoneRef = useRef(false);
  const incomingDoneRef = useRef(false);
  const pendingNavRef = useRef(null);
  const goToSectionRef = useRef(null);
  const prevSectionRef = useRef(loadStoredActiveSection());

  const clearSlideTimers = useCallback(() => {
    if (slideOutFallbackRef.current) {
      clearTimeout(slideOutFallbackRef.current);
      slideOutFallbackRef.current = null;
    }
    if (slideInFallbackRef.current) {
      clearTimeout(slideInFallbackRef.current);
      slideInFallbackRef.current = null;
    }
    if (mountEnterFallbackRef.current) {
      clearTimeout(mountEnterFallbackRef.current);
      mountEnterFallbackRef.current = null;
    }
  }, []);

  const finishSectionNav = useCallback(() => {
    clearSlideTimers();
    setNavPhase("idle");
    setSectionNavLocked(false);
    slideTargetRef.current = null;
    outgoingDoneRef.current = false;
    incomingDoneRef.current = false;
    const pending = pendingNavRef.current;
    pendingNavRef.current = null;
    if (pending) {
      requestAnimationFrame(() => {
        goToSectionRef.current?.(pending, { force: true });
      });
    }
  }, [clearSlideTimers]);

  const beginEnterPhase = useCallback(() => {
    if (navPhaseRef.current !== "mounting") return;
    if (mountEnterFallbackRef.current) {
      clearTimeout(mountEnterFallbackRef.current);
      mountEnterFallbackRef.current = null;
    }
    setNavPhase("entering");
    slideInFallbackRef.current = setTimeout(() => {
      finishSectionNav();
    }, BOUNCE_IN_MS + 40);
  }, [finishSectionNav]);

  const completeExitPhase = useCallback(() => {
    if (outgoingDoneRef.current) return;
    outgoingDoneRef.current = true;
    incomingDoneRef.current = false;
    if (slideOutFallbackRef.current) {
      clearTimeout(slideOutFallbackRef.current);
      slideOutFallbackRef.current = null;
    }
    const targetId = slideTargetRef.current;
    if (!targetId) {
      finishSectionNav();
      return;
    }
    setNavPhase("mounting");
    setActive(targetId);
  }, [finishSectionNav]);

  const handleIncomingComplete = useCallback(() => {
    if (incomingDoneRef.current) return;
    incomingDoneRef.current = true;
    finishSectionNav();
  }, [finishSectionNav]);

  const goToSection = useCallback((id, { force = false } = {}) => {
    if (!ACTIVE_SECTION_IDS.has(id)) return;
    if (sectionNavLocked && !force) {
      pendingNavRef.current = id;
      return;
    }
    if (id === active && !sectionNavLocked) return;

    setSidebarActiveId(id);

    pendingNavRef.current = null;
    clearSlideTimers();
    setNavPhase("idle");
    outgoingDoneRef.current = false;
    incomingDoneRef.current = false;
    prevSectionRef.current = id;

    setSectionNavLocked(false);
    startTransition(() => setActive(id));
  }, [active, clearSlideTimers, sectionNavLocked]);

  goToSectionRef.current = goToSection;
  const [sidebar, setSidebar] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(min-width: 768px)").matches : true
  );
  const [isDesktop, setIsDesktop] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(min-width: 768px)").matches : true
  );
  const [sidebarPush, setSidebarPush] = useState(() =>
    typeof window !== "undefined" ? sidebarPushWidth() : SIDEBAR_W
  );
  const useDesktopTopBar = isDesktop;
  const useMobileMenuPortal = true;
  const [bgUrl, setBgUrl] = useState(BG);
  const [importPreview, setImportPreview] = useState(null);
  const [user, setUser] = useState(null);
  const [mobileTopMenuOpen, setMobileTopMenuOpen] = useState(false);
  const [toast, setToast] = useState({ visible: false, msg: "", variant: "success" });
  const [originRestoreBanner, setOriginRestoreBanner] = useState("");
  const bgRef = useRef(null);
  const importRef = useRef(null);
  const topBarWrapperRef = useRef(null);
  const topBarSpacerRef = useRef(null);
  const appScrollRef = useRef(null);
  const ptrSpinnerAnchorRef = useRef(null);
  const mobileMenuRef = useRef(null);
  const iosPullScroll =
    typeof window !== "undefined" && (isIOSDevice() || isStandalonePWA());
  const touchUi = typeof window !== "undefined" && isTouchUi();

  useEffect(() => {
    if (!touchUi) return undefined;
    document.documentElement.classList.add("nl-touch");
    return () => document.documentElement.classList.remove("nl-touch");
  }, [touchUi]);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const syncLayout = () => {
      setIsDesktop(mq.matches);
      isDesktopNavRef.current = mq.matches;
      setSidebarPush(sidebarPushWidth());
    };
    syncLayout();
    mq.addEventListener("change", syncLayout);
    window.addEventListener("resize", syncLayout);
    return () => {
      mq.removeEventListener("change", syncLayout);
      window.removeEventListener("resize", syncLayout);
    };
  }, []);

  useLayoutEffect(() => {
    const el = topBarWrapperRef.current;
    if (!el) return undefined;
    const spacer = topBarSpacerRef.current;
    let lastH = 0;
    const measure = () => {
      const h = Math.ceil(el.getBoundingClientRect().height);
      if (h <= 0 || h === lastH) return;
      lastH = h;
      if (spacer) spacer.style.height = `${h}px`;
    };
    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [iosPullScroll]);

  useEffect(() => () => finishSectionNav(), [finishSectionNav]);

  useEffect(() => {
    fetch("/auth/me", { credentials: "same-origin", headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        setUser(data);
        const email = data.last_login_email || data.email;
        if (email) rememberLoginEmail(email);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    // Swipe from left edge to open sidebar; swipe left to close it (mobile only)
    if (isDesktop) return;
    let startX = null;
    let startY = null;

    const onTouchStart = (e) => {
      if (!e.touches?.length) return;
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
    };

    const onTouchEnd = (e) => {
      if (startX == null || startY == null || !e.changedTouches?.length) return;
      const endX = e.changedTouches[0].clientX;
      const endY = e.changedTouches[0].clientY;
      const dx = endX - startX;
      const dy = endY - startY;
      const absDx = Math.abs(dx);
      const absDy = Math.abs(dy);
      if (absDx > absDy && absDx > 50) {
        if (startX < 28 && dx > 0 && !sidebar) {
          setSidebar(true);
        } else if (dx < 0 && sidebar) {
          setSidebar(false);
        }
      }
      startX = null;
      startY = null;
    };

    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchend", onTouchEnd, { passive: true });
    return () => {
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchend", onTouchEnd);
    };
  }, [isDesktop, sidebar]);

  useEffect(() => {
    if (!mobileTopMenuOpen || !useMobileMenuPortal) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const scroller = appScrollRef.current;
    const prevScrollOverflow = scroller ? scroller.style.overflow : "";
    if (scroller) {
      scroller.style.overflow = "hidden";
      scroller.style.touchAction = "none";
    }
    return () => {
      document.body.style.overflow = prevOverflow;
      if (scroller) {
        scroller.style.overflow = prevScrollOverflow;
        scroller.style.touchAction = "";
      }
    };
  }, [mobileTopMenuOpen, useMobileMenuPortal]);

  useEffect(() => {
    if (active === "bbt") goToSection("demographics", { force: true });
  }, [active, goToSection]);

  useEffect(() => {
    try {
      localStorage.setItem(ACTIVE_SECTION_LS_KEY, active);
    } catch {}
  }, [active]);

  useEffect(() => {
    if (navPhase !== "idle") return;
    const scrollEl = appScrollRef.current;
    requestAnimationFrame(() => {
      if (scrollEl) scrollEl.scrollTo({ top: 0, behavior: "auto" });
      else window.scrollTo({ top: 0, behavior: "auto" });
    });
  }, [active, navPhase]);

  useEffect(() => {
    if (active === "users" && user && !user.is_admin) {
      goToSection("demographics", { force: true });
    }
  }, [active, user, goToSection]);

  useEffect(() => {
    // Defer large base64 background so first paint is not competing with main.js parse.
    const loadBg = () => {
      fetch("/bg.b64.txt")
        .then((r) => (r.ok ? r.text() : Promise.reject()))
        .then((b64) => setBgUrl(`data:image/jpeg;base64,${b64.trim()}`))
        .catch(() => {});
    };
    if (typeof requestIdleCallback === "function") {
      const id = requestIdleCallback(loadBg, { timeout: 4000 });
      return () => cancelIdleCallback(id);
    }
    const t = setTimeout(loadBg, isStandalonePWA() ? 2500 : 800);
    return () => clearTimeout(t);
  }, []);

  const [fd, setFd] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(FD_LS_KEY));
      if (saved && typeof saved === "object") return saved;
    } catch {}
    return {
      demographics: { participantId: String(nextStudyId()) },
      ipaq: {},
      vas: {},
      vams: {},
      motorchange: {},
      kgia: {},
      wmft: {},
      bbt: {},
      kinematics: {},
    };
  });

  const fdSaveTimerRef = useRef(null);
  const suppressDirtyRef = useRef(true);
  const [sessionDirty, setSessionDirty] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      suppressDirtyRef.current = false;
    });
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    if (suppressDirtyRef.current) return;
    setSessionDirty(true);
  }, [fd]);

  // Auto-save all sections to localStorage on any change (debounced; slower during analyze)
  useEffect(() => {
    if (fdSaveTimerRef.current) clearTimeout(fdSaveTimerRef.current);
    const delay = isKinAnalyzeActive() ? 2000 : 500;
    fdSaveTimerRef.current = setTimeout(() => {
      try {
        localStorage.setItem(FD_LS_KEY, JSON.stringify(fd));
      } catch (e) {
        console.warn("Could not persist session to localStorage (quota or size):", e);
      }
    }, delay);
    return () => {
      if (fdSaveTimerRef.current) clearTimeout(fdSaveTimerRef.current);
    };
  }, [fd]);

  // Sync patients from server after first paint ? never block UI / Drive on boot
  useEffect(() => {
    let cancelled = false;
    const bootDelayMs = isStandalonePWA() ? 18000 : 12000;
    const attempt = () => {
      if (cancelled) return;
      if (isKinAnalyzeActive()) {
        setTimeout(attempt, 4000);
        return;
      }
      syncPatientsWithServer({ silent: true, skipDrive: true }).then(({ ok, patients: merged }) => {
        if (!ok) return;
        const curId = fd._loadedId || fd.demographics?.participantId;
        if (curId) {
          const cur = merged.find((p) => (p._id || p.demographics?.participantId) === curId);
          if (cur?.kinematics?.analysisResults) {
            localStorage.setItem(KIN_LS_KEY, JSON.stringify(cur.kinematics.analysisResults));
          }
        }
      });
    };
    const t = setTimeout(attempt, bootDelayMs);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, []);

  const upd = useCallback((sec, d) => setFd((p) => ({ ...p, [sec]: d })), []);

  const showToast = useCallback((msg, variant = "success") => {
    setToast({ visible: true, msg: formatUserMessage(msg), variant });
    const ms = String(msg || "").length > 80 ? 5600 : 2800;
    setTimeout(() => setToast({ visible: false, msg: "", variant: "success" }), ms);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams(window.location.search);
    const justConnected = params.get("drive") === "connected";
    if (justConnected) {
      params.delete("drive");
      const qs = params.toString();
      try {
        window.history.replaceState({}, "", window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash);
      } catch { /* ignore */ }
    }
    const run = () => {
      if (cancelled || isKinAnalyzeActive()) return;
      startDriveSessionRecall(loadPatients(), { showToast, force: justConnected });
    };
    const t = setTimeout(run, justConnected ? 600 : 2800);
    const onSynced = (ev) => {
      if (ev?.detail?.skipDriveRecall) return;
      if (cancelled || isKinAnalyzeActive()) return;
      startDriveSessionRecall(loadPatients(), { showToast });
    };
    window.addEventListener(PATIENTS_SYNC_EVENT, onSynced);
    return () => {
      cancelled = true;
      clearTimeout(t);
      window.removeEventListener(PATIENTS_SYNC_EVENT, onSynced);
    };
  }, [showToast]);

  // After Space rename (neurolab ? raedai): new browser origin is empty until server restore.
  useEffect(() => {
    let cancelled = false;
    let hideTimer = null;
    const run = async () => {
      let pending = false;
      let done = false;
      let localEmpty = true;
      try {
        pending = localStorage.getItem(RAED_ORIGIN_RESTORE_PENDING_KEY) === "1";
        done = localStorage.getItem(RAED_ORIGIN_RESTORE_DONE_KEY) === "1";
        localEmpty = loadPatients().length === 0;
      } catch {}
      if (done && !pending && !localEmpty) return;
      if (cancelled) return;
      setOriginRestoreBanner("Restoring your study data from the server…");
      const { ok, patients: merged } = await restoreStudyDataFromServer({
        showToast: (msg, variant) => {
          if (!cancelled) showToast(msg, variant);
        },
      });
      if (cancelled) return;
      const count = (merged || []).length;
      // Only mark done when we actually recovered rows ? otherwise retry next launch.
      if (ok && count > 0) {
        try {
          localStorage.setItem(RAED_ORIGIN_RESTORE_DONE_KEY, "1");
          localStorage.removeItem(RAED_ORIGIN_RESTORE_PENDING_KEY);
        } catch {}
      }
      if (ok) {
        window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count } }));
        setOriginRestoreBanner(
          count
            ? `Restored ${count} record(s) from server / Google Drive.`
            : "No records yet — open Database → Restore from Drive (PDFs are on Drive)."
        );
      } else {
        setOriginRestoreBanner("Could not restore yet — tap Restore from Drive in Database when the Space is awake.");
      }
      hideTimer = setTimeout(() => {
        if (!cancelled) setOriginRestoreBanner("");
      }, count > 0 ? 5000 : 12000);
    };
    const t = setTimeout(run, 600);
    return () => {
      cancelled = true;
      clearTimeout(t);
      if (hideTimer) clearTimeout(hideTimer);
    };
  }, [showToast]);

  const performSoftRefresh = useCallback(async () => {
    if (isKinAnalyzeActive()) {
      showToast("Sync paused while video analysis is running", "info");
      return;
    }
    // UI must return immediately ? Drive restore / patient push run in background.
    try {
      const r = await fetchWithTimeout("/auth/me", {}, 5000);
      if (r.ok) {
        const data = await r.json();
        if (data) setUser(data);
      }
    } catch {
      /* keep current session */
    }
    syncPatientsWithServer({ silent: true, skipDrive: true });
  }, [showToast]);

  const logout = useCallback(() => {
    clearAuthToken();
    fetch("/auth/logout", { method: "POST", credentials: "same-origin" })
      .then(() => window.location.reload());
  }, []);

  const saveSession = useCallback(() => {
    const patients = loadPatients();
    const d = fd.demographics || {};
    const studyId = String(d.participantId || "").trim();

    const hasPre = !!(fd.vas?.rest?.pre || fd.motorchange?.control || fd.vams?.happy?.pre);
    const hasPost = !!(fd.vas?.rest?.post || fd.motorchange?.difference || fd.vams?.happy?.post);

    // Match Study ID first (canonical), then internal _loadedId ? prevents duplicate rows.
    let existingIdx = -1;
    if (studyId) {
      existingIdx = patients.findIndex(
        (p) => String(p.demographics?.participantId || "").trim() === studyId
      );
    }
    if (existingIdx < 0 && fd._loadedId) {
      existingIdx = patients.findIndex((p) => p._id === fd._loadedId);
    }

    let kinResults;
    try { kinResults = JSON.parse(localStorage.getItem(KIN_LS_KEY)) || {}; } catch { kinResults = {}; }
    if (existingIdx >= 0) {
      const existing = patients[existingIdx];
      const fdWithKin = { ...fd, kinematics: { ...fd.kinematics, analysisResults: kinResults } };
      const { _loadedId, ...cleanFd } = fdWithKin;
      patients[existingIdx] = {
        ...existing,
        ...cleanFd,
        _id: existing._id,
        _savedAt: new Date().toISOString(),
        _hasPre: existing._hasPre || hasPre,
        _hasPost: existing._hasPost || hasPost,
      };
      const cleaned = savePatients(patients);
      setFd((prev) => ({ ...prev, _loadedId: existing._id }));
      window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count: cleaned.length } }));
      showToast("Session updated");
      backupSessionKinematicsVideosToDrive(fdWithKin.kinematics, d);
      syncPatientsWithServer({ silent: true }).then(({ ok }) => {
        if (!ok) showToast("Saved locally — server sync pending. Tap Sync in Database.", "error");
      });
    } else {
      // Soft-block: same full name + new Study ID was the main clinic duplicate source.
      const nameHits = findActiveByNormalizedName(patients, d.name || d.fullName, {
        excludeStudyId: studyId,
      });
      if (nameHits.length > 0) {
        const hit = nameHits[0];
        const hitId = patientStudyId(hit) || NA;
        const hitName = patientDisplayName(hit) || "this patient";
        const okUpdate = window.confirm(
          `"${hitName}" already exists as Study ID ${hitId}.\n\n` +
            `OK = update that existing record (recommended)\n` +
            `Cancel = abort save (will not create a duplicate)`
        );
        if (!okUpdate) {
          showToast("Save cancelled — open the existing patient from Database", "error");
          return;
        }
        const fdWithKin = {
          ...fd,
          demographics: {
            ...(fd.demographics || {}),
            participantId: String(hit.demographics?.participantId || hitId),
            name: hit.demographics?.name || fd.demographics?.name,
          },
          kinematics: { ...fd.kinematics, analysisResults: kinResults },
        };
        const { _loadedId, ...cleanFd } = fdWithKin;
        const idx = patients.findIndex((p) => p._id === hit._id);
        if (idx >= 0) {
          patients[idx] = {
            ...hit,
            ...cleanFd,
            _id: hit._id,
            _savedAt: new Date().toISOString(),
            _hasPre: hit._hasPre || hasPre,
            _hasPost: hit._hasPost || hasPost,
          };
        }
        const cleaned = savePatients(patients);
        setFd((prev) => ({
          ...prev,
          ...cleanFd,
          _loadedId: hit._id,
          demographics: {
            ...(prev.demographics || {}),
            ...(cleanFd.demographics || {}),
          },
        }));
        window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count: cleaned.length } }));
        showToast(`Updated existing Study ID ${hitId} (same name)`);
        backupSessionKinematicsVideosToDrive(fdWithKin.kinematics, cleanFd.demographics || d);
        syncPatientsWithServer({ silent: true }).then(({ ok }) => {
          if (!ok) showToast("Saved locally — server sync pending. Tap Sync in Database.", "error");
        });
      } else {
        const fdWithKin = { ...fd, kinematics: { ...fd.kinematics, analysisResults: kinResults } };
        const { _loadedId, ...cleanFd } = fdWithKin;
        const newId = `pt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        patients.push({
          _id: newId,
          _savedAt: new Date().toISOString(),
          _hasPre: hasPre,
          _hasPost: hasPost,
          ...cleanFd,
        });
        const cleaned = savePatients(patients);
        setFd((prev) => ({ ...prev, _loadedId: newId }));
        window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count: cleaned.length } }));
        showToast("New patient saved");
        backupSessionKinematicsVideosToDrive(fdWithKin.kinematics, d);
        syncPatientsWithServer({ silent: true }).then(({ ok }) => {
          if (!ok) showToast("Saved locally — server sync pending. Tap Sync in Database.", "error");
        });
        // Stay on the saved patient ? do NOT bump Study ID while keeping the same name/data
        // (that created duplicate people with different Study IDs, especially on iPad).
      }
    }
    suppressDirtyRef.current = true;
    setSessionDirty(false);
    requestAnimationFrame(() => {
      suppressDirtyRef.current = false;
    });
  }, [fd, showToast]);

  const confirmDiscardUnsaved = useCallback(() => {
    if (!sessionDirty) return true;
    try {
      return window.confirm("Unsaved session changes will be lost. Continue?");
    } catch {
      return true;
    }
  }, [sessionDirty]);

  const newSession = useCallback(() => {
    if (!confirmDiscardUnsaved()) return;
    localStorage.setItem("neuro_last_session_backup", JSON.stringify(fd));
    localStorage.removeItem(KIN_LS_KEY);
    suppressDirtyRef.current = true;
    setSessionDirty(false);
    setFd({
      demographics: { participantId: String(nextStudyId()) },
      ipaq: {},
      vas: {},
      vams: {},
      motorchange: {},
      kgia: {},
      wmft: {},
      bbt: {},
      kinematics: {},
    });
    goToSection("demographics");
    if (!isDesktop) setSidebar(false);
    showToast("New session started");
    requestAnimationFrame(() => {
      suppressDirtyRef.current = false;
    });
  }, [fd, showToast, isDesktop, goToSection, confirmDiscardUnsaved]);

  const handleLoadSession = useCallback((record, opts = {}) => {
    if (!confirmDiscardUnsaved()) return;
    const { _id, _savedAt, _hasPre, _hasPost, ...sessionData } = record;
    suppressDirtyRef.current = true;
    setSessionDirty(false);
    setFd((prev) => ({ ...prev, ...sessionData, _loadedId: _id }));
    if (sessionData.kinematics?.analysisResults) {
      localStorage.setItem(KIN_LS_KEY, JSON.stringify(sessionData.kinematics.analysisResults));
    }
    const nextSection = opts.section && ACTIVE_SECTION_IDS.has(opts.section)
      ? opts.section
      : "demographics";
    goToSection(nextSection);
    showToast(`Loaded: ${record.demographics?.name || record.demographics?.participantId || "patient"}`);
    requestAnimationFrame(() => {
      suppressDirtyRef.current = false;
    });
  }, [showToast, goToSection, confirmDiscardUnsaved]);

  const handleImportFile = useCallback(async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      const { patient: normalized, extractedText } = await importPatientFile(file);
      const record = buildImportRecord(normalized);

      const demo = record.demographics || {};
      const hasAnyDemo = Object.values(demo).some((v) => v != null && v !== "");
      if (!hasAnyDemo) {
        setImportPreview({ record, extractedText });
        return;
      }

      const patients = loadPatients();
      const pid = record.demographics?.participantId;
      const idx = pid
        ? patients.findIndex((p) => p.demographics?.participantId === pid)
        : -1;
      if (idx >= 0) {
        patients[idx] = { ...patients[idx], ...record, _id: patients[idx]._id };
        record._id = patients[idx]._id;
      } else {
        patients.push(record);
      }
      savePatients(patients);
      window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count: patients.length } }));
      handleLoadSession(record);
      syncPatientsWithServer({ silent: true });
    } catch (err) {
      showToast(`Import failed: ${err?.message || "Unknown error"}`, "error");
    }
  }, [handleLoadSession, showToast]);

  const confirmImportPreview = () => {
    if (!importPreview) return;
    const record = importPreview.record;
    const patients = loadPatients();
    const pid = record.demographics?.participantId;
    const idx = pid
      ? patients.findIndex((p) => p.demographics?.participantId === pid)
      : -1;
    if (idx >= 0) {
      patients[idx] = { ...patients[idx], ...record, _id: patients[idx]._id };
      record._id = patients[idx]._id;
    } else {
      patients.push(record);
    }
    savePatients(patients);
    window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count: patients.length } }));
    handleLoadSession(record);
    syncPatientsWithServer({ silent: true });
    setImportPreview(null);
  };

  const cancelImportPreview = () => {
    setImportPreview(null);
  };

  const closeMobileTopMenu = () => setMobileTopMenuOpen(false);

  function TopBarActions({ inMenu }) {
    const btnBase = inMenu
      ? "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors duration-200 relative group hover:bg-white/[0.04]"
      : "w-9 h-9 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center text-white/50 transition-all flex-shrink-0";

    const menuItems = [
      { onClick: newSession, icon: <PlusCircle />, label: "New session", colorClass: "hover:text-teal-300" },
      { onClick: saveSession, icon: <Save />, label: sessionDirty ? "Save session (unsaved)" : "Save session", colorClass: "hover:text-sky-300" },
      { onClick: () => { goToSection("analysis"); if (!isDesktop) setSidebar(false); }, icon: <BarChart3 />, label: "Analysis Dashboard", colorClass: "hover:text-amber-300" },
      { onClick: () => revealSessionStatusBar(), icon: <Video />, label: "Sessions from Drive", colorClass: "hover:text-sky-300" },
      { onClick: () => importRef.current?.click(), icon: <FileUp />, label: "Import patient", colorClass: "hover:text-emerald-300" },
      { onClick: () => bgRef.current?.click(), icon: <ImageIcon />, label: "Background" },
      { onClick: () => { goToSection("database"); if (!isDesktop) setSidebar(false); }, icon: <Database />, label: "Database" },
      { onClick: () => { openConnectDrive(); }, icon: <HardDrive />, label: "Connect Drive", colorClass: "hover:text-sky-300" },
      ...(user?.is_admin ? [{ onClick: () => { goToSection("users"); if (!isDesktop) setSidebar(false); }, icon: <Users />, label: "Users", colorClass: "hover:text-violet-300" }] : []),
      { onClick: logout, icon: <LogOut />, label: "Sign out", colorClass: "hover:text-rose-300" },
    ];

    const Action = ({ onClick, icon, label, colorClass = "hover:text-white" }) => (
      <motion.button
        whileTap={nlMotionTap(0.97)}
        onClick={() => { onClick(); if (inMenu) closeMobileTopMenu(); }}
        className={`${btnBase} ${inMenu ? "" : colorClass}`}
        style={inMenu ? { border: "1px solid transparent" } : GLASS_FIELD}
        title={label}
        aria-label={label}
      >
        {inMenu ? (
          <>
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 relative z-10 bg-white/[0.04] group-hover:bg-white/[0.07] transition-all"
              style={GLASS_FIELD}
            >
              {React.cloneElement(icon, { className: "w-4 h-4 text-white/45 group-hover:text-white/70" })}
            </div>
            <span className="text-sm font-extrabold leading-snug text-white/60 group-hover:text-white/85 relative z-10">{label}</span>
          </>
        ) : (
          React.cloneElement(icon, { className: "w-4 h-4 flex-shrink-0" })
        )}
      </motion.button>
    );

    if (!inMenu) return null;

    return (
      <>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={NL_TWEEN_MENU}
          className={`rounded-2xl sidebar-shell ${SIDEBAR_CLS}`}
          style={{ boxShadow: FLOAT_M }}
        >
          <nav className="py-3 px-1 flex flex-col">
            {menuItems.map((item) => (
              <Action key={item.label} onClick={item.onClick} icon={item.icon} label={item.label} colorClass={item.colorClass} />
            ))}
          </nav>
        </motion.div>
      </>
    );
  }

  const nav = NAV_ITEMS.find((n) => n.id === sidebarActiveId);

  const topBarHiddenInputs = (
    <>
      <input
        ref={importRef}
        type="file"
        accept=".json,.pdf,application/json,application/pdf"
        className="hidden"
        onChange={handleImportFile}
      />
      <input
        ref={bgRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) setBgUrl(URL.createObjectURL(f));
        }}
      />
    </>
  );

  const topBarNav = (!sidebar || isDesktop) && nav && (() => {
    const Icon = nav.icon;
    return (
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <Icon className="w-4 h-4 text-white/60 flex-shrink-0" />
        <span className="text-sm font-extrabold text-white truncate">{nav.en}</span>
        <span className="hidden lg:inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-light text-white/40 bg-white/[0.04] border border-white/[0.04]">
          {new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "long", year: "numeric" })}
        </span>
        {readNlVersion() && (
          <span
            className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold tracking-wide text-sky-200/80 bg-sky-400/10 border border-sky-400/20 flex-shrink-0"
            title="App build version — confirm this on iPad after update"
            data-nl-version={readNlVersion()}
          >
            v{readNlVersion()}
          </span>
        )}
      </div>
    );
  })();

  const topBarMenuBtn = (
    <motion.button
      whileTap={nlMotionTap(0.9)}
      onClick={() => setSidebar((p) => !p)}
      className="w-9 h-9 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center text-white/60 hover:text-white transition-all flex-shrink-0"
      style={GLASS_FIELD}
      aria-label={sidebar ? "Close menu" : "Open menu"}
    >
      {sidebar ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
    </motion.button>
  );

  function DesktopUnifiedTopBar() {
    const shellRef = useRef(null);
    const rowRef = useRef(null);
    const rightColRef = useRef(null);
    const shellWidthMv = useMotionValue(0);
    const rowHeightMv = useMotionValue(TOPBAR_ROW_H);

    const applyShellClip = useCallback(() => {
      const shell = shellRef.current;
      if (!shell) return;
      const w = Math.round(
        shell.offsetWidth
        || shellWidthMv.get()
        || topBarWrapperRef.current?.clientWidth
        || 0
      );
      const css = buildTopBarClipPath(
        w,
        Math.round(rowHeightMv.get()),
        w,
        0,
        TOPBAR_FILLET_R,
        false
      );
      shell.style.clipPath = css;
      shell.style.webkitClipPath = css;
    }, [shellWidthMv, rowHeightMv]);

    const measureLayout = useCallback(() => {
      const shell = shellRef.current;
      const row = rowRef.current;
      const right = rightColRef.current;
      if (!shell) return;
      shellWidthMv.set(shell.offsetWidth || topBarWrapperRef.current?.clientWidth || 0);
      const leftH = row?.getBoundingClientRect().height ?? 0;
      const btnRow = right?.firstElementChild;
      const rightH = btnRow?.getBoundingClientRect().height ?? 0;
      rowHeightMv.set(Math.max(leftH, rightH, TOPBAR_ROW_H));
      applyShellClip();
    }, [shellWidthMv, rowHeightMv, applyShellClip]);

    useLayoutEffect(() => {
      measureLayout();
      const shell = shellRef.current;
      const row = rowRef.current;
      const right = rightColRef.current;
      if (!shell) return undefined;

      const ro = new ResizeObserver(measureLayout);
      ro.observe(shell);
      if (row) ro.observe(row);
      if (right) ro.observe(right);
      window.addEventListener("resize", measureLayout);
      return () => {
        ro.disconnect();
        window.removeEventListener("resize", measureLayout);
      };
    }, [measureLayout, user?.is_admin, sidebar, sidebarPush, isDesktop]);

    useLayoutEffect(() => {
      const t = requestAnimationFrame(() => measureLayout());
      return () => cancelAnimationFrame(t);
    }, [sidebar, sidebarPush, isDesktop, measureLayout]);

    return (
      <div
        ref={shellRef}
        className={`relative w-full overflow-hidden app-topbar-glass glass-float ${GLASS_CLS}`}
        style={{ boxShadow: FLOAT_M }}
      >
        <div className="relative z-[1] flex items-start w-full min-w-0 flex-nowrap">
          {topBarHiddenInputs}

          <div
            ref={rowRef}
            className="flex-1 flex items-center gap-3 px-3 sm:px-4 py-2.5 sm:py-3 min-w-0 self-start"
          >
            {topBarMenuBtn}
            {topBarNav}
          </div>

          <div ref={rightColRef} className="flex flex-col flex-shrink-0 self-start">
            <div className="flex items-center gap-2 px-2 sm:px-3 py-2.5 sm:py-3 flex-shrink-0">
              <TopBarSessionCapsule
                onNew={newSession}
                onSave={saveSession}
                dirty={sessionDirty}
              />
              <SessionStatusBar
                getPatients={loadPatients}
                restoreBusy={Boolean(originRestoreBanner)}
                onOpenSession={(record) => handleLoadSession(record, { section: "kinematics" })}
              />

              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={nlMotionTap(0.95)}
                onClick={() => setMobileTopMenuOpen((p) => !p)}
                className={`w-9 h-9 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center text-white/50 hover:text-white transition-colors flex-shrink-0 ${mobileTopMenuOpen ? "text-white bg-white/[0.10]" : ""}`}
                style={GLASS_FIELD}
                title="More actions"
                aria-label="More actions"
                aria-expanded={mobileTopMenuOpen}
                aria-haspopup="dialog"
                animate={{ rotate: mobileTopMenuOpen ? 90 : 0 }}
                transition={NL_TWEEN_MENU}
              >
                <MoreHorizontal className="w-4 h-4" />
              </motion.button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const topBar = useDesktopTopBar ? (
    <DesktopUnifiedTopBar />
  ) : (
    <div
      className={`app-topbar-glass glass-float relative flex items-center gap-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-xl overflow-visible ${sidebar && !isDesktop ? "" : "pr-[7.5rem]"} ${GLASS_CLS}`}
      style={{ boxShadow: FLOAT_M }}
    >
      {topBarMenuBtn}

      {topBarNav}

      {sidebar && !isDesktop && (
        <span className="flex-1 text-sm font-extrabold text-white/70 truncate">Navigation</span>
      )}

      <div className={`absolute right-3 sm:right-4 top-2.5 sm:top-3 z-[70] ${sidebar && !isDesktop ? "hidden" : ""}`}>
        {topBarHiddenInputs}

        <div className="flex items-start gap-2">
          <SessionStatusBar
            getPatients={loadPatients}
            restoreBusy={Boolean(originRestoreBanner)}
            onOpenSession={(record) => handleLoadSession(record, { section: "kinematics" })}
          />
          <motion.button
            whileHover={{ scale: 1.08 }}
            whileTap={nlMotionTap(0.92)}
            onClick={() => setMobileTopMenuOpen((p) => !p)}
            className="w-9 h-9 rounded-lg flex items-center justify-center text-white/50 hover:text-white transition-all flex-shrink-0"
            style={GLASS_FIELD}
            title="Menu"
            aria-label="Menu"
          >
            <MoreHorizontal className="w-4 h-4" />
          </motion.button>
        </div>
      </div>
    </div>
  );

  function UsersSection() {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [usersError, setUsersError] = useState("");
    const [actionLoading, setActionLoading] = useState(null);
    const [mfaStatus, setMfaStatus] = useState(null);
    const [mfaSetup, setMfaSetup] = useState(null);
    const [mfaCode, setMfaCode] = useState("");
    const [mfaError, setMfaError] = useState("");
    const [mfaLoading, setMfaLoading] = useState(false);
    const MFA_INPUT = "w-full bg-[rgba(220,235,255,0.04)] border border-white/[0.03] rounded-lg px-3 py-2.5 text-sm text-white placeholder-white/40 focus:outline-none focus:border-white/50 focus:ring-1 focus:ring-white/30";

    const loadUsers = async () => {
      setLoading(true);
      setUsersError("");
      try {
        const r = await fetch("/auth/users", { credentials: "same-origin", headers: authHeaders() });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
          setUsersError(data.detail || "Failed to load users");
          setUsers([]);
        } else {
          setUsers(data.users || []);
        }
      } catch (e) {
        setUsersError(e?.message || "Network error");
      } finally {
        setLoading(false);
      }
    };

    useEffect(() => { loadUsers(); }, []);

    const approveUser = async (id) => {
      setActionLoading(id);
      try {
        const r = await fetch(`/auth/approve/${id}`, { method: "POST", credentials: "same-origin", headers: authHeaders() });
        if (r.ok) loadUsers();
      } catch (e) {
        console.error(e);
      } finally {
        setActionLoading(null);
      }
    };

    const deleteUser = async (id) => {
      if (!window.confirm("Delete this user?")) return;
      setActionLoading(id);
      try {
        const r = await fetch(`/auth/delete/${id}`, { method: "POST", credentials: "same-origin", headers: authHeaders() });
        if (r.ok) loadUsers();
      } catch (e) {
        console.error(e);
      } finally {
        setActionLoading(null);
      }
    };

    const loadMfaStatus = async () => {
      try {
        const r = await fetch("/auth/mfa/status", { credentials: "same-origin", headers: authHeaders() });
        const data = await r.json().catch(() => ({}));
        setMfaStatus(r.ok ? data.mfa_enabled : false);
      } catch (e) {
        setMfaStatus(false);
      }
    };
    useEffect(() => { loadMfaStatus(); }, []);

    const setupMfa = async () => {
      setMfaLoading(true);
      setMfaError("");
      try {
        const r = await fetch("/auth/mfa/setup", { method: "POST", credentials: "same-origin", headers: authHeaders() });
        const data = await r.json().catch(() => ({}));
        if (r.ok) {
          setMfaSetup(data);
        } else {
          setMfaError(data.detail || "Setup failed");
        }
      } catch (e) {
        setMfaError(e?.message || "Network error");
      } finally {
        setMfaLoading(false);
      }
    };

    const verifyMfa = async () => {
      setMfaLoading(true);
      setMfaError("");
      try {
        const r = await fetch("/auth/mfa/verify", {
          method: "POST",
          credentials: "same-origin",
          headers: authHeaders(),
          body: JSON.stringify({ code: mfaCode }),
        });
        const data = await r.json().catch(() => ({}));
        if (r.ok) {
          setMfaStatus(true);
          setMfaSetup(null);
          setMfaCode("");
        } else {
          setMfaError(data.detail || "Invalid code");
        }
      } catch (e) {
        setMfaError(e?.message || "Network error");
      } finally {
        setMfaLoading(false);
      }
    };

    const disableMfa = async () => {
      if (!window.confirm("Disable MFA? This reduces account security.")) return;
      setMfaLoading(true);
      setMfaError("");
      try {
        const r = await fetch("/auth/mfa/disable", { method: "POST", credentials: "same-origin", headers: authHeaders() });
        const data = await r.json().catch(() => ({}));
        if (r.ok) {
          setMfaStatus(false);
          setMfaSetup(null);
          setMfaCode("");
        } else {
          setMfaError(data.detail || "Disable failed");
        }
      } catch (e) {
        setMfaError(e?.message || "Network error");
      } finally {
        setMfaLoading(false);
      }
    };

    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Users</h2>
          <button onClick={loadUsers} className="text-xs text-white/60 hover:text-white">Refresh</button>
        </div>
        <div className="p-4 rounded-xl bg-white/[0.05] border border-white/10">
          <h3 className="text-sm font-medium text-white">Two-factor authentication (Admin)</h3>
          <p className="text-xs text-white/50 mt-1">
            Status: {mfaStatus === null ? "Loading..." : mfaStatus ? "Enabled" : "Not enabled"}
          </p>
          {mfaStatus === false && (
            <button
              onClick={setupMfa}
              disabled={mfaLoading}
              className="mt-3 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/20 text-emerald-200 hover:bg-emerald-500/30 disabled:opacity-50"
            >
              Enable MFA
            </button>
          )}
          {mfaStatus === true && (
            <button
              onClick={disableMfa}
              disabled={mfaLoading}
              className="mt-3 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/20 text-red-200 hover:bg-red-500/30 disabled:opacity-50"
            >
              Disable MFA
            </button>
          )}
          {mfaError && <p className="text-red-300 text-xs mt-2">{mfaError}</p>}
          {mfaSetup && (
            <div className="mt-4 space-y-3">
              <p className="text-xs text-white/70">
                Scan the QR code with your authenticator app, then enter the 6-digit code.
              </p>
              <img
                src={mfaSetup.qr_data_url}
                alt="MFA QR code"
                className="bg-white p-2 rounded-lg w-44 h-44 object-contain"
              />
              <p className="text-xs text-white/40 break-all">Secret: {mfaSetup.secret}</p>
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                className={MFA_INPUT}
                placeholder="6-digit code"
                maxLength={6}
              />
              <button
                onClick={verifyMfa}
                disabled={mfaLoading || mfaCode.length !== 6}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/20 text-emerald-200 hover:bg-emerald-500/30 disabled:opacity-50"
              >
                Verify & Enable
              </button>
            </div>
          )}
        </div>
        {usersError && <p className="text-red-300 text-sm">{usersError}</p>}
        {loading ? (
          <p className="text-white/50 text-sm">Loading...</p>
        ) : (
          <div className="space-y-2">
            {users.length === 0 && <p className="text-white/50 text-sm">No users found.</p>}
            {users.map((u) => (
              <div key={u.id} className="flex items-center justify-between p-3 rounded-xl bg-white/[0.05] border border-white/10">
                <div>
                  <p className="text-sm font-medium text-white">{u.name || u.email}</p>
                  <p className="text-xs text-white/50">{u.email}</p>
                  <p className="text-xs text-white/40">{u.is_approved ? "Approved" : "Pending approval"} {u.is_admin ? " · Admin" : ""}</p>
                </div>
                <div className="flex items-center gap-2">
                  {!u.is_approved && (
                    <button
                      onClick={() => approveUser(u.id)}
                      disabled={actionLoading === u.id}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/20 text-emerald-200 hover:bg-emerald-500/30 disabled:opacity-50"
                    >
                      Approve
                    </button>
                  )}
                  {!u.is_admin && (
                    <button
                      onClick={() => deleteUser(u.id)}
                      disabled={actionLoading === u.id}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/20 text-red-200 hover:bg-red-500/30 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  const renderSection = useCallback(
    (sectionId) => {
      switch (sectionId) {
        case "demographics":
          return (
            <DemoSection
              data={fd.demographics}
              onChange={(d) => upd("demographics", d)}
              onBulkUpdate={(sec, d) => upd(sec, d)}
            />
          );
        case "ipaq":
          return <IPAQSection data={fd.ipaq} onChange={(d) => upd("ipaq", d)} />;
        case "vas":
          return <VASSection data={fd.vas} onChange={(d) => upd("vas", d)} />;
        case "vams":
          return <VAMSSection data={fd.vams} onChange={(d) => upd("vams", d)} />;
        case "motorchange":
          return <MotorSection data={fd.motorchange} onChange={(d) => upd("motorchange", d)} />;
        case "kgia":
          return <KGIASection data={fd.kgia} onChange={(d) => upd("kgia", d)} />;
        case "wmft":
          return (
            <WMFTSection
              data={fd.wmft}
              kinematics={fd.kinematics}
              showToast={showToast}
              onChange={(d) => upd("wmft", d)}
            />
          );
        case "kinematics":
          return (
            <KinSection
              data={fd.kinematics}
              sessionKey={fd._loadedId || fd.demographics?.participantId}
              demographics={fd.demographics}
              onChange={(d) => upd("kinematics", d)}
              showToast={showToast}
            />
          );
        case "database":
          return (
            <DatabaseSection
              fd={fd}
              setFd={setFd}
              onLoadSession={handleLoadSession}
              showToast={showToast}
              isActive={active === "database"}
            />
          );
        case "report":
          return <ReportSection fd={fd} onChange={(d) => upd("demographics", d)} showToast={showToast} />;
        case "analysis":
          return <AnalysisDashboard />;
        case "users":
          return <UsersSection />;
        default:
          return null;
      }
    },
    [fd, setFd, showToast, handleLoadSession, active, upd]
  );

  const sidebarOpenDesktop = isDesktop && sidebar;
  const mainColumnWidth = sidebarOpenDesktop ? `calc(100% - ${sidebarPush}px)` : "100%";
  const topBarShellStyle = {
    left: sidebarOpenDesktop ? sidebarPush : 0,
    width: mainColumnWidth,
    paddingTop: SAFE_TOP,
    transition: SIDEBAR_LAYOUT_TRANSITION,
  };

  const topBarChrome = (
    <div
      ref={topBarWrapperRef}
      className={`${iosPullScroll ? "sticky" : "fixed"} top-0 z-[60] px-3 sm:px-4 pb-0 ${!isDesktop && sidebar ? "hidden" : ""}`}
      style={topBarShellStyle}
    >
      {topBar}
    </div>
  );

  const mainChrome = (
    <main
      className="flex-none relative z-30"
      style={{
        width: mainColumnWidth,
        marginLeft: sidebarOpenDesktop ? sidebarPush : 0,
        minWidth: 0,
        transition: SIDEBAR_LAYOUT_TRANSITION,
      }}
    >
      {!iosPullScroll && <div ref={topBarSpacerRef} aria-hidden="true" style={{ height: 96 }} />}
      <div
        className={`app-main-inner px-3 sm:px-4 pb-4 sm:pb-6 max-w-5xl w-full mx-auto ${
          iosPullScroll ? "pt-3 sm:pt-4" : "pt-16 sm:pt-6"
        }`}
      >
        <div className={`content-shell rounded-2xl w-full min-w-0${sectionNavLocked && isDesktop ? " content-shell-nav-motion" : ""}`}>
          <div className="content-shell-inner p-4 sm:p-6 w-full min-w-0">
            <SectionTransition
              sectionId={active}
              renderSection={renderSection}
              navPhase={navPhase}
              contentRef={sectionContentRef}
              mobileNav={!isDesktop || isTouchUi()}
              onExitComplete={completeExitPhase}
              onBeginEnter={beginEnterPhase}
              onEnterComplete={handleIncomingComplete}
            />
          </div>
        </div>
      </div>
    </main>
  );

  return (
    <AuthGate>
    <div className="min-h-screen w-full min-w-0 max-w-full flex relative overflow-x-hidden" style={{ fontFamily: "'Inter',system-ui,sans-serif" }}>
      <div className="fixed inset-0 z-0 pointer-events-none" aria-hidden="true">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: `url('${bgUrl}')`,
            backgroundSize: "cover",
            backgroundPosition: "center center",
            backgroundRepeat: "no-repeat",
            filter: BG_FILTER,
            transform: BG_SCALE,
          }}
        />
        <div className="absolute inset-0" style={{ background: BG_OVERLAY }} />
      </div>

      {!isDesktop && sidebar && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setSidebar(false)}
          aria-hidden="true"
          style={{ background: "transparent" }}
        />
      )}

      <aside
        className={`fixed left-0 top-0 h-full ${isDesktop ? "z-50" : "z-[100]"} flex flex-col px-3 pb-3`}
        style={{
          width: isDesktop ? sidebarPush : MOBILE_SIDEBAR_W,
          paddingTop: SAFE_TOP,
          transform: sidebar ? "translate3d(0,0,0)" : (isDesktop ? `translate3d(-${sidebarPush}px,0,0)` : "translate3d(-100%,0,0)"),
          transition: SIDEBAR_SHELL_TRANSITION,
          backfaceVisibility: "hidden",
          WebkitBackfaceVisibility: "hidden",
          isolation: undefined,
        }}
      >
            <div className={`sidebar-shell flex-1 flex flex-col min-h-0 rounded-2xl overflow-hidden ${SIDEBAR_CLS}`} style={{ boxShadow: FLOAT_M }}>
              <div className="px-5 pt-7 pb-5 flex-shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                  <div className="relative flex flex-col items-center text-center gap-2 mb-4">
                    {!isDesktop && (
                      <button
                        type="button"
                        onClick={() => setSidebar(false)}
                        className="absolute top-0 right-0 p-1 rounded-lg text-white/50 hover:text-white hover:bg-white/10 transition"
                        aria-label="Close menu"
                      >
                        <X className="w-5 h-5" />
                      </button>
                    )}
                    <img
                      src={`${process.env.PUBLIC_URL || ""}/raed-logo.png?v=32.88`}
                      alt="RA.ED AI"
                      className="w-[8.75rem] h-auto object-contain"
                      style={{ background: "transparent" }}
                    />
                    <p className="text-base font-extrabold text-white leading-tight tracking-wide">RA.ED AI</p>
                  </div>
                <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl" style={GLASS_FIELD}>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
                  <span className="text-xs font-light text-white/50 truncate">Pre / Post Longitudinal</span>
              </div>
            </div>

              <nav className="flex-1 min-h-0 p-3 space-y-0.5 overflow-y-auto">
                {NAV_ITEMS.filter((item) => !item.topBarOnly && (!item.adminOnly || user?.is_admin)).map((item) => {
                  const on = sidebarActiveId === item.id;
                  const Icon = item.icon;

                  return (
                    <motion.button
                      key={item.id}
                      whileTap={sectionNavLocked ? undefined : nlMotionTap(0.97)}
                      onClick={() => { goToSection(item.id); if (!isDesktop) setSidebar(false); }}
                      disabled={sectionNavLocked}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors duration-200 relative group ${
                        on ? "bg-white/[0.07]" : "hover:bg-white/[0.04]"
                      }${sectionNavLocked ? " pointer-events-none" : ""}`}
                      style={on ? { backgroundColor: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.06)", boxShadow: "none" } : { border: "1px solid transparent" }}
                    >
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 relative z-10 transition-all ${
                        on ? "bg-white/10" : "bg-white/[0.04] group-hover:bg-white/[0.07]"
                      }`} style={GLASS_FIELD}>
                        <Icon className={`w-4 h-4 ${on ? "text-white" : "text-white/45 group-hover:text-white/70"}`} />
                      </div>

                      <div className="flex-1 min-w-0 relative z-10">
                        <p className={`text-sm font-extrabold leading-snug sm:truncate ${on ? "text-white" : "text-white/60 group-hover:text-white/85"}`}>
                          {item.en}
                        </p>
                      </div>

                      {on ? (
                        <ChevronRight className="w-3.5 h-3.5 text-white/40 relative z-10 flex-shrink-0" />
                      ) : (
                        <span className="w-3.5 h-3.5 flex-shrink-0" aria-hidden />
                      )}
                    </motion.button>
                  );
                })}
              </nav>
            </div>
          </aside>

      {iosPullScroll ? (
        <>
          <div
            ref={ptrSpinnerAnchorRef}
            className="ptr-spinner-anchor fixed left-0 right-0 z-[85] flex justify-center pointer-events-none"
            style={{
              opacity: 0,
              top: "max(10px, env(safe-area-inset-top, 0px))",
            }}
            aria-hidden="true"
          >
            <PtrIosSpinner spinning={false} size={20} />
          </div>
          <div
            ref={appScrollRef}
            data-nl-app-scroll="1"
            className="fixed inset-0 z-20 overflow-y-auto overscroll-y-auto"
            style={{ WebkitOverflowScrolling: "touch" }}
          >
            <div className="ptr-inner min-h-full relative">
              <div className="ptr-pull-content">
                {topBarChrome}
                {mainChrome}
              </div>
            </div>
          </div>
          <PullToRefresh
            scrollRef={appScrollRef}
            spinnerAnchorRef={ptrSpinnerAnchorRef}
            onRefresh={performSoftRefresh}
            disabled={sectionNavLocked}
          />
        </>
      ) : (
        <>
          {topBarChrome}
          {mainChrome}
        </>
      )}

      {/* Global Styles */}
      <style>{`
        * { box-sizing: border-box; }
        h1, h2, h3, p, span, label, button {
          text-shadow: 0 1px 2px rgba(0,0,0,0.12);
        }

        /* Design tokens ? very muted liquid glass: minimal light/shine */
        [class*="border-white"] {
          border-color: rgba(255,255,255,0.03) !important;
        }
        .border-b[class*="border-white"],
        .border-t[class*="border-white"] {
          border-color: rgba(255,255,255,0.02) !important;
          box-shadow: none !important;
        }

        .sidebar-shell,
        .glass-float,
        .content-shell {
          position: relative;
          border-color: rgba(255,255,255,0.03) !important;
          backdrop-filter: blur(12px) saturate(2.25) !important;
          -webkit-backdrop-filter: blur(12px) saturate(2.25) !important;
          background-color: rgba(255,255,255,0.008) !important;
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.02), inset 0 -1px 0 rgba(255,255,255,0.01), 0 20px 50px -24px rgba(0,0,0,0.10) !important;
          background-image:
            radial-gradient(ellipse 150% 60% at 50% 0%, rgba(255,255,255,0.015) 0%, transparent 65%),
            radial-gradient(ellipse 150% 70% at 50% 100%, rgba(200,230,255,0.015) 0%, transparent 60%),
            radial-gradient(circle at 0% 25%, rgba(255,255,255,0.008) 0%, transparent 40%),
            radial-gradient(circle at 100% 75%, rgba(255,255,255,0.008) 0%, transparent 40%),
            linear-gradient(175deg, rgba(255,255,255,0.005) 0%, rgba(255,255,255,0.00) 45%, rgba(255,255,255,0.00) 65%, rgba(255,255,255,0.004) 100%) !important;
          background-blend-mode: overlay, overlay, overlay, overlay, normal;
        }

        .sidebar-shell::before,
        .glass-float::before,
        .gselect-menu-portal::before,
        .content-shell::before {
          content: "";
          position: absolute;
          inset: 0;
          border-radius: inherit;
          padding: 2px;
          background: conic-gradient(
            from 180deg at 50% 50%,
            rgba(255,255,255,0.25) 0deg,
            rgba(160,225,255,0.12) 45deg,
            rgba(210,190,255,0.08) 90deg,
            rgba(255,255,255,0.03) 135deg,
            rgba(160,225,255,0.12) 180deg,
            rgba(255,255,255,0.03) 225deg,
            rgba(210,190,255,0.08) 270deg,
            rgba(160,225,255,0.12) 315deg,
            rgba(255,255,255,0.25) 360deg
          );
          -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
          -webkit-mask-composite: xor;
          mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
          mask-composite: exclude;
          pointer-events: none;
          z-index: 0;
          opacity: 0.05;
        }

        .sidebar-shell::after,
        .glass-float::after,
        .gselect-menu-portal::after,
        .content-shell::after {
          content: "";
          position: absolute;
          inset: 0;
          border-radius: inherit;
          pointer-events: none;
          z-index: 0;
          background:
            linear-gradient(180deg, rgba(255,255,255,0.008) 0%, rgba(255,255,255,0.00) 40%, rgba(255,255,255,0.00) 70%, rgba(255,255,255,0.005) 100%);
          mix-blend-mode: overlay;
        }

        .content-shell {
          background: transparent;
        }

        /* Inner section panels ? frosted cards (same on iPad and desktop) */
        .content-shell .content-panel-glass,
        .content-shell .glass-float:not(.section-header):not(.app-topbar-glass) {
          backdrop-filter: blur(16px) saturate(1.85) !important;
          -webkit-backdrop-filter: blur(16px) saturate(1.85) !important;
          background-color: rgba(255,255,255,0.028) !important;
          border-color: rgba(255,255,255,0.05) !important;
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.018), 0 10px 28px -6px rgba(0,0,0,0.12), 0 22px 52px -14px rgba(0,0,0,0.10), 0 36px 72px -24px rgba(0,0,0,0.07) !important;
        }

        .content-shell .content-panel-glass::before,
        .content-shell .glass-float:not(.section-header)::before {
          opacity: 0.025;
        }

        .content-shell .content-panel-glass::after,
        .content-shell .glass-float:not(.section-header)::after {
          opacity: 0.35;
          background:
            linear-gradient(180deg, rgba(255,255,255,0.006) 0%, rgba(255,255,255,0.00) 45%, rgba(255,255,255,0.00) 100%);
        }

        .app-main-inner {
          background: transparent;
        }

        .glass-float .glass-float {
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.02), inset 0 -1px 0 rgba(255,255,255,0.01), 0 20px 50px -24px rgba(0,0,0,0.10) !important;
        }

        /* Section headers ? stronger frosted glass */
        .section-header {
          backdrop-filter: blur(24px) saturate(2.25) !important;
          -webkit-backdrop-filter: blur(24px) saturate(2.25) !important;
        }

        /* Inputs ? neutral dark glass, less blue */
        .glass-field,
        input, select, textarea {
          background-color: rgba(255,255,255,0.06) !important;
          border-color: rgba(255,255,255,0.04) !important;
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.02) !important;
        }
        .glass-float input,
        .glass-float select,
        .glass-float textarea,
        .glass-float .glass-field {
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.03) !important;
        }

        .shadow-lg, .shadow-xl, .shadow-2xl {
          box-shadow: 0 16px 40px -22px rgba(0,0,0,0.05) !important;
        }

        ::-webkit-scrollbar { width: 3px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.10); border-radius: 99px; }
        input[type=number]::-webkit-inner-spin-button { opacity: 0; }
        select option {
          background-color: rgba(255, 255, 255, 0.08);
          color: rgba(255, 255, 255, 0.92);
        }
        input, select, textarea, button { -webkit-tap-highlight-color: transparent; }
        input[type=date] {
          -webkit-appearance: none;
          appearance: none;
          color-scheme: dark;
          min-height: 44px;
        }
        input[type=date]::-webkit-calendar-picker-indicator {
          filter: invert(0.7);
          cursor: pointer;
          opacity: 0.6;
        }
        input[type=date]::-webkit-date-and-time-value { text-align: left; }
        .app-topbar-glass button[aria-label="Refresh"],
        .app-topbar-glass a[aria-label="Refresh"] {
          display: none !important;
          pointer-events: none !important;
        }

        .ptr-inner { position: relative; }
        .ptr-pull-content {
          transform: translate3d(0, 0, 0);
          backface-visibility: hidden;
          -webkit-backface-visibility: hidden;
          touch-action: pan-y;
        }
        .ptr-spinner-anchor {
          overflow: visible;
          will-change: transform, opacity;
        }
        .ptr-ios-spinner {
          position: relative;
          display: inline-block;
          width: 20px;
          height: 20px;
          transform: scale(var(--ptr-scale, 1));
          transform-origin: 50% 50%;
        }
        video { outline: none; background: #000; }
        .grid { min-width: 0; }
        .grid > * { min-width: 0; overflow-wrap: break-word; word-break: break-word; }
        input, select { min-height: 44px !important; }
        button { min-height: 44px !important; }

        .gselect-chevron {
          transition: transform 0.24s cubic-bezier(0.33, 1, 0.68, 1);
          transform: translateZ(0);
        }
        .gselect-chevron-open {
          transform: rotate(180deg) translateZ(0);
        }

        @keyframes gselect-body-in {
          from {
            opacity: 0;
            transform: translate3d(0, -8px, 0);
          }
          to {
            opacity: 1;
            transform: translate3d(0, 0, 0);
          }
        }
        .gselect-menu-body--animate {
          animation: gselect-body-in 0.24s cubic-bezier(0.33, 1, 0.68, 1) both;
          transform: translateZ(0);
          backface-visibility: hidden;
          -webkit-backface-visibility: hidden;
        }

        .gselect-menu-portal {
          contain: layout style;
        }

        .gselect-trigger-shell.glass-float {
          transition: border-color 0.28s cubic-bezier(0.33, 1, 0.68, 1), box-shadow 0.28s cubic-bezier(0.33, 1, 0.68, 1);
        }
        .gselect-trigger-shell.glass-float[aria-expanded="true"] {
          border-color: rgba(255,255,255,0.05) !important;
        }

        .gselect-menu-portal.glass-float {
          border-color: rgba(255,255,255,0.03) !important;
          backdrop-filter: blur(12px) saturate(2.25) !important;
          -webkit-backdrop-filter: blur(12px) saturate(2.25) !important;
          background-color: rgba(255,255,255,0.008) !important;
          background-image:
            radial-gradient(ellipse 150% 60% at 50% 0%, rgba(255,255,255,0.015) 0%, transparent 65%),
            radial-gradient(ellipse 150% 70% at 50% 100%, rgba(200,230,255,0.015) 0%, transparent 60%),
            radial-gradient(circle at 0% 25%, rgba(255,255,255,0.008) 0%, transparent 40%),
            radial-gradient(circle at 100% 75%, rgba(255,255,255,0.008) 0%, transparent 40%),
            linear-gradient(175deg, rgba(255,255,255,0.005) 0%, rgba(255,255,255,0.00) 45%, rgba(255,255,255,0.00) 65%, rgba(255,255,255,0.004) 100%) !important;
          background-blend-mode: overlay, overlay, overlay, overlay, normal;
        }

        .gselect-menu-portal .gselect-option {
          transition: background-color 0.12s, color 0.12s;
          background-color: transparent !important;
          box-shadow: none !important;
          border: none !important;
          backdrop-filter: none !important;
          -webkit-backdrop-filter: none !important;
        }
        .gselect-menu-portal .gselect-option:hover {
          background-color: rgba(255,255,255,0.06) !important;
        }

        /* GSelect portal ? identical liquid glass tokens as .app-topbar-glass (transform anim on inner body only ? keeps backdrop-filter) */
        @media (prefers-reduced-motion: reduce) {
          .gselect-menu-body--animate,
          .gselect-chevron {
            animation: none !important;
            transition: none !important;
          }
        }

        html.nl-touch .sidebar-shell,
        html.nl-touch .glass-float,
        html.nl-touch .content-shell {
          backdrop-filter: blur(8px) saturate(1.45) !important;
          -webkit-backdrop-filter: blur(8px) saturate(1.45) !important;
        }
        html.nl-touch .content-shell .glass-float:not(.section-header):not(.app-topbar-glass),
        html.nl-touch .content-shell .content-panel-glass {
          backdrop-filter: blur(6px) saturate(1.25) !important;
          -webkit-backdrop-filter: blur(6px) saturate(1.25) !important;
        }
        html.nl-touch .sidebar-shell::before,
        html.nl-touch .sidebar-shell::after,
        html.nl-touch .content-shell::before,
        html.nl-touch .content-shell::after,
        html.nl-touch .content-shell .glass-float::before,
        html.nl-touch .content-shell .glass-float::after,
        html.nl-touch .content-shell .content-panel-glass::before,
        html.nl-touch .content-shell .content-panel-glass::after {
          display: none !important;
        }
        html.nl-touch h1,
        html.nl-touch h2,
        html.nl-touch h3,
        html.nl-touch p,
        html.nl-touch span,
        html.nl-touch label,
        html.nl-touch button {
          text-shadow: none !important;
        }

        @media (max-width: 768px) {
          input, select, textarea { font-size: 16px !important; }
          .app-main-inner { padding-left: 12px !important; padding-right: 12px !important; }
          .content-shell-inner { padding: 14px !important; }
          .px-4 { padding-left: 12px !important; padding-right: 12px !important; }
          .p-5 { padding: 14px !important; }
          table { font-size: 11px !important; }
          th, td { padding: 6px 8px !important; }
        }

      `}</style>

      {useMobileMenuPortal && typeof document !== "undefined" && ReactDOM.createPortal(
        <AnimatePresence>
          {mobileTopMenuOpen && (
            <div key="mobile-top-menu" className="fixed inset-0 z-[200]">
              <motion.button
                type="button"
                aria-label="Close menu"
                className="absolute inset-0 bg-black/50 backdrop-blur-[3px]"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                onClick={closeMobileTopMenu}
              />
              <motion.div
                ref={mobileMenuRef}
                role="dialog"
                aria-modal="true"
                aria-label="Actions menu"
                className="absolute left-0 right-0 bottom-0 px-3"
                initial={{ y: "50vh" }}
                animate={{ y: 0 }}
                exit={{ y: "50vh" }}
                transition={{ type: "tween", duration: 0.34, ease: [0.32, 0.72, 0, 1] }}
                style={{
                  maxHeight: "min(78vh, calc(100dvh - env(safe-area-inset-top, 0px) - 72px))",
                  paddingBottom: "max(12px, env(safe-area-inset-bottom, 0px))",
                  willChange: "transform",
                }}
              >
                <div
                  className={`sidebar-shell flex flex-col max-h-full rounded-2xl overflow-hidden ${SIDEBAR_CLS}`}
                  style={{ boxShadow: FLOAT_M }}
                >
                  <nav
                    className="flex-1 min-h-0 px-3 pt-3 pb-3 flex flex-col gap-3 overflow-y-auto overscroll-contain"
                    style={{
                      paddingBottom: "max(12px, calc(12px + env(safe-area-inset-bottom, 0px) * 0.35))",
                    }}
                  >
                    <TopBarActions inMenu={true} />
                  </nav>
                </div>
              </motion.div>
            </div>
          )}
        </AnimatePresence>,
        document.body
      )}

      {importPreview && (
        <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={cancelImportPreview}>
          <div
            className={`w-full max-w-2xl max-h-[85vh] flex flex-col rounded-2xl ${GLASS_CLS}`}
            style={{ boxShadow: FLOAT_M }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h3 className="text-sm font-extrabold text-white">Import Preview — No fields found</h3>
              <button onClick={cancelImportPreview} className="text-white/50 hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            <div className="flex-1 overflow-auto p-4 space-y-4">
              <p className="text-xs text-white/60">
                The parser could not find any recognizable fields. This usually means the PDF is scanned/image-only, or the text layout is not supported. Below is the raw text extracted from the file.
              </p>
              <div className="rounded-xl bg-black/40 border border-white/10 p-3">
                <p className="text-[10px] uppercase tracking-wider text-white/40 mb-1">Extracted text ({importPreview.extractedText.length} chars)</p>
                <pre className="text-xs text-white/70 whitespace-pre-wrap font-mono max-h-[40vh] overflow-auto">
                  {importPreview.extractedText || "(empty — PDF is likely an image)"}
                </pre>
              </div>
              <div className="rounded-xl bg-black/40 border border-white/10 p-3">
                <p className="text-[10px] uppercase tracking-wider text-white/40 mb-1">Parsed record</p>
                <pre className="text-xs text-white/70 whitespace-pre-wrap font-mono">{JSON.stringify(importPreview.record, null, 2)}</pre>
              </div>
            </div>
            <div className="p-4 border-t border-white/10 flex gap-3 justify-end">
              <button
                onClick={cancelImportPreview}
                className="px-4 py-2 rounded-xl text-sm font-semibold text-white/70 hover:bg-white/10 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmImportPreview}
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-violet-500/20 text-violet-200 border border-violet-500/30 hover:bg-violet-500/30 transition-colors"
              >
                Load anyway
              </button>
            </div>
          </div>
        </div>
      )}

      <Toast msg={toast.msg} visible={toast.visible} variant={toast.variant} />
      {originRestoreBanner ? (
        <div className="fixed top-3 left-1/2 -translate-x-1/2 z-[99998] max-w-[92vw] px-4 py-2.5 rounded-xl bg-sky-500/20 border border-sky-400/30 text-sky-100 text-sm font-medium shadow-xl backdrop-blur-xl text-center">
          {originRestoreBanner}
        </div>
      ) : null}
    </div>
    </AuthGate>
  );
}