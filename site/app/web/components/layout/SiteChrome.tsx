"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

// Site header + page wrapper. With ?embed=1 (widget in an iframe) the header is
// not rendered at all and <main> takes the full height without padding.
export function SiteChrome({ children }: { children: ReactNode }) {
  const embed = useSearchParams().get("embed") === "1";
  if (embed) {
    return <main className="flex min-h-0 w-full flex-1 flex-col">{children}</main>;
  }
  return (
    <>
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
    </>
  );
}
