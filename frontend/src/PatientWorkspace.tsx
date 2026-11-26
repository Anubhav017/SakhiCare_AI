import { PatientCare } from "./PatientCare";
import { CarePathways } from "./CarePathways";
import { PregnancyCare } from "./PregnancyCare";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { dateKey, formatDate, listHbReadings, listPatientActivity, type PatientActivityEvent, type HbReading, type Followup, type Patient, patientDetails } from "./records";

function HbTrend({ readings }: { readings: HbReading[] }) {
  const rows = [...readings].sort((a, b) => a.date.localeCompare(b.date) || a.id - b.id);
  const dates = rows.map(row => Date.parse(row.date));
  const start = dates[0];
  const end = dates[dates.length - 1];
  const low = rows.reduce((min, row) => Math.min(min, row.hb), Infinity);
  const high = rows.reduce((max, row) => Math.max(max, row.hb), -Infinity);
  const points = rows.map((row, index) => ({
    x: start === end ? 160 : 14 + 292 * (dates[index] - start) / (end - start),
    y: low === high ? 58 : 102 - 88 * (row.hb - low) / (high - low),
  }));

  return <figure className="hb-trend">
    <figcaption>Haemoglobin trend (g/dL)</figcaption>
    <svg viewBox="0 0 320 116" aria-hidden="true">
      <path className="hb-grid" d="M14 14H306 M14 58H306 M14 102H306" />
      <polyline points={points.map(point => point.x + "," + point.y).join(" ")} />
      {points.map((point, index) =>
        <circle key={rows[index].id} cx={point.x} cy={point.y} r="4">
          <title>{formatDate(rows[index].date)}: {rows[index].hb} g/dL</title>
        </circle>,
      )}
    </svg>
    <div className="hb-trend-labels">
      <span>{formatDate(rows[0].date)} · {rows[0].hb} g/dL</span>
      {rows.length > 1 && <span>{formatDate(rows[rows.length - 1].date)} · {rows[rows.length - 1].hb} g/dL</span>}
    </div>
  </figure>;
}

export function patientRoute(section: string) {
  const match = /^patient\/([1-9]\d*)(\/followups)?$/.exec(section);
  return match ? { id: match[1], fromFollowups: Boolean(match[2]) } : null;
}

export function followupStatus(item: Followup, today: string) {
  if (item.done) return "Completed";
  if (item.date < today) return "Overdue";
  if (item.date === today) return "Due today";
  return "Upcoming";
}

type FollowupListProps = {
  items: Followup[];
  patients?: Patient[];
  empty: string;
  onToggle?: (followup: Followup) => void;
  busyId?: string | null;
};

export function FollowupList({ items, patients, empty, onToggle, busyId }: FollowupListProps) {
  if (!items.length) return <p className="empty">{empty}</p>;
  const today = dateKey();
  const names = new Map(patients?.map(patient => [patient.id, patient.name]));
  return items.map(item => {
    const status = followupStatus(item, today);
    return <article className="row followup-row" key={item.id}>
      <div>
        <strong>{item.title}</strong>
        <small>Due {formatDate(item.date)}</small>
        {names.has(item.patientId) && (
          <a className="patient-link" href={`#patient/${item.patientId}/followups`}>{names.get(item.patientId)}</a>
        )}
      </div>
      <div className="actions">
        <span className={status === "Completed" ? "pill done" : status === "Overdue" ? "pill pending" : "pill"}>{status}</span>
        {onToggle && <button className="btn subtle" disabled={busyId === item.id}
          onClick={() => onToggle(item)}>{item.done ? "Reopen" : "Mark complete"}</button>}
      </div>
    </article>;
  });
}

