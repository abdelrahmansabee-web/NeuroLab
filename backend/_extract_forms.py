# -*- coding: utf-8 -*-
"""One-off: extract text from thesis forms in manuscript f folder."""
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(r"D:\Thesis app\NeuroLab\forms_extract")
OUT.mkdir(exist_ok=True)
BASE = Path(r"D:\Thesis app\manuscript f")

WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    paras = []
    for p in root.iter(f"{WNS}p"):
        texts = [t.text for t in p.iter(f"{WNS}t") if t.text]
        if texts:
            paras.append("".join(texts))
    return "\n".join(paras)


def pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def doc_text_win32(path: Path) -> str:
    import win32com.client

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    doc = word.Documents.Open(str(path.resolve()))
    text = doc.Content.Text
    doc.Close(False)
    word.Quit()
    return text.replace("\r", "\n")


def safe_name(p: Path) -> str:
    return re.sub(r"[^\w\-]+", "_", p.stem)[:60]


TARGETS = [
    "ozgecmis-formu_0.doc",
    "insan-arastirmalar-etik-kurulu-duzeltme-bildirim-formu-21.11.2023 (29).docx",
    "insan-arastirmalari-etik-kurul-basvuru-formu-09.03.2026-1_0 (25).doc",
    "kurum izni biruni (1) (1).docx",
    "Outlook.pdf",
    "Abdelrahman Sabee Proposal (1).docx",
]

# Çigdem file - glob
for p in BASE.glob("*zge*.docx"):
    if "Abdelrahman" not in p.name:
        TARGETS.append(p.name)

for name in TARGETS:
    path = BASE / name
    if not path.exists():
        # try glob for çigdem
        matches = list(BASE.glob(name.split()[0] + "*")) if " " in name else []
        if matches:
            path = matches[0]
        else:
            print("MISSING", name)
            continue
    out = OUT / f"{safe_name(path)}.txt"
    try:
        if path.suffix.lower() == ".docx":
            text = docx_text(path)
        elif path.suffix.lower() == ".pdf":
            text = pdf_text(path)
        elif path.suffix.lower() == ".doc":
            try:
                text = doc_text_win32(path)
            except Exception as e:
                text = f"[Could not read .doc: {e}]"
        else:
            text = "[unknown format]"
        out.write_text(text, encoding="utf-8")
        print(f"OK {path.name} -> {out.name} ({len(text)} chars)")
    except Exception as e:
        print(f"ERR {path.name}: {e}")
