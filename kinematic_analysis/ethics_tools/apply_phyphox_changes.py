# -*- coding: utf-8 -*-
"""
Apply Phyphox changes to the ethics form.

Usage:
    1. Save the original form as:
       C:\Users\acer\AppData\Local\Temp\opencode\ethics_form_original.txt
    2. Run: python apply_phyphox_changes.py
    3. Modified form will be saved as:
       C:\Users\acer\AppData\Local\Temp\opencode\ethics_form_modified_with_phyphox.txt
"""
from pathlib import Path

src = Path(r"C:\Users\acer\AppData\Local\Temp\opencode\ethics_form_original.txt")
out = Path(r"C:\Users\acer\AppData\Local\Temp\opencode\ethics_form_modified_with_phyphox.txt")

text = src.read_text(encoding="utf-8")

# Change 1: Primary outcome paragraph
old1 = """Birincil Sonuç Ölçütü:
Çalışmanın birincil sonuç ölçütü, etkilenen üst ekstremitenin hareket pürüzsüzlüğündeki değişim olacaktır. Hareket pürüzsüzlüğü, Spektral Ark Uzunluğu (Spectral Arc Length, SPARC) yöntemi kullanılarak değerlendirilecektir. Bu amaçla, MediaPipe tabanlı işaretsiz hareket analizi sistemi aracılığıyla akıllı telefon veya web kamerası ile kaydedilen videolardan avuç içi merkezinin hareket yörüngesi elde edilecektir (8).
SPARC hesaplamasında, avuç içi merkezinin iki boyutlu (X–Y) hareket yörüngesinden teğetsel hız profili oluşturulacaktır. Hız sinyali normalize edildikten sonra hızlı Fourier dönüşümü (Fast Fourier Transform, FFT) uygulanarak frekans spektrumu elde edilecek ve 10 Hz'e kadar olan frekans bileşenleri analiz edilecektir. Ardından spektral eğrinin ark uzunluğu hesaplanarak SPARC değeri belirlenecektir (Balasubramanian ve ark., 2012; 2015).
SPARC, hareket pürüzsüzlüğünü değerlendirmede geçerli ve güvenilir bir kinematik ölçüttür. Daha düşük (daha negatif) SPARC değerleri daha pürüzsüz ve kesintisiz hareketi gösterirken, daha yüksek (daha az negatif) değerler hareket sırasında dur-kalk karakterindeki düzensizliklerin arttığını ifade etmektedir."""

new1 = """Birincil Sonuç Ölçütü:
Çalışmanın birincil sonuç ölçütü, etkilenen üst ekstremitenin hareket pürüzsüzlüğündeki değişim olacaktır. Hareket pürüzsüzlüğü, Spektral Ark Uzunluğu (Spectral Arc Length, SPARC) yöntemi kullanılarak değerlendirilecektir. SPARC; hem MediaPipe Pose Landmarker tabanlı işaretsiz hareket analizi sistemi ile videolardan elde edilen avuç içi merkezi yörüngesinden (8), hem de görev sırasında etkilenen taraf bileğine sabitlenen akıllı telefonun üç eksenli akselerometresi (Phyphox uygulaması, RWTH Aachen University) ile kaydedilen teğetsel hız profilinden hesaplanacaktır. İki yöntemden elde edilen SPARC değerleri arasındaki uyum değerlendirilerek, ölçüm güvenilirliği çapraz doğrulama ile desteklenecektir (Staacks ve ark., 2021; Dobkin ve Dorsch, 2011).
SPARC hesaplamasında, hareket penceresi içindeki teğetsel hız profili normalize edildikten sonra hızlı Fourier dönüşümü (Fast Fourier Transform, FFT) uygulanarak frekans spektrumu elde edilecek ve 10 Hz'e kadar olan frekans bileşenleri analiz edilecektir. Ardından spektral eğrinin ark uzunluğu hesaplanarak SPARC değeri belirlenecektir (Balasubramanian ve ark., 2012; 2015). MediaPipe kaydı için avuç içi merkezinin iki boyutlu (X–Y) hareket yörüngesi, Phyphox kaydı için bilek akselerometrisi mutlak hız profili [√(x²+y²+z²)] kullanılacaktır.
SPARC, hareket pürüzsüzlüğünü değerlendirmede geçerli ve güvenilir bir kinematik ölçüttür. Daha düşük (daha negatif) SPARC değerleri daha pürüzsüz ve kesintisiz hareketi gösterirken, daha yüksek (daha az negatif) değerler hareket sırasında dur-kalk karakterindeki düzensizliklerin arttığını ifade etmektedir."""

if old1 in text:
    text = text.replace(old1, new1)
    print("OK: Change 1 applied")
else:
    print("WARNING: Change 1 block not found")

# Change 2: Add secondary outcome 12
old2 = """11. Motor Değişim Derecelendirme Ölçeği (Motor Difference Rating Scale, MDRS)
Amaç: Katılımcının müdahale sonrasında algıladığı motor performans değişimini değerlendirmek.
Ölçüm Yöntemi: Motor Değişim Derecelendirme Ölçeği, müdahale sonrasında uygulanarak katılımcının algıladığı motor performans değişim düzeyi belirlenecektir. Daha yüksek puanlar, katılımcının algıladığı daha fazla olumlu değişimi göstermektedir.

Müdahale"""