export function PatientDetail({ patient, followups, backTo, backLabel, onSchedule, onScreen, onPatientChange,
  onToggle, busyId, followupStatus, pathwayReadOnly = false }: {
  patient: Patient; onPatientChange?: (patient: Patient) => void; followups: Followup[]; backTo: string; backLabel: string;
  followupStatus?: ReactNode;
  onSchedule?: () => void; onScreen?: () => void;
  onToggle?: (followup: Followup) => void; busyId?: string | null;
  pathwayReadOnly?: boolean;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const [history, setHistory] = useState<{ rows: HbReading[] } | "error" | null>(null);
  const [retry, setRetry] = useState(0);
  const [activity, setActivity] = useState<PatientActivityEvent[] | null>(null);
  const [activityError, setActivityError] = useState(false);
  const [activityRetry, setActivityRetry] = useState(0);
  useEffect(() => {
    let current = true;
    setHistory(null);
    listHbReadings(patient.id).then(rows => {
      if (current) setHistory({ rows });
    }).catch(() => {
      if (current) setHistory("error");
    });
    return () => { current = false; };
  }, [patient.id, patient.screening, retry]);

  useEffect(() => {
    let current = true;
    setActivity(null);
    setActivityError(false);
    listPatientActivity(patient.id).then(rows => {
      if (current) setActivity(rows);
    }).catch(() => {
      if (current) setActivityError(true);
    });
    return () => { current = false; };
  }, [patient.id, activityRetry]);

  const timeline = [
    ...(history && history !== "error" ? history.rows : []).map(item => ({ kind: "reading" as const, item })),
    ...followups.filter(item => item.patientId === patient.id).map(item => ({ kind: "followup" as const, item })),
  ].sort((a, b) => b.item.date.localeCompare(a.item.date));

  const demographics = patientDetails(patient);

  useEffect(() => {
    window.scrollTo(0, 0);
    heading.current?.focus({ preventScroll: true });
  }, [patient.id]);

  return (
    <section className="patient-detail" aria-labelledby="patient-title">
      <header className="patient-header">
        <a className="workspace-back patient-back" href={backTo}>
          <span aria-hidden="true">&#8592;</span> {backLabel}
        </a>
        <div className="page-head">
          <div>
            <h1 id="patient-title" ref={heading} tabIndex={-1}>{patient.name}</h1>
            {demographics && <p>{demographics}</p>}
          </div>
          {onScreen && <button className="btn subtle" onClick={onScreen}>Record Hb</button>}
        </div>
      </header>
      <section className="panel followup-panel" aria-label="Hb screening">
        <header className="section-head"><h2>Hb screening</h2></header>
        {patient.screening ? <>
          <dl className="patient-screening-summary">
            <div>
              <dt>Current Hb</dt>
              <dd><strong>{patient.screening.hb === null ? "Test pending" : patient.screening.hb + " g/dL"}</strong></dd>
            </div>
            <div>
              <dt>Risk recorded</dt>
              <dd>{patient.screening.risk
                ? <span className="pill patient-risk">{patient.screening.risk} risk</span>
                : "Not assessed"}</dd>
            </div>
          </dl>
          <div className="patient-screening-details">
            <time dateTime={patient.screening.date}>{formatDate(patient.screening.date)}</time>
            {patient.screening.method && <span>{patient.screening.method}</span>}
          </div>
        </> : <p className="empty">No screening recorded yet.</p>}
      </section>
      <PatientCare key={patient.id} patient={patient} onPatientChange={onPatientChange} />
      <PregnancyCare key={`pregnancy-${patient.id}`} patientId={patient.id} readOnly={pathwayReadOnly} />
      <CarePathways patients={[patient]} patientId={patient.id} readOnly={pathwayReadOnly} />
      <section className="panel followup-panel" aria-label="Record activity">
        <header className="section-head"><h2>Record activity</h2></header>
        {activity === null && !activityError && <p role="status">Loading record activity...</p>}
        {activityError && <div role="alert"><p>Could not load record activity.</p>
          <button className="btn subtle" type="button" onClick={() => setActivityRetry(value => value + 1)}>Retry</button></div>}
        {activity && !activity.length && <p className="empty">No activity recorded yet.</p>}
        {activity?.map(event => <article className="row" key={event.id}>
          <div><strong>{event.summary}</strong><small>{event.actor_name ?? "Former user"}</small></div>
          <time dateTime={event.created_at}>{new Date(event.created_at).toLocaleString("en-IN")}</time>
        </article>)}
      </section>
      <section className="panel followup-panel" aria-label="Patient timeline">
        <header className="section-head">
          <h2>Patient timeline</h2>
          {onSchedule && !followupStatus && <button className="btn subtle" onClick={onSchedule}>Schedule follow-up</button>}
        </header>
        {history === null && <p role="status">Loading Hb history...</p>}
        {history === "error" && <div role="alert">
          <p>Could not load Hb history.</p>
          <button className="btn subtle" onClick={() => setRetry(value => value + 1)}>Retry</button>
        </div>}
        {history && history !== "error" && history.rows.length > 0 && <HbTrend readings={history.rows} />}
        {followupStatus}
        {history && history !== "error" && !followupStatus && !timeline.length &&
          <p className="empty">No Hb readings or follow-ups recorded yet.</p>}
        {timeline.map(entry => entry.kind === "reading"
          ? <article key={"hb-" + entry.item.id} className="row">
              <div><strong>Hb {entry.item.hb} g/dL</strong><small>{entry.item.method}</small></div>
              <time dateTime={entry.item.date}>{formatDate(entry.item.date)}</time>
            </article>
          : <FollowupList key={"followup-" + entry.item.id} items={[entry.item]}
              empty="" onToggle={onToggle} busyId={busyId} />)}
      </section>
    </section>
  );
}
