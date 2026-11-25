export type ScreeningRisk = "low" | "moderate" | "high";

export type AnemiaStatus = "confirmed" | "not_anemic" | null;

export type Patient = {
  id: string; name: string; state?: string | null; district?: string | null; block?: string | null;
  village: string | null; locality_type?: "village" | "ward" | null; town?: string | null; ward?: string | null; age: number | null;
  anemia_status?: AnemiaStatus;
  consent_obtained?: boolean | null;
  consent_recorded_at?: string | null;
  consent_recorded_by?: number | null;
  ashaUserId: number;
  screening: { date: string; hb: number | null; method: string; risk?: ScreeningRisk | null } | null;
};

export type Followup = {
  id: string; patientId: string; title: string; date: string; done: boolean;
};

export type CarePathwayStep = {
  id: number; position: number; title: string; status: "pending" | "completed" | "skipped";
  due_date: string | null; completed_at: string | null;
};

export type CarePathway = {
  id: number; patient_id: number; pathway_key: string; title: string;
  status: "active" | "completed" | "paused" | "cancelled";
  created_at: string; updated_at: string; steps: CarePathwayStep[];
};

export type Records = { patients: Patient[]; followups: Followup[] };

export type Pregnancy = {
  id: number; patient_id: number; lmp_date: string | null; edd_date: string;
  status: "active" | "completed" | "closed"; created_at: string;
};
export type AntenatalVisit = {
  id: number; pregnancy_id: number; due_date: string;
  status: "planned" | "completed" | "cancelled"; facility: string | null; completed_at: string | null;
};
export type IfaPlan = {
  id: number; pregnancy_id: number; start_date: string; source: string; directions: string; updated_at: string;
};
export type IfaIntakeLog = {
  id: number; pregnancy_id: number; intake_date: string;
  status: "taken" | "missed" | "unknown"; created_at: string;
};
export type PregnancyCareData = {
  pregnancy: Pregnancy | null; visits: AntenatalVisit[]; ifa_plan: IfaPlan | null; ifa_logs: IfaIntakeLog[];
};

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

type PatientInput = Pick<Patient, "name" | "state" | "district" | "block" | "village" | "locality_type" | "town" | "ward" | "age"> & {
  consent_obtained: boolean;
  confirm_possible_duplicate?: boolean;
};
type PatientResponse = Pick<Patient, "name" | "state" | "district" | "block" | "village" | "locality_type" | "town" | "ward" | "age" | "consent_obtained" | "consent_recorded_at" | "consent_recorded_by"> & {
  id: number; asha_user_id: number; anemia_status?: AnemiaStatus; screening?: Patient["screening"];
};

export class PossibleDuplicateError extends Error {
  matches: Pick<Patient, "id" | "name" | "village" | "age">[];
  constructor(message: string, matches: Pick<Patient, "id" | "name" | "village" | "age">[]) {
    super(message);
    this.matches = matches;
  }
}

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
  const payload = await response.json().catch(() => null);
  if (response.status === 409 && payload?.detail?.code === "possible_duplicate") {
    throw new PossibleDuplicateError(payload.detail.message, payload.detail.matches ?? []);
  }
  if (!response.ok) throw new Error(typeof payload?.detail === "string" ? payload.detail : "Could not complete the request. Please try again.");
  return payload as T;
}

function notifyCarePathwaysChanged() {
  window.dispatchEvent(new Event("sakhicare:care-pathways-changed"));
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
  const locality = patient.locality_type === "ward"
    ? [patient.town, patient.ward ? `Ward ${patient.ward}` : null]
    : [patient.village];
  return [...locality, patient.block, patient.district, patient.state, age].filter(Boolean).join(" \u00b7 ");
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

export function listCarePathways(patientId?: string) {
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : "";
  return recordRequest<CarePathway[]>(`/pathways${query}`);
}

export function getPregnancyCare(patientId: string) {
  return recordRequest<PregnancyCareData>(`/patients/${encodeURIComponent(patientId)}/pregnancy`);
}

export function createPregnancy(patientId: string, dates: { lmp_date: string | null; edd_date: string }) {
  return recordRequest<Pregnancy>(`/patients/${encodeURIComponent(patientId)}/pregnancy`, {
    method: "POST", headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify(dates),
  });
}

export function closePregnancy(patientId: string, pregnancyId: number, status: "completed" | "closed") {
  return recordRequest<Pregnancy>(`/patients/${encodeURIComponent(patientId)}/pregnancy/${pregnancyId}`, {
    method: "PATCH", headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify({ status }),
  });
}

export function scheduleAncVisit(patientId: string, pregnancyId: number, due_date: string, facility: string) {
  return recordRequest<AntenatalVisit>(`/patients/${encodeURIComponent(patientId)}/pregnancy/${pregnancyId}/anc-visits`, {
    method: "POST", headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify({ due_date, facility: facility || null }),
  });
}

export function updateAncVisit(patientId: string, pregnancyId: number, visitId: number, status: "completed" | "cancelled") {
  return recordRequest<AntenatalVisit>(`/patients/${encodeURIComponent(patientId)}/pregnancy/${pregnancyId}/anc-visits/${visitId}`, {
    method: "PATCH", headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify({ status }),
  });
}

export function saveIfaPlan(patientId: string, pregnancyId: number, plan: Pick<IfaPlan, "start_date" | "source" | "directions">) {
  return recordRequest<IfaPlan>(`/patients/${encodeURIComponent(patientId)}/pregnancy/${pregnancyId}/ifa-plan`, {
    method: "PUT", headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify(plan),
  });
}

export function recordIfaIntake(patientId: string, pregnancyId: number, intake_date: string, status: IfaIntakeLog["status"]) {
  return recordRequest<IfaIntakeLog>(`/patients/${encodeURIComponent(patientId)}/pregnancy/${pregnancyId}/ifa-intake`, {
    method: "PUT", headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify({ intake_date, status }),
  });
}

export function updateCarePathwayStep(runId: number, stepId: number, completed: boolean) {
  return recordRequest<CarePathway>(`/pathways/${runId}/steps/${stepId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
    body: JSON.stringify({ completed }),
  });
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
  }).then(result => { notifyCarePathwaysChanged(); return result; });
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
    patientWrite("POST", { facility, referred_on })).then(result => { notifyCarePathwaysChanged(); return result; });
}

export function updateReferral(id: string, referralId: number, status: Referral["status"], outcome: string | null) {
  return recordRequest<Referral>("/patients/" + id + "/referrals/" + referralId,
    patientWrite("PUT", { status, outcome })).then(result => { notifyCarePathwaysChanged(); return result; });
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


export type PatientActivityEvent = {
  id: number;
  actor_name: string | null;
  action: string;
  summary: string;
  created_at: string;
};

export function listPatientActivity(patientId: string) {
  return recordRequest<PatientActivityEvent[]>(`/patients/${patientId}/activity`);
}

export async function updatePatientConsent(patientId: string, consent_obtained: boolean) {
  return toPatient(await recordRequest<PatientResponse>(
    `/patients/${patientId}/consent`, patientWrite("PUT", { consent_obtained }),
  ));
}


