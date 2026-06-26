# -*- coding: utf-8 -*-
"""Fill Istinye ethics revision forms from manuscript/proposal data."""
from __future__ import annotations

import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import date
from pathlib import Path

import win32com.client

BASE = Path(r"D:\Thesis app\manuscript f")
OUT = BASE / "forms_completed"
OUT.mkdir(exist_ok=True)
OUT_COPY = Path(r"D:\Thesis app\NeuroLab\forms_completed")
OUT_COPY.mkdir(exist_ok=True)

TODAY = date.today().strftime("%d/%m/%Y")
TODAY_TR = f"{date.today().day:02d}/{date.today().month:02d}/{date.today().year}"

STUDY_TITLE = (
    "Immediate Effects of a Single Session of PETTLEP-Based Action Observation "
    "and Motor Imagery (AOMI) on Upper Limb Kinematics in Stroke Survivors: "
    "A Randomized Controlled Trial"
)
STUDY_TITLE_TR = (
    "İnme Sonrası Tek Seans PETTLEP Temelli Eylem Gözlemi ve Motor İmgeleme "
    "(AOMI) Uygulamasının Üst Ekstremite Kinematiği Üzerindeki Anlık Etkileri: "
    "Randomize Kontrollü Çalışma"
)

PI = {
    "name": "Abdelrahman Walid Hamza Mohamed Elsayed Sabee",
    "short": "Abdelrahman Walid Hamza Mohamed Elsayed Sabee",
    "title": "Yüksek Lisans Öğrencisi / Fizyoterapist",
    "org": "İstinye Üniversitesi, Lisansüstü Eğitim Enstitüsü, Fizyoterapi ve Rehabilitasyon Anabilim Dalı",
    "contact": "abdelrahman.sabee@stu.istinye.edu.tr",
    "phone": "[CEP TELEFONU — doldurunuz]",
}

ADVISOR = {
    "name": "Dr. Öğr. Üyesi Begüm Kara Kaya",
    "org": "Biruni Üniversitesi, Fizyoterapi ve Rehabilitasyon Anabilim Dalı",
    "contact": "begum.kara@biruni.edu.tr",
    "phone": "[CEP TELEFONU — doldurunuz]",
}

COINV = {
    "name": "Doç. Dr. Çiğdem Çınar",
    "org": "Biruni Üniversitesi Hastanesi, Fiziksel Tıp ve Rehabilitasyon Anabilim Dalı",
    "contact": "ccinar@biruni.edu.tr",
    "phone": "0507 783464",
}

SITES = (
    "1) İstinye Üniversitesi Liv Bahçeşehir Hastanesi, Nörorehabilitasyon Kliniği, "
    "İstanbul\n"
    "2) Biruni Üniversitesi Hastanesi, Fiziksel Tıp ve Rehabilitasyon Polikliniği, İstanbul "
    "(çok merkezli veri toplama merkezi — revizyon kapsamında eklenmiştir)"
)

RATIONALE = """Stroke sonrası üst ekstremite motor bozukluğu yetişkinlerde önemli bir fonksiyonel kısıtlılık nedenidir. Hareket pürüzsüzlüğündeki bozulma (duraklama yüzdesi), gövde kompensasyonu ve omuz yükselmesi, merkezi motor planlama ve yürütme bozukluklarını yansıtır. PETTLEP çerçevesinde yapılandırılmış Eylem Gözlemi ve Motor İmgeleme (AOMI), fiziksel efor gerektirmeden motor yolları hedefleyebilir; ancak tek seanslı AOMI'nin anlık kinematik etkileri objektif markerless analizle yeterince araştırılmamıştır.

Bu randomize kontrollü çalışma, inme sonrası bireylerde tek seans PETTLEP temelli AOMI'nin hareket pürüzsüzlüğü (smoothness_pause_pct; birincil sonuç), toplam hareket süresi, gövde-kompanzasyon oranı, omuz dikey yer değiştirmesi, tepe el hızı ve üst ekstremite fonksiyonu (WMFT-4) üzerindeki anlık etkilerini, zaman eşleştirilmiş bilişsel ve somatik kontrol koşulu ile karşılaştırmayı amaçlamaktadır.

Literatür: Guerra et al. (2017); Kim & Lee (2022); Holmes & Collins (2001); Schwarz et al. (2022); Lakshminarayanan et al. (2023); Uğur et al. (2021) KVIQ-10; MediaPipe markerless kinematik analiz.

REVİZYON (onaylanmış protokolde değişiklik): Çalışma çok merkezli hale getirilmiş; Biruni Üniversitesi Hastanesi ikinci veri toplama merkezi olarak eklenmiş ve Doç. Dr. Çiğdem Çınar yardımcı araştırmacı olarak ekibe dahil edilmiştir."""

