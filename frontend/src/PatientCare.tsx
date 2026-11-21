import { useEffect, useState, type FormEvent } from "react";
import {
  createReferral, dateKey, formatDate, listReferrals, saveAnemiaAssessment, updateReferral,
  type AnemiaStatus, type Patient, type Referral,
} from "./records";

const assessmentLabels = {
  confirmed: "Anemia confirmed",
  not_anemic: "No anemia recorded",
};

const referralLabels = { referred: "Referred", attended: "Attended", closed: "Closed" };

export function PatientCare({ patient, onPatientChange }: {
  patient: Patient;
  onPatientChange?: (patient: Patient) => void;
}) {
  const [referrals, setReferrals] = useState<Referral[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [closing, setClosing] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    setLoadError(false);
    listReferrals(patient.id).then(rows => {
      if (active) setReferrals(rows);
    }).catch(() => {
      if (active) setLoadError(true);
    });
    return () => { active = false; };
  }, [patient.id, attempt]);

  async function save(action: () => Promise<void>, message: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(message);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save changes.");
    } finally {
      setBusy(false);
    }
  }

  function assess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const status = new FormData(event.currentTarget).get("assessment");
    if (!onPatientChange) return;
    void save(async () => {
      onPatientChange(await saveAnemiaAssessment(patient.id, (status || null) as AnemiaStatus));
    }, "Assessment saved.");
  }

  function refer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const facility = String(fields.get("facility") ?? "").trim();
    if (!facility) {
      setError("Enter the referral facility.");
      return;
    }
    void save(async () => {
      const referral = await createReferral(patient.id, facility, String(fields.get("date") ?? ""));
      setReferrals(rows => [...(rows ?? []), referral].sort((a, b) =>
        b.referred_on.localeCompare(a.referred_on) || b.id - a.id,
      ));
      form.reset();
    }, "Referral saved.");
  }

  function change(referral: Referral, status: Referral["status"], outcome: string | null) {
    void save(async () => {
      const updated = await updateReferral(patient.id, referral.id, status, outcome);
      setReferrals(rows => rows?.map(row => row.id === updated.id ? updated : row) ?? []);
      setClosing(null);
    }, status === "closed" ? "Outcome saved." : "Referral marked attended.");
  }

  return <>
    <section className="panel followup-panel" aria-labelledby="anemia-assessment-title">
      <h2 id="anemia-assessment-title">Anemia assessment</h2>
      <p>{patient.anemia_status ? assessmentLabels[patient.anemia_status] : "Not assessed"}</p>
      {onPatientChange && <form onSubmit={assess}>
        <label>Recorded assessment
          <select name="assessment" defaultValue={patient.anemia_status ?? ""} disabled={busy}>
            <option value="">Not assessed</option>
            <option value="confirmed">Anemia confirmed</option>
            <option value="not_anemic">No anemia recorded</option>
          </select>
        </label>
        <button className="btn subtle" disabled={busy}>Save assessment</button>
      </form>}
    </section>
    <section className="panel followup-panel" aria-labelledby="referrals-title">
      <h2 id="referrals-title">Referrals</h2>
      {loadError ? <div role="alert">
        <p>Could not load referrals.</p>
        <button className="btn subtle" type="button" onClick={() => setAttempt(value => value + 1)}>Retry</button>
      </div> : referrals === null ? <p role="status">Loading referrals...</p> : <>
        {referrals.length === 0 && <p>No referrals recorded.</p>}
        {referrals.map(referral => <article className="panel followup-panel" key={referral.id}>
          <h3>{referral.facility}</h3>
          <p><time dateTime={referral.referred_on}>{formatDate(referral.referred_on)}</time> &middot; {referralLabels[referral.status]}</p>
          {referral.outcome && <p>{referral.outcome}</p>}
          {onPatientChange && referral.status !== "closed" && (closing === referral.id ? (
            <form onSubmit={event => {
              event.preventDefault();
              const outcome = String(new FormData(event.currentTarget).get("outcome") ?? "").trim();
              if (outcome) change(referral, "closed", outcome);
              else setError("Enter the referral outcome.");
            }}>
              <label>Outcome<textarea name="outcome" required maxLength={500} rows={2} /></label>
              <div className="actions">
                <button className="btn subtle" type="button" onClick={() => setClosing(null)} disabled={busy}>Cancel</button>
                <button className="btn" disabled={busy}>Save outcome</button>
              </div>
            </form>
          ) : <div className="actions">
            {referral.status === "referred" && <button className="btn subtle" type="button" disabled={busy}
              onClick={() => change(referral, "attended", null)}>Mark attended</button>}
            <button className="btn subtle" type="button" disabled={busy} onClick={() => setClosing(referral.id)}>Record outcome</button>
          </div>)}
        </article>)}
        {onPatientChange && <details>
          <summary>Add referral</summary>
          <form onSubmit={refer}>
            <label>Facility<input name="facility" required maxLength={120} /></label>
            <label>Referral date<input name="date" type="date" defaultValue={dateKey()} max={dateKey()} required /></label>
            <button className="btn" disabled={busy}>Save referral</button>
          </form>
        </details>}
      </>}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </section>
  </>;
}
