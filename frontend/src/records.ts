export type Patient = {
  id: string; name: string; village: string | null; age: number | null;
  ashaUserId: number;
  screening: { date: string; hb: number | null; method: string } | null;
};

export type Followup = {
  id: string; patientId: string; title: string; date: string; done: boolean;
};

export type Records = { patients: Patient[]; followups: Followup[] };

export function dateKey(offset = 0) {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return [date.getFullYear(), date.getMonth() + 1, date.getDate()]
    .map(part => String(part).padStart(2, "0")).join("-");
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" })
    .format(new Date(value + "T12:00:00"));
}

type PatientInput = Pick<Patient, "name" | "village" | "age">;
type PatientResponse = PatientInput & { id: number; asha_user_id: number; screening?: Patient["screening"] };

async function recordRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/backend-api${path}`, {
      ...options, signal: AbortSignal.timeout(10000), cache: "no-store",
    });
  } catch {
    throw new Error("Could not reach SakhiCare. Check your connection and try again.");
  }
  if (response.status === 401) throw new Error("Your session expired. Sign in again.");
  if (!response.ok) throw new Error("Could not complete the request. Please try again.");
  return await response.json() as T;
}

function toPatient(record: PatientResponse): Patient {
  const { id, asha_user_id, ...details } = record;
  return { ...details, id: String(id), ashaUserId: asha_user_id, screening: record.screening ?? null };
}

export async function listPatients(): Promise<Patient[]> {
  return (await recordRequest<PatientResponse[]>("/patients")).map(toPatient);
}

export async function registerPatient(patient: PatientInput): Promise<Patient> {
  const record = await recordRequest<PatientResponse>("/patients", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify(patient),
  });
  return toPatient(record);
}

export function patientDetails(patient: Patient): string {
  const age = patient.age === null ? null : `${patient.age} years`;
  return [patient.village, age].filter(Boolean).join(" ? ");
}


type FollowupResponse = { id: number; patient_id: number; title: string; due_date: string; is_completed: boolean };

function toFollowup(record: FollowupResponse): Followup {
  return {
    id: String(record.id), patientId: String(record.patient_id), title: record.title,
    date: record.due_date, done: record.is_completed,
  };
}

export async function listFollowups(): Promise<Followup[]> {
  return (await recordRequest<FollowupResponse[]>("/followups")).map(toFollowup);
}

export async function scheduleFollowup(patientId: string, title: string, date: string): Promise<Followup> {
  return toFollowup(await recordRequest<FollowupResponse>("/followups", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify({ patient_id: Number(patientId), title, due_date: date }),
  }));
}

export async function completeFollowup(id: string, done: boolean): Promise<Followup> {
  return toFollowup(await recordRequest<FollowupResponse>(`/followups/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify({ is_completed: done }),
  }));
}


export function saveScreening(patientId: string, screening: NonNullable<Patient["screening"]>) {
  return recordRequest<NonNullable<Patient["screening"]>>(`/patients/${patientId}/screening`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify(screening),
  });
}


export type HbReading = { id: number; date: string; hb: number; method: string };

export function listHbReadings(patientId: string) {
  return recordRequest<HbReading[]>(`/patients/${patientId}/screening/history`);
}