INCLUSION = """• 40–80 yaş arası kadın/erkek yetişkinler
• Tek taraflı iskemik veya hemorajik inme tanısı
• Etkilenen üst ekstremitede artık gönüllü hareket bulunması
• Hafif-orta spastisite (Modified Ashworth Skalası ≤ 2)
• Basit talimatları anlayabilme (MMSE ≥ 21)
• Tıbbi olarak stabil olma
• En az 30 dk desteksiz oturabilme ve kısa bilişsel-motor egzersizleri yapabilme"""

EXCLUSION = """• İnme dışı santral sinir sistemi hastalıkları (Parkinson, MS, TBI vb.)
• Üst ekstremite hareketini kısıtlayan ortopedik/muskuloskeletal durumlar (sabit kontraktür, ciddi eklem deformitesi vb.)
• Görevi veya motor imgelemeyi engelleyen ciddi duyu kaybı, görsel ihmal veya dikkatsizlik
• Kontrolsüz nöbet, ciddi kardiyovasküler instabilite veya imgelemeye kontrendikasyon
• Araştırma protokolüne uyum sağlayamama veya gönüllü geri çekilme"""

METHODS = """Tasarım: Tek kör, ön test–son test, prospektif paralel grup randomize kontrollü çalışma (RCT); çok merkezli (İstinye Üniversitesi Liv Bahçeşehir Hastanesi Nörorehabilitasyon Kliniği + Biruni Üniversitesi Hastanesi FTR Polikliniği).

Örneklem: n=28 (grup başına 14); G*Power ile planlanmış; permütasyon blok randomizasyon (1:1); cinsiyet ve MAS (0–1+ / 2) stratifikasyonu; körleme: katılımcılar kör olamaz, kinematik çıkarımı otomatik/kör.

Görev: Reach & Wipe (havlu ile masada ulaşma-silme); pre/post üç deneme, ortalama analiz.

PETTLEP çerçevesi (Holmes & Collins, 2001):
P: Gerçek oturma düzeni, normal kıyafet, gerçek havlu. E: Değerlendirme ile aynı oda/masa düzeni. T: Reach & Wipe, günlük yaşama uygun. T: Gerçek zamanlı imgeleme (kritik); 3 sn ulaş / 3 sn silme / 3 sn dönüş sayımı. L: Bloklar arası düzeltici rehberlik. E: Rahatlık, güven, doğal kas hissi. P: Watch’ta dış (3. kişi), Imagine’da iç (1. kişi) perspektif.

Deneysel müdahale (PETTLEP-AOMI; toplam ~17 dk; müdahale sırasında fiziksel uygulama YOK):
• 2 dk kalibrasyon (notice–name–transfer; etkilenmemiş uzuv).
• 5 blok × 3 dk: Watch 45 sn (ayna videolu eylem gözlemi) + Imagine 75 sn (gerçek zamanlı kinestetik MI, kulaklık script) + Rest 60 sn.
• Fiziksel Reach & Wipe yalnızca pre/post değerlendirmede.

Kontrol: ~17 dk eşleştirilmiş; 2 dk giriş gevşemesi + 5 blok × 3 dk Beden Taraması / Mekânsal Navigasyon (alternatif).

Ölçümler: MediaPipe + ZoeDepth (NeuroLab); birincil sonuç smoothness_pause_pct; ikincil kinematikler (total_duration_s, total_trunk_palm_ratio, shoulder_vert_norm, total_peak_velocity); WMFT-4, KVIQ-10, VAMS-4, IPAQ, MDRS, VAS.

İstatistik: 2 (Grup) × 2 (Zaman) karma ANOVA; ITT; LOCF; Holm–Bonferroni (ikincil kinematik ailesi)."""

