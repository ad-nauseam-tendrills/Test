import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { Nav } from "@/components/layout/Nav";

export const metadata: Metadata = {
  title: "Aperture — Instagram Post Optimizer",
  description: "Prepare and post your work with more intention.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-canvas font-sans text-stone-900 antialiased">
        <AuthProvider>
          <Nav />
          <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
