export type PatientForm = {
    prescriptions: Prescription[],
    treatment: Treatment,
}

export type MPatientForm = {
    prescriptions: MPrescription[]
    treatment: Treatment,
}

export type Treatment = {
    name: string
    subs: TreatmentSub[]
}

export type TreatmentSub = {
    name: string,
    dose: string // combined mg and usage spec
}

export type Prescription = {
    drug: string,
    mg: string
    subs: string[],
    usage: string
}

export type MPrescription = {
    drug: string
    subs: string,
    usage: string
}

export type Interaction = [number, number, string, "contraindicated" | "major" | "moderate" | "minor" | "unknown"]