CV = {
    "birth": "[DOĞUM TARİHİ VE YERİ — doldurunuz]",
    "languages": "Arapça (ana dil), İngilizce (ileri), Türkçe (orta)",
    "workplace": "İstinye Üniversitesi Liv Bahçeşehir Hastanesi, Nörorehabilitasyon Kliniği",
    "phone": "[CEP TELEFONU — doldurunuz]",
    "email": "abdelrahman.sabee@stu.istinye.edu.tr",
    "ongoing": "İstinye Üniversitesi, Fizyoterapi ve Rehabilitasyon Yüksek Lisans Programı (Tezli)",
    "grad_uni": "[LİSANS MEZUNİYET ÜNİVERSİTESİ / FAKÜLTE — doldurunuz]",
    "grad_year": "[LİSANS MEZUNİYET YILI — doldurunuz]",
    "title": "Fizyoterapist / Yüksek Lisans Öğrencisi",
    "work_history": (
        "[İŞ TECRÜBESİ — kurum, tarih aralığı ve görev olarak doldurunuz]\n"
        "Örnek: … – … | … Hastanesi / Kliniği | Fizyoterapist"
    ),
    "training": "İyi Klinik Uygulamaları (İKU) eğitimi — [tarih/kurum varsa ekleyiniz]",
    "research": (
        "Mevcut tez çalışması: PETTLEP temelli AOMI ve üst ekstremite kinematiği RCT "
        f"({date.today().year}) — Sorumlu Araştırmacı"
    ),
    "publications": "[Yayın yoksa: Henüz hakemli dergi yayını bulunmamaktadır.]",
}

REVISION_RESPONSES = f"""Sayın Etik Kurul Başkanlığı,

Onaylanmış tez protokolümüzde talep edilen revizyon kapsamında aşağıdaki düzenlemeler yapılmıştır:

1) Çok merkezli (multisentrik) çalışma: Biruni Üniversitesi Hastanesi, Fiziksel Tıp ve Rehabilitasyon Polikliniği ikinci veri toplama merkezi olarak protokole eklenmiştir. İlgili kurum izin belgesi (Biruni Üniversitesi Hastanesi) dosyaya eklenmiştir.

2) Araştırma ekibi: Biruni Üniversitesi Hastanesi Fiziksel Tıp ve Rehabilitasyon Uzmanı Doç. Dr. Çiğdem Çınar yardımcı araştırmacı olarak eklenmiştir. Güncel imzalı özgeçmiş formu dosyaya eklenmiştir.

3) Etik Kurul başvuru formu: "Onaylanan Projede Değişiklik Bildirimi" seçeneği işaretlenmiş; yapılan eklemeler kırmızı renkle belirtilmiştir.

4) Veri toplama merkezleri bölümü, yardımcı araştırmacılar tablosu ve gerekçe/amaç bölümü revizyonları yansıtacak şekilde güncellenmiştir.

Protokolün bilimsel tasarımı, örneklem büyüklüğü (n=28), müdahale içeriği, birincil/ikincil sonuç ölçüleri ve istatistiksel analiz planı değiştirilmemiştir.

Saygılarımla,
{PI['name']}
Sorumlu Araştırmacı
{TODAY_TR}"""

