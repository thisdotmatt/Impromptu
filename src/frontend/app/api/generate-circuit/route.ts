import type { NextRequest } from "next/server"
import { NextResponse } from "next/server"

export const runtime = "nodejs"
// (Optional but nice to be explicit)
// export const dynamic = "force-dynamic"

export async function POST(req: NextRequest) {
  const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  const payload = await req.json()
  const run_id = crypto.randomUUID() // better than a constant 1 if you ever want parallel runs

  const backendRes = await fetch(`${BACKEND_URL}/create/${run_id}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
  })

  if (!backendRes.ok || !backendRes.body) {
    const text = await backendRes.text().catch(() => "Backend error")
    return new NextResponse(text, { status: backendRes.status })
  }

  // Create a new streaming response that *pipes* the backend stream
  const stream = new ReadableStream({
    start(controller) {
      const reader = backendRes.body!.getReader()

      const pump = (): any =>
        reader.read().then(({ done, value }) => {
          if (done) {
            controller.close()
            return
          }
          controller.enqueue(value)
          return pump()
        })

      pump().catch((err) => {
        console.error("[generate-circuit] stream pump error", err)
        controller.error(err)
      })
    },
  })

  return new NextResponse(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      // Helps in some reverse proxies:
      // "X-Accel-Buffering": "no",
    },
  })
}
