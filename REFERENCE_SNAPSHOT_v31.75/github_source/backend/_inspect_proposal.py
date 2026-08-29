# -*- coding: utf-8 -*-
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
p = Path(r"D:\Thesis app\manuscript f\Abdelrahman Sabee Proposal (1).docx")
with zipfile.ZipFile(p) as z:
    root = ET.fromstring(z.read("word/document.xml"))
body = root.find(f".//{WNS}body")
children = list(body)
out = []
for i, ch in enumerate(children[:40]):
    tag = ch.tag.split("}")[-1]
    if tag == "p":
        t = "".join(x.text or "" for x in ch.iter(f"{WNS}t"))
        pPr = ch.find(f"{WNS}pPr")
        box = ""
        if pPr is not None:
            if pPr.find(f"{WNS}pBdr") is not None:
                box = " [BORDER]"
        out.append(f"{i} p{box}: {t[:100]}")
    elif tag == "tbl":
        out.append(f"{i} TABLE rows={len(list(ch.iter(f'{WNS}tr')))}")
    elif tag == "sdt":
        t = "".join(x.text or "" for x in ch.iter(f"{WNS}t"))
        out.append(f"{i} SDT: {t[:100]}")
    else:
        out.append(f"{i} {tag}")
Path(r"D:\Thesis app\NeuroLab\forms_extract\proposal_body_start.txt").write_text(
    "\n".join(out), encoding="utf-8"
)
print("tables", len(list(root.iter(f"{WNS}tbl"))))
print("sdt", len(list(root.iter(f"{WNS}sdt"))))
