# Product Requirements Document (PRD)

## PDF Mutasi Bank to Excel Converter

**Versi:** 1.0 (draft untuk approval)  
**Tanggal:** 30 Oktober 2026  
**Status:** Draft - menunggu approval user  
**Target awal:** Internal, lalu publik

---

## 1. Ringkasan Produk

Web tool untuk mengonversi laporan mutasi rekening bank (PDF) menjadi Excel yang rapi, akurat, dan siap digunakan untuk rekonsiliasi, pelaporan, dan analisis keuangan. Bank awal yang didukung:

- BCA
- BSI
- Bank Muamalat

Tool akan mendeteksi bank secara otomatis, mengekstrak metadata rekening dan transaksi, melakukan validasi saldo berjalan, lalu mengekspor hasil ke Excel dengan format standar.

---

## 2. Latar Belakang & Masalah

Mutasi bank dari masing-masing bank memiliki layout berbeda:

- BCA menggunakan tabel horizontal dengan kolom Tanggal, Keterangan, CBG, Mutasi, Saldo.
- BSI menggunakan tabel dengan kolom Date, FT Number, Description, Currency, Amount, DB/CR, Balance.
- Muamalat menggunakan layout landscape/rotated dengan kolom Reference Number, Transaction Date, Effective Date, Debit, Credit, Balance, Description.

Masalah saat ini:

- Copy-paste dari PDF sering rusak.
- Deskripsi transaksi bisa multi-baris.
- Debit/kredit tidak selalu eksplisit di setiap bank.
- Validasi saldo berjalan manual dan rawan salah.
- Rekening dengan ratusan transaksi membutuhkan proses yang lama.

---

## 3. Tujuan Produk

### 3.1 Tujuan Utama

- Menghasilkan Excel mutasi bank yang rapi dan akurat.
- Mendukung auto-detect bank untuk BCA, BSI, dan Muamalat.
- Memvalidasi hasil konversi dengan saldo berjalan dan total ringkasan.
- Menyediakan preview sebelum download.
- Menyediakan alur koreksi manual jika parser perlu penyesuaian.

### 3.2 Tujuan Bisnis

- Mengurangi waktu konversi mutasi dari jam menjadi menit.
- Menjadi tools internal yang dapat dikembangkan menjadi layanan publik.
- Menyediakan fondasi parser bank yang dapat diperluas ke bank lain.

### 3.3 Non-Goals (MVP)

- OCR untuk PDF scan belum menjadi prioritas utama (PDF contoh adalah text-based).
- Integrasi akuntansi penuh (Xero, QuickBooks, Accurate) belum termasuk MVP.
- Rekonsiliasi invoice otomatis belum termasuk MVP.

---

## 4. User Persona

| Persona | Kebutuhan Utama |
|---|---|
| Staff Finance/Accounting | Konversi cepat, validasi saldo, export Excel rapi |
| Admin Internal | Batch upload, audit, koreksi manual |
| User Publik (future) | Upload mandiri, hasil akurat, privasi data |
| Developer/API User (future) | Endpoint API untuk otomatisasi |

---

## 5. Ruang Lingkup Format yang Dianalisis

### 5.1 BCA

Karakteristik:

- Halaman portrait.
- Header rekening: NO. REKENING, HALAMAN, PERIODE, MATA UANG.
- Tabel: `TANGGAL`, `KETERANGAN`, `CBG`, `MUTASI`, `SALDO`.
- Transaksi dimulai dari baris tanggal `DD/MM`.
- Debit ditandai marker `DB` setelah amount.
- Kredit biasanya tidak memiliki marker `DB`.
- Deskripsi dapat multi-baris.
- Ada `SALDO AWAL`, `MUTASI CR`, `MUTASI DB`, `SALDO AKHIR` pada akhir.
- Page footer: `1 / 2`.

### 5.2 BSI

Karakteristik:

- Halaman portrait.
- Header ringkasan: Account, Date, Opening Balance, Closing Balance, Total Debit Amount, Total Debit Record, Total Credit Amount, Total Credit Record, Branch.
- Tabel: `Date`, `FT Number`, `Description`, `Currency`, `Amount`, `DB`, `CR`, `Balance`.
- Satu baris transaksi biasanya satu row, tetapi deskripsi panjang dapat wrap ke baris berikutnya.
- Date dan FT Number kadang menyatu: `10:18:30FT2615220XMD`.
- Debit/kredit eksplisit melalui kolom `DB`/`CR`.
- Jumlah transaksi header: debit 147 + kredit 109 = 256 pada contoh.

### 5.3 Muamalat

Karakteristik:

- Halaman landscape dengan rotation 90 derajat.
- Header rekening: Account No., Account Type, Currency, Period.
- Tabel visual: `Reference Number`, `Transaction Date`, `Effective Date`, `Debit`, `Credit`, `Balance`, `Description`.
- Deskripsi multi-baris dan dapat mengandung nomor rekening pihak lain.
- Debit/kredit ditentukan berdasarkan kolom amount.
- Tidak ada opening/closing balance eksplisit di header.
- Page footer: `Page X of 121`.
- Jumlah transaksi contoh: 806.

---

## 6. Kebutuhan Fungsional

### FR-01 Upload File

- User dapat upload satu atau beberapa file PDF.
- Maksimal ukuran file dapat dikonfigurasi (default 25 MB/file).
- Sistem menolak file non-PDF atau PDF corrupt.
- Sistem mendukung PDF dengan password (user input password).

### FR-02 Auto-Detect Bank

- Sistem mendeteksi bank berdasarkan teks dan layout.
- Output deteksi: `bank_code`, `bank_name`, `confidence`.
- Jika confidence rendah, user dapat memilih bank manual.
- Bank detector harus bekerja pada 1-2 halaman pertama.

### FR-03 Ekstraksi Metadata Rekening

Field minimal:

- Bank
- Nomor rekening
- Nama rekening/pemilik
- Tipe rekening
- Mata uang
- Periode mutasi
- Cabang (jika ada)
- Saldo awal (jika ada)
- Saldo akhir (jika ada)
- Total debit (jika ada)
- Total kredit (jika ada)
- Jumlah record debit/kredit (jika ada)

### FR-04 Ekstraksi Transaksi

Setiap transaksi harus memiliki:

- Tanggal transaksi
- Tanggal efektif (jika ada)
- Nomor referensi
- Deskripsi/keterangan
- Debit
- Kredit
- Saldo setelah transaksi
- Cabang/FT/identifier (jika ada)
- Nomor halaman
- Nomor urut baris

### FR-05 Normalisasi Data

- Tanggal dinormalisasi ke format ISO (`YYYY-MM-DD`) di layer data, tetapi Excel menampilkan format yang mudah dibaca.
- Amount dinormalisasi menjadi angka desimal, bukan teks.
- Deskripsi dibersihkan dari spasi berlebih, tetapi makna dipertahankan.
- Debit/kredit yang kosong menjadi `0` atau `null` secara konsisten (rekomendasi: `0.00` untuk Excel).
- Mata uang disimpan sebagai teks (`IDR`).

### FR-06 Validasi Akurasi

Sistem harus melakukan validasi berikut:

- Saldo berjalan: `saldo_sebelumnya + kredit - debit = saldo_saat_ini`.
- Saldo awal cocok dengan header (jika tersedia).
- Saldo akhir cocok dengan header (jika tersedia).
- Total debit cocok dengan header (jika tersedia).
- Total kredit cocok dengan header (jika tersedia).
- Jumlah record cocok dengan header (jika tersedia).
- Semua amount dapat diparse.
- Semua tanggal valid.
- Tidak ada referensi duplikat tanpa alasan.

Output validasi:

- Status: `PASS`, `WARNING`, `FAIL`.
- Daftar error/warning per baris.
- Confidence score 0-100.

### FR-07 Preview & Koreksi Manual

- User dapat melihat tabel hasil konversi sebelum download.
- User dapat mengedit cell.
- User dapat menambah/menghapus baris.
- User dapat mengubah bank secara manual.
- User dapat memilih kolom output.
- User dapat melihat raw text per transaksi untuk audit.

### FR-08 Export Excel

- Export `.xlsx`.
- Minimal dua sheet:
  - `Summary`
  - `Transactions`
- Formatting:
  - Header bold dan freeze panes.
  - Kolom amount right-aligned dengan 2 desimal.
  - Tanggal dengan format `dd-mmm-yyyy`.
  - Auto column width.
  - Number format untuk IDR.
- Opsional: export CSV dan JSON (future).

### FR-09 Batch Processing

- Upload beberapa PDF sekaligus.
- Proses asynchronous untuk file besar.
- Download hasil per file atau ZIP.
- Progress bar per file.

### FR-10 Audit & History (Internal/Publik Future)

- Simpan metadata job: waktu, bank, jumlah row, status validasi.
- Jangan simpan isi PDF/transaksi lebih lama dari retention policy kecuali user memilih simpan.
- User dapat menghapus data job.

---

## 7. Kebutuhan Non-Fungsional

### NFR-01 Akurasi

- Target akurasi ekstraksi transaksi: >= 99% untuk PDF text-based contoh.
- Target validasi saldo berjalan: 100% untuk transaksi yang berhasil diparse.

### NFR-02 Performa

- File 2 halaman: < 5 detik.
- File 5 halaman: < 10 detik.
- File 121 halaman: < 60 detik pada server standar.
- Preview 1.000 baris tetap responsif.

