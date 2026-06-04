// ============================================================
// Stroke Rehabilitation Platform — Frontend v6.4
// ============================================================

import React, { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  User, Activity, Sliders, TrendingUp, Heart, Timer, Cpu, FileText,
  Menu, X, ChevronRight, Play, Square, RotateCcw, Copy, Check,
  Info, Save, BarChart3, Stethoscope, Brain, Image as ImageIcon,
  RefreshCw, FileSpreadsheet,
  Database, Search, Edit3, Trash2, Plus
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
    className={`bg-white/[0.06] backdrop-blur-2xl border border-white/[0.06] shadow-xl shadow-black/10 rounded-2xl ${className}`}
    style={{ overflow: "visible", ...style }}
    {...r}
  >
    {children}
  </div>
);

const BL = ({ en, tr, className = "" }) => (
  <div className={className}>
    <span className="block font-extrabold text-white leading-snug">{en}</span>
    {tr && <span className="block font-light text-white/40 text-xs mt-0.5">{tr}</span>}
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

  useEffect(() => {
    const h = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const sel = options.find((o) => o.value === value);

  return (
    <div
      className={`flex flex-col gap-1.5 ${className}`}
      ref={ref}
      style={{ position: "relative", zIndex: open ? 50 : 1, isolation: "isolate" }}
    >
      {en && <BL en={en} tr={tr} />}

      <div style={{ position: "relative" }}>
        <motion.button
          type="button"
          onClick={() => setOpen((p) => !p)}
          whileTap={{ scale: 0.98 }}
          className="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white text-sm font-light focus:outline-none text-left flex items-center justify-between gap-2 transition-all hover:bg-white/[0.06]"
        >
          <span className={`truncate ${sel ? "text-white" : "text-white/30"}`}>
            {sel ? sel.label : "Select…"}
          </span>
          <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }} className="text-white/40 flex-shrink-0">
            ▾
          </motion.span>
        </motion.button>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.96 }}
              transition={{ duration: 0.18 }}
              style={{ position: "absolute", top: "calc(100% + 6px)", left: 0, right: 0, zIndex: 9999 }}
              className="rounded-xl bg-[#0e1120]/98 backdrop-blur-2xl border border-white/[0.08] shadow-2xl overflow-hidden"
            >
              {options.map((o) => (
                <motion.button
                  key={o.value}
                  type="button"
                  whileHover={{ backgroundColor: "rgba(255,255,255,0.08)" }}
                  onClick={() => {
                    onChange({ target: { value: o.value } });
                    setOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2.5 text-sm transition-all ${value === o.value ? "text-white font-bold bg-white/10" : "text-white/70 font-light"}`}
                >
                  {o.label}
                </motion.button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
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
      className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border font-semibold text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed ${v[variant]} ${className}`}
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
    n.includes("duration")       ||   // faster = better
    n.includes("pause")          ||   // less pause = smoother
    n.includes("bve")            ||   // lower BVE = smoother
    n.includes("path")           ||   // shorter path = more direct
    n.includes("path ratio")     ||   // closer to 1.0 = straighter
    n.includes("trunk lat")      ||   // less trunk compensation
    n.includes("trunk vert")     ||
    n.includes("trunk rot");

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

  const colorMap = {
    sky: { badge: "bg-sky-500/20 border-sky-400/30 text-sky-200", bar: "from-sky-500/80 to-sky-400/50" },
    emerald: { badge: "bg-emerald-500/20 border-emerald-400/30 text-emerald-200", bar: "from-emerald-500/80 to-emerald-400/50" },
    violet: { badge: "bg-violet-500/20 border-violet-400/30 text-violet-200", bar: "from-violet-500/80 to-violet-400/50" },
    cyan: { badge: "bg-cyan-500/20 border-cyan-400/30 text-cyan-200", bar: "from-cyan-500/80 to-cyan-400/50" },
    amber: { badge: "bg-amber-500/20 border-amber-400/30 text-amber-200", bar: "from-amber-500/80 to-amber-400/50" },
    rose: { badge: "bg-rose-500/20 border-rose-400/30 text-rose-200", bar: "from-rose-500/80 to-rose-400/50" },
  };

  const c = colorMap[color];
  const decimals = Math.max(0, (String(step).split(".")[1] || "").length);
  const clamp = (n) => Math.min(max, Math.max(min, n));
  const snap = (raw) => Number((Math.round((raw - min) / step) * step + min).toFixed(decimals));

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
    setFromClientX(e.clientX);
  };

  const endDrag = (e) => {
    dragging.current = false;
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  };

  const onTouch = (e) => {
    if (window.PointerEvent) return;
    e.preventDefault();
    const t = e.touches[0] || e.changedTouches[0];
    if (t) setFromClientX(t.clientX);
  };

  const onKeyDown = (e) => {
    let next = value;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") next = value + step;
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = value - step;
    else if (e.key === "Home") next = min;
    else if (e.key === "End") next = max;
    else return;

    e.preventDefault();
    onChange(String(clamp(snap(next))));
  };

  return (
    <div className="flex flex-col gap-2 select-none" style={{ touchAction: "none" }}>
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
        onTouchStart={onTouch}
        onTouchMove={onTouch}
        onKeyDown={onKeyDown}
        className="relative h-10 rounded-full bg-white/[0.04] overflow-hidden cursor-pointer focus:outline-none focus:ring-2 focus:ring-white/10 select-none"
        style={{ touchAction: "none", WebkitUserSelect: "none", userSelect: "none" }}
      >
        <div className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r ${c.bar}" style={{ width: `${pct}%`, willChange: "width" }} />
      </div>

      {label && (
        <div className={`text-center px-3 py-2 rounded-xl border ${c.badge}`}>
          <p className="text-sm font-extrabold">{label}</p>
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

const DemoSection = ({ data, onChange }) => {
  const s = (k, v) => onChange({ ...data, [k]: v });

  const bmi = (() => {
    const h = parseFloat(data.height);
    const w = parseFloat(data.weight);
    if (!h || !w) return "";
    return (w / ((h / 100) ** 2)).toFixed(1);
  })();

  useEffect(() => {
    if (bmi !== data.bmi && bmi !== "") onChange({ ...data, bmi });
  }, [bmi, data, onChange]);

  const shoulderWidth = (() => {
    const h = parseFloat(data.height);
    if (!h) return "";
    return (0.23 * h).toFixed(1);
  })();

  useEffect(() => {
    if (shoulderWidth && !data.shoulderWidth) onChange({ ...data, shoulderWidth });
  }, [shoulderWidth, data, onChange]);

  const toggleC = (val) => {
    const cur = data.comorbidities || [];
    s(
      "comorbidities",
      cur.includes(val) ? cur.filter((c) => c !== val) : [...cur, val]
    );
  };

  return (
    <div className="space-y-5">
      <SH icon={User} en="Participant Demographics" tr="Demografik Bilgiler" badge="Section 1" />

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Personal / Kişisel</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <GI en="Full Name" tr="Ad Soyad" value={data.name} onChange={(e) => s("name", e.target.value)} />
          <GI en="Participant ID" tr="Katılımcı Kimliği" value={data.participantId} onChange={(e) => s("participantId", e.target.value)} placeholder="PART-2026-001" />
          <GSelect en="Group" tr="Grup" value={data.group} onChange={(e) => s("group", e.target.value)} options={[{ value:"intervention",label:"Intervention / Müdahale" },{ value:"control",label:"Control / Kontrol" }]} />
          <GI en="Age (years)" tr="Yaş (yıl)" type="number" value={data.age} onChange={(e) => s("age", e.target.value)} placeholder="65" />
          <GSelect en="Gender" tr="Cinsiyet" value={data.gender} onChange={(e) => s("gender", e.target.value)} options={[{ value:"male",label:"Male / Erkek" },{ value:"female",label:"Female / Kadın" },{ value:"other",label:"Other / Diğer" }]} />
          <GSelect en="Dominant Hand" tr="Dominant El" value={data.dominantHand} onChange={(e) => s("dominantHand", e.target.value)} options={[{ value:"right",label:"Right / Sağ" },{ value:"left",label:"Left / Sol" },{ value:"both",label:"Both / İki El" }]} />
        </div>
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Anthropometrics / Antropometri</p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
          <GI en="Height (cm)" tr="Boy (cm)" type="number" value={data.height} onChange={(e) => s("height", e.target.value)} placeholder="170" />
          <GI en="Weight (kg)" tr="Kilo (kg)" type="number" value={data.weight} onChange={(e) => s("weight", e.target.value)} placeholder="70" />

          <div className="flex flex-col gap-1.5">
            <BL en="BMI (auto)" tr="VKİ (otomatik)" />
            <div className={`w-full px-3 py-2.5 rounded-xl border text-sm font-extrabold text-center ${
              bmi
                ? parseFloat(bmi) < 18.5
                  ? "bg-sky-400/10 border-sky-400/20 text-sky-300"
                  : parseFloat(bmi) < 25
                  ? "bg-emerald-400/10 border-emerald-400/20 text-emerald-300"
                  : parseFloat(bmi) < 30
                  ? "bg-amber-400/10 border-amber-400/20 text-amber-300"
                  : "bg-rose-400/10 border-rose-400/20 text-rose-300"
                : "bg-white/[0.05] border-white/[0.04] text-white/25"
            }`}>
              {bmi ? `${bmi} kg/m²` : "— Enter height & weight"}
            </div>
          </div>

          <GI
            en="Shoulder Width (cm)"
            tr="Omuz Genişliği (cm)"
            type="number"
            step="0.1"
            value={data.shoulderWidth || ""}
            onChange={(e) => s("shoulderWidth", e.target.value)}
            placeholder={`~${shoulderWidth || "39"}`}
          />

          <div className="sm:col-span-2 flex items-end">
            <p className="text-[10px] text-white/30">📐 Auto-estimated from height (23%). Edit if you have actual measurement.</p>
          </div>
        </div>
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Clinical / Klinik</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <GI en="Stroke Date" tr="İnme Tarihi" type="date" value={data.strokeDate} onChange={(e) => s("strokeDate", e.target.value)} />
          <GSelect en="Stroke Type" tr="İnme Tipi" value={data.strokeType} onChange={(e) => s("strokeType", e.target.value)} options={[{ value:"ischemic",label:"Ischemic / İskemik" },{ value:"hemorrhagic",label:"Hemorrhagic / Hemorajik" }]} />
          <GSelect en="Affected Side" tr="Etkilenen Taraf" value={data.side} onChange={(e) => s("side", e.target.value)} options={[{ value:"right",label:"Right / Sağ" },{ value:"left",label:"Left / Sol" },{ value:"bilateral",label:"Bilateral / İki Taraflı" }]} />
          <GSelect en="Affected Hemisphere" tr="Etkilenen Hemisfer" value={data.hemisphere} onChange={(e) => s("hemisphere", e.target.value)} options={[{ value:"left",label:"Left / Sol" },{ value:"right",label:"Right / Sağ" },{ value:"bilateral",label:"Bilateral" }]} />
          <GI en="Assessment Date" tr="Değerlendirme Tarihi" type="date" value={data.assessDate} onChange={(e) => s("assessDate", e.target.value)} />

          <div className="flex flex-col gap-1.5">
            <BL en="Treatment Duration" tr="Tedavi Süresi" />
            <div className="flex gap-2">
              <input
                type="number"
                value={data.treatValue ?? ""}
                onChange={(e) => s("treatValue", e.target.value)}
                placeholder="0"
                className="flex-1 min-w-0 px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white text-sm font-light focus:outline-none transition-all"
              />
              <select
                value={data.treatUnit ?? "week"}
                onChange={(e) => s("treatUnit", e.target.value)}
                className="w-24 flex-shrink-0 px-2 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white text-sm font-light focus:outline-none transition-all appearance-none"
                style={{ colorScheme: "dark" }}
              >
                {["day","week","month","year"].map((u) => (
                  <option key={u} value={u} className="bg-[#1a1a2e]">{u}</option>
                ))}
              </select>
            </div>
          </div>

          <GSelect en="Disease Stage" tr="Hastalık Evresi" value={data.diseaseStage} onChange={(e) => s("diseaseStage", e.target.value)} options={[{ value:"acute",label:"Acute (<1 month) / Akut" },{ value:"subacute",label:"Subacute (1-6 months) / Subakut" },{ value:"chronic",label:"Chronic (>6 months) / Kronik" }]} />
          <GI en="Hospital / Clinic" tr="Hastane / Klinik" value={data.hospital} onChange={(e) => s("hospital", e.target.value)} placeholder="Hospital name" />

          <div className="sm:col-span-2 flex flex-col gap-1.5">
            <BL en="Clinical Notes" tr="Klinik Notlar" />
            <textarea
              rows={3}
              value={data.notes ?? ""}
              onChange={(e) => s("notes", e.target.value)}
              placeholder="Patient history, comorbidities, assessment context, notes about PRE/POST video recording conditions…"
              className="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none focus:bg-white/[0.06] transition-all"
            />
          </div>
        </div>
      </Glass>

      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Medications / İlaçlar</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div className="flex flex-col gap-1.5">
            <BL en="Antispastic Drugs" tr="Antispastik İlaçlar" />
            <textarea
              rows={2}
              value={data.antispasticDrugs ?? ""}
              onChange={(e) => s("antispasticDrugs", e.target.value)}
              placeholder="Baclofen, Tizanidine, Botulinum toxin…"
              className="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none focus:bg-white/[0.06] transition-all"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <BL en="Other Stroke-related Drugs" tr="Diğer İnme İlişkili İlaçlar" />
            <textarea
              rows={2}
              value={data.otherDrugs ?? ""}
              onChange={(e) => s("otherDrugs", e.target.value)}
              placeholder="Aspirin, Warfarin, Statins…"
              className="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-white text-sm font-light placeholder-white/15 resize-none focus:outline-none focus:bg-white/[0.06] transition-all"
            />
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
              <motion.button
                key={opt.value}
                whileTap={{ scale: 0.95 }}
                onClick={() => toggleC(opt.value)}
                className={`text-left px-3 py-2.5 rounded-xl border text-xs font-semibold transition-all ${
                  active
                    ? "bg-violet-500/25 border-violet-400/40 text-violet-200"
                    : "bg-white/[0.05] border-white/[0.04] text-white/50 hover:bg-white/[0.08]"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className={`w-3.5 h-3.5 rounded-sm border flex-shrink-0 flex items-center justify-center ${active ? "bg-violet-500 border-violet-400" : "border-white/20"}`}>
                    {active && <Check className="w-2.5 h-2.5 text-white" />}
                  </div>
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
      <SH icon={Heart} en="Visual Analogue Mood Scale (VAMS-4)" tr="Görsel Duygu Durum Ölçeği" badge="4 Items · 0–10" />

      <Glass className="p-4 border-l-2 border-indigo-400/40">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-indigo-300 flex-shrink-0 mt-0.5" />
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
                <VASSlider value={data[item.k]?.[ph] ?? "0"} onChange={(v) => s(item.k, ph, v)} color={ph === "pre" ? "sky" : "emerald"} />
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

// ─── Kinematics AI Lab Section ────────────────────────────────────────────────

const KinSection = ({ data, demographics, onChange, showToast }) => {
  const [kinematicsResults, setKinematicsResults] = useState({});
  const [settings, setSettings] = useState({
    cutoffFrequency: 6.0,
    filterOrder: 4,
  });
  const [expandedResults, setExpandedResults] = useState({});

  const phases = [
    { k:"pre", l:"Pre", c:"sky" },
    { k:"during", l:"During", c:"violet" },
    { k:"post", l:"Post", c:"emerald" },
    { k:"baseline", l:"Baseline", c:"amber" },
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
    showToast(`\u2713 Video uploaded for ${phase}`);
  };

  const clearPhase = (phase) => {
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
      showToast("Please select a video first", "error");
      return;
    }

    onChange({ ...data, [statusKey(phase)]: "analyzing" });

    try {
      const fd = new FormData();
      fd.append("video", file);
      fd.append("arm_type", "paretic");
      fd.append("phase", phase);
      fd.append("affected_side", "auto");
      fd.append("trial_count", "3");
      fd.append("best_trial_metric", "sparc");
      fd.append("patient_height_cm", demographics?.height || "auto");
      fd.append("shoulder_width_cm", demographics?.shoulderWidth || "auto");
      fd.append("cutoff_frequency", settings.cutoffFrequency.toString());
      fd.append("filter_order", settings.filterOrder.toString());

      const res = await fetch("http://127.0.0.1:8000/analyze", { method: "POST", body: fd });
      if (!res.ok) throw new Error(`Server error ${res.status}`);

      const result = await res.json();

      if (result.error) {
        showToast(`Analysis error: ${result.error}`, "error");
        onChange({ ...data, [statusKey(phase)]: "uploaded" });
        return;
      }

      setKinematicsResults((prev) => ({ ...prev, [phase]: result }));
      onChange({ ...data, [resultKey(phase)]: result, [statusKey(phase)]: "completed" });
      showToast(`✓ Analysis complete for ${phase}`);
    } catch (err) {
      showToast("Cannot connect to backend. Ensure Python server is running at 127.0.0.1:8000", "error");
      onChange({ ...data, [statusKey(phase)]: "uploaded" });
    }
  };

  const downloadFile = async (phase, type) => {
    const result = kinematicsResults[phase];
    if (!result) return;

    let filename = "";
    if (type === "csv") filename = result.csv_filename;
    if (type === "trc") filename = result.trc_filename;
    if (type === "video") filename = result.validation_video;
    if (!filename) return;

    const a = document.createElement("a");
    a.href = `http://127.0.0.1:8000/download-${type}/${encodeURIComponent(filename)}`;
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
    { group: "Tertiary", name: "Max Elbow Extension",            key: "total_max_elbow_deg",    unit: "deg",   tip: "Maximum elbow extension angle. Higher = better ability to extend arm" },
    { group: "Tertiary", name: "Duration",                       key: "total_duration_s",       unit: "sec",   tip: "Total movement time from onset to offset" },
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
      <SH icon={Cpu} en="Kinematics AI Laboratory" tr="Kinematik Yapay Zeka Laboratuvarı" badge="Pre / During / Post / Baseline" />

      <Glass className="p-5">
        <p className="text-sm font-extrabold text-white/80 mb-4">Video Upload & Analysis</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {phases.map((ph) => {
            const status = data[statusKey(ph.k)] || "idle";
            const hasResult = !!kinematicsResults[ph.k];

            return (
              <div key={ph.k} className={`flex flex-col rounded-xl border transition-all ${status === "analyzing" ? "border-amber-400/40" : hasResult ? "border-emerald-400/30" : "border-white/[0.04]"}`}>
                <div className="flex items-center justify-between px-3 pt-3 pb-2">
                  <span className={`text-xs font-extrabold uppercase tracking-wider ${
                    ph.c === "sky"
                      ? "text-sky-300"
                      : ph.c === "violet"
                      ? "text-violet-300"
                      : ph.c === "emerald"
                      ? "text-emerald-300"
                      : "text-amber-300"
                  }`}>
                    {ph.l}
                  </span>

                  {status === "analyzing" && (
                    <span className="text-[9px] px-2 py-0.5 rounded-full bg-amber-400/20 border border-amber-400/30 text-amber-300">
                      Processing...
                    </span>
                  )}

                  {hasResult && (
                    <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-400/20 border border-emerald-400/30 text-emerald-300">
                      \u2713
                    </span>
                  )}
                </div>

                <div className="mx-3 mb-2">
                  <input
                    type="file"
                    accept="video/*"
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
                      <GBtn variant="default" onClick={() => downloadFile(ph.k, "video")} className="text-[10px] py-2 px-2.5 flex items-center justify-center" title="2D Skeleton Video">
                        <Play className="w-3.5 h-3.5" />
                      </GBtn>
                      <GBtn variant="danger" onClick={() => clearPhase(ph.k)} className="text-[10px] py-2 px-2.5 flex items-center justify-center" title="Remove">
                        <X className="w-3.5 h-3.5" />
                      </GBtn>
                    </div>
                  )}
                </div>

                {hasResult && (
                  <button onClick={() => toggleResult(ph.k)} className="mx-3 mb-3 w-full text-xs text-white/50 hover:text-white/80 flex items-center justify-center gap-2 py-2 font-medium tracking-wide" title={expandedResults[ph.k] ? "Hide chart" : "Show movement chart"}>
                    {expandedResults[ph.k] ? "\u25B2 Hide" : "Show movement chart \u25BC"}
                  </button>
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
                      const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
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
                      vs Baseline
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
                      {d.gender && <span>· {d.gender}</span>}
                      {d.strokeType && <span>· {d.strokeType}</span>}
                      {d.side && <span>· {d.side} side</span>}
                      {d.assessDate && <span>· Assessed: {d.assessDate}</span>}
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

  const calcDelta = (pre, post) => {
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
    rows.push({ tool:"VAS", metric:item.en, pre, post, delta:calcDelta(pre, post) });
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
    rows.push({ tool:"VAMS", metric:item.en, pre, post, delta:calcDelta(pre, post) });
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
      rows.push({ tool:"KVIQ", metric:`${t.en}: ${mov.en}`, pre, post, delta:calcDelta(pre, post) });
    })
  );

  // WMFT
  const wmft = fd.wmft || {};
  WMFT_ITEMS.forEach((t) => {
    const preT = v(wmft[t.id]?.pre?.time);
    const postT = v(wmft[t.id]?.post?.time);
    const preR = v(wmft[t.id]?.pre?.rating);
    const postR = v(wmft[t.id]?.post?.rating);

    rows.push({ tool:"WMFT", metric:`${t.en} — Time (sec)`, pre:preT, post:postT, delta:calcDelta(preT, postT) });
    rows.push({ tool:"WMFT", metric:`${t.en} — Ability Rating (0–5)`, pre:preR, post:postR, delta:calcDelta(preR, postR) });
  });

  return rows;
}

// ─── SPSS Export Helper ───────────────────────────────────────────────────────

function buildSPSSData(fd) {
  const d = fd.demographics || {};
  const rows = [];

  if (!d.participantId && !d.name) return rows;

  const row = {};

  // ── Demographics ──
  row.participant_id = d.participantId || "";
  row.name = d.name || "";
  row.group = d.group || "";
  row.age = d.age || "";
  row.gender = d.gender || "";
  row.dominant_hand = d.dominantHand || "";
  row.height_cm = d.height || "";
  row.weight_kg = d.weight || "";
  row.bmi = d.bmi || "";
  row.shoulder_width_cm = d.shoulderWidth || "";
  row.stroke_type = d.strokeType || "";
  row.affected_side = d.side || "";
  row.affected_hemisphere = d.hemisphere || "";
  row.stroke_date = d.strokeDate || "";
  row.assess_date = d.assessDate || "";
  row.treatment_value = d.treatValue || "";
  row.treatment_unit = d.treatUnit || "";

  // ── IPAQ (per-category + total) ──
  const ipaq = fd.ipaq || {};
  let totalMET = 0;
  IPAQ_ACTS.forEach((a) => {
    const mins = parseFloat(ipaq[a.id]?.sure) || 0;
    const days = parseFloat(ipaq[a.id]?.gun) || 0;
    const metVal = mins * days * a.met;
    totalMET += metVal;
    row[`ipaq_${a.id}_minweek`] = (mins * days).toFixed(0);
    row[`ipaq_${a.id}_metminweek`] = metVal.toFixed(0);
  });
  row.ipaq_total_met = totalMET.toFixed(0);

  // ── VAS ──
  const vas = fd.vas || {};
  ["rest", "activity", "night"].forEach((k) => {
    row[`vas_${k}_pre`] = vas[k]?.pre ?? "";
    row[`vas_${k}_post`] = vas[k]?.post ?? "";
  });
  row.vas_notes = vas?.notes ?? "";

  // ── VAMS-4 ──
  const vams = fd.vams || {};
  ["happy", "sad", "calm", "tense"].forEach((k) => {
    row[`vams_${k}_pre`] = vams[k]?.pre ?? "";
    row[`vams_${k}_post`] = vams[k]?.post ?? "";
  });

  // ── Motor Control ──
  const mc = fd.motorchange || {};
  row.motor_control_pre = mc.control ?? "";
  row.motor_difference_post = mc.difference ?? "";

  // ── KVIQ ──
  const kgia = fd.kgia || {};
  KGIA_MOVEMENTS.forEach((mov, mi) =>
    KGIA_TYPES.forEach((t) => {
      row[`kviq_${mi}_${t.key}_pre`] = kgia[`${mi}_${t.key}`]?.once ?? "";
      row[`kviq_${mi}_${t.key}_post`] = kgia[`${mi}_${t.key}`]?.sonra ?? "";
    })
  );

  // ── WMFT ──
  const wmft = fd.wmft || {};
  WMFT_ITEMS.forEach((t) => {
    row[`wmft_${t.id}_pre_time`] = wmft[t.id]?.pre?.time ?? "";
    row[`wmft_${t.id}_pre_rating`] = wmft[t.id]?.pre?.rating ?? "";
    row[`wmft_${t.id}_post_time`] = wmft[t.id]?.post?.time ?? "";
    row[`wmft_${t.id}_post_rating`] = wmft[t.id]?.post?.rating ?? "";
  });

  // ── Kinematics: global + per-phase ──
  const kin = fd.kinematics || {};
  const kinPhases = ["pre", "during", "post", "baseline"];
  const phNames = ["forward", "wipe_right", "wipe_left", "return"];
  const phVars = [
    "duration_s","peak_velocity","mean_velocity",
    "distance_norm","lateral_range_norm","forward_range_norm",
    "pause_pct","path_ratio","trunk_palm_ratio","max_elbow_deg",
    "present",
  ];

  kinPhases.forEach((ph) => {
    const result = kin[`result_${ph}`] || {};

    // Global vars
    const globKeys = [
      "total_duration_s","total_peak_velocity","total_mean_velocity",
      "total_path_ratio","total_lat_range_norm","total_trunk_palm_ratio",
      "total_max_elbow_deg","smoothness_pause_pct",
      "trunk_lat_norm","trunk_vert_norm","trunk_rot_norm",
      "arm_length_norm","shoulder_width_norm","ref_scale",
      "phases_detected","rest_velocity","baseline_elbow_deg",
    ];
    globKeys.forEach((k) => {
      row[`kin_${ph}_${k}`] = result[k] ?? "";
    });

    // Per-phase vars
    phNames.forEach((pn) => {
      const phase = result.phases?.[pn] || {};
      phVars.forEach((pv) => {
        const val = phase[pv];
        row[`kin_${ph}_${pn}_${pv}`] = (pv === "present")
          ? (val ? 1 : 0)
          : (val ?? "");
      });
    });
  });

  rows.push(row);
  return rows;
}

// ─── Report Section ───────────────────────────────────────────────────────────

const ReportSection = ({ fd }) => {
  const d = fd.demographics || {};
  const rows = buildSummaryRows(fd);
  const tools = Array.from(new Set(rows.map((r) => r.tool)));
  const kinRows = Array.isArray(fd.kinematics?.uploadedData) ? fd.kinematics.uploadedData : [];
  const kinCharts = Array.isArray(fd.kinematics?.chartImages) ? fd.kinematics.chartImages : [];

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
  };

  // ── PDF Export ──
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
      const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${xp(p.t).toFixed(1)},${yp(p.v).toFixed(1)}`).join(" ");
      const peak = pts.reduce((a, b) => a.v > b.v ? a : b);

      const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">
        <rect width="${w}" height="${h}" fill="white"/>
        <text x="${pad}" y="${pad - 10}" font-family="Helvetica,Arial,sans-serif" font-size="28" font-weight="bold" fill="#333">${label}</text>
        <line x1="${pad}" y1="${h - pad}" x2="${w - pad}" y2="${h - pad}" stroke="#ddd" stroke-width="2"/>
        <path d="${path}" fill="none" stroke="#3b82f6" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="${xp(peak.t)}" cy="${yp(peak.v)}" r="8" fill="#3b82f6" stroke="white" stroke-width="3"/>
        <text x="${xp(peak.t)}" y="${yp(peak.v) - 20}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="24" fill="#2563eb" font-weight="bold">${peak.v.toFixed(2)}</text>
        <text x="${pad}" y="${h - pad + 40}" font-family="Helvetica,Arial,sans-serif" font-size="22" fill="#999">${tMin.toFixed(1)}s</text>
        <text x="${w - pad}" y="${h - pad + 40}" text-anchor="end" font-family="Helvetica,Arial,sans-serif" font-size="22" fill="#999">${tMax.toFixed(1)}s</text>
        <text x="${w/2}" y="${h - pad + 40}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="22" fill="#999">Time (s)</text>
        <text x="${pad - 40}" y="${h/2}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="22" fill="#999" transform="rotate(-90,${pad - 40},${h/2})">Velocity (norm/s)</text>
      </svg>`;
      return "data:image/svg+xml;base64," + btoa(svg);
    };

    // White modern header
    doc.setFillColor(255, 255, 255);
    doc.rect(0, 0, 210, 42, "F");
    doc.setDrawColor(59, 130, 246);
    doc.setLineWidth(2);
    doc.line(0, 42, 210, 42);
    doc.setTextColor(15, 23, 42);
    doc.setFontSize(18);
    doc.setFont("helvetica", "bold");
    doc.text("Stroke Rehabilitation Research Platform", 14, 18);
    doc.setFontSize(10);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(100, 116, 139);
    doc.text("Clinical Assessment Report", 14, 26);
    doc.setFontSize(8);
    doc.text(`Generated: ${new Date().toLocaleString()}`, 14, 34);
    doc.text(`Participant: ${d.name || "—"} | ID: ${d.participantId || "—"}`, 14, 38);

    // Demographics
    doc.setTextColor(30, 41, 59);
    doc.setFontSize(12);
    doc.setFont("helvetica", "bold");
    doc.text("Demographics", 14, 54);
    doc.setFontSize(9);
    doc.setFont("helvetica", "normal");

    const demo = [
      ["Name", d.name || "—"],
      ["Participant ID", d.participantId || "—"],
      ["Age", d.age ? `${d.age} years` : "—"],
      ["Gender", d.gender || "—"],
      ["BMI", d.bmi ? `${d.bmi} kg/m²` : "—"],
      ["Shoulder Width", d.shoulderWidth ? `${d.shoulderWidth} cm` : "—"],
      ["Dominant Hand", d.dominantHand || "—"],
      ["Stroke Type", d.strokeType || "—"],
      ["Affected Side", d.side || "—"],
      ["Hemisphere", d.hemisphere || ""],
      ["Stroke Date", d.strokeDate || ""],
      ["Assessment Date", d.assessDate || ""],
      ["Treatment Duration", d.treatValue ? `${d.treatValue} ${d.treatUnit}` : ""],
    ];

    demo.forEach((row, i) => {
      const col = i % 2 === 0 ? 14 : 110;
      const yy = 60 + Math.floor(i / 2) * 6;
      doc.setFont("helvetica", "bold");
      doc.setTextColor(71, 85, 105);
      doc.text(`${row[0]}:`, col, yy);
      doc.setFont("helvetica", "normal");
      doc.setTextColor(30, 41, 59);
      doc.text(String(row[1]), col + 36, yy);
    });

    const startY = 60 + Math.ceil(demo.length / 2) * 6 + 8;

    // Summary Table
    doc.setFontSize(12);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(30, 41, 59);
    doc.text("Clinical Summary", 14, startY);

    autoTable(doc, {
      startY: startY + 4,
      head: [["Tool", "Metric / Task", "Pre", "Post", "Δ Change"]],
      body: rows.map((r) => [r.tool, r.metric, r.pre, r.post, r.delta]),
      styles: { fontSize: 7, cellPadding: 2, overflow: "linebreak" },
      headStyles: { fillColor: [59, 130, 246], textColor: [255, 255, 255], fontStyle: "bold" },
      alternateRowStyles: { fillColor: [248, 250, 252] },
      columnStyles: {
        0: { fontStyle: "bold", cellWidth: 28 },
        1: { cellWidth: 75 },
        2: { cellWidth: 25, halign: "center" },
        3: { cellWidth: 25, halign: "center" },
        4: { cellWidth: 20, halign: "center", fontStyle: "bold" },
      },
      didParseCell: (data) => {
        if (data.column.index === 4 && data.section === "body") {
          const val = data.cell.raw;
          if (val && val !== "—") {
            data.cell.styles.textColor = val.startsWith("+") ? [22, 163, 74] : [220, 38, 38];
          }
        }
      },
    });

    // Kinematics results from AI analysis — via kinRows (manual upload to fd.kinematics)
    if (kinRows.length > 0) {
      let y = (doc.lastAutoTable?.finalY || 20) + 10;
      if (y > 245) { doc.addPage(); y = 18; }

      doc.setFontSize(11);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(30, 41, 59);
      doc.text("Kinematics AI Lab — Generated Results", 14, y);

      autoTable(doc, {
        startY: y + 4,
        head: [["Variable", "Unit", "Pre", "During", "Post", "Δ"]],
        body: kinRows.map((r) => [r.name || "—", r.unit || "", r.pre || "", r.during || "", r.post || "", calcKinDelta(r.pre, r.post)]),
        styles: { fontSize: 7, cellPadding: 2 },
        headStyles: { fillColor: [59, 130, 246], textColor: [255, 255, 255] },
        alternateRowStyles: { fillColor: [248, 250, 252] },
      });

      if (kinCharts.length > 0) {
        doc.addPage();
        doc.setFontSize(11);
        doc.setFont("helvetica", "bold");
        doc.setTextColor(30, 41, 59);
        doc.text("Kinematics AI Lab — Movement Charts", 18, 18);

        let yImg = 26;
        kinCharts.slice(0, 6).forEach((img, i) => {
          try {
            if (yImg > 225) { doc.addPage(); yImg = 18; }
            const format = img.includes("image/png") ? "PNG" : "JPEG";
            doc.addImage(img, format, 14, yImg, 85, 48);
            doc.text(`Chart ${i + 1}`, 104, yImg + 6);
            yImg += 56;
          } catch {}
        });
      }
    }

    doc.save(`clinical_report_${d.participantId || "participant"}_${new Date().toISOString().split("T")[0]}.pdf`);
  };

  // ── Excel Export ──
  const exportExcel = () => {
    const wb = XLSX.utils.book_new();

    // Sheet 1: Demographics
    const demoData = [
      ["Field", "Value"],
      ["Name", d.name || ""],
      ["Participant ID", d.participantId || ""],
      ["Age", d.age || ""],
      ["Gender", d.gender || ""],
      ["Dominant Hand", d.dominantHand || ""],
      ["Height (cm)", d.height || ""],
      ["Weight (kg)", d.weight || ""],
      ["BMI (kg/m²)", d.bmi || ""],
      ["Shoulder Width (cm)", d.shoulderWidth || ""],
      ["Stroke Type", d.strokeType || ""],
      ["Affected Side", d.side || ""],
      ["Hemisphere", d.hemisphere || ""],
      ["Stroke Date", d.strokeDate || ""],
      ["Assessment Date", d.assessDate || ""],
      ["Treatment Duration", d.treatValue ? `${d.treatValue} ${d.treatUnit}` : ""],
      ["Comorbidities", (d.comorbidities || []).join(", ")],
      ["Clinical Notes", d.notes || ""],
      ["Antispastic Drugs", d.antispasticDrugs || ""],
      ["Other Drugs", d.otherDrugs || ""],
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

  // ── SPSS Export ──
  const exportSPSS = () => {
    const spssData = buildSPSSData(fd);

    if (spssData.length === 0) {
      return;
    }

    const wb = XLSX.utils.book_new();

    // Main data sheet
    const ws = XLSX.utils.json_to_sheet(spssData);
    ws["!cols"] = Object.keys(spssData[0]).map(() => ({ wch: 18 }));
    XLSX.utils.book_append_sheet(wb, ws, "SPSS_Data");

    // Codebook
    const codebook = [
      ["Variable_Name", "Label", "Type", "Values"],
      ["participant_id", "Participant ID", "String", ""],
      ["name", "Full Name", "String", ""],
      ["group", "Group Assignment", "String", "intervention/control"],
      ["gender", "Gender", "String", "male/female/other"],
      ["dominant_hand", "Dominant Hand", "String", "right/left/both"],
      ["height_cm", "Height (cm)", "Numeric", ""],
      ["weight_kg", "Weight (kg)", "Numeric", ""],
      ["bmi", "Body Mass Index", "Numeric", "kg/m²"],
      ["shoulder_width_cm", "Shoulder Width (cm)", "Numeric", ""],

      ["stroke_type", "Stroke Type", "String", "ischemic/hemorrhagic"],
      ["affected_side", "Affected Side", "String", "right/left/bilateral"],
      ["affected_hemisphere", "Affected Hemisphere", "String", "left/right/bilateral"],

      ["stroke_date", "Stroke Date", "Date", "YYYY-MM-DD"],
      ["assess_date", "Assessment Date", "Date", "YYYY-MM-DD"],
      ["treatment_value", "Treatment Duration Value", "Numeric", ""],
      ["treatment_unit", "Treatment Duration Unit", "String", "day/week/month/year"],

      ["ipaq_total_met", "IPAQ Total MET-min/week", "Numeric", ""],

      ["vas_rest_pre", "VAS Pain at Rest - Pre", "Numeric", "0-10"],
      ["vas_rest_post", "VAS Pain at Rest - Post", "Numeric", "0-10"],
      ["vas_activity_pre", "VAS Pain During Activity - Pre", "Numeric", "0-10"],
      ["vas_activity_post", "VAS Pain During Activity - Post", "Numeric", "0-10"],
      ["vas_night_pre", "VAS Night Pain - Pre", "Numeric", "0-10"],
      ["vas_night_post", "VAS Night Pain - Post", "Numeric", "0-10"],
      ["vas_notes", "VAS Session Notes", "String", ""],

      ["vams_happy_pre", "VAMS Happy - Pre", "Numeric", "0-10"],
      ["vams_happy_post", "VAMS Happy - Post", "Numeric", "0-10"],
      ["vams_sad_pre", "VAMS Sad - Pre", "Numeric", "0-10"],
      ["vams_sad_post", "VAMS Sad - Post", "Numeric", "0-10"],
      ["vams_calm_pre", "VAMS Calm - Pre", "Numeric", "0-10"],
      ["vams_calm_post", "VAMS Calm - Post", "Numeric", "0-10"],
      ["vams_tense_pre", "VAMS Tense - Pre", "Numeric", "0-10"],
      ["vams_tense_post", "VAMS Tense - Post", "Numeric", "0-10"],

      ["motor_control_pre", "Muscle Control - Pre", "Numeric", "0-10"],
      ["motor_difference_post", "Muscle Control Difference - Post", "Numeric", "0-10"],
    ];

    KGIA_MOVEMENTS.forEach((mov, mi) =>
      KGIA_TYPES.forEach((t) => {
        codebook.push([`kviq_${mi}_${t.key}_pre`, `KVIQ ${t.en} ${mov.en} - Pre`, "Numeric", "1-5"]);
        codebook.push([`kviq_${mi}_${t.key}_post`, `KVIQ ${t.en} ${mov.en} - Post`, "Numeric", "1-5"]);
      })
    );

    WMFT_ITEMS.forEach((t) => {
      codebook.push([`wmft_${t.id}_pre_time`, `WMFT ${t.en} Time - Pre`, "Numeric", "seconds"]);
      codebook.push([`wmft_${t.id}_pre_rating`, `WMFT ${t.en} Rating - Pre`, "Numeric", "0-5"]);
      codebook.push([`wmft_${t.id}_post_time`, `WMFT ${t.en} Time - Post`, "Numeric", "seconds"]);
      codebook.push([`wmft_${t.id}_post_rating`, `WMFT ${t.en} Rating - Post`, "Numeric", "0-5"]);
    });

    // Kinematics codebook entries (auto-generated)
    codebook.push(["", "── GLOBAL KINEMATICS ──", "", ""]);
    const kinGlobLabels = {
      total_duration_s:"Duration (sec)", total_peak_velocity:"Peak Velocity (norm/s)",
      total_mean_velocity:"Mean Velocity (norm/s)", total_path_length:"Total Path Length (norm)",
      total_lat_range_norm:"Lateral Range (norm)", total_trunk_palm_ratio:"Trunk/Palm Ratio (ratio)",
      total_max_elbow_deg:"Max Elbow Extension (deg)", smoothness_pause_pct:"Pause % (%)",
      trunk_lat_norm:"Trunk Lateral (norm)", trunk_vert_norm:"Trunk Vertical (norm)",
      trunk_rot_norm:"Trunk Rotation (norm)", arm_length_norm:"Arm Length (norm)",
      shoulder_width_norm:"Shoulder Width (norm)", ref_scale:"Reference Scale (norm)",
      phases_detected:"Phases Detected (count)", rest_velocity:"Rest Velocity (norm/s)",
      baseline_elbow_deg:"Baseline Elbow Angle (deg)", side_analyzed:"Side Analyzed",
      active_hand_path:"Active Hand Path (norm)", inactive_hand_path:"Inactive Hand Path (norm)",
      shoulder_width_cm:"Shoulder Width (cm)", arm_length_cm:"Arm Length (cm)",
      total_path_length_cm:"Total Path Length (cm)", total_lat_range_cm:"Lateral Range (cm)",
      trunk_lat_cm:"Trunk Lateral (cm)", trunk_vert_cm:"Trunk Vertical (cm)",
      trunk_rot_cm:"Trunk Rotation (cm)",
    };
    ["pre","during","post","baseline"].forEach((tp) => {
      Object.entries(kinGlobLabels).forEach(([k, lbl]) => {
        codebook.push([`kin_${tp}_${k}`, `${tp.toUpperCase()} ${lbl}`, "Numeric", ""]);
      });
      // Per-phase
      ["forward","wipe_right","wipe_left","return"].forEach((pn) => {
        codebook.push([`kin_${tp}_${pn}_present`, `${tp.toUpperCase()} ${pn} Present`, "Numeric", "0/1"]);
        codebook.push([`kin_${tp}_${pn}_duration_s`, `${tp.toUpperCase()} ${pn} Duration (sec)`, "Numeric", ""]);
        codebook.push([`kin_${tp}_${pn}_distance_norm`, `${tp.toUpperCase()} ${pn} Distance (norm)`, "Numeric", ""]);
        codebook.push([`kin_${tp}_${pn}_lateral_range_norm`, `${tp.toUpperCase()} ${pn} Lateral Range (norm)`, "Numeric", ""]);
        codebook.push([`kin_${tp}_${pn}_forward_range_norm`, `${tp.toUpperCase()} ${pn} Forward Range (norm)`, "Numeric", ""]);
        codebook.push([`kin_${tp}_${pn}_peak_velocity`, `${tp.toUpperCase()} ${pn} Peak Velocity (norm/s)`, "Numeric", ""]);
        codebook.push([`kin_${tp}_${pn}_mean_velocity`, `${tp.toUpperCase()} ${pn} Mean Velocity (norm/s)`, "Numeric", ""]);
        codebook.push([`kin_${tp}_${pn}_pause_pct`, `${tp.toUpperCase()} ${pn} Pause % (%)`, "Numeric", ""]);
        codebook.push([`kin_${tp}_${pn}_path_ratio`, `${tp.toUpperCase()} ${pn} Path Ratio (ratio)`, "Numeric", ""]);
        codebook.push([`kin_${tp}_${pn}_trunk_palm_ratio`, `${tp.toUpperCase()} ${pn} Trunk/Palm Ratio (ratio)`, "Numeric", ""]);
        codebook.push([`kin_${tp}_${pn}_max_elbow_deg`, `${tp.toUpperCase()} ${pn} Max Elbow (deg)`, "Numeric", ""]);
      });
    });

    const wsCodebook = XLSX.utils.aoa_to_sheet(codebook);
    wsCodebook["!cols"] = [{ wch: 30 }, { wch: 55 }, { wch: 12 }, { wch: 20 }];
    XLSX.utils.book_append_sheet(wb, wsCodebook, "Codebook");

    XLSX.writeFile(wb, `spss_ready_${d.participantId || "participant"}_${new Date().toISOString().split("T")[0]}.xlsx`);
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
                      const isPos = dVal !== "—" && dVal.startsWith("+");
                      const isNeg = dVal !== "—" && dVal.startsWith("-");

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
                                  : isPos
                                  ? "text-emerald-300 bg-emerald-500/15 border-emerald-400/25"
                                  : isNeg
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

      {/* Export Buttons */}
      <Glass className="p-5">
        <p className="text-xs font-extrabold text-white/50 uppercase tracking-widest mb-4">Professional Export Options</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* PDF */}
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            onClick={exportPDF}
            className="flex flex-col gap-3 p-5 rounded-xl bg-rose-500/10 border border-rose-400/25 hover:bg-rose-500/15 hover:border-rose-400/40 transition-all text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-400/30 flex items-center justify-center flex-shrink-0">
                <FileText className="w-5 h-5 text-rose-300" />
              </div>
              <div>
                <p className="font-extrabold text-rose-200 text-sm">Download PDF</p>
                <p className="text-[10px] text-rose-300/60">Clinical Report Document</p>
              </div>
            </div>
            <p className="text-xs text-white/45 leading-relaxed">
              A4 PDF with demographics, clinical summary, and kinematics table/charts when available.
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
                <p className="text-[10px] text-violet-300/60">Statistical Analysis Format</p>
              </div>
            </div>
            <p className="text-xs text-white/45 leading-relaxed">
              Excel file with flat data row + codebook sheet ready to import into SPSS.
            </p>
          </motion.button>
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

  const [fd, setFd] = useState({
    demographics: { assessDate: getTodayDate() },
    ipaq: {},
    vas: {},
    vams: {},
    motorchange: {},

    kgia: {},
    wmft: {},
    kinematics: {},
  });

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

    const existingIdx = patients.findIndex(
      (p) => p.demographics?.participantId && p.demographics.participantId === d.participantId
    );

    if (existingIdx >= 0) {
      const existing = patients[existingIdx];
      patients[existingIdx] = {
        ...existing,
        ...fd,
        _savedAt: new Date().toISOString(),
        _hasPre: existing._hasPre || hasPre,
        _hasPost: existing._hasPost || hasPost,
      };
      savePatients(patients);
      showToast(`✓ Session updated for ${d.name || d.participantId || "patient"}`);
    } else {
      patients.push({
        _id: `pt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        _savedAt: new Date().toISOString(),
        _hasPre: hasPre,
        _hasPost: hasPost,
        ...fd,
      });
      savePatients(patients);
      showToast("✓ New patient record saved");
    }
  }, [fd, showToast]);

  const handleLoadSession = useCallback((record) => {
    const { _id, _savedAt, _hasPre, _hasPost, ...sessionData } = record;
    setFd((prev) => ({ ...prev, ...sessionData }));
    setActive("demographics");
    showToast(`✓ Loaded: ${record.demographics?.name || record.demographics?.participantId || "patient"}`);
  }, [showToast]);

  const nav = NAV_ITEMS.find((n) => n.id === active);

  const sections = {
    demographics: <DemoSection data={fd.demographics} onChange={(d) => upd("demographics", d)} />,
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
  };

  return (
    <div className="min-h-screen flex overflow-hidden relative" style={{ fontFamily: "'Inter',system-ui,sans-serif" }}>
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

      {/* Sidebar */}
      <AnimatePresence>
        {sidebar && (
          <motion.aside
            key="sb"
            initial={{ x: -280, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -280, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 32 }}
            className="fixed left-0 top-0 h-full z-30 w-[255px] flex flex-col p-3"
          >
            <div className="flex-1 flex flex-col rounded-2xl overflow-hidden bg-white/[0.04] backdrop-blur-2xl border border-white/[0.04] shadow-xl">
              {/* Logo */}
              <div className="p-5 border-b border-white/[0.08]">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-white/10 border border-white/[0.08] flex items-center justify-center flex-shrink-0">
                    <Stethoscope className="w-5 h-5 text-white/80" />
                  </div>

                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-extrabold text-white truncate">Stroke Rehab Platform</p>
                    <p className="text-xs font-thin text-white/35">v6.4 — Full Suite + SPSS</p>
                  </div>
                </div>

                <div className="mt-3 flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-white/[0.06] border border-white/[0.09]">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
                  <span className="text-xs font-light text-white/50 truncate">Pre / Post Longitudinal</span>
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
                      onClick={() => setActive(item.id)}
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
                  onClick={saveSession}
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
        @media (max-width: 768px) {
          main { margin-left: 0 !important; }
        }
      `}</style>

      <Toast msg={toast.msg} visible={toast.visible} variant={toast.variant} />
    </div>
  );
}