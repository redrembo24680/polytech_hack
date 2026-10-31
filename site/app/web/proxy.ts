import { NextResponse, type NextRequest } from "next/server";

// Marks embed mode (?embed=1) for server components: the root layout reads
// the `x-embed` request header to skip the site header.
export function proxy(req: NextRequest) {
  const headers = new Headers(req.headers);
  if (req.nextUrl.searchParams.get("embed") === "1") headers.set("x-embed", "1");
  else headers.delete("x-embed");
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: ["/((?!_next/|api/|favicon.ico).*)"] };