KURUM = {
    "pi_line": f"{PI['title']}, {PI['name']}",
    "pi_org": "İstinye Üniversitesi Liv Bahçeşehir Hastanesi, Nörorehabilitasyon Kliniği",
    "assistants": (
        "Prof. Dr. Yakup Krespi\n"
        "Kurum: İstinye Üniversitesi Liv Bahçeşehir Hastanesi, Nöroloji Anabilim Dalı\n\n"
        "Dr. Öğr. Üyesi Begüm Kara Kaya (Tez Danışmanı)\n"
        "Kurum: Biruni Üniversitesi, Fizyoterapi ve Rehabilitasyon Anabilim Dalı\n\n"
        "Doç. Dr. Çiğdem Çınar (Yardımcı Araştırmacı)\n"
        "Kurum: Biruni Üniversitesi Hastanesi, Fiziksel Tıp ve Rehabilitasyon Anabilim Dalı"
    ),
    "title": STUDY_TITLE_TR,
    "dates": "Etik Kurul onayı sonrası 12 ay (Şubat 2026 – Şubat 2027)",
    "type": "Tez kapsamında prospektif randomize kontrollü klinik araştırma (multisentrik)",
    "purpose": (
        "İnme sonrası tek seans PETTLEP temelli AOMI müdahalesinin üst ekstremite "
        "kinematiği ve klinik sonuçları üzerindeki anlık etkisini değerlendirmek; "
        "Biruni Üniversitesi Hastanesi'nde ikinci merkez olarak katılımcı tarama/veri toplama."
    ),
    "data_requested": (
        "• Tanı, yaş, cinsiyet, inme tarafı ve süresi\n"
        "• Spastisite (MAS), MMSE, NIHSS skorları\n"
        "• Üst ekstremite fonksiyonel değerlendirme sonuçları (WMFT-4 vb.)\n"
        "• Video tabanlı kinematik kayıtlar (anonim kodlu)\n"
        "• Rıza formu onayı ve çalışma ziyaret tarihleri\n"
        "Not: Kimlik bilgileri (TCKN, adres, telefon) talep edilmeyecektir; yalnızca araştırma kodu kullanılacaktır."
    ),
    "applicant": PI["name"],
    "applicant_date": TODAY_TR,
}

WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _kill_word() -> None:
    import subprocess

    subprocess.run(
        ["taskkill", "/F", "/IM", "WINWORD.EXE"],
        capture_output=True,
        check=False,
    )


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


def set_checkbox(ff, checked: bool) -> None:
    ff.CheckBox.Value = checked


def insert_after(doc, find_text: str, insert_text: str, red: bool = False) -> None:
    rng = doc.Content
    f = rng.Find
    f.ClearFormatting()
    f.Text = find_text
    f.Forward = True
    f.Wrap = 0
    if not f.Execute():
        return
    ins = doc.Range(rng.End, rng.End)
    ins.Text = insert_text
    ins.Font.ColorIndex = 6 if red else 0


def insert_red_after(doc, find_text: str, insert_text: str) -> None:
    insert_after(doc, find_text, insert_text, red=True)


def replace_after_label(doc, label: str, value: str, red: bool = False) -> None:
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
    if red:
        ins.Font.ColorIndex = 6


