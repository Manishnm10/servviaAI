import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  try {
    const { path } = await params;
    // Construct the backend URL using exactly 127.0.0.1
    // Join the path array and enforce the trailing slash which Django expects
    const targetUrl = `http://127.0.0.1:9000/api/${path.join('/')}/`;
    
    const reqContentType = req.headers.get('content-type') || '';
    let bodyData: FormData | string;
    let fetchHeaders: any = {};
    
    if (reqContentType.includes('multipart/form-data')) {
      bodyData = await req.formData();
      // DO NOT set Content-Type header for multipart, fetch will auto-generate it with the boundary!
    } else {
      bodyData = await req.text();
      fetchHeaders['Content-Type'] = reqContentType || 'application/json';
    }

    const backendResponse = await fetch(targetUrl, {
      method: 'POST',
      headers: fetchHeaders,
      body: bodyData
    });

    // ── Handle Server-Sent Events (SSE) Stream specifically ──
    if (backendResponse.headers.get('content-type')?.includes('text/event-stream')) {
      return new NextResponse(backendResponse.body as any, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache, no-transform',
          'Connection': 'keep-alive',
        }
      });
    }

    // ── Handle normal JSON/Text responses ──
    const contentType = backendResponse.headers.get('content-type') || 'application/json';
    const responseData = await backendResponse.text();
    
    return new NextResponse(responseData, {
      status: backendResponse.status,
      headers: { 'Content-Type': contentType }
    });
    
  } catch (error: any) {
    console.error("Proxy error:", error.message);
    return NextResponse.json({ 
      success: false, 
      error: `Proxy failed to connect to Django on 127.0.0.1:9000: ${error.message}` 
    }, { status: 502 });
  }
}
