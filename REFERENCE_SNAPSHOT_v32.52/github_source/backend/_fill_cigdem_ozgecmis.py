# -*- coding: utf-8 -*-
"""Fill Istinye ozgecmis-formu_0.doc with Dr. Cigdem Cinar data from her CV file."""
from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path

import win32com.client

BASE = Path(r"D:\Thesis app\manuscript f")
OUT = BASE / "forms_completed"
OUT.mkdir(exist_ok=True)
OUT_COPY = Path(r"D:\Thesis app\NeuroLab\forms_completed")
OUT_COPY.mkdir(exist_ok=True)

TODAY_TR = date.today().strftime("%d/%m/%Y")

CIGDEM = {
    "name": "Çiğdem Çınar",
    "birth": "27.06.1984 / Adana",
    "languages": "İngilizce",
    "workplace": "Biruni Üniversitesi Hastanesi, Fiziksel Tıp ve Rehabilitasyon Anabilim Dalı",
    "phone": "0507 783464",
    "email": "ccinar@biruni.edu.tr",
    "ongoing_edu": "Yok",
    "graduation": (
        "Çukurova Üniversitesi Tıp Fakültesi (Tıp Doktoru); "
        "İstanbul Fizik Tedavi Rehabilitasyon EAH, Fiziksel Tıp ve Rehabilitasyon Uzmanlığı"
    ),
    "grad_years": "2009 (Tıp Fakültesi); 2015 (Uzmanlık)",
    "title": "Doçent Doktor",
    "work_history": (
        "09.2009–05.2010 | Muş Bulanık Devlet Hastanesi | Pratisyen Doktor\n"
        "2011–2015 | İstanbul Fizik Tedavi Rehabilitasyon EAH | Asistan Doktor\n"
        "2015–2022 | İstanbul Fizik Tedavi Rehabilitasyon EAH | Uzman Doktor\n"
        "2022–2023 | Ulus Liv Hospital | Uzman Doktor\n"
        "2023–halen | Biruni Üniversitesi Hastanesi | Doçent Doktor"
    ),
    "iku": "İyi Klinik Uygulamaları (İKU) eğitimi — Biruni Üniversitesi Hastanesi, 27.07.2024",
    "research": (
        "1) Effect of robotic-assisted gait training on functional status in complete spinal cord injury "
        "(Int J Rehabil Res, 2021) — Sorumlu araştırmacı\n"
        "2) Ultrasonographic evaluation of abdominal muscle thickness in adolescent idiopathic scoliosis "
        "(Eur J Phys Rehabil Med, 2021) — Yardımcı araştırmacı\n"
        "3) Ultrasound-Guided Versus Blind Subacromial Steroid Injections (Arch Health Sci Res, 2022) "
        "— Sorumlu araştırmacı\n"
        "4) Hand-Wrist Findings of Rheumatoid Arthritis Patients (Cureus, 2023) — Sorumlu araştırmacı\n"
        "5) Lipedema awareness among medical doctors in Turkey (Phlebology, 2025) — Yardımcı araştırmacı\n"
        "6) Dual pathology in lateral elbow pain (Ir J Med Sci, 2026) — Yardımcı araştırmacı\n"
        "7) Mirror Therapy + Botulinum Toxin A for upper limb spasticity in chronic stroke "
        "(Acupuncture & Electro-Therapeutics Research, 2026) — Yardımcı araştırmacı\n"
        "8) PETTLEP-AOMI üst ekstremite kinematiği RCT (İstinye Üniversitesi tez çalışması, 2026) "
        "— Yardımcı araştırmacı (Biruni Üniversitesi Hastanesi veri toplama merkezi)"
    ),
    "publications": (
        "Terzibaşıoğlu AM, Çınar Ç, Öneş K, et al. Ultrasound-Guided Versus Blind Subacromial "
        "Steroid Injections. Arch Health Sci Res. 2022;9(3):180-185.\n"
        "Çınar Ç, Doğan YE, Harman H, et al. Hand-Wrist Findings of Rheumatoid Arthritis Patients. "
        "Cureus. 2023. doi:10.7759/cureus.46876\n"
        "Bagatir N, Cinar C, Akansel A, et al. Lipedema awareness among medical doctors in Turkey. "
        "Phlebology. 2025;40(9):680-688.\n"
        "Bucak ÖF, Yalcin U, Cinar C, Coskun E. Dual pathology in lateral elbow pain. "
        "Ir J Med Sci. 2026;195(1):383-394.\n"
        "Doran M, Çınar Ç, Tekdemir N, et al. Mirror Therapy + Botulinum Toxin A for upper limb "
        "spasticity in chronic stroke. Acupuncture & Electro-Therapeutics Research. 2026."
    ),
}