def fill_irb_application() -> Path:
    _kill_word()
    src = BASE / "insan-arastirmalari-etik-kurul-basvuru-formu-09.03.2026-1_0 (25).doc"
    dst = OUT / "insan-arastirmalari-etik-kurul-basvuru-formu-DOLDURULMUS.doc"
    shutil.copy2(src, dst)

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    doc = word.Documents.Open(str(dst.resolve()))
    try:
        insert_after(doc, "Tarih:", TODAY_TR)
        insert_after(doc, "PROJENİN ADI:", "\n" + STUDY_TITLE_TR)

        for idx in (4, 7, 9, 11, 17, 18, 20, 22, 26):
            set_checkbox(doc.FormFields(idx), True)

        tbl = doc.Tables(1)
        tbl.Cell(2, 1).Range.Text = ADVISOR["name"]
        tbl.Cell(2, 2).Range.Text = ADVISOR["org"]
        tbl.Cell(2, 3).Range.Text = f"{ADVISOR['phone']} / {ADVISOR['contact']}"
        for c in range(1, 4):
            tbl.Cell(2, c).Range.Font.ColorIndex = 0

        tbl2 = doc.Tables(2)
        tbl2.Cell(2, 1).Range.Text = PI["title"] + "\n" + PI["name"]
        tbl2.Cell(2, 2).Range.Text = PI["org"]
        tbl2.Cell(2, 3).Range.Text = f"{PI['phone']} / {PI['contact']}"
        for c in range(1, 4):
            tbl2.Cell(2, c).Range.Font.ColorIndex = 0

        tbl3 = doc.Tables(3)
        tbl3.Cell(2, 1).Range.Text = COINV["name"]
        tbl3.Cell(2, 2).Range.Text = COINV["org"]
        tbl3.Cell(2, 3).Range.Text = f"{COINV['phone']} / {COINV['contact']}"
        for c in range(1, 4):
            tbl3.Cell(2, c).Range.Font.ColorIndex = 6

        main_rationale, _, revision_tail = RATIONALE.partition("\n\nREVİZYON")
        revision_text = "REVİZYON" + revision_tail

        rng = doc.Content
        f = rng.Find
        f.Text = "ARAŞTIRMANIN GEREKÇESİ, AMACI VE KAYNAKLARI"
        f.Execute()
        ins = doc.Range(rng.End, rng.End)
        ins.Text = "\n" + main_rationale.strip() + "\n"
        ins.Font.ColorIndex = 0

        ins2 = doc.Range(ins.End, ins.End)
        ins2.Text = revision_text.strip() + "\n"
        ins2.Font.ColorIndex = 6

        for label, text in [
            ("Araştırmaya Dahil Olma Kriterleri:", INCLUSION),
            ("Araştırmaya Hariç Olma Kriterleri:", EXCLUSION),
            ("UYGULANACAK YAKLAŞIM VE İSTATİSTİKSEL YÖNTEM", METHODS),
        ]:
            rng = doc.Content
            f = rng.Find
            f.Text = label
            f.Execute()
            ins = doc.Range(rng.End, rng.End)
            ins.Text = "\n" + text + "\n"
            ins.Font.ColorIndex = 0

        tbl4 = doc.Tables(4)
        tbl4.Cell(2, 4).Range.Text = "12 ay (Şubat 2026 – Şubat 2027)"
        tbl4.Cell(3, 1).Range.Text = "Hasta (İnme / Stroke)\r"
        tbl4.Cell(3, 2).Range.Text = "28"
        tbl4.Cell(3, 3).Range.Text = "40–80"
        tbl4.Cell(5, 2).Range.Text = "28"
        for r in (2, 3, 5):
            for c in range(1, 5):
                try:
                    tbl4.Cell(r, c).Range.Font.ColorIndex = 0
                except Exception:
                    pass

        rng = doc.Content
        f = rng.Find
        f.Text = "Kurum/Kuruluş Adı ve Adresi:"
        f.Execute()
        ins = doc.Range(rng.End, rng.End)
        ins.Text = (
            "\n1) İstinye Üniversitesi Liv Bahçeşehir Hastanesi, Nörorehabilitasyon Kliniği, İstanbul\n"
        )
        ins.Font.ColorIndex = 0
        ins2 = doc.Range(ins.End, ins.End)
        ins2.Text = (
            "2) Biruni Üniversitesi Hastanesi, Fiziksel Tıp ve Rehabilitasyon Polikliniği, İstanbul "
            "(çok merkezli veri toplama merkezi — revizyon kapsamında eklenmiştir)\n"
        )
        ins2.Font.ColorIndex = 6
    finally:
        _close_word(word, doc)
    return dst


