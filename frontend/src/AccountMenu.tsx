import { useEffect, useRef } from "react";
import type { Account } from "./AuthPage";

export function accountInitials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join("").toUpperCase();
}

export function accountRole(account: Account) {
  return account.role === "super_admin" ? "Super Admin" : "ASHA worker";
}

export function AccountMenu({ account, signingOut, onLogout }: {
  account: Account;
  signingOut: boolean;
  onLogout: () => void;
}) {
  const menu = useRef<HTMLDetailsElement>(null);
  const summary = useRef<HTMLElement>(null);

  useEffect(() => {
    const closeOutside = (event: PointerEvent) => {
      if (menu.current?.open && event.target instanceof Node && !menu.current.contains(event.target)) {
        menu.current.open = false;
      }
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && menu.current?.open) {
        menu.current.open = false;
        summary.current?.focus();
      }
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", escape);
    };
  }, []);

  return (
    <details className="account-menu" ref={menu}>
      <summary ref={summary} aria-label={`Account menu for ${account.name}`}>
        <span className="avatar" aria-hidden="true">{accountInitials(account.name)}</span>
        <span className="account-label"><strong>{account.name}</strong><small>{accountRole(account)}</small></span>
        <span className="account-options" aria-hidden="true">...</span>
      </summary>
      <div className="account-popover">
        <a href="#profile" onClick={() => { if (menu.current) menu.current.open = false; }}>Profile</a>
        <button type="button" onClick={onLogout} disabled={signingOut}>
          {signingOut ? "Signing out..." : "Sign out"}
        </button>
      </div>
    </details>
  );
}

export function ProfilePage({ account, backLabel }: { account: Account; backLabel: string }) {
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    window.scrollTo(0, 0);
    heading.current?.focus({ preventScroll: true });
  }, []);

  return (
    <section className="profile-page" aria-labelledby="profile-title">
      <a className="workspace-back" href="#today">{backLabel}</a>
      <header className="page-head">
        <div><h1 id="profile-title" ref={heading} tabIndex={-1}>Profile</h1></div>
      </header>
      <div className="panel profile-card">
        <header>
          <span className="avatar" aria-hidden="true">{accountInitials(account.name)}</span>
          <div><h2>{account.name}</h2><p>{accountRole(account)}</p></div>
        </header>
        <dl>
          <div><dt>Full name</dt><dd>{account.name}</dd></div>
          <div><dt>Username</dt><dd>{account.username}</dd></div>
          <div><dt>Email</dt><dd>{account.email}</dd></div>
          <div><dt>Role</dt><dd>{accountRole(account)}</dd></div>
        </dl>
      </div>
    </section>
  );
}
