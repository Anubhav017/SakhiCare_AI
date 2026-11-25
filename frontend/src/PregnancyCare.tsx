import { useEffect, useState, type FormEvent } from "react";
import {
  dateKey, formatDate, getPregnancyCare, createPregnancy, closePregnancy, scheduleAncVisit,
  updateAncVisit, saveIfaPlan, recordIfaIntake, scheduleFollowup,
  type PregnancyCareData, type AntenatalVisit, type IfaIntakeLog,
} from "./records";

function orderedVisits(visits: AntenatalVisit[]) {
  return [...visits].sort((a, b) => a.due_date.localeCompare(b.due_date) || a.id - b.id);
}

function hasThreeReportedMisses(logs: IfaIntakeLog[]) {
  const recent = [...logs].sort((a, b) => b.intake_date.localeCompare(a.intake_date)).slice(0, 3);
  if (recent.length < 3 || recent.some(log => log.status !== "missed")) return false;
  const days = recent.map(log => Date.parse(log.intake_date + "T12:00:00Z"));
  return days[0] - days[1] === 86_400_000 && days[1] - days[2] === 86_400_000;
}

export function PregnancyCare({ patientId }: { patientId: string }) {
  const [data, setData] = useState<PregnancyCareData | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [checkinScheduled, setCheckinScheduled] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    getPregnancyCare(patientId).then(value => {
      if (active) setData(value);
    }).catch(cause => {
      if (active) setError(cause instanceof Error ? cause.message : "Could not load pregnancy care.");
    });
    return () => { active = false; };
  }, [patientId, retry]);

  async function mutate(action: () => Promise<unknown>, message: string): Promise<boolean> {
    if (busy) return false;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setData(await getPregnancyCare(patientId));
      window.dispatchEvent(new Event("sakhicare:records-changed"));
      setNotice(message);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save pregnancy care.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  function addPregnancy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const lmp = String(values.get("lmp_date") ?? "");
    void mutate(() => createPregnancy(patientId, {
      lmp_date: lmp || null, edd_date: String(values.get("edd_date") ?? ""),
    }), "Pregnancy dates saved from the care record.");
  }

  function addVisit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!data?.pregnancy) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    void mutate(() => scheduleAncVisit(
      patientId, data.pregnancy!.id, String(values.get("due_date") ?? ""), String(values.get("facility") ?? "").trim(),
    ), "ANC visit scheduled and added to follow-ups.").then(() => form.reset());
  }

  function savePlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!data?.pregnancy) return;
    const values = new FormData(event.currentTarget);
    void mutate(() => saveIfaPlan(patientId, data.pregnancy!.id, {
      start_date: String(values.get("start_date") ?? ""),
      source: String(values.get("source") ?? "").trim(),
      directions: String(values.get("directions") ?? "").trim(),
    }), "IFA instructions saved from the stated care plan.");
  }

  function logIntake(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!data?.pregnancy) return;
    const values = new FormData(event.currentTarget);
    void mutate(() => recordIfaIntake(
      patientId, data.pregnancy!.id, String(values.get("intake_date") ?? ""),
      String(values.get("status") ?? "unknown") as IfaIntakeLog["status"],
    ), "IFA intake status saved.");
  }

  return <section className="panel followup-panel pregnancy-care" aria-labelledby="pregnancy-care-title">
    <header className="section-head"><div><h2 id="pregnancy-care-title">Pregnancy & ANC care</h2>
      <p>Record dates from the patient’s or provider’s care record.</p></div></header>
    {error && <div role="alert"><p>{error}</p>{!data && <button className="btn subtle" type="button" onClick={() => setRetry(value => value + 1)}>Retry</button>}</div>}
    {!data && !error && <p role="status">Loading pregnancy care…</p>}
    {data && !data.pregnancy && <form onSubmit={addPregnancy}>
      <p>No active pregnancy record. Enter only dates confirmed from a care record; SakhiCare does not estimate an EDD.</p>
      <label>Last menstrual period (optional)<input name="lmp_date" type="date" max={dateKey()} /></label>
      <label>Expected due date (EDD)<input name="edd_date" type="date" required /></label>
      <button className="btn" disabled={busy}>Save pregnancy record</button>
    </form>}
    {data?.pregnancy && <>
      <dl className="patient-screening-summary">
        {data.pregnancy.lmp_date && <div><dt>LMP recorded</dt><dd>{formatDate(data.pregnancy.lmp_date)}</dd></div>}
        <div><dt>EDD recorded</dt><dd><strong>{formatDate(data.pregnancy.edd_date)}</strong></dd></div>
      </dl>
      <button className="btn subtle" type="button" disabled={busy}
        onClick={() => {
          if (window.confirm("End tracking for this pregnancy? Any planned ANC visits will be cancelled.")) {
            void mutate(() => closePregnancy(patientId, data.pregnancy!.id, "closed"), "Pregnancy tracking ended.");
          }
        }}>End pregnancy tracking</button>

      <section aria-labelledby="anc-visits-title">
        <header className="section-head"><h3 id="anc-visits-title">ANC visits</h3></header>
        {!data.visits.length && <p>No ANC visits scheduled.</p>}
        {orderedVisits(data.visits).map(visit => <article className="row" key={visit.id}>
          <div><strong>{visit.facility || "ANC visit"}</strong><small>{formatDate(visit.due_date)}</small></div>
          <div className="actions"><span className={`pill ${visit.status === "completed" ? "done" : visit.status === "planned" ? "pending" : ""}`}>{visit.status}</span>
            {visit.status === "planned" && <>
              <button className="btn subtle" type="button" disabled={busy || visit.due_date > dateKey()}
                title={visit.due_date > dateKey() ? "This visit date is still in the future." : undefined}
                onClick={() => void mutate(() => updateAncVisit(patientId, data.pregnancy!.id, visit.id, "completed"), "ANC visit marked completed.")}>Mark completed</button>
              <button className="btn subtle" type="button" disabled={busy}
                onClick={() => void mutate(() => updateAncVisit(patientId, data.pregnancy!.id, visit.id, "cancelled"), "ANC visit cancelled.")}>Cancel</button>
            </>}
          </div>
        </article>)}
        <details><summary>Schedule an ANC visit</summary><form onSubmit={addVisit}>
          <label>Visit date<input name="due_date" type="date" min={dateKey()} required /></label>
          <label>Facility (optional)<input name="facility" maxLength={120} /></label>
          <button className="btn" disabled={busy}>Schedule visit</button>
        </form></details>
      </section>

      <section aria-labelledby="ifa-title">
        <header className="section-head"><h3 id="ifa-title">IFA plan & intake tracking</h3></header>
        <p>Record the provider’s instructions as given. SakhiCare does not prescribe IFA doses or schedule.</p>
        {data.ifa_plan && <article className="row">
          <div><strong>Instructions recorded</strong><small>{data.ifa_plan.directions}</small><small>Source: {data.ifa_plan.source} · Starts {formatDate(data.ifa_plan.start_date)}</small></div>
        </article>}
        <details><summary>{data.ifa_plan ? "Update recorded IFA instructions" : "Record provider’s IFA instructions"}</summary>
          <form onSubmit={savePlan}>
            <label>Plan start date<input name="start_date" type="date" defaultValue={data.ifa_plan?.start_date ?? dateKey()} max={dateKey()} required /></label>
            <label>Prescribing facility / clinician<input name="source" maxLength={120} defaultValue={data.ifa_plan?.source ?? ""} required /></label>
            <label>Instructions as prescribed<textarea name="directions" maxLength={240} rows={2} defaultValue={data.ifa_plan?.directions ?? ""} required /></label>
            <button className="btn" disabled={busy}>Save IFA instructions</button>
          </form>
        </details>
        {data.ifa_plan && <>
          {hasThreeReportedMisses(data.ifa_logs) && <div className="notice" role="status">
            Three consecutive days are recorded as missed. Check in with the patient and consult the ANM or clinician about next steps.
            {!checkinScheduled && <button className="btn subtle" type="button" disabled={busy}
              onClick={() => void mutate(
                () => scheduleFollowup(patientId, "IFA adherence check-in", dateKey(1)),
                "Check-in added to the follow-up list.",
              ).then(saved => { if (saved) setCheckinScheduled(true); })}>Schedule check-in for tomorrow</button>}
          </div>}
          <form onSubmit={logIntake}>
            <label>Date<input name="intake_date" type="date" defaultValue={dateKey()} min={data.ifa_plan.start_date} max={dateKey()} required /></label>
            <label>Reported intake status<select name="status" defaultValue="taken">
              <option value="taken">Taken</option><option value="missed">Missed</option><option value="unknown">Not known</option>
            </select></label>
            <button className="btn subtle" disabled={busy}>Save daily status</button>
          </form>
          <h4>Recent reported intake</h4>
          {!data.ifa_logs.length && <p>No intake statuses recorded.</p>}
          {data.ifa_logs.map(log => <article className="row" key={log.id}>
            <strong>{formatDate(log.intake_date)}</strong><span className={`pill ${log.status === "taken" ? "done" : log.status === "missed" ? "pending" : ""}`}>{log.status}</span>
          </article>)}
          <small>Only explicitly reported entries appear here. Missing entries are not treated as missed doses.</small>
        </>}
      </section>
    </>}
    {notice && <p role="status">{notice}</p>}
  </section>;
}