def fill_ozgecmis() -> Path:
    _kill_word()
    src = BASE / "ozgecmis-formu_0.doc"
    dst = OUT / "ozgecmis-formu_Abdelrahman_Sabee_DOLDURULMUS.doc"
    shutil.copy2(src, dst)

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    doc = word.Documents.Open(str(dst.resolve()))

    pairs = [
        ("Adı soyadı:", PI["name"]),
        ("Doğum tarihi ve yeri:", CV["birth"]),
        ("Yabancı dil bilgisi:", CV["languages"]),
        ("Görev yeri:", CV["workplace"]),
        ("Telefon No:", CV["phone"]),
        ("Mail Adresi:", CV["email"]),
        ("Devam eden eğitim (yüksek lisans / doktora)", CV["ongoing"]),
        ("Mezun olduğu üniversite / fakülte / Enstitü:", CV["grad_uni"]),
        ("Mezuniyet tarihini lütfen belirtiniz (yıl olarak):", CV["grad_year"]),
        ("Varsa, akademik ünvanları :", CV["title"]),
        (
            "Bugüne kadar çalıştığı kurum / kuruluşları  lütfen belirtiniz:",
            CV["work_history"],
        ),
        (
            "varsa insan araştırmaları konusunda aldığı eğitim ve sertifikalar:",
            CV["training"],
        ),
        (
            "Varsa, araştırmacı olarak katıldığı insan araştırmaları (klinik, sosyal vb)",
            CV["research"],
        ),
        (
            "Varsa son 5 yıl içinde hakemli dergilerde yayınlanan makaleler",
            CV["publications"],
        ),
        ("El yazısıyla adı soyadı:", PI["name"]),
        ("Tarih (gün/ay/yıl olarak):", TODAY_TR),
    ]
    try:
        for label, val in pairs:
            replace_after_label(doc, label, val, red=False)
    finally:
        _close_word(word, doc)
    return dst


def _replace_paragraph_text(p, new_text: str) -> None:
    for t in list(p.iter(f"{WNS}t")):
        t.text = ""
    ts = p.findall(f".//{WNS}t")
    if ts:
        ts[0].text = new_text
    else:
        r = ET.SubElement(p, f"{WNS}r")
        t = ET.SubElement(r, f"{WNS}t")
        t.text = new_text


def fill_docx_replace(src_name: str, dst_name: str, replacements: list[tuple[str, str]]) -> Path:
    src = BASE / src_name
    dst = OUT / dst_name
    shutil.copy2(src, dst)

    with zipfile.ZipFile(dst, "r") as zin:
        xml = zin.read("word/document.xml")
        other = {n: zin.read(n) for n in zin.namelist() if n != "word/document.xml"}

    root = ET.fromstring(xml)
    paras = list(root.iter(f"{WNS}p"))
    full = "\n".join(
        "".join(t.text or "" for t in p.iter(f"{WNS}t")) for p in paras
    )

    for old, new in replacements:
        if old not in full:
            continue
        for p in paras:
            txt = "".join(t.text or "" for t in p.iter(f"{WNS}t"))
            if old in txt:
                _replace_paragraph_text(p, txt.replace(old, new, 1))

    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        zout.writestr("word/document.xml", new_xml)
        for n, data in other.items():
            zout.writestr(n, data)
    return dst


