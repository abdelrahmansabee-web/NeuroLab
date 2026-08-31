"""Same Clinical Assessment Report HTML as frontend exportGlassReport()."""
from __future__ import annotations

import html
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from patient_drive_archive import program_patient_record
from patient_pdf import (
    IPAQ_ACTS,
    KINEMATIC_VARS,
    MISSING,
    _demo_value,
    _plain,
    build_summary_rows,
)

TOOL_META = {
    "VAS": {"label": "Pain Scale (VAS) / Ağrı Skalası", "color": "#800020", "bg": "#fdf2f4"},
    "VAMS": {"label": "Mood Scale (VAMS-4) / Ruh Hali", "color": "#0ea5e9", "bg": "#f0f9ff"},
    "Muscle Control": {"label": "Muscle Control Scale / Kas Kontrolü", "color": "#10b981", "bg": "#ecfdf5"},
    "KVIQ": {"label": "Motor Imagery (KVIQ) / Motor İmgeleme", "color": "#0d9488", "bg": "#f0fdfa"},
    "WMFT": {"label": "Wolf Motor Function (WMFT) / Motor Fonksiyon", "color": "#0ea5e9", "bg": "#ecfeff"},
    "Kinematics": {"label": "Kinematic Analysis / Kinematik Analiz", "color": "#f43f5e", "bg": "#fff1f2"},
}

GLASS_CSS = r"""
  * { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',system-ui,-apple-system,'DejaVu Sans',sans-serif; }
  body { background:#f5f0eb; color:#1e293b; padding:28px; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  .wrap { max-width:920px; margin:0 auto; }
  .header { border:1px solid rgba(255,255,255,0.3); border-radius:1rem; box-shadow:0 25px 50px -8px rgba(0,0,0,0.10); padding:22px 30px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center; }
  .header h1 { font-size:20px; color:#1e293b; font-weight:800; }
  .header .sub { font-size:12px; color:#64748b; margin-top:3px; }
  .header .meta { text-align:right; font-size:11px; color:#64748b; }
  .patient { background:rgba(204,251,241,0.35); border:1px solid rgba(255,255,255,0.3); border-radius:1rem; box-shadow:0 25px 50px -8px rgba(0,0,0,0.10); padding:20px 28px; margin-bottom:20px; }
  .patient .name { font-size:22px; font-weight:800; color:#1e293b; }
  .patient .pid { font-size:12px; color:#64748b; margin:3px 0 14px; }
  .demogrid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }
  .demoitem { display:flex; flex-direction:column; }
  .demok { font-size:9px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.05em; font-weight:700; }
  .demov { font-size:13px; color:#334155; font-weight:700; margin-top:1px; }
  tr { break-inside:avoid; page-break-inside:avoid; }
  .tool-interp { margin-top:14px; padding:10px 14px; background:rgba(255,255,255,0.5); border:1px solid rgba(255,255,255,0.3); border-radius:0.75rem; display:inline-block; font-size:11px; color:#334155; font-weight:600; }
  .sum-item { display:flex; align-items:center; gap:10px; padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.3); font-size:12px; color:#334155; }
  .sum-item:last-child { border-bottom:none; }
  .sum-badge { display:inline-block; font-size:9px; font-weight:800; padding:3px 12px; border-radius:0.75rem; flex-shrink:0; background:rgba(255,255,255,0.25); border:1px solid rgba(255,255,255,0.3); }
  .badge { display:inline-block; color:#fff; font-size:10px; font-weight:800; padding:5px 16px; border-radius:1rem; margin-bottom:12px; letter-spacing:0.02em; border:1px solid rgba(255,255,255,0.3); }
  .tblwrap { border-radius:0.75rem; overflow:hidden; border:1px solid rgba(255,255,255,0.3); box-shadow:0 8px 25px -6px rgba(0,0,0,0.06); background:rgba(255,255,255,0.4); }
  table { width:100%; border-collapse:collapse; }
  thead th { color:#fff; font-size:10px; font-weight:700; padding:9px 14px; text-align:left; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  thead th:not(:first-child) { text-align:center; }
  tbody td { padding:9px 14px; font-size:11px; color:#475569; border-top:1px solid rgba(255,255,255,0.3); }
  tbody tr:nth-child(even) { background:rgba(255,255,255,0.2); }
  td.metric { font-weight:500; }
  td.num { text-align:center; }
  .delta { font-weight:800; }
  .delta.up { color:#16a34a; } .delta.down { color:#dc2626; } .delta.neutral { color:#94a3b8; }
  .singlecol .card { break-inside:avoid; page-break-inside:avoid; background:rgba(255,255,255,0.65); border:1px solid rgba(255,255,255,0.3); border-radius:1rem; box-shadow:0 25px 50px -8px rgba(0,0,0,0.10); padding:18px 22px; margin-bottom:20px; }
  .pagebreak { break-before:page; page-break-before:always; }
  @media print {
    body { -webkit-print-color-adjust:exact !important; print-color-adjust:exact !important; background:#f5f0eb !important; padding:16px; }
    .card, .header, .patient { box-shadow:0 10px 30px -6px rgba(0,0,0,0.08) !important; page-break-inside:avoid; break-inside:avoid; }
    .badge, thead th, .tblwrap { -webkit-print-color-adjust:exact !important; print-color-adjust:exact !important; }
    @page { margin:12mm; size: A4; }
  }
"""


def esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _tool_interp_html(tool: str, trows: List[Dict[str, Any]]) -> str:
    items = [r for r in trows if r.get("delta") != MISSING]
    en: List[str] = []
    tr: List[str] = []
    if tool == "VAS":
        imp = sum(1 for r in items if r.get("improving") is True)
        wors = sum(1 for r in items if r.get("improving") is False)
        if imp and not wors:
            en, tr = ["Pain decreased"], ["Ağrı azaldı"]
        elif wors and not imp:
            en, tr = ["Pain increased"], ["Ağrı arttı"]
        elif imp and wors:
            en, tr = ["Mixed pain results"], ["Karışık ağrı sonuçları"]
        else:
            en, tr = ["Pain stable"], ["Ağrı sabit"]
    elif tool == "VAMS":
        pos = ("Happy", "Calm")
        neg = ("Sad", "Tense")
        if any(any(n in r["metric"] for n in pos) and r.get("improving") for r in items):
            en.append("Positive mood improved")
            tr.append("Olumlu ruh hali iyileşti")
        if any(any(n in r["metric"] for n in neg) and r.get("improving") for r in items):
            en.append("Negative mood decreased")
            tr.append("Olumsuz ruh hali azaldı")
        if not en:
            en, tr = ["Mood stable"], ["Ruh hali sabit"]
    elif tool == "Muscle Control":
        pre_val = next((r["pre"] for r in trows if r["pre"] != MISSING), None)
        post_val = next((r["post"] for r in trows if r["post"] != MISSING), None)
        try:
            if pre_val and post_val and float(post_val) > float(pre_val):
                en, tr = ["Muscle control improved"], ["Kas kontrolü iyileşti"]
            elif pre_val and post_val and float(post_val) < float(pre_val):
                en, tr = ["Muscle control declined"], ["Kas kontrolü azaldı"]
            elif pre_val or post_val:
                en, tr = ["Muscle control stable"], ["Kas kontrolü sabit"]
        except (TypeError, ValueError):
            if pre_val or post_val:
                en, tr = ["Muscle control stable"], ["Kas kontrolü sabit"]
    elif tool == "KVIQ":
        imp = sum(1 for r in items if r.get("improving"))
        tot = len(items)
        if tot and imp > tot / 2:
            en, tr = ["Imagery improved in most items"], ["Çoğu öğede imgeleme iyileşti"]
        elif imp:
            en, tr = ["Imagery improved in some items"], ["Bazı öğelerde imgeleme iyileşti"]
        else:
            en, tr = ["Imagery stable"], ["İmgeleme sabit"]
    elif tool == "WMFT":
        time_rows = [r for r in items if "Time" in r["metric"]]
        rate_rows = [r for r in items if "Rating" in r["metric"]]
        if any(r.get("improving") for r in time_rows):
            en.append("Faster task time")
            tr.append("Daha hızlı görev süresi")
        if any(r.get("improving") is False for r in time_rows):
            en.append("Slower task time")
            tr.append("Daha yavaş görev süresi")
        if any(r.get("improving") for r in rate_rows):
            en.append("Functional ability improved")
            tr.append("Fonksiyonel yetenek iyileşti")
        if any(r.get("improving") is False for r in rate_rows):
            en.append("Functional ability declined")
            tr.append("Fonksiyonel yetenek azaldı")
        if not en and items:
            en, tr = ["No notable change in WMFT"], ["WMFT'de kayda değer değişiklik yok"]
    elif tool == "Kinematics":
        imp = sum(1 for r in items if r.get("improving"))
        tot = len(items)
        if tot and imp > tot / 2:
            en, tr = ["Kinematics improved"], ["Kinematik iyileşti"]
        elif imp:
            en, tr = ["Kinematics partially improved"], ["Kinematik kısmen iyileşti"]
        elif tot:
            en, tr = ["Kinematics stable"], ["Kinematik sabit"]
    if not en:
        return ""
    return f'<div class="tool-interp">{esc(", ".join(en))} / {esc(", ".join(tr))}</div>'


