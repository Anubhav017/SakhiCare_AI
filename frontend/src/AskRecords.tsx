import { useEffect, useRef, useState } from "react";

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

type ConversationTurn = { id: number; question: string; kind: "read" | "change"; answer?: RecordAnswer; error?: string };

function isChangeRequest(question: string) {
  return /^\s*(?:please\s+)?(?:add|create|register|update|edit|save|schedule|complete|mark|cancel|archive|set|change|correct|remove|delete|close|confirm|withdraw)\b/i.test(question) ||
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

function suggestedQuestions(answer: RecordAnswer | undefined, isAdmin: boolean): string[] {
  if (!answer) return isAdmin
    ? ["How many patients does my team have?", "Which follow-ups are due today or overdue?", "How many patients does each ASHA have?"]
    : ["How many patients do I have?", "Which follow-ups are due today or overdue?", "Show my patients with high risk"];
  if (answer.count !== undefined) return isAdmin
    ? ["Which patients have high risk?", "Which follow-ups are due today or overdue?", "Show active care pathways"]
    : ["Which of my patients have high risk?", "Which follow-ups are due today or overdue?", "Show active care pathways"];
  if (answer.patients) return ["Which patients have high risk?", "Which patients have Hb screening pending?", "Which follow-ups are due today or overdue?"];
  if (answer.followups) return ["Show upcoming follow-ups", "Show active care pathways", "Which referrals are still open?"];
  if (answer.referrals) return ["Which referrals have an outcome?", "Which follow-ups are due today or overdue?", "Show active care pathways"];
  if (answer.pathways) return ["Which patients have open referrals?", "Which follow-ups are due today or overdue?", "How many patients do I have?"];
  if (answer.workers) return ["Which patients have high risk?", "Which follow-ups are due today or overdue?", "Show active care pathways"];
  return ["How many patients do I have?", "Which follow-ups are due today or overdue?", "Show active care pathways"];
}

export function AskRecords({ isAdmin, backLabel, onSessionExpired }: {
  isAdmin: boolean;
  backLabel: string;
  onSessionExpired: () => void;
}) {
  const [typedQuestion, setTypedQuestion] = useState("");
  const [inputMode, setInputMode] = useState<"ask" | "change">("ask");
  const [questionError, setQuestionError] = useState("");
  const [conversation, setConversation] = useState<ConversationTurn[]>([]);
  const [pendingQuestion, setPendingQuestion] = useState("");
  const turnId = useRef(0);
  const [pending, setPending] = useState(false);
  const [drafts, setDrafts] = useState<AskAction[]>([]);
  const [savingDraft, setSavingDraft] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  const conversationEnd = useRef<HTMLDivElement>(null);
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => {
    if (conversation.length) conversationEnd.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [conversation, pending]);

  useEffect(() => {
    let active = true;
    if (isAdmin) return () => { active = false; };
    fetch("/backend-api/api/ask/records/actions/pending", { cache: "no-store" })
      .then(async response => {
        if (response.status === 401) { onSessionExpired(); return []; }
        if (!response.ok) return [];
        return await response.json() as AskAction[];
      })
      .then(rows => { if (active && rows.length) setDrafts(rows); })
      .catch(() => {});
    return () => { active = false; };
  }, [isAdmin, onSessionExpired]);

  const questions: { id: Report; label: string }[] = [
    { id: "patient_count", label: isAdmin ? "How many patients does my team have?" : "How many patients do I have?" },
    { id: "due_followups", label: "Which follow-ups are due today or overdue?" },
    { id: "pathway_status", label: "Show active care pathways" },
  ];
  if (isAdmin) questions.push({ id: "patients_by_worker", label: "How many patients does each ASHA have?" });

  async function ask(question: string, worker?: string, submittedDraft?: string) {
    setQuestionError("");
    const id = ++turnId.current;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const previousQuestions = conversation
      .filter(turn => turn.kind === "read" && turn.answer)
      .slice(-3)
      .map(turn => turn.question);
    setConversation(current => [...current, { id, question, kind: "read" }]);
    setPendingQuestion(question);
    setPending(true);
    try {
      const response = await fetch("/backend-api/api/ask/records", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, worker, previous_questions: previousQuestions }),
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]),
        cache: "no-store",
      });
      if (controller.signal.aborted) return;
      if (response.status === 401) return onSessionExpired();
      if (worker && (response.status === 404 || response.status === 409)) {
        const { detail } = await response.json();
        if (!controller.signal.aborted) setConversation(current => current.map(turn => turn.id === id ? { ...turn, error: detail } : turn));
        return;
      }
      if (!response.ok) throw new Error(await responseMessage(response, "I couldn't read those records. Please try again."));
      const result = await response.json() as RecordAnswer;
      if (!controller.signal.aborted) {
        setConversation(current => current.map(turn => turn.id === id ? { ...turn, answer: result } : turn));
        if (submittedDraft !== undefined) {
          setTypedQuestion(current => current === submittedDraft ? "" : current);
        }
      }
    } catch {
      if (!controller.signal.aborted) setConversation(current => current.map(turn => turn.id === id ? { ...turn, error: "Could not load records. Please try again." } : turn));
    } finally {
      if (!controller.signal.aborted) { setPending(false); setPendingQuestion(""); }
    }
  }

  async function proposeChange(question: string) {
    setQuestionError("");
    const id = ++turnId.current;
    setConversation(current => [...current, { id, question, kind: "change" }]);
    setPendingQuestion(question);
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
      setConversation(current => current.map(turn => turn.id === id ? {
        ...turn,
        answer: { answer: "I prepared a change preview. Nothing has been saved yet. Review the details below, then choose Save change or Cancel." },
      } : turn));
      setTypedQuestion(current => current === question ? "" : current);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Could not prepare a safe change preview.";
      setQuestionError(message);
      setConversation(current => current.map(turn => turn.id === id ? { ...turn, error: message } : turn));
    } finally {
      setPending(false);
      setPendingQuestion("");
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
    <section className="ask-workspace records-workspace conversational-ask" aria-labelledby="records-title">
      <header className="ask-heading ask-heading-actions">
        <a className="ask-back" href="#today"><span aria-hidden="true">&#8592;</span> {backLabel}</a>
        <div><h1 id="records-title">Ask SakhiCare</h1><p>Ask about your patients, care, and follow-ups.</p></div>
      </header>
      <div className="ask-conversation" aria-live="polite" aria-busy={pending}>
        {!conversation.length && <section className="ask-welcome">
          <span className="ask-welcome-mark" aria-hidden="true">✦</span>
          <h2>How can I help with your care work?</h2>
          <p>Ask in your own words. I can look up assigned patient records, screenings, referrals, follow-ups, and care pathways.</p>
          <div className="ask-suggestions" aria-label="Suggested questions">
            {suggestedQuestions(undefined, isAdmin).map(question => <button key={question} className="btn subtle" type="button" onClick={() => void ask(question)}>{question}</button>)}
          </div>
        </section>}
        {conversation.map(turn => <article className="ask-turn" key={turn.id}>
          <div className="records-question-bubble" aria-label="Your question">{turn.question}</div>
          {turn.error ? <p className="ask-conversation-error" role="alert">{turn.error}</p> : turn.answer ? <>
            <section className="panel records-result ask-response">
              <span className="ask-response-label"><span aria-hidden="true">✦</span> SakhiCare</span>
              {turn.answer.answer && <p>{turn.answer.answer}</p>}
              {turn.answer.count !== undefined && <p className="records-total">{isAdmin ? "Your team has" : "You have"} <strong>{turn.answer.count}</strong> assigned patients.</p>}
              {turn.answer.patients && (turn.answer.patients.length ? <ul>{turn.answer.patients.map(patient => <li key={patient.id}>
                <a className="patient-link" href={`#patient/${patient.id}`}>{patient.name}</a>
                {patient.village && <> &middot; {patient.village}</>}
                {patient.age != null && <> &middot; {patient.age} years</>}
                {patient.risk && <> &middot; ASHA-recorded {patient.risk} risk</>}
                {patient.anemia_status === "confirmed" && <> &middot; ASHA-recorded anemia assessment: confirmed</>}
              </li>)}</ul> : <p>No matching patients.</p>)}
              {turn.answer.workers && (turn.answer.workers.length ? <ul>{turn.answer.workers.map((row, index) => <li key={index}>{row.worker} &middot; {row.count} patients</li>)}</ul> : <p>No ASHA workers assigned.</p>)}
              {turn.answer.followups && (turn.answer.followups.length ? <ul>{turn.answer.followups.map(row => <li key={row.id}>
                <a className="patient-link" href={`#patient/${row.patient_id}/followups`}>{row.patient}</a>{" "} &middot; {row.title} &middot; <time dateTime={row.due_date}>{row.due_date}</time>
              </li>)}</ul> : <p>No matching follow-ups.</p>)}
              {turn.answer.referrals && (turn.answer.referrals.length ? <ul>{turn.answer.referrals.map(row => <li key={row.id}>
                <a className="patient-link" href={`#patient/${row.patient_id}`}>{row.patient}</a>{" "} &middot; {row.facility} &middot; {row.status}{row.outcome && <> &middot; {row.outcome}</>}
              </li>)}</ul> : <p>No matching referrals.</p>)}
              {turn.answer.pathways && (turn.answer.pathways.length ? <div className="records-pathways">{turn.answer.pathways.map(run => <article key={run.id}>
                <h3><a className="patient-link" href={`#patient/${run.patient_id}`}>{run.patient}</a> · {run.title}</h3>
                <span className={`pill ${run.status === "completed" ? "done" : "pending"}`}>{run.status}</span>
                {run.steps?.length ? <ol>{run.steps.map((step, index) => <li key={index}>{step.title} · {step.status}</li>)}</ol> : null}
              </article>)}</div> : <p>No matching care pathways.</p>)}
              {turn.answer.truncated && <p>Showing the first 50 matches. Use the Patients page to browse the full list.</p>}
            </section>
            <div className="ask-suggestions ask-turn-suggestions" aria-label="Suggested follow-up questions">
              {suggestedQuestions(turn.answer, isAdmin).map(question => <button key={question} className="btn subtle" type="button" disabled={pending} onClick={() => void ask(question)}>{question}</button>)}
            </div>
          </> : pending && pendingQuestion === turn.question ? <p className="ask-thinking" role="status"><span aria-hidden="true">✦</span> Checking your records…</p> : null}
        </article>)}
        <div ref={conversationEnd} />
      </div>
      {!isAdmin && drafts.map(draft => <section className={`panel ask-action-review ask-action-${draft.status}`} key={draft.id}
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
      <form className="panel ask-composer records-composer ask-chat-composer" onSubmit={event => {
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
        if (!isAdmin && requestText && (inputMode === "change" || isChangeRequest(typedQuestion))) {
          setTypedQuestion("");
          void proposeChange(typedQuestion.trim());
        } else if (match) {
          setTypedQuestion("");
          void ask(match.id, undefined, typedQuestion);
        } else if (worker) {
          setTypedQuestion("");
          void ask("worker_patients", worker.trim(), typedQuestion);
        } else if (requestText) {
          setTypedQuestion("");
          void ask(typedQuestion.trim(), undefined, typedQuestion);
        }
      }}>
        <label htmlFor="records-question" className="visually-hidden">{inputMode === "change" ? "Describe the change" : "Ask SakhiCare"}</label>
        <textarea id="records-question" value={typedQuestion} maxLength={500}
          placeholder={inputMode === "change" ? "Describe the change you want to prepare…" : "Ask anything about your patients or care work…"} onChange={event => {
            setTypedQuestion(event.target.value);
            setQuestionError("");
          }} />
        {!isAdmin && <p className="ask-action-hint">Record changes are only saved after you review the preview and select Save.</p>}
        <div className="ask-actions">
          {!isAdmin && <button type="button" className="btn subtle ask-change-toggle" aria-pressed={inputMode === "change"}
            disabled={pending} onClick={() => setInputMode(current => current === "change" ? "ask" : "change")}>
            {inputMode === "change" ? "Cancel change request" : "+ Prepare a record change"}
          </button>}
          <button className="btn ask-send" type="submit" disabled={!typedQuestion.trim() || pending}>
            {pending ? "Thinking…" : inputMode === "change" ? "Preview change" : "Ask"}
          </button>
        </div>
        {questionError && <p className="signup-error" role="alert">{questionError}</p>}
      </form>
    </section>
  );
}