def fill_duzeltme_bildirim() -> Path:
    src = BASE / "insan-arastirmalar-etik-kurulu-duzeltme-bildirim-formu-21.11.2023 (29).docx"
    dst = OUT / "insan-arastirmalar-etik-kurulu-duzeltme-bildirim-formu-DOLDURULMUS.docx"
    shutil.copy2(src, dst)

    with zipfile.ZipFile(dst, "r") as zin:
        xml = zin.read("word/document.xml")
        other = {n: zin.read(n) for n in zin.namelist() if n != "word/document.xml"}
    root = ET.fromstring(xml)
    body = root.find(f".//{WNS}body")
    paras = list(body.iter(f"{WNS}p"))

    response_blocks = [
        (
            f"İnsan Araştırmaları Etik Kurulu'na {TODAY_TR} tarihli başvurumuzda "
            f'"{STUDY_TITLE_TR}" başlıklı çalışmamızda düzeltilmesi için önerilen '
            "hususlarla ilgili cevaplar aşağıda bilgilerinize sunulmuştur."
        ),
        REVISION_RESPONSES.replace("Sayın Etik Kurul Başkanlığı,\n\n", "").strip(),
    ]

    dotted_indices = [
        i
        for i, p in enumerate(paras)
        if "…………" in "".join(t.text or "" for t in p.iter(f"{WNS}t"))
    ]
    if dotted_indices:
        first = dotted_indices[0]
        _replace_paragraph_text(paras[first], response_blocks[0])
        if len(dotted_indices) > 1:
            _replace_paragraph_text(paras[dotted_indices[1]], response_blocks[1])
        for idx in dotted_indices[2:]:
            _replace_paragraph_text(paras[idx], "")

    filled = False
    for p in paras:
        txt = "".join(t.text or "" for t in p.iter(f"{WNS}t"))
        if txt.strip() in ("Ad-Soyadı İmza", "Ad-Soyadı: İmza"):
            _replace_paragraph_text(p, f"Ad-Soyadı: {PI['name']}    İmza: _____________")
            filled = True

    if filled:
        tail = {"Saygılarımla.", "Sorumlu Araştırmacı", "Ad-Soyadı İmza", "Ad-Soyadı: İmza"}
        for p in paras[-4:]:
            txt = "".join(t.text or "" for t in p.iter(f"{WNS}t")).strip()
            if txt in tail or txt.startswith("Ad-Soyadı:"):
                _replace_paragraph_text(p, "")

    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        zout.writestr("word/document.xml", new_xml)
        for n, data in other.items():
            zout.writestr(n, data)
    return dst


def fill_kurum_izni() -> Path:
    src = BASE / "kurum izni biruni (1) (1).docx"
    dst = OUT / "kurum_izni_biruni_DOLDURULMUS.docx"
    shutil.copy2(src, dst)

    with zipfile.ZipFile(dst, "r") as zin:
        xml = zin.read("word/document.xml")
        other = {n: zin.read(n) for n in zin.namelist() if n != "word/document.xml"}
    root = ET.fromstring(xml)
    paras = list(root.iter(f"{WNS}p"))

    for p in paras:
        txt = "".join(t.text or "" for t in p.iter(f"{WNS}t"))
        if txt.startswith("1. Araştırma Sorumluları"):
            _replace_paragraph_text(
                p,
                f"1. Araştırma Sorumluları (Unvanı, Adı ve Soyadı): {KURUM['pi_line']}\n"
                f"Kurum: {KURUM['pi_org']}",
            )
        elif txt.startswith("2. Yardımcı Araştırmacılar"):
            _replace_paragraph_text(
                p,
                f"2. Yardımcı Araştırmacılar (Unvanı, Adı ve Soyadı):\n\n{KURUM['assistants']}",
            )
        elif txt.strip().startswith("Doç. Dr. Çiğdem") or txt.strip().startswith("Kurum: Biruni"):
            _replace_paragraph_text(p, "")
        elif txt.startswith("3. Tıbbi / Bilimsel Araştırmanın Başlığı:"):
            _replace_paragraph_text(p, f"3. Tıbbi / Bilimsel Araştırmanın Başlığı: {KURUM['title']}")
        elif txt.startswith("4. Araştırmanın Yapılacağı Tarih Aralığı:"):
            _replace_paragraph_text(p, f"4. Araştırmanın Yapılacağı Tarih Aralığı: {KURUM['dates']}")
        elif txt.startswith("5. Araştırmanın Türü:"):
            _replace_paragraph_text(p, f"5. Araştırmanın Türü: {KURUM['type']}")
        elif txt.startswith("6. Tıbbi / Bilimsel Araştırmanın Amaç / Kapsamı:"):
            _replace_paragraph_text(
                p,
                f"6. Tıbbi / Bilimsel Araştırmanın Amaç / Kapsamı: {KURUM['purpose']} "
                "(50 kelimeyi geçmeyecek şekilde belirtiniz).",
            )
        elif txt.startswith("7. Hasta ile ilgili hangi bilgileri talep ediyorsunuz:"):
            _replace_paragraph_text(
                p,
                f"7. Hasta ile ilgili hangi bilgileri talep ediyorsunuz:\n{KURUM['data_requested']} "
                "(Maddeler halinde yazınız).",
            )
        elif txt.strip() == "Ad Soyad:":
            _replace_paragraph_text(p, f"Ad Soyad: {KURUM['applicant']}")
        elif txt.strip().startswith("Tarih: İmza:"):
            _replace_paragraph_text(p, f"Tarih: {KURUM['applicant_date']}  İmza: _____________")

    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        zout.writestr("word/document.xml", new_xml)
        for n, data in other.items():
            zout.writestr(n, data)
    return dst


