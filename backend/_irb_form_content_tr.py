# -*- coding: utf-8 -*-
"""IRB form — black = unchanged vs approved PDF; red = revisions / new proposal content."""

from typing import List, Tuple

Seg = Tuple[str, bool]  # (text, is_red)

STUDY_TITLE_TR = (
    "İnme Sonrası Tek Seans PETTLEP Temelli Eylem Gözlemi ve Motor İmgeleme (AOMI) "
    "Uygulamasının Üst Ekstremite Kinematiği Üzerindeki Anlık Etkileri: "
    "Randomize Kontrollü Çalışma"
)

REVISION_NOTE = (
    "REVİZYON (onaylanmış protokolde değişiklik): Çalışma çok merkezli hale getirilmiş; "
    "Biruni Üniversitesi Hastanesi ikinci veri toplama merkezi olarak eklenmiş ve "
    "Doç. Dr. Çiğdem Çınar yardımcı araştırmacı olarak ekibe dahil edilmiştir. "
    "Bilimsel tasarım, örneklem (n=28) ve birincil sonuç (smoothness_pause_pct) değiştirilmemiştir."
)

# --- Section 6: Gerekçe (paras 1–3 = PDF; rest = updated) ---
GEREKCE_SEGMENTS: List[Seg] = [
    (
        """İnme, dünya genelinde yetişkin engelliliğinin üçüncü önde gelen nedenidir ve hastaların büyük bir kısmında uzun vadeli motor, kas tonusu ve üst ekstremite fonksiyon kontrolü ve koordinasyon bozukluğu görülmektedir (1). Bu eksiklikler, kortikal ve subkortikal motor sistemlerdeki hasara bağlı olarak etkili motor komutların üretimindeki bozulmadan kaynaklanmaktadır. Sonuç olarak, sarsıntılı yörüngelerle (hareket pürüzsüzlüğünün kaybı) karakterize patolojik hareket modelleri inme sonrasında oldukça tipiktir; hastalar zayıflığın üstesinden gelmek için gövdeyi hareket ettirme veya omzu yukarı kaldırma (omuz kuşağı elevasyonu) gibi uyumsuz stratejilerle telafi ederler (2,3).

Geleneksel tedavilerde vurgu görev pratiği üzerinedir; ancak inme geçirenlerin büyük bir kısmı, özellikle şiddetli hemiplejisi olanlar, bu tür eğitimlere katılmak için gereken istemli motor çıktıyı üretemezler (4). Bu grupta, fiziksel çıktı olmaksızın motor komutların bilişsel simülasyonu olan Motor İmgeleme (Mİ) önemli bir alternatif sunar. Mİ, fiziksel icra için kullandığımızla aynı nöral substratı kullanır (4,5). Yeni kanıtlar, Mİ'nin Eylem Gözlemi (AO) ile birleştirilmesinin (AOMI protokolü) motor plan için tek başına Mİ'den daha fazla destek sağladığını öne sürmektedir (6).

Ancak Mİ'deki zihinsel simülasyonun kalitesi ve titizliği, onun ne kadar güçlü olacağını belirleyecektir. İcra edilen ve hayal edilen eylemler arasındaki nöral substrat benzerliğini artırmak için PETTLEP modeli tanıtılmıştır (7). AOMI'nin PETTLEP ilkeleriyle sunulması, protokolün katılımcı odaklı olmasını ve motor yolları aktive edecek pragmatik bir destek olmasını sağlayacaktır.

""",
        False,
    ),
    (
        """Bu amaçla, MediaPipe Pose Landmarker tabanlı işaretsiz hareket yakalama sistemi ve ZoeDepth monoküler derinlik ağı ile metrik ölçekleme önerilmektedir. MediaPipe'nin inme sonrası üst ekstremite ulaşma hareketlerinde el, omuz ve gövde kinematiğini tek kamera ile izlemede kullanılabilirliği önceki çalışmalarda gösterilmiştir (8). Hareket pürüzsüzlüğü (smoothness_pause_pct), gövde-kompanzasyon oranı (total_trunk_palm_ratio) ve omuz dikey yer değiştirmesi (shoulder_vert_norm) gibi parametreler objektif olarak ölçülecektir. WMFT-4 ile kombinasyon, hareket kalitesinin fonksiyonel üst ekstremite performansı ile ilişkilendirilmesine olanak tanır (9).

Dolayısıyla, bu çalışmanın beklentisi nöro-rehabilitasyon literatüründeki kritik bir boşluğu doldurmaktır. Özelleştirilmiş PETTLEP tabanlı AOMI protokolü ile birlikte, spesifik zihinsel pratiğin inme sonrası bireylerde hareket pürüzsüzlüğü, telafi edici stratejiler ve fonksiyonel el becerisinde ölçülebilir kısa vadeli değişikliklere yol açıp açmadığı araştırılacaktır.

Anahtar Kelimeler: Motor imgeleme, eylem gözlemi, AOMI, PETTLEP, inme, MediaPipe, kinematik, üst ekstremite rehabilitasyonu.

Araştırma Sorusu:
Tek seanslık PETTLEP tabanlı AOMI; bilişsel ve somatik kontrol grubuna kıyasla, inme geçiren bireylerde etkilenen üst ekstremitenin hareket pürüzsüzlüğü (smoothness_pause_pct), gövde kompanzasyonu, omuz kuşağı elevasyonu ve üst ekstremite fonksiyonunda (WMFT-4) anlık iyileşmelere yol açar mı?

Hipotezler:
H₀: Tek seanslık PETTLEP tabanlı AOMI, kontrol grubuna kıyasla inme sonrası bireylerde paretik üst ekstremitenin kinematik parametrelerinde (smoothness_pause_pct, total_duration_s, total_trunk_palm_ratio, shoulder_vert_norm, total_peak_velocity) veya WMFT-4 skorunda anlamlı değişikliklere yol açmayacaktır.

H₁: Tek seanslık PETTLEP tabanlı AOMI, kontrol grubuna kıyasla inme sonrası bireylerde bu kinematik parametrelerde ve WMFT-4 skorunda anlamlı iyileşmelere yol açar.
""",
        True,
    ),
]

