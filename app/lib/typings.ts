export type PatientForm = {
  prescriptions: Prescription[];
  treatment: Treatment;
};

export type MPatientForm = {
  prescriptions: MPrescription[];
  treatment: Treatment;
};

export type Treatment = {
  name: string;
  subs: TreatmentSub[];
};

export type TreatmentSub = {
  name: string;
  dose: string; // combined mg and usage spec
};

export type Prescription = {
  drug: string;
  mg: string;
  subs: string[];
  usage: string;
  /** Patient's note for the doctor; missing in forms saved by older versions. */
  note?: string;
};

export type MPrescription = {
  drug: string;
  subs: string;
  usage: string;
  note?: string;
};

export type Interaction = [
  number,
  number,
  string,
  "contraindicated" | "major" | "moderate" | "minor" | "unknown",
];
