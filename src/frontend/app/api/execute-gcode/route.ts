export const runtime = "nodejs"

export async function POST(req: Request) {
  const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  const body = await req.json()

  const resp = await fetch(`${BACKEND_URL}/execute-gcode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })

  return new Response(JSON.stringify(await resp.json()), {
    status: resp.status,
    headers: { "Content-Type": "application/json" },
  })
}