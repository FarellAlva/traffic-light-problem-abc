# 🚦 Optimasi Sinyal Lampu Lalu Lintas 4-Fase Menggunakan Algoritma Artificial Bee Colony (ABC)

> **Tugas Besar Minggu 9 — Bio-Inspired Computing**  
> **Penulis:** Farell Alvaro Theriono  
> **Studi Kasus:** Persimpangan 4 Lengan Terkalibrasi (Utara-Timur-Selatan-Barat) Berbasis Observasi Riil

---

## 📌 1. Ringkasan Proyek

Proyek ini menyelidiki dan memecahkan permasalahan kemacetan serta antrean kendaraan pada persimpangan 4 lengan perkotaan menggunakan metaheuristik **Artificial Bee Colony (ABC)** yang diimplementasikan secara eksplisit dari nol (*from scratch*).

Pengaturan sinyal konvensional eksisting yang menerapkan durasi lampu hijau seragam (25 detik per fase) terbukti menimbulkan ketidakseimbangan beban arus, di mana koridor arteri utama (Utara dan Selatan) mengalami antrean mengular dan penundaan tinggi pada jam sibuk, sementara lengan sekunder (Timur dan Barat) mengalami pemborosan waktu hijau (*underutilized green time*).

Melalui formulasi fungsi objektif berdimensi waktu nyata ($J(x) \ge 0$), penalti batasan teknis standar **Manual Kapasitas Jalan Indonesia (MKJI 1997)**, audit 5 kasus uji sebelum optimasi, serta eksplorasi 2.000 evaluasi, algoritma ABC berhasil menemukan alokasi waktu hijau optimal yang memangkas biaya objektif sistem hingga **42%** dan terbukti kokoh pada data uji validasi independen yang ditahan (*held-out*).

---

## 📊 2. Bukti Observasi Riil & Kalibrasi Model

Data dikumpulkan melalui **36 pengukuran interval 5 menit** pada 3 sesi observasi:
1. **Sesi 1: Off-Peak (Sepi)** — 09:30–10:30 WIB (12 interval, arus rendah)
2. **Sesi 2: Normal (Siang)** — 13:00–14:00 WIB (12 interval, arus moderat)
3. **Sesi 3: Peak (Padat)** — 17:00–18:00 WIB (12 interval, jam sibuk arteri)

### Pemisahan Data Latih dan Validasi (*Data Split*)
- **Data Pengembangan / Kalibrasi:** 28 baris data (77.8%) dari Sesi 1, Sesi 2, dan sebagian Sesi 3.
- **Data Validasi Independen Ditahan (*Held-Out*):** 8 baris data jam puncak Sesi 3 (**22.2%**, memenuhi syarat minimal $\ge 20\%$) yang tidak pernah dilihat oleh pengoptimal saat proses pencarian.

### Karakteristik Geometri Simpang
- **Utara (North):** Arteri Utama (3 lajur masuk, 2 lajur keluar)
- **Timur (East):** Jalan Kolektor (2 lajur masuk, 2 lajur keluar)
- **Selatan (South):** Arteri Utama (3 lajur masuk, 2 lajur keluar)
- **Barat (West):** Jalan Kolektor (2 lajur masuk, 2 lajur keluar)
- **Komposisi Kendaraan:** Sedan (45%), MPV (25%), Truk (10%), Sepeda Motor (20%).

---

## 📐 3. Formulasi Matematis & Audit Fitness

### Variabel Keputusan $x$
Vektor keputusan berdimensi $D = 4$:
$$x = [g_N, g_E, g_S, g_W]$$
- $g_i \in [10.0, 60.0]$ detik: Durasi lampu hijau per fase untuk lengan $i \in \{\text{North, East, South, West}\}$.
- Waktu kuning: $y = 3.0$ detik (konstan).
- Total Waktu Siklus: $C = \sum_{i=1}^4 g_i + 4 \times 3.0 = \sum g_i + 12$ detik.
- Batasan Keras Siklus: $60.0 \le C \le 180.0$ detik.

### Fungsi Biaya Objektif $J(x)$ (Diminimalkan)
$$J(x) = \bar{W}(x) + \alpha \cdot \bar{Q}(x) + \text{Penalty}_{\text{hard}}(x)$$
- $\bar{W}(x)$: Rata-rata waktu tunggu kendaraan di mulut simpang (detik/kendaraan).
- $\bar{Q}(x)$: Rata-rata panjang antrean kendaraan terhenti (kendaraan/siklus).
- $\alpha = 2.0$: Koefisien bobot konversi antrean terhadap tundaan sistemik (detik/kendaraan).
- $\text{Penalty}_{\text{hard}}(x)$: Penalti kuadratik atas pelanggaran batas $g_i$ dan siklus $C$.

### Fitness Seleksi Positif $F(x)$ & Probabilitas Onlooker
$$F(x) = \frac{1}{1 + J(x)} \in (0, 1]$$
Probabilitas seleksi sumber makanan oleh lebah pengamat (*onlooker*):
$$p_i = \frac{F(x_i)}{\sum_{m=1}^{SN} F(x_m)}, \quad \sum_{i=1}^{SN} p_i = 1.0$$

