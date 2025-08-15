import type { NextRequest } from "next/server"

export const runtime = "nodejs" // ensure robust streaming behavior on Node runtime

export async function POST(req: NextRequest) {
  const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  const payload = await req.json()

  const resp = await fetch(`${BACKEND_URL}/orchestrator/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // Keep the body identical to what the backend expects
    body: JSON.stringify(payload),
    // @ts-expect-error: keepalive is allowed in node fetch
    keepalive: true,
  })

  if (!resp.ok) {
    const text = await resp.text().catch(() => "Backend error")
    return new Response(text, { status: resp.status })
  }

  // Pipe the streaming body through unchanged so the UI keeps working
  return new Response(resp.body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    },
  })
}
