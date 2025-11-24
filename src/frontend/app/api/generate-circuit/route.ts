import type { NextRequest } from "next/server"

export const runtime = "nodejs"

export async function POST(req: NextRequest) {
  const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  const payload = await req.json()
  const run_id = 1

  const resp = await fetch(`${BACKEND_URL}/create/${run_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    keepalive: true,
  })

  if (!resp.ok) {
    const text = await resp.text().catch(() => "Backend error")
    return new Response(text, { status: resp.status })
  }

  // Forward backend headers and force SSE-compatible headers
  const headers = new Headers(resp.headers)
  headers.set("Cache-Control", "no-cache")
  headers.set("Connection", "keep-alive")
  headers.set("Content-Type", "text/event-stream; charset=utf-8")

  return new Response(resp.body, {
    status: resp.status,
    statusText: resp.statusText,
    headers,
  })
}
