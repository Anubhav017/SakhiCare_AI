import "@fontsource-variable/noto-sans/wght.css";
import "@fontsource-variable/noto-sans-devanagari/wght.css";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { getDashboardSummary, type DashboardSummary, saveScreening, dateKey, listPatients, listFollowups, scheduleFollowup, completeFollowup, patientDetails, registerPatient, PossibleDuplicateError, type Records, type Followup, type ScreeningRisk } from "./records";
import { AuthPage, restoreSession, signOut, type Account } from "./AuthPage";
import { AdminDashboard } from "./AdminDashboard";
import { OnboardingConsole } from "./OnboardingConsole";
import { CarePathways } from "./CarePathways";
import { AskGuidelines } from "./AskGuidelines";
import { FollowupList, PatientDetail, followupStatus, patientRoute } from "./PatientWorkspace";
import { AccountMenu, ProfilePage } from "./AccountMenu";
import { PatientReportUpload } from "./PatientReportUpload";
import { PatientLocationFields } from "./PatientLocationFields";
import "./styles.css";

const tabs = [
  { id: "today", label: "Home", icon: "\u2302" },
  { id: "patients", label: "Patients", icon: "\u25ce" },
  { id: "upload", label: "Upload", icon: "\u21e7" },
  { id: "ask", label: "Ask AI", icon: "\u2726" },
] as const;

function FollowupNotifications({ due, patients, today, loading, failed }: {
  due: Followup[]; patients: Records["patients"]; today: string; loading: boolean; failed: boolean;
}) {
  const panel = useRef<HTMLDetailsElement>(null);
  const names = new Map(patients.map(patient => [patient.id, patient.name]));
  const entries = [...due].sort((a, b) => a.date.localeCompare(b.date)).slice(0, 5);
  const close = () => { if (panel.current) panel.current.open = false; };

  return (
    <details className="followup-notifications" ref={panel} onKeyDown={event => {
      if (event.key === "Escape") {
        close();
        panel.current?.querySelector("summary")?.focus();
      }
    }}>
      <summary aria-label={`Follow-up notifications, ${due.length} due or overdue`}>
        <span aria-hidden="true">&#128276;</span> Follow-ups
        {due.length > 0 && <span className="pill" aria-hidden="true">{due.length}</span>}
      </summary>
      <section className="panel followup-notification-panel" aria-label="Follow-up notifications">
        <h2>Follow-up reminders</h2>
        {loading ? <p role="status">Loading reminders...</p>
          : failed ? <p>Reminders are unavailable.</p>
          : entries.length ? <ul>
            {entries.map(item => <li key={item.id}>
              <a href={`#patient/${item.patientId}/followups`} onClick={close}>
                <strong>{item.title}</strong>
                <small>{names.get(item.patientId)} &middot; {followupStatus(item, today)}</small>
              </a>
            </li>)}
          </ul> : <p>No due or overdue follow-ups.</p>}
        <a className="workspace-back" href="#followups" onClick={close}>View all follow-ups</a>
      </section>
    </details>
  );
}

type Editor = { kind: "patient" } | { kind: "screening"; patientId: string } | { kind: "followup"; patientId?: string };
const initials = (name: string) => name.split(/\s+/).slice(0, 2).map(word => word[0]).join("").toUpperCase();

