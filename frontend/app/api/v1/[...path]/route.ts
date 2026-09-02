import { NextRequest, NextResponse } from "next/server";

async function proxyRequest(request: NextRequest, pathParams: string[]) {
  const pathStr = pathParams.join("/");
  const search = request.nextUrl.search;
  
  // Try internal Docker backend name first, fallback to localhost:8000 if local
  const isLocal = process.env.NODE_ENV === "development" || !process.env.INTERNAL_BACKEND_URL;
  const primaryBackend = process.env.INTERNAL_BACKEND_URL ?? "http://backend:8000";
  const fallbackBackend = "http://localhost:8000";

  const targets = isLocal ? [fallbackBackend, primaryBackend] : [primaryBackend, fallbackBackend];

  const incomingHeaders = new Headers(request.headers);
  incomingHeaders.delete("host");

  for (const baseUrl of targets) {
    const targetUrl = `${baseUrl}/api/v1/${pathStr}${search}`;
    try {
      const init: RequestInit = {
        method: request.method,
        headers: incomingHeaders,
        cache: "no-store",
      };

      if (request.method !== "GET" && request.method !== "HEAD") {
        init.body = await request.text();
      }

      const res = await fetch(targetUrl, init);
      const data = await res.text();

      return new NextResponse(data, {
        status: res.status,
        headers: {
          "content-type": res.headers.get("content-type") ?? "application/json",
        },
      });
    } catch {
      // Try next target
      continue;
    }
  }

  return NextResponse.json(
    { status: "offline", error: "Backend service unavailable on port 8000" },
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
