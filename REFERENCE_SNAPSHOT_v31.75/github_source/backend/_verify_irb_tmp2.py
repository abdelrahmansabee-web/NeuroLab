from pathlib import Path
import re
doc = Path(r"D:\Thesis app\NeuroLab\forms_extract\verify_irb_comprehensive.txt").read_text(encoding="utf-8")
pdf = Path(r"D:\Thesis app\NeuroLab\forms_extract\_pdf_ref_tmp.txt").read_text(encoding="utf-8")

def ref_stats(label, text):
    # section after GEREKCE or KAYNAK
    for key in ["KAYNAKLAR", "Kaynaklar", "GEREKÇESİ", "GEREKCESI"]:
        i = text.find(key)
        if i >= 0:
            seg = text[i:i+12000]
            break
    else:
        seg = text
    years = len(re.findall(r"\b(19|20)\d{2}\b", seg))
    doi = len(re.findall(r"doi", seg, re.I))
    print(label, "chars", len(text), "seg_chars", len(seg), "year_tokens", years, "doi", doi)

ref_stats("DOC", doc)
ref_stats("PDF", pdf)

# missing in doc vs pdf (simple keyword diff)
keywords = ["MediaPipe", "Reach", "Wipe", "WMFT", "MAS", "1000 TL", "17", "Krespi", "Çiğdem", "Cigdem", "NeuroLab", "PETTLEP", "Pettlep", "AOMI"]
for k in keywords:
    d = k.lower() in doc.lower()
    p = k.lower() in pdf.lower()
    if d != p:
        print("DIFF", k, "doc", d, "pdf", p)

# count parenthetical refs like Author et al
print("DOC et al count", len(re.findall(r"et al", doc, re.I)))
print("PDF et al count", len(re.findall(r"et al", pdf, re.I)))
