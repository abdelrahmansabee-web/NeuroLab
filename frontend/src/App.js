// ============================================================
// Stroke Rehabilitation Platform — Frontend v6.4
// ============================================================

import React, { useState, useRef, useCallback, useEffect } from "react";
import ReactDOM from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  User, Activity, Sliders, TrendingUp, Heart, Timer, Cpu, FileText,
  Menu, X, ChevronRight, Play, Square, RotateCcw, Copy, Check,
  Info, Save, BarChart3, Stethoscope, Brain, Image as ImageIcon,
  RefreshCw, FileSpreadsheet,
  Database, Search, Edit3, Trash2, Plus,
} from "lucide-react";
import * as XLSX from "xlsx";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

const BG = "/bg.jpg";

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
  { id:"database", icon:Database, en:"Patient Database", tr:"Hasta Veritabanı" },
  { id:"analysis", icon:BarChart3, en:"Analysis Dashboard", tr:"Analiz Paneli" },
];

const LS_KEY = "stroke_rehab_patients_v6";

function loadPatients() {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch { return []; }
}
function savePatients(list) {
  localStorage.setItem(LS_KEY, JSON.stringify(list));
}

// ─── Shared UI ────────────────────────────────────────────────────────────────

const Glass = ({ children, className = "", style = {}, ...r }) => (
  <div
    className={`bg-white/[0.08] backdrop-blur-xl border border-white/[0.08] shadow-2xl rounded-2xl ${className}`}
    style={{ overflow:"visible", ...style }}
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
  <div className="flex items-center gap-3 mb-6">
    <div className="w-11 h-11 rounded-xl bg-white/10 border border-white/[0.06] flex items-center justify-center flex-shrink-0">
      <Icon className="w-5 h-5 text-white/80" />
    </div>
    <div className="min-w-0 flex-1">
      <h2 className="text-xl font-extrabold text-white leading-tight">{en}</h2>
      <p className="text-xs font-light text-white/35 uppercase tracking-widest truncate">{tr}</p>
    </div>
    {badge && (
      <span className="ml-auto flex-shrink-0 px-3 py-1 rounded-full text-xs font-semibold bg-white/[0.06] border border-white/[0.04] text-white/50">
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
      className="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white placeholder-white/15 text-sm font-light focus:outline-none focus:bg-white/[0.06] transition-all"
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
          className="w-full px-3 py-2.5 rounded-xl bg-white/[0.06] border border-white/[0.08] text-white text-sm font-light text-left flex items-center justify-between gap-2"
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
            <div style={{ backgroundColor: "rgba(30,35,45,0.6)", backdropFilter: "blur(30px) saturate(150%)", WebkitBackdropFilter: "blur(30px) saturate(150%)", border: "1px solid rgba(255,255,255,0.1)", boxShadow: "0 8px 32px 0 rgba(0,0,0,0.37)" }} className="rounded-xl overflow-hidden py-1">
              {options.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => { onChange({ target: { value: o.value } }); setOpen(false); }}
                  className={`w-full text-left px-3 py-2.5 text-sm block ${value === o.value ? "text-white font-bold" : "text-white/90"}`}
                  style={{ backgroundColor: value === o.value ? "rgba(255,255,255,0.12)" : "transparent" }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.08)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = value === o.value ? "rgba(255,255,255,0.12)" : "transparent"; }}
                >
                  {o.label}
                </button>
              ))}
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
    danger: "bg-red-500/20 border-red-400/30 text-red-200 hover:bg-red-500/30",
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
            : "bg-rose-500/20 border-rose-400/30 text-rose-200"
        }`}
      >
        <Check className="w-4 h-4" /> {msg}
      </motion.div>
    )}
  </AnimatePresence>
);

const calculateClinicalDelta = (pre, post, metricName) => {
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

  // Metrics where a LOWER post value = clinical improvement
  const n = (metricName || "").toLowerCase();
  const lowerIsBetter =
    n.includes("pain")           ||   // VAS pain: higher = worse
    n.includes("anxiety")        ||   // VAMS: higher = more anxious
    n.includes("distress")       ||   // VAMS: higher = more distressed
    n.includes("fear")           ||
    n.includes("confusion")      ||
    n.includes("sad")            ||
    n.includes("fatigue")        ||
    n.includes("tension")        ||
    n.includes("tense")          ||
    n.includes("duration")       ||   // faster = better
    n.includes("pause")          ||   // less pause = smoother
    n.includes("bve")            ||   // lower BVE = smoother
    n.includes("path")           ||   // shorter path = more direct
    n.includes("path ratio")     ||   // closer to 1.0 = straighter
    n.includes("trunk lat")      ||   // less trunk compensation
    n.includes("trunk vert")     ||
    n.includes("trunk rot")      ||
    n.includes("shoulder vert");

  // Peak velocity: higher = better → higherIsBetter
  // Elbow extension: higher degrees = better → higherIsBetter
  // Displacement norm: not directional → treat as higher=better (neutral)

  const isImprovement = lowerIsBetter ? delta < 0 : delta > 0;

  return {
    text,
    colorClass: isImprovement
      ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
      : "text-rose-400 bg-rose-400/10 border-rose-400/20",
  };
};

const ThickSlider = ({ value, min = 0, max = 10, step = 0.5, color = "sky", onChange, label }) => {
  const trackRef = useRef(null);
  const dragging = useRef(false);
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));

  const accent = {
    sky: "#38bdf8",
    emerald: "#34d399",
    violet: "#a78bfa",
    cyan: "#22d3ee",
    amber: "#fbbf24",
    rose: "#fb7185",
  };

  const clr = accent[color] || accent.sky;
  const decimals = Math.max(0, (String(step).split(".")[1] || "").length);
  const clamp = (n) => Math.min(max, Math.max(min, n));
  const snap = (raw) => Number((Math.round((raw - min) / step) * step + min).toFixed(decimals));

  const rafId = useRef(null);
  const setFromClientX = useCallback((clientX) => {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0) return;
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    onChange(String(clamp(snap(min + ratio * (max - min)))));
  }, [min, max, step, onChange, clamp, snap]);

  const onPointerDown = (e) => {
    e.preventDefault();
    dragging.current = true;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setFromClientX(e.clientX);
  };

  const onPointerMove = (e) => {
    if (!dragging.current) return;
    e.preventDefault();
    if (rafId.current != null) return;
    rafId.current = requestAnimationFrame(() => {
      rafId.current = null;
      setFromClientX(e.clientX);
    });
  };

  const endDrag = (e) => {
    dragging.current = false;
    if (rafId.current != null) { cancelAnimationFrame(rafId.current); rafId.current = null; }
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  };

  const onKeyDown = (e) => {
    let next = value;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") next = +value + step;
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = +value - step;
    else if (e.key === "Home") next = min;
    else if (e.key === "End") next = max;
    else return;
    e.preventDefault();
    onChange(String(clamp(snap(next))));
  };

  return (
    <div style={{ touchAction: "none" }}>
      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
        className="relative h-8 rounded-full cursor-pointer focus:outline-none select-none"
        style={{ touchAction: "none", background: "rgba(255,255,255,0.06)", userSelect: "none", WebkitUserSelect: "none" }}
      >
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${clr}55, ${clr}33)`, transition: "width 0.05s linear" }}
        />
      </div>
      {label && (
        <div className="text-center mt-2">
          <span className="text-xs font-bold text-white/60">{label}</span>
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
        label={`${n.toFixed(1)} / 10 — ${closestFace.en} / ${closestFace.tr}`}
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
        label={`${n.toFixed(1)} / 10 — ${closestFace.en} / ${closestFace.tr}`}
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
        label={`${n.toFixed(1)} / 10 — ${getLabel(n)}`}
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
        label={curr ? `${n} — ${curr.en} / ${curr.tr}` : "Select / Seçin"}
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
          label={`${rv} — ${ratingLabels[rv]}`}
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
              <input type="number" value={data.treatValue ?? ""} onChange={(e) => s("treatValue", e.target.value)} placeholder="0" className="flex-1 min-w-0 px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white text-sm font-light focus:outline-none transition-all" />
              <select value={data.treatUnit ?? "week"} onChange={(e) => s("treatUnit", e.target.value)} className="w-24 flex-shrink-0 px-2 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white text-sm font-light focus:outline-none transition-all appearance-none" style={{ colorScheme:"dark" }}>{["day","week","month","year"].map((u) => <option key={u} value={u} className="bg-[#1a1a2e]">{u}</option>)}</select>
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
          <textarea rows={2} value={data.notes ?? ""} onChange={(e) => s("notes", e.target.value)} placeholder="Medical history, comorbidities, assessment context…" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none transition-all" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <textarea rows={2} value={data.antispasticDrugs ?? ""} onChange={(e) => s("antispasticDrugs", e.target.value)} placeholder="Antispastic drugs: Baclofen, Tizanidine…" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none transition-all" />
            <textarea rows={2} value={data.otherDrugs ?? ""} onChange={(e) => s("otherDrugs", e.target.value)} placeholder="Other medications: Aspirin, Warfarin…" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none transition-all" />
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
  const ic = "w-full px-2 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-white text-sm font-bold text-center placeholder-white/15 focus:outline-none focus:bg-white/[0.06] transition-all";

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

      <Glass className="p-5">
        <div className="overflow-x-auto rounded-xl border border-white/[0.08]">
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

      <Glass className="p-5 border-l-2 border-amber-400/40">
        <div className="flex items-start gap-3 mb-4">
          <BarChart3 className="w-5 h-5 text-amber-300 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-extrabold text-white/90">Physical Activity Level Interpretation</p>
            <p className="text-xs font-light text-white/40 mt-0.5">Based on IPAQ scoring guidelines</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="px-4 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08]">
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
          ].map((btn) => (
            <button
              key={btn.val}
              type="button"
              onClick={() => {
                const existing = data?.notes || "";
                const sep = existing ? "\n" : "";
                onChange({ ...data, notes: existing + sep + btn.val });
              }}
              className="text-[9px] font-bold px-2 py-1 rounded-lg bg-amber-400/10 border border-amber-400/20 text-amber-300 hover:bg-amber-400/20 transition-all whitespace-nowrap"
            >
              + {btn.label}
            </button>
          ))}
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