def _delta_cell(row: Dict[str, Any]) -> str:
    delta = row.get("delta") or MISSING
    if delta == MISSING:
        return f'<span class="delta neutral">{MISSING}</span>'
    cls = "up" if row.get("improving") is True else ("down" if row.get("improving") is False else "neutral")
    return f'<span class="delta {cls}">{esc(delta)}</span>'


def _ipaq_section(patient: Dict[str, Any]) -> str:
    rec = program_patient_record(patient)
    ipaq = rec.get("ipaq") if isinstance(rec.get("ipaq"), dict) else {}
    rows_html = []
    total_met = 0.0
    for key, label, met in IPAQ_ACTS:
        item = ipaq.get(key) if isinstance(ipaq.get(key), dict) else {}
        gun = _plain(item.get("gun"))
        sure = _plain(item.get("sure"))
        if not gun and not sure:
            continue
        try:
            tot_min = float(gun or 0) * float(sure or 0)
        except (TypeError, ValueError):
            tot_min = 0.0
        met_val = tot_min * met
        rows_html.append(
            "<tr>"
            f'<td class="metric">{esc(label)}</td>'
            f'<td class="num">{esc(gun or "0")}</td>'
            f'<td class="num">{esc(sure or "0")}</td>'
            f'<td class="num">{tot_min:.0f}</td>'
            f'<td class="num">{met:g}</td>'
            f'<td class="num">{met_val:.0f}</td>'
            "</tr>"
        )
    total_met = 0.0
    for key, _label, met in IPAQ_ACTS:
        item = ipaq.get(key) if isinstance(ipaq.get(key), dict) else {}
        try:
            gun_n = float(_plain(item.get("gun")) or 0)
            sure_n = float(_plain(item.get("sure")) or 0)
        except (TypeError, ValueError):
            gun_n = sure_n = 0.0
        total_met += gun_n * sure_n * met
    if not rows_html:
        return ""
    high_days = int(float(_plain((ipaq.get("high") or {}).get("gun")) or 0) or 0) if isinstance(ipaq.get("high"), dict) else 0
    med_days = int(float(_plain((ipaq.get("medium") or {}).get("gun")) or 0) or 0) if isinstance(ipaq.get("medium"), dict) else 0
    light_days = int(float(_plain((ipaq.get("light") or {}).get("gun")) or 0) or 0) if isinstance(ipaq.get("light"), dict) else 0
    try:
        med_item = ipaq.get("medium") if isinstance(ipaq.get("medium"), dict) else {}
        light_item = ipaq.get("light") if isinstance(ipaq.get("light"), dict) else {}
        med_total = float(_plain(med_item.get("sure")) or 0) * float(_plain(med_item.get("gun")) or 0)
        light_total = float(_plain(light_item.get("sure")) or 0) * float(_plain(light_item.get("gun")) or 0)
    except (TypeError, ValueError):
        med_total = light_total = 0.0
    if high_days >= 3 and total_met >= 1500:
        cls_level, cls_color, cls_text = "High", "#10b981", "Vigorous activity ≥3 days & ≥1500 MET-min/week"
    elif (med_days + light_days) >= 7 and total_met >= 3000:
        cls_level, cls_color, cls_text = "High", "#10b981", "Mixed activities 7 days & ≥3000 MET-min/week"
    elif total_met >= 600 or (med_days + light_days >= 5 and (med_total + light_total) >= 150):
        cls_level, cls_color, cls_text = "Moderate", "#f59e0b", "≥600 MET-min/week or 5+ days moderate/walking"
    else:
        cls_level, cls_color, cls_text = "Low", "#f43f5e", "Not meeting moderate or high criteria"
    return (
        '<div class="singlecol"><div class="card">'
        '<div class="badge" style="background:#0ea5e988">Physical Activity (IPAQ) / Fiziksel Aktivite</div>'
        '<div class="tblwrap"><table><thead><tr style="background:#0ea5e988">'
        "<th>Activity</th><th>Days/wk</th><th>Min/day</th><th>Total min/wk</th><th>MET</th><th>MET-min/wk</th>"
        "</tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table></div>"
        '<hr style="border:none;border-top:1px solid rgba(0,0,0,0.06);margin:14px 0">'
        '<p style="font-size:9px;color:#94a3b8;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 2px">Physical Activity Level Interpretation</p>'
        '<p style="font-size:11px;color:#64748b;margin:0 0 10px">Based on IPAQ scoring guidelines</p>'
        '<div style="display:flex;gap:10px">'
        '<div style="flex:1;padding:10px 14px;background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.3);border-radius:0.75rem">'
        '<p style="font-size:9px;color:#94a3b8;font-weight:800;text-transform:uppercase;margin:0 0 2px">Total MET-minutes/week</p>'
        f'<p style="font-size:22px;font-weight:800;color:#1e293b;margin:0">{total_met:.0f}</p>'
        '<p style="font-size:11px;color:#64748b;margin:4px 0 0">Metabolic Equivalent of Task</p>'
        "</div>"
        f'<div style="flex:1;padding:10px 14px;border-radius:0.75rem;border:1px solid;background:{cls_color}15;border-color:{cls_color}30">'
        '<p style="font-size:9px;color:#94a3b8;font-weight:800;text-transform:uppercase;margin:0 0 2px">Activity Classification</p>'
        f'<p style="font-size:22px;font-weight:800;color:{cls_color};margin:0">{cls_level}</p>'
        f'<p style="font-size:11px;color:{cls_color};margin:4px 0 0;opacity:0.7">{esc(cls_text)}</p>'
        "</div></div></div></div>"
    )


