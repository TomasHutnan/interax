import { PatientForm } from '@/lib/typings'
import type { NextRequest } from 'next/server'

export async function GET(request: NextRequest) {
    const code = request.nextUrl.searchParams.get('code')

    if (code === null) {
        return Response.json({ error: 'Missing "code" query parameter' }, { status: 400 })
    }

    const form: PatientForm = {
        prescriptions: [
            {
                drug: 'Ibalgin 400',
                mg: '400 mg',
                subs: ['Ibuprofen'],
                usage: '1-0-1-0'
            },
            {
                drug: 'Anopyrin 100',
                mg: '100 mg',
                subs: ['Acetylsalicylic acid'],
                usage: '1x'
            },
            {
                drug: 'Prolia',
                mg: '60 mg',
                subs: ['Denosumab'],
                usage: 'á 2'
            }
        ],
        treatment: {
            name: `Sample treatment otp=${code}`,
            subs: [
                { name: 'Ibuprofen 400 mg', dose: '1-0-1-0' },
                { name: 'Acetylsalicylic acid 100 mg', dose: '1x' },
                { name: 'Denosumab 60 mg', dose: 'á 180' }
            ]
        }
    }

    return Response.json(form)
}
