import { useEffect, useRef, useState } from "react";

type Report = "patient_count" | "due_followups" | "patients_by_worker";
type Question = Report | "worker_patients";
type RecordAnswer =
  | { worker: string; total: number; patients: { id: number; name: string }[] }
  | { count: number }
  | { workers: { worker: string; count: number }[] }
  | { total: number; followups: { id: number; patient_id: number; patient: string; title: string; due_date: string }[] };

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
};

export function AskRecords({ isAdmin, backLabel, onSessionExpired }: {
  isAdmin: boolean;
  backLabel: string;
  onSessionExpired: () => void;
}) {
  const [typedQuestion, setTypedQuestion] = useState("");
  const [questionError, setQuestionError] = useState("");
  const [selected, setSelected] = useState<Question | null>(null);
  const [answer, setAnswer] = useState<RecordAnswer | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  const questions: { id: Report; label: string }[] = [
    { id: "patient_count", label: isAdmin ? "How many patients does my team have?" : "How many patients do I have?" },
    { id: "due_followups", label: "Which follow-ups are due today or overdue?" },
  ];
  if (isAdmin) questions.push({ id: "patients_by_worker", label: "How many patients does each ASHA have?" });

  async function ask(question: Question, worker?: string) {
    setQuestionError("");
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setSelected(question);
    setAnswer(null);
    setError("");
    setPending(true);
    try {
      const params = new URLSearchParams({ question });
      if (worker) params.set("worker", worker);
      const response = await fetch(`/backend-api/api/ask/records?${params}`, {
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]),
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
      if (!controller.signal.aborted) setAnswer(result);
    } catch {
      if (!controller.signal.aborted) setError("Could not load records. Select a question to try again.");
    } finally {
      if (!controller.signal.aborted) setPending(false);
    }
  }

  return (
    <section className="ask-workspace records-workspace" aria-labelledby="records-title">
      <header className="ask-heading ask-heading-actions">
        <a className="ask-back" href="#today"><span aria-hidden="true">&#8592;</span> {backLabel}</a>
        <h1 id="records-title">Ask Records</h1>
      </header>
      <div aria-live="polite" aria-busy={pending}>
        {pending && <p className="ask-answer" role="status">Looking up records&hellip;</p>}
        {error && <p className="signup-error" role="alert">{error}</p>}
        {answer && <section className="panel records-result">
          <h2>{"patients" in answer ? `Patients for ${answer.worker}` : questions.find(question => question.id === selected)?.label}</h2>
          {"patients" in answer && (answer.total ? <>
            <p>{answer.total} {answer.total === 1 ? "patient" : "patients"}</p>
            <ul>{answer.patients.map(patient => <li key={patient.id}>
              <a className="patient-link" href={`#patient/${patient.id}`}>{patient.name}</a>
            </li>)}</ul>
            {answer.total > answer.patients.length && <a href="#today">View the full team list</a>}
          </> : <p>No patients assigned.</p>)}
          {"count" in answer && <p className="records-total"><strong>{answer.count}</strong> {answer.count === 1 ? "patient" : "patients"}</p>}
          {"workers" in answer && (answer.workers.length ? <ul>
            {answer.workers.map((row, index) => <li key={index}>{row.worker} &middot; {row.count} patients</li>)}
          </ul> : <p>No ASHA workers assigned.</p>)}
          {"followups" in answer && (answer.total ? <>
            <p>{answer.total} due or overdue {answer.total === 1 ? "follow-up" : "follow-ups"}</p>
            <ul>{answer.followups.map(row => <li key={row.id}>
              <a className="patient-link" href={`#patient/${row.patient_id}/followups`}>{row.patient}</a>
              {" "} &middot; {row.title} &middot; <time dateTime={row.due_date}>{row.due_date}</time>
            </li>)}</ul>
            {answer.total > answer.followups.length && <a href="#followups">View all follow-ups</a>}
          </> : <p>No due or overdue follow-ups.</p>)}
        </section>}
      </div>
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
          void ask(match.id);
        } else if (worker) {
          void ask("worker_patients", worker.trim());
        } else {
          request.current?.abort();
          setPending(false);
          setSelected(null);
          setAnswer(null);
          setError("");
          setQuestionError(isAdmin
            ? 'Try a patient count, due follow-ups, or "ASHA name patient list".'
            : "Try asking for your patient count or due follow-ups.");
        }
      }}>
        <label htmlFor="records-question">Your records question</label>
        <div className="records-input-row">
        <input id="records-question" value={typedQuestion} maxLength={200}
          placeholder={questions[0].label} onChange={event => {
            setTypedQuestion(event.target.value);
            setQuestionError("");
          }} />
        <button className="btn" type="submit" disabled={!typedQuestion.trim()}>Ask</button>
        </div>
        {questionError && <p className="signup-error" role="alert">{questionError}</p>}
      </form>
      <div className="ask-records" role="group" aria-label="Quick questions">
        {questions.map(question => (
          <button key={question.id} type="button" className="btn subtle" aria-pressed={selected === question.id}
            onClick={() => { setTypedQuestion(question.label); void ask(question.id); }}>{shortcutLabels[question.id]}</button>
        ))}
      </div>
    </section>
  );
}