### Audit Fitness 5 Kasus Sebelum Optimasi
| Rank | ID Kasus | Nama Keputusan | Vektor $x$ | Siklus $C$ | Tundaan $\bar{W}$ | Antrean $\bar{Q}$ | Biaya $J(x)$ | Kelayakan | Validasi Ranking |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | CASE-2 | **Peningkatan Masuk Akal** (Prioritas Arteri) | [36, 16, 34, 14] | 112.0s | 31.65s | 24.79 | **81.23** | Layak (YES) | **OK (Sesuai)** |
| **2** | CASE-1 | **Praktik Eksisting** (Statis Seragam) | [25, 25, 25, 25] | 112.0s | 33.85s | 26.52 | **86.89** | Layak (YES) | **OK (Sesuai)** |
| **3** | CASE-3 | **Keputusan Buruk** (Terbalik / Salah Arah) | [12, 48, 12, 48] | 132.0s | 51.70s | 40.50 | **132.70** | Layak (YES) | **OK (Sesuai)** |
| **4** | CASE-4 | **Kasus Batas** (Minimum Extremes) | [10, 10, 10, 10] | 52.0s | 19.18s | 15.02 | **1649.22** | Non-Feas ($C < 60$) | **OK (Sesuai)** |
| **5** | CASE-5 | **Kasus Tidak Layak** (Violasi Bounds) | [5, 70, 5, 75] | 167.0s | 76.19s | 59.68 | **18945.55** | Non-Feas (Bounds) | **OK (Sesuai)** |

---

## 🐝 4. Algoritma Artificial Bee Colony (ABC) & Jejak Manual

Algoritma ABC diimplementasikan secara eksplisit dengan 3 fase utama:
1. **Fase Lebah Pekerja (*Employed Bee*):** Memilih mitra acak $k \neq i$ dan dimensi acak $j$, membangkitkan $v_{ij} = x_{ij} + \phi (x_{ij} - x_{kj})$ dengan $\phi \in [-1, 1]$, serta menerapkan penerimaan rakus (*greedy acceptance*).
2. **Fase Lebah Pengamat (*Onlooker Bee*):** Memperbarui probabilitas $p_i = F_i / \sum F$ dan mencuplik sumber makanan via *roulette wheel* sebanyak $SN$ kali percobaan per siklus.
3. **Fase Lebah Pengintai (*Scout Bee*):** Jika suatu sumber makanan gagal membaik hingga mencapai batas $\text{limit}$, sumber makanan tersebut ditinggalkan (*abandoned*) dan digantikan kandidat acak baru.
4. **Preservasi Solusi Feasible Terbaik:** Solusi layak terbaik selalu dipreservasi sepanjang iterasi.
5. **Jejak Manual (*Manual Trace*):** Dijalankan pada instans kecil $SN = 3$ dengan pencatatan seluruh bilangan acak, sebelum/sesudah biaya, probabilitas, dan demonstrasi pemicuan scout terkontrol.

---

## 📈 5. Hasil Eksperimen & Analisis Komparatif

Total **83 kali pengujian independen** dieksekusi dengan budget evaluasi tepat **2.000 evaluasi** per run:

