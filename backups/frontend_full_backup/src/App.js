// ============================================================
// Stroke Rehabilitation Platform — Frontend v6.5
// ============================================================

import React, { useState, useRef, useCallback, useEffect } from "react";
import ReactDOM from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  User, Activity, Sliders, TrendingUp, Heart, Timer, Cpu, FileText,
  Menu, X, ChevronRight, Play, Square, RotateCcw, Copy, Check,
  Info, Save, BarChart3, Stethoscope, Brain, Image as ImageIcon,
  RefreshCw, FileSpreadsheet, Upload, FileUp,
  Database, Search, Edit3, Trash2, Plus, PlusCircle,
} from "lucide-react";
import * as XLSX from "xlsx";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import {
  STUDY_DESIGN, SPSS_WORKFLOW, KINEMATIC_VARS, orderedKinematicVars, CLINICAL_VARS,
  buildMasterDataset, buildMasterRow, generateStudySPSSSyntax, analyzeAllOutcomes,
  fmtP, sigStars,   getPatientKinPhase, pickKinField,
  calcImprovement, calcGap, formatKinPrePostPct, formatKinPostHealthyPct,
  RECOVERY_SUMMARY_KEYS, kinCrossPhaseComparable,
} from "./analysisPlan";
import {
  PROGRAM_GAPS, generateLiteratureReviewMarkdown, generateConsortSapMarkdown,
} from "./thesisDocs";
import { importPatientFile, buildImportRecord } from "./patientImport";

const APP_VERSION = "7.1.0-sparc-pwa";
const SAFE_TOP = "calc(env(safe-area-inset-top, 0px) + 8px)";

const BG = "/bg.jpg";

/* ── Glassmorphism (all Glass containers) ── */
const GLASS_CLS = "bg-white/[0.08] backdrop-blur-xl border border-white/12";
const SIDEBAR_CLS = "bg-white/[0.08] backdrop-blur-xl border border-white/12";
const INPUT_CLS = "bg-white/[0.09] border border-white/12";

const GSELECT_MENU_BOX = {
  backgroundColor: "#0e1120",
  border: "1px solid rgba(255, 255, 255, 0.25)",
  boxShadow: "0 10px 40px rgba(0, 0, 0, 0.7)",
  borderRadius: "12px",
};

const BG_FILTER = "blur(16px) brightness(0.48) saturate(0.70)";
const BG_SCALE = "scale(1.08)";
const BG_OVERLAY = "rgba(4, 6, 18, 0.32)";

function isIOSDevice() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function isStandalonePWA() {
  return window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true;
}

const SIDEBAR_W = 255;
const SIDEBAR_X_HIDDEN = -280;
const SIDEBAR_SPRING = { type: "spring", stiffness: 420, damping: 36, mass: 0.82 };

function sidebarPushWidth() {
  if (typeof window === "undefined") return SIDEBAR_W;
  if (window.matchMedia("(min-width: 768px)").matches) return SIDEBAR_W;
  return window.innerWidth;
}

const MOBILE_TOPBAR_PT = "4.75rem";
const PTR_THRESHOLD = 72;
const PTR_MAX_PULL = 118;

const FLOAT_L = "0 36px 80px -40px rgba(0,0,0,0.06)";
const FLOAT_M = "0 20px 48px -30px rgba(0,0,0,0.04)";

const GLASS_FIELD = {
  backgroundColor: "rgba(255,255,255,0.09)",
  border: "1px solid rgba(255,255,255,0.12)",
  boxShadow: "none",
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
  { en:"Neck forward–backward flexion", tr:"Boynu öne-arkaya eğme", ue:false },
  { en:"Shoulder elevation (shrug)", tr:"Omuz elevasyonu (silkme)", ue:true },
  { en:"Forward arm raise", tr:"Öne kol kaldırma (omuz fleksiyonu)", ue:true },
  { en:"Elbow flexion", tr:"Dirsek fleksiyonu", ue:true },
  { en:"Thumb-to-finger opposition", tr:"Başparmak-parmak karşıtlığı", ue:true },
  { en:"Forward trunk lean", tr:"Öne gövde eğilmesi", ue:false },
  { en:"Knee extension", tr:"Diz ekstansiyonu", ue:false },
  { en:"Hip abduction", tr:"Kalça abduksiyonu", ue:false },
  { en:"Foot tapping", tr:"Ayak vurma", ue:false },
  { en:"Foot external rotation", tr:"Ayak dış rotasyonu", ue:false },
];

const KGIA_TYPES = [
  {
    key:"gorsel", en:"Visual", tr:"Görsel",
    qEN:"How clearly do you see this movement in your mind?",
    qTR:"Bu hareketi zihninizde ne kadar net görüyorsunuz?",
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
    qEN:"How strongly do you feel as if you are performing this movement?",
    qTR:"Bu hareketi yapıyormuş gibi ne kadar hissediyorsunuz?",
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
  // WMFT-4: 4-item short form (Kim et al., 2026) — R=0.98 with full WMFT
  { id:1, en:"Hand to Table (front)", tr:"Eli masaya koyma (ön)" },
  { id:2, en:"Hand to Box (front)", tr:"Eli kutuya koyma (ön)" },
  { id:3, en:"Extend Elbow (no weight)", tr:"Dirsek uzatma (ağırlıksız)" },
  { id:4, en:"Lift Can (front)", tr:"Kutu kaldırma (ön)" },
];

const COMORBIDITIES = [
  { value:"hypertension", label:"Hypertension / Hipertansiyon" },
  { value:"hypotension", label:"Hypotension / Hipotansiyon" },
  { value:"diabetes", label:"Diabetes / Diyabet" },
  { value:"cardiovascular", label:"Cardiovascular / Kardiyovasküler" },
  { value:"copd", label:"COPD / KOAH" },
  { value:"arthritis", label:"Arthritis / Artrit" },
  { value:"osteoporosis", label:"Osteoporosis / Osteoporoz" },
  { value:"depression", label:"Depression / Depresyon" },
  { value:"other", label:"Other / Diğer" },
];

const VAS_FACES = [
  { val:0, emoji:"😊", en:"No hurt", tr:"Acı yok" },
  { val:2, emoji:"🙂", en:"Hurts little bit", tr:"Biraz acıyor" },
  { val:4, emoji:"😐", en:"Hurts little more", tr:"Biraz daha acıyor" },
  { val:6, emoji:"😟", en:"Hurts even more", tr:"Daha çok acıyor" },
  { val:8, emoji:"😢", en:"Hurts whole lot", tr:"Çok acıyor" },
  { val:10, emoji:"😭", en:"Hurts worst", tr:"En kötü acı" },
];

const VAMS_FACES = [
  { val:0, emoji:"😐", en:"Neutral", tr:"Nötr" },
  { val:2, emoji:"🙂", en:"A little", tr:"Biraz" },
  { val:4, emoji:"😊", en:"Somewhat", tr:"Oldukça" },
  { val:6, emoji:"😃", en:"Moderately", tr:"Orta" },
  { val:8, emoji:"😄", en:"Very", tr:"Çok" },
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
  { id:"analysis", icon:BarChart3, en:"Analysis Dashboard", tr:"Analiz Paneli" },
];

const LS_KEY = "stroke_rehab_patients_v6";

function loadPatients() {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch { return []; }
}
function savePatients(list) {
  localStorage.setItem(LS_KEY, JSON.stringify(list));
}

/** Drop heavy kinematic arrays before server sync (keep summary metrics). */
function stripKinPhaseForSync(phase) {
  if (!phase || typeof phase !== "object") return phase;
  const { velocity_profile, phases, ...rest } = phase;
  return rest;
}
function stripKinResultsForSync(kin) {
  if (!kin || typeof kin !== "object") return kin;
  return Object.fromEntries(
    Object.entries(kin).map(([k, v]) => [k, stripKinPhaseForSync(v)])
  );
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patients: patientsForServerSync(patients) }),
  });
}

const PATIENTS_SYNC_EVENT = "neurolab-patients-synced";
const SYNC_FETCH_MS = 90000;

async function fetchWithTimeout(url, options = {}, ms = SYNC_FETCH_MS) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...options, signal: ctrl.signal });
  } finally {
    clearTimeout(timer);
  }
}

function mergePatientLists(serverPts, localPts) {
  const merged = Array.isArray(serverPts) ? [...serverPts] : [];
  localPts.forEach((lp) => {
    const id = lp._id || lp.demographics?.participantId;
    if (id && !merged.some((sp) => (sp._id || sp.demographics?.participantId) === id)) {
      merged.push(lp);
    }
  });
  return merged;
}

/** Push local patients to server, pull merge, persist to localStorage. */
async function syncPatientsWithServer({ showToast, silent = false } = {}) {
  const localPts = loadPatients();
  try {
    const push = await fetchWithTimeout("/api/patients", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patients: patientsForServerSync(localPts) }),
    });
    if (!push.ok) {
      const detail = await push.text().catch(() => "");
      if (!silent) showToast?.(`Server save failed (${push.status})`, "error");
      console.warn("Patient push sync failed:", push.status, detail);
      return { ok: false, patients: localPts, pushed: false };
    }

    const r = await fetchWithTimeout("/api/patients");
    if (!r.ok) {
      if (!silent) showToast?.(`Could not load server records (${r.status})`, "error");
      return { ok: false, patients: localPts, pushed: true };
    }

    const serverPts = await r.json();
    const merged = mergePatientLists(serverPts, localPts);
    savePatients(merged);
    window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count: merged.length } }));

    if (!silent) {
      if (merged.length === 0) {
        showToast?.("Sync OK — no records yet. Save a session first.", "info");
      } else {
        showToast?.(`✓ Synced — ${merged.length} record(s)`, "success");
      }
    }
    return { ok: true, patients: merged, pushed: true };
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

// ─── Shared UI ────────────────────────────────────────────────────────────────