def _kill_word() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "WINWORD.EXE"], capture_output=True, check=False)


def replace_after_label(doc, label: str, value: str) -> None:
    rng = doc.Content
    f = rng.Find
    f.ClearFormatting()
    f.Text = label
    f.Forward = True
    f.Wrap = 0
    if not f.Execute():
        return
    ins = doc.Range(rng.End, rng.End)
    ins.Text = " " + value


def fill_istinye_ozgecmis() -> Path:
    _kill_word()
    src = BASE / "ozgecmis-formu_0.doc"
    dst = OUT / "ozgecmis-formu_Cigdem_Cinar_DOLDURULMUS.doc"
    shutil.copy2(src, dst)

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    doc = word.Documents.Open(str(dst.resolve()))
    try:
        pairs = [
            ("Adı soyadı:", CIGDEM["name"]),
            ("Doğum tarihi ve yeri:", CIGDEM["birth"]),
            ("Yabancı dil bilgisi:", CIGDEM["languages"]),
            ("Görev yeri:", CIGDEM["workplace"]),
            ("Telefon No:", CIGDEM["phone"]),
            ("Mail Adresi:", CIGDEM["email"]),
            ("Devam eden eğitim (yüksek lisans / doktora)", CIGDEM["ongoing_edu"]),
            ("Mezun olduğu üniversite / fakülte / Enstitü:", CIGDEM["graduation"]),
            ("Mezuniyet tarihini lütfen belirtiniz (yıl olarak):", CIGDEM["grad_years"]),
            ("Varsa, akademik ünvanları :", CIGDEM["title"]),
            (
                "Bugüne kadar çalıştığı kurum / kuruluşları  lütfen belirtiniz:",
                CIGDEM["work_history"],
            ),
            (
                "varsa insan araştırmaları konusunda aldığı eğitim ve sertifikalar:",
                CIGDEM["iku"],
            ),
            (
                "Varsa, araştırmacı olarak katıldığı insan araştırmaları (klinik, sosyal vb)",
                CIGDEM["research"],
            ),
            (
                "Varsa son 5 yıl içinde hakemli dergilerde yayınlanan makaleler",
                CIGDEM["publications"],
            ),
            ("El yazısıyla adı soyadı:", CIGDEM["name"]),
            ("Tarih (gün/ay/yıl olarak):", TODAY_TR),
        ]
        for label, val in pairs:
            replace_after_label(doc, label, val)
        doc.Save()
    finally:
        try:
            doc.Close(False)
        except Exception:
            pass
        try:
            word.Quit()
        except Exception:
            pass
        _kill_word()
    return dst


def main() -> None:
    path = fill_istinye_ozgecmis()
    shutil.copy2(path, OUT_COPY / path.name)
    note = OUT / "CIGDEM_OZGEGMIS_NOT.txt"
    note.write_text(
        "\n".join(
            [
                "Istinye ozgecmis formu — Dr. Cigdem Cinar",
                f"Doldurulma tarihi: {TODAY_TR}",
                f"Dosya: {path.name}",
                "",
                "Kaynak: Cigdem Cinar Ozgecmis.docx (manuscript f klasoru)",
                "",
                "Manuel:",
                "  • Dogum tarihi CV'de yok — gerekirse el ile ekleyin",
                "  • Islak imza",
                "  • PDF olarak etik dosyasina ekleyin",
            ]
        ),
        encoding="utf-8",
    )
    shutil.copy2(note, OUT_COPY / note.name)
    print("OK", path)


if __name__ == "__main__":
    main()
