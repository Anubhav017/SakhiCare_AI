import { AdminReports } from "./AdminReports";
import { useEffect, useRef, useState } from "react";
import { listManagedAshas, type Account, type ManagedAsha } from "./AuthPage";
import { AskGuidelines } from "./AskGuidelines";
import { AccountMenu, ProfilePage } from "./AccountMenu";
import { listFollowups, listPatients, patientDetails, type Followup, type Patient } from "./records";
import { FollowupList, PatientDetail, patientRoute } from "./PatientWorkspace";

type Props = { account: Account; onLogout: () => Promise<void>; onSessionExpired: () => void };

function CountCard({ count, label, description }: { count: number; label: string; description: string }) {
  const [expanded, setExpanded] = useState(false);
  const id = label === "Patients" ? "patient-count-help" : "asha-count-help";

  return (
    <div className="stat">
      <div><strong>{count}</strong><span>{label}</span></div>
      <div className="count-help" onKeyDown={event => {
        if (event.key === "Escape") setExpanded(false);
      }}>
        <button type="button" aria-label={"About the " + label + " count"}
          aria-describedby={id} aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="1.75" strokeLinecap="round" aria-hidden="true">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 11v5" />
            <circle cx="12" cy="8" r="1" fill="currentColor" stroke="none" />
          </svg>
        </button>
        <div id={id} className="count-tooltip" role="tooltip">{description}</div>
      </div>
    </div>
  );
}

const ASHA_PAGE_SIZE = 10;