def _format_kin(key: str, value: Any) -> str:
    if value is None or value == MISSING or value == "":
        return MISSING
    if isinstance(value, str) and not value.replace(".", "", 1).replace("-", "", 1).isdigit():
        return value
    try:
        val = float(value)
    except (TypeError, ValueError):
        return str(value)
    if key == "nvp" or key == "number_of_stops":
        return f"{val:.0f}"
    if key == "straightness" or "elevation" in key:
        return f"{val:.3f}"
    if key == "pause_time_sec" or key == "movement_time_sec":
        return f"{val:.2f}"
    if key == "trunk_ratio":
        return f"{val * 100:.1f}%"
    if key == "elbow_angle_mean_deg":
        return f"{val:.1f}"
    if key == "peak_elbow_ang_vel_deg_s":
        return f"{val:.1f} °/s"
    return f"{val:.2f}"


def _video_section(patient: Dict[str, Any]) -> str:
    rec = program_patient_record(patient)
    kin = rec.get("kinematics") if isinstance(rec.get("kinematics"), dict) else {}
    phase_labels = {"pre": "Pre", "post": "Post", "baseline": "Healthy side", "healthy": "Healthy side"}
    phases: List[str] = []
    seen_healthy = False
    for key in ("pre", "post", "baseline", "healthy"):
        block = kin.get(key)
        if not isinstance(block, dict) or not block:
            continue
        if key in ("baseline", "healthy"):
            if seen_healthy:
                continue
            seen_healthy = True
        phases.append(key)
    if not phases:
        return ""
    headers = ["Variable", "Unit"] + [phase_labels[p] for p in phases]
    body_rows = []
    for key, label, unit, direction in KINEMATIC_VARS:
        if "shoulder width" in label.lower():
            continue
        shown = f"{label} {'↑' if direction == 'higher' else '↓' if direction == 'lower' else ''}".strip()
        unit_s = "" if unit == "count" else unit
        cells = [_format_kin(key, (kin.get(p) or {}).get(key)) for p in phases]
        if not any(c != MISSING for c in cells):
            continue
        body_rows.append((shown, unit_s, cells, direction))
    if not body_rows:
        return ""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    pre_idx = headers.index("Pre") if "Pre" in headers else -1
    post_idx = headers.index("Post") if "Post" in headers else -1
    if pre_idx >= 0 and post_idx >= 0:
        head += '<th style="text-align:center">Pre → Post</th>'
    rows_html = []
    for shown, unit_s, cells, direction in body_rows:
        tds = f'<td class="metric">{esc(shown)}</td><td class="num">{esc(unit_s)}</td>'
        tds += "".join(f'<td class="num">{esc(c)}</td>' for c in cells)
        if pre_idx >= 0 and post_idx >= 0:
            # cells align to phases, headers offset by 2
            pre_i = phases.index("pre") if "pre" in phases else -1
            post_i = phases.index("post") if "post" in phases else -1
            extra = MISSING
            if pre_i >= 0 and post_i >= 0:
                try:
                    pre_n = float(cells[pre_i])
                    post_n = float(cells[post_i])
                    if direction == "higher":
                        pct = (post_n - pre_n) / abs(pre_n) * 100 if pre_n else 0
                    else:
                        pct = (pre_n - post_n) / pre_n * 100 if pre_n else 0
                    extra = f"{abs(pct):.0f}%"
                except (TypeError, ValueError, ZeroDivisionError):
                    extra = MISSING
            tds += f'<td class="num">{esc(extra)}</td>'
        rows_html.append(f"<tr>{tds}</tr>")
    return (
        '<div class="singlecol"><div class="card">'
        '<div class="badge" style="background:#0d948888">Video Kinematic Analysis</div>'
        '<div class="tblwrap"><table><thead><tr style="background:#0d948888">'
        f"{head}</tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>"
        "</div></div>"
    )


