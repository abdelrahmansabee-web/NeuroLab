# -*- coding: utf-8 -*-
"""Fill Istinye IRB form — PDF detail, black unchanged / red revisions."""
from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path

import win32com.client

from _irb_form_content_tr import (
    BUTCE,
    DAHIL_KRITER_SEGMENTS,
    DAHIL_SEGMENTS,
    GEREKCE_SEGMENTS,
    HARIC_KRITER,
    ISTATISTIK_SEGMENTS,
    KAYNAKLAR_SEGMENTS,
    REVISION_NOTE,
    STUDY_TITLE_TR,
    VERI_SEGMENTS,
)

BASE = Path(r"D:\Thesis app\manuscript f")
SRC = BASE / "insan-arastirmalari-etik-kurul-basvuru-formu-09.03.2026-1_0 (25).doc"
OUT_DIR = BASE / "forms_completed"
OUT = OUT_DIR / "insan-arastirmalari-etik-kurul-basvuru-formu-DOLDURULMUS.doc"
TODAY_TR = f"{date.today().day:02d}/{date.today().month:02d}/{date.today().year}"

ADVISOR = {
    "name": "Dr. Öğr. Üyesi Begüm Kara Kaya",
    "org": "Biruni Üniversitesi, Sağlık Bilimleri Fakültesi, Fizyoterapi ve Rehabilitasyon Bölümü",
    "contact": "begum.kara@biruni.edu.tr",
    "phone": "0535 572 00 21",
}
PI = {
    "title": "Fzt. / Yüksek Lisans Öğrencisi",
    "name": "Abdelrahman Walid Hamza Mohamed Elsayed Sabee",
    "org": "İstinye Üniversitesi, Lisansüstü Eğitim Enstitüsü, Fizyoterapi ve Rehabilitasyon Anabilim Dalı",
    "contact": "abdelrahman.sabee@stu.istinye.edu.tr",
    "phone": "+90 537 960 05 20",
}
COINV = [
    {
        "name": "Prof. Dr. Yakup Krespi",
        "org": "İstinye Üniversitesi Tıp Fakültesi, Nöroloji Anabilim Dalı",
        "contact": "ykrespi@gmail.com",
        "phone": "+90 530 469 81 18",
        "red": False,
    },
    {
        "name": "Doç. Dr. Çiğdem Çınar",
        "org": "Biruni Üniversitesi Hastanesi, Fiziksel Tıp ve Rehabilitasyon Anabilim Dalı",
        "contact": "ccinar@biruni.edu.tr",
        "phone": "0507 783464",
        "red": True,
    },
]

BLACK = 0
RED = 6


def _kill_word() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "WINWORD.EXE"], capture_output=True, check=False)


def _close_word(word, doc, save: bool = True) -> None:
    try:
        if save:
            doc.Save()
        doc.Close(False)
    except Exception:
        pass
    try:
        word.Quit()
    except Exception:
        pass
    _kill_word()


def _find_after(doc, label: str) -> int | None:
    rng = doc.Content
    f = rng.Find
    f.ClearFormatting()
    f.Text = label
    f.Forward = True
    f.Wrap = 0
    if not f.Execute():
        return None
    return rng.End


def _insert_at(doc, pos: int, text: str, red: bool = False) -> int:
    ins = doc.Range(pos, pos)
    ins.Text = text
    ins.Font.ColorIndex = RED if red else BLACK
    try:
        ins.ListFormat.RemoveNumbers()
    except Exception:
        pass
    return ins.End


def _insert_segments_after(doc, label: str, segments: list[tuple[str, bool]], lead: str = "\n") -> None:
    pos = _find_after(doc, label)
    if pos is None:
        return
    first = True
    for text, is_red in segments:
        chunk = (lead if first else "") + text
        first = False
        pos = _insert_at(doc, pos, chunk, red=is_red)


def _insert_after(doc, label: str, text: str, red: bool = False) -> None:
    pos = _find_after(doc, label)
    if pos is None:
        return
    _insert_at(doc, pos, text, red=red)


def _set_checkbox(doc, idx: int, checked: bool) -> None:
    doc.FormFields(idx).CheckBox.Value = checked


