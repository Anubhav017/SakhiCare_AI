import { AdminReports } from "./AdminReports";
import { useEffect, useRef, useState } from "react";
import { listManagedAshas, listManagedHierarchy, updateManagedMember, type Account, type ManagedAsha, type ManagedMember } from "./AuthPage";
import { AskGuidelines } from "./AskGuidelines";
import { CarePathways } from "./CarePathways";
import { AccountMenu, accountRole, ProfilePage } from "./AccountMenu";
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

function HierarchyBranch({ person, members }: { person: Pick<Account, "id" | "name" | "role">; members: ManagedMember[] }) {
  const children = members.filter(member => member.reports_to_id === person.id);
  const label = person.role === "user" ? "ASHA worker · User" : person.role[0].toUpperCase() + person.role.slice(1);
  return <li><div className="hierarchy-person"><strong>{label}</strong><small>{person.name}</small>
    <span>{children.length} direct {children.length === 1 ? "report" : "reports"}</span></div>
    {children.length > 0 && <ul>{children.map(child => <HierarchyBranch key={child.id} person={child} members={members} />)}</ul>}
  </li>;
}

export function AdminDashboard({ account, onLogout, onSessionExpired }: Props) {
  const [section, setSection] = useState(() => location.hash.slice(1));
  const detail = patientRoute(section);
  const active = detail ? "patient" : section === "ask" || section === "profile" || section === "followups" || section === "reports" || (section === "workspace" && account.role === "admin") ? section : "today";
  const showWorkspace = active === "workspace";
  const showDirectory = active === "today" || showWorkspace;
  const [workspaceView, setWorkspaceView] = useState<"roles" | "people">("roles");
  const [roleView, setRoleView] = useState<"table" | "hierarchy">("hierarchy");
  const [peopleSearch, setPeopleSearch] = useState("");
  const [editingPerson, setEditingPerson] = useState<number | null>(null);
  const [draftRole, setDraftRole] = useState<Exclude<Account["role"], "admin" | "super_admin">>("user");
  const [draftManager, setDraftManager] = useState("");
  const [savingAccess, setSavingAccess] = useState(false);
  const [accessError, setAccessError] = useState("");
  const [search, setSearch] = useState("");
  const [searchField, setSearchField] = useState("all");
  const [page, setPage] = useState(1);
  const [workers, setWorkers] = useState<ManagedAsha[]>([]);
  const [members, setMembers] = useState<ManagedMember[]>([]);
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
    Promise.all([listManagedAshas(), listPatients(), account.role === "admin" ? listManagedHierarchy() : Promise.resolve([])]).then(([ashas, assigned, hierarchy]) => {
      if (active) {
        setWorkers(ashas);
        setPatients(assigned);
        setMembers(hierarchy);
      }
    }).catch((error: Error) => {
      if (active) setLoadError(error.message);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [account.role, attempt]);

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
  const people = [{ ...account, reports_to_id: null as number | null }, ...members];
  const filteredPeople = people.filter(person =>
    [person.name, person.email, person.username].some(value => value.toLowerCase().includes(peopleSearch.trim().toLowerCase()))
  );
  const parentRoleFor: Record<Exclude<Account["role"], "admin" | "super_admin">, Account["role"]> = {
    executive: "admin", manager: "executive", user: "manager",
  };

  async function saveAccess(personId: number) {
    if (!draftManager) {
      setAccessError("Choose a reporting manager for this role.");
      return;
    }
    setSavingAccess(true);
    setAccessError("");
    try {
      await updateManagedMember(personId, draftRole, Number(draftManager));
      setMembers(await listManagedHierarchy());
      setEditingPerson(null);
    } catch (error) {
      setAccessError(error instanceof Error ? error.message : "Could not update workspace access.");
    } finally {
      setSavingAccess(false);
    }
  }

  return (
    <div className="shell admin-shell">
      <aside className="sidebar">
        <a className="brand" href="#today">
          <span className="mark" aria-hidden="true">&#10022;</span>
          <span>SakhiCare <b>AI</b><small>{accountRole(account).toUpperCase()} WORKSPACE</small></span>
        </a>
        <nav aria-label={`${accountRole(account)} workspace`}>
          <a href="#today" aria-current={active === "today" ? "page" : undefined}>
            <span aria-hidden="true">&#8962;</span> ASHA
          </a>
          {account.role === "admin" && <a href="#workspace" aria-current={showWorkspace ? "page" : undefined}>
            <span aria-hidden="true">&#9638;</span> Workspace
          </a>}
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
        <header className="topbar"><span>{accountRole(account)} workspace</span><span className="demo">{accountRole(account)}</span></header>
        <div id="view" className="admin-view">
          {logoutError && <p className="signup-error" role="alert">{logoutError}</p>}
          {active === "reports" && !loading && !loadError && <AdminReports workers={workers} patients={patients} />}
          {active === "profile" && <ProfilePage account={account} backLabel={`Back to ${accountRole(account)}`} />}
          {active === "ask" && <AskGuidelines isAdmin={true} accountName={account.name} backLabel={`Back to ${accountRole(account)}`} onSessionExpired={onSessionExpired} />}
          {active === "followups" && <header className="page-head">
            <div><h1 ref={teamHeading} tabIndex={-1}>Follow-ups</h1><p>Scheduled visits for your ASHA team.</p></div>
          </header>}
          {showDirectory && <header className="page-head">
            <div><h1 ref={teamHeading} tabIndex={-1}>{showWorkspace ? "Workspace" : "ASHA"}</h1>{!showWorkspace && <p>{account.name} &middot; {accountRole(account)}</p>}</div>
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
            <CarePathways patients={patients} readOnly />
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
                backLabel={detail.fromFollowups ? "Back to follow-ups" : `Back to ${accountRole(account)}`} pathwayReadOnly />
            : <p className="empty">Patient unavailable. <a href="#today">Back to {accountRole(account)}</a></p>)}
          {showWorkspace && !loading && !loadError && <>
            <div className="workspace-tabs" role="tablist" aria-label="Workspace access control">
              <button type="button" role="tab" aria-selected={workspaceView === "roles"} onClick={() => setWorkspaceView("roles")}>Roles</button>
              <button type="button" role="tab" aria-selected={workspaceView === "people"} onClick={() => setWorkspaceView("people")}>People</button>
            </div>
            {workspaceView === "roles" ? <>
              <div className="workspace-toolbar">
                <div className="asha-view-switch" role="group" aria-label="Role display">
                  <button className="btn subtle" type="button" aria-pressed={roleView === "table"}
                    onClick={() => setRoleView("table")}>Table</button>
                  <button className="btn subtle" type="button" aria-pressed={roleView === "hierarchy"}
                    onClick={() => setRoleView("hierarchy")}>Hierarchy</button>
                </div>
              </div>
              {roleView === "table" ? <section className="panel workspace-roles" aria-label="Workspace roles">
                <table>
                  <thead><tr><th scope="col">Role</th><th scope="col">Direct reports to</th><th scope="col">People</th><th scope="col">Ask access</th></tr></thead>
                  <tbody>
                    {(["admin", "executive", "manager", "user"] as const).map(role => <tr key={role}>
                      <th scope="row">{role === "user" ? "ASHA worker · User" : role[0].toUpperCase() + role.slice(1)}</th>
                      <td>{{ admin: "—", executive: "Admin", manager: "Executive", user: "Manager" }[role]}</td>
                      <td>{(account.role === role ? 1 : 0) + members.filter(member => member.role === role).length}</td>
                      <td>{role === "user" ? "Read assigned records · Ask Write with review" : "Read descendant records · Ask read-only"}</td>
                    </tr>)}
                  </tbody>
                </table>
              </section> : <section className="panel asha-hierarchy" aria-label="Role hierarchy">
                <p className="hierarchy-caption">REPORTING HIERARCHY · ACCESS FOLLOWS THE ROLE AND REPORTING LINE</p>
                <ul><HierarchyBranch person={account} members={members} /></ul>
                {members.some(member => member.reports_to_id === null) && <>
                  <h3 className="unassigned-heading">Not assigned to a reporting line yet</h3>
                  <ul>{members.filter(member => member.reports_to_id === null).map(person =>
                    <HierarchyBranch key={person.id} person={person} members={members} />
                  )}</ul>
                </>}
              </section>}
            </> : <section className="panel workspace-people" aria-label="People in this workspace">
              <header className="workspace-people-toolbar">
                <label className="workspace-search">Search people
                  <input type="search" value={peopleSearch} placeholder="Name, username, or email"
                    onChange={event => setPeopleSearch(event.target.value)} />
                </label>
                <span>{filteredPeople.length} of {people.length} people</span>
              </header>
              {accessError && <p className="signup-error" role="alert">{accessError}</p>}
              <div className="workspace-people-table-wrap"><table>
                <thead><tr><th scope="col">Name</th><th scope="col">Email / username</th><th scope="col">Role</th><th scope="col">Reports to</th><th scope="col">Ask access</th>{account.role === "admin" && <th scope="col">Actions</th>}</tr></thead>
                <tbody>{filteredPeople.map(person => {
                  const isSystemAdmin = person.role === "admin";
                  const currentManager = people.find(candidate => candidate.id === person.reports_to_id);
                  const childIds = new Set<number>();
                  let frontier = [person.id];
                  while (frontier.length) {
                    const next = members.filter(member => frontier.includes(member.reports_to_id ?? -1)).map(member => member.id);
                    next.forEach(id => childIds.add(id));
                    frontier = next;
                  }
                  const parentOptions = people.filter(candidate => candidate.id !== person.id && !childIds.has(candidate.id)
                    && candidate.role === parentRoleFor[draftRole]);
                  const draftManagerValid = parentOptions.some(option => option.id === Number(draftManager));
                  return <tr key={person.id}>
                    <td><strong>{person.name}</strong></td>
                    <td>{person.email}<small>{person.username}</small></td>
                    <td>{editingPerson === person.id ? <select aria-label={`Role for ${person.name}`} value={draftRole}
                      onChange={event => {
                        const nextRole = event.target.value as Exclude<Account["role"], "admin" | "super_admin">;
                        setDraftRole(nextRole);
                        const oldParent = people.find(candidate => candidate.id === Number(draftManager));
                        if (oldParent?.role !== parentRoleFor[nextRole]) setDraftManager("");
                      }}><option value="user">User · ASHA</option><option value="manager">Manager</option><option value="executive">Executive</option></select>
                      : person.role === "user" ? "User · ASHA" : person.role[0].toUpperCase() + person.role.slice(1)}</td>
                    <td>{editingPerson === person.id ? <select aria-label={`Reporting manager for ${person.name}`} value={draftManager}
                      onChange={event => setDraftManager(event.target.value)}><option value="">Select manager</option>
                      {parentOptions.map(option => <option key={option.id} value={option.id}>{option.name} · {option.role}</option>)}</select>
                      : currentManager?.name ?? (isSystemAdmin ? "Organization root" : "Not assigned")}</td>
                    <td><span className={`pill ${((editingPerson === person.id ? draftRole : person.role) === "user") ? "done" : ""}`}>
                      {(editingPerson === person.id ? draftRole : person.role) === "user" ? "Read + Ask Write" : "Read-only"}
                    </span></td>
                    {account.role === "admin" && <td>{isSystemAdmin ? <span>System admin</span> : editingPerson === person.id ? <div className="workspace-row-actions">
                      <button type="button" className="btn subtle" disabled={savingAccess} onClick={() => { setEditingPerson(null); setAccessError(""); }}>Cancel</button>
                      <button type="button" className="btn" disabled={savingAccess || !draftManagerValid} onClick={() => void saveAccess(person.id)}>{savingAccess ? "Saving…" : "Save"}</button>
                    </div> : <button type="button" className="btn subtle" onClick={() => {
                      setEditingPerson(person.id);
                      setDraftRole(person.role === "admin" || person.role === "super_admin" ? "user" : person.role);
                      setDraftManager(person.reports_to_id == null ? "" : String(person.reports_to_id));
                      setAccessError("");
                    }}>Manage access</button>}</td>}
                  </tr>;
                })}</tbody>
              </table></div>
              <p className="workspace-access-note">Ask Write is included with the ASHA User role and requires review before saving. Manager, Executive, and Admin roles are read-only for patient records.</p>
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
