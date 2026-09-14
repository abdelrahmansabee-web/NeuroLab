#!/usr/bin/env python3
"""After analyze: keep the upload card simple. Drive overlay matches the in-app player.

The phase cards were showing a camera preview, metric tiles, and a movement
chart after Analyze. Those belong under Validation Video / Kinematic Results.

The Drive file was a native-resolution composite of the camera plus a stretched
display overlay, so it missed the clinic surround color and the variables panel,
and the skeleton looked softer than the on-screen player.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

VIDEO_OFF = (
    'p&&(Se[t.k]||l["".concat(Re(t.k),"_url")])?(0,Un.jsx)("video",{'
    'src:Se[t.k]||l["".concat(Re(t.k),"_url")],'
    'className:"w-full rounded-lg bg-black mb-1.5",controls:!0,playsInline:!0,muted:!0,autoPlay:!1'
    "}):null,"
)
VIDEO_ON = VIDEO_OFF.replace("autoPlay:!1", "autoPlay:!0")

METRICS = (
    'p&&(0,Un.jsx)("div",{className:"grid grid-cols-2 gap-1.5",children:tt.map(e=>{'
    "const n=Wy.find(t=>t.key===e);return n?(0,Un.jsxs)(\"div\",{className:\"rounded-lg border px-2 py-1.5 \".concat(ot(t.c)),"
    'children:[(0,Un.jsx)("p",{className:"text-[9px] font-bold text-white/45 leading-tight",children:n.label}),'
    '(0,Un.jsxs)("p",{className:"text-sm font-mono font-extrabold text-white/90 mt-0.5",'
    "children:[Ze(t.k,e),(0,Un.jsx)(\"span\",{className:\"text-[9px] font-normal text-white/35 ml-0.5\",children:n.unit})]})]},e):null})}),"
)
METRICS_HIDDEN = METRICS.replace("grid grid-cols-2", "sm:hidden grid grid-cols-2")

CHART = (
    "p&&(null===(o=m[t.k])||void 0===o?void 0:o.velocity_profile)&&(0,Un.jsxs)(Un.Fragment,{children:["
    '(0,Un.jsx)("button",{type:"button",onClick:()=>{return e=t.k,void F(t=>a(a({},t),{},{[e]:!t[e]}));var e},'
    'className:"w-full text-[11px] text-white/45 hover:text-white/75 py-1.5 font-medium tracking-wide border '
    'border-white/[0.06] rounded-lg bg-white/[0.03] hover:bg-white/[0.06] transition-colors",'
    'title:P[t.k]?"Hide chart":"Show movement chart",'
    'children:P[t.k]?"\\u25b2 Hide chart":"\\u25bc Movement chart"}),'
    "(0,Un.jsx)(ml,{children:P[t.k]&&(0,Un.jsx)(sl.div,{initial:{height:0,opacity:0},animate:{height:\"auto\",opacity:1},"
    'exit:{height:0,opacity:0},transition:{duration:.25},className:"overflow-hidden",'
    'children:(0,Un.jsx)("div",{className:"rounded-xl border border-white/[0.08] bg-black/30 overflow-hidden",'
    'children:(0,Un.jsx)("div",{className:"w-full h-[140px] p-2 kin-phase-chart",'
    "dangerouslySetInnerHTML:{__html:gS({[t.k]:m[t.k].velocity_profile},!1,!0)}})})})})]})"
)

FT_OLD = (
    "ft=(0,e.useCallback)(()=>{const e=x.current,t=z.current,n=_.current;if(!e||!t||!n)return;"
    "const r=t.getContext(\"2d\");t.width===e.videoWidth&&t.height===e.videoHeight||"
    "(t.width=e.videoWidth||640,t.height=e.videoHeight||480),"
    "r.drawImage(e,0,0,t.width,t.height),r.drawImage(n,0,0,t.width,t.height)},[])"
)

FT_NEW = (
    "ft=(0,e.useCallback)(()=>{const e=x.current,t=z.current,n=_.current,i=T.current;"
    "if(!e||!t||!n)return;const a=t.getContext(\"2d\");if(!a)return;"
    "const s=i&&i.getBoundingClientRect?i.getBoundingClientRect():null;"
    "if(!s||s.width<2||s.height<2){"
    "t.width===e.videoWidth&&t.height===e.videoHeight||(t.width=e.videoWidth||640,t.height=e.videoHeight||480),"
    "a.drawImage(e,0,0,t.width,t.height),a.drawImage(n,0,0,t.width,t.height);return}"
    "const o=n.getBoundingClientRect(),l=e.videoWidth||640,c=o.width>1?l/o.width:1;"
    "let d=Math.round(s.width*c),u=Math.round(s.height*c);"
    "const h=Math.min(1,1920/Math.max(d,u,1));"
    "d=Math.max(2,Math.round(d*h)),u=Math.max(2,Math.round(u*h));"
    "t.width===d&&t.height===u||(t.width=d,t.height=u);"
    "const p=t.width/s.width,f=t.height/s.height;"
    "a.fillStyle=\"#141821\",a.fillRect(0,0,t.width,t.height),a.imageSmoothingEnabled=!0,a.imageSmoothingQuality=\"high\";"
    "try{const m=I.current||i,g=m?window.getComputedStyle(m,\":before\").backgroundImage:\"\","
    "v=/url\\(([\"']?)([^\"')]+)\\1\\)/.exec(g);if(v&&v[2]){if(!t.nlBg||t.nlBgSrc!==v[2])"
    "{const b=new Image;b.crossOrigin=\"anonymous\",b.src=v[2],t.nlBg=b,t.nlBgSrc=v[2]}"
    "const b=t.nlBg;if(b&&b.complete&&b.naturalWidth){const y=t.width/b.naturalWidth,k=t.height/b.naturalHeight,"
    "S=Math.max(y,k),A=(t.width-b.naturalWidth*S)/2,P=(t.height-b.naturalHeight*S)/2;"
    "a.drawImage(b,A,P,b.naturalWidth*S,b.naturalHeight*S),a.fillStyle=\"rgba(8,8,8,0.28)\","
    "a.fillRect(0,0,t.width,t.height)}}}catch(z){}"
    "const pe=function(r,j){if(!r)return;const G=r.getBoundingClientRect();if(G.width<1||G.height<1)return;"
    "const W=(G.left-s.left)*p,V=(G.top-s.top)*f,H=G.width*p,K=G.height*f;"
    "if(\"CANVAS\"===r.tagName||\"VIDEO\"===r.tagName){try{a.drawImage(r,W,V,H,K)}catch(Y){}return}"
    "if(j){const X=window.getComputedStyle(r),$=X.backgroundColor;"
    "if($&&\"rgba(0, 0, 0, 0)\"!==$&&\"transparent\"!==$){a.fillStyle=$;const J=parseFloat(X.borderRadius)||0;"
    "if(J>1){const Q=Math.min(J*p,H/2,K/2);a.beginPath(),a.moveTo(W+Q,V),"
    "a.arcTo(W+H,V,W+H,V+K,Q),a.arcTo(W+H,V+K,W,V+K,Q),a.arcTo(W,V+K,W,V,Q),a.arcTo(W,V,W+H,V,Q),"
    "a.closePath(),a.fill()}else a.fillRect(W,V,H,K)}"
    "const Z=(r.textContent||\"\").trim();if(!r.children.length&&Z)"
    "{a.fillStyle=X.color||\"#fff\";"
    "a.font=(X.fontWeight||\"600\")+\" \"+Math.max(10,parseFloat(X.fontSize)*f)+\"px \"+(X.fontFamily||\"sans-serif\");"
    "a.textBaseline=\"middle\";a.textAlign=\"right\"===X.textAlign?\"right\":\"left\";"
    "a.fillText(Z,\"right\"===a.textAlign?W+H-8:W+8,V+K/2);return}}"
    "for(let ee=0;ee<r.children.length;ee++)pe(r.children[ee],j)};"
    "pe(e,!1),pe(n,!1);const te=R.current;if(te){const ne=te.getBoundingClientRect();ne.width>=40&&pe(te,!0)}},[])"
)

RECORDER_OLD = (
    'const n=t.captureStream(30),r=["video/webm;codecs=vp9","video/webm;codecs=vp8","video/webm"]'
    ".find(e=>MediaRecorder.isTypeSupported(e))||\"video/webm\",i=new MediaRecorder(n,{mimeType:r});"
)
RECORDER_NEW = (
    'const n=t.captureStream(30),r=["video/mp4","video/webm;codecs=vp9","video/webm;codecs=vp8","video/webm"]'
    ".find(e=>MediaRecorder.isTypeSupported(e))||\"video/webm\";"
    "let i;try{i=new MediaRecorder(n,{mimeType:r,videoBitsPerSecond:1e7})}"
    "catch(z){i=new MediaRecorder(n,{mimeType:r})}"
)

DOWNLOAD_OLD = (
    "onDownloadReady:(t,n)=>{if(!n)return;const r=(n.type||\"\").includes(\"mp4\")?\"mp4\":\"webm\";"
    "Nk(\"validation_\".concat(e.k,\"_\").concat((new Date).toISOString().split(\"T\")[0],\".\").concat(r),n,"
    "{patientKey:Ck(c),subfolder:\"videos\"})}"
)
DOWNLOAD_NEW = (
    "onDownloadReady:(t,n)=>{if(!n)return;"
    "Me(e.k,{unifiedVideoBlob:n,unifiedVideoFilename:\"\".concat(e.k,\"_validation_unified.mp4\")});"
    "Nk(\"\".concat(e.k,\"_validation_unified.mp4\"),n,{patientKey:Ck(c),subfolder:\"videos\"})}"
)

REMOVE_SNIPPETS = (
    ("phase-card camera preview", (VIDEO_OFF, VIDEO_ON)),
    ("phase-card metric tiles", (METRICS, METRICS_HIDDEN)),
    ("phase-card movement chart", (CHART,)),
)

REPLACE_SNIPPETS = (
    ("record the visible overlay stage for Drive", FT_OLD, FT_NEW),
    ("higher-bitrate overlay recorder", RECORDER_OLD, RECORDER_NEW),
    ("save overlay recording as the Drive validation video", DOWNLOAD_OLD, DOWNLOAD_NEW),
)


def patch_js_text(text: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    for label, variants in REMOVE_SNIPPETS:
        hit = False
        for old in variants:
            if old in text:
                text = text.replace(old, "", 1)
                applied.append(label)
                hit = True
                break
        if hit:
            continue
        applied.append(f"already {label}")
    for label, old, new in REPLACE_SNIPPETS:
        if new in text:
            applied.append(f"already {label}")
            continue
        if old not in text:
            raise SystemExit(f"pattern not found: {label}")
        text = text.replace(old, new, 1)
        applied.append(label)
    return text, applied


def patch_pwa_reload(root: Path) -> list[str]:
    notes: list[str] = []
    idx = root / "frontend" / "build" / "index.html"
    if idx.is_file():
        html = idx.read_text(encoding="utf-8")
        updated = re.sub(
            r"main\.0626212c\.js(?:\?[^\"']*)?",
            "main.0626212c.js?kin=7",
            html,
        )
        updated = re.sub(
            r'(meta name="nl-version" content=")[^"]+',
            r"\g<1>31.79",
            updated,
            count=1,
        )
        if updated != html:
            idx.write_text(updated, encoding="utf-8")
            notes.append("index kin=7 nl-version 31.79")
    manifest = root / "frontend" / "build" / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return notes
        if data.get("start_url") != "./?v=29.61-pwa":
            data["start_url"] = "./?v=29.61-pwa"
            manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            notes.append("manifest start_url 29.61-pwa")
    return notes


def patch_clinic_card_and_drive(root: Path) -> int:
    js = root / "frontend" / "build" / "static" / "js" / "main.0626212c.js"
    if not js.is_file():
        print("WARN: frontend bundle missing; clinic-card-and-drive not patched")
        return 0
    original = js.read_text(encoding="utf-8", errors="replace")
    updated, applied = patch_js_text(original)
    if updated != original:
        js.write_text(updated, encoding="utf-8")
    print("clinic-card-and-drive:", ", ".join(applied))
    notes = patch_pwa_reload(root)
    if notes:
        print("pwa reload:", ", ".join(notes))
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_clinic_card_and_drive.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_clinic_card_and_drive(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
