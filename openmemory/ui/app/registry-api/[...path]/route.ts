import { NextRequest, NextResponse } from "next/server";

import { sanitizeUpstreamHeaders } from "@/lib/proxy-headers";
import {
  applyLegacyRegistryAuthorization,
  hasRegistryAuthorization,
  isRegistryProxyPathAllowed,
  registryInternalBase,
  registryProxyTarget,
} from "@/lib/registry-proxy";

function rewriteRegistryRedirectLocation(
  location: string,
  internalBase: string,
): string {
  if (!location) return location;

  const base = internalBase.replace(/\/$/, "");
  if (location.startsWith(base)) {
    return `/registry-api${location.slice(base.length)}`;
  }

  try {
    const parsed = new URL(location);
    const internal = new URL(base.includes("://") ? base : `http://${base}`);
    if (parsed.host === internal.host) {
      return `/registry-api${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
  } catch {
    if (location.startsWith("/")) {
      return `/registry-api${location}`;
    }
  }

  return location;
}

async function proxyRegistryRequest(
  req: NextRequest,
  pathSegments: string[],
): Promise<NextResponse> {
  // Google: exige Bearer da sessão. Legado: injeta Bearer local se ausente.
  const authorizedHeaders = applyLegacyRegistryAuthorization(req.headers);
  if (!hasRegistryAuthorization(authorizedHeaders)) {
    return NextResponse.json(
      { detail: "registry authentication required" },
      { status: 401 },
    );
  }

  if (!isRegistryProxyPathAllowed(req.method, pathSegments)) {
    return NextResponse.json(
      { detail: "registry endpoint not allowed" },
      { status: 403 },
    );
  }

  const internalBase = registryInternalBase();
  const target = registryProxyTarget(internalBase, pathSegments, req.nextUrl.search);
  const headers = sanitizeUpstreamHeaders(authorizedHeaders);
  headers.delete("cookie");

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const followRedirects = req.method === "GET" || req.method === "HEAD";
  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: followRedirects ? "follow" : "manual",
  };
  if (hasBody) {
    init.body = await req.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch (err) {
    return NextResponse.json(
      { detail: "registry upstream indisponível", error: String(err) },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers(upstream.headers);
  if (
    !followRedirects &&
    upstream.status >= 300 &&
    upstream.status < 400
  ) {
    const location = responseHeaders.get("location");
    if (location) {
      responseHeaders.set(
        "location",
        rewriteRegistryRedirectLocation(location, internalBase),
      );
    }
  }
  responseHeaders.delete("transfer-encoding");
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyRegistryRequest(req, path);
}

export async function POST(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyRegistryRequest(req, path);
}

export async function PUT(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyRegistryRequest(req, path);
}

export async function PATCH(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyRegistryRequest(req, path);
}

export async function DELETE(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyRegistryRequest(req, path);
}