export function AdminDashboard({ account, onLogout, onSessionExpired }: Props) {
  const [section, setSection] = useState(() => location.hash.slice(1));
  const detail = patientRoute(section);
  const active = detail ? "patient" : section === "ask" || section === "profile" || section === "followups" || section === "workspace" || section === "reports" ? section : "today";
  const showWorkspace = active === "workspace";
  const showDirectory = active === "today" || showWorkspace;
  const [workspaceView, setWorkspaceView] = useState<"roles" | "hierarchy">("roles");
  const [search, setSearch] = useState("");
  const [searchField, setSearchField] = useState("all");
  const [page, setPage] = useState(1);
  const [workers, setWorkers] = useState<ManagedAsha[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [followupError, setFollowupError] = useState(false);
  const [loadingFollowups, setLoadingFollowups] = useState(true);
  const [followupAttempt, setFollowupAttempt] = useState(0);
  const [followups, setFollowups] = useState<Followup[]>([]);
  const selectedPatient = patients.find(patient => patient.id === detail?.id);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [loadError, setLoadError] = useState("");
  const [logoutError, setLogoutError] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  const teamHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (showDirectory || active === "followups" || active === "patient") {
      window.scrollTo(0, 0);
      teamHeading.current?.focus({ preventScroll: true });
    }
  }, [active, section, showDirectory]);

  useEffect(() => {
    let active = true;
    Promise.all([listManagedAshas(), listPatients()]).then(([ashas, assigned]) => {
      if (active) {
        setWorkers(ashas);
        setPatients(assigned);
      }
    }).catch((error: Error) => {
      if (active) setLoadError(error.message);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [attempt]);

  useEffect(() => {
    if (active !== "followups" && active !== "patient") return;
    let current = true;
    setLoadingFollowups(true);
    setFollowupError(false);
    listFollowups().then(items => {
      if (current) setFollowups(items);
    }).catch(() => {
      if (current) setFollowupError(true);
    }).finally(() => {
      if (current) setLoadingFollowups(false);
    });
    return () => { current = false; };
  }, [active, followupAttempt]);

  useEffect(() => {
    const navigate = () => setSection(location.hash.slice(1));
    addEventListener("hashchange", navigate);
    return () => removeEventListener("hashchange", navigate);
  }, []);

  async function logout() {
    setSigningOut(true);
    setLogoutError("");
    try {
      await onLogout();
    } catch {
      setLogoutError("Could not sign out. Check your connection and try again.");
      setSigningOut(false);
    }
  }

  function retry() {
    setLoadError("");
    setLoading(true);
    setAttempt(value => value + 1);
  }

  const patientsByWorker = new Map<number, Patient[]>();
  for (const patient of patients) {
    const assigned = patientsByWorker.get(patient.ashaUserId);
    if (assigned) assigned.push(patient);
    else patientsByWorker.set(patient.ashaUserId, [patient]);
  }
  const query = search.trim().toLowerCase();
  const matchingWorkers = workers.filter(worker => {
    const nameMatches = worker.name.toLowerCase().includes(query);
    const usernameMatches = worker.username.toLowerCase().includes(query);
    if (searchField === "name") return nameMatches;
    if (searchField === "username") return usernameMatches;
    return nameMatches || usernameMatches;
  });
  const pageCount = Math.max(1, Math.ceil(matchingWorkers.length / ASHA_PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const start = (currentPage - 1) * ASHA_PAGE_SIZE;
  const visibleWorkers = matchingWorkers.slice(start, start + ASHA_PAGE_SIZE);

  return (
    <div className="shell admin-shell">
      <aside className="sidebar">
        <a className="brand" href="#today">
          <span className="mark" aria-hidden="true">&#10022;</span>
          <span>SakhiCare <b>AI</b><small>ADMIN WORKSPACE</small></span>
        </a>
        <nav aria-label="Admin workspace">
          <a href="#today" aria-current={active === "today" ? "page" : undefined}>
            <span aria-hidden="true">&#8962;</span> ASHA
          </a>
          <a href="#workspace" aria-current={showWorkspace ? "page" : undefined}>
            <span aria-hidden="true">&#9638;</span> Workspace
          </a>
          <a href="#reports" aria-current={active === "reports" ? "page" : undefined}>
            <span aria-hidden="true">&#9636;</span> Reports
          </a>
          <a href="#ask" aria-current={active === "ask" ? "page" : undefined}>
            <span aria-hidden="true">&#10022;</span> Ask
          </a>
          <a href="#followups" aria-current={active === "followups" ? "page" : undefined}>
            <span aria-hidden="true">&#10003;</span> Follow-ups
          </a>
        </nav>
        <AccountMenu account={account} signingOut={signingOut} onLogout={logout} />
      </aside>
      <main>
        <header className="topbar"><span>Admin workspace</span><span className="demo">Super Admin</span></header>
        <div id="view" className="admin-view">
          {logoutError && <p className="signup-error" role="alert">{logoutError}</p>}
          {active === "reports" && !loading && !loadError && <AdminReports workers={workers} patients={patients} />}
          {active === "profile" && <ProfilePage account={account} backLabel="Back to ASHA" />}
          {active === "ask" && <AskGuidelines isAdmin={true} accountName={account.name} backLabel="Back to ASHA" onSessionExpired={onSessionExpired} />}
          {active === "followups" && <header className="page-head">
            <div><h1 ref={teamHeading} tabIndex={-1}>Follow-ups</h1><p>Scheduled visits for your ASHA team.</p></div>
          </header>}
          {showDirectory && <header className="page-head">
            <div><h1 ref={teamHeading} tabIndex={-1}>{showWorkspace ? "Workspace" : "ASHA"}</h1>{!showWorkspace && <p>{account.name} &middot; Super Admin</p>}</div>
          </header>}
          {(showDirectory || active === "followups" || active === "patient" || active === "reports") && <>
            {loading && <p className="empty" role="status">Loading team and patients...</p>}
            {loadError && <div className="panel" role="alert">
              <p>Could not load the ASHA team and patients.</p>
              <button className="btn subtle" onClick={retry}>Retry</button>
            </div>}
          </>}
          {active === "followups" && loadingFollowups && <p className="empty" role="status">Loading follow-ups...</p>}
          {active === "followups" && followupError && <div className="panel" role="alert">
            <p>Could not load follow-ups.</p>
            <button className="btn subtle" onClick={() => setFollowupAttempt(value => value + 1)}>Retry</button>
          </div>}
          {active === "followups" && !loading && !loadError && !loadingFollowups && !followupError && <>
            <section className="panel followup-panel">
              <header className="section-head"><h2>Open</h2></header>
              <FollowupList items={followups.filter(item => !item.done)} patients={patients} empty="No open follow-ups." />
            </section>
            <section className="panel followup-panel">
              <header className="section-head"><h2>Completed</h2></header>
              <FollowupList items={followups.filter(item => item.done)} patients={patients} empty="No completed follow-ups." />
            </section>
          </>}
          {detail && !loading && !loadError && (selectedPatient
            ? <PatientDetail patient={selectedPatient} followups={followups}
                followupStatus={loadingFollowups ? <p role="status">Loading follow-ups...</p> : followupError
                  ? <div role="alert"><p>Could not load follow-ups.</p>
                    <button className="btn subtle" onClick={() => setFollowupAttempt(value => value + 1)}>Retry</button>
                  </div> : undefined}
                backTo={detail.fromFollowups ? "#followups" : "#today"}
                backLabel={detail.fromFollowups ? "Back to follow-ups" : "Back to ASHA"} />
            : <p className="empty">Patient unavailable. <a href="#today">Back to ASHA</a></p>)}
          {showWorkspace && !loading && !loadError && <>
            <div className="asha-view-switch" role="group" aria-label="Workspace view">
              <button className="btn subtle" type="button" aria-pressed={workspaceView === "roles"}
                onClick={() => setWorkspaceView("roles")}>Roles</button>
              <button className="btn subtle" type="button" aria-pressed={workspaceView === "hierarchy"}
                onClick={() => setWorkspaceView("hierarchy")}>Hierarchy</button>
            </div>
            {workspaceView === "roles" ? <section className="panel workspace-roles" aria-label="Workspace roles">
              <table>
                <thead><tr><th scope="col">Role</th><th scope="col">People in this workspace</th></tr></thead>
                <tbody>
                  <tr><th scope="row">Super Admin</th><td>1</td></tr>
                  <tr><th scope="row">ASHA worker</th><td>{workers.length}</td></tr>
                </tbody>
              </table>
            </section> : <section className="panel asha-hierarchy" aria-label="Role hierarchy">
              <h2>Role hierarchy</h2>
              <ul>
                <li><strong>Super Admin</strong><small>{account.name}</small>
                  <ul><li><strong>ASHA workers</strong><small>{workers.length} reporting to this Super Admin</small></li></ul>
                </li>
              </ul>
            </section>}
          </>}
          {active === "today" && <>
            {!loading && !loadError && <>
              <div className="stats" aria-label="Team totals">
                <CountCard count={workers.length} label="ASHA workers" description="Workers assigned to your account." />
                <CountCard count={patients.length} label="Patients" description="Patients assigned to the ASHA workers you manage." />
              </div>
              <div className="asha-directory-controls">
                <label>Search ASHA workers
                  <input type="search" value={search} placeholder="Name or username" onChange={event => {
                    setSearch(event.target.value);
                    setPage(1);
                  }} />
                </label>
                <label>Search by
                  <select value={searchField} onChange={event => {
                    setSearchField(event.target.value);
                    setPage(1);
                  }}>
                    <option value="all">Name or username</option>
                    <option value="name">Name</option>
                    <option value="username">Username</option>
                  </select>
                </label>
              </div>
              <p className="asha-directory-summary" role="status">
                {matchingWorkers.length
                  ? "Showing " + (start + 1) + " to " + (start + visibleWorkers.length) + " of " + matchingWorkers.length + " ASHA workers"
                  : workers.length ? "No ASHA workers match your search and filter." : "No ASHA workers assigned yet."}
              </p>
              <div className="admin-team-list">
                {visibleWorkers.map(worker => {
                  const assigned = patientsByWorker.get(worker.id) ?? [];
                  return (
                    <section className="panel admin-worker" key={worker.id}>
                      <header className="section-head">
                        <div><h2>{worker.name}</h2><small>{worker.username}</small></div>
                        <span className="pill">{assigned.length} {assigned.length === 1 ? "patient" : "patients"}</span>
                      </header>
                      {assigned.length === 0 && <p className="empty">No patients assigned.</p>}
                      {assigned.map(patient => (
                        <div className="row" key={patient.id}>
                          <div><a className="patient-link" href={"#patient/" + patient.id}>{patient.name}</a><small>{patientDetails(patient)}</small></div>
                        </div>
                      ))}
                    </section>
                  );
                })}
              </div>
              {pageCount > 1 && <nav className="asha-directory-pagination" aria-label="ASHA directory pages">
                <button className="btn subtle" type="button" disabled={currentPage === 1}
                  onClick={() => setPage(currentPage - 1)}>Previous</button>
                <span>Page {currentPage} of {pageCount}</span>
                <button className="btn subtle" type="button" disabled={currentPage === pageCount}
                  onClick={() => setPage(currentPage + 1)}>Next</button>
              </nav>}
            </>}
          </>}
        </div>
        <footer className="admin-footer">
          <button className="btn subtle" type="button" onClick={() => window.scrollTo(0, 0)}>Back to top</button>
        </footer>
      </main>
    </div>
  );
}
