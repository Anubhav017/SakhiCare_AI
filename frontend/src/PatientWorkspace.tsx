import { useEffect, useRef, useState, type ReactNode } from "react";
import { dateKey, formatDate, listHbReadings, type HbReading, type Followup, type Patient } from "./records";

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

export function PatientDetail({ patient, followups, backTo, backLabel, onSchedule, onScreen,
  onToggle, busyId, followupStatus }: {
  patient: Patient; followups: Followup[]; backTo: string; backLabel: string;
  followupStatus?: ReactNode;
  onSchedule?: () => void; onScreen?: () => void;
  onToggle?: (followup: Followup) => void; busyId?: string | null;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const [history, setHistory] = useState<{ rows: HbReading[] } | "error" | null>(null);
  const [retry, setRetry] = useState(0);
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

  const timeline = [
    ...(history && history !== "error" ? history.rows : []).map(item => ({ kind: "reading" as const, item })),
    ...followups.filter(item => item.patientId === patient.id).map(item => ({ kind: "followup" as const, item })),
  ].sort((a, b) => b.item.date.localeCompare(a.item.date));

  const demographics = [patient.village, patient.age == null ? null : `${patient.age} years`].filter(Boolean);

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
            {demographics.length > 0 && <p>{demographics.join(" \u00b7 ")}</p>}
          </div>
          {onScreen && <button className="btn subtle" onClick={onScreen}>Record Hb</button>}
        </div>
      </header>
      <section className="panel followup-panel" aria-label="Hb screening">
        <header className="section-head"><h2>Hb screening</h2></header>
        {patient.screening ? <>
          <p>{patient.screening.hb === null ? "Hb test pending" : `Hb ${patient.screening.hb} g/dL`}</p>
          <small>{formatDate(patient.screening.date)}{patient.screening.method && <> &middot; {patient.screening.method}</>}</small>
        </> : <p className="empty">No screening recorded yet.</p>}
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