# Refs 1–7 unchanged; 8–13 updated
KAYNAKLAR_SEGMENTS: List[Seg] = [
    ("KAYNAKLAR:\n", False),
    (
        "1. World Stroke Organization (WSO). Global Stroke Fact Sheet 2022. Geneva: World Stroke Organization; 2022.\n"
        "2. Facciorusso S, Guanziroli E, Brambilla C, Spina S, Giraud M, Molinari Tosatti L, et al. Muscle synergies in upper limb stroke rehabilitation: a scoping review. Eur J Phys Rehabil Med. 2024 Oct;60(5):767-792.\n"
        "3. Schwarz A, Bhagubai MMC, Nies SHG, Held JPO, Veltink PH, Buurke JH, Luft AR. Characterization of stroke-related upper limb motor impairments across various upper limb activities by use of kinematic core set measures. J Neuroeng Rehabil. 2022 Jan 12;19(1):2.\n"
        "4. Guerra ZF, Lucchetti AL, Lucchetti G. Motor Imagery Training After Stroke: A Systematic Review. J Neurol Phys Ther. 2017;41(4):205-214.\n"
        "5. Lakshminarayanan K, Shahbazi M, Janouch C, Ladda AM. Editorial: Recent advancements in motor imagery. Front Neurol. 2023;14:1248023.\n"
        "6. Kim JH, Lee BH. The Effect of Action Observation Combined with Motor Imagery Training on Upper Extremity Function and Corticospinal Excitability in Stroke Patients: A Randomized Controlled Trial. Int J Environ Res Public Health. 2022;19(19):12048.\n"
        "7. Holmes PS, Collins DJ. The PETTLEP Approach to Motor Imagery: A Functional Equivalence Model for Sport Psychologists. J Appl Sport Psychol. 2001;13(1):60–83.\n",
        False,
    ),
    (
        "8. Wagh V, Scott MW, Andrushko JW, Jones CB, Larssen BC, Boyd LA, Kraeutner SN. Using MediaPipe to track upper-limb reaching movements after stroke: a proof-of-principle study. J Neuroeng Rehabil. 2025 Nov 25;22(1):268.\n"
        "9. Wolf SL, Catlin PA, Ellis M, et al. Assessing Wolf Motor Function Test scores against normative values. Arch Phys Med Rehabil. 2001;82(5):609-614.\n"
        "10. Caires TA, Fernandes LFRM, Patrizzi LJ, de Almeida Oliveira R, de Souza LAPS. Immediate effect of mental practice with and without mirror therapy on muscle activation in hemiparetic stroke patients. J Bodyw Mov Ther. 2017;21(4):1024-1027.\n"
        "11. Bijur PE, Silver W, Gallagher EJ. Reliability of the visual analog scale for measurement of acute pain. Acad Emerg Med. 2001;8(12):1153–1157.\n"
        "12. Malouin F, Richards CL, Jackson PL, et al. The Kinesthetic and Visual Imagery Questionnaire (KVIQ) for assessing motor imagery in persons with physical disabilities: a reliability and construct validity study. J Neurol Phys Ther. 2007;31(1):20-29.\n"
        "13. Schuster C, Hilfiker R, Amft O, Scheidhauer A, Andrews B, Butler J, et al. Best practice for motor imagery: a systematic literature review on motor imagery training elements in five different disciplines. BMC Med. 2011;9:75.\n",
        True,
    ),
]

