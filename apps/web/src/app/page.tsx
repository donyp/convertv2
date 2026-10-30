"use client";

import { useState } from "react";

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

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
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
      setError(err.message || "Upload failed");
      setUploading(false);
    }
  }

  async function pollJob(jobId: string) {
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
        setError(err.message || "Polling failed");
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
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl font-semibold">Bank Mutation PDF to Excel</h1>
      <p className="mt-2 text-sm text-zinc-400">
        Upload mutasi BCA, BSI, atau Muamalat. Bank terdeteksi otomatis.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4 rounded-lg border border-zinc-800 bg-zinc-900 p-6">
        <div>
          <label className="block text-sm font-medium">File PDF</label>
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="mt-2 block w-full text-sm text-zinc-300 file:mr-4 file:rounded file:border-0 file:bg-zinc-800 file:px-3 file:py-2 file:text-zinc-100"
          />
        </div>
        <div>
          <label className="block text-sm font-medium">Password PDF (opsional)</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-2 w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={!file || uploading}
          className="rounded bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 disabled:opacity-50"
        >
          {uploading ? "Processing..." : "Convert"}
        </button>
      </form>

      {error && <div className="mt-4 rounded border border-red-800 bg-red-950 p-3 text-sm text-red-200">{error}</div>}

      {job && (
        <div className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900 p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-zinc-400">Status</div>
              <div className="text-lg font-medium">{job.status}</div>
            </div>
            <div className="text-right">
              <div className="text-sm text-zinc-400">Bank</div>
              <div className="text-lg font-medium">{job.bank || "-"}</div>
            </div>
          </div>
          <div className="mt-4 h-2 w-full rounded bg-zinc-800">
            <div className="h-2 rounded bg-zinc-300" style={{ width: `${job.progress}%` }} />
          </div>
          <div className="mt-2 text-sm text-zinc-400">{job.message}</div>
          {job.transaction_count !== null && (
            <div className="mt-2 text-sm text-zinc-400">
              Transaksi: {job.transaction_count} | Validasi: {job.validation_status}
            </div>
          )}
          {job.status === "completed" && (
            <button onClick={downloadXlsx} className="mt-4 rounded bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900">
              Download Excel
            </button>
          )}
        </div>
      )}

      {result && (
        <div className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900 p-6">
          <h2 className="text-lg font-medium">Preview (maks 50 baris)</h2>
          <div className="mt-4 max-h-96 overflow-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-zinc-800">
                <tr>
                  <th className="px-2 py-1 text-left">Tanggal</th>
                  <th className="px-2 py-1 text-left">Referensi</th>
                  <th className="px-2 py-1 text-left">Keterangan</th>
                  <th className="px-2 py-1 text-right">Debit</th>
                  <th className="px-2 py-1 text-right">Kredit</th>
                  <th className="px-2 py-1 text-right">Saldo</th>
                </tr>
              </thead>
              <tbody>
                {result.transactions.slice(0, 50).map((t: any) => (
                  <tr key={t.row_id} className="border-t border-zinc-800">
                    <td className="px-2 py-1">{t.transaction_date}</td>
                    <td className="px-2 py-1">{t.reference}</td>
                    <td className="px-2 py-1">{t.description}</td>
                    <td className="px-2 py-1 text-right">{t.debit}</td>
                    <td className="px-2 py-1 text-right">{t.credit}</td>
                    <td className="px-2 py-1 text-right">{t.balance}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </main>
  );
}