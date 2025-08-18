export const runtime = "nodejs"

export async function POST(req: Request) {
  const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  const body = await req.text()

  const resp = await fetch(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  })

  if (!resp.ok) {
    const text = await resp.text().catch(() => "Backend error")
    return new Response(text, { status: resp.status })
  }

  // Pass SSE through unchanged
  const headers = new Headers(resp.headers)
  headers.set("Cache-Control", "no-cache")
  headers.set("Connection", "keep-alive")
  headers.set("Content-Type", "text/event-stream")

  return new Response(resp.body, {
    status: resp.status,
    statusText: resp.statusText,
    headers,
  })
}