def _narrative(grouped: Dict[str, List[Dict[str, Any]]]) -> str:
    sections = []
    for tool, trows in grouped.items():
        items = [r for r in trows if r.get("delta") != MISSING and r.get("pre") != MISSING and r.get("post") != MISSING]
        if tool == "VAS" and items:
            parts = []
            for r in items:
                try:
                    d = float(r["post"]) - float(r["pre"])
                except (TypeError, ValueError):
                    continue
                trend = "decreased (improvement)" if d < 0 else ("increased (worsening)" if d > 0 else "remained stable")
                parts.append(
                    f"{esc(r['metric'])} went from {esc(r['pre'])} to {esc(r['post'])} (Δ{esc(r['delta'])}), indicating pain {trend}"
                )
            if parts:
                sections.append(
                    '<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0">'
                    f'<strong style="color:#0d9488">Pain Scale (VAS):</strong> {"; ".join(parts)}.</p>'
                )
        elif tool == "VAMS" and items:
            pos_items = [r for r in items if any(n in r["metric"] for n in ("Happy", "Calm"))]
            neg_items = [r for r in items if any(n in r["metric"] for n in ("Sad", "Tense"))]
            parts = []
            if pos_items:
                parts.append("positive moods (" + ", ".join(f"{r['pre']}→{r['post']} (Δ{r['delta']})" for r in pos_items) + ")")
            if neg_items:
                parts.append("negative moods (" + ", ".join(f"{r['pre']}→{r['post']} (Δ{r['delta']})" for r in neg_items) + ")")
            if parts:
                sections.append(
                    '<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0">'
                    f'<strong style="color:#0ea5e9">Mood Scale (VAMS-4):</strong> {esc("; ".join(parts))}.</p>'
                )
        elif tool == "Muscle Control":
            pre_val = next((r["pre"] for r in trows if r["pre"] != MISSING), None)
            post_val = next((r["post"] for r in trows if r["post"] != MISSING), None)
            if pre_val and post_val:
                try:
                    d = float(post_val) - float(pre_val)
                    trend = "improved" if d > 0 else ("declined" if d < 0 else "remained stable")
                    sign = "+" if d > 0 else ""
                    sections.append(
                        '<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0">'
                        f'<strong style="color:#10b981">Muscle Control:</strong> The participant\'s perceived muscle control '
                        f"changed from {esc(pre_val)} to {esc(post_val)} (Δ{sign}{d:.2f}), indicating the feeling of control has {trend}.</p>"
                    )
                except (TypeError, ValueError):
                    pass
        elif tool == "KVIQ" and items:
            imp = sum(1 for r in items if r.get("improving") is True)
            tot = len(items)
            if imp > tot / 2:
                summary = "Most imagery items improved"
            elif imp > 0:
                summary = "Mixed imagery results"
            else:
                summary = "Imagery remained stable"
            vis = [r for r in items if str(r["metric"]).startswith("Visual")]
            kin = [r for r in items if str(r["metric"]).startswith("Kinesthetic")]
            details = []
            if vis:
                details.append(f"visual imagery: {sum(1 for r in vis if r.get('improving') is True)}/{len(vis)} items improved")
            if kin:
                details.append(
                    f"kinesthetic imagery: {sum(1 for r in kin if r.get('improving') is True)}/{len(kin)} items improved"
                )
            sections.append(
                '<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0">'
                f'<strong style="color:#0d9488">Motor Imagery (KVIQ):</strong> {esc(summary)}. In detail, {esc("; ".join(details))}.</p>'
            )
        elif tool == "WMFT" and items:
            time_items = [r for r in items if "Time" in r["metric"]]
            rate_items = [r for r in items if "Rating" in r["metric"]]
            parts = []
            if time_items:
                parts.append(
                    f"task time: {sum(1 for r in time_items if r.get('improving') is True)} faster, "
                    f"{sum(1 for r in time_items if r.get('improving') is False)} slower"
                )
            if rate_items:
                parts.append(
                    f"functional rating: {sum(1 for r in rate_items if r.get('improving') is True)} improved, "
                    f"{sum(1 for r in rate_items if r.get('improving') is False)} declined"
                )
            if parts:
                sections.append(
                    '<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0">'
                    f'<strong style="color:#0ea5e9">Wolf Motor Function (WMFT):</strong> {esc("; ".join(parts))}.</p>'
                )
        elif tool == "Kinematics" and items:
            improved = [r["metric"] for r in items if r.get("improving") is True]
            worsened = [r["metric"] for r in items if r.get("improving") is False]
            parts = []
            if improved:
                parts.append("improved metrics: " + ", ".join(improved))
            if worsened:
                parts.append("declining metrics: " + ", ".join(worsened))
            sections.append(
                '<p style="font-size:12px;color:#334155;line-height:1.8;margin:0 0 12px 0">'
                f'<strong style="color:#f43f5e">Kinematic Analysis:</strong> {len(improved)} of {len(items)} '
                f'kinematic variables showed improvement. {esc("; ".join(parts))}.</p>'
            )
    if not sections:
        return ""
    return (
        '<div class="singlecol pagebreak"><div class="card" style="border-left:6px solid #0d9488">'
        '<div class="badge" style="background:#0d948888;font-size:11px;padding:5px 18px">Clinical Narrative / Klinik Anlatım</div>'
        f'<div style="padding:4px 0">{"".join(sections)}</div></div></div>'
    )