def copy_reference_docs() -> None:
    cvd = BASE / "Çigdem Çınar Özgeçmiş.docx"
    if not cvd.exists():
        for p in BASE.glob("*zge*.docx"):
            if "Abdelrahman" not in p.name:
                cvd = p
                break
    if cvd.exists():
        shutil.copy2(cvd, OUT / "Cigdem_Cinar_Ozgecmis_EK.docx")


def main() -> None:
    results = []
    results.append(("IRB Başvuru", fill_irb_application()))
    results.append(("Özgeçmiş", fill_ozgecmis()))
    results.append(("Düzeltme Bildirimi", fill_duzeltme_bildirim()))
    results.append(("Kurum İzni Biruni", fill_kurum_izni()))
    copy_reference_docs()

    for label, path in results:
        shutil.copy2(path, OUT_COPY / path.name)

    log = OUT / "FORMLAR_OZET.txt"
    lines = [
        "DOLDURULMUŞ ETİK REVİZYON FORMLARI",
        f"Tarih: {TODAY_TR}",
        "",
        "Kaynak: manuscript + UPDATED_CORRECTED + Outlook.pdf (Etik Kurul yanıtı)",
        "",
        "Revizyon kapsamı:",
        "  • Çok merkezli: Biruni Üniversitesi Hastanesi eklendi",
        "  • Yardımcı araştırmacı: Doç. Dr. Çiğdem Çınar",
        "",
        "Oluşturulan dosyalar:",
    ]
    for label, path in results:
        lines.append(f"  • {label}: {path.name}")
    lines += [
        "",
        "MANUEL TAMAMLANMASI GEREKEN ALANLAR:",
        "  • ozgecmis-formu_Cigdem_Cinar_DOLDURULMUS.doc — dogum tarihi (gerekirse), imza",
        "  • Abdelrahman IRB/PI alanlari — cep telefonu",
        "",
        "İMZALAR:",
        "  • Tüm formlara ıslak imza",
        "  • IRB formunda değişiklikler kırmızı renkte (otomatik uygulandı — kontrol edin)",
        "  • PDF olarak tarayıp etikkurul@istinye.edu.tr adresine gönderin",
        "",
        "Ek belgeler (hazır):",
        "  • Cigdem_Cinar_Ozgecmis_EK.docx (imzalı güncel tarihli kopya alın)",
    ]
    log.write_text("\n".join(lines), encoding="utf-8")
    try:
        print(log.read_text(encoding="utf-8"))
    except UnicodeEncodeError:
        print(str(log))


if __name__ == "__main__":
    main()
