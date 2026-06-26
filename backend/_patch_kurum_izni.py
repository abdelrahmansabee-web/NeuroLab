# -*- coding: utf-8 -*-
"""Apply Biruni kurum izni revisions — researchers from proposal."""
from pathlib import Path

from docx import Document

PI_BLOCK = (
    "1. Araştırma Sorumluları (Unvanı, Adı ve Soyadı): "
    "Yüksek Lisans Öğrencisi / Fizyoterapist, Abdelrahman Walid Hamza Mohamed Elsayed Sabee\n"
    "Kurum: İstinye Üniversitesi Liv Bahçeşehir Hastanesi, Nörorehabilitasyon Kliniği"
)
ASST_BLOCK = (
    "2. Yardımcı Araştırmacılar (Unvanı, Adı ve Soyadı):\n\n"
    "Prof. Dr. Yakup Krespi\n"
    "Kurum: İstinye Üniversitesi Liv Bahçeşehir Hastanesi, Nöroloji Anabilim Dalı\n\n"
    "Dr. Öğr. Üyesi Begüm Kara Kaya (Tez Danışmanı)\n"
    "Kurum: Biruni Üniversitesi, Fizyoterapi ve Rehabilitasyon Anabilim Dalı\n\n"
    "Doç. Dr. Çiğdem Çınar (Yardımcı Araştırmacı)\n"
    "Kurum: Biruni Üniversitesi Hastanesi, Fiziksel Tıp ve Rehabilitasyon Anabilim Dalı"
)

TARGETS = [
    Path(r"D:\Thesis app\manuscript f\REVIZYON_PAKETI\kurum_izni_biruni_DOLDURULMUS.docx"),
    Path(r"D:\Thesis app\manuscript f\REVIZYON_PAKETI\kurum_izni_biruni_DOLDURULMUS_IMZALI.docx"),
    Path(r"D:\Thesis app\manuscript f\forms_completed\kurum_izni_biruni_DOLDURULMUS.docx"),
]


def patch(path: Path) -> None:
    doc = Document(str(path))
    in_asst = False
    asst_done = False
    for p in doc.paragraphs:
        t = p.text.strip()
        if t.startswith("1. Araştırma Sorumluları"):
            p.text = PI_BLOCK
            in_asst = False
        elif t.startswith("2. Yardımcı Araştırmacılar"):
            p.text = ASST_BLOCK
            in_asst = True
            asst_done = True
        elif asst_done and in_asst and (
            t.startswith("Doç. Dr. Çiğdem")
            or t.startswith("Dr. Öğr. Üyesi Begüm")
            or t.startswith("Prof. Dr. Yakup")
            or t.startswith("Doğum tarihi")
            or (t.startswith("Kurum:") and "Anabilim" in t)
        ):
            if not t.startswith("3."):
                p.text = ""
        elif t.startswith("3. Tıbbi"):
            in_asst = False
        elif t in ("Kurum:", "Kurum: "):
            p.text = ""
    doc.save(str(path))


def main() -> None:
    for path in TARGETS:
        if not path.exists():
            print(f"SKIP: {path}")
            continue
        patch(path)
        print(f"OK: {path}")


if __name__ == "__main__":
    main()