function getNextStudyId() {
  const id = parseInt(localStorage.getItem(NEXT_ID_LS_KEY)) || 100;
  return id + 1;
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

function incrementStudyId() {
  const id = parseInt(localStorage.getItem(NEXT_ID_LS_KEY)) || 100;
  localStorage.setItem(NEXT_ID_LS_KEY, id + 1);
}

// ─── Kinematics AI Lab Section ────────────────────────────────────────────────

const KIN_LS_KEY = "neuro_kin_results";
const KIN_LS_EXP_KEY = "neuro_kin_expanded";

const KinSection = ({ data, demographics, onChange, showToast }) => {
  const [kinematicsResults, setKinematicsResults] = useState(() => {
    try { return JSON.parse(localStorage.getItem(KIN_LS_KEY)) || {}; } catch { return {}; }
  });
  const [settings, setSettings] = useState({
    cutoffFrequency: 6.0,
    filterOrder: 4,
  });
  const [expandedResults, setExpandedResults] = useState(() => {
    try { return JSON.parse(localStorage.getItem(KIN_LS_EXP_KEY)) || {}; } catch { return {}; }
  });

  const abortRef = useRef({});

  useEffect(() => {
    localStorage.setItem(KIN_LS_KEY, JSON.stringify(kinematicsResults));
  }, [kinematicsResults]);

  useEffect(() => {
    localStorage.setItem(KIN_LS_EXP_KEY, JSON.stringify(expandedResults));
  }, [expandedResults]);

  // Import parsed kinematics data (from PDF/CSV) into kinematicsResults
  useEffect(() => {
    if (!data || Object.keys(kinematicsResults).length > 0) return;
    const kinMap = {
      movementDuration: "total_duration_s",
      peakVelocity: "total_peak_velocity",
      meanVelocity: "total_mean_velocity",
      totalPathLength: "total_path_length",
      lateralRange: "total_lat_range_norm",
      trunkPalmRatio: "total_trunk_palm_ratio",
      maxElbowAngle: "total_max_elbow_deg",
      pauseSmoothness: "smoothness_pause_pct",
      shoulderVertExcursion: "shoulder_vert_norm",
      trunkLateralFlexion: "trunk_lat_norm",
      trunkForwardFlexion: "trunk_vert_norm",
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
    { k:"during", l:"During", c:"violet" },
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
      setKinematicsResults((prev) => { const n = { ...prev }; delete n[phase]; return n; });
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
    onChange(upd);
    setKinematicsResults((prev) => { const n = { ...prev }; delete n[phase]; return n; });
    setExpandedResults((prev) => { const n = { ...prev }; delete n[phase]; return n; });
    showToast(`Cleared ${phase}`);
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
      fd.append("affected_side", "auto");
      fd.append("cutoff_frequency", settings.cutoffFrequency.toString());
      fd.append("filter_order", settings.filterOrder.toString());
      fd.append("patient_height_cm", demographics?.height || "auto");
      fd.append("shoulder_width_cm", demographics?.shoulderWidth || "auto");
      if (!isCsv) {
        fd.append("arm_type", "paretic");
        fd.append("trial_count", "3");
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

      setKinematicsResults((prev) => ({ ...prev, [phase]: result }));
      onChange({ ...data, [resultKey(phase)]: result, [statusKey(phase)]: "completed" });
      showToast(`✓ Analysis complete for ${phase}`);
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
    if (!filename) return;

    const a = document.createElement("a");
    a.href = `${API_BASE}/download-${type}/${encodeURIComponent(filename)}`;
    a.download = filename;
    a.click();
  };

  const toggleResult = (phase) => {
    setExpandedResults((prev) => ({ ...prev, [phase]: !prev[phase] }));
  };

  const getMetricValue = (phase, key) => {
    const result = kinematicsResults[phase];
    if (!result || result[key] == null) return "—";
    const val = result[key];
    if (typeof val === "object" && val !== null) {
      return val.best ?? val.mean ?? "—";
    }
    return val ?? "—";
  };

  const variables = [
    // 🥇 Primary — Smoothness & Compensation

    { group: "Primary", name: "Smoothness (Pause %)",           key: "smoothness_pause_pct",    unit: "%",     tip: "Pause Ratio = % time velocity below 10% of peak. Lower = more continuous movement (smoother). Healthy ~5–10%, Impaired >25%" },
    { group: "Primary", name: "Trunk/Palm Ratio",                key: "total_trunk_palm_ratio", unit: "ratio", tip: "Total trunk path / total hand path. Higher = more trunk compensation" },

    // 🥈 Secondary — Performance

    { group: "Secondary", name: "Lateral Wiping Range (norm)",   key: "total_lat_range_norm",   unit: "ratio", tip: "Width of wiping motion, normalized to shoulder width. Higher = fuller reach" },
    { group: "Secondary", name: "Peak Velocity",                 key: "total_peak_velocity",    unit: "norm/s", tip: "Maximum hand speed. Higher = more explosive movement" },
    { group: "Secondary", name: "Total Path Length",             key: "total_path_length",      unit: "norm",   tip: "Total distance traveled by the hand (body-proportional units). Most robust overall activity metric" },
    { group: "Secondary", name: "Mean Velocity",                 key: "total_mean_velocity",    unit: "norm/s", tip: "Average hand speed across whole movement" },

    // 🥉 Tertiary — Supporting details

    { group: "Tertiary", name: "Trunk Lateral Disp. (norm)",     key: "trunk_lat_norm",         unit: "ratio", tip: "Side-to-side trunk displacement. Lower = better trunk stability" },
    { group: "Tertiary", name: "Trunk Vertical Disp. (norm)",    key: "trunk_vert_norm",        unit: "ratio", tip: "Up-down trunk displacement" },
    { group: "Tertiary", name: "Trunk Rotation (norm)",          key: "trunk_rot_norm",         unit: "ratio", tip: "Shoulder separation change. Lower = less rotation of upper body" },
    { group: "Tertiary", name: "Arm Length (norm)",                 key: "arm_length_norm",       unit: "ratio", tip: "Normalized arm length (pixel arm length / shoulder width)" },
    { group: "Tertiary", name: "Ref Scale (Shoulder)",              key: "ref_scale",             unit: "px",    tip: "The reference scale used for normalization (shoulder width in pixels)" },
    { group: "Tertiary", name: "Shoulder Vertical Excursion",   key: "shoulder_vert_norm",     unit: "ratio", tip: "Vertical shoulder movement. Lower = less compensatory shoulder elevation" },
    { group: "Tertiary", name: "Max Elbow Extension",            key: "total_max_elbow_deg",    unit: "deg",   tip: "Maximum elbow extension angle. Higher = better ability to extend arm" },
    { group: "Tertiary", name: "Duration",                       key: "total_duration_s",       unit: "sec",   tip: "Total movement time from onset to offset" },
    { group: "Tertiary", name: "Code Version",                 key: "_code_version",        unit: "",      tip: "Diagnostic: which code version is running" },
    { group: "Tertiary", name: "Side Analyzed",                key: "side_analyzed",        unit: "",      tip: "Which side was analyzed (left/right)" },
  ];

  const phaseInfo = {
    forward:    { label: "Forward Reach",   color: "sky" },
    wipe_right: { label: "Wipe Right",      color: "violet" },
    wipe_left:  { label: "Wipe Left",       color: "amber" },
    return:     { label: "Return",          color: "rose" },
  };

  const phaseMetrics = [
    { key: "distance_norm",        name: "Distance",        unit: "norm" },
    { key: "lateral_range_norm",   name: "Lateral Range",   unit: "norm" },
    { key: "forward_range_norm",   name: "Forward Range",   unit: "norm" },
    { key: "peak_velocity",        name: "Peak Vel.",       unit: "norm/s" },
    { key: "pause_pct",            name: "Pause %",         unit: "%" },
    { key: "path_ratio",           name: "Path Ratio",      unit: "ratio" },
    { key: "trunk_palm_ratio",     name: "Trunk/Palm",      unit: "ratio" },
  ];

  const getPhaseMetricValue = (phaseKey, phaseName, metricKey) => {
    const result = kinematicsResults[phaseKey];
    if (!result || !result.phases || !result.phases[phaseName] || !result.phases[phaseName].present) return "\u2014";
    const val = result.phases[phaseName][metricKey];
    return val != null ? val : "\u2014";
  };

  // Collect phase names present in at least one recording
  const presentPhases = (() => {
    const names = new Set();
    Object.values(kinematicsResults).forEach((r) => {
      if (r.phases) {
        Object.entries(r.phases).forEach(([pn, pd]) => {
          if (pd?.present) names.add(pn);
        });
      }
    });
    return names;
  })();

  const hasPrePost = kinematicsResults.pre && kinematicsResults.post;
  const recordingColumns = phases.filter((ph) => kinematicsResults[ph.k]);

  return (
    <div className="space-y-5">
      <SH icon={Cpu} en="Kinematics AI Laboratory" tr="Kinematik Yapay Zeka Laboratuvarı" badge="Pre / During / Post / Healthy side" />

      <Glass className="p-5">
        <p className="text-sm font-extrabold text-white/80 mb-4">Video Upload & Analysis</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {phases.map((ph) => {
            const status = data[statusKey(ph.k)] || "idle";
            const hasResult = !!kinematicsResults[ph.k];

            return (
              <div key={ph.k} className={`flex flex-col rounded-xl border transition-all overflow-hidden ${status === "analyzing" ? "border-amber-400/40" : hasResult ? "border-emerald-400/30" : "border-white/[0.04]"}`}>
                <div className="flex items-center justify-between px-3 pt-3 pb-2">
                  <div className="flex items-center gap-2">
                    {(hasResult || status === "analyzing") && (
                      <GBtn variant="default" onClick={() => clearPhase(ph.k)} className="text-[10px] py-1 px-1.5 flex items-center justify-center bg-red-500/15 border-white/[0.06] text-red-300 hover:bg-red-500/25" title={status === "analyzing" ? "Cancel analysis" : "Remove"}>
                        <X className="w-3 h-3" />
                      </GBtn>
                    )}
                    <span className={`text-xs font-extrabold uppercase tracking-wider ${
                      ph.c === "sky" ? "text-sky-300" : ph.c === "violet" ? "text-violet-300" : ph.c === "emerald" ? "text-emerald-300" : "text-amber-300"
                    }`}>{ph.l}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {status === "analyzing" && (
                      <span className="text-[9px] px-2 py-0.5 rounded-full bg-amber-400/20 border border-amber-400/30 text-amber-300">Processing...</span>
                    )}
                    {hasResult && (
                      <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-400/20 border border-emerald-400/30 text-emerald-300">\u2713</span>
                    )}
                  </div>
                </div>

                <div className="mx-3 mb-2">
                  <input
                    type="file"
                    accept="video/*,.csv"
                    onChange={(e) => handleFile(ph.k, e.target.files?.[0])}
                    className="w-full text-xs text-white/50 file:mr-2 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-white/10 file:text-white hover:file:bg-white/15"
                  />
                </div>

                <div className="mx-3 mb-3 flex flex-wrap gap-1.5">
                  <GBtn variant={ph.c} onClick={() => analyzeVideo(ph.k)} disabled={status === "analyzing" || !data[vidKey(ph.k)]} className="flex-1 text-xs py-2 min-w-[80px]" title="Analyze">
                    {status === "analyzing" ? <span className="animate-pulse">...</span> : <Play className="w-4 h-4 mx-auto" />}
                  </GBtn>
                  {hasResult && (
                    <div className="flex gap-1">
                      <GBtn variant="default" onClick={() => downloadFile(ph.k, "csv")} className="text-[10px] py-2 px-2.5 flex items-center justify-center" title="CSV data">
                        <FileSpreadsheet className="w-3.5 h-3.5" />
                      </GBtn>
                      <GBtn variant="default" onClick={() => downloadFile(ph.k, "trc")} className="text-[10px] py-2 px-2.5 flex items-center justify-center" title="OpenSim TRC">
                        <Database className="w-3.5 h-3.5" />
                      </GBtn>
                      <GBtn variant="default" onClick={() => downloadFile(ph.k, "mot")} className="text-[10px] py-2 px-2.5 flex items-center justify-center" title="OpenSim MOT (IK)">
                        <Activity className="w-3.5 h-3.5" />
                      </GBtn>
                      <GBtn variant="default" onClick={() => downloadFile(ph.k, "video")} className="text-[10px] py-2 px-2.5 flex items-center justify-center whitespace-nowrap" title="2D Skeleton Video">
                        <span className="text-[10px] font-bold">2D</span>
                      </GBtn>
                    </div>
                  )}
                </div>

                {hasResult && (
                  <div className="mx-3 mb-3 flex justify-center">
                    <button onClick={() => toggleResult(ph.k)} className="text-xs text-white/50 hover:text-white/80 flex items-center justify-center gap-2 py-2 font-medium tracking-wide" title={expandedResults[ph.k] ? "Hide chart" : "Show movement chart"}>
                    {expandedResults[ph.k] ? "\u25B2 Hide" : "Show movement chart \u25BC"}
                  </button>
                  </div>
                )}

                {hasResult && expandedResults[ph.k] && kinematicsResults[ph.k]?.velocity_profile && (
                  <div className="mx-3 mb-3 p-3 rounded-xl bg-white/[0.03]">
                    <p className="text-[9px] font-extrabold uppercase tracking-widest text-white/40 mb-2">Velocity Profile / Hız Profili</p>
                    {(() => {
                      const prof = kinematicsResults[ph.k].velocity_profile;
                      const pts = prof.t.map((t, i) => ({ t, v: prof.v[i] }));
                      const w = 260, h = 60, pad = 4;
                      const tMin = pts[0].t, tMax = pts[pts.length - 1].t, vMax = Math.max(...pts.map(p => p.v), 0.01);
                      const x = (t) => pad + ((t - tMin) / (tMax - tMin || 1)) * (w - 2 * pad);
                      const y = (v) => h - pad - (v / vMax) * (h - 2 * pad);
                      const path = smoothVelPath(pts, x, y);
                      const peak = pts.reduce((a, b) => a.v > b.v ? a : b);
                      return (
                        <svg viewBox={`0 0 ${w} ${h}`} className="w-full max-w-[280px] h-auto" preserveAspectRatio="xMidYMid meet">
                          <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
                          <path d={path} fill="none" stroke="rgba(148,163,184,0.6)" strokeWidth="1.5" />
                          <circle cx={x(peak.t)} cy={y(peak.v)} r="3" fill="rgba(148,163,184,0.9)" />
                          <text x={x(peak.t)} y={y(peak.v) - 6} textAnchor="middle" fill="rgba(148,163,184,0.7)" fontSize="7">{peak.v.toFixed(2)}</text>
                          <text x={pad} y={h - 2} fill="rgba(255,255,255,0.15)" fontSize="6">{tMin.toFixed(1)}s</text>
                          <text x={w - pad} y={h - 2} textAnchor="end" fill="rgba(255,255,255,0.15)" fontSize="6">{tMax.toFixed(1)}s</text>
                        </svg>
                      );
                    })()}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Glass>

      {Object.keys(kinematicsResults).length > 0 && (
        <Glass className="p-5">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-extrabold text-white/80">Kinematic Results</p>
            <GBtn variant="danger" onClick={() => {
              phases.forEach((ph) => clearPhase(ph.k));
              localStorage.removeItem(KIN_LS_KEY);
              localStorage.removeItem(KIN_LS_EXP_KEY);
            }} className="text-[10px] py-1.5 px-3" title="Remove all results">
              <X className="w-3 h-3 mr-1" />
              Clear All
            </GBtn>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/[0.08]">
            <table className="w-full text-sm min-w-[900px]">
              <thead>
                <tr className="border-b border-white/[0.08] bg-white/[0.04]">
                  <th className="text-left px-3 py-3 font-extrabold text-white/40 text-[10px] uppercase w-24">Group</th>
                  <th className="text-left px-4 py-3 font-extrabold text-white/60 text-xs uppercase">Variable</th>
                  <th className="text-left px-3 py-3 font-extrabold text-white/60 text-xs uppercase w-20">Unit</th>
                  {phases.filter((ph) => kinematicsResults[ph.k]).map((ph) => (
                    <th
                      key={ph.k}
                      className={`text-center px-3 py-3 font-extrabold text-xs uppercase ${
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
                  {kinematicsResults.pre && kinematicsResults.baseline && (
                    <th className="text-center px-3 py-3 font-extrabold text-amber-300 text-xs uppercase">
                      vs Healthy side
                    </th>
                  )}
                  {kinematicsResults.pre && kinematicsResults.post && (
                    <th className="text-center px-3 py-3 font-extrabold text-emerald-300 text-xs uppercase">
                      \u0394 Pre\u2192Post
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

                  const deltaPrePost = preVal !== "\u2014" && postVal !== "\u2014"
                    ? calculateClinicalDelta(preVal, postVal, metric.name)
                    : null;

                  const deltaVsBaseline = preVal !== "\u2014" && baselineVal !== "\u2014"
                    ? calculateClinicalDelta(baselineVal, preVal, metric.name)
                    : null;

                  return (
                    <React.Fragment key={metric.key}>
                      {showGroupHeader && (
                        <tr>
                          <td
                            colSpan={
                              3 +
                              phases.filter((ph) => kinematicsResults[ph.k]).length +
                              (kinematicsResults.pre && kinematicsResults.baseline ? 1 : 0) +
                              (kinematicsResults.pre && kinematicsResults.post ? 1 : 0)
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
                        <td className="px-4 py-2.5 font-bold text-white/80 text-sm">
                          {metric.name}
                          {metric.tip && (
                            <span className="group relative inline-flex ml-1.5 align-middle cursor-help">
                              <Info className="w-3 h-3 text-white/30 hover:text-white/60 transition-colors" />
                              <span className="absolute left-0 bottom-full mb-2 hidden group-hover:block z-50 w-72 px-3 py-2 text-[11px] leading-relaxed text-white bg-slate-800/95 border border-white/[0.04] rounded-lg shadow-xl pointer-events-none">
                                ▸ {metric.tip}
                              </span>
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 font-light text-white/40 text-xs">{metric.unit}</td>

                        {phases.filter((ph) => kinematicsResults[ph.k]).map((ph) => (
                          <td key={ph.k} className="px-3 py-2.5 text-center">
                            <span className="text-white/80 font-mono text-sm">
                              {getMetricValue(ph.k, metric.key)}
                            </span>
                          </td>
                        ))}

                        {kinematicsResults.pre && kinematicsResults.baseline && (
                          <td className="px-3 py-2.5 text-center">
                            {deltaVsBaseline ? (
                              <span className={`px-2.5 py-1 text-xs font-bold rounded-lg border ${deltaVsBaseline.colorClass}`}>
                                {deltaVsBaseline.text}
                              </span>
                            ) : (
                              <span className="text-white/20 text-xs">\u2014</span>
                            )}
                          </td>
                        )}

                        {kinematicsResults.pre && kinematicsResults.post && (
                          <td className="px-3 py-2.5 text-center">
                            {deltaPrePost ? (
                              <span className={`px-2.5 py-1 text-xs font-bold rounded-lg border ${deltaPrePost.colorClass}`}>
                                {deltaPrePost.text}
                              </span>
                            ) : (
                              <span className="text-white/20 text-xs">\u2014</span>
                            )}
                          </td>
                        )}
                      </tr>
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Glass>
      )}

      {/* ─── Phase-by-Phase Comparison ─── */}
      {presentPhases.size > 0 && recordingColumns.length >= 2 && (
        <Glass className="p-5 mt-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-violet-300" />
            <p className="text-sm font-extrabold text-white/80">Phase-by-Phase Comparison</p>
            <span className="text-[9px] px-2 py-0.5 rounded-full bg-violet-400/15 border border-violet-400/25 text-violet-300">
              Avoids Simpson&apos;s Paradox
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {['forward', 'wipe_right', 'wipe_left', 'return']
              .filter((pn) => presentPhases.has(pn))
              .map((pn) => {
                const pi = phaseInfo[pn];
                return (
                  <div key={pn} className="rounded-xl border border-white/[0.08] overflow-hidden">
                    <div className={`px-3 py-2 text-xs font-extrabold uppercase tracking-wider bg-white/[0.03] border-b border-white/[0.08] ${
                      pi.color === "sky" ? "text-sky-300" :
                      pi.color === "violet" ? "text-violet-300" :
                      pi.color === "amber" ? "text-amber-300" : "text-rose-300"
                    }`}>
                      {pi.label}
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-white/[0.05] bg-white/[0.02]">
                          <th className="text-left px-3 py-2 font-bold text-white/40 text-[10px] uppercase">Metric</th>
                          {recordingColumns.map((ph) => (
                            <th key={ph.k} className={`text-center px-2 py-2 font-extrabold text-[10px] uppercase ${
                              ph.c === "sky" ? "text-sky-300" :
                              ph.c === "violet" ? "text-violet-300" :
                              ph.c === "emerald" ? "text-emerald-300" : "text-amber-300"
                            }`}>
                              {ph.l}
                            </th>
                          ))}
                          {hasPrePost && (
                            <th className="text-center px-2 py-2 font-extrabold text-[10px] uppercase text-emerald-300">
                              \u0394
                            </th>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {phaseMetrics.map((pm) => {
                          const vals = recordingColumns.map((ph) => getPhaseMetricValue(ph.k, pn, pm.key));

                          let delta = null;
                          if (hasPrePost) {
                            const preVal = parseFloat(getPhaseMetricValue("pre", pn, pm.key));
                            const postVal = parseFloat(getPhaseMetricValue("post", pn, pm.key));
                            if (!isNaN(preVal) && !isNaN(postVal)) {
                              const lowerBetter = pm.key === "pause_pct" || pm.key === "path_ratio" || pm.key === "trunk_palm_ratio";
                              const pctChange = preVal !== 0 ? ((postVal - preVal) / Math.abs(preVal)) * 100 : 0;
                              const improved = lowerBetter ? pctChange < 0 : pctChange > 0;
                              delta = { text: `${pctChange > 0 ? "+" : ""}${pctChange.toFixed(1)}%`, improved };
                            }
                          }

                          return (
                            <tr key={pm.key} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                              <td className="px-3 py-1.5 text-xs font-bold text-white/70">{pm.name}</td>
                              <td className="px-2 py-1.5 text-center text-xs font-mono text-white/80">{vals[0]}</td>
                              {vals.length > 1 && <td className="px-2 py-1.5 text-center text-xs font-mono text-white/80">{vals[1] || "\u2014"}</td>}
                              {vals.length > 2 && <td className="px-2 py-1.5 text-center text-xs font-mono text-white/80">{vals[2] || "\u2014"}</td>}
                              {vals.length > 3 && <td className="px-2 py-1.5 text-center text-xs font-mono text-white/80">{vals[3] || "\u2014"}</td>}
                              {hasPrePost && (
                                <td className="px-2 py-1.5 text-center">
                                  {delta ? (
                                    <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded ${
                                      delta.improved ? "text-emerald-300 bg-emerald-400/10" : "text-red-300 bg-red-400/10"
                                    }`}>
                                      {delta.text}
                                    </span>
                                  ) : (
                                    <span className="text-white/20 text-xs">\u2014</span>
                                  )}
                                </td>
                              )}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                );
              })}
          </div>
        </Glass>
      )}

    </div>
  );
};

// ─── Patient Database ─────────────────────────────────────────────────────────

const DatabaseSection = ({ onLoadSession, showToast }) => {
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState("");
  const [confirm, setConfirm] = useState(null);

  useEffect(() => {
    setPatients(loadPatients());
  }, []);

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

          <GBtn variant="default" onClick={() => setPatients(loadPatients())}>
            <RefreshCw className="w-4 h-4" /> Refresh
          </GBtn>
        </div>
      </Glass>

      {filtered.length === 0 ? (
        <Glass className="p-12 text-center">
          <Database className="w-16 h-16 text-white/10 mx-auto mb-4" />
          <p className="text-white/50 font-semibold text-lg mb-2">
            {search ? "No patients match your search" : "No patient records yet"}
          </p>
          <p className="text-white/25 text-sm">Save a session from any assessment tab to create a record.</p>
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
                        hasPre ? "bg-sky-500/15 border-sky-400/25 text-sky-300" : "bg-white/[0.05] border-white/[0.04] text-white/25"
                      }`}>
                        {hasPre ? "✓ Pre-Assessment" : "○ Pre missing"}
                      </span>

                      <span className={`text-[9px] font-bold px-2 py-1 rounded-full border ${
                        hasPost ? "bg-emerald-500/15 border-emerald-400/25 text-emerald-300" : "bg-white/[0.05] border-white/[0.04] text-white/25"
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
    return (d >= 0 ? "+" : "") + d.toFixed(2);
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
    const improving = (pre !== "—" && post !== "—")
      ? (lowerIsBetter(item.en) ? parseFloat(pre) > parseFloat(post) : parseFloat(post) > parseFloat(pre))
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
    const improving = (pre !== "—" && post !== "—")
      ? (lowerIsBetter(item.en) ? parseFloat(pre) > parseFloat(post) : parseFloat(post) > parseFloat(pre))
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
      const improving = (pre !== "—" && post !== "—") ? parseFloat(post) > parseFloat(pre) : null;
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

    const improvingT = (preT !== "—" && postT !== "—") ? parseFloat(preT) > parseFloat(postT) : null;
    const improvingR = (preR !== "—" && postR !== "—") ? parseFloat(postR) > parseFloat(preR) : null;
    rows.push({ tool:"WMFT", metric:`${t.en} — Time (sec)`, pre:preT, post:postT, delta:calcDelta(preT, postT), improving: improvingT });
    rows.push({ tool:"WMFT", metric:`${t.en} — Ability Rating (0–5)`, pre:preR, post:postR, delta:calcDelta(preR, postR), improving: improvingR });
  });

  // Kinematics
  const kin = fd.kinematics || {};
  const kinDisplay = [
    { k:"movementDuration", en:"Movement Duration (s)" },
    { k:"peakVelocity", en:"Peak Velocity (norm/s)" },
    { k:"meanVelocity", en:"Mean Velocity (norm/s)" },
    { k:"totalPathLength", en:"Total Path Length (norm)" },
    { k:"lateralRange", en:"Lateral Range (norm)" },
    { k:"trunkPalmRatio", en:"Trunk/Palm Ratio" },
    { k:"maxElbowAngle", en:"Max Elbow Angle (deg)" },
    { k:"pauseSmoothness", en:"Pause % (Smoothness)" },
    { k:"armLength", en:"Arm Length (norm)" },
    { k:"shoulderVertExcursion", en:"Shoulder Vertical Excursion (norm)" },
    { k:"trunkLateralFlexion", en:"Trunk Lateral Flexion (norm)" },
    { k:"trunkForwardFlexion", en:"Trunk Forward Flexion (norm)" },
  ];
  kinDisplay.forEach((item) => {
    const pre = v(kin.pre?.[item.k]);
    const post = v(kin.post?.[item.k]);
    const improving = (pre !== "—" && post !== "—")
      ? (lowerIsBetter(item.en) ? parseFloat(pre) > parseFloat(post) : parseFloat(post) > parseFloat(pre))
      : null;
    rows.push({ tool:"Kinematics", metric:item.en, pre, post, delta:calcDelta(pre, post, item.en), improving });
  });

  return rows;
}

// ─── SPSS Export Helper ───────────────────────────────────────────────────────

function buildSPSSData(fd) {
  const d = fd.demographics || {};
  if (!d.participantId && !d.name) return [];

  const row = {};

  // ── Demographics ──
  row.ID = d.participantId || "";
  row.Group = d.group || "";
  row.Age = d.age || "";
  row.Sex = d.sex || "";
  row.TimeSinceStroke = d.timeSinceStroke || "";
  row.StrokeType = d.strokeType || "";
  row.AffectedSide = d.side || "";
  row.MAS = d.mas ?? "";
  row.MRC = d.mrc ?? "";

  // ── Kinematics: Pre + Post only ──
  const kin = fd.kinematics || {};
  const kinMap = {
    smoothness: "smoothness_pause_pct",
    duration: "total_duration_s",
    peakVel: "total_peak_velocity",
    meanVel: "total_mean_velocity",
    pathLen: "total_path_length",
    latRange: "total_lat_range_norm",
    trunkPalm: "total_trunk_palm_ratio",
    elbow: "total_max_elbow_deg",
    shoulderDep: "total_depression_cm",
    trunkLat: "trunk_lat_norm",
    trunkVert: "trunk_vert_norm",
  };
  ["pre", "post"].forEach((tp) => {
    const result = kin[`result_${tp}`] || {};
    Object.entries(kinMap).forEach(([newName, oldKey]) => {
      row[`${newName}_${tp === "pre" ? "Pre" : "Post"}`] = result[oldKey] ?? "";
    });
  });

  // ── WMFT total (sum of ratings) ──
  const wmft = fd.wmft || {};
  let wmftPre = 0, wmftPost = 0, wmftC = 0;
  WMFT_ITEMS.forEach((t) => {
    const pre = parseFloat(wmft[t.id]?.pre?.rating);
    const post = parseFloat(wmft[t.id]?.post?.rating);
    if (!isNaN(pre)) { wmftPre += pre; wmftC++; }
    if (!isNaN(post)) { wmftPost += post; }
  });
  row.WMFT_Pre = wmftC > 0 ? wmftPre : "";
  row.WMFT_Post = wmftC > 0 ? wmftPost : "";

  const vams = fd.vams || {};
  ["happy", "sad", "calm", "tense"].forEach((k) => {
    row[`VAMS_${k.charAt(0).toUpperCase() + k.slice(1)}_Pre`] = vams[k]?.pre ?? "";
    row[`VAMS_${k.charAt(0).toUpperCase() + k.slice(1)}_Post`] = vams[k]?.post ?? "";
  });

  // ── KVIQ Visual & Kinesthetic totals ──
  const kgia = fd.kgia || {};
  let visPre = 0, visPost = 0, kinPre = 0, kinPost = 0;
  let visC = 0, kinC = 0;
  KGIA_MOVEMENTS.forEach((_, mi) => {
    const v = kgia[`${mi}_gorsel`];
    if (v) {
      const p = parseFloat(v.once);
      const q = parseFloat(v.sonra);
      if (!isNaN(p)) { visPre += p; visC++; }
      if (!isNaN(q)) { visPost += q; }
    }
    const k = kgia[`${mi}_kinestetik`];
    if (k) {
      const p = parseFloat(k.once);
      const q = parseFloat(k.sonra);
      if (!isNaN(p)) { kinPre += p; kinC++; }
      if (!isNaN(q)) { kinPost += q; }
    }
  });
  row.KVIQ_Vis_Pre = visC > 0 ? visPre : "";
  row.KVIQ_Vis_Post = visC > 0 ? visPost : "";
  row.KVIQ_Kin_Pre = kinC > 0 ? kinPre : "";
  row.KVIQ_Kin_Post = kinC > 0 ? kinPost : "";

  // ── IPAQ total MET ──
  const ipaq = fd.ipaq || {};
  let totalMET = 0;
  IPAQ_ACTS.forEach((a) => {
    const mins = parseFloat(ipaq[a.id]?.sure) || 0;
    const days = parseFloat(ipaq[a.id]?.gun) || 0;
    totalMET += mins * days * a.met;
  });
  row.IPAQ_Pre = totalMET > 0 ? totalMET.toFixed(0) : "";

  // ── VAS Pain (average of rest/activity/night) ──
  const vas = fd.vas || {};
  let vasPre = 0, vasPost = 0, vasPreC = 0, vasPostC = 0;
  ["rest", "activity", "night"].forEach((k) => {
    const p = parseFloat(vas[k]?.pre);
    const q = parseFloat(vas[k]?.post);
    if (!isNaN(p)) { vasPre += p; vasPreC++; }
    if (!isNaN(q)) { vasPost += q; vasPostC++; }
  });
  row.VAS_Pre = vasPreC > 0 ? (vasPre / vasPreC).toFixed(1) : "";
  row.VAS_Post = vasPostC > 0 ? (vasPost / vasPostC).toFixed(1) : "";

  // ── MDRS (post only) ──
  const mc = fd.motorchange || {};
  row.MDRS_Post = mc.difference ?? "";

  return [row];
}

// ─── Report Section ───────────────────────────────────────────────────────────

const ReportSection = ({ fd }) => {
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
    const phaseLabels = { pre: "Pre", during: "During", post: "Post", baseline: "Healthy side" };
    const vars = [
      { key: "total_duration_s", label: "Movement Duration", unit: "s" },
      { key: "total_peak_velocity", label: "Peak Velocity", unit: "norm/s" },
      { key: "total_mean_velocity", label: "Mean Velocity", unit: "norm/s" },
      { key: "total_path_length", label: "Total Path Length", unit: "norm" },
      { key: "total_lat_range_norm", label: "Lateral Range", unit: "norm" },
      { key: "total_trunk_palm_ratio", label: "Trunk/Palm Ratio", unit: "" },
      { key: "total_max_elbow_deg", label: "Max Elbow Angle", unit: "deg" },
      { key: "smoothness_pause_pct", label: "Pause % (Smoothness)", unit: "%" },
      { key: "arm_length_norm", label: "Arm Length", unit: "norm" },
      { key: "shoulder_width_norm", label: "Shoulder Width", unit: "norm" },
      { key: "shoulder_vert_norm", label: "Shoulder Vertical Excursion", unit: "norm" },
      { key: "trunk_lat_norm", label: "Trunk Lateral Flexion", unit: "norm" },
      { key: "trunk_vert_norm", label: "Trunk Forward Flexion", unit: "norm" },
    ];
    const phases = ["pre", "post", "during", "baseline"].filter((p) => kr[p]);
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
    return { headers, body };
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
        if (items.some((r) => r.improving)) { en.push("Muscle control improved"); tr.push("Kas kontrolü iyileşti"); }
        else { en.push("Muscle control stable"); tr.push("Kas kontrolü sabit"); }
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

    const deltaCell = (r) => {
      if (!r.delta || r.delta === "\u2014") return `<span class="delta neutral">\u2014</span>`;
      const cls = r.improving === true ? "up" : r.improving === false ? "down" : "neutral";
      return `<span class="delta ${cls}">${esc(r.delta)}</span>`;
    };

    let toolSections = "";
    Object.entries(grouped).forEach(([tool, trows]) => {
      const meta = toolMeta[tool] || { label: tool, color: "#0d9488" };
      const body = trows.map((r) => `
        <tr>
          <td class="metric">${esc(r.metric)}</td>
          <td class="num">${esc(r.pre)}</td>
          <td class="num">${esc(r.post)}</td>
          <td class="num">${deltaCell(r)}</td>
        </tr>`).join("");
      const interp = buildToolInterp(tool, trows);
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

    // velocity profiles — MUST be defined before videoSection below
    let kr2; try { kr2 = JSON.parse(localStorage.getItem(KIN_LS_KEY)) || {}; } catch { kr2 = {}; }
    const velImgs = ["pre","post","baseline"]
      .filter((p) => kr2[p]?.velocity_profile)
      .map((p) => {
        const lbl = { pre:"Pre", post:"Post", baseline:"Healthy side" }[p];
        const prof = kr2[p].velocity_profile;
        if (!prof?.t || prof.t.length < 2) return "";
        const w = 800, h = 220, pad = 40;
        const tMin = prof.t[0], tMax = prof.t[prof.t.length - 1];
        const vMax = Math.max(...prof.v, 0.01);
        const xp = (t) => pad + ((t - tMin) / (tMax - tMin || 1)) * (w - 2 * pad);
        const yp = (v) => h - pad - (v / vMax) * (h - 2 * pad);
        const path = prof.t.map((t, i) => `${i === 0 ? "M" : "L"}${xp(t).toFixed(1)},${yp(prof.v[i]).toFixed(1)}`).join(" ");
        return `<div class="velcard" style="flex:1">
          <div class="vellabel">${esc(lbl)}</div>
          <svg viewBox="0 0 ${w} ${h}" width="100%">
            <line x1="${pad}" y1="${h-pad}" x2="${w-pad}" y2="${h-pad}" stroke="#e2e8f0" stroke-width="2"/>
            <path d="${path}" fill="none" stroke="#0d9488" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>`;
      }).join("");
    let velSection = velImgs ? `<div class="singlecol"><div class="card"><div class="badge" style="background:#0d948888">Velocity Profiles</div><div class="velrow">${velImgs}</div></div></div>` : "";

    // video kinematics
    const videoKin = buildVideoKinRows();
    let videoSection = "";
    if (videoKin) {
      const fBody = videoKin.body.filter((row) => !String(row[0]).toLowerCase().includes("shoulder width"));
      const head = videoKin.headers.map((h) => `<th>${esc(h)}</th>`).join("");
      const body = fBody.map((row) => `<tr>${row.map((c, i) => `<td class="${i < 2 ? "metric" : "num"}">${esc(c)}</td>`).join("")}</tr>`).join("");
      videoSection = `
        <div class="singlecol">
        <div class="card">
          <div class="badge" style="background:#0d948888">Video Kinematic Analysis</div>
          <div class="tblwrap">
          <table><thead><tr style="background:#0d948888;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)">${head}</tr></thead><tbody>${body}</tbody></table>
          </div>
        </div>
        ${velImgs ? `<div class="card"><div class="badge" style="background:#0d948888">Velocity Profiles</div><div class="velrow">${velImgs}</div></div>` : ""}
        </div>`;
      // remove velSection since it's now inside videoSection
      velSection = "";
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

    const html = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Clinical Report - ${esc(d.name || "Participant")}</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',system-ui,-apple-system,sans-serif; }
  body { background:linear-gradient(135deg,#f0fdfa 0%,#e0f2fe 100%); color:#1e293b; padding:28px; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
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

  .singlecol .card { break-inside:avoid; page-break-inside:avoid; background:rgba(255,255,255,0.65); backdrop-filter:blur(40px) saturate(180%); -webkit-backdrop-filter:blur(40px) saturate(180%); border:1px solid rgba(255,255,255,0.3); border-radius:1rem; box-shadow:0 25px 50px -8px rgba(0,0,0,0.10); padding:18px 22px; margin-bottom:20px; }
  .pagebreak { break-before:page; page-break-before:always; }

  .interp { font-size:12px; line-height:1.8; color:#334155; }
  @media print {
    body { -webkit-print-color-adjust:exact !important; print-color-adjust:exact !important; background:linear-gradient(135deg,#f0fdfa 0%,#e0f2fe 100%) !important; padding:16px; }
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
  </div>
  <div class="tools">${toolSections}</div>
  ${videoSection}
  ${velSection}
  ${buildSummaryInterp()}
</div>
<script>window.onload = () => { setTimeout(() => window.print(), 400); };</script>
</body></html>`;

    const win = window.open("", "_blank");
    if (!win) { alert("Please allow pop-ups to export the report / Lütfen raporu dışa aktarmak için açılır pencerelere izin verin"); return; }
    win.document.write(html);
    win.document.close();
    } catch (e) { alert("Report error: " + e.message); } };

  // ── PDF Export (jsPDF fallback) ──
  const exportPDF = () => {
    const doc = new jsPDF({ orientation:"portrait", unit:"mm", format:"a4" });

    // Helper: render velocity profile to a canvas data URL
    const renderVelProfile = (profile, label) => {
      if (!profile || !profile.t || profile.t.length < 2) return null;
      const pts = profile.t.map((t, i) => ({ t, v: profile.v[i] }));
      const w = 1800, h = 400, pad = 60;
      const tMin = pts[0].t, tMax = pts[pts.length - 1].t;
      const vMax = Math.max(...pts.map(p => p.v), 0.01);
      const xp = (t) => pad + ((t - tMin) / (tMax - tMin || 1)) * (w - 2 * pad);
      const yp = (v) => h - pad - (v / vMax) * (h - 2 * pad);
      const path = smoothVelPath(pts, xp, yp);
      const peak = pts.reduce((a, b) => a.v > b.v ? a : b);

      const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">
        <rect width="${w}" height="${h}" fill="#f8fafc"/>
        <text x="${pad}" y="${pad - 10}" font-family="Helvetica,Arial,sans-serif" font-size="28" font-weight="bold" fill="#1e293b">${label}</text>
        <line x1="${pad}" y1="${h - pad}" x2="${w - pad}" y2="${h - pad}" stroke="#e2e8f0" stroke-width="2"/>
        <path d="${path}" fill="none" stroke="#0d9488" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="${xp(peak.t)}" cy="${yp(peak.v)}" r="8" fill="#0d9488" stroke="white" stroke-width="3"/>
        <text x="${xp(peak.t)}" y="${yp(peak.v) - 20}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="24" fill="#0f766e" font-weight="bold">${peak.v.toFixed(2)}</text>
        <text x="${pad}" y="${h - pad + 40}" font-family="Helvetica,Arial,sans-serif" font-size="22" fill="#94a3b8">${tMin.toFixed(1)}s</text>
        <text x="${w - pad}" y="${h - pad + 40}" text-anchor="end" font-family="Helvetica,Arial,sans-serif" font-size="22" fill="#94a3b8">${tMax.toFixed(1)}s</text>
        <text x="${w/2}" y="${h - pad + 40}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="22" fill="#94a3b8">Time (s)</text>
        <text x="${pad - 40}" y="${h/2}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="22" fill="#94a3b8" transform="rotate(-90,${pad - 40},${h/2})">Velocity (norm/s)</text>
      </svg>`;
      return "data:image/svg+xml;base64," + btoa(svg);
    };

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

    // ── Velocity profiles ─────────────────────────────────────────
    let kr2;
    try { kr2 = JSON.parse(localStorage.getItem(KIN_LS_KEY)) || {}; } catch { kr2 = {}; }
    const kinPhases = ["pre","post","baseline"].filter((p) => kr2[p]?.velocity_profile);
    if (kinPhases.length > 0) {
      y = checkPage(y, 60);
      rr(M, y, CW, 0.1, R, null, C.gray300); y += 1.5;
      sectionBadge("Velocity Profiles", M + 4, y + 3, C.teal);
      y += 8;
      kinPhases.forEach((ph) => {
        const lbl = { pre:"Pre", post:"Post", baseline:"Healthy side" }[ph];
        const img = renderVelProfile(kr2[ph]?.velocity_profile, lbl);
        if (img) {
          y = checkPage(y, 54);
          rr(M + 4, y, CW - 8, 44, R2, C.white, C.gray200);
          try { doc.addImage(img, "SVG", M + 4, y, CW - 8, 44); y += 48; } catch {}
        }
      });
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
          ["Variable", "Unit", "Pre", "During", "Post", "Δ"],
          ...kinRows.map((r) => [r.name || "", r.unit || "", r.pre || "", r.during || "", r.post || "", calcKinDelta(r.pre, r.post)]),
        ]),
        "Kinematics"
      );
    }

    XLSX.writeFile(wb, `research_data_${d.participantId || "participant"}_${new Date().toISOString().split("T")[0]}.xlsx`);
  };

  // ── SPSS Export (all patients) ──
  const exportSPSS = () => {
    const allPts = loadPatients();
    if (allPts.length === 0) { return; }

    const rows = [];
    allPts.forEach((pt) => {
      const built = buildSPSSData(pt);
      if (built.length > 0) rows.push(built[0]);
    });
    if (rows.length === 0) { return; }

    const ws = XLSX.utils.json_to_sheet(rows);
    const csvData = XLSX.utils.sheet_to_csv(ws);
    const blob = new Blob(["\uFEFF" + csvData], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `spss_data_${allPts.length}patients_${new Date().toISOString().split("T")[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // ── JSON Export (all patients) ──
  const exportJSON = () => {
    const allPts = loadPatients();
    if (allPts.length === 0) { return; }
    const clean = allPts.map(({ _id, _savedAt, _hasPre, _hasPost, ...rest }) => rest);
    const blob = new Blob([JSON.stringify(clean, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `neuro_data_${allPts.length}patients_${new Date().toISOString().split("T")[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // ── SPSS Syntax (.sps) export ──
  const exportSPSSyntax = () => {
    const vars = [
      { n:"ID", l:"Study ID", m:"nominal", v:"" },
      { n:"Group", l:"Group (1=AOMI, 2=Control)", m:"nominal", v:"1 'AOMI' 2 'Control'" },
      { n:"Age", l:"Age (years)", m:"scale", v:"" },
      { n:"Sex", l:"Sex (1=Male, 2=Female)", m:"nominal", v:"1 'Male' 2 'Female'" },
      { n:"TimeSinceStroke", l:"Time since stroke (months)", m:"scale", v:"" },
      { n:"StrokeType", l:"Stroke type (1=Ischemic, 2=Hemorrhagic)", m:"nominal", v:"1 'Ischemic' 2 'Hemorrhagic'" },
      { n:"AffectedSide", l:"Affected side (1=Left, 2=Right)", m:"nominal", v:"1 'Left' 2 'Right'" },
      { n:"MAS", l:"Modified Ashworth Scale", m:"ordinal", v:"0 'No increase' 1 'Slight catch' \"1+\" 'Catch+resistance' 2 'More marked' 3 'Considerable' 4 'Rigid'" },
      { n:"MRC", l:"MRC Muscle Strength", m:"ordinal", v:"2 'Gravity eliminated' 3 'Against gravity' 4 'Some resistance' 5 'Normal'" },
    ];
    const kMap = { smoothness:"Smoothness Pause %", duration:"Movement Duration (s)", peakVel:"Peak Velocity (norm/s)", meanVel:"Mean Velocity (norm/s)", pathLen:"Path Length (norm)", latRange:"Lateral Range (norm)", trunkPalm:"Trunk/Palm Ratio", elbow:"Max Elbow Angle (deg)", shoulderDep:"Shoulder Depression (cm)", trunkLat:"Trunk Lateral (norm)", trunkVert:"Trunk Vertical (norm)" };
    Object.entries(kMap).forEach(([k, lbl]) => { vars.push({ n:`${k}_Pre`, l:`${lbl} - Pre`, m:"scale", v:"" }); vars.push({ n:`${k}_Post`, l:`${lbl} - Post`, m:"scale", v:"" }); });
    const clinVars = [
      ["WMFT_Pre","WMFT-SF Total - Pre"],["WMFT_Post","WMFT-SF Total - Post"],
      ["KVIQ_Vis_Pre","KVIQ Visual Total - Pre"],["KVIQ_Vis_Post","KVIQ Visual Total - Post"],
      ["KVIQ_Kin_Pre","KVIQ Kinesthetic Total - Pre"],["KVIQ_Kin_Post","KVIQ Kinesthetic Total - Post"],
    ];
    ["Happy","Sad","Calm","Tense"].forEach((e) => { clinVars.push([`VAMS_${e}_Pre`,`VAMS ${e} - Pre`],[`VAMS_${e}_Post`,`VAMS ${e} - Post`]); });
    clinVars.push(["IPAQ_Pre","IPAQ Total MET-min/week"]);
    clinVars.push(["VAS_Pre","VAS Pain (avg) - Pre"],["VAS_Post","VAS Pain (avg) - Post"]);
    clinVars.push(["MDRS_Post","Motor Difference Rating Scale - Post"]);
    clinVars.forEach(([n, l]) => vars.push({ n, l, m:"scale", v:"" }));

    let syn = "* SPSS Syntax - Auto-generated by NeuroLab Platform.\n* Variable Labels, Value Labels, and Measure Level.\n\n";
    syn += "VARIABLE LABELS\n";
    vars.forEach((v) => { syn += `  ${v.n} '${v.l}'.\n`; });
    syn += "\nVALUE LABELS\n";
    vars.filter((v) => v.v).forEach((v) => { syn += `  ${v.n} ${v.v}.\n`; });
    syn += "\nVARIABLE LEVEL";
    vars.forEach((v) => { syn += `\n  ${v.n} (${v.m.toUpperCase()})`; });
    syn += ".\n\nEXECUTE.\n";

    const blob = new Blob(["\uFEFF" + syn], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `neuro_variable_syntax.sps`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
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

      {/* Clinical Summary Dashboard */}
      <Glass className="p-5">
        <div className="flex items-start gap-3 mb-5">
          <BarChart3 className="w-5 h-5 text-amber-300 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-extrabold text-white/90">Clinical Summary Dashboard</p>
            <p className="text-xs font-light text-white/40 mt-0.5">All assessment tools · Pre vs Post results · Auto-calculated Δ</p>
          </div>
        </div>

        {tools.map((tool) => {
          const toolRows = rows.filter((r) => r.tool === tool);
          const tc = toolColor[tool] || "text-white/60 bg-white/[0.05] border-white/[0.04]";

          return (
            <div key={tool} className="mb-6">
              <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border mb-3 text-xs font-bold ${tc}`}>
                {tool}
              </div>

              <div className="overflow-x-auto rounded-xl border border-white/[0.08]">
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
                    {toolRows.map((row, i) => {
                      const dVal = row.delta;
                      const imp = row.improving;

                      return (
                        <tr key={i} className={`border-b border-white/[0.05] hover:bg-white/[0.03] ${i % 2 === 0 ? "" : "bg-white/[0.02]"}`}>
                          <td className="px-4 py-2.5 text-xs text-white/75 font-medium">{row.metric}</td>

                          <td className="px-3 py-2.5 text-center">
                            <span className="px-2.5 py-1 rounded-lg border bg-sky-500/10 border-sky-400/20 text-sky-200 text-xs font-bold">
                              {row.pre}
                            </span>
                          </td>

                          <td className="px-3 py-2.5 text-center">
                            <span className="px-2.5 py-1 rounded-lg border bg-emerald-500/10 border-emerald-400/20 text-emerald-200 text-xs font-bold">
                              {row.post}
                            </span>
                          </td>

                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-2.5 py-1 rounded-lg text-xs font-extrabold border ${
                                dVal === "—"
                                  ? "text-white/25 bg-white/[0.03] border-white/[0.06]"
                                  : imp === true
                                  ? "text-emerald-300 bg-emerald-500/15 border-emerald-400/25"
                                  : imp === false
                                  ? "text-rose-300 bg-rose-500/15 border-rose-400/25"
                                  : "text-white/40 bg-white/[0.05] border-white/[0.08]"
                              }`}
                            >
                              {dVal}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
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
            <div className="overflow-x-auto rounded-xl border border-white/[0.08] mb-5">
              <table className="w-full text-sm min-w-[560px]">
                <thead>
                  <tr className="bg-white/[0.04] border-b border-white/[0.08]">
                    <th className="text-left px-4 py-2.5 text-xs font-extrabold text-white/50 uppercase">Variable</th>
                    <th className="text-left px-3 py-2.5 text-xs font-extrabold text-white/50 uppercase">Unit</th>
                    <th className="text-center px-3 py-2.5 text-sky-300 uppercase">Pre</th>
                    <th className="text-center px-3 py-2.5 text-violet-300 uppercase">During</th>
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
                        <span className="px-2.5 py-1 rounded-lg border bg-violet-500/10 border-violet-400/20 text-violet-200 text-xs font-bold">
                          {r.during || "—"}
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
                            calcKinDelta(r.pre, r.post) === "—"
                              ? "text-white/25 bg-white/[0.03] border-white/[0.06]"
                              : calcKinDelta(r.pre, r.post).startsWith("+")
                              ? "text-emerald-300 bg-emerald-500/15 border-emerald-400/25"
                              : "text-rose-300 bg-rose-500/15 border-rose-400/25"
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
        const phaseLabels = { pre: "Pre", during: "During", post: "Post", baseline: "Healthy side" };
        return (
          <Glass className="p-5 border-l-2 border-blue-400/40">
            <div className="flex items-start gap-3 mb-5">
              <Activity className="w-5 h-5 text-blue-300 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-extrabold text-white/90">Video Kinematic Analysis</p>
                <p className="text-xs font-light text-white/40 mt-0.5">Per-video kinematic metrics from pose estimation</p>
              </div>
            </div>
            <div className="overflow-x-auto rounded-xl border border-white/[0.08]">
              <table className="w-full text-sm min-w-[560px]">
                <thead>
                  <tr className="bg-white/[0.04] border-b border-white/[0.08]">
                    <th className="text-left px-4 py-2.5 text-xs font-extrabold text-white/50 uppercase">Variable</th>
                    <th className="text-left px-3 py-2.5 text-xs font-extrabold text-white/50 uppercase">Unit</th>
                    {videoKin.headers.slice(2).map((h, i) => (
                      <th key={i} className="text-center px-3 py-2.5 uppercase text-xs font-extrabold" style={{ color: h === "Pre" ? "#7dd3fc" : h === "Post" ? "#6ee7b7" : h === "Healthy side" ? "#fcd34d" : "#c4b5fd" }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {videoKin.body.map((row, i) => (
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
                    </tr>
                  ))}
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
                <p className="font-extrabold text-violet-200 text-sm">Export SPSS Ready</p>
                <p className="text-[10px] text-violet-300/60">CSV + all patients</p>
              </div>
            </div>
            <p className="text-xs text-white/45 leading-relaxed">
              Flat CSV ready to import into SPSS. All patients combined with pre/post columns.
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

const AnalysisDashboard = () => {
  const pts = loadPatients();
  const n = pts.length;
  const aomi = pts.filter((p) => p.demographics?.group === "1");
  const ctrl = pts.filter((p) => p.demographics?.group === "2");

  const kinVars = ["smoothness","duration","peakVel","meanVel","pathLen","latRange","trunkPalm","elbow","shoulderDep","trunkLat","trunkVert"];
  const kinLabels = { smoothness:"Smoothness (%)", duration:"Duration (s)", peakVel:"Peak Vel (n/s)", meanVel:"Mean Vel (n/s)", pathLen:"Path Len (n)", latRange:"Lat Range (n)", trunkPalm:"Trunk/Palm", elbow:"Elbow (°)", shoulderDep:"Sh Depression (cm)", trunkLat:"Trunk Lat (n)", trunkVert:"Trunk Vert (n)" };
  const kinMap = { smoothness:"smoothness_pause_pct", duration:"total_duration_s", peakVel:"total_peak_velocity", meanVel:"total_mean_velocity", pathLen:"total_path_length", latRange:"total_lat_range_norm", trunkPalm:"total_trunk_palm_ratio", elbow:"total_max_elbow_deg", shoulderDep:"total_depression_cm", trunkLat:"trunk_lat_norm", trunkVert:"trunk_vert_norm" };

  const getVals = (group, tp, v) => {
    const arr = [];
    group.forEach((pt) => {
      const k = pt.kinematics?.[`result_${tp}`] || {};
      const val = parseFloat(k[kinMap[v]]);
      if (!isNaN(val)) arr.push(val);
    });
    return arr;
  };

  const calcStats = (group, tp) => {
    const stats = {};
    kinVars.forEach((v) => {
      const arr = getVals(group, tp, v);
      if (arr.length < 2) { stats[v] = null; return; }
      stats[v] = { mean: _mean(arr).toFixed(2), sd: _sd(arr).toFixed(2), n: arr.length };
    });
    return stats;
  };

  const preAomi = calcStats(aomi, "pre");
  const preCtrl = calcStats(ctrl, "pre");
  const postAomi = calcStats(aomi, "post");
  const postCtrl = calcStats(ctrl, "post");

  const missingFields = [];
  pts.forEach((pt) => {
    const d = pt.demographics || {};
    if (!d.participantId) missingFields.push({ id: d.participantId || "?", field: "Study ID" });
    if (!d.group) missingFields.push({ id: d.participantId || "?", field: "Group" });
    if (!d.age) missingFields.push({ id: d.participantId || "?", field: "Age" });
    if (!d.sex) missingFields.push({ id: d.participantId || "?", field: "Sex" });
  });

  // ── Normality Check ──
  const normalityResults = {};
  kinVars.forEach((v) => {
    ["pre","post"].forEach((tp) => {
      ["aomi","ctrl"].forEach((g) => {
        const group = g === "aomi" ? aomi : ctrl;
        const key = `${v}_${tp}_${g}`;
        const arr = getVals(group, tp, v);
        normalityResults[key] = _normalityCheck(arr);
      });
    });
  });

  // ── Preliminary Analysis ──
  const prelimResults = {};
  kinVars.forEach((v) => {
    const aPre = getVals(aomi, "pre", v);
    const aPost = getVals(aomi, "post", v);
    const cPre = getVals(ctrl, "pre", v);
    const cPost = getVals(ctrl, "post", v);
    const deltaA = aPre.length === aPost.length && aPre.length > 0 ? aPre.map((x, i) => aPost[i] - x) : [];
    const deltaC = cPre.length === cPost.length && cPre.length > 0 ? cPre.map((x, i) => cPost[i] - x) : [];

    const withinA = (aPre.length > 1 && aPost.length > 1 && aPre.length === aPost.length) ? _ttestPaired(aPost, aPre) : null;
    const withinC = (cPre.length > 1 && cPost.length > 1 && cPre.length === cPost.length) ? _ttestPaired(cPost, cPre) : null;
    const between = (deltaA.length > 1 && deltaC.length > 1) ? _ttestWelch(deltaA, deltaC) : null;
    const baseline = (aPre.length > 1 && cPre.length > 1) ? _ttestWelch(aPre, cPre) : null;

    prelimResults[v] = { withinA, withinC, between, baseline, deltaA, deltaC };
  });

  return (
    <div className="space-y-5">
      <SH icon={BarChart3} en="Analysis Dashboard" tr="Analiz Paneli" badge="v6.4" />

      {/* Enrollment */}
      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Enrollment / Kayıt</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "Total / Toplam", val: n, color: "text-white" },
            { label: "AOMI (n)", val: aomi.length, color: "text-teal-300" },
            { label: "Control (n)", val: ctrl.length, color: "text-rose-300" },
            { label: "Completion %", val: n > 0 ? Math.round((aomi.length + ctrl.length) / n * 100) : 0, color: "text-amber-300" },
          ].map((item) => (
            <div key={item.label} className="p-4 rounded-xl bg-white/[0.04] border border-white/[0.06] text-center">
              <p className={`text-2xl font-black ${item.color}`}>{item.val}</p>
              <p className="text-[10px] text-white/40 font-bold uppercase tracking-widest mt-1">{item.label}</p>
            </div>
          ))}
        </div>
      </Glass>

      {/* Descriptive Stats */}
      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Mean ± SD Per Group / Grup Başına Ort ± SS</p>
        <div className="overflow-x-auto rounded-xl border border-white/[0.08]">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-white/[0.04] border-b border-white/[0.08]">
                <th className="text-left px-3 py-2 font-extrabold text-white/50 uppercase">Variable</th>
                <th className="text-center px-3 py-2 font-extrabold text-sky-300 uppercase">AOMI Pre</th>
                <th className="text-center px-3 py-2 font-extrabold text-emerald-300 uppercase">AOMI Post</th>
                <th className="text-center px-3 py-2 font-extrabold text-rose-300 uppercase">Ctrl Pre</th>
                <th className="text-center px-3 py-2 font-extrabold text-amber-300 uppercase">Ctrl Post</th>
              </tr>
            </thead>
            <tbody>
              {kinVars.map((v) => {
                const aPre = preAomi[v], aPost = postAomi[v], cPre = preCtrl[v], cPost = postCtrl[v];
                if (!aPre && !cPre) return null;
                const fmt = (s) => s ? `${s.mean} ± ${s.sd}` : "—";
                return (
                  <tr key={v} className="border-b border-white/[0.04]">
                    <td className="px-3 py-2 text-white/70 font-medium">{kinLabels[v]}</td>
                    <td className="px-3 py-2 text-center text-white/60">{fmt(aPre)}</td>
                    <td className="px-3 py-2 text-center text-white/60">{fmt(aPost)}</td>
                    <td className="px-3 py-2 text-center text-white/60">{fmt(cPre)}</td>
                    <td className="px-3 py-2 text-center text-white/60">{fmt(cPost)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Glass>

      {/* Normality Check */}
      {aomi.length >= 2 && ctrl.length >= 2 && (
        <Glass className="p-5">
          <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Normality Check (Skewness/Kurtosis) / Normallik Kontrolü</p>
          <p className="text-[10px] text-white/30 mb-3">🟢 Normal (|skew|&lt;2 & |kurtosis|&lt;7) → Parametric · 🔴 Non-normal → Non-parametric</p>
          <div className="overflow-x-auto rounded-xl border border-white/[0.08]">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-white/[0.04] border-b border-white/[0.08]">
                  <th className="text-left px-3 py-2 font-extrabold text-white/50 uppercase">Variable</th>
                  <th className="text-center px-3 py-2 font-extrabold text-white/40 uppercase">AOMI Pre</th>
                  <th className="text-center px-3 py-2 font-extrabold text-white/40 uppercase">AOMI Post</th>
                  <th className="text-center px-3 py-2 font-extrabold text-white/40 uppercase">Ctrl Pre</th>
                  <th className="text-center px-3 py-2 font-extrabold text-white/40 uppercase">Ctrl Post</th>
                </tr>
              </thead>
              <tbody>
                {kinVars.map((v) => {
                  const c = (g, tp) => normalityResults[`${v}_${tp}_${g}`];
                  const aPre = c("aomi","pre"), aPost = c("aomi","post"), cPre = c("ctrl","pre"), cPost = c("ctrl","post");
                  if (!aPre && !cPre) return null;
                  const fmt = (r) => r ? (r.normal ? "🟢" : "🔴") : "—";
                  return (
                    <tr key={v} className="border-b border-white/[0.04]">
                      <td className="px-3 py-2 text-white/70 font-medium">{kinLabels[v]}</td>
                      <td className="px-3 py-2 text-center text-white/60">{fmt(aPre)}</td>
                      <td className="px-3 py-2 text-center text-white/60">{fmt(aPost)}</td>
                      <td className="px-3 py-2 text-center text-white/60">{fmt(cPre)}</td>
                      <td className="px-3 py-2 text-center text-white/60">{fmt(cPost)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Glass>
      )}

      {/* Preliminary Analysis */}
      {aomi.length >= 2 && ctrl.length >= 2 && (
        <Glass className="p-5">
          <div className="flex items-start gap-3 mb-4">
            <div className="flex-1">
              <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest">Preliminary Analysis / Ön Analiz</p>
              <p className="text-[10px] text-amber-400/80 font-bold mt-1">⚠ PRELIMINARY — Not for publication · Use SPSS for final analysis</p>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/[0.08]">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-white/[0.04] border-b border-white/[0.08]">
                  <th className="text-left px-3 py-2 font-extrabold text-white/50 uppercase">Variable</th>
                  <th className="text-center px-3 py-2 font-extrabold text-sky-300 uppercase">Baseline p</th>
                  <th className="text-center px-3 py-2 font-extrabold text-teal-300 uppercase">AOMI Δ p</th>
                  <th className="text-center px-3 py-2 font-extrabold text-rose-300 uppercase">Ctrl Δ p</th>
                  <th className="text-center px-3 py-2 font-extrabold text-amber-300 uppercase">Between Δ p</th>
                  <th className="text-center px-3 py-2 font-extrabold text-violet-300 uppercase">Cohen's d</th>
                </tr>
              </thead>
              <tbody>
                {kinVars.map((v) => {
                  const r = prelimResults[v];
                  if (!r) return null;
                  const fmtP = (x) => x ? (x.p < 0.001 ? "&lt;0.001" : x.p.toFixed(3)) : "—";
                  const fmtD = (x) => x ? (x.d ? Math.abs(x.d).toFixed(2) : (x.dz ? Math.abs(x.dz).toFixed(2) : "—")) : "—";
                  return (
                    <tr key={v} className="border-b border-white/[0.04]">
                      <td className="px-3 py-2 text-white/70 font-medium">{kinLabels[v]}</td>
                      <td className="px-3 py-2 text-center text-white/60">{fmtP(r.baseline)}</td>
                      <td className="px-3 py-2 text-center text-white/60">{fmtP(r.withinA)}</td>
                      <td className="px-3 py-2 text-center text-white/60">{fmtP(r.withinC)}</td>
                      <td className="px-3 py-2 text-center text-white/60">{fmtP(r.between)}</td>
                      <td className="px-3 py-2 text-center text-white/60">{fmtD(r.between)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Glass>
      )}

      {/* Missing Data */}
      {missingFields.length > 0 && (
        <Glass className="p-5">
          <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Missing Data / Eksik Veri</p>
          <div className="overflow-x-auto rounded-xl border border-rose-500/20">
            <table className="w-full text-xs">
              <thead><tr className="bg-rose-500/10 border-b border-rose-500/20"><th className="text-left px-3 py-2 font-extrabold text-rose-300 uppercase">Patient ID</th><th className="text-left px-3 py-2 font-extrabold text-rose-300 uppercase">Missing Field</th></tr></thead>
              <tbody>{missingFields.map((m, i) => <tr key={i} className="border-b border-rose-500/10"><td className="px-3 py-2 text-white/60">{m.id}</td><td className="px-3 py-2 text-rose-200/80">{m.field}</td></tr>)}</tbody>
            </table>
          </div>
        </Glass>
      )}

      {/* Export buttons */}
      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Exports / Dışa Aktarma</p>
        <div className="flex flex-wrap gap-3">
          <button onClick={() => {
            const allPts = loadPatients();
            if (!allPts.length) return;
            const rows = [];
            allPts.forEach((pt) => { const r = buildSPSSData(pt); if (r.length) rows.push(r[0]); });
            if (!rows.length) return;
            const ws = XLSX.utils.json_to_sheet(rows);
            const csv = XLSX.utils.sheet_to_csv(ws);
            const blob = new Blob(["\uFEFF" + csv], { type:"text/csv;charset=utf-8" });
            const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `spss_${allPts.length}pts.csv`;
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
          }} className="px-5 py-2.5 rounded-xl bg-violet-500/20 border border-violet-400/30 text-violet-200 text-xs font-extrabold hover:bg-violet-500/30 transition-all">⬇ SPSS CSV</button>

          <button onClick={() => {
            const allPts = loadPatients();
            if (!allPts.length) return;
            const clean = allPts.map(({ _id, _savedAt, _hasPre, _hasPost, ...r }) => r);
            const blob = new Blob([JSON.stringify(clean, null, 2)], { type:"application/json" });
            const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `neuro_${allPts.length}pts.json`;
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
          }} className="px-5 py-2.5 rounded-xl bg-emerald-500/20 border border-emerald-400/30 text-emerald-200 text-xs font-extrabold hover:bg-emerald-500/30 transition-all">⬇ JSON</button>
        </div>
      </Glass>
    </div>
  );
};

// ─── Root App ─────────────────────────────────────────────────────────────────

const getTodayDate = () => new Date().toISOString().split("T")[0];

export default function App() {
  const [active, setActive] = useState("demographics");
  const [sidebar, setSidebar] = useState(true);
  const [toast, setToast] = useState({ visible: false, msg: "", variant: "success" });
  const [bgUrl, setBgUrl] = useState(BG);
  const bgRef = useRef(null);

  const [fd, setFd] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(FD_LS_KEY));
      if (saved && typeof saved === "object") return saved;
    } catch {}
    return {
      demographics: { participantId: String(getNextStudyId()) },
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

    if (existingIdx >= 0) {
      const existing = patients[existingIdx];
      const { _loadedId, ...cleanFd } = fd;
      patients[existingIdx] = {
        ...existing,
        ...cleanFd,
        _savedAt: new Date().toISOString(),
        _hasPre: existing._hasPre || hasPre,
        _hasPost: existing._hasPost || hasPost,
      };
      savePatients(patients);
      showToast(`✓ Session updated for ${d.name || d.participantId || "patient"}`);
    } else {
      const { _loadedId, ...cleanFd } = fd;
      patients.push({
        _id: `pt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        _savedAt: new Date().toISOString(),
        _hasPre: hasPre,
        _hasPost: hasPost,
        ...cleanFd,
      });
      savePatients(patients);
      incrementStudyId();
      setFd((p) => ({
        ...p,
        demographics: { ...p.demographics, participantId: String(getNextStudyId()) },
      }));
      showToast("✓ New patient record saved");
    }
  }, [fd, showToast]);

  const handleLoadSession = useCallback((record) => {
    const { _id, _savedAt, _hasPre, _hasPost, ...sessionData } = record;
    setFd((prev) => ({ ...prev, ...sessionData, _loadedId: _id }));
    setActive("demographics");
    showToast(`✓ Loaded: ${record.demographics?.name || record.demographics?.participantId || "patient"}`);
  }, [showToast]);

  const nav = NAV_ITEMS.find((n) => n.id === active);

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
        demographics={fd.demographics}
        onChange={(d) => upd("kinematics", d)}
        showToast={showToast}
      />
    ),
    database: <DatabaseSection onLoadSession={handleLoadSession} showToast={showToast} />,
    report: <ReportSection fd={fd} />,
    analysis: <AnalysisDashboard />,
  };

  return (
    <div className="min-h-screen flex relative" style={{ fontFamily: "'Inter',system-ui,sans-serif" }}>
      {/* Background */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: `url('${bgUrl}')`,
            backgroundSize: "cover",
            backgroundPosition: "center",
            filter: "blur(16px) brightness(0.38) saturate(0.65)",
            transform: "scale(1.08)",
          }}
        />
        <div className="absolute inset-0" style={{ background: "rgba(4,6,18,0.60)" }} />
      </div>

      {/* Sidebar backdrop (mobile only) */}
      {sidebar && (
        <div
          className="fixed inset-0 z-20 sm:hidden bg-black/60"
          onClick={() => setSidebar(false)}
        />
      )}
      <AnimatePresence>
        {sidebar && (
          <motion.aside
            key="sb"
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ type: "spring", stiffness: 320, damping: 32 }}
            className="fixed left-0 top-0 h-full z-30 w-72 max-w-[85vw] sm:w-[255px] flex flex-col p-3 sm:p-3 p-2"
          >
            <div             className="flex-1 flex flex-col rounded-2xl overflow-hidden bg-[#181818]/90 backdrop-blur-xl border border-white/[0.06] shadow-xl">
              {/* Logo */}
              <div className="p-5 border-b border-white/[0.08] flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-white/10 border border-white/[0.08] flex items-center justify-center flex-shrink-0">
                      <Stethoscope className="w-5 h-5 text-white/80" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-extrabold text-white truncate">Stroke Rehab Platform</p>
                      <p className="text-xs font-thin text-white/35">v6.4 — Full Suite + SPSS</p>
                    </div>
                    <button onClick={() => setSidebar(false)} className="sm:hidden w-8 h-8 rounded-lg bg-white/10 border border-white/10 flex items-center justify-center text-white/60 hover:text-white flex-shrink-0">
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                <div className="mt-3 flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-white/[0.06] border border-white/[0.08]">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
                  <span className="text-xs font-light text-white/50 truncate">Pre / Post Longitudinal</span>
                </div>
              </div>
            </div>

              {/* Navigation */}
              <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
                {NAV_ITEMS.map((item) => {
                  const on = active === item.id;
                  const Icon = item.icon;

                  return (
                    <motion.button
                      key={item.id}
                      whileTap={{ scale: 0.97 }}
                      onClick={() => { setActive(item.id); if (window.innerWidth < 768) setSidebar(false); }}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all relative group ${
                        on ? "bg-white/[0.07] border border-white/[0.06]" : "hover:bg-white/[0.04] border border-transparent"
                      }`}
                    >
                      {on && (
                        <motion.div
                          layoutId="np"
                          className="absolute inset-0 rounded-xl bg-white/[0.07]"
                          transition={{ type: "spring", stiffness: 380, damping: 30 }}
                        />
                      )}

                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 relative z-10 transition-all ${
                        on ? "bg-white/10 border border-white/10" : "bg-white/[0.04] border border-white/[0.04] group-hover:bg-white/[0.07]"
                      }`}>
                        <Icon className={`w-4 h-4 ${on ? "text-white" : "text-white/45 group-hover:text-white/70"}`} />
                      </div>

                      <div className="flex-1 min-w-0 relative z-10">
                        <p className={`text-sm font-extrabold truncate ${on ? "text-white" : "text-white/60 group-hover:text-white/85"}`}>
                          {item.en}
                        </p>
                        <p className={`text-[10px] font-light truncate ${on ? "text-white/40" : "text-white/20"}`}>
                          {item.tr}
                        </p>
                      </div>

                      {on && <ChevronRight className="w-3.5 h-3.5 text-white/40 relative z-10 flex-shrink-0" />}
                    </motion.button>
                  );
                })}
              </nav>

              {/* Save Button */}
              <div className="p-3 border-t border-white/[0.08]">
                <motion.button
                  whileTap={{ scale: 0.96 }}
                  onClick={() => { saveSession(); if (window.innerWidth < 768) setSidebar(false); }}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl bg-emerald-500/15 border border-emerald-400/25 text-emerald-200 hover:bg-emerald-500/25 hover:border-emerald-400/40 transition-all"
                >
                  <Save className="w-4 h-4 flex-shrink-0" />
                  <span className="text-sm font-bold">Save Session</span>
                  <Plus className="w-3.5 h-3.5 ml-auto opacity-60 flex-shrink-0" />
                </motion.button>
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <main className="flex-1 relative z-10 transition-all duration-500" style={{ marginLeft: sidebar ? "255px" : "0" }}>
        {/* Top Bar */}
        <div className="sticky top-0 z-20 px-4 pt-4 pb-0">
          <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-white/[0.04] backdrop-blur-2xl border border-white/[0.04] shadow-xl">
            <motion.button
              whileTap={{ scale: 0.9 }}
              onClick={() => setSidebar((p) => !p)}
              className="w-8 h-8 rounded-lg bg-white/[0.08] border border-white/[0.06] flex items-center justify-center text-white/60 hover:text-white transition-all flex-shrink-0"
            >
              {sidebar ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </motion.button>

            {nav && (() => {
              const Icon = nav.icon;
              return (
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <Icon className="w-4 h-4 text-white/60" />
                  <span className="text-sm font-extrabold text-white truncate">{nav.en}</span>
                  <span className="text-xs font-light text-white/30 hidden md:inline truncate">/{nav.tr}</span>
                </div>
              );
            })()}

            <div className="ml-auto flex items-center gap-2 flex-shrink-0">
              <span className="text-xs font-light text-white/30 hidden lg:block whitespace-nowrap">
                {new Date().toLocaleDateString("tr-TR", { day: "2-digit", month: "long", year: "numeric" })}
              </span>

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
                onClick={() => bgRef.current?.click()}
                className="w-8 h-8 rounded-lg bg-white/[0.08] border border-white/[0.06] flex items-center justify-center text-white/50 hover:text-white transition-all flex-shrink-0"
              >
                <ImageIcon className="w-4 h-4" />
              </motion.button>

              <motion.button
                whileHover={{ scale: 1.08 }}
                whileTap={{ scale: 0.92 }}
                onClick={() => setActive("database")}
                className="w-8 h-8 rounded-lg bg-white/[0.08] border border-white/[0.06] flex items-center justify-center text-white/50 hover:text-white transition-all flex-shrink-0"
              >
                <Database className="w-4 h-4" />
              </motion.button>
            </div>
          </div>
        </div>

        {/* Sections */}
        <div className="px-4 py-6 max-w-5xl mx-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={active}
              initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: -8, filter: "blur(4px)" }}
              transition={{ duration: 0.3 }}
            >
              {sections[active]}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Footer */}
        <div className="px-4 pb-6">
          <div className="px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-center">
            <p className="text-xs font-light text-white/20">
              Stroke Rehabilitation Research Platform v6.4 · LocalStorage Patient DB · PDF & Excel & SPSS Export · Touch-Optimised Sliders · Kinematics AI Lab
            </p>
          </div>
        </div>
      </main>

      {/* Global Styles */}
      <style>{`
        * { box-sizing: border-box; }
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
          main { margin-left: 0 !important; }
          input, select, textarea { font-size: 16px !important; }
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