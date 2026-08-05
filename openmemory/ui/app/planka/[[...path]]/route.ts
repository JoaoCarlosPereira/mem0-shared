import { NextRequest, NextResponse } from "next/server";

import { sanitizeUpstreamHeaders } from "@/lib/proxy-headers";
import { plankaInternalBase, rewritePlankaRedirectLocation } from "@/lib/planka-proxy";

/**
 * Reverse proxy same-origin /planka → sidecar PLANKA (Kanban, ADR-007/ADR-008).
 *
 * Sem isto, o board só era alcançável via Traefik na porta não-TLS (:8765,
 * profile sidecars) — quebrando o embed same-origin quando a UI é acessada
 * pela porta 3000 direta ou pelo domínio HTTPS de produção (o mesmo problema
 * que /api-proxy e /registry-api já resolvem para a API/Store).
 *
 * Catch-all opcional ([[...path]]): a raiz "/planka" (sem segmentos) é a
 * primeira requisição do embed — o índice da SPA.
 */
function targetPath(pathSegments: string[]): string {
  const suffix = pathSegments
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return suffix ? `/${suffix}` : "/";
}

async function proxyPlankaRequest(
  req: NextRequest,
  pathSegments: string[],
): Promise<NextResponse> {
  const internalBase = plankaInternalBase();
  // Traefik despe o prefixo /planka antes de repassar ao container (ver
  // stripprefix.prefixes=/planka em docker-compose.scale.yml) — replicamos
  // o mesmo contrato aqui: o sidecar nunca vê "/planka" no path.
  const target = `${internalBase}${targetPath(pathSegments)}${req.nextUrl.search}`;

  const headers = sanitizeUpstreamHeaders(req.headers);

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  // Segue redirects server-side em GET/HEAD (ex.: Sails normalizando barra
  // final); mutações seguem manuais para reescrever o Location antes do
  // browser tentar segui-lo direto ao host Docker-interno.
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
      { detail: "PLANKA indisponível", error: String(err) },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers(upstream.headers);
  if (!followRedirects && upstream.status >= 300 && upstream.status < 400) {
    const location = responseHeaders.get("location");
    if (location) {
      responseHeaders.set(
        "location",
        rewritePlankaRedirectLocation(location, internalBase),
      );
    }
  }
  // fetch() já descomprime a resposta — repassar o content-encoding/length
  // originais faria o browser tentar descomprimir de novo (corpo corrompido).
  responseHeaders.delete("transfer-encoding");
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

type RouteContext = { params: Promise<{ path?: string[] }> };

export async function GET(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyPlankaRequest(req, path ?? []);
}

export async function POST(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyPlankaRequest(req, path ?? []);
}

export async function PUT(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyPlankaRequest(req, path ?? []);
}

export async function PATCH(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyPlankaRequest(req, path ?? []);
}

export async function DELETE(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyPlankaRequest(req, path ?? []);
}
