import { NextRequest, NextResponse } from "next/server";

async function proxyRequest(request: NextRequest, pathParams: string[]) {
  const pathStr = pathParams.join("/");
  const search = request.nextUrl.search;
  
  // Try internal Docker backend name first, fallback to localhost:8000 if local
  const isLocal = process.env.NODE_ENV === "development";
  const primaryBackend = process.env.INTERNAL_BACKEND_URL ?? "http://backend:8000";
  const fallbackBackend = "http://localhost:8000";

  const targets = isLocal ? [fallbackBackend, primaryBackend] : [primaryBackend, fallbackBackend];

  const incomingHeaders = new Headers(request.headers);
  incomingHeaders.delete("host");
  incomingHeaders.delete("content-length");
  const body = request.method !== "GET" && request.method !== "HEAD" ? await request.text() : undefined;

  let lastError = "";

  for (const baseUrl of targets) {
    const targetUrl = `${baseUrl}/api/v1/${pathStr}${search}`;
    try {
      // A full all-market scan currently takes several minutes. Keep the
      // ordinary proxy timeout short, but allow this explicit operator action
      // to finish instead of incorrectly reporting the healthy API as offline.
      const timeoutMs = request.method === "POST" && pathStr === "scanner/run" ? 600_000 : 60_000;
      const init: RequestInit = {
        method: request.method,
        headers: incomingHeaders,
        cache: "no-store",
        signal: AbortSignal.timeout(timeoutMs),
      };

      if (body !== undefined) {
        init.body = body;
      }

      const res = await fetch(targetUrl, init);
      const data = await res.text();

      return new NextResponse(data, {
        status: res.status,
        headers: {
          "content-type": res.headers.get("content-type") ?? "application/json",
        },
      });
    } catch (err: any) {
      lastError = err?.message ?? String(err);
      continue;
    }
  }

  return NextResponse.json(
    { status: "offline", error: `Backend service unavailable on port 8000 (${lastError})` },
    { status: 503 }
  );
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyRequest(request, path);
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyRequest(request, path);
}

export async function PUT(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyRequest(request, path);
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyRequest(request, path);
}
