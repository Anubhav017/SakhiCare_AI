import { useEffect, useState, type FormEvent } from "react";
import { createOrganizationAdmin, listOrganizationAdmins, type OnboardedAdmin } from "./AuthPage";

export function OnboardingConsole({ onLogout, onSessionExpired }: {
  onLogout: () => Promise<void>;
  onSessionExpired: () => void;
}) {
  const [admins, setAdmins] = useState<OnboardedAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    listOrganizationAdmins().then(rows => {
      if (active) setAdmins(rows);
    }).catch(cause => {
      if (active) setError(cause instanceof Error ? cause.message : "Could not load client Admin accounts.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await createOrganizationAdmin({
        name: String(values.get("name") ?? "").trim(),
        username: String(values.get("username") ?? "").trim(),
        email: String(values.get("email") ?? "").trim(),
        password: String(values.get("password") ?? ""),
      });
      setAdmins(current => [...current, created].sort((a, b) => a.name.localeCompare(b.name)));
      form.reset();
      setNotice(`${created.name} is set up as a client Admin. They can now sign in and manage their own workspace.`);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Could not create the client Admin account.";
      if (message.includes("sign in")) onSessionExpired();
      else setError(message);
    } finally {
      setBusy(false);
    }
  }

  return <main className="onboarding-shell">
    <header className="onboarding-header">
      <a className="brand" href="/onboarding"><span className="mark" aria-hidden="true">✦</span>
        <span>SakhiCare <b>AI</b><small>IN-HOUSE ONBOARDING</small></span></a>
      <button className="btn subtle" type="button" onClick={() => void onLogout()}>Sign out</button>
    </header>
    <div className="onboarding-content">
      <header className="page-head"><div><h1>Client Admin onboarding</h1>
        <p>Create a separate Admin workspace for each client.</p></div></header>
      <section className="panel onboarding-explainer">
        <strong>SakhiCare Super Admin</strong>
        <p>Each Admin you create becomes the root of a separate reporting hierarchy. They can assign User, Manager, and Executive roles in their Workspace. Patient records stay scoped to that hierarchy.</p>
      </section>
      <section className="panel onboarding-form-panel">
        <h2>Set up a client Admin</h2>
        <form onSubmit={submit}>
          <label>Full name<input name="name" autoComplete="name" required maxLength={100} /></label>
          <label>Username<input name="username" autoComplete="username" required minLength={3} maxLength={64} /></label>
          <label>Email<input name="email" type="email" autoComplete="email" required maxLength={254} /></label>
          <label>Temporary password<input name="password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} /></label>
          <p className="onboarding-note">Give the password to the client Admin through a secure channel. SakhiCare does not email credentials.</p>
          {error && <p className="signup-error" role="alert">{error}</p>}
          {notice && <p className="onboarding-success" role="status">{notice}</p>}
          <button className="btn" type="submit" disabled={busy}>{busy ? "Creating Admin…" : "Create client Admin"}</button>
        </form>
      </section>
      <section className="panel onboarding-admin-list" aria-labelledby="client-admins-heading">
        <header className="section-head"><h2 id="client-admins-heading">Client Admin accounts</h2><span>{admins.length}</span></header>
        {loading ? <p role="status">Loading Admin accounts…</p> : admins.length ? <div className="workspace-people-table-wrap">
          <table><thead><tr><th scope="col">Name</th><th scope="col">Email / username</th><th scope="col">Role</th></tr></thead>
            <tbody>{admins.map(admin => <tr key={admin.id}><td><strong>{admin.name}</strong></td>
              <td>{admin.email}<small>{admin.username}</small></td><td><span className="pill">Admin</span></td></tr>)}</tbody>
          </table>
        </div> : <p>No client Admin accounts have been onboarded yet.</p>}
      </section>
    </div>
  </main>;
}
