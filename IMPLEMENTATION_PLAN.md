# Implementation Plan

## PDF Mutasi Bank to Excel Converter

**Versi:** 1.0 (draft untuk approval)  
**Referensi:** `PRD.md`  
**Target:** MVP internal, lalu public-ready

---

## 1. Strategi Implementasi

Implementasi dibagi menjadi 6 fase:

1. Foundation & parsing engine
2. Validation & Excel export
3. API & async jobs
4. Frontend preview & editing
5. Security, testing, hardening
6. Public release readiness

Prinsip:

- Parser bank dibuat terpisah dan testable.
- Gunakan golden PDF samples sebagai regression tests.
- Jangan langsung export sebelum validasi saldo.
- Semua amount menggunakan `Decimal`, bukan float.

---

## 2. Struktur Repository (Usulan)

```text
apps/
  web/                    # Next.js frontend
  api/                    # FastAPI backend
packages/
  parser/                 # Bank parsers & validators
  shared/                 # Shared types/schemas
infra/
  docker/
  scripts/
samples/
  bca/
  bsi/
  muamalat/
tests/
  golden/
  integration/
docs/
  PRD.md
  IMPLEMENTATION_PLAN.md
```

---

## 3. Fase 0 - Analisis & Fixtures (1-2 hari)

### Task

- [ ] Simpan sample PDF sebagai fixtures (BCA, BSI, Muamalat).
- [ ] Buat script inspeksi layout (`extract words`, `x0`, `top`).
- [ ] Dokumentasikan koordinat kolom per bank.
- [ ] Tentukan expected row count:
  - BCA: 23
  - BSI: 256
  - Muamalat: 806

### Output

- `tests/golden/expected/*.json`
- Dokumentasi layout parser.

---

## 4. Fase 1 - Parser Engine (5-7 hari)

### 4.1 Core Models

Implement Pydantic models:

- `StatementMetadata`
- `Transaction`
- `ParseResult`
- `ValidationResult`
- `BankDetectionResult`

### 4.2 Bank Detector

Rules:

- BCA: teks mengandung `REKENING GIRO`, `KETERANGAN`, `MUTASI`, `SALDO`, `BCA`.
- BSI: teks mengandung `Account Statement`, `FT Number`, `BSI`.
- Muamalat: teks mengandung `ACCOUNT STATEMENT`, `Muamalat`, `Reference Number`.

Output confidence 0-1.

### 4.3 BCA Parser

Tasks:

- [ ] Parse header metadata.
- [ ] Detect table start.
- [ ] Group rows by date.
- [ ] Parse amount dan DB marker.
- [ ] Parse balance.
- [ ] Gabungkan deskripsi multi-baris.
- [ ] Parse summary (`SALDO AWAL`, `MUTASI CR`, `MUTASI DB`, `SALDO AKHIR`).
- [ ] Abaikan footer page.

### 4.4 BSI Parser

Tasks:

- [ ] Parse header summary.
- [ ] Detect table header.
- [ ] Parse date + FT number.
- [ ] Gabungkan description continuation.
- [ ] Parse amount + DB/CR.
- [ ] Parse balance.
- [ ] Abaikan footer dan repeated header.

### 4.5 Muamalat Parser

Tasks:

- [ ] Handle rotation PDF.
- [ ] Parse header metadata.
- [ ] Detect table header.
- [ ] Parse reference + transaction/effective date.
- [ ] Parse debit/credit columns.
- [ ] Parse balance dan pisahkan dari description.
- [ ] Gabungkan deskripsi multi-baris.
- [ ] Abaikan footer.

### 4.6 Normalizer

- [ ] Parse tanggal `DD/MM`, `YYYY-MM-DD`, `DD-MMM-YYYY`.
- [ ] Parse amount dengan comma/dot.
- [ ] Bersihkan deskripsi.
- [ ] Tentukan transaction type.

### Deliverable Fase 1

- Parser dapat dijalankan via CLI/script.
- Output JSON untuk setiap sample.
- Row count sesuai expected.

---

## 5. Fase 2 - Validation & Excel Export (3-4 hari)

### 5.1 Validator

- [ ] Running balance check.
- [ ] Header total check.
- [ ] Header count check.
- [ ] Date validity check.
- [ ] Amount parse check.
- [ ] Duplicate reference check.
- [ ] Confidence scoring.

### 5.2 Excel Exporter

- [ ] Sheet `Summary`.
- [ ] Sheet `Transactions`.
- [ ] Formatting number/date.
- [ ] Freeze panes.
- [ ] Auto width.
- [ ] Highlight invalid rows (opsional MVP: kolom `flags`).

### Deliverable Fase 2

- File xlsx dapat dibuka di Excel/LibreOffice.
- Validasi BCA/BSI/Muamalat pass.

---

## 6. Fase 3 - API & Async Jobs (4-5 hari)

### Backend Endpoints (MVP)