VERI_SEGMENTS: List[Seg] = [
    (
        """Yöntem ve Değerlendirme Araçları
Materyal ve Metot:

Çalışma Tasarımı:
Bu çalışmada, iki koşulun (deneysel koşul: PETTLEP modeli tabanlı AOMI ve kontrol koşulu: bilişsel ve somatik kontrol) yürütüleceği tek kör, ön test-son test müdahaleli prospektif randomize kontrollü bir çalışma (RCT) tasarımı kullanılacaktır. Denemenin tasarımı, iki kollu (deneysel grup: PETTLEP tabanlı AOMI; kontrol grubu: bilişsel ve somatik kontrol) tek kör, ön test-son test müdahaleli prospektif RCT'dir. Bu çalışmada, işaretsiz hareket yakalama kullanılarak tek seanslık PETTLEP tabanlı bir AOMI görevinin inme bireylerinde etkilenen üst ekstremitenin kinematiği ve fonksiyonel performansı üzerindeki etkisini öncül olarak araştırmaktayız. Etik kurul onayından sonra bilgilendirilmiş onam alınacaktır. Toplam süre: Şubat 2026 – Şubat 2027 (12 ay).

""",
        False,
    ),
    (
        """Çalışma çok merkezlidir: İstinye Üniversitesi Liv Bahçeşehir Hastanesi Nörorehabilitasyon Kliniği ve Biruni Üniversitesi Hastanesi Fiziksel Tıp ve Rehabilitasyon Polikliniği.

""",
        True,
    ),
    (
        """Örneklem Büyüklüğü ve Randomizasyon:
2 (Grup: Motor İmgeleme vs. Kontrol) × 2 (Zaman: Ön vs. Son) tekrarlı ölçümler ANOVA için G*Power 3.1.9.2 kullanılarak a priori güç analizi yapılmıştır. Benzer bir akut motor imgeleme çalışmasının sonuçlarına göre f = 0.40 (Cohen's d ≈ 1.2) etki büyüklüğü referans olarak kullanılmıştır. Ancak, mevcut çalışmanın akut, tek seanslık tasarımı göz önüne alındığında, etki büyüklüğü üzerindeki bu varsayım oldukça iyimserdir. Yeterli gücü (1 − β = 0.95) α = 0.05 düzeyinde korumak için, çalışma başlamadan önce anlamlı bir grup × zaman etkileşim etkisi elde etmek üzere toplam N = 24 (grup başına 12 denek) örneklem büyüklüğü gerekmektedir. Olası terk ve/veya normal olmayan veri dağılımını telafi etmek için, istenen örneklem büyüklüğü %15 oranında artırılarak 28 katılımcılık (grup başına 14) bir alım hedefi belirlenmiştir (10).

Katılımcılar, gizlilikle tabakalandırılmış permütasyonlu blok randomizasyonu kullanılarak 1:1 temelinde motor imgeleme veya kontrol grubuna randomize edilecektir. Tabakalandırma kriterleri: (i) cinsiyet = erkek veya kadın; (ii) Modifiye Ashworth Skalası (MAS) ile değerlendirildiği üzere etkilenen üst ekstremite spastisite şiddeti — hafif (MAS 0–1+) ve orta (MAS 2). Bağımsız bir araştırmacı, dengeyi ve öngörülemezliği korumak için bilgisayarlı bir randomizasyon aracı kullanarak her tabaka için 4 ila 6 değişken blok büyüklüğünde bir randomizasyon listesi oluşturacaktır. Tahsisat, alıma doğrudan dahil olmayan biri tarafından hazırlanan sıralı numaralandırılmış, opak, kapalı zarflarda gizlenecektir. Bir tabaka içinde bir bloğu tamamlamak için yeterli katılımcı yoksa, o tabakadaki son katılımcı(lar), uygulanabilirliği sürdürmek için bloğu tamamlamak üzere rastgele tahsis edilecektir.

Değerlendirmeler:
Güvenilirlik ve tutarlılığı sağlamak amacıyla, çevresel koşullar tüm değerlendirmeler için standardize edilecektir. Her katılımcı, müdahale seansının hemen öncesinde ve hemen sonrasında olmak üzere iki kez değerlendirilecektir. Bu ön test–son test protokolü, motor imgeleme veya kontrol görevi sonrası (hareket pürüzsüzlüğü, Gövde Yer Değiştirmesi, Omuz Kuşağı Elevasyonu) parametrelerindeki geçici değişikliklerin tespit edilmesini sağlar. Değerlendiriciler arası değişkenliği önlemek amacıyla testler her merkezde tek bir eğitimli fizyoterapist tarafından yürütülecektir.

""",
        False,
    ),
    (
        """Kinematik parametreler, MediaPipe Pose Landmarker (33 landmark) kullanılarak video kayıtlarından otomatik olarak çıkarılacaktır. MediaPipe tabanlı işaretsiz hareket analizinin inme sonrası bireylerde üst ekstremite ulaşma kinematiğini izlemede geçerliliği daha önce gösterilmiştir (8).

""",
        True,
    ),
    (
        """Deneysel Koşulların Standardizasyonu:
Bu çalışmadaki katılımcılara, düzenli eğitim kıyafetlerinin bir parçası olan uzun kollu, koyu mor bir tişört giydirilecektir. Örgüler/at kuyrukları, boyun ve omuz işaretleyicilerinin kamera tarafından engellenmeden görülmesini sağlayacak şekilde sabitlenmelidir. Deneysel koşullar (sandalye ve masa yüksekliği ile katılımcı ve hedef arasındaki mesafe) tek tip olacak ve her bir katılımcı için ön ve son test prosedürleri arasında değişmeden kalacaktır. Eğitimin diğer anlık etkilerini önlemek amacıyla, katılımcılardan test seansının yapıldığı gün başka bir üst ekstremite rehabilitasyon tedavisine katılmamaları istenecektir.

""",
        False,
    ),
    (
        """Görevin Yürütülmesi (Reach & Wipe — Ulaş-Sil):
Ulaş-Sil görevi için sözlü talimat, dikkatte yanlılığı önlemek amacıyla aynı standart metinden verilecektir. Katılımcıların her değerlendirme zaman noktasında (önce ve sonra) kaydedilmek üzere üç deneme tamamlamaları gerekmektedir; analiz için üç denemenin ortalaması kullanılacaktır. Yerleşik hareket davranışlarını yakalamak için "hızlı" veya "yavaş" gitmeleri yönünde açık bir talimat verilmeksizin, görevi kendileri için doğal olan bir hızda (rahat hareket hızı) tamamlamaları söylenecektir.

Veri Toplama Kurulumu:
Anlık kinematik değişiklikleri değerlendirmek amacıyla, tek eğitim seansının öncesinde ve hemen sonrasında kayıtlar alınacaktır. Sensör tutarlılığını sağlamak için tüm katılımcılarda aynı akıllı telefon veya web kamerası modeli kullanılacaktır. Kamera, sabit bir yüksekliğe monte edilen tripod üzerine yerleştirilecek ve katılımcıya göre frontal açıda yaklaşık 1.5–2.0 m standart mesafede konumlandırılacaktır. Kayıtlar 1080p çözünürlükte ve saniyede 30 kare (fps) yapılacaktır. Yapay zeka takibini engelleyebilecek arkadan aydınlatma veya gölgeleri önlemek için kayıtlar tutarlı, dağınık aydınlatmaya sahip bir odada gerçekleştirilecektir. Veri karşılaştırılabilirliğini sağlamak için tüm katılımcı analizlerinde aynı MediaPipe işleme parametreleri kullanılacaktır. Video verileri, MediaPipe Pose Landmarker (33 landmark, 2D) ile işlenecek; ZoeDepth monoküler derinlik ağı ile metrik ölçekleme uygulanacaktır. İsteğe bağlı olarak OpenSim ters kinematik (14 DOF) analizi yapılabilir.

Birincil Sonuç:
Çalışmanın birincil sonucu, etkilenen üst ekstremitenin hareket pürüzsüzlüğündeki değişimdir (smoothness_pause_pct). Klasik işaretleyici tabanlı hareket yakalama sistemlerinin aksine, MediaPipe tabanlı pipeline akıllı telefon veya web kamerası videosundan kinematik türetir (8). Hareket Pürüzsüzlüğü (Pause Time %): Aktif hareket penceresinde el hızının normalize eşik (0.03 SW/s) altında kaldığı sürenin yüzdesi olarak hesaplanır. Düşük değerler daha pürüzsüz, kesintisiz hareketi ifade eder; yüksek değerler stop-and-go davranışını ve motor kontrol kaybını yansıtır.

İkincil Kinematik Sonuçlar:
Omuz Kuşağı Elevasyonu (Telafi Edici Strateji):
Amaç: Bir telafi stratejisi olarak ölçmek; işaretsiz yakalama sistemi yüzey landmark'larını takip eder.
Ölçüm Yöntemi: Hareket sırasında omuz landmark'ının dikey (Y ekseni) yer değiştirmesinin omuz genişliğine normalize edilmesiyle hesaplanır (shoulder_vert_norm).

Gövde Yer Değiştirmesi (Telafi Edici Strateji):
Amaç: Hastanın azalmış kol uzunluğunu telafi etmek için gövde eğilmesine ne derece başvurduğunu nicelleştirmek. Amaç, hastanın gerçekten üst ekstremiteyi mi hareket ettirdiğini yoksa gövdeyi kullanarak mı telafi ettiğini belirlemektir. Bu, biyomekanik fonksiyonun mutlak bir değeri olarak değil, telafi edici strateji kullanım kalitesinin bir göstergesi olarak ifade edilir.
Ölçüm Yöntemi: Gövde-kompanzasyon oranı (total_trunk_palm_ratio) — gövde yer değiştirmesinin el/palm hareketine oranı.

Ek ikincil kinematik değişkenler: total_duration_s, total_peak_velocity, total_path_length, lateral_hand_range, maksimum dirsek açısı (elbow_max), faz-spesifik metrikler (forward, wipe, return).

Üst Ekstremite Fonksiyonu — Wolf Motor Function Test – 4 Maddelik Kısa Form (WMFT-4):
Amaç: Kinematikteki iyileşmelerin günlük yaşam aktivitelerinde gerçek fonksiyonel faydalara yol açıp açmadığını değerlendirmek.
Ölçüm Yöntemi: Etkilenen üst ekstremite performansını değerlendiren 4 maddelik kısa form; her madde için fonksiyonel puanlama ve süre kaydı. Rehabilitasyon literatüründe üst ekstremite fonksiyonunu değerlendirmek için evrensel olarak kullanılan standart bir klinik araçtır (9).

""",
        True,
    ),
    (
        """Ağrı — Görsel Analog Skalası (VAS):
Amaç: Etkilenen üst ekstremitedeki ağrı şiddetini değerlendirmek ve müdahalenin güvenliğini izlemek için kısa vadede ağrı algısındaki değişiklikleri değerlendirmek.
Ölçüm Yöntemi: Katılımcılar ağrı şiddetini 10 cm'lik yatay bir çizgi üzerine işaret koyarak belirtirler. Sol taraf "ağrı yok" (0) ve sağ taraf "hayal edilebilecek en kötü ağrı" olarak etiketlenmiştir (11). Genel klinik pratiğin bir parçası (public domain) olarak kabul edildiğinden, kullanımı için herhangi bir yazar veya telif izni gerekmemektedir.

""",
        False,
    ),
    (
        """Hareket İmgeleme Yeteneği — Kinestetik ve Görsel İmgeleme Anketi-10 (KVIQ-10):
Amaç: Katılımcının hareket imgeleme kapasitesini kinestetik ve görsel alt ölçeklerde değerlendirmek.
Ölçüm Yöntemi: Hasta, bir dizi temel hareketi yapmaya veya izlemeye yönlendirilir ve ardından bunları zihinsel olarak canlandırması istenir. Daha sonra, bu imgelemenin canlılığını bir Likert ölçeğinde (daha yüksek puanlar daha fazla canlılığı ifade eder) değerlendirirler (12). Baseline'da uygulanır.

Duygu Durumu — Görsel Analog Duygu Durumu Ölçeği-4 (VAMS-4):
Amaç: Müdahalenin duygusal etkisini değerlendirmek.
Ölçüm Yöntemi: Mutlu, sakin, üzgün ve gergin olmak üzere dört boyutta duygu durumu; pre/post uygulanır.

Fiziksel Aktivite — Uluslararası Fiziksel Aktivite Anketi (IPAQ):
Baseline'da fiziksel aktivite düzeyini değerlendirmek için uygulanır.

Motor Fark Algısı — Motor Difference Rating Scale (MDRS):
Müdahale sonrası katılımcının algıladığı motor değişikliği değerlendirmek için yalnızca post-intervention uygulanır.

Müdahale (Intervention):
Müdahale protokolü, Eylem Gözlemi (AO) ile birlikte PETTLEP tabanlı Motor İmgeleme (Mİ) protokolüne dayalı olarak geliştirilmiştir. Çalışma prosedürü birbirini izleyen üç aşamayı içerir: ön değerlendirme, tedavi ve son değerlendirme. Müdahale aşaması yaklaşık 17 dakika sürer (önerilen 15–20 dakika aralığında). Müdahale sırasında kasıtlı olarak fiziksel uygulama (overt physical practice) hariç tutulmuştur; fiziksel Reach & Wipe yalnızca pre/post değerlendirmede (üç deneme, ortalama analiz) gerçekleştirilir.

Temel Değerlendirme: Sistem kalibrasyonundan sonra, her denek tarafından Reach & Wipe görevinin üç aktif tekrarı gerçekleştirilecektir. Hareket kinematikleri, MediaPipe tabanlı işaretsiz hareket yakalama sistemi ile kaydedilecektir (müdahale öncesi hareket kalitesi: Hareket Pürüzsüzlüğü ve Gövde Yer Değiştirmesi).

Müdahale Aşaması: Katılımcılar rastgele Deneysel ve Kontrol kollarına ayrılır. Her iki grup da eşleştirilmiş sürede (~17 dk) müdahale alır.

Deneysel Grup (PETTLEP-AOMI):
Toplam doz: 2 dk kalibrasyon + 5 × 3 dk eğitim bloğu = 17 dk. Her 3 dakikalık blok: Watch 45 sn + Imagine 75 sn + Rest 60 sn.

Faz 1 — Kalibrasyon ve Hazırlık (120 sn):
Amaç: Derin zihinsel odaklanma ve etkilenmemiş uzvun etkilenen uzva duyusal-motor transferi.
Script (kulaklık, sakin ses): (0–15 sn) "Gözlerinizi kapatın. Oturduğunuz sandalyeyi ve vücut ağırlığınızı hissedin. Derin bir nefes alın… ve yavaşça verin." (15–60 sn) "Şimdi etkilenmemiş elinize odaklanın. Altındaki havluyu hissedin. O elinizle masayı pürüzsüzce silmeyi hayal edin — kendi gözlerinizden bakın (iç perspektif). Omuz ve kol kaslarının doğal kasılmasını ve pürüzsüz hareketin rahatlığını hissedin. Bu duyguya 'rahatlık' diyeceğiz." (60–120 sn) "Şimdi bu güçlü 'rahatlık' sinyalinin beyninizden etkilenen kolunuza geçtiğini canlı bir şekilde hayal edin. Kas liflerinin uyandığını hissedin. Hazırsınız."

Faz 2 — Eğitim Blokları (5 tekrar):
Her blok aynı Watch → Imagine → Rest sırasını izler.

Watch / Eylem Gözlemi (45 sn; Perspektif & Görev):
Katılımcı, etkilenmemiş uzvunun Reach & Wipe hareketini gösteren ayna ters çevrilmiş birinci şahıs videosunu izler.
Script: "Gözlerinizi açın ve videoyu izleyin. Dış bir gözlemci gibi dikkatle izleyin — pürüzsüz kol uzanması, boyuna doğru kalkmayan rahat omuzlar ve doğal zamanlama: ulaş… sil… dön."

Imagine / Motor İmgeleme (75 sn; Fiziksel, Zamanlama & Duygu):
Gözler kapalı; iç perspektif; gerçek zamanlı imgeleme kritiktir.
Script: "Gözlerinizi tekrar kapatın. Vücudunuzun içine dönün. Etkilenen elinizin altındaki masayı ve havluyu kendi gözlerinizden görün. Hareketi tam gerçek zamanında hayal edeceğiz." Terapist sayarak tempo verir: İleri ulaş… (havlunun kaydığını hisset); Yana sil… (kol ağırlığının güvenle hareket ettiğini hisset); Geri dön… (kas gevşemesini hisset). 75 saniye içinde 3–5 tam döngü tamamlanır. İmgeleme sarsıntılı veya telafi edici hale gelirse, katılımcı zihinsel olarak son pürüzsüz noktaya döner ve düzeltilmiş planla devam eder.

Rest / Nöral Dinlenme (60 sn):
Script: "İmgelemeyi durdurun. Zihninizi ve kaslarınızı tamamen gevşetin. Bir dakika boyunca hareket hakkında düşünmeyin. Sakin nefes alın."

Müdahale Uyumu:
PETTLEP modeline bağlılığı sağlamak için tüm imgeleme ipuçları standart sözlü metinler (önceden kaydedilmiş dijital ses dosyaları, kulaklık) aracılığıyla sunulacaktır. Zihinsel Kronometri her Imagine fazından sonra izlenecektir: "Hayal ettiğiniz hareket normal hızınızda mıydı?" Hayal edilen hareket süresi fiziksel süreye ±%25 oranında karşılık gelmelidir. Gözetmen fizyoterapist, her blok sonrası yapılandırılmış fidelity checklist dolduracaktır (katılım, Imagine sırasında gözler kapalı, overt hareket yok, advers olay).

Kontrol Grubu (Bilişsel ve Somatik Kontrol):
Katılımcılar, motor olmayan bilişsel sistemi uyararak motor ağların katılımını azaltmayı amaçlayan, süre ve dikkat açısından eşleştirilmiş bir protokolü takip edeceklerdir. 2 dakikalık giriş gevşemesi + 5 blok × 3 dk:
Vücut Taraması (Somatik Dikkat): Katılımcılara bir vücut taraması yapmaları ve dikkatlerini nefese ve vücuttaki bir dizi konuma (ayaklardan başa kadar) getirmeleri, hareket etmeme veya hareket etmeyi hayal etmeme talimatıyla sıcaklık veya koltuk hissi gibi duyumları not etmeleri söylenir.
Uzaysal Navigasyon (Görsel-Uzaysal Kontrol): Katılımcılar zihinsel bir "Ev Turu" gerçekleştirirler. Sanki evlerinde dolaşıyorlarmış gibi mobilyaların yerleşimini görüntülerler. Bu, motor korteksi aktive etmeden görsel-uzaysal ağı aktive eder. Her iki görev de standart kulaklık sesi ile sunulur; oda düzeni deneysel grupla eşleştirilir.

PETTLEP Çerçevesinin Uygulanması:
Mİ seansı, görselleştirilen aktivitelerin ekolojik geçerliliğini artıran PETTLEP modeline (Fiziksel, Çevre, Görev, Zamanlama, Öğrenme, Duygu ve Perspektif) dayanmaktadır:
P – Fiziksel (Dinamik Hazırlama): Gerçek oturma pozisyonu, normal kıyafet, gerçek havlu altında el; değerlendirme ile aynı konfigürasyon.
E – Çevre (Bağlamsal Sadakat): Tedavi, değerlendirmede kullanılan aynı masa, sandalye ve hedef nesneyi (havlu) kullanarak gerçekleşir.
T – Görev (Fonksiyonel): Reach & Wipe, mevcut üst ekstremite kapasitesine ve günlük yaşam ihtiyaçlarına uygun.
T – Zaman (Zamansallık — kritik): Katılımcılardan o anda hareket ettiklerini hayal etmeleri istenir. Zihinsel Kronometri, hayal edilen sürenin fiziksel sürenin %75'i (±%25) içinde olup olmadığı kontrol edilir.
L – Öğrenme (Hata Tabanlı Kalibrasyon): Protokol tekrarlayıcı değil, reaktiftir. Video gözlemi ile imgeleme arasında gidip gelerek, uygulayıcı "tahmini" "çıktı" ile tekrar tekrar test eder.
E – Duygu (Güven ve Rahatlama): Sözlü talimatlar, "rahatlık", "akış" ve "hafiflik" vurgusu yapar; performans kaygısını hafifletir.
P – Perspektif: Watch'ta dış perspektif (üçüncü şahıs gözlem); Imagine'da iç perspektif (birinci şahıs, kinestetik).

Hedeflenen Görevin Fonksiyonel Uygunluğu: Reach & Wipe
Bu çalışma, tekil kas kasılmalarına odaklanmak yerine, masaya ulaşıp silme hareketi ile ilgilidir. Aşağıdaki nedenler, bu hareketin temel görev olarak seçilmesini haklı çıkarmaktadır:
Ekolojik Geçerlilik: Reach & Wipe, günlük yaşam aktivitelerinde (GYA) bağımsızlığın temel hareket ettiricilerinden biridir. Bir yüzeye ulaşıp temizleme yeteneği, izole kas gücünden çok daha fazlasını ifade eder.
Uzanma ve Gövde Fazı: Omuz fleksiyonu ve dirsek ekstansiyonu mesafe bileşenine katkıda bulunur. Gövde Kompanzasyonu ve Omuz Kuşağı Elevasyonu, inme sonrası hastaların bu aşamasında gerçekten çok sık görülen telafi edici davranışlardır. İmgeleme scriptleri, gövdeyi sabit tutmayı ve omuzları rahat bırakmayı vurgular; bu, total_trunk_palm_ratio ve shoulder_vert_norm ile nicel olarak ölçülür.
Silme Fazı (Pürüzsüzlük): Yana silme, koordineli dirsek ve el hareketi gerektirir. Gerçek zamanlı imgeleme ve "rahatlık" vurgusu, hareket pürüzsüzlüğü ve doğruluğu üzerinde hassas motor kontrolü eğitmeyi hedefler; smoothness_pause_pct ile ölçülür.

Diğer veri toplama yöntemleri: Görüntü kaydı, Ölçek, Test, Bilgisayar ortamında uygulama (Yapay Zeka Tabanlı Hareket Analizi — MediaPipe). Uygulanacak anket ve ölçekler anonim değildir; katılımcılara araştırma kodu atanır.

""",
        True,
    ),
    ("BAP Destek Talebi: Yok\n", False),
]