def build_glass_html(patient: Dict[str, Any]) -> str:
    rec = program_patient_record(patient)
    demo = rec.get("demographics") if isinstance(rec.get("demographics"), dict) else {}
    name = _plain(demo.get("name") or demo.get("fullName") or "Participant") or "Participant"
    pid = _plain(demo.get("participantId") or rec.get("_id") or "")
    group = str(demo.get("group") or "")
    stamped = datetime.now(timezone.utc).strftime("%d %b %Y")
    header_bg = "rgba(167,243,208,0.3)" if group == "1" else "rgba(251,207,232,0.4)"
    header_title = "AOMI Group / AOMI Grubu" if group == "1" else "Control Group / Kontrol Grubu"
    rows = build_summary_rows(patient)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["tool"], []).append(row)

    demo_items = [
        ("Age / Yaş", _demo_value("age", demo.get("age"))),
        ("Sex", _demo_value("sex", demo.get("sex"))),
        ("Stroke Type", _demo_value("strokeType", demo.get("strokeType"))),
        ("Affected Side", _demo_value("side", demo.get("side"))),
        ("Time Since Stroke", _demo_value("timeSinceStroke", demo.get("timeSinceStroke"))),
        ("MAS", _plain(demo.get("mas")) or MISSING),
        ("MRC", _plain(demo.get("mrc")) or MISSING),
    ]
    demo_html = "".join(
        f'<div class="demoitem"><span class="demok">{esc(k)}</span><span class="demov">{esc(v)}</span></div>'
        for k, v in demo_items
    )

    notes_src = _plain(demo.get("notes"))
    notes_bits = []
    if demo.get("antispasticDrugs"):
        notes_bits.append(
            '<p style="font-size:11px;color:#334155;margin:0 0 4px">'
            '<strong style="color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">'
            f"Antispastic Drugs / Antispastik İlaçlar:</strong><br>{esc(demo.get('antispasticDrugs'))}</p>"
        )
    if demo.get("otherDrugs"):
        notes_bits.append(
            '<p style="font-size:11px;color:#334155;margin:0 0 4px">'
            '<strong style="color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">'
            f"Other Medications / Diğer İlaçlar:</strong><br>{esc(demo.get('otherDrugs'))}</p>"
        )
    if notes_src:
        notes_bits.append(
            '<p style="font-size:11px;color:#334155;margin:0 0 4px">'
            '<strong style="color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:0.05em">'
            f"Clinical Notes / Klinik Notlar:</strong><br>"
            f'<div style="margin-top:4px;white-space:pre-wrap">{esc(notes_src)}</div></p>'
        )
    notes_html = (
        '<div style="margin-top:14px;padding-top:14px;border-top:1px solid rgba(255,255,255,0.3)">'
        + "".join(notes_bits)
        + "</div>"
        if notes_bits
        else ""
    )

    tool_sections = []
    for tool, trows in grouped.items():
        if tool == "Kinematics":
            continue
        if not any(r["pre"] != MISSING or r["post"] != MISSING for r in trows):
            continue
        meta = TOOL_META.get(tool) or {"label": tool, "color": "#0d9488", "bg": "#f0fdfa"}
        interp = _tool_interp_html(tool, trows)
        if tool == "Muscle Control":
            pre_val = next((r["pre"] for r in trows if r["pre"] != MISSING), MISSING)
            post_val = next((r["post"] for r in trows if r["post"] != MISSING), MISSING)
            if pre_val != MISSING and post_val != MISSING:
                try:
                    delta = f"{float(post_val) - float(pre_val):.2f}"
                except (TypeError, ValueError):
                    delta = MISSING
            else:
                delta = MISSING
            body = (
                f'<tr><td class="metric">Felt Difference</td><td class="num">{esc(pre_val)}</td>'
                f'<td class="num">{esc(post_val)}</td><td class="num">{esc(delta)}</td></tr>'
            )
        else:
            body = "".join(
                "<tr>"
                f'<td class="metric">{esc(r["metric"])}</td>'
                f'<td class="num">{esc(r["pre"])}</td>'
                f'<td class="num">{esc(r["post"])}</td>'
                f'<td class="num">{_delta_cell(r)}</td>'
                "</tr>"
                for r in trows
            )
        tool_sections.append(
            f'<div class="card" style="background:{meta["bg"]}cc;border:1px solid rgba(255,255,255,0.3);'
            f'border-radius:1rem;box-shadow:0 20px 40px -8px rgba(0,0,0,0.08);padding:18px 22px;margin-bottom:20px;">'
            f'<div class="badge" style="background:{meta["color"]}88">{esc(meta["label"])}</div>'
            '<div class="tblwrap"><table><thead>'
            f'<tr style="background:{meta["color"]}88">'
            "<th>Metric / Task</th><th>Pre</th><th>Post</th><th>Change</th>"
            f"</tr></thead><tbody>{body}</tbody></table></div>{interp}</div>"
        )

    summary_items = []
    for tool, trows in grouped.items():
        text = _tool_interp_html(tool, trows)
        if not text:
            continue
        color = (TOOL_META.get(tool) or TOOL_META["VAS"])["color"]
        inner = text.replace("<div class=\"tool-interp\">", "").replace("</div>", "").strip()
        summary_items.append(
            f'<p class="sum-item"><span class="sum-badge" style="background:{color}88">{esc(tool)}</span> {inner}</p>'
        )
    summary_html = (
        '<div class="singlecol pagebreak"><div class="card" style="border-left:6px solid #0d9488">'
        '<div class="badge" style="background:#0d948888;font-size:11px;padding:5px 18px">Summary / Özet</div>'
        f"{''.join(summary_items)}</div></div>"
        if summary_items
        else ""
    )

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Clinical Report - {esc(name)}</title>
<style>{GLASS_CSS}</style></head><body><div class="wrap">
  <div class="header" style="background:{header_bg}">
    <div><h1>{esc(header_title)}</h1><div class="sub">Clinical Assessment Report / Klinik Değerlendirme Raporu</div></div>
    <div class="meta">{esc(stamped)}<br>{esc(name)}</div>
  </div>
  <div class="patient">
    <div class="name">{esc(name)}</div>
    <div class="pid">{("ID: " + esc(pid)) if pid else ""}</div>
    <div class="demogrid">{demo_html}</div>
    {notes_html}
  </div>
  {_ipaq_section(patient)}
  <div class="tools">{''.join(tool_sections)}</div>
  {_video_section(patient)}
  {summary_html}
  {_narrative(grouped)}
