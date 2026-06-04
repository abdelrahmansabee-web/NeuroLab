import React, { useState, useEffect, useRef, useCallback } from "react";
import { Play, Pause, RotateCcw } from "lucide-react";

const NAMES = [
  "NOSE","LEFT_EYE_INNER","LEFT_EYE","LEFT_EYE_OUTER",
  "RIGHT_EYE_INNER","RIGHT_EYE","RIGHT_EYE_OUTER",
  "LEFT_EAR","RIGHT_EAR","MOUTH_LEFT","MOUTH_RIGHT",
  "LEFT_SHOULDER","RIGHT_SHOULDER","LEFT_ELBOW","RIGHT_ELBOW",
  "LEFT_WRIST","RIGHT_WRIST","LEFT_PINKY","RIGHT_PINKY",
  "LEFT_INDEX","RIGHT_INDEX","LEFT_THUMB","RIGHT_THUMB",
  "LEFT_HIP","RIGHT_HIP","LEFT_KNEE","RIGHT_KNEE",
  "LEFT_ANKLE","RIGHT_ANKLE","LEFT_HEEL","RIGHT_HEEL",
  "LEFT_FOOT_INDEX","RIGHT_FOOT_INDEX",
];

const CONNS = [
  [11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24],
  [23,25],[25,27],[27,29],[29,31],[27,31],[24,26],[26,28],[28,30],
  [30,32],[28,32],[15,17],[15,19],[15,21],[17,19],[16,18],[16,20],
  [16,22],[18,20],[0,1],[1,2],[2,3],[3,7],[0,4],[4,5],[5,6],[6,8],[9,10],
];

const HAND_IDX = new Set([15,16,17,18,19,20,21,22]);

function connColor(s, e) {
  const T=[11,12,23,24],RA=[12,14,16],LA=[11,13,15],RL=[24,26,28,30,32],LL=[23,25,27,29,31],H=[0,1,2,3,4,5,6,7,8,9,10];
  if(T.includes(s)&&T.includes(e)) return "#4ecdc4";
  if(RA.includes(s)&&RA.includes(e)) return "#45b7d1";
  if(LA.includes(s)&&LA.includes(e)) return "#96ceb4";
  if(RL.includes(s)&&RL.includes(e)) return "#ffeaa7";
  if(LL.includes(s)&&LL.includes(e)) return "#dfe6e9";
  if(H.includes(s)&&H.includes(e)) return "#ff6b6b";
  return "#666";
}

function buildFrames(rows) {
  return rows.map(pts => {
    const p = NAMES.map(n => [pts[n+"_X"]||0, -(pts[n+"_Y"]||0), pts[n+"_Z"]||0]);
    const c = [0,0,0]; p.forEach(v=>{c[0]+=v[0];c[1]+=v[1];c[2]+=v[2];}); c[0]/=33;c[1]/=33;c[2]/=33;
    const centered = p.map(v=>[v[0]-c[0],v[1]-c[1],v[2]-c[2]]);
    const maxD = Math.max(...centered.map(v=>Math.sqrt(v[0]**2+v[1]**2+v[2]**2)),0.01);
    return centered.map(v=>[v[0]*3.5/maxD, v[1]*3.5/maxD, v[2]*3.5/maxD]);
  });
}