### NFR-03 Keamanan & Privasi

- Semua transfer HTTPS.
- File upload divalidasi tipe dan ukuran.
- File temporary dihapus otomatis (default 24 jam).
- Tidak ada data sensitif di log.
- Untuk publik: rate limiting, CAPTCHA, dan kebijakan privasi.
- PDF password tidak disimpan.

### NFR-04 Skalabilitas

- Parser stateless.
- Job processing dapat di-scale horizontal.
- Storage dan database terpisah dari compute.

### NFR-05 Maintainability

- Setiap bank memiliki parser terpisah.
- Parser mengikuti interface yang sama.
- Golden test files untuk setiap bank.
- Perubahan layout bank dapat ditangani dengan parser versioning.

---

## 8. Data Model (Canonical Schema)

### 8.1 StatementMetadata

| Field | Tipe | Keterangan |
|---|---|---|
| bank_code | string | `BCA`, `BSI`, `MUAMALAT` |
| bank_name | string | Nama bank |
| account_number | string | Nomor rekening |
| account_name | string | Nama pemilik |
| account_type | string | Tipe rekening |
| currency | string | `IDR` |
| period_start | date | Awal periode |
| period_end | date | Akhir periode |
| branch | string | Cabang |
| opening_balance | decimal | Saldo awal |
| closing_balance | decimal | Saldo akhir |
| total_debit | decimal | Total debit |
| total_credit | decimal | Total kredit |
| debit_record_count | int | Jumlah debit |
| credit_record_count | int | Jumlah kredit |

### 8.2 Transaction

| Field | Tipe | Keterangan |
|---|---|---|
| row_id | string | ID unik baris |
| page_number | int | Halaman sumber |
| row_number | int | Urutan baris |
| transaction_date | date | Tanggal transaksi |
| effective_date | date | Tanggal efektif |
| reference_number | string | Nomor referensi |
| description | string | Keterangan |
| branch_or_ft | string | CBG/FT/identifier |
| debit | decimal | Nominal debit |
| credit | decimal | Nominal kredit |
| balance | decimal | Saldo setelah transaksi |
| transaction_type | string | `debit` / `credit` |
| confidence | float | 0-1 |
| flags | string[] | Warning/error |
| raw_text | string | Teks sumber (opsional) |

---

## 9. Arsitektur Parser

### 9.1 Pipeline

1. Upload PDF.
2. Detect encrypted/password.
3. Extract text + layout per halaman.
4. Detect bank.
5. Parse metadata.
6. Parse transactions.
7. Normalize data.
8. Validate.
9. Preview.
10. Export Excel.

### 9.2 Komponen

| Komponen | Tanggung Jawab |
|---|---|
| `BankDetector` | Menentukan bank dan confidence |
| `BCAParser` | Parse layout BCA |
| `BSIParser` | Parse layout BSI |
| `MuamalatParser` | Parse layout Muamalat rotated |
| `Normalizer` | Normalisasi tanggal, amount, deskripsi |
| `Validator` | Validasi saldo dan ringkasan |
| `ExcelExporter` | Generate xlsx |
| `JobManager` | Queue dan progress |

### 9.3 Strategi Parsing per Bank

#### BCA

- Kelompokkan words berdasarkan `top`.
- Baris transaksi dimulai jika kolom tanggal (`x ~ 40-75`) berisi `DD/MM`.
- Amount diambil dari kolom mutasi (`x ~ 370-445`).
- Marker `DB` menentukan debit.
- Baris tanpa `DB` dianggap kredit.
- Balance diambil dari kolom saldo (`x ~ 500-570`).
- Deskripsi adalah semua baris antara baris tanggal sampai baris tanggal berikutnya.
- Header/footer dideteksi dan diabaikan.

#### BSI

- Kelompokkan words berdasarkan `top`.
- Baris transaksi dimulai jika kolom date (`x ~ 30-75`) berisi `YYYY-MM-DD`.
- Pisahkan time dan FT number menggunakan regex.
- Description diambil dari kolom description; baris continuation digabungkan.
- Amount dan DB/CR diambil dari kolom amount.
- Balance diambil dari kolom balance.
- Validasi dengan total debit/kredit/record dari header.

#### Muamalat

- Tangani rotasi PDF; gunakan koordinat visual.
- Kelompokkan words berdasarkan `top`.
- Baris transaksi dimulai jika kolom reference (`x ~ 30-135`) berisi reference dan kolom tanggal berisi date.
- Amount debit diambil dari kolom debit (`x ~ 320-390`).
- Amount credit diambil dari kolom credit (`x ~ 425-475`).
- Balance diambil dari kolom balance (`x ~ 530-605`), lalu dipisahkan dari deskripsi yang menempel.
- Deskripsi adalah semua baris setelah baris transaksi sampai referensi berikutnya.
- Header/footer dideteksi dan diabaikan.

