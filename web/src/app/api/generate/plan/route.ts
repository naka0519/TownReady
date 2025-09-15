export async function POST(req: Request) {
  try {
    const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || '';
    if (!API_BASE) {
      return new Response(JSON.stringify({ status: 'error', message: 'API_BASE_URL is not set' }), { status: 500 });
    }
    const payload = await req.json();
    const res = await fetch(`${API_BASE}/api/generate/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      // Disable Next fetch cache to avoid stale responses
      cache: 'no-store',
    });
    const text = await res.text();
    return new Response(text, { status: res.status, headers: { 'Content-Type': res.headers.get('content-type') || 'application/json' } });
  } catch (e: any) {
    return new Response(JSON.stringify({ status: 'error', message: e?.message || 'proxy_failed' }), { status: 500 });
  }
}