function Dashboard({ account, onLogout, onSessionExpired }: { account: Account; onLogout: () => Promise<void>; onSessionExpired: () => void }) {
  const [records, setRecords] = useState<Records>({ patients: [], followups: [] });
  const [loadingPatients, setLoadingPatients] = useState(true);
  const [patientError, setPatientError] = useState("");
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [savingRecord, setSavingRecord] = useState(false);
  const [updatingFollowup, setUpdatingFollowup] = useState<string | null>(null);
  const [registrationError, setRegistrationError] = useState("");
  const [duplicateMatches, setDuplicateMatches] = useState<Pick<Records["patients"][number], "id" | "name" | "village" | "age">[]>([]);
  const [confirmPossibleDuplicate, setConfirmPossibleDuplicate] = useState(false);
  const [section, setSection] = useState(() => location.hash.slice(1));
  const [editor, setEditor] = useState<Editor | null>(null);
  const [testPending, setTestPending] = useState(false);
  const [search, setSearch] = useState("");
  const [screeningFilter, setScreeningFilter] = useState("all");
  const [patientPage, setPatientPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("All");
  const [notice, setNotice] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    let active = true;
    Promise.all([listPatients(), listFollowups()]).then(([patients, followups]) => {
      if (active) setRecords({ patients, followups });
    }).catch((error: Error) => {
      if (active) setPatientError(error.message);
    }).finally(() => {
      if (active) setLoadingPatients(false);
    });
    return () => { active = false; };
  }, [loadAttempt]);

  useEffect(() => {
    const refresh = () => {
      setPatientError("");
      setLoadingPatients(true);
      setLoadAttempt(attempt => attempt + 1);
    };
    window.addEventListener("sakhicare:records-changed", refresh);
    return () => window.removeEventListener("sakhicare:records-changed", refresh);
  }, []);

  function retryPatients() {
    setPatientError("");
    setLoadingPatients(true);
    setLoadAttempt(attempt => attempt + 1);
  }

  useEffect(() => {
    const navigate = () => setSection(location.hash.slice(1));
    addEventListener("hashchange", navigate);
    return () => removeEventListener("hashchange", navigate);
  }, []);

  useEffect(() => {
    const element = dialog.current;
    if (editor && element && !element.open) element.showModal();
    if (!editor && element?.open) element.close();
  }, [editor]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 3800);
    return () => clearTimeout(timer);
  }, [notice]);

  const detail = patientRoute(section);
  const selectedPatient = detail && records.patients.find(item => item.id === detail.id);
  const active = detail ? "patient" : section === "profile" || section === "followups" ? section : tabs.find(tab => tab.id === section)?.id ?? "today";
  useEffect(() => {
    if (active === "today" || active === "patients" || active === "followups") {
      window.scrollTo(0, 0);
      document.getElementById("field-page-heading")?.focus({ preventScroll: true });
    }
  }, [active]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  useEffect(() => {
    if (active !== "today" || loadingPatients || patientError) return;
    let current = true;
    setSummary(null);
    getDashboardSummary().then(result => {
      if (current) setSummary(result);
    }).catch(() => {});
    return () => { current = false; };
  }, [active, loadingPatients, patientError, records.patients]);

  const confirmedAnemiaCount = records.patients.filter(item => item.anemia_status === "confirmed").length;
  const notAssessedCount = records.patients.filter(item => !item.anemia_status).length;
  const weeklyHbChange = summary?.weekly_hb_change;

  const today = dateKey();
  const patient = editor && "patientId" in editor ? records.patients.find(item => item.id === editor.patientId) : undefined;
  const due = records.followups.filter(item => !item.done && item.date <= today);
  const sorted = [...records.followups].sort((a, b) => a.date.localeCompare(b.date));
  const statusOptions = ["All", "Overdue", "Due today", "Upcoming", "Completed"];
  const filteredFollowups = sorted.filter(item =>
    statusFilter === "All" || followupStatus(item, dateKey()) === statusFilter);

  const patientQuery = search.trim().toLowerCase();
  const matchingPatients = records.patients.filter(item => {
    const status = item.screening === null ? "none" : item.screening.hb === null ? "pending" : "measured";
    return (screeningFilter === "all" || screeningFilter === status) &&
      `${item.name} ${item.village ?? ""} ${item.block ?? ""} ${item.district ?? ""} ${item.state ?? ""} ${item.town ?? ""} ${item.ward ?? ""}`.toLowerCase().includes(patientQuery);
  });
  const pageSize = 8;
  const patientPageCount = Math.max(1, Math.ceil(matchingPatients.length / pageSize));
  const currentPatientPage = Math.min(patientPage, patientPageCount);
  const visiblePatients = matchingPatients.slice((currentPatientPage - 1) * pageSize, currentPatientPage * pageSize);

  function openEditor(next: Editor) {
    const previous = next.kind === "screening" && records.patients.find(item => item.id === next.patientId)?.screening;
    setTestPending(Boolean(previous && previous.hb === null));
    setRegistrationError("");
    setDuplicateMatches([]);
    setConfirmPossibleDuplicate(false);
    setEditor(next);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor || savingRecord) return;
    const data = new FormData(event.currentTarget);
    const value = (key: string) => String(data.get(key) ?? "").trim();
    if (editor.kind === "patient") {
      if (!value("name")) {
        setRegistrationError("Enter the patient name.");
        return;
      }
      setRegistrationError("");
      setSavingRecord(true);
      try {
        const patient = await registerPatient({
          name: value("name"),
          state: value("state") || null,
          district: value("district") || null,
          block: value("block") || null,
          village: value("village") || null,
          locality_type: value("locality_type") === "village" ? "village" : value("locality_type") === "ward" ? "ward" : null,
          town: value("town") || null,
          ward: value("ward") || null,
          age: value("age") === "" ? null : Number(value("age")),
          consent_obtained: data.has("consent_obtained"),
          confirm_possible_duplicate: confirmPossibleDuplicate,
        });
        setRecords(current => ({
          ...current,
          patients: [...current.patients, patient].sort((a, b) => a.name.localeCompare(b.name)),
        }));
        setNotice("Patient added");
      } catch (error) {
        if (error instanceof PossibleDuplicateError) {
          setDuplicateMatches(error.matches);
          setConfirmPossibleDuplicate(false);
          setRegistrationError(error.message);
        } else {
          setRegistrationError(error instanceof Error ? error.message : "Could not register the patient.");
        }
        return;
      } finally {
        setSavingRecord(false);
      }
    } else if (editor.kind === "screening") {
      setRegistrationError("");
      setSavingRecord(true);
      try {
        const screening = await saveScreening(editor.patientId, {
          date: value("date"), hb: testPending ? null : Number(value("hb")),
          method: testPending ? "" : value("method"),
          risk: (value("risk") || null) as ScreeningRisk | null,
        });
        setRecords(current => ({
          ...current,
          patients: current.patients.map(item => item.id === editor.patientId ? { ...item, screening } : item),
        }));
        setNotice(testPending ? "Hb test marked pending" : "Hb result saved");
      } catch (error) {
        setRegistrationError(error instanceof Error ? error.message : "Could not save the Hb screening.");
        return;
      } finally {
        setSavingRecord(false);
      }
    } else {
      if (!value("title")) return;
      setRegistrationError("");
      setSavingRecord(true);
      try {
        const followup = await scheduleFollowup(value("patientId"), value("title"), value("date"));
        setRecords(current => ({ ...current, followups: [...current.followups, followup] }));
        setNotice("Follow-up scheduled");
      } catch (error) {
        setRegistrationError(error instanceof Error ? error.message : "Could not schedule a follow-up.");
        return;
      } finally {
        setSavingRecord(false);
      }
    }
    setEditor(null);
  }

  async function logout() {
    setSigningOut(true);
    try {
      await onLogout();
    } catch {
      setNotice("Could not sign out. Check your connection and try again.");
      setSigningOut(false);
    }
  }

  async function toggleFollowup(item: Followup) {
    if (updatingFollowup) return;
    setUpdatingFollowup(item.id);
    try {
      const saved = await completeFollowup(item.id, !item.done);
      setRecords(current => ({
        ...current, followups: current.followups.map(entry => entry.id === saved.id ? saved : entry),
      }));
      setNotice(saved.done ? "Follow-up completed" : "Follow-up reopened");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not update the follow-up.");
    } finally {
      setUpdatingFollowup(null);
    }
  }

  const measuredHb = records.patients.flatMap(({ screening }) =>
    screening?.hb == null ? [] : [screening.hb],
  );
  const averageHb = loadingPatients || patientError || !measuredHb.length
    ? null
    : measuredHb.reduce((sum, hb) => sum + hb, 0) / measuredHb.length;

  return (
    <>
      <div className="shell field-shell">
        <aside className="sidebar">
          <a className="brand" href="#today"><span className="mark" aria-hidden="true">✦</span><span>SakhiCare <b>AI</b><small>ASHA FIELD WORKSPACE</small></span></a>
          <nav className="field-navigation" aria-label="Workspace">{tabs.map(tab => (
            <a key={tab.id} href={`#${tab.id}`} aria-current={(active === tab.id || (active === "patient" && tab.id === "patients")) ? "page" : undefined}><span aria-hidden="true">{tab.icon}</span>{tab.label}</a>
          ))}</nav>
          <div className="field-header-actions">
            <FollowupNotifications due={due} patients={records.patients} today={today}
              loading={loadingPatients} failed={Boolean(patientError)} />
            <AccountMenu account={account} signingOut={signingOut} onLogout={logout} />
          </div>
        </aside>
        <main>
          <div id="view">
            {loadingPatients && <p className="empty" role="status">Loading patients and follow-ups...</p>}
            {patientError && <div className="panel" role="alert">
              <p>{patientError}</p><button className="btn subtle" onClick={retryPatients}>Retry</button>
            </div>}
            {active === "today" && <>
              <header className="page-head field-dashboard-head">
                <div><h1 id="field-page-heading" tabIndex={-1}>Dashboard</h1><p>Anemia surveillance overview</p></div>
                <div className="actions field-dashboard-actions">
                  <a className="btn subtle" href="#ask">Ask SakhiCare</a>
                  <button className="btn" disabled={loadingPatients || Boolean(patientError)} onClick={() => openEditor({ kind: "patient" })}>+ Register patient</button>
                </div>
              </header>
              <div className="stats field-summary" aria-label="Dashboard totals">
                <a className="stat" href="#patients">
                  <span>Total Patients <b aria-hidden="true">&#9678;</b></span>
                  <strong>{loadingPatients || patientError ? "—" : records.patients.length}</strong>
                  {summary && <small>+{summary.registered_this_week} this week</small>}
                </a>
                <div className="stat">
                  <span>Anemia confirmed (recorded) <b title="Based on an ASHA-entered assessment; this is not calculated from Hb." aria-label="About this count">&#9432;</b></span>
                  <strong>{loadingPatients || patientError ? "—" : confirmedAnemiaCount}</strong>
                  {!loadingPatients && !patientError && <small>
                    ASHA-entered assessment · {notAssessedCount} not assessed
                  </small>}
                </div>
                <div className="stat">
                  <span>Avg Haemoglobin <b aria-hidden="true">&#9612;</b></span>
                  <strong>{averageHb === null ? "—" : averageHb.toFixed(1) + " g/dL"}</strong>
                  <small>{weeklyHbChange == null ? "No weekly comparison" :
                    (weeklyHbChange > 0 ? "+" : "") + weeklyHbChange.toFixed(1) + " g/dL vs last week"}</small>
                </div>
                <div className="stat">
                  <span>High risk (recorded) <b title="Risk is entered by the ASHA; SakhiCare does not calculate it from Hb." aria-label="About this risk count">&#9888;</b></span>
                  <strong>{loadingPatients || patientError || !records.patients.some(item => item.screening?.risk) ? "—" : records.patients.filter(item => item.screening?.risk === "high").length}</strong><small>{summary && summary.high_risk_without_open_referral > 0 ?
                    summary.high_risk_without_open_referral + " without open referral · ASHA-entered risk" : "ASHA-entered risk; not calculated from Hb"}</small>
                </div>
              </div>
              <section className="panel"><header className="section-head"><h2>Due today and overdue</h2></header><FollowupList items={due} patients={records.patients} empty="No follow-ups due."
                onToggle={toggleFollowup} busyId={updatingFollowup} /></section>
            </>}
            {active === "upload" && !loadingPatients && !patientError && <PatientReportUpload patients={records.patients} />}
            {active === "profile" && <ProfilePage account={account} backLabel="Back to Home" />}
            {active === "ask" && <AskGuidelines isAdmin={false} accountName={account.name} backLabel="Back to Home" onSessionExpired={onSessionExpired} />}
            {active === "patients" && <>
              <header className="page-head"><div><h1 id="field-page-heading" tabIndex={-1}>Patients</h1><p>Register patients and record measured Hb results.</p></div><button className="btn" disabled={loadingPatients || Boolean(patientError)} onClick={() => openEditor({ kind: "patient" })}>＋ Register patient</button></header>
              <section aria-label="Patient list">
                <div className="patient-directory-controls">
                  <label>Search patients
                    <input type="search" placeholder="Name or village" value={search} onChange={event => {
                      setSearch(event.target.value);
                      setPatientPage(1);
                    }} />
                  </label>
                  <label>Hb screening
                    <select value={screeningFilter} onChange={event => {
                      setScreeningFilter(event.target.value);
                      setPatientPage(1);
                    }}>
                      <option value="all">All statuses</option>
                      <option value="pending">Test pending</option>
                      <option value="measured">Result recorded</option>
                      <option value="none">No screening yet</option>
                    </select>
                  </label>
                </div>
                {!loadingPatients && !patientError && !matchingPatients.length && <p className="panel empty" role="status">
                  {records.patients.length ? "No patients match these filters." : "No patients assigned yet."}
                </p>}
                <div className="patient-card-grid">
                  {visiblePatients.map(item => (
                    <article className="panel patient-directory-card" key={item.id}>
                      <a className="patient-card-link" href={"#patient/" + item.id}>
                        <span className="avatar" aria-hidden="true">{initials(item.name)}</span>
                        <div><h2>{item.name}</h2>
                          {patientDetails(item) && <small>{patientDetails(item)}</small>}
                        </div>
                      </a>
                      <div className="patient-card-screening">
                        <span className={`pill ${item.screening?.hb === null ? "pending" : ""}`}>
                          {item.screening?.hb === null ? "Hb test pending" : item.screening ? `Hb ${item.screening.hb} g/dL` : "No screening yet"}
                        </span>
                        {item.screening && <div className="patient-screening-meta">
                          {item.screening.risk && <span className="pill patient-risk">Recorded: {item.screening.risk} risk</span>}
                          <time dateTime={item.screening.date}>{item.screening.date}</time>
                        </div>}
                      </div>
                      <div className="actions">
                        <button className="btn subtle" onClick={() => openEditor({ kind: "screening", patientId: item.id })}>Record Hb</button>
                        <button className="btn subtle" onClick={() => openEditor({ kind: "followup", patientId: item.id })}>Follow-up</button>
                      </div>
                    </article>
                  ))}
                </div>
                {patientPageCount > 1 && <nav className="asha-directory-pagination" aria-label="Patient list pages">
                  <button className="btn subtle" type="button" disabled={currentPatientPage === 1}
                    onClick={() => setPatientPage(currentPatientPage - 1)}>Previous</button>
                  <span role="status">Page {currentPatientPage} of {patientPageCount}</span>
                  <button className="btn subtle" type="button" disabled={currentPatientPage === patientPageCount}
                    onClick={() => setPatientPage(currentPatientPage + 1)}>Next</button>
                </nav>}
              </section>
            </>}
            {active === "patient" && detail && (selectedPatient ? <PatientDetail
              patient={selectedPatient} followups={sorted}
              onPatientChange={patient => setRecords(current => ({
                ...current,
                patients: current.patients.map(item => item.id === patient.id ? patient : item),
              }))} backTo={detail.fromFollowups ? "#followups" : "#patients"}
              backLabel={detail.fromFollowups ? "Back to Follow-ups" : "Back to Patients"}
              onScreen={() => openEditor({ kind: "screening", patientId: selectedPatient.id })}
              onSchedule={() => openEditor({ kind: "followup", patientId: selectedPatient.id })}
              onToggle={toggleFollowup} busyId={updatingFollowup}
            /> : !loadingPatients && !patientError && <section className="panel">
              <a className="workspace-back" href="#patients">Back to Patients</a><h1>Patient not found</h1>
            </section>)}
            {active === "followups" && <>
              <header className="page-head"><div><h1 id="field-page-heading" tabIndex={-1}>Follow-ups</h1><p>Schedule visits and track completed work.</p></div><button className="btn" disabled={loadingPatients || Boolean(patientError) || !records.patients.length} onClick={() => openEditor({ kind: "followup" })}>＋ Schedule follow-up</button></header>
              <section className="panel followup-panel">
                <header className="section-head followup-filter-header">
                  <h2>Scheduled follow-ups</h2>
                  <label>Filter by status
                    <select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}>
                      {statusOptions.map(status => <option key={status}>{status}</option>)}
                    </select>
                  </label>
                </header>
                <FollowupList items={filteredFollowups} patients={records.patients}
                  empty={statusFilter === "All" ? "No follow-ups scheduled yet." : "No follow-ups with this status."}
                  onToggle={toggleFollowup} busyId={updatingFollowup} />
              </section>
              <CarePathways patients={records.patients} />
            </>}
          </div>
        </main>
      </div>
      <dialog ref={dialog} aria-labelledby="editor-title" onClose={() => setEditor(null)}
        onCancel={event => { if (savingRecord) event.preventDefault(); }}>
        {editor && <>
          <h2 id="editor-title">{editor.kind === "patient" ? "Register patient" : editor.kind === "screening" ? "Record Hb screening" : "Schedule follow-up"}</h2>
          {patient && <small>{patient.name}</small>}
          <form onSubmit={submit}>
            {editor.kind === "patient" && <>
              <label>Patient name<input name="name" required maxLength={100} autoFocus onChange={() => { setDuplicateMatches([]); setConfirmPossibleDuplicate(false); setRegistrationError(""); }} /></label>
              <PatientLocationFields />
              <label>Age in years (optional)<input name="age" type="number" min="0" max="130" step="1" onChange={() => { setDuplicateMatches([]); setConfirmPossibleDuplicate(false); setRegistrationError(""); }} /></label>
              <label className="remember-option"><input name="consent_obtained" type="checkbox" required />
                <span>Consent confirmed<small>I explained why this record is being created and the patient agreed.</small></span>
              </label>
              {duplicateMatches.length > 0 && <section className="panel duplicate-patient-warning" aria-label="Possible duplicate patients">
                <h3>Possible matching records</h3>
                <ul>{duplicateMatches.map(match => <li key={match.id}>
                  {match.name}{match.village ? <> &middot; {match.village}</> : null}{match.age == null ? null : <> &middot; {match.age} years</>}
                  <button className="btn subtle" type="button" onClick={() => {
                    setEditor(null);
                    location.hash = `patient/${match.id}`;
                  }}>Open record</button>
                </li>)}</ul>
                <label className="remember-option"><input type="checkbox" checked={confirmPossibleDuplicate}
                  onChange={event => setConfirmPossibleDuplicate(event.target.checked)} />
                  <span>Register as a separate patient<small>Use only after confirming this is not the same person.</small></span>
                </label>
              </section>}
            </>}
            {editor.kind === "screening" && <>
              <label>Test status<select value={testPending ? "pending" : "recorded"} onChange={event => setTestPending(event.target.value === "pending")} autoFocus><option value="recorded">Measured Hb</option><option value="pending">Hb test pending</option></select></label>
              <label>Risk level
                <small>Record the risk per your approved protocol. SakhiCare does not calculate it from Hb.</small>
                <select name="risk" defaultValue={patient?.screening?.risk ?? ""}>
                  <option value="">Not assessed</option>
                  <option value="low">Low</option>
                  <option value="moderate">Moderate</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label>{testPending ? "Date recorded" : "Test date"}<input name="date" type="date" required max={today} defaultValue={patient?.screening?.date ?? today} /></label>
              {!testPending && <>
                <label>Hemoglobin (g/dL)<input name="hb" type="number" inputMode="decimal" required min="0.1" step="0.1" defaultValue={patient?.screening?.hb ?? ""} /></label>
                <label>Measurement method<input name="method" required maxLength={100} defaultValue={patient?.screening?.method ?? ""} /></label>
              </>}
            </>}
            {editor.kind === "followup" && <>
              <label>Patient<select name="patientId" required defaultValue={patient?.id ?? ""} autoFocus><option value="" disabled>Select a patient</option>{records.patients.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
              <label>Follow-up action<input name="title" required maxLength={160} placeholder="Example: Check in about Hb test" /></label>
              <label>Due date<input name="date" required type="date" defaultValue={today} /></label>
            </>}
            {registrationError && <p className="signup-error" role="alert">{registrationError}</p>}
            <div className="actions">
              <button type="button" className="btn subtle" disabled={savingRecord} onClick={() => setEditor(null)}>Cancel</button>
              <button type="submit" className="btn" disabled={savingRecord || (editor.kind === "patient" && duplicateMatches.length > 0 && !confirmPossibleDuplicate)}>{savingRecord ? "Saving..." : editor.kind === "patient" && confirmPossibleDuplicate ? "Confirm separate patient" : "Save"}</button>
            </div>
          </form>
        </>}
      </dialog>
      <div id="notice" role="status" aria-live="polite">{notice}</div>
    </>
  );
}

