import type { NextRequest } from "next/server"

export const runtime = "nodejs"

// proxy for server.py, keeps CORS really simple
export async function POST(req: NextRequest) {
  const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  const payload = await req.json()
  const run_id = 1;

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

  return new Response(resp.body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    },
  })
}