</div></body></html>"""


def html_to_pdf(html_doc: str) -> Optional[bytes]:
    try:
        from weasyprint import HTML

        blob = HTML(string=html_doc, base_url=".").write_pdf()
        if blob:
            return bytes(blob)
    except Exception as exc:
        print(f"weasyprint skipped: {exc}", flush=True)

    chrome = shutil.which("google-chrome") or shutil.which("chromium-browser") or shutil.which("chromium")
    if chrome:
        with tempfile.TemporaryDirectory(prefix="nl-glass-") as raw:
            html_path = Path(raw) / "report.html"
            pdf_path = Path(raw) / "report.pdf"
            profile = Path(raw) / "chrome-profile"
            profile.mkdir()
            html_path.write_text(html_doc, encoding="utf-8")
            cmd = [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                "--no-first-run",
                "--no-default-browser-check",
                "--no-pdf-header-footer",
                f"--user-data-dir={profile}",
                f"--print-to-pdf={pdf_path}",
                f"file://{html_path}",
            ]
            proc = subprocess.run(cmd, capture_output=True, timeout=12, check=False)
            if pdf_path.is_file() and pdf_path.stat().st_size > 100:
                return pdf_path.read_bytes()
            print(f"chrome print-to-pdf failed rc={proc.returncode}: {proc.stderr[-400:]}", flush=True)
    return None


def build_glass_pdf(patient: Dict[str, Any]) -> Optional[bytes]:
    return html_to_pdf(build_glass_html(patient))