function App() {
  const [account, setAccount] = useState<Account | null>(null);
  const [route, setRoute] = useState(location.pathname);
  const [checkingSession, setCheckingSession] = useState(true);
  const sessionCheck = useRef<AbortController | null>(null);
  const returnToAsk = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    sessionCheck.current = controller;
    let mounted = true;
    restoreSession(controller.signal).then(user => {
      if (mounted && !controller.signal.aborted) setAccount(user);
    }).catch(() => {
      // The login screen can retry once the API is reachable.
    }).finally(() => {
      if (mounted) setCheckingSession(false);
    });
    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  function navigate(path: string, replace = false) {
    if (replace) history.replaceState(null, "", path);
    else history.pushState(null, "", path);
    setRoute(location.pathname);
  }

  useEffect(() => {
    const handleBack = () => setRoute(location.pathname);
    addEventListener("popstate", handleBack);
    return () => removeEventListener("popstate", handleBack);
  }, []);

  useEffect(() => {
    if (checkingSession) return;
    if (account?.role === "super_admin" && route !== "/onboarding") {
      history.replaceState(null, "", "/onboarding");
      setRoute("/onboarding");
    } else if (account && (route === "/login" || route === "/signup" || route === "/onboarding")) {
      history.replaceState(null, "", "/#today");
      setRoute("/");
    } else if (!account && route !== "/login" && route !== "/signup") {
      history.replaceState(null, "", "/login");
      setRoute("/login");
    }
  }, [account, checkingSession, route]);

  if (account) {
    if (account.role === "super_admin") return <OnboardingConsole onSessionExpired={() => {
      setAccount(null);
      navigate("/login", true);
    }} onLogout={async () => {
      await signOut();
      setAccount(null);
      navigate("/login", true);
    }} />;
    const Workspace = account.role === "user" ? Dashboard : AdminDashboard;
    return <Workspace key={account.id} account={account} onSessionExpired={() => {
      returnToAsk.current = true;
      setAccount(null);
      navigate("/login", true);
    }} onLogout={async () => {
      await signOut();
      setAccount(null);
      navigate("/login", true);
    }} />;
  }
  return (
    <AuthPage key={route === "/signup" ? "signup" : "login"}
      mode={route === "/signup" ? "signup" : "login"}
      navigate={navigate}
      sessionExpired={returnToAsk.current}
      onLogin={user => {
        sessionCheck.current?.abort();
        navigate(user.role === "super_admin" ? "/onboarding" : returnToAsk.current ? "/#ask" : "/#today", true);
        returnToAsk.current = false;
        setAccount(user);
      }}
    />
  );
}

createRoot(document.getElementById("root")!).render(<App />);



