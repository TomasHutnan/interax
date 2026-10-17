import { Interaction, PatientForm } from '@/lib/typings'
import type { NextRequest } from 'next/server'

export async function POST(request: NextRequest) {
    const ints: Interaction[] = [
        [0, 1, "blabla", "moderate"]
    ]
    
    return Response.json(ints)
}