const Glass = ({ children, className = "", style = {}, soft = false, ...r }) => (
  <div
    className={`glass-float rounded-2xl ${GLASS_CLS} ${className}`}
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
  <div className="flex flex-col sm:flex-row sm:items-center gap-2.5 sm:gap-3 mb-5 sm:mb-6">
    <div className="flex items-start sm:items-center gap-3 min-w-0 flex-1">
      <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl flex items-center justify-center flex-shrink-0" style={GLASS_FIELD}>
      <Icon className="w-5 h-5 text-white/80" />
    </div>
    <div className="min-w-0 flex-1">
        <h2 className="text-base sm:text-xl font-extrabold text-white leading-snug">{en}</h2>
        <p className="text-[10px] sm:text-xs font-light text-white/35 uppercase tracking-wide sm:tracking-widest mt-0.5">{tr}</p>
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
  const ref = useRef(null);
  const btnRef = useRef(null);

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

  const sel = options.find((o) => o.value === value);

  return (
    <div className={`flex flex-col gap-1.5 ${className}`} ref={ref}>
      {en && <BL en={en} tr={tr} />}
      <div style={{ position: "relative" }}>
        <button
          ref={btnRef}
          type="button"
          onClick={() => setOpen((p) => !p)}
          className={`w-full px-3 py-2.5 rounded-xl text-white text-sm font-light text-left flex items-center justify-between gap-2 ${INPUT_CLS}`}
          style={GLASS_FIELD}
        >
          <span className={`truncate ${sel ? "text-white" : "text-white/30"}`}>
            {sel ? sel.label : "Select\u2026"}
          </span>
          <span className="text-white/40 flex-shrink-0 flex items-center justify-center w-4 h-4">
            <svg width="10" height="6" viewBox="0 0 10 6" fill="none" className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}>
              <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </button>

        {open && btnRef.current && ReactDOM.createPortal(
          <div data-gselect-portal="true"
            style={{
              position: "fixed",
              top: btnRef.current.getBoundingClientRect().bottom + 4,
              left: btnRef.current.getBoundingClientRect().left,
              width: btnRef.current.getBoundingClientRect().width,
              zIndex: 999999,
            }}
          >
            <div className="overflow-hidden py-1" style={GSELECT_MENU_BOX}>
              {options.map((o) => {
                const selected = value === o.value;
                const optStyle = {
                  backgroundColor: selected ? "rgba(255,255,255,0.10)" : "transparent",
                  color: selected ? "#ffffff" : "rgba(255,255,255,0.75)",
                  fontWeight: selected ? 700 : 400,
                  transition: "background-color 0.15s",
                };
                return (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => { onChange({ target: { value: o.value } }); setOpen(false); }}
                  className="w-full text-left px-3 py-2.5 text-sm block"
                  style={optStyle}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.10)";
                    e.currentTarget.style.color = "#ffffff";
                    e.currentTarget.style.fontWeight = "700";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = selected ? "rgba(255,255,255,0.10)" : "transparent";
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
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-md border font-semibold text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed ${v[variant]} ${className}`}
    >
      {children}
    </motion.button>
  );
};

const PullToRefresh = ({ scrollRef }) => {
  const pullRef = useRef(0);
  const tracking = useRef(false);
  const refreshingRef = useRef(false);
  const startY = useRef(0);
  const enabled = isIOSDevice() || isStandalonePWA();

  const paint = useCallback((el, y, state) => {
    pullRef.current = y;
    const inner = el.querySelector(".ptr-inner");
    const spinner = inner?.querySelector(".ptr-spinner-anchor");
    if (inner) {
      if (y > 0 || state === "refreshing") {
        inner.style.paddingTop = `${y}px`;
        inner.style.transform = "";
      } else {
        inner.style.paddingTop = "0px";
        inner.style.transform = "";
      }
      inner.style.transition = state === "idle"
        ? "padding-top 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)"
        : "none";
    }
    if (!spinner) return;
    const show = y >= 10 || state === "refreshing";
    spinner.style.opacity = show
      ? String(state === "refreshing" ? 1 : Math.min((y - 10) / 14, 1))
      : "0";
    const ring = spinner.querySelector(".ptr-ring");
    if (ring) {
      if (state === "refreshing") {
        ring.classList.add("ptr-ring-active");
        ring.style.transform = "";
      } else {
        ring.classList.remove("ptr-ring-active");
        const p = Math.min(y / PTR_THRESHOLD, 1);
        ring.style.transform = `rotate(${-90 + p * 360}deg) scale(${0.45 + p * 0.55})`;
      }
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const el = scrollRef?.current;
    if (!el) return;

    const onStart = (e) => {
      if (refreshingRef.current || el.scrollTop > 1) return;
      startY.current = e.touches[0].clientY;
      tracking.current = true;
    };

    const onMove = (e) => {
      if (!tracking.current || refreshingRef.current) return;
      const dy = e.touches[0].clientY - startY.current;
      if (el.scrollTop <= 0 && dy > 0) {
        paint(el, Math.min(dy * 0.52, PTR_MAX_PULL), "pulling");
        if (dy > 4 && e.cancelable) e.preventDefault();
      } else if (dy <= 0 && el.scrollTop <= 0) {
        paint(el, 0, "idle");
      }
    };

    const finish = () => {
      if (!tracking.current) return;
      tracking.current = false;
      if (pullRef.current >= PTR_THRESHOLD && !refreshingRef.current) {
        refreshingRef.current = true;
        paint(el, 48, "refreshing");
        window.location.reload();
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
    };
  }, [enabled, scrollRef, paint]);

  return null;
};

const Toast = ({ msg, visible, variant = "success" }) => (
  <AnimatePresence>
    {visible && (
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.94 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -10 }}
        className={`fixed bottom-8 right-8 z-[99999] flex items-center gap-2.5 px-5 py-3 rounded-2xl backdrop-blur-xl border text-sm font-semibold shadow-2xl ${
          variant === "success"
            ? "bg-emerald-500/20 border-emerald-400/30 text-emerald-200"
            : variant === "info"
            ? "bg-sky-500/20 border-sky-400/30 text-sky-200"
            : "bg-rose-500/20 border-rose-400/30 text-rose-200"
        }`}
      >
        <Check className="w-4 h-4" /> {msg}
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
  const text = formatKinPrePostPct(pct);
  if (!text) return null;
  return {
    text,
    colorClass:
      pct >= 0
        ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
        : "text-rose-400 bg-rose-400/10 border-rose-400/20",
  };
};

const kinPostHealthyBadge = (post, healthy, direction) => {
  const pct = calcGap(post, healthy, direction);
  const text = formatKinPostHealthyPct(pct);
  if (!text) return null;
  return {
    text,
    colorClass: "text-amber-300/90 bg-amber-400/10 border-amber-400/25",
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
          const active = Math.abs(face.val - n) < 1.5;
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
          return `${v.toFixed(1)} / 10 — ${face.en} / ${face.tr}`;
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
          const active = Math.abs(face.val - n) < 1.5;
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
          return `${v.toFixed(1)} / 10 — ${face.en} / ${face.tr}`;
        }}
      />
    </div>
  );
};

const MotorSlider = ({ value, onChange, color = "sky" }) => {
  const n = parseFloat(value) || 0;

  const getLabel = (v) => {
    if (v === 0) return "No control / Kontrol yok";
    if (v <= 2) return "Very limited / Çok sınırlı";
    if (v <= 4) return "Limited / Sınırlı";
    if (v <= 6) return "Moderate / Orta";
    if (v <= 8) return "Good / İyi";
    return "Full control / Tam kontrol";
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
          return item ? `${v} — ${item.en} / ${item.tr}` : "Select / Seçin";
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

const SWBlock = ({ phase, taskData, onUpdate }) => {
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
              whileTap={{ scale: 0.88 }}
              onClick={fn}
              disabled={dis}
              className={`w-9 h-9 rounded-xl border flex items-center justify-center transition-all ${dis ? `${disCls} cursor-not-allowed` : cls}`}
            >
              <Icon className="w-3.5 h-3.5" />
            </motion.button>
          ))}

          <motion.button
            whileTap={{ scale: 0.88 }}
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

// ─── Demographics ─────────────────────────────────────────────────────────────

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
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Identification / Kimlik</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <GI en="Full Name" tr="Ad Soyad" value={data.name} onChange={(e) => s("name", e.target.value)} />
          <GI en="Study ID" tr="Çalışma Kimliği" type="number" min="101" value={data.participantId} onChange={(e) => s("participantId", e.target.value)} placeholder="Auto" />
          <GSelect en="Group" tr="Grup" value={data.group} onChange={(e) => s("group", e.target.value)} options={[{ value:"1",label:"1 = AOMI (Intervention)" },{ value:"2",label:"2 = Control" }]} />
          <GI en="Age (years)" tr="Yaş (yıl)" type="number" min="40" max="80" value={data.age} onChange={(e) => s("age", e.target.value)} placeholder="40–80" />
          <GSelect en="Gender" tr="Cinsiyet" value={data.sex} onChange={(e) => s("sex", e.target.value)} options={[{ value:"1",label:"1 = Male / Erkek" },{ value:"2",label:"2 = Female / Kadın" }]} />
          <GI en="Time Since Stroke (months)" tr="İnme Üzerinden Geçen Süre (ay)" type="number" min="1" value={data.timeSinceStroke} onChange={(e) => s("timeSinceStroke", e.target.value)} placeholder="months" />
        </div>
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Clinical / Klinik</p>

        <p className="text-[10px] font-bold text-white/30 uppercase tracking-wider mb-3">Side &amp; Hemisphere / Taraf &amp; Hemisfer</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <GSelect en="Dominant Hand" tr="Dominant El" value={data.dominantHand} onChange={(e) => s("dominantHand", e.target.value)} options={[{ value:"right",label:"Right / Sağ" },{ value:"left",label:"Left / Sol" },{ value:"both",label:"Both / İki El" }]} />
          <GSelect en="Affected Hemisphere" tr="Etkilenen Hemisfer" value={data.hemisphere} onChange={(e) => s("hemisphere", e.target.value)} options={[{ value:"left",label:"Left / Sol" },{ value:"right",label:"Right / Sağ" },{ value:"bilateral",label:"Bilateral" }]} />
          <GSelect en="Stroke Type" tr="İnme Tipi" value={data.strokeType} onChange={(e) => s("strokeType", e.target.value)} options={[{ value:"1",label:"1 = Ischemic / İskemik" },{ value:"2",label:"2 = Hemorrhagic / Hemorajik" }]} />
          <GSelect en="Affected Side" tr="Etkilenen Taraf" value={data.side} onChange={(e) => s("side", e.target.value)} options={[{ value:"1",label:"1 = Left / Sol" },{ value:"2",label:"2 = Right / Sağ" }]} />
        </div>

        <p className="text-[10px] font-bold text-white/30 uppercase tracking-wider mb-3">Anthropometrics / Antropometri</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <GI en="Height (cm)" tr="Boy (cm)" type="number" value={data.height} onChange={(e) => s("height", e.target.value)} placeholder="170" />
          <GI en="Weight (kg)" tr="Kilo (kg)" type="number" value={data.weight} onChange={(e) => s("weight", e.target.value)} placeholder="70" />
          <div className="flex flex-col gap-1.5">
            <BL en="BMI (auto)" tr="VKİ (otomatik)" />
            <div className={`w-full px-3 py-2.5 rounded-xl border text-sm font-extrabold text-center ${(() => { const h=parseFloat(data.height), w=parseFloat(data.weight); if(!h||!w) return "bg-white/[0.05] border-white/[0.04] text-white/25"; const b=(w/((h/100)**2)).toFixed(1); if(b<18.5) return "bg-sky-400/10 border-sky-400/20 text-sky-300"; if(b<25) return "bg-emerald-400/10 border-emerald-400/20 text-emerald-300"; if(b<30) return "bg-amber-400/10 border-amber-400/20 text-amber-300"; return "bg-rose-400/10 border-rose-400/20 text-rose-300"; })()}`}>
              {(() => { const h=parseFloat(data.height), w=parseFloat(data.weight); return h&&w ? `${(w/((h/100)**2)).toFixed(1)} kg/m²` : "—"; })()}
            </div>
          </div>
          <GI en="Shoulder Width (cm)" tr="Omuz Genişliği (cm)" type="number" step="0.1" value={data.shoulderWidth || ""} onChange={(e) => s("shoulderWidth", e.target.value)} placeholder={(() => { const h=parseFloat(data.height); return h ? `~${(0.23*h).toFixed(1)}` : "~39"; })()} />
        </div>

        <p className="text-[10px] font-bold text-white/30 uppercase tracking-wider mb-3">Dates / Tarihler</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <GI en="Assessment Date" tr="Değerlendirme Tarihi" type="date" value={data.assessDate} onChange={(e) => s("assessDate", e.target.value)} />
          <GI en="Stroke Date" tr="İnme Tarihi" type="date" value={data.strokeDate} onChange={(e) => s("strokeDate", e.target.value)} />
        </div>

        <p className="text-[10px] font-bold text-white/30 uppercase tracking-wider mb-3">Clinical Assessment / Klinik Değerlendirme</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
          <GSelect en="MAS (Modified Ashworth)" tr="MAS" value={data.mas} onChange={(e) => s("mas", e.target.value)} options={[{ value:"0",label:"0 — No increase" },{ value:"1",label:"1 — Slight catch" },{ value:"1+",label:"1+ — Catch + minimal resistance" },{ value:"2",label:"2 — More marked" },{ value:"3",label:"3 — Considerable" },{ value:"4",label:"4 — Rigid" }]} />
          <GSelect en="MRC Muscle Strength" tr="MRC Kas Gücü" value={data.mrc} onChange={(e) => s("mrc", e.target.value)} options={[{ value:"2",label:"2 — Active, gravity eliminated" },{ value:"3",label:"3 — Against gravity" },{ value:"4",label:"4 — Against some resistance" },{ value:"5",label:"5 — Normal power" }]} />
        </div>
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Medical History / Tıbbi Geçmiş</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <GSelect en="Disease Stage" tr="Hastalık Evresi" value={data.diseaseStage} onChange={(e) => s("diseaseStage", e.target.value)} options={[{ value:"acute",label:"Acute (<1 month) / Akut" },{ value:"subacute",label:"Subacute (1-6 months) / Subakut" },{ value:"chronic",label:"Chronic (>6 months) / Kronik" }]} />
          <div className="flex flex-col gap-1.5">
            <BL en="Treatment Duration" tr="Tedavi Süresi" />
            <div className="flex gap-2">
              <input type="number" value={data.treatValue ?? ""} onChange={(e) => s("treatValue", e.target.value)} placeholder="0" className="flex-1 min-w-0 px-3 py-2.5 rounded-xl bg-white/[0.09] border border-white/12 text-white text-sm font-light focus:outline-none transition-all" />
              <select value={data.treatUnit ?? "week"} onChange={(e) => s("treatUnit", e.target.value)} className="w-24 flex-shrink-0 px-2 py-2.5 rounded-xl bg-white/[0.09] border border-white/12 text-white text-sm font-light focus:outline-none transition-all appearance-none" style={{ colorScheme:"dark" }}>{["day","week","month","year"].map((u) => <option key={u} value={u} className="bg-[#0e1120]">{u}</option>)}</select>
            </div>
          </div>
        </div>
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-1">Comorbidities / Eşlik Eden Hastalıklar</p>
        <p className="text-xs text-white/30 mb-4">Select all that apply / Geçerli tüm seçenekleri işaretleyin</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
          {COMORBIDITIES.map((opt) => {
            const active = (data.comorbidities || []).includes(opt.value);
            return (
              <motion.button key={opt.value} whileTap={{ scale:0.95 }} onClick={() => { const cur = data.comorbidities || []; s("comorbidities", cur.includes(opt.value) ? cur.filter((c) => c !== opt.value) : [...cur, opt.value]); }}
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
            <GI en="Specify other" tr="Diğerini belirtin" value={data.otherComorbidity} onChange={(e) => s("otherComorbidity", e.target.value)} placeholder="Other conditions…" />
          </motion.div>
        )}
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Clinical Notes / Klinik Notlar</p>
        <div className="flex flex-col gap-3">
          <textarea rows={2} value={data.notes ?? ""} onChange={(e) => s("notes", e.target.value)} placeholder="Medical history, comorbidities, assessment context…" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.09] border border-white/12 text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none transition-all" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <textarea rows={2} value={data.antispasticDrugs ?? ""} onChange={(e) => s("antispasticDrugs", e.target.value)} placeholder="Antispastic drugs: Baclofen, Tizanidine…" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.09] border border-white/12 text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none transition-all" />
            <textarea rows={2} value={data.otherDrugs ?? ""} onChange={(e) => s("otherDrugs", e.target.value)} placeholder="Other medications: Aspirin, Warfarin…" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.09] border border-white/12 text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none transition-all" />
          </div>
        </div>
      </Glass>
    </div>
  );
};

// ─── IPAQ Section ─────────────────────────────────────────────────────────────

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
      return { level:"High", color:"emerald", text:"Vigorous activity ≥3 days & ≥1500 MET-min/week" };
    }
    if ((medDays + lightDays) >= 7 && totalMET >= 3000) {
      return { level:"High", color:"emerald", text:"Mixed activities 7 days & ≥3000 MET-min/week" };
    }
    if (totalMET >= 600 || (medDays + lightDays >= 5 && (med + light) >= 150)) {
      return { level:"Moderate", color:"amber", text:"≥600 MET-min/week or 5+ days moderate/walking" };
    }
    return { level:"Low", color:"rose", text:"Not meeting moderate or high criteria" };
  };

  const cls = getClass();

  return (
    <div className="space-y-5">
      <SH icon={Activity} en="International Physical Activity Questionnaire (IPAQ)" tr="Uluslararası Fiziksel Aktivite Anketi" />

      <Glass className="p-4 sm:p-5">
        {/* Mobile — stacked cards (no horizontal squeeze) */}
        <div className="md:hidden space-y-3">
          {IPAQ_ACTS.map((a) => (
            <div key={a.id} className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3 space-y-3">
              <div>
                <p className="text-sm font-extrabold text-white/90 leading-snug">{a.en}</p>
                <p className="text-[10px] text-white/35 italic mt-0.5">{a.tr}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[10px] font-extrabold text-sky-300/90 uppercase mb-1.5">Min/day · Dk/gün</p>
                  <input type="number" min="0" value={data[a.id]?.sure ?? ""} onChange={(e) => sv(a.id, "sure", e.target.value)} className={ic} placeholder="—" />
                </div>
                <div>
                  <p className="text-[10px] font-extrabold text-violet-300/90 uppercase mb-1.5">Days/wk · Gün</p>
                  <input type="number" min="0" max="7" value={data[a.id]?.gun ?? ""} onChange={(e) => sv(a.id, "gun", e.target.value)} className={ic} placeholder="—" />
                </div>
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-white/[0.06]">
                <span className="text-[10px] font-extrabold text-emerald-300/80 uppercase">Total min/wk</span>
                <div className="px-3 py-1.5 rounded-lg bg-emerald-400/10 border border-emerald-400/20 text-emerald-300 font-extrabold text-sm min-w-[3rem] text-center">{tot(a.id)}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Desktop — table */}
        <div className="hidden md:block glass-float overflow-x-auto rounded-xl border border-white/[0.08]">
          <table className="w-full text-sm min-w-[580px]">
            <thead>
              <tr className="bg-white/[0.06] border-b border-white/[0.04]">
                <th className="text-left px-3 py-3 font-extrabold text-white/70 text-xs uppercase w-1/2">Activity / Aktivite</th>
                <th className="text-center px-3 py-3 text-sky-300 text-xs font-extrabold uppercase">
                  Min/day
                  <br />
                  <span className="font-light text-white/30">Dk/gün</span>
                </th>
                <th className="text-center px-3 py-3 text-violet-300 text-xs font-extrabold uppercase">
                  Days/week
                  <br />
                  <span className="font-light text-white/30">Gün/hafta</span>
                </th>
                <th className="text-center px-3 py-3 text-emerald-300 text-xs font-extrabold uppercase">
                  Total min/wk
                  <br />
                  <span className="font-light text-white/30">Toplam</span>
                </th>
              </tr>
            </thead>

            <tbody>
              {IPAQ_ACTS.map((a, i) => (
                <tr key={a.id} className={`border-b border-white/[0.06] hover:bg-white/[0.03] ${i % 2 === 0 ? "" : "bg-white/[0.02]"}`}>
                  <td className="px-3 py-3 text-xs text-white/80">
                    <span className="block">{a.en}</span>
                    <span className="block text-white/35 text-[10px] italic mt-0.5">{a.tr}</span>
                  </td>
                  <td className="px-2 py-2">
                    <input type="number" min="0" value={data[a.id]?.sure ?? ""} onChange={(e) => sv(a.id, "sure", e.target.value)} className={ic} placeholder="—" />
                  </td>
                  <td className="px-2 py-2">
                    <input type="number" min="0" max="7" value={data[a.id]?.gun ?? ""} onChange={(e) => sv(a.id, "gun", e.target.value)} className={ic} placeholder="—" />
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

// ─── VAS Section ──────────────────────────────────────────────────────────────

const VASSection = ({ data, onChange }) => {
  const s = (k, ph, v) => onChange({ ...data, [k]: { ...data[k], [ph]: v } });
  const items = [
    { k:"rest", en:"Pain at Rest", tr:"İstirahat Ağrısı" },
    { k:"activity", en:"Pain During Activity", tr:"Aktivite Sırasında Ağrı" },
    { k:"night", en:"Night Pain", tr:"Gece Ağrısı" },
  ];

  return (
    <div className="space-y-5">
      <SH icon={Sliders} en="Visual Analogue Scale (VAS)" tr="Görsel Analog Skala" badge="0 – 10 with Faces" />

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
          <p className="text-xs font-extrabold text-white/70 uppercase tracking-widest">Session Notes / Seans Notları</p>
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
                {exists ? "✕ " : "+ "}{btn.label}
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

// ─── VAMS-4 Section ──────────────────────────────────────────────────────────────

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
      <SH icon={Heart} en="Mood Scale (VAMS-4)" tr="Ruh Hali Ölçeği" badge="0 – 10" />

      <Glass className="p-5 border-l-2 border-violet-400/40">
        <div className="flex gap-3">
          <Heart className="w-5 h-5 text-violet-300 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-light text-white/75">
              Rate your current mood from <span className="font-bold text-white">0 (not at all)</span> to <span className="font-bold text-white">10 (extremely)</span>
            </p>
            <p className="text-xs text-white/50 mt-1">VAMS-4 (Machado et al. 2019) · Validated in stroke (Stern 1999, Barrows 2018)</p>
          </div>
        </div>
      </Glass>

      {items.map((item) => (
        <Glass key={item.k} className="p-5">
          <BL en={item.en} tr={item.tr} className="mb-1" />
          <div className="flex items-center gap-2 mb-4 px-0.5">
            <p className="text-xs text-white/60 italic">{item.qEN}</p>
            <span className="text-white/20 text-[9px]">/</span>
            <p className="text-xs text-white/35 italic">{item.qTR}</p>
          </div>

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

// ─── Motor Section ────────────────────────────────────────────────────────────

const MotorSection = ({ data, onChange }) => {
  const s = (k, v) => onChange({ ...data, [k]: v });

  return (
    <div className="space-y-5">
      <SH icon={TrendingUp} en="Patient Perceived Muscle Control Change Scale" tr="Hasta Algılanan Kas Kontrol Değişim Ölçeği" />

      <Glass className="p-5 border-l-2 border-amber-400/40">
        <div className="flex gap-3">
          <Info className="w-5 h-5 text-amber-300 flex-shrink-0 mt-0.5" />
          <p className="text-sm font-light text-white/75 italic">0 = no control, 10 = full normal control. / 0 = hiç kontrol yok, 10 = tam kontrol.</p>
        </div>
      </Glass>

      {MOTOR_ITEMS.map((item) => (
        <Glass key={item.key} className="p-5">
          <p className="font-extrabold text-white/90 text-sm mb-0.5">{item.en}</p>
          <p className="text-xs font-light text-white/35 mb-4">{item.tr}</p>

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

// ─── KVIQ Section ─────────────────────────────────────────────────────────────

const KGIASection = ({ data, onChange }) => {
  const s = (mi, type, f, v) => {
    const k = `${mi}_${type}`;
    onChange({ ...data, [k]: { ...(data[k] || {}), [f]: v } });
  };

  return (
    <div className="space-y-5">
      <SH icon={Brain} en="Kinesthetic & Visual Imagery Questionnaire (KVIQ-10)" tr="Kinestetik ve Görsel İmgeleme Anketi" badge="10 Movements × 2 Types" />

      <div className="flex gap-3 flex-wrap">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-400/10 border border-amber-400/20">
          <span className="w-3 h-3 rounded-full bg-amber-400 flex-shrink-0" />
          <span className="text-xs font-bold text-amber-300">Upper Extremity / Üst Ekstremite</span>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.04]">
          <span className="w-3 h-3 rounded-full bg-white/30 flex-shrink-0" />
          <span className="text-xs font-bold text-white/50">Other / Diğer</span>
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
                <p className="text-xs font-light text-white/40 mt-0.5">{mov.tr}</p>
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
                    <span className="text-[10px] text-white/35">{t.tr}</span>
                  </div>

                  <p className="text-xs font-semibold text-white/65 mb-0.5">{t.qEN}</p>
                  <p className="text-[10px] font-light text-white/35 mb-4 italic">{t.qTR}</p>

                  {["once","sonra"].map((f, fi) => (
                    <div key={f} className={fi === 1 ? "mt-4" : ""}>
                      <p className={`text-[10px] font-extrabold uppercase tracking-widest mb-2 ${fi === 0 ? "text-sky-300" : "text-emerald-300"}`}>
                        {fi === 0 ? "Pre (1–5) / Önce" : "Post (1–5) / Sonra"}
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

// ─── WMFT Section ─────────────────────────────────────────────────────────────

const WMFTSection = ({ data, onChange }) => {
  const up = (id, ph, f, v) =>
    onChange({ ...data, [id]: { ...data[id], [ph]: { ...(data[id]?.[ph] || {}), [f]: v } } });

  return (
    <div className="space-y-5">
      <SH icon={Timer} en="Wolf Motor Function Test (WMFT-4)" tr="Wolf Motor Fonksiyon Testi — Kısa Form" badge="4 Tasks" />

      {WMFT_ITEMS.map((t) => (
        <Glass key={t.id} className="p-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-xl bg-amber-500/20 border border-amber-400/20 flex items-center justify-center text-amber-300 font-extrabold text-sm flex-shrink-0">
              {t.id}
            </div>
            <div>
              <p className="font-extrabold text-white/90 text-sm">{t.en}</p>
              <p className="text-xs font-light text-white/35 mt-0.5">{t.tr}</p>
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

// ─── Form data persistence ────────────────────────────────────────────────────

const FD_LS_KEY = "neuro_fd_data";
const NEXT_ID_LS_KEY = "neuro_next_id";
const API_BASE = "";

// Cross-platform file download — never window.open on iOS PWA (no back button)
function downloadBlob(blob, filename) {
  const tryShare = async () => {
    if (!navigator.share) return false;
    try {
      const file = new File([blob], filename, { type: blob.type || "application/octet-stream" });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: filename });
        return true;
      }
    } catch (_) {}
    return false;
  };

  const linkDownload = () => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  };

  if (isIOSDevice()) {
    tryShare().then((shared) => { if (!shared) linkDownload(); });
    return;
  }
  linkDownload();
}

function nextStudyId() {
  const patients = loadPatients();
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
  const entries = Object.entries(profiles).filter(([_, p]) => p?.t?.length >= 2);
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


// ─── Kinematics AI Lab Section ────────────────────────────────────────────────

const KIN_LS_KEY = "neuro_kin_results";
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

const KIN_SKELETON_VIEWS = ["front", "posterior", "right", "left"];

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
  const frames = [...KIN_SKELETON_VIEWS, ...KIN_SKELETON_VIEWS];
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
          {frames.map((_, i) => (
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

function KinPhaseAnalyzingOverlay({ accent = "amber" }) {
  const blur = {
    backdropFilter: "blur(80px) saturate(180%)",
    WebkitBackdropFilter: "blur(80px) saturate(180%)",
  };
  return (
    <motion.div
      key="kin-analyzing"
      className="kin-analyzing-overlay absolute inset-0 z-30 flex items-center justify-center rounded-2xl overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="absolute inset-0 z-0 rounded-2xl" style={blur} />
      <div className="relative z-20 w-full px-3 flex justify-center">
        <KinFilmStripLoop accent={accent} />
      </div>
    </motion.div>
  );
}

const kinPhaseCardCls = (c, status, hasResult) => {
  const a = KIN_PHASE_ACCENT[c] || KIN_PHASE_ACCENT.amber;
  const base = `relative flex flex-col rounded-2xl border border-t-[3px] bg-gradient-to-b ${a.top} to-white/[0.02] min-h-[240px] transition-all duration-300 overflow-hidden`;
  if (status === "analyzing") return `${base} border-amber-400/35 ring-1 ring-amber-400/20 kin-analyzing-ring`;
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

const armSideLabel = (side) => (side === "left" ? "Left" : side === "right" ? "Right" : "—");

const analyzedArmForPhase = (kinematicsResults, phaseKey) => {
  const s = (kinematicsResults[phaseKey]?.side_analyzed || kinematicsResults[phaseKey]?.side || "").toString().toLowerCase();
  return s === "left" || s === "right" ? s : null;
};

const KinSection = ({ data, demographics, onChange, showToast, sessionKey }) => {
  const [kinematicsResults, setKinematicsResults] = useState(() => {
    try {
      const ls = JSON.parse(localStorage.getItem(KIN_LS_KEY)) || {};
      const fd = data?.analysisResults || {};
      const merged = { ...fd, ...ls };
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
  const [expandedResults, setExpandedResults] = useState(() => {
    try { return JSON.parse(localStorage.getItem(KIN_LS_EXP_KEY)) || {}; } catch { return {}; }
  });
  const [kinResultsTab, setKinResultsTab] = useState("compare");
  const [mediaPreview, setMediaPreview] = useState(null);

  const abortRef = useRef({});

  useEffect(() => {
    localStorage.setItem(KIN_LS_KEY, JSON.stringify(kinematicsResults));
  }, [kinematicsResults]);

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
      sparc: "sparc",
      trunkRatio: "trunk_ratio",
      shoulderVertNorm: "shoulder_vert_norm",
      elbowAngleMean: "elbow_angle_mean",
      movementTimeSec: "movement_time_sec",
      peakVelocityPxS: "peak_velocity_px_s",
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
    const upd = { ...data, [vidKey(phase)]: file.name, [`${vidKey(phase)}_file`]: file };
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
    delete upd[resultKey(phase)];
    upd[statusKey(phase)] = "idle";
    const nextResults = { ...kinematicsResults };
    delete nextResults[phase];
    setKinematicsResults(nextResults);
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
      delete upd[resultKey(ph.k)];
      upd[statusKey(ph.k)] = "idle";
    });
    upd.analysisResults = {};
    setKinematicsResults({});
    setExpandedResults({});
    setKinResultsTab("compare");
    localStorage.removeItem(KIN_LS_KEY);
    localStorage.removeItem(KIN_LS_EXP_KEY);
    onChange(upd);
    showToast("All kinematics cleared");
  };

  const analyzeVideo = async (phase) => {
    const file = data[`${vidKey(phase)}_file`];
    if (!file) {
      showToast("Please select a file first", "error");
      return;
    }

    const controller = new AbortController();
    abortRef.current[phase] = controller;
    onChange({ ...data, [statusKey(phase)]: "analyzing" });

    try {
      const fd = new FormData();
      const isCsv = file.name.endsWith(".csv");
      fd.append(isCsv ? "csv" : "video", file);
      fd.append("phase", phase);
      const strokeSideRaw = (demographics?.side || demographics?.affectedSide || demographics?.strokeSide || "auto").toString();
      const strokeSide = strokeSideRaw === "1" ? "left" : strokeSideRaw === "2" ? "right" : strokeSideRaw.toLowerCase();
      fd.append("stroke_side", strokeSide.includes("left") ? "left" : strokeSide.includes("right") ? "right" : "auto");
      fd.append("affected_side", "auto");
      fd.append("cutoff_frequency", settings.cutoffFrequency.toString());
      fd.append("filter_order", settings.filterOrder.toString());
      fd.append("patient_height_cm", demographics?.height || "auto");
      fd.append("shoulder_width_cm", demographics?.shoulderWidth || "auto");
      const sexRaw = (demographics?.sex || demographics?.gender || "unknown").toString().toLowerCase();
      fd.append("patient_sex", sexRaw.includes("female") || sexRaw === "2" ? "female" : sexRaw.includes("male") || sexRaw === "1" ? "male" : "unknown");
      if (!isCsv) {
        fd.append("arm_type", "paretic");
        fd.append("trial_count", "1");
        fd.append("best_trial_metric", "sparc");
      }

      const endpoint = isCsv ? "/analyze-csv" : "/analyze";
      const res = await fetch(`${API_BASE}${endpoint}`, { method: "POST", body: fd, signal: controller.signal });
      if (!res.ok) {
        let detail = `Server error ${res.status}`;
        try { const e = await res.json(); if (e.error || e.detail) detail += `: ${e.error || e.detail}`; } catch (_) {}
        throw new Error(detail);
      }

      const result = await res.json();

      if (result.error) {
        showToast(`Analysis error: ${result.error}`, "error");
        onChange({ ...data, [statusKey(phase)]: "uploaded" });
        delete abortRef.current[phase];
        return;
      }

      const nextResults = { ...kinematicsResults, [phase]: result };
      setKinematicsResults(nextResults);
      onChange({
        ...data,
        analysisResults: nextResults,
        [resultKey(phase)]: result,
        [statusKey(phase)]: "completed",
      });
      showToast(`✓ Analysis complete for ${phase}${result.trials_detected > 1 ? ` (${result.trials_detected} trials → mean)` : ""}${(result.warnings || []).length ? " — see warnings" : ""}`);
    } catch (err) {
      if (err.name === "AbortError") {
        showToast(`✕ Analysis cancelled for ${phase}`, "info");
      } else {
        const errorMsg = `Backend request failed: ${err.message}`;
        showToast(errorMsg, "error");
        console.error("ANALYSIS ERROR:", err);
        // Keep the error message visible longer or alert it
        alert(errorMsg); 
      }
      onChange({ ...data, [statusKey(phase)]: "uploaded" });
    }
    delete abortRef.current[phase];
  };

  const downloadFile = async (phase, type) => {
    const result = kinematicsResults[phase];
    if (!result) return;

    let filename = "";
    if (type === "csv") filename = result.csv_filename;
    if (type === "trc") filename = result.trc_filename;
    if (type === "mot") filename = result.mot_filename;
    if (type === "video") filename = result.validation_video;
    if (!filename) {
      if (type === "video") showToast("Skeleton validation video not available — re-analyze the video file", "error");
      return;
    }

    const url = `${API_BASE}/download-${type}/${encodeURIComponent(filename)}`;

    // Play video inside app — iOS PWA has no back button if we navigate away
    if (type === "video") {
      setMediaPreview({ url, title: `${phases.find((p) => p.k === phase)?.l || phase} — Skeleton Video` });
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

  const toggleResult = (phase) => {
    setExpandedResults((prev) => ({ ...prev, [phase]: !prev[phase] }));
  };

  const getMetricValue = (phase, key) => {
    const result = kinematicsResults[phase];
    if (!result) return "—";
    if (key === "elbow_angle_mean" && result.elbow_angle_reliable === false) return "—";
    const num = pickKinField(result, key);
    if (num !== null) return num;
    if (key === "side_analyzed" || key === "side") {
      return result.side_analyzed ?? result.side ?? "—";
    }
    const direct = result[key];
    if (direct != null && typeof direct !== "object") return direct;
    return "—";
  };

  const displayMetricValue = (phase, key) => {
    const val = getMetricValue(phase, key);
    if (val === "—" || typeof val === "string") return val;
    if (typeof val !== "number") return val;
    if (key === "sparc") return val.toFixed(3);
    if (key === "trunk_ratio") return (val * 100).toFixed(1);
    if (key === "shoulder_vert_norm") return (val * 100).toFixed(1);
    if (key === "elbow_angle_mean") return val.toFixed(1);
    if (key === "movement_time_sec") return val.toFixed(2);
    if (key === "peak_velocity_px_s") return val.toFixed(1);
    if (key.includes("ratio") || key.includes("trunk") || key.includes("_sw") || key.includes("path_eff")) return val.toFixed(3);
    return val.toFixed(2);
  };

  const KIN_TIPS = {
    sparc: "SPARC — less negative (closer to 0) = smoother movement (Balasubramanian 2012/2015).",
    trunk_ratio: "Trunk displacement / palm displacement. Lower = less compensation.",
    shoulder_vert_norm: "Shoulder elevation (method adapts to camera: frontal=rest-to-peak, side=range norm).",
    elbow_angle_mean: "Mean elbow interior angle during reach (MediaPipe world 3D when available; else 2D). Higher = more extended. World method is comparable across left/right arms.",
    movement_time_sec: "Active movement duration (onset to offset).",
    peak_velocity_px_s: "Peak tangential hand velocity during reach.",
  };

  const CARD_PREVIEW_KEYS = ["sparc", "trunk_ratio", "shoulder_vert_norm", "peak_velocity_px_s"];

  const variables = orderedKinematicVars().map((v) => ({
    group: v.tier === "primary" ? "Primary" : v.tier === "secondary" ? "Secondary" : "Exploratory",
    name: v.label,
    key: v.key,
    unit: v.unit || "—",
    direction: v.dir === "lower" ? "lower" : v.dir === "higher" ? "higher" : "none",
    tip: KIN_TIPS[v.key] || "",
  }));

  const activeResultPhases = phases.filter((ph) => kinematicsResults[ph.k]);
  const kinViewWarning = (() => {
    const lowSparc = activeResultPhases.filter((ph) => kinematicsResults[ph.k]?.sparc_comparable === false);
    if (lowSparc.length) {
      return `Reach amplitude low in ${lowSparc.map((ph) => ph.label).join(", ")} — SPARC may be less reliable`;
    }
    return null;
  })();
  const hasKinTriple =
    kinematicsResults.pre && kinematicsResults.post && kinematicsResults.baseline;
  const recoverySummaryRows = hasKinTriple
    ? RECOVERY_SUMMARY_KEYS.map((key) => {
        const meta = KINEMATIC_VARS.find((v) => v.key === key);
        if (!meta) return null;
        const preV = getMetricValue("pre", key);
        const postV = getMetricValue("post", key);
        const helV = getMetricValue("baseline", key);
        if (!kinCrossPhaseComparable(kinematicsResults, key, analyzedArmForPhase)) return null;
        if (preV === "—" || postV === "—" || helV === "—") return null;
        return {
          key,
          label: meta.label,
          prePost: kinPrePostBadge(preV, postV, meta.dir),
          postHealthy: kinPostHealthyBadge(postV, helV, meta.dir),
        };
      }).filter(Boolean)
    : [];
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
    if (dir === "higher") return { sym: "↑", tip: "↑ زيادة = تحسّن" };
    if (dir === "lower") return { sym: "↓", tip: "↓ نقص = تحسّن" };
    return null;
  };

  const renderKinMetricRow = (metric, idx, prevGroup) => {
    const showGroupHeader = metric.group !== prevGroup;
    const preVal = getMetricValue("pre", metric.key);
    const postVal = getMetricValue("post", metric.key);
    const baselineVal = getMetricValue("baseline", metric.key);
    const kinComparable = kinCrossPhaseComparable(kinematicsResults, metric.key, analyzedArmForPhase);
    const deltaPrePost = kinComparable && preVal !== "—" && postVal !== "—"
      ? kinPrePostBadge(preVal, postVal, metric.direction) : null;
    const deltaPostHealthy = kinComparable && postVal !== "—" && baselineVal !== "—"
      ? kinPostHealthyBadge(postVal, baselineVal, metric.direction) : null;
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
                  Post → Healthy: {deltaPostHealthy.text}
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
        <p className="text-sm font-extrabold text-white/80 mb-3 text-center sm:text-left">Video Upload & Analysis</p>
        <div className="mb-4 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2.5 text-[11px] text-white/55">
          <span className="font-bold text-white/70">Auto arm:</span>{" "}
          The more active arm during the reach is detected and analyzed automatically for each video.
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
                  <AnimatePresence>
                    {status === "analyzing" && <KinPhaseAnalyzingOverlay accent={ph.c} />}
                  </AnimatePresence>
                  <div className={status === "analyzing" ? "invisible" : "flex flex-col items-center justify-center gap-1.5 w-full"}>
                  <input
                      id={`kin-file-${ph.k}`}
                    type="file"
                    accept="video/*,.csv"
                    onChange={(e) => handleFile(ph.k, e.target.files?.[0])}
                      disabled={status === "analyzing"}
                      className="sr-only"
                    />
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
                </div>
                  </label>

                  <div className="mt-auto flex flex-col gap-2">
                    <GBtn variant={ph.c} onClick={() => analyzeVideo(ph.k)} disabled={status === "analyzing" || !data[vidKey(ph.k)]} className="w-full text-xs py-2.5" title="Analyze">
                      {status === "analyzing" ? (
                        <span className="font-bold opacity-70">Analyzing…</span>
                      ) : (
                        <Play className="w-4 h-4 mx-auto" />
                      )}
                  </GBtn>

                  {hasResult && (
                      <div className="flex justify-center gap-1">
                        <GBtn variant="default" onClick={() => downloadFile(ph.k, "csv")} className="!py-1.5 !px-2 min-w-[2.25rem] shrink-0" title="CSV data">
                        <FileSpreadsheet className="w-3.5 h-3.5" />
                      </GBtn>
                        <GBtn variant="default" onClick={() => downloadFile(ph.k, "trc")} className="!py-1.5 !px-2 min-w-[2.25rem] shrink-0" title="OpenSim TRC">
                        <Database className="w-3.5 h-3.5" />
                      </GBtn>
                        <GBtn variant="default" onClick={() => downloadFile(ph.k, "mot")} className="!py-1.5 !px-2 min-w-[2.25rem] shrink-0" title="OpenSim MOT (IK)">
                        <Activity className="w-3.5 h-3.5" />
                      </GBtn>
                        <GBtn variant="default" onClick={() => downloadFile(ph.k, "video")} disabled={!kinematicsResults[ph.k]?.validation_video} className="!py-1.5 !px-2 min-w-[2.25rem] shrink-0" title={kinematicsResults[ph.k]?.validation_video ? "2D Skeleton Video" : "Re-analyze video to generate skeleton overlay"}>
                          <span className="text-[10px] font-bold leading-none">2D</span>
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
                          {expandedResults[ph.k] ? "▲ Hide chart" : "▼ Movement chart"}
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
          {hasKinTriple && recoverySummaryRows.length > 0 && (
            <div className="mb-5 rounded-xl border border-cyan-400/20 bg-cyan-500/5 p-4">
              <p className="text-xs font-extrabold uppercase tracking-widest text-cyan-300/90 mb-1">
                Pre → Post · Post → Healthy
              </p>
              <p className="text-[11px] text-white/45 leading-relaxed mb-3">
                calc_improvement / calc_gap — same formulas as manuscript table.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {recoverySummaryRows.map(({ key, label, prePost, postHealthy }) => (
                  <div key={key} className="rounded-lg border border-white/[0.08] bg-black/20 px-2.5 py-2">
                    <p className="text-[9px] font-bold text-white/45 leading-tight">{label}</p>
                    <p className={`text-sm font-mono font-extrabold mt-1 ${prePost?.colorClass?.split(" ")[0] || "text-white/80"}`}>
                      {prePost?.text || "—"}
                    </p>
                    <p className={`text-sm font-mono font-extrabold mt-0.5 ${postHealthy?.colorClass?.split(" ")[0] || "text-white/70"}`}>
                      {postHealthy?.text || "—"}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="flex items-center justify-between mb-3 gap-2">
            <p className="text-sm font-extrabold text-white/80">Kinematic Results</p>
            <GBtn variant="danger" onClick={clearAllKin} className="text-[10px] py-1.5 px-3 flex-shrink-0" title="Remove all results">
              <X className="w-3 h-3 mr-1" />
              Clear All
            </GBtn>
          </div>
          {kinViewWarning && (
            <div className="mb-3 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2.5 text-[11px] text-amber-100/90">
              {kinViewWarning}
            </div>
          )}

          {/* Mobile / tablet — tabs + vertical cards (no horizontal swipe) */}
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

          {/* Desktop — full comparison table */}
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

                  const deltaPrePost = kinComparable && preVal !== "—" && postVal !== "—"
                    ? kinPrePostBadge(preVal, postVal, metric.direction)
                    : null;

                  const deltaPostHealthy = kinComparable && postVal !== "—" && baselineVal !== "—"
                    ? kinPostHealthyBadge(postVal, baselineVal, metric.direction)
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
                                ▸ {metric.tip}
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
                              <span className={`px-2.5 py-1 text-xs font-bold rounded-lg border ${deltaPrePost.colorClass}`}>
                                {deltaPrePost.text}
                              </span>
                            ) : (
                              <span className="text-white/20 text-xs">—</span>
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
                              <span className="text-white/20 text-xs">—</span>
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
                      <td className="px-2 py-2.5 text-center text-white/20 text-xs">—</td>
                    )}
                    {kinematicsResults.pre && kinematicsResults.post && (
                      <td className="px-2 py-2.5 text-center text-white/20 text-xs">—</td>
                    )}
                    {hasKinTriple && (
                      <td className="px-2 py-2.5 text-center text-white/20 text-xs">—</td>
                    )}
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Glass>
      )}

      {Object.keys(kinematicsResults).filter(k => kinematicsResults[k]?.velocity_profile).length >= 1 && (
        <Glass className="p-4 sm:p-5">
          <p className="text-sm font-extrabold text-white/80 mb-3">Combined Velocity Profile / Birleşik Hız Profili</p>
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

      {/* In-app video viewer — stay inside PWA on iOS/iPad */}
      <AnimatePresence>
        {mediaPreview && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[99998] flex flex-col bg-black/95 backdrop-blur-sm"
            onClick={() => setMediaPreview(null)}
          >
            <div className="flex items-center justify-between px-4 py-3 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
              <p className="text-sm font-bold text-white/80 truncate">{mediaPreview.title}</p>
              <GBtn variant="default" onClick={() => setMediaPreview(null)} className="!py-1.5 !px-3 text-xs shrink-0">
                <X className="w-4 h-4 mr-1" /> Close
              </GBtn>
            </div>
            <div className="flex-1 flex items-center justify-center px-3 pb-6 min-h-0" onClick={(e) => e.stopPropagation()}>
              <video
                key={mediaPreview.url}
                src={mediaPreview.url}
                controls
                playsInline
                autoPlay
                className="w-full max-h-full rounded-xl bg-black"
                style={{ maxHeight: "calc(100dvh - 5rem)" }}
                onError={() => {
                  showToast("Could not load validation video — try re-analyzing the video", "error");
                  setMediaPreview(null);
                }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
};

// ─── Patient Database ─────────────────────────────────────────────────────────

const DatabaseSection = ({ fd, setFd, onLoadSession, showToast, isActive }) => {
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState("");
  const [confirm, setConfirm] = useState(null);
  const [syncing, setSyncing] = useState(false);

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

  const filtered = patients.filter((p) => {
    const q = search.toLowerCase();
    return (
      (p.demographics?.name || "").toLowerCase().includes(q) ||
      (p.demographics?.participantId || "").toLowerCase().includes(q)
    );
  });

  const deletePatient = (id) => {
    const updated = patients.filter((p) => p._id !== id);
    savePatients(updated);
    setPatients(updated);
    setConfirm(null);
    showToast("Patient record deleted");
    postPatientsSync(updated).catch(() => {});
  };

  return (
    <div className="space-y-5">
      <SH icon={Database} en="Patient Database" tr="Hasta Veritabanı" badge={`${patients.length} Records`} />

      <Glass className="p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex-1 min-w-0 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or Participant ID…"
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
                    setFd((prev) => ({ ...prev, ...cur }));
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
        </div>
      </Glass>

      {filtered.length === 0 ? (
        <Glass className="p-12 text-center">
          <Database className="w-16 h-16 text-white/10 mx-auto mb-4" />
          <p className="text-white/50 font-semibold text-lg mb-2">
            {search ? "No patients match your search" : "No patient records yet"}
          </p>
          <p className="text-white/25 text-sm">Save a session from any assessment tab, then tap Sync to share across devices.</p>
        </Glass>
      ) : (
        <div className="space-y-3">
          {filtered.map((p) => {
            const d = p.demographics || {};
            const hasPre = !!p._hasPre;
            const hasPost = !!p._hasPost;

            return (
              <Glass key={p._id} className="p-4">
                <div className="flex items-start gap-4 flex-wrap">
                  <div className="w-10 h-10 rounded-xl bg-violet-500/20 border border-violet-400/20 flex items-center justify-center flex-shrink-0">
                    <User className="w-5 h-5 text-violet-300" />
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
                      {d.sex && <span>· {d.sex === "1" ? "Male" : "Female"}</span>}
                      {d.strokeType && <span>· {d.strokeType === "1" ? "Ischemic" : "Hemorrhagic"}</span>}
                      {d.side && <span>· {d.side === "1" ? "Left" : "Right"} side</span>}
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-[9px] font-bold px-2 py-1 rounded-full border ${
                        hasPre ? "bg-sky-500/20 border-sky-400/30 text-sky-300" : "bg-white/[0.05] border-white/[0.04] text-white/25"
                      }`}>
                        {hasPre ? "✓ Pre-Assessment" : "○ Pre missing"}
                      </span>

                      <span className={`text-[9px] font-bold px-2 py-1 rounded-full border ${
                        hasPost ? "bg-emerald-500/20 border-emerald-400/30 text-emerald-300" : "bg-white/[0.05] border-white/[0.04] text-white/25"
                      }`}>
                        {hasPost ? "✓ Post-Assessment" : "○ Post missing"}
                      </span>

                      <span className="text-[9px] text-white/25 ml-auto">Saved: {new Date(p._savedAt).toLocaleString()}</span>
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0 flex-wrap mt-3">
                      <GBtn variant="sky" onClick={() => onLoadSession(p)} className="text-xs px-3 py-2">
                        <Edit3 className="w-3.5 h-3.5" /> Load / Edit
                      </GBtn>

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
          })}
        </div>
      )}
    </div>
  );
};

