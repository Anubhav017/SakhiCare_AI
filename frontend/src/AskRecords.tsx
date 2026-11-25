import { useEffect, useRef, useState, type ReactNode } from "react";

type Report = "patient_count" | "due_followups" | "patients_by_worker" | "pathway_status";
type Question = Report | "worker_patients";
type RecordAnswer = {
  answer?: string;
  worker?: string;
  count?: number;
  total?: number;
  truncated?: boolean;
  patients?: { id: number; name: string; village?: string | null; age?: number | null; anemia_status?: string | null; risk?: string | null }[];
  workers?: { worker: string; count: number }[];
  followups?: { id: number; patient_id: number; patient: string; title: string; due_date: string }[];
  referrals?: { id: number; patient_id: number; patient: string; facility: string; referred_on: string; status: string; outcome: string | null }[];
  pathways?: { id: number; patient_id: number; patient: string; title: string; status: string; updated_at?: string; steps?: { title: string; status: string }[] }[];
};

type AskAction = {
  id: string;
  action: string;
  preview: { title: string; patient: string; details: string[] };
  status: "pending" | "applied" | "cancelled" | "expired" | "failed";
  expires_at: string;
  result?: { message?: string } | null;
};

function isChangeRequest(question: string) {
  return /\b(?:add|create|register|update|edit|record|save|schedule|complete|mark|cancel|archive|set|change|correct|remove|delete|close|confirm|withdraw)\b/i.test(question.trim()) ||
    /(?:follow[- ]?up\s+(?:dena|schedule|karna|banao)|(?:मरीज|रोगी).*(?:जोड़|बनाओ|दर्ज|अपडेट|बदलो|रद्द)|(?:दर्ज|बदलो|पूरा|रद्द).*(?:मरीज|फॉलो|रेफरल|एचबी))/i.test(question);
}

async function responseMessage(response: Response, fallback: string) {
  try {
    const data = await response.json();
    const detail = data?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail.message === "string") return detail.message;
  } catch { /* use the local fallback */ }
  return fallback;
}

const questionAliases: Record<Report, string[]> = {
  "patient_count": [
    "how many patients do i have",
    "how many patients does my team have",
    "how many patients",
    "patient count",
    "total patients",
    "mere kitne patients hain",
    "meri team me kitne patients hain",
    "मेरे कितने मरीज हैं",
    "मेरी टीम में कितने मरीज हैं",
    "कुल मरीज कितने हैं"
  ],
  "due_followups": [
    "which follow-ups are due today or overdue",
    "which follow ups are due today or overdue",
    "due follow-ups",
    "due follow ups",
    "which follow-ups are due",
    "aaj kin patients ka follow-up due hai",
    "aaj kiske follow-up due hain",
    "आज किसका फॉलो-अप बाकी है",
    "आज किन मरीजों का फॉलो-अप बाकी है"
  ],
  "patients_by_worker": [
    "how many patients does each asha have",
    "patients by asha",
    "patient count by asha",
    "har asha ke kitne patients hain",
    "हर आशा के कितने मरीज हैं"
  ],
  "pathway_status": [
    "show active care pathways",
    "care pathway status",
    "care pathways",
    "what pathways are active",
    "मेरे मरीजों के केयर पाथवे दिखाएं"
  ]
};

