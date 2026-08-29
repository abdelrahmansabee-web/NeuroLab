from pathlib import Path
import re
text = Path(r"D:\Thesis app\NeuroLab\forms_extract\verify_irb_comprehensive.txt").read_text(encoding="utf-8")
text_lower = text.lower()
checks = [
    ("Turkish title keywords", any(k in text for k in ["Aksiyon", "Gözlem", "Gozlem", "AOMI", "inme", "İnme", "Inme"])),
    ("Krespi", "Krespi" in text),
    ("Cigdem/Cinar", any(k in text for k in ["Çiğdem", "Cigdem", "Çınar", "Cinar", "ccinar"])),
    ("17 dk protocol", bool(re.search(r"17\s*(dk|dakika|min)", text, re.I))),
    ("MediaPipe", "mediapipe" in text_lower),
    ("Reach and Wipe", ("Reach" in text and "Wipe" in text)),
    ("WMFT-4", "WMFT" in text),
    ("MAS threshold", bool(re.search(r"MAS\s*[\u2264<=]\s*2", text)) or ("Modified Ashworth" in text and "2" in text)),
    ("1000 TL budget", bool(re.search(r"1000\s*TL", text))),
    ("PI phone", "537 960 05 20" in text or "5379600520" in text.replace(" ", "")),
    ("Advisor phone", "535 572 00 21" in text),
    ("Krespi phone", "530 469 81 18" in text or "5304698118" in text.replace(" ", "")),
    ("Cigdem phone", "507 783464" in text or "0507 783464" in text),
]
print("=== CHECKS ===")
for name, ok in checks:
    print(name + ":", "PASS" if ok else "FAIL")
ref_markers = ["J Neurol Phys Ther", "doi", "PubMed", "Stroke", "BMC", "Front", "Neurorehabil", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025"]
hits = [m for m in ref_markers if m.lower() in text_lower]
print("Reference markers:", len(hits), hits)
idx = text.find("PROJEN")
if idx >= 0:
    print("TITLE AREA:", text[idx:idx+400].replace("\r", " ")[:400])
idx = text.find("DESTEK")
if idx >= 0:
    print("BUDGET AREA:", text[idx:idx+500].replace("\r", " ")[:500])
