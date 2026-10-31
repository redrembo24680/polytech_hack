import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin", "cyrillic"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Bookly — онлайн-запис",
  description: "Платформа онлайн-запису для салонів і клінік",
};

// "Bookly" is a placeholder brand name.
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="uk"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <ToastProvider>
          <header className="border-b border-slate-200 bg-white">
            <div className="mx-auto flex h-14 max-w-6xl items-center px-4">
              <Link href="/" className="flex items-center gap-2 text-lg font-semibold text-slate-900">
                <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent-600 text-sm text-white">
                  B
                </span>
                Bookly
              </Link>
            </div>
          </header>
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        </ToastProvider>
      </body>
    </html>
  );
}
