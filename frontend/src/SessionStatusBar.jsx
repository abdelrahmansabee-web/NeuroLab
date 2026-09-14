import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  Check,
  ChevronDown,
  EyeOff,
  Video,
  X,
} from "lucide-react";
import { NL_TWEEN_OVERLAY } from "./motionPresets";
import {
  SESSION_PHASES,
  SESSION_STATUS_LS,
  SESSION_STATUS_SS,
  formatPhaseMetricLine,
  summarizeInventory,
} from "./sessionInventory";

const PATIENTS_SYNC_EVENT = "neurolab-patients-synced";

const GLASS = {
  backgroundColor: "rgba(18, 24, 32, 0.92)",
  border: "1px solid rgba(255,255,255,0.08)",
  boxShadow: "0 24px 60px -28px rgba(0,0,0,0.55)",
  backdropFilter: "blur(22px) saturate(1.6)",
  WebkitBackdropFilter: "blur(22px) saturate(1.6)",
};

const TONE_DOT = {
  ready: "bg-emerald-400",
  partial: "bg-amber-400",
  empty: "bg-white/25",
};

function ssGet(key) {
  try {
    return sessionStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}
function ssSet(key, on) {
  try {
    if (on) sessionStorage.setItem(key, "1");
    else sessionStorage.removeItem(key);
  } catch { /* ignore */ }
}
function lsGet(key) {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}
function lsSet(key, on) {
  try {
    if (on) localStorage.setItem(key, "1");
    else localStorage.removeItem(key);
  } catch { /* ignore */ }
}

function PhasePills({ phases }) {
  return (
    <div className="flex items-center gap-1 flex-shrink-0">
      {SESSION_PHASES.map((meta, i) => {
        const ph = phases[i];
        const title = `${meta.l}: ${ph.hasKin ? "kinematics" : "no analysis"}${ph.hasVideo ? ", video" : ", no video"}`;
        return (
          <span
            key={meta.k}
            title={title}
            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-md text-[9px] font-semibold uppercase tracking-wide text-white/70 bg-white/[0.05] border border-white/[0.06]"
          >
            <span className={`w-1.5 h-1.5 rounded-full ${TONE_DOT[ph.tone]}`} />
            {meta.l[0]}
            {ph.hasVideo ? <Video className="w-2.5 h-2.5 text-sky-300/80" /> : null}
          </span>
        );
      })}
    </div>
  );
}

function SessionRow({ row, expanded, onToggle, onOpen }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] overflow-hidden">
      <div className="flex items-stretch">
        <button
          type="button"
          onClick={onToggle}
          className="flex-1 min-w-0 flex items-center gap-2 px-2.5 py-2 text-left hover:bg-white/[0.04]"
        >
          <ChevronDown
            className={`w-3.5 h-3.5 text-white/40 flex-shrink-0 transition-transform ${expanded ? "" : "-rotate-90"}`}
          />
          <div className="min-w-0 flex-1">
            <div className="text-[12px] font-semibold text-white/90 truncate">
              {row.id || "—"}
              {row.name ? <span className="text-white/50 font-medium"> · {row.name}</span> : null}
            </div>
            <div className="text-[10px] text-white/40">
              {row.kinCount ? `${row.kinCount} analysis` : "No kinematics"}
              {" · "}
              {row.videoCount ? `${row.videoCount} video` : "No video"}
            </div>
          </div>
          <PhasePills phases={row.phases} />
        </button>
        <button
          type="button"
          onClick={() => onOpen(row.record)}
          className="px-2.5 text-[10px] font-semibold text-sky-200/90 hover:bg-sky-400/10 border-l border-white/[0.06] flex-shrink-0"
        >
          Open
        </button>
      </div>
      {expanded ? (
        <div className="px-3 pb-2.5 pt-0 space-y-1.5 border-t border-white/[0.05]">
          {SESSION_PHASES.map((meta, i) => {
            const ph = row.phases[i];
            const line = formatPhaseMetricLine(ph);
            return (
              <div key={meta.k} className="flex items-start justify-between gap-2 text-[11px]">
                <span className="text-white/55 w-14 flex-shrink-0 pt-0.5">{meta.l}</span>
                <div className="flex-1 min-w-0 text-white/80">
                  {ph.hasKin ? (line || "Analysis saved") : "No analysis"}
                  <div className="text-[10px] text-white/40 truncate">
                    {ph.hasVideo ? ph.videoName || "Video on file" : "Video not restored"}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

export default function SessionStatusBar({
  getPatients,
  restoreBusy = false,
  onOpenSession,
}) {
  const chipRef = useRef(null);
  const panelRef = useRef(null);
  const [inventory, setInventory] = useState(() => summarizeInventory(getPatients?.() || []));
  const [open, setOpen] = useState(false);
  const [chipHidden, setChipHidden] = useState(() => ssGet(SESSION_STATUS_SS.chipHidden));
  const [filter, setFilter] = useState("all");
  const [expandedKey, setExpandedKey] = useState("");
  const [noAutoOpen, setNoAutoOpen] = useState(() => lsGet(SESSION_STATUS_LS.noAutoOpen));
  const [panelPos, setPanelPos] = useState({ top: 56, right: 12 });

  const refresh = useCallback(() => {
    setInventory(summarizeInventory(getPatients?.() || []));
  }, [getPatients]);

  useEffect(() => {
    refresh();
    const onSync = () => refresh();
    window.addEventListener(PATIENTS_SYNC_EVENT, onSync);
    return () => window.removeEventListener(PATIENTS_SYNC_EVENT, onSync);
  }, [refresh]);

  const placePanel = useCallback(() => {
    const el = chipRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const width = Math.min(380, window.innerWidth - 16);
    let right = window.innerWidth - r.right;
    if (right + width > window.innerWidth - 8) right = 8;
    setPanelPos({
      top: Math.round(r.bottom + 8),
      right: Math.round(Math.max(8, right)),
      width,
    });
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    placePanel();
    refresh();
    const onWin = () => placePanel();
    window.addEventListener("resize", onWin);
    window.addEventListener("scroll", onWin, true);
    return () => {
      window.removeEventListener("resize", onWin);
      window.removeEventListener("scroll", onWin, true);
    };
  }, [open, placePanel, refresh]);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (chipRef.current?.contains(e.target)) return;
      if (panelRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (restoreBusy || noAutoOpen || chipHidden) return undefined;
    if (ssGet(SESSION_STATUS_SS.autoShown)) return undefined;
    if (inventory.total === 0) return undefined;
    if (inventory.partial + inventory.empty === 0) return undefined;
    const t = setTimeout(() => {
      if (ssGet(SESSION_STATUS_SS.autoShown)) return;
      ssSet(SESSION_STATUS_SS.autoShown, true);
      setChipHidden(false);
      setOpen(true);
    }, 1400);
    return () => clearTimeout(t);
  }, [restoreBusy, noAutoOpen, chipHidden, inventory.total, inventory.partial, inventory.empty]);

  useEffect(() => {
    const show = () => {
      ssSet(SESSION_STATUS_SS.chipHidden, false);
      setChipHidden(false);
      setOpen(true);
    };
    window.addEventListener("nl-session-status-show", show);
    return () => window.removeEventListener("nl-session-status-show", show);
  }, []);

  const visibleRows = useMemo(() => {
    if (filter === "ready") return inventory.rows.filter((r) => r.bucket === "ready");
    if (filter === "partial") return inventory.rows.filter((r) => r.bucket === "partial");
    if (filter === "empty") return inventory.rows.filter((r) => r.bucket === "empty");
    return inventory.rows;
  }, [filter, inventory.rows]);

  const issueCount = inventory.partial + inventory.empty;
  const chipLabel = inventory.total === 1 ? "1 session" : `${inventory.total} sessions`;

  const openPanel = () => {
    setChipHidden(false);
    ssSet(SESSION_STATUS_SS.chipHidden, false);
    setOpen(true);
  };

  const hideList = () => {
    setOpen(false);
  };

  const hideChipThisVisit = () => {
    ssSet(SESSION_STATUS_SS.chipHidden, true);
    setChipHidden(true);
    setOpen(false);
  };

  const toggleNoAuto = (next) => {
    setNoAutoOpen(next);
    lsSet(SESSION_STATUS_LS.noAutoOpen, next);
  };

  if (chipHidden && !open) return null;

  return (
    <>
      <button
        ref={chipRef}
        type="button"
        onClick={() => (open ? setOpen(false) : openPanel())}
        className={`flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 min-h-[36px] rounded-xl border text-xs font-semibold flex-shrink-0 transition-colors ${
          open
            ? "bg-white/[0.10] border-white/15 text-white"
            : "bg-white/[0.04] border-white/[0.06] text-white/75 hover:bg-white/[0.07]"
        }`}
        title="Loaded sessions, videos, and kinematics"
        aria-label={`${chipLabel}. ${issueCount} incomplete.`}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        {restoreBusy ? (
          <span className="w-3.5 h-3.5 rounded-full border border-white/30 border-t-sky-300 animate-spin flex-shrink-0" />
        ) : issueCount > 0 ? (
          <AlertCircle className="w-3.5 h-3.5 text-amber-300 flex-shrink-0" />
        ) : (
          <Check className="w-3.5 h-3.5 text-emerald-300 flex-shrink-0" />
        )}
        <span className="hidden sm:inline">{chipLabel}</span>
        <span className="sm:hidden">{inventory.total}</span>
        {issueCount > 0 ? (
          <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-amber-400/20 text-amber-100 text-[10px] font-bold">
            {issueCount}
          </span>
        ) : null}
      </button>

      {typeof document !== "undefined" &&
        createPortal(
          <AnimatePresence>
            {open && (
              <motion.div
                ref={panelRef}
                key="session-status-panel"
                role="dialog"
                aria-label="Loaded sessions"
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={NL_TWEEN_OVERLAY}
                className="fixed z-[210] flex flex-col rounded-2xl overflow-hidden"
                style={{
                  ...GLASS,
                  top: panelPos.top,
                  right: panelPos.right,
                  width: panelPos.width || 360,
                  maxHeight: "min(70vh, calc(100dvh - 72px))",
                }}
              >
                <div className="flex items-start justify-between gap-2 px-3 pt-3 pb-2">
                  <div>
                    <div className="text-[13px] font-extrabold text-white/90">Loaded sessions</div>
                    <div className="text-[10px] text-white/45 mt-0.5">
                      {inventory.ready} ready · {inventory.partial} incomplete · {inventory.empty} no analysis
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={hideList}
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-white/45 hover:text-white hover:bg-white/[0.06]"
                    aria-label="Close session list"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex gap-1 px-3 pb-2">
                  {[
                    { id: "all", l: "All" },
                    { id: "ready", l: "Ready" },
                    { id: "partial", l: "Incomplete" },
                    { id: "empty", l: "Missing" },
                  ].map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => setFilter(f.id)}
                      className={`px-2 py-1 rounded-lg text-[10px] font-semibold ${
                        filter === f.id
                          ? "bg-white/[0.12] text-white"
                          : "text-white/45 hover:text-white/70"
                      }`}
                    >
                      {f.l}
                    </button>
                  ))}
                </div>

                <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-3 pb-2 space-y-1.5">
                  {visibleRows.length === 0 ? (
                    <p className="text-[12px] text-white/45 py-6 text-center">
                      {inventory.total === 0
                        ? "No sessions on this device yet. Restore from Drive in Database."
                        : "Nothing in this filter."}
                    </p>
                  ) : (
                    visibleRows.map((row) => (
                      <SessionRow
                        key={row.key}
                        row={row}
                        expanded={expandedKey === row.key}
                        onToggle={() => setExpandedKey((k) => (k === row.key ? "" : row.key))}
                        onOpen={(record) => {
                          setOpen(false);
                          onOpenSession?.(record);
                        }}
                      />
                    ))
                  )}
                </div>

                <div className="px-3 py-2.5 border-t border-white/[0.06] space-y-2">
                  <label className="flex items-center gap-2 text-[11px] text-white/55 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={noAutoOpen}
                      onChange={(e) => toggleNoAuto(e.target.checked)}
                      className="rounded border-white/20 bg-transparent"
                    />
                    Don&apos;t open this list on launch
                  </label>
                  <div className="flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={hideChipThisVisit}
                      className="inline-flex items-center gap-1 text-[10px] font-semibold text-white/40 hover:text-white/70"
                    >
                      <EyeOff className="w-3 h-3" />
                      Hide chip until next sign-in
                    </button>
                    <span className="text-[10px] text-white/30">Tap the chip to reopen</span>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>,
          document.body,
        )}
    </>
  );
}

export function revealSessionStatusBar() {
  try {
    sessionStorage.removeItem(SESSION_STATUS_SS.chipHidden);
  } catch { /* ignore */ }
  window.dispatchEvent(new Event("nl-session-status-show"));
}