// ─── Report Helpers ───────────────────────────────────────────────────────────

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
    if (isNaN(p) || isNaN(q)) return "—";
    const d = q - p;
    if (d === 0) return "0.00";
    return (d > 0 ? "+" : "") + d.toFixed(2);
  };

  const v = (x) => (x !== undefined && x !== null && x !== "" ? String(x) : "—");

  // VAS
  const vas = fd.vas || {};
  [
    { k:"rest", en:"Pain at Rest" },
    { k:"activity", en:"Pain During Activity" },
    { k:"night", en:"Night Pain" },
  ].forEach((item) => {
    const pre = v(vas[item.k]?.pre);
    const post = v(vas[item.k]?.post);
    const pNum = parseFloat(pre), qNum = parseFloat(post);
    const improving = (pre !== "—" && post !== "—")
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
    const improving = (pre !== "—" && post !== "—")
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
      pre: item.phase === "pre" ? val : "—",
      post: item.phase === "post" ? val : "—",
      delta:"—"
    });
  });

  // KVIQ
  const kgia = fd.kgia || {};
  KGIA_MOVEMENTS.forEach((mov, mi) =>
    KGIA_TYPES.forEach((t) => {
      const pre = v(kgia[`${mi}_${t.key}`]?.once);
      const post = v(kgia[`${mi}_${t.key}`]?.sonra);
      const improving = (pre !== "—" && post !== "—") ? (parseFloat(pre) === parseFloat(post) ? null : parseFloat(post) > parseFloat(pre)) : null;
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

    const improvingT = (preT !== "—" && postT !== "—") ? (parseFloat(preT) === parseFloat(postT) ? null : parseFloat(preT) > parseFloat(postT)) : null;
    const improvingR = (preR !== "—" && postR !== "—") ? (parseFloat(preR) === parseFloat(postR) ? null : parseFloat(postR) > parseFloat(preR)) : null;
    rows.push({ tool:"WMFT", metric:`${t.en} — Time (sec)`, pre:preT, post:postT, delta:calcDelta(preT, postT), improving: improvingT });
    rows.push({ tool:"WMFT", metric:`${t.en} — Ability Rating (0–5)`, pre:preR, post:postR, delta:calcDelta(preR, postR), improving: improvingR });
  });

  // Kinematics
  let kin = fd.kinematics || {};
  if (!kin.pre && !kin.post) {
    try { const kr = JSON.parse(localStorage.getItem(KIN_LS_KEY)) || {}; kin = { pre: kr.pre, post: kr.post }; } catch {}
  }
  const kinDisplay = orderedKinematicVars().map((v) => ({
    k: v.key,
    en: v.label,
    dir: v.dir,
  }));
  kinDisplay.forEach((item) => {
    const pre = v(kin.pre?.[item.k]);
    const post = v(kin.post?.[item.k]);
    const pNum = parseFloat(pre), qNum = parseFloat(post);
    const improving = (pre !== "—" && post !== "—")
      ? (pNum === qNum ? null : (item.dir === "lower" ? pNum > qNum : qNum > pNum))
      : null;
    rows.push({ tool:"Kinematics", metric:item.en, pre, post, delta:calcDelta(pre, post, item.en), improving });
  });

  return rows;
}

