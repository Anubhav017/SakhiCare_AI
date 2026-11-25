import { useEffect, useState } from "react";
import { listCarePathways, updateCarePathwayStep, type CarePathway, type Patient } from "./records";

export function CarePathways({ patients, patientId, readOnly = false }: {
  patients: Patient[]; patientId?: string; readOnly?: boolean;
}) {
  const [runs, setRuns] = useState<CarePathway[] | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    let current = true;
    setRuns(null);
    setError(false);
    listCarePathways(patientId).then(rows => {
      if (current) setRuns(rows);
    }).catch(() => {
      if (current) setError(true);
    });
    const refresh = () => setRetry(value => value + 1);
    window.addEventListener("sakhicare:care-pathways-changed", refresh);
    return () => {
      current = false;
      window.removeEventListener("sakhicare:care-pathways-changed", refresh);
    };
  }, [patientId, retry]);

  async function toggle(run: CarePathway, stepId: number, completed: boolean) {
    const key = `${run.id}:${stepId}`;
    setBusy(key);
    setActionError("");
    try {
      const updated = await updateCarePathwayStep(run.id, stepId, completed);
      setRuns(current => current?.map(item => item.id === updated.id ? updated : item) ?? current);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not update the pathway step.");
    } finally {
      setBusy(null);
    }
  }

  const patientNames = new Map(patients.map(patient => [Number(patient.id), patient.name]));
  const heading = patientId ? "Care pathway" : "Care pathways";
  return <section className="panel followup-panel care-pathways" aria-label={heading}>
    <header className="section-head"><div><h2>{heading}</h2><small>Guided follow-up steps. These do not replace your team's approved protocol.</small></div></header>
    {runs === null && !error && <p role="status">Loading care pathways...</p>}
    {error && <div role="alert"><p>Could not load care pathways.</p>
      <button className="btn subtle" type="button" onClick={() => setRetry(value => value + 1)}>Retry</button></div>}
    {runs && !runs.length && <p className="empty">No pathways started yet. A pathway starts when a moderate or high risk Hb result or a referral is recorded.</p>}
    {actionError && <p className="signup-error" role="alert">{actionError}</p>}
    {runs?.map(run => <article className="care-pathway-run" key={run.id}>
      <header><div>
        {patientId ? <h3>{run.title}</h3> : <h3><a className="patient-link" href={`#patient/${run.patient_id}`}>{patientNames.get(run.patient_id) ?? "Patient"}</a><small>{run.title}</small></h3>}
        <span className={`pill ${run.status === "completed" ? "done" : "pending"}`}>{run.status}</span>
      </div></header>
      <ol>{run.steps.map(step => <li key={step.id} className={step.status === "completed" ? "care-pathway-step is-complete" : "care-pathway-step"}>
        <span>{step.title}</span>
        <span className="care-pathway-step-state">{step.status === "completed" ? "Completed" : step.status === "skipped" ? "Skipped" : "To do"}</span>
        {!readOnly && run.status === "active" && step.status !== "skipped" && <button className="btn subtle" type="button"
          disabled={busy === `${run.id}:${step.id}`}
          onClick={() => void toggle(run, step.id, step.status !== "completed")}>{busy === `${run.id}:${step.id}` ? "Saving..." : step.status === "completed" ? "Undo" : "Mark complete"}</button>}
      </li>)}</ol>
    </article>)}
  </section>;
}