def fill() -> Path:
    _kill_word()
    OUT_DIR.mkdir(exist_ok=True)
    shutil.copy2(SRC, OUT)

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    doc = word.Documents.Open(str(OUT.resolve()))

    try:
        _insert_after(doc, "Tarih:", TODAY_TR, red=False)
        _insert_after(doc, "PROJENİN ADI:", "\n" + STUDY_TITLE_TR, red=True)

        for idx in (4, 7, 9, 11, 17, 18, 20, 22, 26):
            _set_checkbox(doc, idx, True)

        t1 = doc.Tables(1)
        t1.Cell(2, 1).Range.Text = ADVISOR["name"]
        t1.Cell(2, 2).Range.Text = ADVISOR["org"]
        t1.Cell(2, 3).Range.Text = f"{ADVISOR['phone']} / {ADVISOR['contact']}"
        for c in range(1, 4):
            t1.Cell(2, c).Range.Font.ColorIndex = BLACK

        t2 = doc.Tables(2)
        t2.Cell(2, 1).Range.Text = PI["title"] + "\n" + PI["name"]
        t2.Cell(2, 2).Range.Text = PI["org"]
        t2.Cell(2, 3).Range.Text = f"{PI['phone']} / {PI['contact']}"
        for c in range(1, 4):
            t2.Cell(2, c).Range.Font.ColorIndex = BLACK

        t3 = doc.Tables(3)
        for row_idx, coinv in enumerate(COINV, start=2):
            if row_idx > t3.Rows.Count:
                t3.Rows.Add()
            t3.Cell(row_idx, 1).Range.Text = coinv["name"]
            t3.Cell(row_idx, 2).Range.Text = coinv["org"]
            t3.Cell(row_idx, 3).Range.Text = f"{coinv['phone']} / {coinv['contact']}"
            color = RED if coinv["red"] else BLACK
            for c in range(1, 4):
                t3.Cell(row_idx, c).Range.Font.ColorIndex = color

        _insert_segments_after(doc, "ARAŞTIRMANIN GEREKÇESİ, AMACI VE KAYNAKLARI", GEREKCE_SEGMENTS)
        _insert_segments_after(
            doc,
            "WMFT-4 skorunda anlamlı iyileşmelere yol açar.",
            KAYNAKLAR_SEGMENTS,
            lead="\n\n",
        )
        _insert_after(doc, "BMC Med. 2011;9:75.", "\n\n" + REVISION_NOTE + "\n", red=True)

        t4 = doc.Tables(4)
        t4.Cell(2, 4).Range.Text = "12 ay (Şubat 2026 – Şubat 2027)"
        t4.Cell(3, 1).Range.Text = "Hasta (İnme / Stroke)\r"
        t4.Cell(3, 2).Range.Text = "28"
        t4.Cell(3, 3).Range.Text = "40–80"
        t4.Cell(5, 2).Range.Text = "28"

        _insert_after(
            doc,
            "Kurum/Kuruluş Adı ve Adresi:",
            "\nİstinye Üniversitesi Liv Bahçeşehir Hastanesi, Nörorehabilitasyon Kliniği, İstanbul\n",
            red=False,
        )
        pos = _find_after(doc, "Nörorehabilitasyon Kliniği, İstanbul")
        if pos is not None:
            pos = _insert_at(
                doc,
                pos,
                "\nBiruni Üniversitesi Hastanesi, Fiziksel Tıp ve Rehabilitasyon Polikliniği, "
                "İstanbul (çok merkezli veri toplama merkezi — revizyon kapsamında eklenmiştir)\n",
                red=True,
            )

        _insert_segments_after(doc, "VERİ TOPLAMA YÖNTEMİ", VERI_SEGMENTS)

        _insert_segments_after(
            doc,
            "ARAŞTIRMAYA DAHİL EDİLME, HARİÇ TUTULMA VE ARAŞTIRMADAN ÇIKARILMA KRİTERLERİ",
            DAHIL_SEGMENTS,
        )
        _insert_segments_after(doc, "Araştırmaya Dahil Olma Kriterleri:", DAHIL_KRITER_SEGMENTS)
        _insert_after(doc, "Araştırmaya Hariç Olma Kriterleri:", "\n" + HARIC_KRITER + "\n", red=False)

        _insert_segments_after(doc, "UYGULANACAK YAKLAŞIM VE İSTATİSTİKSEL YÖNTEM", ISTATISTIK_SEGMENTS)
        _insert_after(doc, "DESTEK VE BÜTÇE BİLGİSİ", "\n" + BUTCE + "\n", red=False)
        _insert_after(doc, "El yazısıyla adı soyadı:", " " + PI["name"], red=False)

    finally:
        _close_word(word, doc)

    for dest in (
        Path(r"D:\Thesis app\NeuroLab\forms_completed") / OUT.name,
        BASE / "REVIZYON_PAKETI" / OUT.name,
    ):
        dest.parent.mkdir(exist_ok=True)
        shutil.copy2(OUT, dest)

    return OUT


if __name__ == "__main__":
    p = fill()
    print(f"OK: {p}")
