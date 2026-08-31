#!/usr/bin/env python3
"""Keep kinematics results after Save / sessionKey remap, and retry analyze polls.

The live clinic bundle wipes neuro_kin_results whenever sessionKey changes and
analysisResults is empty. First Save remaps sessionKey from participantId to
_loadedId, so completed analysis disappears while the camera file stays in the
picker. Progress polls also fail closed on one network error.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

WIPE_OLD = (
    "(0,e.useEffect)(()=>{if(!h)return;const e=null===l||void 0===l?void 0:l.analysisResults;"
    'if(e&&"object"===typeof e&&Object.keys(e).length>0){const t=a({},e);delete t.during,g(t),'
    "localStorage.setItem(vS,JSON.stringify(t))}else g({}),localStorage.removeItem(vS)},[h])"
)

WIPE_NEW = (
    "(0,e.useEffect)(()=>{if(!h)return;const e=null===l||void 0===l?void 0:l.analysisResults;"
    'if(e&&"object"===typeof e&&Object.keys(e).length>0){const t=a({},e);delete t.during,'
    "g(n=>a(a({},n),t));try{localStorage.setItem(vS,JSON.stringify(t))}catch(QS){}}},[h]),"
    "(0,e.useEffect)(()=>{if(!Ce)return;let n=!1;(async()=>{try{const e=[\"pre\",\"post\",\"baseline\"],t={};"
    "for(const r of e){const i=await H_(Ce,r),o=null===i||void 0===i?void 0:i.kinematicsSnapshot;"
    'if(o&&"object"===typeof o&&Object.keys(o).length>0)t[r]=o}'
    "if(!n&&Object.keys(t).length>0)g(e=>a(a({},t),e))}catch(i){}})();return()=>{n=!0}},[Ce])"
)

SESSIONKEY_OLD = (
    "sessionKey:Ee._loadedId||(null===(t=Ee.demographics)||void 0===t?void 0:t.participantId)"
)
SESSIONKEY_NEW = (
    "sessionKey:(null===(t=Ee.demographics)||void 0===t?void 0:t.participantId)||Ee._loadedId"
)

SYNC_MERGE_OLD = (
    "if(e)i(t=>a(a({},t),e)),null!==(t=e.kinematics)&&void 0!==t&&t.analysisResults&&"
    "localStorage.setItem(vS,JSON.stringify(e.kinematics.analysisResults))"
)
SYNC_MERGE_NEW = (
    "if(e)i(t=>{const n=a(a({},t),e),r=null===t||void 0===t?void 0:t.kinematics,"
    "o=null===e||void 0===e?void 0:e.kinematics,c=null===o||void 0===o?void 0:o.analysisResults;"
    'if(!(c&&"object"===typeof c&&Object.keys(c).length>0)&&r&&r.analysisResults)'
    "n.kinematics=a(a({},o||r||{}),{},{analysisResults:r.analysisResults});return n}),"
    "null!==(t=e.kinematics)&&void 0!==t&&t.analysisResults&&"
    "localStorage.setItem(vS,JSON.stringify(e.kinematics.analysisResults))"
)

POLL_OLD = (
    "if(_.job_id&&_.async&&!i){const n=_.job_id,i=1400;for(;;){if(r.signal.aborted)"
    '{const e=new Error("Analysis cancelled");throw e.name="AbortError",e}'
    'const s=await fetch("".concat(pS,"/analyze-progress/").concat(encodeURIComponent(n)),'
    '{signal:r.signal});if(!s.ok)throw new Error("Progress poll failed (".concat(s.status,")"));'
    "const o=await s.json();"
)

POLL_NEW = (
    "if(_.job_id&&_.async&&!i){const n=_.job_id,i=1400;"
    'try{sessionStorage.setItem("neuro_kin_analyze_ui",JSON.stringify({phase:t,job_id:n,pct:5,step:"Analyzing\\u2026"}))}'
    "catch(f){}for(;;){if(r.signal.aborted){const e=new Error(\"Analysis cancelled\");"
    'throw e.name="AbortError",e}let s=null,tries=0,lastErr="Progress poll failed";'
    "for(;tries<8;tries+=1){try{s=await fetch("
    '"".concat(pS,"/analyze-progress/").concat(encodeURIComponent(n)),{signal:r.signal});'
    "if(s.ok)break;lastErr=\"Progress poll failed (\".concat(s.status,\")\");"
    "if(401===s.status||403===s.status)throw new Error(lastErr)}"
    'catch(qg){if(qg&&"AbortError"===qg.name)throw qg;lastErr=qg&&qg.message||lastErr;s=null}'
    "await new Promise(e=>setTimeout(e,i))}if(!s||!s.ok)throw new Error(lastErr);const o=await s.json();"
)

RESULT_OLD = (
    'const s=await fetch("".concat(pS,"/analyze-result/").concat(encodeURIComponent(n)),'
    '{signal:r.signal});if(!s.ok){let e="Server error ".concat(s.status);'
    "try{const t=await s.json();t.error&&(e+=\": \".concat(t.error))}catch(qg){}"
    "throw new Error(e)}_=await s.json()"
)

RESULT_NEW = (
    'let s=null,tries=0,lastErr="Server error";for(;tries<8;tries+=1){'
    'try{s=await fetch("".concat(pS,"/analyze-result/").concat(encodeURIComponent(n)),'
    '{signal:r.signal})}catch(qg){if(qg&&"AbortError"===qg.name)throw qg;s=null;'
    'lastErr=qg&&qg.message||"Server error"}if(s&&s.ok)break;'
    "if(s&&(401===s.status||403===s.status)){let e=\"Server error \".concat(s.status);"
    "try{const t=await s.json();t.error&&(e+=\": \".concat(t.error))}catch(qg){}throw new Error(e)}"
    'lastErr=s?"Server error ".concat(s.status):lastErr;await new Promise(e=>setTimeout(e,i))}'
    "if(!s||!s.ok)throw new Error(lastErr);_=await s.json()"
)

PATCHES = (
    ("keep kinematics on sessionKey remap", WIPE_OLD, WIPE_NEW),
    ("prefer participantId for sessionKey", SESSIONKEY_OLD, SESSIONKEY_NEW),
    ("keep local analysisResults on Sync merge", SYNC_MERGE_OLD, SYNC_MERGE_NEW),
    ("retry analyze-progress polls", POLL_OLD, POLL_NEW),
    ("retry analyze-result fetch", RESULT_OLD, RESULT_NEW),
)


def patch_js_text(text: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    for label, old, new in PATCHES:
        if new in text and old not in text:
            applied.append(f"already {label}")
            continue
        if old not in text:
            raise SystemExit(f"pattern not found: {label}")
        text = text.replace(old, new, 1)
        applied.append(label)
    return text, applied


def cache_bust_index(html: str) -> str:
    return re.sub(
        r"main\.0626212c\.js(?:\?[^\"']*)?",
        "main.0626212c.js?kin=1",
        html,
    )


def patch_keep_kin_results(root: Path) -> int:
    js = root / "frontend" / "build" / "static" / "js" / "main.0626212c.js"
    if not js.is_file():
        print("WARN: frontend bundle missing; kinematics keep-results not patched")
        return 0
    original = js.read_text(encoding="utf-8", errors="replace")
    updated, applied = patch_js_text(original)
    if updated != original:
        js.write_text(updated, encoding="utf-8")
    print("keep-kin-results:", ", ".join(applied))
    idx = root / "frontend" / "build" / "index.html"
    if idx.is_file():
        html = idx.read_text(encoding="utf-8")
        busted = cache_bust_index(html)
        if busted != html:
            idx.write_text(busted, encoding="utf-8")
            print("cache-bust index.html main JS ?kin=1")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_keep_kin_results.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_keep_kin_results(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