function normalizeQuestion(text: string) {
  return text.normalize("NFKC").toLowerCase()
    .replace(/[?!.,?-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const shortcutLabels: Record<Report, string> = {
  patient_count: "Patient count",
  due_followups: "Due follow-ups",
  patients_by_worker: "Patients by ASHA",
  pathway_status: "Care pathways",
};

export function AskRecords({ isAdmin, backLabel, onSessionExpired, sourceControl }: {
  sourceControl: ReactNode;
  isAdmin: boolean;
  backLabel: string;
  onSessionExpired: () => void;
}) {
  const [typedQuestion, setTypedQuestion] = useState("");
  const [inputMode, setInputMode] = useState<"ask" | "change">("ask");
  const [questionError, setQuestionError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [answer, setAnswer] = useState<RecordAnswer | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [drafts, setDrafts] = useState<AskAction[]>([]);
  const [savingDraft, setSavingDraft] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  useEffect(() => {
    let active = true;
    fetch("/backend-api/api/ask/records/actions/pending", { cache: "no-store" })
      .then(async response => {
        if (response.status === 401) { onSessionExpired(); return []; }
        if (!response.ok) return [];
        return await response.json() as AskAction[];
      })
      .then(rows => { if (active && rows.length) setDrafts(rows); })
      .catch(() => {});
    return () => { active = false; };
  }, [onSessionExpired]);

  const questions: { id: Report; label: string }[] = [
    { id: "patient_count", label: isAdmin ? "How many patients does my team have?" : "How many patients do I have?" },
    { id: "due_followups", label: "Which follow-ups are due today or overdue?" },
    { id: "pathway_status", label: "Show active care pathways" },
  ];
  if (isAdmin) questions.push({ id: "patients_by_worker", label: "How many patients does each ASHA have?" });

  async function ask(question: string, worker?: string, submittedDraft?: string) {
    setQuestionError("");
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setSelected(question);
    setAnswer(null);
    setError("");
    setPending(true);
    try {
      const response = await fetch("/backend-api/api/ask/records", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, worker }),
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]),
        cache: "no-store",
      });
      if (controller.signal.aborted) return;
      if (response.status === 401) return onSessionExpired();
      if (worker && (response.status === 404 || response.status === 409)) {
        const { detail } = await response.json();
        if (!controller.signal.aborted) setError(detail);
        return;
      }
      if (!response.ok) throw new Error("Record request failed");
      const result = await response.json() as RecordAnswer;
      if (!controller.signal.aborted) {
        setAnswer(result);
        if (submittedDraft !== undefined) {
          setTypedQuestion(current => current === submittedDraft ? "" : current);
        }
      }
    } catch {
      if (!controller.signal.aborted) setError("Could not load records. Select a question to try again.");
    } finally {
      if (!controller.signal.aborted) setPending(false);
    }
  }

  async function proposeChange(question: string) {
    setQuestionError("");
    setAnswer(null);
    setError("");
    setPending(true);
    try {
      const response = await fetch("/backend-api/api/ask/records/actions", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
        body: JSON.stringify({ question }),
        cache: "no-store",
      });
      if (response.status === 401) return onSessionExpired();
      if (!response.ok) throw new Error(await responseMessage(response, "Could not prepare a safe change preview."));
      const draft = await response.json() as AskAction;
      setDrafts(current => [draft, ...current.filter(item => item.id !== draft.id)]);
      setTypedQuestion(current => current === question ? "" : current);
    } catch (reason) {
      setQuestionError(reason instanceof Error ? reason.message : "Could not prepare a safe change preview.");
    } finally {
      setPending(false);
    }
  }

  async function decideChange(draft: AskAction, approved: boolean) {
    setSavingDraft(draft.id);
    setQuestionError("");
    try {
      const response = await fetch(`/backend-api/api/ask/records/actions/${draft.id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
        body: JSON.stringify({ approved }),
        cache: "no-store",
      });
      if (response.status === 401) return onSessionExpired();
      if (!response.ok) throw new Error(await responseMessage(response, "Could not resolve this change."));
      const updated = await response.json() as AskAction;
      setDrafts(current => current.map(item => item.id === updated.id ? updated : item));
      if (updated.status === "applied") {
        window.dispatchEvent(new Event("sakhicare:records-changed"));
        window.dispatchEvent(new Event("sakhicare:care-pathways-changed"));
      }
    } catch (reason) {
      setQuestionError(reason instanceof Error ? reason.message : "Could not resolve this change.");
    } finally {
      setSavingDraft(null);
    }
  }

  return (
    <section className="ask-workspace records-workspace" aria-labelledby="records-title">
      <header className="ask-heading ask-heading-actions">
        <a className="ask-back" href="#today"><span aria-hidden="true">&#8592;</span> {backLabel}</a>
        <h1 id="records-title">Ask Records</h1>
      </header>
      <div aria-live="polite" aria-busy={pending}>
        {pending && <p className="ask-answer" role="status">
          {inputMode === "change" || isChangeRequest(typedQuestion) ? "Preparing a change preview&hellip;" : "Looking up records&hellip;"}
        </p>}
        {error && <p className="signup-error" role="alert">{error}</p>}
        {answer && <section className="panel records-result">
          {answer.answer && <p>{answer.answer}</p>}
          {answer.count !== undefined && <p className="records-total"><strong>{answer.count}</strong> patients</p>}
          {answer.patients && (answer.patients.length ? <ul>{answer.patients.map(patient => <li key={patient.id}>
            <a className="patient-link" href={`#patient/${patient.id}`}>{patient.name}</a>
            {patient.village && <> &middot; {patient.village}</>}
            {patient.age != null && <> &middot; {patient.age} years</>}
            {patient.risk && <> &middot; ASHA-recorded {patient.risk} risk</>}
            {patient.anemia_status === "confirmed" && <> &middot; ASHA-recorded anemia assessment: confirmed</>}
          </li>)}</ul> : <p>No matching patients.</p>)}
          {answer.workers && (answer.workers.length ? <ul>{answer.workers.map((row, index) => <li key={index}>{row.worker} &middot; {row.count} patients</li>)}</ul> : <p>No ASHA workers assigned.</p>)}
          {answer.followups && (answer.followups.length ? <ul>{answer.followups.map(row => <li key={row.id}>
            <a className="patient-link" href={`#patient/${row.patient_id}/followups`}>{row.patient}</a>
            {" "} &middot; {row.title} &middot; <time dateTime={row.due_date}>{row.due_date}</time>
          </li>)}</ul> : <p>No matching follow-ups.</p>)}
          {answer.referrals && (answer.referrals.length ? <ul>{answer.referrals.map(row => <li key={row.id}>
            <a className="patient-link" href={`#patient/${row.patient_id}`}>{row.patient}</a>
            {" "} &middot; {row.facility} &middot; {row.status}{row.outcome && <> &middot; {row.outcome}</>}
          </li>)}</ul> : <p>No matching referrals.</p>)}
          {answer.pathways && (answer.pathways.length ? <div className="records-pathways">{answer.pathways.map(run => <article key={run.id}>
            <h3><a className="patient-link" href={`#patient/${run.patient_id}`}>{run.patient}</a> · {run.title}</h3>
            <span className={`pill ${run.status === "completed" ? "done" : "pending"}`}>{run.status}</span>
            {run.steps?.length ? <ol>{run.steps.map((step, index) => <li key={index}>{step.title} · {step.status}</li>)}</ol> : null}
          </article>)}</div> : <p>No matching care pathways.</p>)}
          {answer.truncated && <p>Showing the first 50 matches. Use the Patients page to browse the full list.</p>}
        </section>}
      </div>
      {drafts.map(draft => <section className={`panel ask-action-review ask-action-${draft.status}`} key={draft.id}
        aria-labelledby={`ask-action-title-${draft.id}`}>
        <div className="ask-action-banner"><span aria-hidden="true">{draft.status === "pending" ? "Review" : draft.status}</span>
          <strong>{draft.status === "pending" ? "Nothing is saved yet" : draft.status === "applied" ? "Saved" : draft.status === "cancelled" ? "Cancelled" : draft.status === "expired" ? "Preview expired" : "Not saved"}</strong>
        </div>
        <h2 id={`ask-action-title-${draft.id}`}>{draft.preview.title}</h2>
        <p className="ask-action-patient">{draft.preview.patient}</p>
        <ul>{draft.preview.details.map((detail, index) => <li key={index}>{detail}</li>)}</ul>
        {draft.status === "pending" ? <>
          <p className="ask-action-expiry">Review and save within 15 minutes. Cancel leaves the record unchanged.</p>
          <div className="ask-action-buttons">
            <button className="btn subtle" type="button" disabled={savingDraft === draft.id}
              onClick={() => void decideChange(draft, false)}>Cancel</button>
            <button className="btn" type="button" disabled={savingDraft === draft.id}
              onClick={() => void decideChange(draft, true)}>{savingDraft === draft.id ? "Saving..." : "Save change"}</button>
          </div>
        </> : <p className="ask-action-result" role="status">{draft.result?.message}</p>}
      </section>)}
      <form className="panel ask-composer records-composer" onSubmit={event => {
        event.preventDefault();
        const typed = normalizeQuestion(typedQuestion);
        const match = questions.find(question =>
          [question.label, ...questionAliases[question.id]].some(alias => normalizeQuestion(alias) === typed)
        );
        const requestText = typedQuestion.trim().replace(/[?.!]+$/g, "");
        const worker = isAdmin && (
          /^(?:show (?:me )?|list )?patients (?:assigned to|for|of) (.+)$/i.exec(requestText)?.[1] ??
          /^(?:show (?:me )?)?(.+?)(?:['’]s)?\s+patient list$/i.exec(requestText)?.[1] ??
          /^(?:list|show)(?: me)? (.+?)['’]s patients$/i.exec(requestText)?.[1]
        );
        if (match) {
          void ask(match.id, undefined, typedQuestion);
        } else if (worker) {
          void ask("worker_patients", worker.trim(), typedQuestion);
        } else if (requestText && (inputMode === "change" || isChangeRequest(typedQuestion))) {
          void proposeChange(typedQuestion.trim());
        } else if (requestText) {
          void ask(typedQuestion.trim(), undefined, typedQuestion);
        }
      }}>
        <label htmlFor="records-mode">What would you like to do?</label>
        <select id="records-mode" className="records-mode-select" value={inputMode}
          onChange={event => setInputMode(event.target.value as "ask" | "change")}>
          <option value="ask">Ask about records</option>
          <option value="change">Prepare a record change</option>
        </select>
        <label htmlFor="records-question">{inputMode === "change" ? "Describe the change" : "Your records question"}</label>
        <input id="records-question" value={typedQuestion} maxLength={200}
          placeholder={inputMode === "change" ? "e.g., Schedule a follow-up for Meena on 25 November" : questions[0].label} onChange={event => {
            setTypedQuestion(event.target.value);
            setQuestionError("");
          }} />
        <p className="ask-action-hint">Record changes are only saved after you review the preview and select Save.</p>
        <div className="ask-actions">
          {sourceControl}
          <button className="btn ask-send" type="submit" disabled={!typedQuestion.trim()}>
            {inputMode === "change" ? "Preview change" : "Ask"}
          </button>
        </div>
        {questionError && <p className="signup-error" role="alert">{questionError}</p>}
      </form>
      <div className="ask-records" role="group" aria-label="Quick questions">
        {questions.map(question => (
          <button key={question.id} type="button" className="btn subtle" aria-pressed={selected === question.id}
            onClick={() => void ask(question.id)}>{shortcutLabels[question.id]}</button>
        ))}
      </div>
    </section>
  );
}