DAHIL_SEGMENTS: List[Seg] = [
    (
        """Dahil edilme kriterlerini karşılayan toplam 28 inme hastası (her grupta 14 kişi) çalışmaya dahil edilecek ve randomize yöntemle iki gruba ayrılacaktır.

Çalışma popülasyonu, İstanbul, Türkiye'deki İstinye Üniversitesi Liv Bahçeşehir Hastanesi Nörorehabilitasyon Kliniği""",
        False,
    ),
    (
        """ ve Biruni Üniversitesi Hastanesi Fiziksel Tıp ve Rehabilitasyon Polikliniği'ne başvuran veya takipli inme hastalarından oluşmaktadır (çok merkezli). Katılımcılar, uygunluğu belirlemek için bir nörolog (Prof. Dr. Yakup Krespi veya merkez nörologu) ve fizyoterapist tarafından yapılan taramanın ardından gönüllü katılım yoluyla çalışmaya alınacaktır. Çalışma deneklere tam olarak açıklanacak ve kayıttan önce bir onam formu imzalamaları istenecektir. Hasta alımı etik kurul onayından sonra başlayacak ve gerekli örneklem büyüklüğü elde edilene kadar devam edecektir.
""",
        True,
    ),
]

DAHIL_KRITER_SEGMENTS: List[Seg] = [
    (
        """• 40–80 yaş arası kadın/erkek yetişkinler
• Tek taraflı iskemik veya hemorajik inme tanısı
• Etkilenen üst ekstremitede artık gönüllü hareket bulunması
""",
        False,
    ),
    ("• Hafif-orta spastisite (Modified Ashworth Skalası ≤ 2)\n", True),
    (
        """• Sözlü talimatları anlayabilecek yeterli bilişsel fonksiyon (MMSE ≥ 21)
• Tıbbi olarak stabil olma
• Desteksiz en az 30 dk oturabilme ve kısa bilişsel-motor egzersizleri tolere edebilme
""",
        False,
    ),
]

