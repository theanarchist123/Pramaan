import { apiTarget, isAllowed } from "@/lib/proxy-allow";

// Free-hosting proxy: the console calls /staff/api/<api path> on its OWN address and this forwards it to the API (API_INTERNAL_URL), so the
// SameSite=Strict staff cookie is always first-party. The target is read per request, and a missing one says so in plain words instead of a bare 404.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const PASS_REQUEST = ["content-type", "cookie", "origin", "referer", "user-agent", "accept", "accept-language"];

function problem(status: number, detail: string) {
  return new Response(JSON.stringify({ type: "about:blank", title: "Staff console proxy", status, detail }), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });
}

async function forward(req: Request, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const target = apiTarget();
  if (!target) return problem(503, "The console is not connected to the API: API_INTERNAL_URL is not set on this Vercel project (set it to your Render address, then redeploy).");
  const { path } = await ctx.params;
  const joined = (path ?? []).join("/");
  if (!isAllowed(joined)) return problem(404, "That API path is not available through the staff console.");

  const url = new URL(req.url);
  const headers = new Headers();
  for (const h of PASS_REQUEST) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  const ip = req.headers.get("x-forwarded-for");
  if (ip) headers.set("x-forwarded-for", ip);

  const hasBody = !["GET", "HEAD"].includes(req.method);
  let upstream: Response;
  try {
    upstream = await fetch(`${target}/${joined}${url.search}`, { method: req.method, headers, body: hasBody ? await req.arrayBuffer() : undefined, redirect: "manual", cache: "no-store" });
  } catch {
    return problem(502, "The console could not reach the API. If it is on a free Render plan it may be waking up: wait a minute and try again.");
  }

  const out = new Headers();
  for (const h of ["content-type", "cache-control", "retry-after"]) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  for (const c of upstream.headers.getSetCookie()) out.append("set-cookie", c);
  return new Response(upstream.status === 204 ? null : await upstream.arrayBuffer(), { status: upstream.status, headers: out });
}

export { forward as GET, forward as POST, forward as PUT, forward as PATCH, forward as DELETE };
