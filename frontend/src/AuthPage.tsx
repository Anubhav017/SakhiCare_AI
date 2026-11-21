import { useState, type FormEvent } from "react";

export type Account = {
  id: number; name: string; username: string; email: string;
  role: "asha" | "super_admin";
};

export type ManagedAsha = Pick<Account, "id" | "name" | "username">;

export function listManagedAshas(): Promise<ManagedAsha[]> {
  return request("/user/managed-ashas", { cache: "no-store" }, "Could not load your ASHA workers.");
}
type Mode = "login" | "signup";

async function request<T>(path: string, options: RequestInit, fallback: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/backend-api${path}`, { ...options, signal: AbortSignal.timeout(12000) });
  } catch {
    throw new Error("Could not reach SakhiCare. Check that the API is running and try again.");
  }
  const data = await response.json().catch(() => null);
  if (response.ok && data !== null) return data as T;
  if (response.status === 400 && typeof data?.detail === "string") throw new Error(data.detail);
  if (response.status === 401) throw new Error("Incorrect username or password.");
  throw new Error(fallback);
}

export async function restoreSession(signal: AbortSignal): Promise<Account | null> {
  const response = await fetch("/backend-api/user/session", {
    signal: AbortSignal.any([signal, AbortSignal.timeout(5000)]),
  });
  return response.ok ? await response.json() as Account : null;
}

export async function signOut(): Promise<void> {
  const response = await fetch("/backend-api/user/session", {
    method: "DELETE",
    headers: { "X-SakhiCare-Session": "1" },
    signal: AbortSignal.timeout(5000),
  });
  if (response.status !== 204) throw new Error("Sign-out failed");
}

function PasswordField({ name, label, signup }: { name: string; label: string; signup: boolean }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="password-field">
      <label htmlFor={name}>{label}</label>
      <div className="password-input">
        <input id={name} name={name} type={visible ? "text" : "password"} required
          autoComplete={signup ? "new-password" : "current-password"} minLength={signup ? 8 : undefined} />
        <button type="button" className="password-toggle" onClick={() => setVisible(!visible)}
          aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          aria-controls={name}>
          <svg viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor"
            strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z" />
            <circle cx="12" cy="12" r="2.7" />
            {visible && <path d="m4 4 16 16" />}
          </svg>
        </button>
      </div>
    </div>
  );
}

function post(body: object): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" }, body: JSON.stringify(body) };
}

type Props = { mode: Mode; sessionExpired?: boolean; navigate: (path: string) => void; onLogin: (account: Account) => void };

export function AuthPage({ mode, navigate, onLogin, sessionExpired }: Props) {
  const [role, setRole] = useState<Account["role"]>("asha");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [createdUsername, setCreatedUsername] = useState("");
  const signup = mode === "signup";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;

    setError("");
    const data = new FormData(event.currentTarget);
    const username = String(data.get("username") ?? "").trim();
    const password = String(data.get("password") ?? "");
    const name = String(data.get("name") ?? "").trim();
    const email = String(data.get("email") ?? "").trim();
    if (!username || (signup && !name)) {
      setError(signup ? "Enter your full name and a username." : "Enter your username.");
      return;
    }
    if (signup && password !== data.get("confirm")) {
      setError("The passwords do not match.");
      return;
    }

    setSaving(true);
    try {
      if (signup) {
        await request<Omit<Account, "role">>("/user/register", post({ name, username, email, password }), "Could not create your account. Please try again.");
        setCreatedUsername(username);
      } else {
        const account = await request<Account>("/user/session", post({
          username, password, role, remember: data.has("remember"),
        }), "Could not sign in. Please try again.");
        onLogin(account);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className={signup ? "signup" : "signup mobile-signin"}>
      <div className="brand"><span className="mark" aria-hidden="true">✦</span><span>SakhiCare <b>AI</b><small className="auth-workspace-label">ASHA FIELD WORKSPACE</small><small className="mobile-signin-subtitle">Anemia care for ASHA workers</small></span></div>
      <section className="panel signup-card">
        {createdUsername ? (
          <>
            <h1>Account created</h1>
            <p role="status">Your SakhiCare username is <strong>{createdUsername}</strong>.</p>
            <a className="btn" href="/login" onClick={event => { event.preventDefault(); navigate("/login"); }}>Go to sign in</a>
          </>
        ) : (
          <>
            <h1 className="auth-form-heading">{signup ? "ASHA worker sign-up" : "Sign in to SakhiCare"}</h1>
            {!signup && sessionExpired && <p role="status">Your session expired. Sign in to return to Ask.</p>}
            <form onSubmit={submit}>
              {!signup && (
                <fieldset className="login-role" disabled={saving}>
                  <legend>Role</legend>
                  <div className="login-role-options">
                    <label><input type="radio" name="role" value="asha" checked={role === "asha"} onChange={() => { setRole("asha"); setError(""); }} /><span>ASHA Worker</span></label>
                    <label><input type="radio" name="role" value="super_admin" checked={role === "super_admin"} onChange={() => { setRole("super_admin"); setError(""); }} /><span>Admin</span></label>
                  </div>
                </fieldset>
              )}
              {signup && <>
                <label>Full name<input name="name" autoComplete="name" required maxLength={100} /></label>
                <label>Email<input name="email" type="email" autoComplete="email" required maxLength={254} /></label>
              </>}
              <label>Username<input name="username" autoComplete="username" required maxLength={64} /></label>
              <PasswordField name="password" label="Password" signup={signup} />
              {signup ? <PasswordField name="confirm" label="Confirm password" signup /> : (
                <label className="remember-option">
                  <input name="remember" type="checkbox" />
                  <span>Remember me<small>Use only on a private device.</small></span>
                </label>
              )}
              {error && <p className="signup-error" role="alert">{error}</p>}
              <button className="btn" type="submit" disabled={saving}>{saving ? (signup ? "Creating account…" : "Signing in…") : (signup ? "Create account" : "Sign in")}</button>
            </form>
            <a className="back-link" href={signup ? "/login" : "/signup"} onClick={event => { event.preventDefault(); navigate(signup ? "/login" : "/signup"); }}>
              {signup ? "Already have an account? Sign in" : "New ASHA worker? Create an account"}
            </a>
          </>
        )}
      </section>
    </main>
  );
}