---

## 10. UX Flow & UI Design

### 10.0 UI Design Principles

- Tema default: **dark mode sederhana**.
- Tidak menggunakan efek glassmorphism, blur berat, transparansi berlebihan, atau animasi dekoratif.
- Fokus pada keterbacaan, kontras tinggi, dan tabel data yang jelas.
- Layout minimal: upload, progress, preview, validasi, download.
- Warna status sederhana: hijau untuk pass, kuning untuk warning, merah untuk fail.

### 10.1 User Flow

1. User membuka halaman upload.
2. User drag-and-drop PDF atau pilih file.
3. User menekan `Convert`.
4. Sistem menampilkan progress.
5. Sistem menampilkan hasil deteksi bank, metadata, jumlah transaksi, status validasi.
6. User melakukan preview tabel.
7. Jika ada warning, baris bermasalah ditandai.
8. User melakukan koreksi jika perlu.
9. User menekan `Download Excel`.
10. Sistem menghasilkan file xlsx dan menghapus file temporary sesuai retention.

---

## 11. Tech Stack Rekomendasi

### 11.1 Frontend

- Next.js 15 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Table
- TanStack Query
- React Hook Form + Zod
- Recharts (opsional dashboard)

Alasan:

- Cocok untuk produk publik.
- Ekosistem matang.
- Performa preview tabel besar baik dengan virtualization.

### 11.2 Backend

- Python 3.11+
- FastAPI
- Pydantic
- pdfplumber
- PyMuPDF
- pandas
- openpyxl
- python-multipart
- Celery atau RQ + Redis
- PostgreSQL
- S3-compatible storage (MinIO/AWS S3)

Alasan:

- Python unggul untuk PDF parsing dan Excel.
- FastAPI cocok untuk API async.
- pdfplumber memberikan koordinat layout yang dibutuhkan untuk tabel kompleks.
- PostgreSQL cocok untuk metadata/audit.

### 11.3 Infra & Observability

- Docker Compose untuk local/dev.
- GitHub Actions untuk CI/CD.
- Sentry untuk error tracking.
- PostHog/Plausible untuk analytics.
- Cloudflare untuk CDN/WAF (publik).
- Redis untuk queue/cache.

### 11.4 Testing

- pytest untuk backend.
- Golden PDF fixtures.
- Property-based tests untuk amount/date parsing.
- Playwright untuk E2E.
- k6/Locust untuk load test (future).

---

## 12. Fitur Tambahan yang Disarankan

### Prioritas Tinggi

- Password PDF support.
- Manual bank override.
- Preview dan edit tabel.
- Highlight baris gagal validasi.
- Download Excel dengan formatting.
- Batch upload + ZIP.
- Job progress.
- Error report yang aman (tanpa PII).

### Prioritas Menengah

- Template kolom custom.
- Simpan profile mapping.
- Deteksi duplikat file/transaksi.
- Re-run parsing.
- OCR fallback untuk scanned PDF.
- API key untuk otomatisasi.
- Webhook hasil job.

### Prioritas Rendah/Future

- Integrasi Accurate/Xero/QuickBooks.
- Dashboard rekonsiliasi.
- Multi-user role dan billing.
- Bank tambahan (Mandiri, BNI, CIMB, dll).
- Mobile app/PWA.

---

## 13. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Layout bank berubah | Parser gagal | Parser versioning, golden tests, fallback text parser |
| Deskripsi multi-baris salah grouping | Data kotor | Grouping berbasis koordinat dan row starter |
| PDF scan tidak bisa dibaca | Gagal total | OCR fallback di fase lanjut |
| File besar membebani server | Timeout | Async queue, timeout, chunking |
| Privasi data | Kepercayaan user | Retention pendek, hapus otomatis, no PII logs |
| Amount/decimal salah | Fatal accounting | Validasi saldo berjalan, decimal exact |

---

## 14. Metrik Sukses

- Conversion success rate >= 98%.
- Row accuracy >= 99%.
- Balance validation pass >= 99%.
- Median processing time untuk 100 halaman < 45 detik.
- User correction rate < 2%.
- Zero known data leakage incidents.

---

## 15. Open Questions

1. Apakah output Excel perlu satu sheet gabungan untuk batch atau satu file per PDF?
2. Apakah deskripsi perlu mempertahankan line break asli atau digabung satu baris?
3. Apakah perlu menyimpan history job untuk user publik?
4. Apakah perlu menambahkan bank lain segera setelah MVP?
5. Apakah perlu mode akuntan dengan kolom debit/kredit terpisah dan signed amount?

---

## 16. Approval

Silakan review PRD ini. Jika disetujui, langkah berikutnya adalah implementasi MVP sesuai `IMPLEMENTATION_PLAN.md`.
