"use client";

import { useCallback, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

type ResultInfo = {
  bank: string | null;
  validation: string | null;
  count: number | null;
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [info, setInfo] = useState<ResultInfo | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const acceptFile = useCallback((f: File | null) => {
    if (!f) return;
    if (f.type !== "application/pdf" && !f.name.toLowerCase().endsWith(".pdf")) {
      setError("File harus berformat PDF.");
      return;
    }
    setError(null);
    setInfo(null);
    setFile(f);
  }, []);

  async function handleConvert(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!file) return;
    setError(null);
    setInfo(null);
    setProcessing(true);
    try {
      const form = new FormData();
      form.append("file", file);
      if (password) form.append("password", password);
      const url = API_URL ? `${API_URL}/api/v1/convert` : "/api/v1/convert";
      const res = await fetch(url, { method: "POST", body: form });
      if (!res.ok) {
        const text = await res.text();
        let message = `Request gagal (${res.status})`;
        try {
          const data = JSON.parse(text);
          message = data.detail || data.message || message;
        } catch {
          if (text && text.length < 200) message = text;
        }
        throw new Error(message);
      }
      const blob = await res.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      a.download = match ? match[1] : `${file.name.replace(/\.pdf$/i, "")}.xlsx`;
      a.click();
      URL.revokeObjectURL(downloadUrl);
      setInfo({ bank: null, validation: null, count: null });
    } catch (err: any) {
      setError(err.message || "Konversi gagal");
    } finally {
      setProcessing(false);
    }
  }

  return (
    <main className="min-h-screen overflow-x-hidden bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-5xl px-4 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight">Bank Mutation Converter</h1>
          <p className="mt-2 text-sm text-zinc-400">
            Konversi mutasi BCA, BSI, dan Muamalat PDF ke Excel. Bank terdeteksi otomatis.
          </p>
        </header>

        <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
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
            className={`flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
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
            <div className="text-3xl text-zinc-500">↑</div>
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
            onClick={() => handleConvert()}
            disabled={!file || processing}
            className="mt-5 w-full rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {processing ? "Memproses..." : "Convert & Download Excel"}
          </button>

          {error && (
            <div className="mt-4 max-w-full overflow-hidden rounded-lg border border-red-900 bg-red-950/60 p-3 text-sm text-red-200">
              <div className="break-words whitespace-pre-wrap">{error}</div>
            </div>
          )}

          {info && (
            <div className="mt-4 rounded-lg border border-zinc-700 bg-zinc-950 p-3 text-sm text-zinc-300">
              Bank: {info.bank || "-"} | Validasi: {info.validation || "-"} | Transaksi: {info.count ?? "-"}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}