HARIC_KRITER = """• İnme dışı santral sinir sistemi patolojileri (Parkinson, MS, TBI vb.)
• Üst ekstremite hareketini kısıtlayan kas-iskelet sistemi veya ortopedik durumlar (sabit kontraktür, ciddi eklem deformitesi, omuz subluksasyonu)
• Görev uygulamasını veya motor imgeleme katılımını etkileyen ciddi duyu kaybı, görsel ihmal veya dikkat eksikliği
• Kontrolsüz epilepsi, ciddi kardiyovasküler instabilite veya imgelemeye kontrendikasyon
• Araştırma protokolüne uyum sağlayamama veya gönüllü geri çekilme"""

ISTATISTIK_SEGMENTS: List[Seg] = [
    (
        """Araştırmanın tasarımı, örnekleme yöntemi ve istatistiksel analiz yöntemleri:

Tüm analizler IBM SPSS Statistics for Mac, sürüm 24.0 (IBM Corp., Armok, New York, ABD) ile yapılacaktır.

Tanımlayıcı istatistikler: Katılımcı örneklemini ve sonuç değişkenlerini tanımlamak için tanımlayıcı istatistikler raporlanacaktır: normal dağılım gösteren sürekli değişkenler için ortalamalar ve standart sapmalar (SS); normal dağılım göstermeyen veya ordinal değişkenler için medyanlar ve çeyrekler arası aralıklar (IQR). Her sürekli değişken için dağılımın normalliği Shapiro-Wilk testi ile değerlendirilecektir.

Birincil ve İkincil Sonuç Analizi:
Parametrik Analiz: Normallik varsayımını karşılayan sürekli değişkenler (kinematik parametreler""",
        False,
    ),
    (
        """ ve WMFT-4 gibi) için tedavi etkilerinin araştırılması, 2 × 2 Karma Model Varyans Analizi (ANOVA) ile gerçekleştirilecektir. Model, "Zaman" (Müdahale Öncesi vs. Müdahale Sonrası) grup içi faktörünü ve "Grup" (Deneysel vs. Kontrol) gruplar arası faktörünü içerir. Birincil analizler, deneysel grupta kontrol grubuna kıyasla anlamlı derecede daha büyük bir iyileşme olup olmadığını belirlemek için Grup × Zaman etkileşim etkisine odaklanacaktır. Birincil sonuç smoothness_pause_pct için α = 0.05 korunacaktır.

Parametrik Olmayan Analiz: Sürekli verilerin anlamlı derecede normal olmadığı ve dönüştürülemediği durumlarda veya ordinal veriler (örneğin, ağrı için VAS ve KVIQ-10 alt ölçekleri) için parametrik olmayan yöntemler uygulanacaktır. Gruplar arası farklar Mann-Whitney U Testi ile test edilirken, grup içi değişiklikler Wilcoxon İşaretli Sıralar Testi ile değerlendirilecektir.

Korelasyonlar: Daha yüksek imgeleme yeteneğinin daha iyi motor performans sonucunu öngörüp öngörmediğini doğrulamak için, denek tarafından derecelendirilen imgeleme canlılığı (KVIQ-10 skorları) ve kinematik iyileşmenin büyüklüğü (smoothness_pause_pct ve total_trunk_palm_ratio Δ skorları), normal dağılım için Pearson korelasyonu (r) veya normal olmayan dağılım için Spearman rho (ρ) kullanılarak araştırılacaktır.

Etki Büyüklüğü: Müdahalenin etkisinin büyüklüğünü nicelleştirmek için etki büyüklükleri hesaplanacaktır: ANOVA sonuçları için kısmi eta kare (ηp²) ve ikili karşılaştırmalar için Cohen's d veya rank-biserial korelasyon (r = Z / √N). Tüm analizler için istatistiksel anlamlılık düzeyi p < 0.05 olarak belirlenecektir. İkincil kinematik değişken ailesi (k = 8) için Holm–Bonferroni düzeltmesi uygulanacaktır.

Eksik Verilerin Ele Alınması: Randomizasyonu korumak ve etki tahminindeki yanlılığı azaltmak için, titiz bir ITT (Intention-to-Treat) analizi yapılacaktır. Hiçbir veri silinmeyecek (ikili silme yok), bunun yerine randomize edilen tüm deneklerin nihai analizde yer alması için istatistiksel atama (imputation) (örneğin Son Gözlemin İleri Taşınması [LOCF] birincil imputation yöntemi olarak; Doğrusal Karma Modeller duyarlılık analizi olarak) ile işlenecektir.
""",
        True,
    ),
]

BUTCE = """Bu araştırma herhangi bir kurum tarafından desteklenmemektedir (TÜBİTAK/BAP: Hayır).

Gider Kalemleri:
Baskı maliyeti (bilgilendirilmiş onam formları, veri formları): 1000 TL
Genel Toplam: 1000 TL — Sorumlu araştırmacı tarafından karşılanacaktır."""
