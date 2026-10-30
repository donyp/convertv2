"use client";

import { useCallback, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type JobStatus = {
  id: string;
  status: string;
  progress: number;
  message: string;
  bank: string | null;
  validation_status: string | null;
  transaction_count: number | null;
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const acceptFile = useCallback((f: File | null) => {
    if (!f) return;
    if (f.type !== "application/pdf" && !f.name.toLowerCase().endsWith(".pdf")) {
      setError("File harus berformat PDF.");
      return;
    }
    setError(null);
    setResult(null);
    setJob(null);
    setFile(f);
  }, []);

  async function handleSubmit(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!file) return;
    setError(null);
    setResult(null);
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      if (password) form.append("password", password);
      const res = await fetch(`${API_URL}/api/v1/jobs`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      pollJob(data.job_id);
    } catch (err: any) {
      setError(err.message || "Upload gagal");
      setUploading(false);
    }
  }

  function pollJob(jobId: string) {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/jobs/${jobId}`);
        const data = await res.json();
        setJob(data);
        if (data.status === "completed") {
          clearInterval(interval);
          setUploading(false);
          const r = await fetch(`${API_URL}/api/v1/jobs/${jobId}/result`);
          setResult(await r.json());
        } else if (data.status === "failed") {
          clearInterval(interval);
          setUploading(false);
          setError(data.message);
        }
      } catch (err: any) {
        clearInterval(interval);
        setUploading(false);
        setError(err.message || "Polling gagal");
      }
    }, 1500);
  }

  async function downloadXlsx() {
    if (!job) return;
    const res = await fetch(`${API_URL}/api/v1/jobs/${job.id}/download`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${job.bank || "mutation"}_${job.id}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-6xl px-4 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight">Bank Mutation Converter</h1>
          <p className="mt-2 text-sm text-zinc-400">
            Konversi mutasi BCA, BSI, dan Muamalat PDF ke Excel. Bank terdeteksi otomatis.
          </p>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                acceptFile(e.dataTransfer.files?.[0] || null);
              }}
              onClick={() => inputRef.current?.click()}
              className={`flex min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors ${
                dragging
                  ? "border-zinc-300 bg-zinc-800"
                  : "border-zinc-700 bg-zinc-950 hover:border-zinc-500"
              }`}
            >
              <input
                ref={inputRef}
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={(e) => acceptFile(e.target.files?.[0] || null)}
              />
              <div className="text-4xl text-zinc-500">↑</div>
              <div className="mt-3 text-base font-medium">
                {dragging ? "Lepaskan file di sini" : "Drag & drop PDF mutasi"}
              </div>
              <div className="mt-1 text-sm text-zinc-500">atau klik untuk pilih file</div>
              {file && (
                <div className="mt-4 rounded-md border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm">
                  <span className="font-medium text-zinc-100">{file.name}</span>
                  <span className="ml-2 text-zinc-500">{formatBytes(file.size)}</span>
                </div>
              )}
            </div>

            <div className="mt-5">
              <label className="block text-sm font-medium text-zinc-300">Password PDF (opsional)</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Kosongkan jika tidak ada password"
                className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-400"
              />
            </div>

            <button
              onClick={() => handleSubmit()}
              disabled={!file || uploading}
              className="mt-5 w-full rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              {uploading ? "Memproses..." : "Convert ke Excel"}
            </button>

            {error && (
              <div className="mt-4 rounded-lg border border-red-900 bg-red-950/60 p-3 text-sm text-red-200">
                {error}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
            <h2 className="text-lg font-medium">Status</h2>
            {!job && <p className="mt-3 text-sm text-zinc-500">Belum ada proses.</p>}
            {job && (
              <div className="mt-4 space-y-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-zinc-400">Status</span>
                  <span className="font-medium capitalize">{job.status}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-zinc-400">Bank</span>
                  <span className="font-medium">{job.bank || "-"}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-zinc-400">Transaksi</span>
                  <span className="font-medium">{job.transaction_count ?? "-"}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-zinc-400">Validasi</span>
                  <span className="font-medium">{job.validation_status || "-"}</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
                  <div
                    className="h-2 rounded-full bg-zinc-200 transition-all"
                    style={{ width: `${job.progress}%` }}
                  />
                </div>
                <div className="text-xs text-zinc-500">{job.message}</div>
                {job.status === "completed" && (
                  <button
                    onClick={downloadXlsx}
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:bg-zinc-700"
                  >
                    Download Excel
                  </button>
                )}
              </div>
            )}
          </div>
        </section>

        {result && (
          <section className="mt-8 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium">Preview (maks 50 baris)</h2>
              <span className="text-xs text-zinc-500">{result.transactions.length} transaksi</span>
            </div>
            <div className="mt-4 max-h-[420px] overflow-auto rounded-lg border border-zinc-800">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-zinc-800 text-zinc-300">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Tanggal</th>
                    <th className="px-3 py-2 text-left font-medium">Referensi</th>
                    <th className="px-3 py-2 text-left font-medium">Keterangan</th>
                    <th className="px-3 py-2 text-right font-medium">Debit</th>
                    <th className="px-3 py-2 text-right font-medium">Kredit</th>
                    <th className="px-3 py-2 text-right font-medium">Saldo</th>
                  </tr>
                </thead>
                <tbody>
                  {result.transactions.slice(0, 50).map((t: any) => (
                    <tr key={t.row_id} className="border-t border-zinc-800 text-zinc-300">
                      <td className="px-3 py-2 whitespace-nowrap">{t.transaction_date}</td>
                      <td className="px-3 py-2">{t.reference}</td>
                      <td className="px-3 py-2">{t.description}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{t.debit}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{t.credit}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{t.balance}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}