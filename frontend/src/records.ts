export type ScreeningRisk = "low" | "moderate" | "high";

export type AnemiaStatus = "confirmed" | "not_anemic" | null;

export type Patient = {
  id: string; name: string; village: string | null; age: number | null;
  anemia_status?: AnemiaStatus;
  ashaUserId: number;
  screening: { date: string; hb: number | null; method: string; risk?: ScreeningRisk | null } | null;
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
type PatientResponse = PatientInput & { id: number; asha_user_id: number; anemia_status?: AnemiaStatus; screening?: Patient["screening"] };

async function recordRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/backend-api${path}`, {
      ...options, signal: options.signal
        ? AbortSignal.any([options.signal, AbortSignal.timeout(10000)])
        : AbortSignal.timeout(10000), cache: "no-store",
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
  return [patient.village, age].filter(Boolean).join(" \u00b7 ");
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

export async function uploadPatientReport(patientId: string, file: File): Promise<void> {
  if (file.size > 10 * 1024 * 1024) throw new Error("PDFs must be 10 MB or smaller.");
  if (!file.name.toLowerCase().endsWith(".pdf")) throw new Error("Choose a PDF file.");
  const body = new FormData();
  body.set("file", file);
  await recordRequest("/patients/" + encodeURIComponent(patientId) + "/reports", {
    method: "POST",
    headers: { "X-SakhiCare-Session": "1" },
    body,
  });
}

export type Referral = {
  id: number;
  facility: string;
  referred_on: string;
  status: "referred" | "attended" | "closed";
  outcome: string | null;
};

function patientWrite(method: "POST" | "PUT", body: object): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify(body),
  };
}

export async function saveAnemiaAssessment(id: string, status: AnemiaStatus) {
  return toPatient(await recordRequest<PatientResponse>(
    "/patients/" + id + "/anemia-assessment", patientWrite("PUT", { status }),
  ));
}

export function listReferrals(id: string) {
  return recordRequest<Referral[]>("/patients/" + id + "/referrals");
}

export function createReferral(id: string, facility: string, referred_on: string) {
  return recordRequest<Referral>("/patients/" + id + "/referrals",
    patientWrite("POST", { facility, referred_on }));
}

export function updateReferral(id: string, referralId: number, status: Referral["status"], outcome: string | null) {
  return recordRequest<Referral>("/patients/" + id + "/referrals/" + referralId,
    patientWrite("PUT", { status, outcome }));
}

export type DashboardSummary = {
  registered_this_week: number;
  weekly_hb_change: number | null;
  high_risk_without_open_referral: number;
};

export function getDashboardSummary() {
  return recordRequest<DashboardSummary>("/patients/dashboard-summary");
}

export type TeamReportRow = {
  worker_id: number;
  worker_name: string;
  patients: number;
  hb_recorded: number;
  hb_pending: number;
  anemia_confirmed: number;
  not_assessed: number;
  followups_due: number;
  followups_overdue: number;
  followups_completed: number;
  referrals_referred: number;
  referrals_attended: number;
  referrals_closed: number;
};

export function getTeamReport(filters: Record<string, string>, signal: AbortSignal) {
  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== ""));
  return recordRequest<TeamReportRow[]>("/patients/team-report?" + query.toString(), { signal });
}