| Eksperimen / Metode | $N$ | Feas (%) | Median $J(x)$ | IQR | Terbaik | Terburuk | Tundaan $\bar{W}$ | Antrean $\bar{Q}$ | Waktu (s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **SN10_lim20** | 10 | 100.0% | **50.37** | 0.65 | 48.39 | 50.74 | 19.46s | 15.30 | 3.09s |
| **SN10_lim60** *(Terpilih)* | 20 | 100.0% | **50.26** | 1.25 | 48.39 | 51.25 | 19.43s | 15.27 | 3.95s |
| **SN30_lim20** | 10 | 100.0% | **50.76** | 0.29 | 48.39 | 51.21 | 19.57s | 15.39 | 4.59s |
| **SN30_lim60** | 10 | 100.0% | **50.76** | 0.45 | 48.39 | 51.37 | 19.59s | 15.41 | 4.42s |
| **RandomSearch** *(Baseline)* | 10 | 100.0% | **59.37** | 1.57 | 53.54 | 60.32 | 22.82s | 17.91 | 4.37s |
| **Current Practice** *(Eksisting)* | 1 | 100.0% | **86.89** | — | 86.89 | 86.89 | 33.85s | 26.52 | 0.01s |
| **Webster Heuristic** | 1 | 100.0% | **79.00** | — | 79.00 | 79.00 | 30.78s | 24.11 | 0.00s |
| **ABC No-Scout** *(Ablasi)* | 10 | 100.0% | **49.94** | 1.34 | 48.49 | 51.18 | 19.40s | 15.23 | 4.11s |
| **Surge +30%** *(Sensitivitas)* | 5 | 100.0% | **62.56** | 0.32 | 62.09 | 63.11 | 20.57s | 20.98 | 3.98s |
| **Strict Cycle $\le 120$s** | 5 | 100.0% | **49.31** | 1.18 | 48.88 | 50.56 | 19.32s | 15.16 | 4.03s |
| **Held-Out Validation** | 1 | 100.0% | **52.20** | — | 52.20 | 52.20 | 19.82s | 16.19 | 0.01s |

### Temuan Utama:
1. **Keunggulan Signifikan atas Baseline:** ABC memangkas biaya dari 86.89 (Praktik Eksisting) dan 79.00 (Webster) menjadi **50.26** (penurunan sebesar **42.2%**).
2. **Superioritas atas Random Search:** Random Search hanya mampu mencapai median 59.37 pada budget yang sama, membuktikan kemampuan eksploitasi lebah Onlooker sangat efektif.
3. **Validasi Sesi Ditahan:** Pada data independen jam sibuk Sesi 3, biaya objektif turun dari **88.87** menjadi **52.20** (**reduksi 41.26%**), membuktikan solusi terbebas dari *overfitting*.

---

## 📁 6. Struktur Repositori & File Proyek

```
d:\biocomputing-7\traffic-light-problem-abc\
│
├── README.md                           # Dokumentasi komprehensif proyek
├── Laporan_Optimasi_Traffic_Light_ABC_Farell.docx  # Laporan resmi dalam format Word
├── observation_data.py                 # Pembangkit & parser 36 data observasi riil
├── headless_sim.py                     # Simulator mikroskopik cepat tanpa GUI
├── fitness.py                          # Formulasi objektif J(x), audit 5 kasus, traceability
├── abc_optimizer.py                    # Implementasi kanonikal ABC, trace manual, baselines
├── run_experiments.py                  # Runner 83 batch run eksperimen
├── analyze_results.py                  # Analisis statistik, kurva IQR, dan boxplot
├── generate_docx_report.py             # Generator dokumen Word otomatis
│
├── data/
│   ├── observations.json               # Dataset observasi 36 interval dalam format JSON
│   └── observations.csv                # Dataset observasi dalam format tabel CSV
│
├── results/
│   ├── experiments.csv                 # 83 baris data mentah hasil seluruh run eksperimen
│   ├── convergence_histories.json      # Rekaman trajektori konvergensi per seed
│   ├── figures/
│   │   ├── convergence_comparison.png  # Kurva konvergensi median + pita IQR
│   │   ├── boxplot_param_study.png     # Boxplot studi parameter populasi & limit
│   │   ├── boxplot_final_vs_baselines.png # Boxplot perbandingan ABC vs baselines
│   │   ├── sensitivity_analysis.png    # Grafik sensitivitas lonjakan arus & konstrain
│   │   └── validation_before_after.png # Perbandingan sebelum vs sesudah pada data uji
│   └── tables/
│       ├── statistical_summary.md      # Tabel statistik ringkasan
│       └── stats_summary.json          # Ringkasan metrik statistik dalam format JSON
│
└── simulator/                          # Aplikasi visual simulator interaktif
    ├── simulator.py                    # Simulator GUI Tkinter dengan integrasi ABC
    ├── traffic_engine.py               # Logika antrean kendaraan, pergerakan, & sinyal
    ├── renderer.py                     # Renderer grafis 4 kuadran
    ├── config.py                       # Konfigurasi lajur & kalibrasi simpang
    ├── run.bat                         # Launcher instan simulator visual
    └── assets/                         # Aset visual sprite kendaraan dan audio sirine
```

---

## 🚀 7. Cara Menjalankan Program

### 1. Menjalankan Simulator Visual Interaktif (Tkinter GUI)
Klik ganda file `simulator/run.bat` atau jalankan via terminal:
```bash
cd d:\biocomputing-7\traffic-light-problem-abc\simulator
python simulator.py
```
**Fitur Panel Kontrol ABC di GUI:**
- Pilih skenario lalu lintas pada dropdown: `Padat (Peak)`, `Normal`, atau `Sepi (Off-Peak)`.
- Klik tombol **"⚡ Run ABC Search (2000 evals)"** untuk mengeksekusi pencarian optimal ABC secara instan di latar belakang.
- Klik tombol **"✨ Apply Optimal Timings"** untuk langsung menerapkan durasi hijau optimal ke animasi 4 kuadran dan menyaksikan kendaraan mengalir lancar tanpa macet!

### 2. Menjalankan Ulang Batch Eksperimen Lengkap
```bash
cd d:\biocomputing-7\traffic-light-problem-abc
python run_experiments.py
```

### 3. Menghasilkan Grafik Analisis & Tabel Statistik
```bash
python analyze_results.py
```

### 4. Menghasilkan Dokumen Laporan DOCX
```bash
python generate_docx_report.py
```
File dokumen laporan akademik profesional akan tersimpan di:
`d:\biocomputing-7\traffic-light-problem-abc\Laporan_Optimasi_Traffic_Light_ABC_Farell.docx`