| Method | Endpoint | Fungsi |
|---|---|---|
| POST | `/api/v1/jobs` | Upload PDF dan buat job |
| GET | `/api/v1/jobs/{id}` | Status dan progress |
| GET | `/api/v1/jobs/{id}/result` | Preview JSON |
| PATCH | `/api/v1/jobs/{id}/transactions/{row_id}` | Edit baris |
| POST | `/api/v1/jobs/{id}/export` | Generate Excel |
| GET | `/api/v1/jobs/{id}/download` | Download file |
| DELETE | `/api/v1/jobs/{id}` | Hapus job dan file |

### Tasks

- [ ] Setup FastAPI project.
- [ ] File upload validation.
- [ ] Password PDF handling.
- [ ] Job state machine: `queued`, `processing`, `needs_review`, `completed`, `failed`.
- [ ] Redis + RQ/Celery worker.
- [ ] Progress reporting.
- [ ] Temporary storage cleanup.
- [ ] Basic rate limiting.

### Deliverable Fase 3

- API dapat dipanggil dari frontend.
- File 121 halaman diproses async tanpa timeout HTTP.

---

## 7. Fase 4 - Frontend (5-7 hari)

### Pages

- `/` upload page
- `/jobs/[id]` preview & validation
- `/jobs/[id]/export` download

### Components

- Upload dropzone
- Bank detection badge
- Metadata card
- Validation summary
- Data table dengan TanStack Table
- Inline cell editor
- Progress indicator
- Download button

### Tasks

- [ ] Setup Next.js + Tailwind + shadcn/ui.
- [ ] Terapkan tema dark sederhana tanpa glassmorphism/blur berat.
- [ ] Upload flow.
- [ ] Polling job status.
- [ ] Render preview table.
- [ ] Inline editing.
- [ ] Manual bank override.
- [ ] Download Excel.
- [ ] Error/empty states.

### Deliverable Fase 4

- User dapat upload, preview, koreksi, dan download Excel.

---

## 8. Fase 5 - Testing & Hardening (4-5 hari)

### Backend Tests

- [ ] Unit tests parser per bank.
- [ ] Golden file tests row count.
- [ ] Validation tests saldo berjalan.
- [ ] Amount/date parsing tests.
- [ ] API tests upload/export.

### Frontend Tests

- [ ] Component tests.
- [ ] E2E upload-to-download.

### Security

- [ ] File type validation.
- [ ] Size limit.
- [ ] Password handling.
- [ ] Temporary file cleanup.
- [ ] Rate limiting.
- [ ] No PII in logs.

### Performance

- [ ] Benchmark BCA/BSI/Muamalat.
- [ ] Optimize Muamalat 121 pages.
- [ ] Virtualized table.

### Deliverable Fase 5

- CI pipeline hijau.
- Benchmark sesuai target PRD.

---

## 9. Fase 6 - Public Release Readiness (3-4 hari)

- [ ] Kebijakan privasi dan terms.
- [ ] Retention policy final.
- [ ] Monitoring dan alerting.
- [ ] Dokumentasi user.
- [ ] API documentation.
- [ ] Deployment production.
- [ ] Backup database.
- [ ] Load test.

---

## 10. Timeline Ringkas

| Fase | Estimasi |
|---|---:|
| Fase 0 - Fixtures & analisis | 1-2 hari |
| Fase 1 - Parser engine | 5-7 hari |
| Fase 2 - Validation & Excel | 3-4 hari |
| Fase 3 - API & jobs | 4-5 hari |
| Fase 4 - Frontend | 5-7 hari |
| Fase 5 - Testing & hardening | 4-5 hari |
| Fase 6 - Public readiness | 3-4 hari |
| **Total MVP internal** | **~22-34 hari** |

---

## 11. Risiko Implementasi

| Risiko | Mitigasi |
|---|---|
| Parser Muamalat kompleks | Mulai dari golden tests dan validasi saldo |
| BSI description wrap | Grouping continuation berbasis x dan date starter |
| File 121 halaman lambat | Async worker dan benchmark |
| Perubahan layout bank | Parser version + regression tests |

---

## 12. Definition of Done (MVP)

MVP dianggap selesai jika:

- [ ] BCA, BSI, Muamalat dapat dikonversi.
- [ ] Auto-detect bank berfungsi.
- [ ] Row count sesuai sample.
- [ ] Validasi saldo berjalan pass untuk sample.
- [ ] Excel dapat dibuka dan rapi.
- [ ] Preview dan koreksi manual tersedia.
- [ ] File temporary dibersihkan.
- [ ] Tests utama lulus.

---

## 13. Rekomendasi Langkah Berikutnya

1. Approve PRD dan plan.
2. Saya buat scaffold repository.
3. Implement parser BCA terlebih dahulu sebagai proof of concept.
4. Lanjut BSI dan Muamalat.
5. Baru frontend dan deployment.