// ─── SPSS Export Helper ───────────────────────────────────────────────────────

function buildSPSSData(fd) {
  const row = buildMasterRow(fd, WMFT_ITEMS, KGIA_MOVEMENTS, IPAQ_ACTS);
  return row ? [row] : [];
}

// ─── Report Section ───────────────────────────────────────────────────────────

const ReportSection = ({ fd, onChange, showToast }) => {
  const d = fd.demographics || {};
  const rows = buildSummaryRows(fd);
  const tools = Array.from(new Set(rows.map((r) => r.tool)));
  const kinRows = Array.isArray(fd.kinematics?.uploadedData) ? fd.kinematics.uploadedData : [];
  const kinCharts = Array.isArray(fd.kinematics?.chartImages) ? fd.kinematics.chartImages : [];

  // Build kinematics data from video analysis results
  const buildVideoKinRows = () => {
    let kr;
    try { kr = JSON.parse(localStorage.getItem(KIN_LS_KEY)) || {}; } catch { kr = {}; }
    if (Object.keys(kr).length === 0) return null;
    const phaseLabels = { pre: "Pre", post: "Post", baseline: "Healthy side" };
    const vars = orderedKinematicVars().map((v) => ({
      key: v.key,
      label: `${v.label}${v.dir === "higher" ? " ↑" : v.dir === "lower" ? " ↓" : ""}`,
      unit: v.unit === "count" ? "" : v.unit,
      dir: v.dir,
    }));
    const phases = ["pre", "post", "baseline"].filter((p) => kr[p]);
    if (phases.length === 0) return null;

    const headers = ["Variable", "Unit", ...phases.map((p) => phaseLabels[p] || p)];
    const body = vars.map((v) => {
      const row = [v.label, v.unit];
      phases.forEach((p) => {
        const val = kr[p]?.[v.key];
        row.push(val != null ? (typeof val === "number" ? val.toFixed(2) : String(val)) : "—");
      });
      return row;
    });
    return { headers, body, varMeta: vars, phases };
  };

  const kinDirectionMap = (name) => {
    const n = (name || "").toLowerCase();
    if (n.includes("pause")) return "lower";
    if (n.includes("nsub")) return "lower";
    if (n.includes("sparc")) return "higher";
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
    if (isNaN(p) || isNaN(q)) return "—";
    const delta = q - p;
    return (delta >= 0 ? "+" : "") + delta.toFixed(2);
  };

  const toolColor = {
    VAS: "text-sky-300 bg-sky-500/10 border-sky-400/20",
    VAMS: "text-indigo-300 bg-indigo-500/10 border-indigo-400/20",
    "Muscle Control": "text-teal-300 bg-teal-500/10 border-teal-400/20",

    KVIQ: "text-cyan-300 bg-cyan-500/10 border-cyan-400/20",
    WMFT: "text-amber-300 bg-amber-500/10 border-amber-400/20",
    Kinematics: "text-rose-300 bg-rose-500/10 border-rose-400/20",
  };

  // ── Glassmorphism HTML Report (print → PDF) ──
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
        const preVal = trows.find(r => r.pre !== "—")?.pre;
        const postVal = trows.find(r => r.post !== "—")?.post;
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
          const items = trows.filter(r => r.delta !== "—" && r.delta !== "\u2014" && r.pre !== "—" && r.post !== "—");
          if (!items.length) return;
          const parts = items.map(r => {
            const p = parseFloat(r.pre), q = parseFloat(r.post);
            const d = q - p;
            const trend = trendWord(-d, "decreased (improvement)", "increased (worsening)");
            return `${esc(r.metric)} went from ${r.pre} to ${r.post} (Δ${r.delta}), indicating pain ${trend}`;
          });
          sections.push(`<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0"><strong style="color:#0d9488">Pain Scale (VAS):</strong> ${parts.join("; ")}.</p>`);
          return;
        }

        if (tool === "VAMS") {
          const items = trows.filter(r => r.delta !== "—" && r.delta !== "\u2014" && r.pre !== "—" && r.post !== "—");
          if (!items.length) return;
          const positive = ["Happy","Calm"]; const negative = ["Sad","Tense"];
          const posItems = items.filter(r => positive.some(n => r.metric.includes(n)));
          const negItems = items.filter(r => negative.some(n => r.metric.includes(n)));
          const parts = [];
          if (posItems.length) {
            const trends = posItems.map(r => `${r.pre}→${r.post} (Δ${r.delta})`).join(", ");
            parts.push(`positive moods (${trends})`);
          }
          if (negItems.length) {
            const trends = negItems.map(r => `${r.pre}→${r.post} (Δ${r.delta})`).join(", ");
            parts.push(`negative moods (${trends})`);
          }
          sections.push(`<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0"><strong style="color:#0ea5e9">Mood Scale (VAMS-4):</strong> ${parts.join("; ")}.</p>`);
          return;
        }

        if (tool === "Muscle Control") {
          const preRow = trows.find(r => r.pre !== "—");
          const postRow = trows.find(r => r.post !== "—");
          const preVal = preRow?.pre, postVal = postRow?.post;
          if (!preVal || !postVal) return;
          const d = parseFloat(postVal) - parseFloat(preVal);
          const trend = trendWord(d, "improved", "declined");
          sections.push(`<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0"><strong style="color:#10b981">Muscle Control:</strong> The participant's perceived muscle control changed from ${preVal} to ${postVal} (Δ${d > 0 ? "+" : ""}${d.toFixed(2)}), indicating the feeling of control has ${trend}.</p>`);
          return;
        }

        if (tool === "KVIQ") {
          const items = trows.filter(r => r.delta !== "—" && r.delta !== "\u2014" && r.pre !== "—" && r.post !== "—");
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
          const items = trows.filter(r => r.delta !== "—" && r.delta !== "\u2014" && r.pre !== "—" && r.post !== "—");
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

        if (tool === "Kinematics") {
          const items = trows.filter(r => r.delta !== "—" && r.delta !== "\u2014" && r.pre !== "—" && r.post !== "—");
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
      const hasData = trows.some(r => r.pre !== "—" || r.post !== "—");
      if (!hasData) return;
      const meta = toolMeta[tool] || { label: tool, color: "#0d9488" };
      const interp = buildToolInterp(tool, trows);
      let body;
      if (tool === "Muscle Control") {
        const preRow = trows.find(r => r.pre !== "—");
        const postRow = trows.find(r => r.post !== "—");
        const preVal = preRow ? preRow.pre : "—";
        const postVal = postRow ? postRow.post : "—";
        const delta = preVal !== "—" && postVal !== "—"
          ? (parseFloat(postVal) - parseFloat(preVal)).toFixed(2)
          : "—";
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
    let kr2; try { kr2 = JSON.parse(localStorage.getItem(KIN_LS_KEY)) || {}; } catch { kr2 = {}; }
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
            const badge = kinPrePostBadge(preVal, postVal, dir);
            prePostHtml = `<td class="num">${esc(badge?.text || "—")}</td>`;
          } else {
            prePostHtml = '<td class="num">—</td>';
          }
        }
        if (postIdx >= 0 && healthyIdx >= 0) {
          const postVal = parseFloat(row[postIdx]);
          const helVal = parseFloat(row[healthyIdx]);
          if (!isNaN(postVal) && !isNaN(helVal)) {
            const badge = kinPostHealthyBadge(postVal, helVal, dir);
            postHealthyHtml = `<td class="num">${esc(badge?.text || "—")}</td>`;
          } else {
            postHealthyHtml = '<td class="num">—</td>';
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
          const impLabel = imp > total / 2 ? "Most kinematic metrics improved" : imp > 0 ? "Some kinematic metrics improved" : "No kinematic improvement";
          videoInterp = `<div class="tool-interp">${impLabel} (${imp} improved, ${wors} worsened, ${total - imp - wors} stable)</div>`;
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
      if (highDays >= 3 && ipaqTotalMET >= 1500) { clsLevel="High"; clsColor="#10b981"; clsText="Vigorous activity ≥3 days & ≥1500 MET-min/week"; }
      else if ((medDays+lightDays) >= 7 && ipaqTotalMET >= 3000) { clsLevel="High"; clsColor="#10b981"; clsText="Mixed activities 7 days & ≥3000 MET-min/week"; }
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
      (fmtNotes ? '<p style="font-size:11px;color:#334155;margin:0 0 4px"><strong style="color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">Clinical Notes / Klinik Notlar:</strong><br><div style="margin-top:4px;white-space:pre-wrap">' + fmtNotes + '</div></p>' : "") +
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
    <div><h1>${d.group === "1" ? "AOMI Group / AOMI Grubu" : "Control Group / Kontrol Grubu"}</h1><div class="sub">Clinical Assessment Report / Klinik Değerlendirme Raporu</div></div>
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
      alert("✓ Report downloaded — open the file and print to PDF");
    } else {
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    }
    } catch (e) { alert("Report error: " + e.message); } };

  // ── PDF Export (jsPDF fallback) ──
  const exportPDF = () => {
    const doc = new jsPDF({ orientation:"portrait", unit:"mm", format:"a4" });

    // ── Design tokens (GlassCard style) ────────────────────────────
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

    // ── Helpers ────────────────────────────────────────────────────
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

    // ── Page 1: background ────────────────────────────────────────
    drawPageBg();

    // Glass header card
    let y = 14;
    rr(M, y, CW, 22, R, C.white, C.gray200);
    rr(M + 2, y + 2, 4, 18, 2, C.teal, null);
    txt("Stroke Rehabilitation Research Platform", M + 10, y + 8, 12, true, C.gray900);
    txt("Clinical Assessment Report", M + 10, y + 14, 8, false, C.gray500);
    txt(new Date().toLocaleDateString("en-GB", {day:"2-digit",month:"short",year:"numeric"}), W - M - 10, y + 8, 7.5, false, C.gray500, "right");
    txt(d.name || "Participant", W - M - 10, y + 14, 7.5, false, C.gray500, "right");

    // ── Patient Card (GlassCard style) ─────────────────────────────
    y = 42;
    rr(M, y, CW, 32, R, C.white, C.gray200);
    rr(M + 2, y + 2, 4, 28, 2, C.teal, null);

    txt(d.name || "—", M + 10, y + 9, 13, true, C.gray900);
    txt(d.participantId ? `ID: ${d.participantId}` : "", M + 10, y + 15, 7.5, false, C.gray500);

    const demoGrid = [
      ["Age",        d.age ? `${d.age} yrs` : "—"],
      ["Sex",        d.sex === "1" ? "Male" : d.sex === "2" ? "Female" : "—"],
      ["Stroke",     d.strokeType === "1" ? "Ischemic" : d.strokeType === "2" ? "Hemorrhagic" : "—"],
      ["Side",       d.side === "1" ? "Left" : d.side === "2" ? "Right" : "—"],
      ["TSS",        d.timeSinceStroke ? `${d.timeSinceStroke}m` : "—"],
      ["MAS",        d.mas || "—"],
      ["MRC",        d.mrc || "—"],
    ];
    const colW = CW / 4;
    demoGrid.forEach((item, i) => {
      const cx = M + 5 + (i % 4) * colW;
      const cy = y + (i < 4 ? 21 : 28);
      txt(item[0], cx, cy, 6, false, C.gray500);
      txt(item[1], cx, cy + 4, 7, true, C.gray700);
    });

    y = 80;

    // ── Per-tool sections (GlassCard style) ───────────────────────
    const toolConfig = {
      "VAS":          { label: "Pain Scale (VAS)",          color: C.rose  },
      "VAMS":         { label: "Mood Scale (VAMS-4)",        color: C.violet},
      "Muscle Control":{ label: "Muscle Control Scale",      color: C.amber },
      "KVIQ":         { label: "Motor Imagery (KVIQ)",       color: C.teal  },
      "WMFT":         { label: "Wolf Motor Function (WMFT)", color: C.cyan  },
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
            if (delta && delta !== "—") {
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

    // ── Video Kinematics ──────────────────────────────────────────
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

    // ── Velocity profiles (combined chart) ────────────────────────
    let kr2;
    try { kr2 = JSON.parse(localStorage.getItem(KIN_LS_KEY)) || {}; } catch { kr2 = {}; }
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

    // ── Footer on each page ───────────────────────────────────────
    const totalPages = doc.getNumberOfPages();
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i);
      doc.setDrawColor(...C.gray300); doc.setLineWidth(0.3);
      doc.line(M, 285, W - M, 285);
      txt(`Stroke Rehab Platform  |  Confidential  |  Page ${i} of ${totalPages}`, W / 2, 290, 6.5, false, C.gray500, "center");
    }

    doc.save(`report_${d.participantId || d.name || "participant"}_${new Date().toISOString().split("T")[0]}.pdf`);
  };

  // ── Excel Export ──
  const exportExcel = () => {
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
      ["Tool", "Metric / Task", "Pre-Assessment", "Post-Assessment", "Δ Change"],
      ...rows.map((r) => [
        r.tool,
        r.metric,
        r.pre === "—" ? "" : r.pre,
        r.post === "—" ? "" : r.post,
        r.delta === "—" ? "" : r.delta,
      ]),
    ]);
    ws2["!cols"] = [{ wch: 20 }, { wch: 55 }, { wch: 18 }, { wch: 18 }, { wch: 12 }];
    XLSX.utils.book_append_sheet(wb, ws2, "Clinical Summary");

    // Sheet 3: VAS
    const vas = fd.vas || {};
    const vasSheet = [["Metric", "Pre (0-10)", "Post (0-10)", "Δ"]];
    [
      { k:"rest", en:"Pain at Rest" },
      { k:"activity", en:"Pain During Activity" },
      { k:"night", en:"Night Pain" },
    ].forEach((item) => vasSheet.push([item.en, vas[item.k]?.pre || "", vas[item.k]?.post || "", ""]));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(vasSheet), "VAS");

    // Sheet 4: VAMS-4
    const vams = fd.vams || {};
    const vamsSheet = [["Metric", "Pre (0-10)", "Post (0-10)", "Δ"]];
    [
      { k:"happy", en:"Happy" },
      { k:"sad", en:"Sad" },
      { k:"calm", en:"Calm" },
      { k:"tense", en:"Tense" },
    ].forEach((item) => vamsSheet.push([item.en, vams[item.k]?.pre || "", vams[item.k]?.post || "", ""]));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(vamsSheet), "VAMS-4");

    // Sheet 5: KVIQ
    const kgia = fd.kgia || {};
    const kviqSheet = [["#", "Movement", "Type", "Pre (1-5)", "Post (1-5)", "Δ"]];
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

    // Sheet 7: Kinematics (if uploaded)
    if (kinRows.length > 0) {
      XLSX.utils.book_append_sheet(
        wb,
        XLSX.utils.aoa_to_sheet([
          ["Variable", "Unit", "Pre", "Post", "Δ"],
          ...kinRows.map((r) => [r.name || "", r.unit || "", r.pre || "", r.post || "", calcKinDelta(r.pre, r.post)]),
        ]),
        "Kinematics"
      );
    }

    XLSX.writeFile(wb, `research_data_${d.participantId || "participant"}_${new Date().toISOString().split("T")[0]}.xlsx`);
  };

  // ── SPSS Export (all patients, split by group + demo/assess/full) ──
  const exportSPSS = () => {
    const allPts = loadPatients();
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

    const aomi = masterRows.filter((r) => r.Group === "1");
    const ctrl = masterRows.filter((r) => r.Group === "2");
    const demoKeys = ["ID","Group","Age","Sex","TimeSinceStroke","StrokeType","AffectedSide","MAS","MRC"];
    const assessKeys = Object.keys(masterRows[0]).filter((k) => k !== "ID" && !demoKeys.includes(k));
    const pick = (row, keys) => keys.reduce((o, k) => ({ ...o, [k]: row[k] }), {});

    toCsv("aomi_full.csv", aomi.map((r) => pick(r, ["ID", ...demoKeys.slice(1), ...assessKeys])));
    toCsv("control_full.csv", ctrl.map((r) => pick(r, ["ID", ...demoKeys.slice(1), ...assessKeys])));

    setTimeout(() => downloadBlob(
      new Blob(["\uFEFF" + generateStudySPSSSyntax("master_study_data.csv")], { type: "text/plain;charset=utf-8" }),
      "neuro_study_analysis.sps"
    ), count * 400);

    showToast(`✓ Exported master CSV + group files + SPSS syntax`);
  };

  // ── JSON Export (all patients) ──
  const exportJSON = () => {
    const allPts = loadPatients();
    if (allPts.length === 0) { return; }
    const clean = allPts.map(({ _id, _savedAt, _hasPre, _hasPost, ...rest }) => rest);
    const blob = new Blob([JSON.stringify(clean, null, 2)], { type: "application/json" });
    downloadBlob(blob, `neuro_data_${allPts.length}patients_${new Date().toISOString().split("T")[0]}.json`);
  };

  // ── SPSS Syntax (.sps) export — full study analysis workflow ──
  const exportSPSSyntax = () => {
    const syn = generateStudySPSSSyntax("master_study_data.csv");
    const blob = new Blob(["\uFEFF" + syn], { type: "text/plain;charset=utf-8" });
    downloadBlob(blob, "neuro_study_analysis.sps");
    showToast("✓ SPSS syntax downloaded (neuro_study_analysis.sps)");
  };

  return (
    <div className="space-y-5">
      <SH icon={FileText} en="Clinical Report & Export" tr="Klinik Rapor ve Dışa Aktarma" />

      {d.name && (
        <Glass className="p-4 border-l-2 border-violet-400/40">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="w-10 h-10 rounded-xl bg-violet-500/20 border border-violet-400/20 flex items-center justify-center flex-shrink-0">
              <User className="w-5 h-5 text-violet-300" />
            </div>

            <div className="min-w-0">
              <p className="font-extrabold text-white text-sm">{d.name}</p>
              <p className="text-xs text-white/40 truncate">
                {d.participantId} · {d.age} yrs · {d.strokeType} · {d.side} side
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
              <p className="text-sm font-extrabold text-white/90">Clinical Notes / Klinik Notlar</p>
              <p className="text-xs font-light text-white/40 mt-0.5">Medical history, medications, and clinician observations</p>
            </div>
          </div>
          <div className="space-y-3">
            {d.antispasticDrugs && (
              <div className="glass-float bg-white/[0.09] border border-white/12 rounded-xl px-4 py-2.5">
                <p className="text-[10px] font-extrabold text-white/40 uppercase tracking-widest mb-1">Antispastic Drugs / Antispastik İlaçlar</p>
                <p className="text-sm text-white/80 font-medium">{d.antispasticDrugs}</p>
              </div>
            )}
            {d.otherDrugs && (
              <div className="glass-float bg-white/[0.09] border border-white/12 rounded-xl px-4 py-2.5">
                <p className="text-[10px] font-extrabold text-white/40 uppercase tracking-widest mb-1">Other Medications / Diğer İlaçlar</p>
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
                <p className="text-xs font-light text-white/40 mt-0.5">Uluslararası Fiziksel Aktivite Anketi</p>
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
              if (highDays >= 3 && totalMET >= 1500) cls = { level:"High", color:"emerald", text:"Vigorous activity ≥3 days & ≥1500 MET-min/week" };
              else if ((medDays + lightDays) >= 7 && totalMET >= 3000) cls = { level:"High", color:"emerald", text:"Mixed activities 7 days & ≥3000 MET-min/week" };
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
            <p className="text-xs font-light text-white/40 mt-0.5">All assessment tools · Pre vs Post results · Auto-calculated Δ</p>
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
                      <th className="text-center px-3 py-2.5 text-xs font-extrabold text-amber-300 uppercase">Δ Change</th>
                    </tr>
                  </thead>

                  <tbody>
                    {tool === "Muscle Control" ? (() => {
                      const preRow = toolRows.find(r => r.pre !== "—");
                      const postRow = toolRows.find(r => r.post !== "—");
                      const preVal = preRow ? preRow.pre : "—";
                      const postVal = postRow ? postRow.post : "—";
                      const delta = preVal !== "—" && postVal !== "—" ? (parseFloat(postVal) - parseFloat(preVal)).toFixed(2) : "—";
                      const imp = preVal !== "—" && postVal !== "—" ? (parseFloat(postVal) > parseFloat(preVal) ? true : parseFloat(postVal) < parseFloat(preVal) ? false : null) : null;
                      return (
                        <tr className="border-b border-white/[0.05] bg-white/[0.02]">
                          <td className="px-4 py-2.5 text-xs text-white/75 font-medium">Felt Difference</td>
                          <td className="px-3 py-2.5 text-center"><span className="px-2.5 py-1 rounded-lg border bg-sky-500/10 border-sky-400/20 text-sky-200 text-xs font-bold">{preVal}</span></td>
                          <td className="px-3 py-2.5 text-center"><span className="px-2.5 py-1 rounded-lg border bg-emerald-500/10 border-emerald-400/20 text-emerald-200 text-xs font-bold">{postVal}</span></td>
                          <td className="px-3 py-2.5 text-center"><span className={`px-2.5 py-1 rounded-lg text-xs font-extrabold border ${delta === "—" ? "text-white/25 bg-white/[0.03] border-white/[0.06]" : imp === true ? "text-emerald-300 bg-emerald-500/20 border-emerald-400/30" : imp === false ? "text-rose-300 bg-rose-500/20 border-rose-400/30" : "text-white/40 bg-white/[0.05] border-white/[0.08]"}`}>{delta}</span></td>
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
                            <td className="px-3 py-2.5 text-center"><span className={`px-2.5 py-1 rounded-lg text-xs font-extrabold border ${dVal === "—" ? "text-white/25 bg-white/[0.03] border-white/[0.06]" : imp === true ? "text-emerald-300 bg-emerald-500/20 border-emerald-400/30" : imp === false ? "text-rose-300 bg-rose-500/20 border-rose-400/30" : "text-white/40 bg-white/[0.05] border-white/[0.08]"}`}>{dVal}</span></td>
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
                      <td className="px-3 py-2.5 text-center text-xs text-white/40">{r.unit || "—"}</td>

                      <td className="px-3 py-2.5 text-center">
                        <span className="px-2.5 py-1 rounded-lg border bg-sky-500/10 border-sky-400/20 text-sky-200 text-xs font-bold">
                          {r.pre || "—"}
                        </span>
                      </td>

                      <td className="px-3 py-2.5 text-center">
                        <span className="px-2.5 py-1 rounded-lg border bg-emerald-500/10 border-emerald-400/20 text-emerald-200 text-xs font-bold">
                          {r.post || "—"}
                        </span>
                      </td>

                      <td className="px-3 py-2.5 text-center">
                        <span
                          className={`px-2.5 py-1 rounded-lg text-xs font-extrabold border ${
                            (() => {
                              const d = calcKinDelta(r.pre, r.post);
                              if (d === "—") return "text-white/25 bg-white/[0.03] border-white/[0.06]";
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
                        const badge = kinPrePostBadge(preVal, postVal, dir);
                        prePostHtml = (
                          <span className={`px-2.5 py-1 rounded-lg border text-xs font-extrabold ${badge?.colorClass || "text-white/40 bg-white/[0.05] border-white/[0.08]"}`}>
                            {badge?.text || "—"}
                          </span>
                        );
                      }
                    }
                    if (postIdx >= 0 && healthyIdx >= 0) {
                      const postVal = parseFloat(row[postIdx]);
                      const helVal = parseFloat(row[healthyIdx]);
                      if (!isNaN(postVal) && !isNaN(helVal)) {
                        const badge = kinPostHealthyBadge(postVal, helVal, dir);
                        postHealthyHtml = (
                          <span className={`px-2.5 py-1 rounded-lg border text-xs font-extrabold ${badge?.colorClass || "text-white/40 bg-white/[0.05] border-white/[0.08]"}`}>
                            {badge?.text || "—"}
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
                          <td className="px-3 py-2.5 text-center">{prePostHtml || <span className="text-white/25 text-xs">—</span>}</td>
                        )}
                        {postIdx >= 0 && healthyIdx >= 0 && (
                          <td className="px-3 py-2.5 text-center">{postHealthyHtml || <span className="text-white/25 text-xs">—</span>}</td>
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
            whileTap={{ scale: 0.98 }}
            onClick={exportGlassReport}
            className="flex flex-col gap-3 p-5 rounded-xl bg-rose-500/10 border border-rose-400/25 hover:bg-rose-500/15 hover:border-rose-400/40 transition-all text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-400/30 flex items-center justify-center flex-shrink-0">
                <FileText className="w-5 h-5 text-rose-300" />
              </div>
              <div>
                <p className="font-extrabold text-rose-200 text-sm">Download PDF</p>
                <p className="text-[10px] text-rose-300/60">Glassmorphism Report → Print/Save PDF</p>
              </div>
            </div>
            <p className="text-xs text-white/45 leading-relaxed">
              Opens a styled report; use the print dialog to Save as PDF (enable "Background graphics").
            </p>
          </motion.button>

          {/* SPSS */}
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            onClick={exportSPSS}
            className="flex flex-col gap-3 p-5 rounded-xl bg-violet-500/10 border border-violet-400/25 hover:bg-violet-500/15 hover:border-violet-400/40 transition-all text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-violet-500/20 border border-violet-400/30 flex items-center justify-center flex-shrink-0">
                <Database className="w-5 h-5 text-violet-300" />
              </div>
              <div>
                <p className="font-extrabold text-violet-200 text-sm">Export SPSS CSVs</p>
                <p className="text-[10px] text-violet-300/60">AOMI + Control · Demo / Assess / Full</p>
              </div>
            </div>
            <p className="text-xs text-white/45 leading-relaxed">
              6 CSV files (AOMI & Control groups × demographics / assessments / full). Ready for SPSS.
            </p>
          </motion.button>

          {/* JSON */}
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
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
            whileTap={{ scale: 0.98 }}
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

// ─── Analysis Dashboard ───────────────────────────────────────────────────────────

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

  const pts = loadPatients();
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
    const id = d.participantId || "?";
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

  const downloadSpssSyntax = () => {
    downloadBlob(
      new Blob(["\uFEFF" + generateStudySPSSSyntax("master_study_data.csv")], { type: "text/plain;charset=utf-8" }),
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
      <SH icon={BarChart3} en="Analysis Dashboard" tr="Analiz Paneli" badge="RCT v6" />

      <div className="flex flex-wrap gap-2">
        <TabBtn id="plan" label="Analysis Plan" />
        <TabBtn id="results" label="Results Preview" />
        <TabBtn id="export" label="SPSS Export" />
        <TabBtn id="thesis" label="Thesis Docs" />
      </div>

      {/* Enrollment — always visible */}
      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Enrollment / Kayıt (target n={STUDY_DESIGN.targetN})</p>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[
            { label: "Total", val: n, color: "text-white" },
            { label: "AOMI", val: aomi.length, color: "text-teal-300" },
            { label: "Control", val: ctrl.length, color: "text-rose-300" },
            { label: "Kin complete", val: kinComplete, color: "text-sky-300" },
            { label: "Ready for ANOVA", val: rows.length >= 8 && aomi.length >= 2 && ctrl.length >= 2 ? "✓" : "—", color: "text-amber-300" },
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
                placeholder={auto != null ? String(auto) : "—"}
                onChange={(e) => saveConsort({ [k]: e.target.value === "" ? "" : parseInt(e.target.value, 10) })}
              />
              {auto != null && <p className="text-[9px] text-white/30 mt-1">Auto: {auto}</p>}
            </div>
          ))}
        </div>
        <p className="text-[10px] text-white/35">Healthy baseline collected: {healthyComplete} · LOCF export: {locfExport ? "on" : "off"}</p>
      </Glass>

      {tab === "plan" && (
        <>
          <Glass className="p-5">
            <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-3">Study Design</p>
            <p className="text-sm text-white/70 leading-relaxed mb-4">{STUDY_DESIGN.design} · Primary: <strong className="text-violet-300">{STUDY_DESIGN.primaryOutcome}</strong> · α={STUDY_DESIGN.alpha}</p>
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
            <p className="text-[10px] text-white/35 mt-4">Full document: STUDY_ANALYSIS_PLAN.md in NeuroLab folder</p>
          </Glass>
        </>
      )}

      {tab === "results" && (
        <>
          <Glass className="p-5">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div>
                <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest">Preliminary 2×2 Analysis</p>
                <p className="text-[10px] text-amber-400/80 font-bold mt-1">Δ between groups ≈ Group×Time interaction · Confirm in SPSS GLM</p>
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
                    <th className="text-center px-2 py-2 text-emerald-200">Normal?</th>
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
                    const fmtM = (s) => s ? `${s.mean}±${s.sd}` : "—";
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
                          {norm ? (norm.normal ? <span className="text-emerald-400" title={`skew=${norm.skew} kurt=${norm.kurt}`}>✓</span> : <span className="text-amber-400" title={`skew=${norm.skew} kurt=${norm.kurt}`}>NP</span>) : "—"}
                        </td>
                        <td className="px-2 py-2 text-center text-white/55">{fmtM(r.aomiPre)}</td>
                        <td className="px-2 py-2 text-center text-white/55">{fmtM(r.aomiPost)}</td>
                        <td className="px-2 py-2 text-center text-white/55">{fmtM(r.ctrlPre)}</td>
                        <td className="px-2 py-2 text-center text-white/55">{fmtM(r.ctrlPost)}</td>
                        <td className="px-2 py-2 text-center">{fmtP(r.withinAomi?.p)}{sigStars(r.withinAomi?.p)}</td>
                        <td className="px-2 py-2 text-center">{fmtP(r.withinCtrl?.p)}{sigStars(r.withinCtrl?.p)}</td>
                        <td className="px-2 py-2 text-center font-bold text-white">{fmtP(r.betweenDelta?.p)}{sigStars(r.betweenDelta?.p)}</td>
                        <td className="px-2 py-2 text-center text-white/50">{r.betweenDelta?.es != null ? Math.abs(r.betweenDelta.es).toFixed(2) : "—"}</td>
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
                          <td className="px-3 py-2 text-center text-white/60">{ix ? ix.F.toFixed(3) : "—"}</td>
                          <td className="px-3 py-2 text-center font-bold">{ix ? fmtP(ix.p) : "—"}</td>
                          <td className="px-3 py-2 text-center text-white/50">{ix ? ix.eta_p2 : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Glass>
          {backendReport?.holm_secondary_kinematic && (
        <Glass className="p-5">
              <p className="text-xs font-extrabold text-amber-300 uppercase tracking-widest mb-4">Holm–Bonferroni (secondary kinematic, k=8)</p>
              <div className="overflow-x-auto rounded-xl border border-amber-500/20">
            <table className="w-full text-xs">
              <thead>
                    <tr className="bg-amber-500/10">
                      <th className="text-left px-3 py-2 text-amber-200">Variable</th>
                      <th className="text-center px-3 py-2">p (interaction)</th>
                      <th className="text-center px-3 py-2">Holm α</th>
                      <th className="text-center px-3 py-2">Sig?</th>
                </tr>
              </thead>
              <tbody>
                    {backendReport.holm_secondary_kinematic.map((h) => (
                      <tr key={h.name} className="border-b border-white/[0.04]">
                        <td className="px-3 py-2 text-white/70">{h.name}</td>
                        <td className="px-3 py-2 text-center">{fmtP(h.p)}</td>
                        <td className="px-3 py-2 text-center text-white/50">{h.holm_alpha}</td>
                        <td className="px-3 py-2 text-center font-bold">{h.significant ? "✓" : "—"}</td>
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
                ⬇ Literature Review
              </button>
              <button type="button" onClick={() => downloadBlob(new Blob(["\uFEFF" + generateConsortSapMarkdown()], { type: "text/markdown;charset=utf-8" }), "THESIS_CONSORT_SAP.md")} className="px-5 py-2.5 rounded-xl bg-violet-500/20 border border-violet-400/30 text-violet-200 text-xs font-extrabold">
                ⬇ CONSORT + SAP
              </button>
          </div>
        </Glass>

          <Glass className="p-5">
            <p className="text-xs font-extrabold text-rose-300 uppercase tracking-widest mb-4">Program Roadmap (what NeuroLab still needs)</p>
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
            Apply LOCF imputation (missing Post ← Pre) for ITT export
          </label>
        <div className="flex flex-wrap gap-3">
            <button type="button" onClick={downloadMasterCsv} className="px-5 py-2.5 rounded-xl bg-violet-500/20 border border-violet-400/30 text-violet-200 text-xs font-extrabold hover:bg-violet-500/30">
              ⬇ master_study_data.csv
            </button>
            <button type="button" onClick={downloadSpssSyntax} className="px-5 py-2.5 rounded-xl bg-sky-500/20 border border-sky-400/30 text-sky-200 text-xs font-extrabold hover:bg-sky-500/30">
              ⬇ neuro_study_analysis.sps
            </button>
            <button type="button" onClick={() => {
            const allPts = loadPatients();
              downloadBlob(new Blob([JSON.stringify(allPts, null, 2)], { type: "application/json" }), `neuro_backup_${allPts.length}pts.json`);
            }} className="px-5 py-2.5 rounded-xl bg-emerald-500/20 border border-emerald-400/30 text-emerald-200 text-xs font-extrabold">
              ⬇ JSON backup
            </button>
          </div>
          <p className="text-[10px] text-white/35 mt-4 font-mono">CLI: python backend/study_analysis.py master_study_data.csv --out study_results.txt</p>
        </Glass>
      )}

      {missingFields.length > 0 && (
        <Glass className="p-5">
          <p className="text-xs font-extrabold text-rose-300 uppercase tracking-widest mb-3">Missing Data ({missingFields.length})</p>
          <div className="max-h-40 overflow-y-auto text-xs text-white/50 space-y-1">
            {missingFields.slice(0, 20).map((m, i) => (
              <p key={i}>{m.id}: {m.field}</p>
            ))}
            {missingFields.length > 20 && <p>…and {missingFields.length - 20} more</p>}
        </div>
      </Glass>
      )}
    </div>
  );
};

// ─── Root App ─────────────────────────────────────────────────────────────────

const getTodayDate = () => new Date().toISOString().split("T")[0];

export default function App() {
  const [active, setActive] = useState("demographics");
  const [sidebar, setSidebar] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(min-width: 768px)").matches : true
  );
  const [isDesktop, setIsDesktop] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(min-width: 768px)").matches : true
  );
  const [sidebarPush, setSidebarPush] = useState(() => sidebarPushWidth());
  const [toast, setToast] = useState({ visible: false, msg: "", variant: "success" });
  const [bgUrl, setBgUrl] = useState(BG);
  const bgRef = useRef(null);
  const importRef = useRef(null);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const syncLayout = () => {
      setIsDesktop(mq.matches);
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

  useEffect(() => {
    const KEY = "nl_app_v";
    try {
      const prev = localStorage.getItem(KEY);
      if (prev && prev !== APP_VERSION) {
        localStorage.setItem(KEY, APP_VERSION);
        const url = new URL(window.location.href);
        if (url.searchParams.get("_v") !== APP_VERSION) {
          url.searchParams.set("_v", APP_VERSION);
          window.location.replace(url.toString());
          return;
        }
      }
      localStorage.setItem(KEY, APP_VERSION);
    } catch {}
  }, []);

  useEffect(() => {
    fetch("/bg.b64.txt")
      .then((r) => (r.ok ? r.text() : Promise.reject()))
      .then((b64) => setBgUrl(`data:image/jpeg;base64,${b64.trim()}`))
      .catch(() => {});
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
      kinematics: {},
    };
  });

  // Auto-save all sections to localStorage on any change
  useEffect(() => {
    localStorage.setItem(FD_LS_KEY, JSON.stringify(fd));
  }, [fd]);

  // Sync patients from server on startup (cross-device)
  useEffect(() => {
    syncPatientsWithServer({ silent: true }).then(({ ok, patients: merged }) => {
      if (!ok) return;
          const curId = fd._loadedId || fd.demographics?.participantId;
          if (curId) {
            const cur = merged.find((p) => (p._id || p.demographics?.participantId) === curId);
            if (cur?.kinematics?.analysisResults) {
              localStorage.setItem(KIN_LS_KEY, JSON.stringify(cur.kinematics.analysisResults));
            }
          }
    });
  }, []);

  const upd = useCallback((sec, d) => setFd((p) => ({ ...p, [sec]: d })), []);

  const showToast = useCallback((msg, variant = "success") => {
    setToast({ visible: true, msg, variant });
    setTimeout(() => setToast({ visible: false, msg: "", variant: "success" }), 2800);
  }, []);

  const saveSession = useCallback(() => {
    const patients = loadPatients();
    const d = fd.demographics || {};

    const hasPre = !!(fd.vas?.rest?.pre || fd.motorchange?.control || fd.vams?.happy?.pre);
    const hasPost = !!(fd.vas?.rest?.post || fd.motorchange?.difference || fd.vams?.happy?.post);

    // Try to match by internal _loadedId first, then by participantId
    let existingIdx = -1;
    if (fd._loadedId) {
      existingIdx = patients.findIndex((p) => p._id === fd._loadedId);
    }
    if (existingIdx < 0) {
      existingIdx = patients.findIndex(
        (p) => p.demographics?.participantId && p.demographics.participantId === d.participantId
      );
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
        _savedAt: new Date().toISOString(),
        _hasPre: existing._hasPre || hasPre,
        _hasPost: existing._hasPost || hasPost,
      };
      savePatients(patients);
      window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count: patients.length } }));
      showToast("✓ Session updated");
      syncPatientsWithServer({ silent: true }).then(({ ok }) => {
        if (!ok) showToast("Saved locally — server sync pending. Tap Sync in Database.", "error");
      });
    } else {
      const fdWithKin = { ...fd, kinematics: { ...fd.kinematics, analysisResults: kinResults } };
      const { _loadedId, ...cleanFd } = fdWithKin;
      patients.push({
        _id: `pt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        _savedAt: new Date().toISOString(),
        _hasPre: hasPre,
        _hasPost: hasPost,
        ...cleanFd,
      });
      savePatients(patients);
      window.dispatchEvent(new CustomEvent(PATIENTS_SYNC_EVENT, { detail: { count: patients.length } }));
      showToast("✓ New patient saved");
      syncPatientsWithServer({ silent: true }).then(({ ok }) => {
        if (!ok) showToast("Saved locally — server sync pending. Tap Sync in Database.", "error");
      });
      setFd((p) => ({
        ...p,
        demographics: { ...p.demographics, participantId: String(nextStudyId()) },
      }));
    }
  }, [fd, showToast]);

  const newSession = useCallback(() => {
    localStorage.setItem("neuro_last_session_backup", JSON.stringify(fd));
    localStorage.removeItem(KIN_LS_KEY);
    setFd({
      demographics: { participantId: String(nextStudyId()) },
      ipaq: {},
      vas: {},
      vams: {},
      motorchange: {},
      kgia: {},
      wmft: {},
      kinematics: {},
    });
    setActive("demographics");
    if (!isDesktop) setSidebar(false);
    showToast("✓ New session started / Yeni seans başlatıldı");
  }, [fd, showToast, isDesktop]);

  const handleLoadSession = useCallback((record) => {
    const { _id, _savedAt, _hasPre, _hasPost, ...sessionData } = record;
    setFd((prev) => ({ ...prev, ...sessionData, _loadedId: _id }));
    if (sessionData.kinematics?.analysisResults) {
      localStorage.setItem(KIN_LS_KEY, JSON.stringify(sessionData.kinematics.analysisResults));
    }
    setActive("demographics");
    showToast(`✓ Loaded: ${record.demographics?.name || record.demographics?.participantId || "patient"}`);
  }, [showToast]);

  const handleImportFile = useCallback(async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      const normalized = await importPatientFile(file);
      const record = buildImportRecord(normalized);
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

  const nav = NAV_ITEMS.find((n) => n.id === active);

  const topBar = (
    <div className={`app-topbar-glass glass-float flex items-center gap-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-xl ${GLASS_CLS}`} style={{ boxShadow: FLOAT_M }}>
      <motion.button
        whileTap={{ scale: 0.9 }}
        onClick={() => setSidebar((p) => !p)}
        className="w-9 h-9 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center text-white/60 hover:text-white transition-all flex-shrink-0"
        style={GLASS_FIELD}
        aria-label={sidebar ? "Close menu" : "Open menu"}
      >
        {sidebar ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
      </motion.button>

      {(!sidebar || isDesktop) && nav && (() => {
        const Icon = nav.icon;
        return (
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Icon className="w-4 h-4 text-white/60 flex-shrink-0" />
            <span className="text-sm font-extrabold text-white truncate">{nav.en}</span>
            <span className="text-xs font-light text-white/30 hidden md:inline truncate">/{nav.tr}</span>
          </div>
        );
      })()}

      {sidebar && !isDesktop && (
        <span className="flex-1 text-sm font-extrabold text-white/70 truncate">Navigation</span>
      )}

      <div className={`ml-auto flex items-center gap-2 flex-shrink-0 ${sidebar && !isDesktop ? "hidden" : ""}`}>
        <span className="text-xs font-light text-white/30 hidden lg:block whitespace-nowrap">
          {new Date().toLocaleDateString("tr-TR", { day: "2-digit", month: "long", year: "numeric" })}
        </span>

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

        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
          onClick={() => importRef.current?.click()}
          className="w-9 h-9 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center text-white/50 hover:text-emerald-300 transition-all flex-shrink-0"
          style={GLASS_FIELD}
          title="Import patient (JSON or Clinical Report PDF)"
          aria-label="Import patient file"
        >
          <FileUp className="w-4 h-4" />
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
          onClick={() => bgRef.current?.click()}
          className="w-9 h-9 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center text-white/50 hover:text-white transition-all flex-shrink-0"
          style={GLASS_FIELD}
        >
          <ImageIcon className="w-4 h-4" />
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
          onClick={() => { setActive("database"); if (!isDesktop) setSidebar(false); }}
          className="w-9 h-9 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center text-white/50 hover:text-white transition-all flex-shrink-0"
          style={GLASS_FIELD}
        >
          <Database className="w-4 h-4" />
        </motion.button>
      </div>
    </div>
  );

  const sections = {
    demographics: <DemoSection data={fd.demographics} onChange={(d) => upd("demographics", d)} onBulkUpdate={(sec, d) => upd(sec, d)} />,
    ipaq: <IPAQSection data={fd.ipaq} onChange={(d) => upd("ipaq", d)} />,
    vas: <VASSection data={fd.vas} onChange={(d) => upd("vas", d)} />,
    vams: <VAMSSection data={fd.vams} onChange={(d) => upd("vams", d)} />,
    motorchange: <MotorSection data={fd.motorchange} onChange={(d) => upd("motorchange", d)} />,

    kgia: <KGIASection data={fd.kgia} onChange={(d) => upd("kgia", d)} />,
    wmft: <WMFTSection data={fd.wmft} onChange={(d) => upd("wmft", d)} />,
    kinematics: (
      <KinSection
        data={fd.kinematics}
        sessionKey={fd._loadedId || fd.demographics?.participantId}
        demographics={fd.demographics}
        onChange={(d) => upd("kinematics", d)}
        showToast={showToast}
      />
    ),
    database: <DatabaseSection fd={fd} setFd={setFd} onLoadSession={handleLoadSession} showToast={showToast} isActive={active === "database"} />,
    report: <ReportSection fd={fd} onChange={(d) => upd("demographics", d)} showToast={showToast} />,
    analysis: <AnalysisDashboard />,
  };

  return (
    <div className="min-h-screen flex relative overflow-x-hidden" style={{ fontFamily: "'Inter',system-ui,sans-serif" }}>
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
          className="fixed inset-0 z-20 bg-black/60"
          onClick={() => setSidebar(false)}
          aria-hidden="true"
        />
      )}

          <motion.aside
        initial={false}
        animate={{ x: sidebar ? 0 : (isDesktop ? SIDEBAR_X_HIDDEN : "-100%") }}
        transition={SIDEBAR_SPRING}
        className={`fixed left-0 top-0 h-full z-30 flex flex-col px-3 pb-3 ${isDesktop ? "" : "w-full"}`}
        style={isDesktop ? { width: sidebarPush, paddingTop: SAFE_TOP } : { width: "100%", paddingTop: SAFE_TOP }}
      >
            <div className={`sidebar-shell flex-1 flex flex-col min-h-0 rounded-2xl overflow-hidden ${SIDEBAR_CLS}`} style={{ boxShadow: FLOAT_M }}>
              <div className="p-5 flex-shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                  <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={GLASS_FIELD}>
                      <Stethoscope className="w-5 h-5 text-white/80" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-extrabold text-white truncate">Stroke Rehab Platform</p>
                    <p className="text-[10px] text-white/30 font-light">{APP_VERSION}</p>
                    </div>
                  </div>
                <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl" style={GLASS_FIELD}>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
                  <span className="text-xs font-light text-white/50 truncate">Pre / Post Longitudinal</span>
              </div>
            </div>

              <nav className="flex-1 min-h-0 p-3 space-y-0.5 overflow-y-auto">
                {NAV_ITEMS.map((item) => {
                  const on = active === item.id;
                  const Icon = item.icon;

                  return (
                    <motion.button
                      key={item.id}
                      whileTap={{ scale: 0.97 }}
                      onClick={() => { setActive(item.id); if (!isDesktop) setSidebar(false); }}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors duration-200 relative group ${
                        on ? "bg-white/[0.07]" : "hover:bg-white/[0.04]"
                      }`}
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
                        <p className={`text-[10px] font-light leading-snug sm:truncate ${on ? "text-white/40" : "text-white/20"}`}>
                          {item.tr}
                        </p>
                      </div>

                      {on && <ChevronRight className="w-3.5 h-3.5 text-white/40 relative z-10 flex-shrink-0" />}
                    </motion.button>
                  );
                })}
              </nav>

              <div className="p-3 flex-shrink-0 space-y-2" style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}>
                <motion.button
                  whileTap={{ scale: 0.96 }}
                  onClick={() => { newSession(); }}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl bg-violet-500/15 border border-violet-400/25 text-violet-200 hover:bg-violet-500/25 hover:border-violet-400/40 transition-all"
                >
                  <PlusCircle className="w-4 h-4 flex-shrink-0" />
                  <span className="text-sm font-bold">New Session</span>
                  <RotateCcw className="w-3.5 h-3.5 ml-auto opacity-60 flex-shrink-0" />
                </motion.button>
                <motion.button
                  whileTap={{ scale: 0.96 }}
                  onClick={() => { saveSession(); if (!isDesktop) setSidebar(false); }}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl bg-emerald-500/15 border border-emerald-400/25 text-emerald-200 hover:bg-emerald-500/25 hover:border-emerald-400/40 transition-all"
                >
                  <Save className="w-4 h-4 flex-shrink-0" />
                  <span className="text-sm font-bold">Save Session</span>
                  <Plus className="w-3.5 h-3.5 ml-auto opacity-60 flex-shrink-0" />
                </motion.button>
              </div>
            </div>
          </motion.aside>

      <main
        className="flex-1 relative z-10 transition-[margin] duration-300"
        style={{ marginLeft: isDesktop && sidebar ? sidebarPush : 0 }}
      >
          <div className="sticky top-0 z-[60] px-3 sm:px-4 pb-0" style={{ paddingTop: SAFE_TOP }}>
            {topBar}
                </div>
        <div className="app-main-inner px-3 sm:px-4 py-4 sm:py-6 max-w-5xl w-full mx-auto">
          <div className="content-shell rounded-2xl">
            <div className="content-shell-inner p-4 sm:p-6">
              <div className="section-transition-host min-h-[420px]">
                <AnimatePresence mode="sync" initial={false}>
            <motion.div
              key={active}
                    className="section-pane w-full"
              initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: -8, filter: "blur(4px)" }}
              transition={{ duration: 0.3 }}
            >
              {sections[active]}
            </motion.div>
          </AnimatePresence>
        </div>
            </div>
          </div>
        </div>
      </main>

      {/* Global Styles */}
      <style>{`
        * { box-sizing: border-box; }
        h1, h2, h3, p, span, label, button {
          text-shadow: 0 1px 3px rgba(0,0,0,0.25);
        }

        /* Design tokens — glass 8% white / border 12% / inputs 9% */
        [class*="border-white"] {
          border-color: rgba(255,255,255,0.12) !important;
        }
        .border-b[class*="border-white"],
        .border-t[class*="border-white"] {
          border-color: rgba(255,255,255,0.08) !important;
          box-shadow: none !important;
        }

        .sidebar-shell,
        .glass-float {
          border-color: rgba(255,255,255,0.12) !important;
        }

        .content-shell {
          border-color: rgba(255,255,255,0.11) !important;
        }

        .glass-float {
          box-shadow: none !important;
        }

        /* Inputs — bg 9%, border 12% */
        .glass-field,
        input, select, textarea {
          background-color: rgba(255,255,255,0.09) !important;
          border-color: rgba(255,255,255,0.12) !important;
          box-shadow: none !important;
        }
        .glass-float input,
        .glass-float select,
        .glass-float textarea,
        .glass-float .glass-field {
          box-shadow: none !important;
        }
        .glass-float .glass-float {
          box-shadow: none !important;
        }

        .shadow-lg, .shadow-xl, .shadow-2xl {
          box-shadow: 0 16px 40px -22px rgba(0,0,0,0.07) !important;
        }

        ::-webkit-scrollbar { width: 3px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.18); border-radius: 99px; }
        input[type=number]::-webkit-inner-spin-button { opacity: 0; }
        select option { background-color: #0e1120; color: white; }
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
        video { outline: none; background: #000; }
        .grid { min-width: 0; }
        .grid > * { min-width: 0; overflow-wrap: break-word; word-break: break-word; }
        input, select { min-height: 44px !important; }
        button { min-height: 44px !important; }
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

      <Toast msg={toast.msg} visible={toast.visible} variant={toast.variant} />
    </div>
  );
}