export default function Skeleton3D({ csvUrl }) {
  const canvasRef = useRef(null);
  const framesRef = useRef(null);
  const frameIdxRef = useRef(0);
  const playingRef = useRef(true);
  const rotRef = useRef({ x: 0.3, y: 0.8 });
  const dragRef = useRef({ active: false, lx: 0, ly: 0 });

  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uiFrame, setUiFrame] = useState(0);
  const [uiTotal, setUiTotal] = useState(0);
  const [uiPlaying, setUiPlaying] = useState(true);

  useEffect(() => {
    if (!csvUrl) return;
    setLoading(true); setError(null); setReady(false);
    fetch(csvUrl)
      .then(r => { if (!r.ok) throw Error("Fetch failed"); return r.text(); })
      .then(text => {
        const lines = text.trim().split("\n");
        if (lines.length < 2) throw Error("Empty CSV");
        const hdrs = lines[0].split(",");
        const rows = [];
        for (let i=1;i<lines.length;i++) {
          const vals = lines[i].split(",");
          const row = {};
          hdrs.forEach((h,idx) => { row[h.trim()] = parseFloat(vals[idx]) || 0; });
          rows.push(row);
        }
        framesRef.current = buildFrames(rows);
        frameIdxRef.current = 0;
        playingRef.current = true;
        setUiFrame(0);
        setUiTotal(rows.length);
        setUiPlaying(true);
        setLoading(false);
        setReady(true);
      })
      .catch(err => { setError(err.message); setLoading(false); });
  }, [csvUrl]);

  // Render loop
  useEffect(() => {
    if (!ready) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    let running = true;
    const render = () => {
      if (!running) return;
      const f = framesRef.current;
      if (!f || f.length === 0) { requestAnimationFrame(render); return; }
      const idx = Math.min(frameIdxRef.current, f.length - 1);
      const pts = f[idx];
      if (!pts) { requestAnimationFrame(render); return; }

      const W = canvas.width, H = canvas.height;
      const cx = W/2, cy = H/2 + 30;
      const rx = rotRef.current.x, ry = rotRef.current.y;
      const cosX = Math.cos(rx), sinX = Math.sin(rx);
      const cosY = Math.cos(ry), sinY = Math.sin(ry);

      // Project
      const proj = pts.map(v => {
        const y1 = v[1] * cosX - v[2] * sinX;
        const z1 = v[1] * sinX + v[2] * cosX;
        const x1 = v[0] * cosY + z1 * sinY;
        const z2 = -v[0] * sinY + z1 * cosY;
        const s = 130 / (z2 + 4);
        return [cx + x1 * s, cy - y1 * s, z2];
      });

      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = "#0a0a1a";
      ctx.fillRect(0, 0, W, H);

      // Grid
      ctx.strokeStyle = "#1a1a3a";
      ctx.lineWidth = 0.5;
      for (let i=-6;i<=6;i++) {
        ctx.beginPath(); ctx.moveTo(cx + i*50, cy - 300); ctx.lineTo(cx + i*50, cy + 300); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(cx - 300, cy + i*50); ctx.lineTo(cx + 300, cy + i*50); ctx.stroke();
      }

      // Draw connections sorted by depth for proper layering
      const zSorted = [...Array(33).keys()].map(i => ({i, z: proj[i][2]})).sort((a,b)=>a.z-b.z);
      const drawnEdges = new Set();

      for (const item of zSorted) {
        const i = item.i;
        for (const [s,e] of CONNS) {
          const key = Math.min(s,e)+","+Math.max(s,e);
          if (drawnEdges.has(key)) continue;
          if (i === s || i === e) {
            const p1 = proj[s], p2 = proj[e];
            if (p1 && p2) {
              ctx.strokeStyle = connColor(s,e);
              ctx.lineWidth = 3;
              ctx.globalAlpha = 0.8;
              ctx.beginPath(); ctx.moveTo(p1[0],p1[1]); ctx.lineTo(p2[0],p2[1]); ctx.stroke();
              ctx.globalAlpha = 1;
              drawnEdges.add(key);
            }
          }
        }
      }

      // Draw joints
      for (let i=0;i<33;i++) {
        const p = proj[i];
        if (!p) continue;
        const isH = HAND_IDX.has(i);
        ctx.beginPath(); ctx.arc(p[0],p[1], isH?7:5, 0, Math.PI*2);
        ctx.fillStyle = isH ? "#ffd93d" : "#ffffff";
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,0.2)";
        ctx.lineWidth = 1; ctx.stroke();
      }

      ctx.fillStyle = "#aaa";
      ctx.font = "13px monospace";
      ctx.fillText(`Frame ${idx+1}/${f.length}`, 15, 25);
      ctx.fillStyle = "#555";
      ctx.font = "10px sans-serif";
      ctx.fillText("Drag to orbit", 15, 45);

      requestAnimationFrame(render);
    };
    requestAnimationFrame(render);
    return () => { running = false; };
  }, [ready]);

  // Animation timer
  useEffect(() => {
    if (!ready) return;
    const iv = setInterval(() => {
      if (!playingRef.current) return;
      const f = framesRef.current;
      if (!f) return;
      const next = frameIdxRef.current + 1;
      if (next >= f.length) return;
      frameIdxRef.current = next;
      setUiFrame(next);
    }, 1000/30);
    return () => clearInterval(iv);
  }, [ready]);

  // Mouse handlers
  const onMouseDown = useCallback((e) => {
    dragRef.current = { active: true, lx: e.clientX, ly: e.clientY };
  }, []);
  const onMouseMove = useCallback((e) => {
    const d = dragRef.current;
    if (!d.active) return;
    const dx = e.clientX - d.lx, dy = e.clientY - d.ly;
    d.lx = e.clientX; d.ly = e.clientY;
    rotRef.current.y += dx * 0.012;
    rotRef.current.x = Math.max(-1.5, Math.min(1.5, rotRef.current.x + dy * 0.012));
  }, []);
  const onMouseUp = useCallback(() => { dragRef.current.active = false; }, []);

  const toggle = useCallback(() => {
    playingRef.current = !playingRef.current;
    setUiPlaying(playingRef.current);
  }, []);
  const reset = useCallback(() => {
    playingRef.current = true;
    frameIdxRef.current = 0;
    setUiPlaying(true);
    setUiFrame(0);
  }, []);
  const seek = useCallback((e) => {
    const v = Number(e.target.value);
    frameIdxRef.current = v;
    setUiFrame(v);
  }, []);

  if (!csvUrl) return null;
  if (loading) return <div className="flex items-center justify-center h-72 bg-white/[0.02] rounded-xl border border-white/[0.08]"><div className="text-white/40 animate-pulse text-sm">Loading 3D...</div></div>;
  if (error) return <div className="flex items-center justify-center h-72 bg-white/[0.02] rounded-xl border border-white/[0.08]"><div className="text-red-400/80 text-sm">Error: {error}</div></div>;
  if (!ready || uiTotal < 2) return <div className="flex items-center justify-center h-72 bg-white/[0.02] rounded-xl border border-white/[0.08]"><div className="text-white/30 text-sm">Not enough data</div></div>;

  return (
    <div className="rounded-xl overflow-hidden border border-white/[0.08] bg-[#0a0a1a] select-none">
      <canvas
        ref={canvasRef}
        width={800}
        height={420}
        className="w-full h-[420px] cursor-grab active:cursor-grabbing"
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      />
      <div className="px-4 py-2.5 flex items-center gap-3 border-t border-white/[0.08] bg-white/[0.02]">
        <button onClick={toggle} className="p-1.5 rounded-lg hover:bg-white/10 text-white/50 hover:text-white/90 transition-colors">
          {uiPlaying ? <Pause className="w-4 h-4"/> : <Play className="w-4 h-4"/>}
        </button>
        <button onClick={reset} className="p-1.5 rounded-lg hover:bg-white/10 text-white/50 hover:text-white/90 transition-colors">
          <RotateCcw className="w-4 h-4"/>
        </button>
        <input type="range" min={0} max={uiTotal-1} value={uiFrame} onChange={seek} className="flex-1 h-1 bg-white/10 rounded-full appearance-none cursor-pointer accent-sky-400" />
        <span className="text-white/30 text-xs font-mono min-w-[90px] text-right">{uiFrame+1}/{uiTotal}</span>
      </div>
      <div className="px-4 pb-2.5 text-[10px] text-white/25 flex gap-3">
        <span>🖱 Drag to rotate</span><span>Scroll to zoom</span>
      </div>
    </div>
  );
}
