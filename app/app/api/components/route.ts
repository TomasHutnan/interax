import type { NextRequest } from 'next/server'

export async function GET(request: NextRequest) {
    const code = request.nextUrl.searchParams.get('name')

    if (code === null) {
        return Response.json({ error: 'Missing "name" query parameter' }, { status: 400 })
    }

    return Response.json(["substance a", "substance b"])
}