new2 = """11. Motor Değişim Derecelendirme Ölçeği (Motor Difference Rating Scale, MDRS)
Amaç: Katılımcının müdahale sonrasında algıladığı motor performans değişimini değerlendirmek.
Ölçüm Yöntemi: Motor Değişim Derecelendirme Ölçeği, müdahale sonrasında uygulanarak katılımcının algıladığı motor performans değişim düzeyi belirlenecektir. Daha yüksek puanlar, katılımcının algıladığı daha fazla olumlu değişimi göstermektedir.

12. Bilek Akselerometrisi (Wrist Accelerometry – Phyphox)
Amaç: Reach & Return görevi sırasında etkilenen üst ekstremitenin segmental ivme ve hız profilini objektif olarak kaydetmek, MediaPipe tabanlı SPARC sonuçlarıyla çapraz doğrulama sağlamak ve telafi edici hareket stratejilerine eşlik eden segmental salınımları nicel olarak değerlendirmek.
Ölçüm Yöntemi: Görev sırasında katılımcının etkilenen taraf bileğine, standart bir akıllı telefon Phyphox uygulaması (RWTH Aachen University) aracılığıyla sabitlenecektir. Linear acceleration sensöründen x, y, z eksenlerindeki ivmeler yaklaşık 100 Hz örnekleme frekansıyla kaydedilecektir. Mutlak akselerasyon [√(x²+y²+z²)] profili üzerinden düşük geçişli filtreleme ve hareket pencereleme uygulanacak; aynı pencere için SPARC, normalize edilmiş jerk cost ve tepe akselerasyon değerleri hesaplanacaktır. Akıllı telefon akselerometreleri, hareket analizi ve nörorehabilitasyon alanında geçerli, güvenilir, taşınabilir ve düşük maliyetli bir ölçüm aracı olarak kullanılmaktadır (Staacks ve ark., 2021; Dobkin ve Dorsch, 2011; Dobkin, 2013).

Müdahale"""

if old2 in text:
    text = text.replace(old2, new2)
    print("OK: Change 2 applied")
else:
    print("WARNING: Change 2 block not found")

# Change 3: Data collection methods
old3 = """Veri Toplama Yöntemleri
Veriler görüntü kaydı, klinik ölçekler, performans testleri ve yapay zekâ tabanlı hareket analizi sistemi (MediaPipe) kullanılarak toplanacaktır. Katılımcı bilgileri araştırma kodları ile kodlanacak ve analizler kimliksizleştirilmiş veriler üzerinden gerçekleştirilecektir."""

new3 = """Veri Toplama Yöntemleri
Veriler görüntü kaydı, klinik ölçekler, performans testleri, yapay zekâ tabanlı hareket analizi sistemi (MediaPipe) ve akıllı telefon akselerometrisi (Phyphox) kullanılarak toplanacaktır. Katılımcı bilgileri araştırma kodları ile kodlanacak ve analizler kimliksizleştirilmiş veriler üzerinden gerçekleştirilecektir."""

if old3 in text:
    text = text.replace(old3, new3)
    print("OK: Change 3 applied")
else:
    print("WARNING: Change 3 block not found")

# Change 4: Task execution
old4 = "Katılımcıların her değerlendirme zaman noktasında (önce ve sonra) kaydedilmek üzere üç deneme tamamlamaları gerekmektedir; analiz için üç denemenin ortalaması kullanılacaktır. Yerleşik hareket davranışlarını yakalamak için \"hızlı\" veya \"yavaş\" gitmeleri yönünde açık bir talimat verilmeksizin, görevi kendileri için doğal olan bir hızda (rahat hareket hızı) tamamlamaları söylenecektir."

new4 = "Katılımcıların her değerlendirme zaman noktasında (önce ve sonra) kaydedilmek üzere üç deneme tamamlamaları gerekmektedir; analiz için üç denemenin ortalaması kullanılacaktır. Her deneme sırasında etkilenen taraf bileğine Phyphox uygulaması yüklü akıllı telefon sabitlenerek video kaydıyla eşzamanlı akselerometri verisi toplanacaktır. Yerleşik hareket davranışlarını yakalamak için \"hızlı\" veya \"yavaş\" gitmeleri yönünde açık bir talimat verilmeksizin, görevi kendileri için doğal olan bir hızda (rahat hareket hızı) tamamlamaları söylenecektir."

if old4 in text:
    text = text.replace(old4, new4)
    print("OK: Change 4 applied")
else:
    print("WARNING: Change 4 block not found")

# Change 5: References
old5 = "18. Saes M, Refai MIM, van Kordelaar J, Scheltinga BL, van Beijnum B-JF, Bussmann JB, et al. Smoothness metric during reach-to-grasp after stroke. Part 2. Longitudinal association with motor impairment. J Neuroeng Rehabil. 2021;18(1):144."

new5 = """18. Saes M, Refai MIM, van Kordelaar J, Scheltinga BL, van Beijnum B-JF, Bussmann JB, et al. Smoothness metric during reach-to-grasp after stroke. Part 2. Longitudinal association with motor impairment. J Neuroeng Rehabil. 2021;18(1):144.
19. Staacks S, Hütz S, Heinke H, Stampfer C. Advanced tools for smartphone-based experiments: phyphox. Phys Teach. 2021;59(3):214-215.
20. Dobkin BH, Dorsch A. The promise of mHealth: physical activity, fitness, and stroke. Neurorehabil Neural Repair. 2011;25(8):711-715.
21. Dobkin BH. Wearable motion sensors to continuously measure real-world physical activities. Curr Opin Neurol. 2013;26(6):602-608."""

if old5 in text:
    text = text.replace(old5, new5)
    print("OK: Change 5 applied")
else:
    print("WARNING: Change 5 block not found")

out.write_text(text, encoding="utf-8")
print(f"Saved modified form to: {out}")
