import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bank Mutation Converter",
  description: "Convert bank mutation PDF to Excel",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" className="dark">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased">
        {children}
      </body>
    </html>
  );
}