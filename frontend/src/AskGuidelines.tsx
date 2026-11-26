import { VoiceQuestion } from "./VoiceQuestion";
import { AskRecords } from "./AskRecords";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useWorkspaceGreeting } from "./workspaceGreeting";

type Language = "hi" | "en";
type Reference = { document_id: number; title: string; version: string | null; page: number };
type Answer = { answer: string; references: Reference[] };
type Exchange = Answer & { question: string; language: Language };
type EmailDraft = { to: string; subject: string; body: string; message: string };

const followupQuestions: Record<Language, string[]> = {
  en: [
    "Can you explain that in simpler words?",
    "What should I cover in a follow-up conversation?",
    "Which guideline passage supports this?",
  ],
  hi: [
    "क्या आप इसे आसान शब्दों में समझा सकते हैं?",
    "दोबारा बात करते समय किन बातों पर ध्यान दूँ?",
    "दिशानिर्देश के किस हिस्से में यह जानकारी है?",
  ],
};

const suggestions: Record<Language, string[]> = {
  en: [
    "What is anemia and what does a hemoglobin test measure?",
    "How are hemoglobin levels interpreted by age and pregnancy status?",
    "What foods help prevent anemia during pregnancy?",
    "What do the guidelines say about iron and folic acid during pregnancy?",
    "What are the signs of anemia in children and how is it checked?",
  ],
  hi: [
    "एनीमिया क्या है और हीमोग्लोबिन जाँच क्या बताती है?",
    "उम्र और गर्भावस्था के अनुसार हीमोग्लोबिन का स्तर कैसे समझें?",
    "गर्भावस्था में एनीमिया से बचाव के लिए क्या खाना चाहिए?",
    "गर्भावस्था में आयरन और फोलिक एसिड की गोलियों के बारे में दिशानिर्देश क्या कहते हैं?",
    "बच्चों में एनीमिया के क्या लक्षण हो सकते हैं और जाँच कैसे होती है?",
  ],
};

type AskProps = {
  accountName: string;
  backLabel: string;
  onSessionExpired: () => void;
  isAdmin: boolean;
};

export function AskGuidelines(props: AskProps) {
  const [mode, setMode] = useState<"guidelines" | "records">("guidelines");

  return <div className="ask-source-shell">
    <div className="ask-source-tabs" role="tablist" aria-label="Ask SakhiCare source">
      <button id="ask-guidelines-tab" type="button" role="tab" aria-selected={mode === "guidelines"}
        aria-controls="ask-guidelines-panel" onClick={() => setMode("guidelines")}>Guidelines</button>
      <button id="ask-records-tab" type="button" role="tab" aria-selected={mode === "records"}
        aria-controls="ask-records-panel" onClick={() => setMode("records")}>Patient records</button>
    </div>
    <div id="ask-guidelines-panel" role="tabpanel" aria-labelledby="ask-guidelines-tab" hidden={mode !== "guidelines"}>
      <GuidelineChat {...props} active={mode === "guidelines"} />
    </div>
    <div id="ask-records-panel" role="tabpanel" aria-labelledby="ask-records-tab" hidden={mode !== "records"}>
      {mode === "records" && <AskRecords {...props} />}
    </div>
  </div>;
}

function GuidelineChat({ accountName, backLabel, onSessionExpired, active, isAdmin }:
  AskProps & { active: boolean }) {
  const greeting = useWorkspaceGreeting(accountName);
  const heading = useRef<HTMLHeadingElement>(null);
  const request = useRef<AbortController | null>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const thread = useRef<HTMLDivElement>(null);
  const latestQuestion = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    window.scrollTo(0, 0);
    heading.current?.focus({ preventScroll: true });
    return () => request.current?.abort();
  }, []);
  const [language, setLanguage] = useState<Language>("hi");
  const [question, setQuestion] = useState(() => suggestions[language][0]);
  const [asked, setAsked] = useState("");
  const [suggestionIndex, setSuggestionIndex] = useState(0);
  const [conversation, setConversation] = useState<Exchange[]>([]);
  const [emailDrafts, setEmailDrafts] = useState<Record<number, EmailDraft>>({});
  const [emailDraftOpen, setEmailDraftOpen] = useState<Record<number, boolean>>({});
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const panel = thread.current;
    const latest = latestQuestion.current;
    if (asked && panel && latest) {
      panel.scrollTop += latest.getBoundingClientRect().top - panel.getBoundingClientRect().top;
    }
  }, [asked, conversation.length, pending]);

  function newChat() {
    setConversation([]);
    setEmailDrafts({});
    setEmailDraftOpen({});
    setSuggestionIndex(0);
    setAsked("");
    setError("");
    setQuestion(suggestions[language][0]);
    composer.current?.focus();
  }

  function toggleEmailDraft(index: number, exchange: Exchange) {
    if (emailDrafts[index]) {
      setEmailDraftOpen(current => ({ ...current, [index]: !current[index] }));
      return;
    }
    setEmailDrafts(current => {
      const uniqueReferences = Array.from(new Map(exchange.references.map(reference => [
        `${reference.document_id}:${reference.page}`, reference,
      ])).values());
      const referenceText = uniqueReferences.map(reference =>
        `${reference.title}${reference.version ? `, version ${reference.version}` : ""}, page ${reference.page}`
      ).join("\n");
      const hindi = exchange.language === "hi";
      const body = hindi
        ? `नमस्ते टीम,\n\nSakhiCare के दिशानिर्देशों के आधार पर यह जानकारी साझा कर रहा/रही हूँ:\n\n${exchange.answer}\n\nदिशानिर्देश स्रोत:\n${referenceText}\n\nकृपया इस ईमेल में मरीजों के नाम, फोन नंबर, पहचान संख्या या अन्य पहचान बताने वाली जानकारी शामिल न करें। मरीज-विशिष्ट निर्णय के लिए ANM या योग्य चिकित्सक से सलाह लें।\n\nसादर,\n${accountName}`
        : `Hello team,\n\nSharing this information based on SakhiCare's team guidelines:\n\n${exchange.answer}\n\nGuideline source:\n${referenceText}\n\nPlease keep patient names, phone numbers, IDs, and other identifying details out of this email. For patient-specific decisions, consult the ANM or a qualified clinician.\n\nRegards,\n${accountName}`;
      return { ...current, [index]: {
        to: "",
        subject: hindi ? "SakhiCare: दिशानिर्देश फॉलो-अप" : "SakhiCare guidance follow-up",
        body,
        message: "",
      } };
    });
    setEmailDraftOpen(current => ({ ...current, [index]: true }));
  }

  function updateEmailDraft(index: number, field: "to" | "subject" | "body", value: string) {
    setEmailDrafts(current => {
      const draft = current[index];
      return draft ? { ...current, [index]: { ...draft, [field]: value, message: "" } } : current;
    });
  }

  async function copyEmailDraft(index: number) {
    const draft = emailDrafts[index];
    if (!draft) return;
    const text = `${draft.to.trim() ? `To: ${draft.to.trim()}\n` : ""}Subject: ${draft.subject.trim()}\n\n${draft.body}`;
    try {
      await navigator.clipboard.writeText(text);
      setEmailDrafts(current => current[index]
        ? { ...current, [index]: { ...current[index], message: "Draft copied." } }
        : current);
    } catch {
      setEmailDrafts(current => current[index]
        ? { ...current, [index]: { ...current[index], message: "Clipboard access is unavailable. Select the draft text and copy it." } }
        : current);
    }
  }

  function openEmailApp(index: number) {
    const draft = emailDrafts[index];
    if (!draft) return;
    const recipients = draft.to.split(/[;,]/).map(address => address.trim()).filter(Boolean);
    if (recipients.some(address => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address))) {
      setEmailDrafts(current => current[index]
        ? { ...current, [index]: { ...current[index], message: "Enter valid email addresses separated by commas, or leave To blank and choose recipients in your email app." } }
        : current);
      return;
    }
    const to = recipients.map(encodeURIComponent).join(",");
    const mailto = `mailto:${to}?subject=${encodeURIComponent(draft.subject)}&body=${encodeURIComponent(draft.body)}`;
    window.location.href = mailto;
    setEmailDrafts(current => current[index]
      ? { ...current, [index]: { ...current[index], message: "Email app opened. Review the draft and send it manually." } }
      : current);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (pending || text.length < 3) return;
    const controller = new AbortController();
    request.current = controller;
    setPending(true);
    setAsked(text);
    setError("");

    try {
      const response = await fetch("/backend-api/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-SakhiCare-Session": "1" },
        body: JSON.stringify({
          question: text, source: "guidelines", language,
          previous_questions: conversation.slice(-3).map(exchange => exchange.question),
        }),
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(130000)]),
      });
      if (response.status === 401) {
        onSessionExpired();
      } else if (!response.ok) {
        const payload = await response.json().catch(() => null);
        if (!controller.signal.aborted) {
          const code = payload?.detail?.code;
          if (code === "reindex_required") {
            setError("Guidelines need to be reindexed after an embedding model change. Contact your Admin.");
          } else if (code === "model_unavailable") {
            setError("The configured AI model is unavailable. Ask your Admin to check the model settings.");
          } else {
            setError("Guideline search is unavailable. Please try again.");
          }
        }
      } else {
        const reply = await response.json() as Answer;
        setSuggestionIndex(0);
        setConversation(current => [...current, { ...reply, question: text, language }]);
        setQuestion(current => current.trim() === text ? "" : current);
      }
    } catch {
      if (!controller.signal.aborted) setError("Could not reach guideline search. Check your connection and try again.");
    } finally {
      if (!controller.signal.aborted) setPending(false);
    }
  }

  const hasConversation = Boolean(asked);
  const choices = conversation.length > 0
    ? followupQuestions[language]
    : suggestions[language];

  const suggestionPanel = !pending && (
    <div className="ask-suggestions">
        <h2>{conversation.length ? "Suggested follow-ups" : "Example questions"}</h2>
        <button className="btn subtle ask-suggestion" type="button" lang={language}
          onClick={() => {
            setQuestion(choices[suggestionIndex]);
            composer.current?.focus();
          }}>{choices[suggestionIndex]}</button>
        <div className="ask-suggestion-nav">
          <button className="btn subtle" type="button" disabled={suggestionIndex === 0}
            onClick={() => setSuggestionIndex(index => index - 1)} aria-label="Previous suggested question">&#8592;</button>
          <span role="status">{suggestionIndex + 1} / {choices.length}</span>
          <button className="btn subtle" type="button" disabled={suggestionIndex === choices.length - 1}
            onClick={() => setSuggestionIndex(index => index + 1)} aria-label="Next suggested question">&#8594;</button>
        </div>
      </div>
  );

  return (
    <section className={hasConversation ? "ask-workspace ask-workspace-chat" : "ask-workspace"} data-ask-chat={!isAdmin ? "field" : undefined} aria-label="Ask SakhiCare">
      <header className="ask-heading">
        <div className="ask-heading-actions">
          <a className="ask-back" href="#today">
            <span aria-hidden="true">&#8592;</span> {backLabel}
          </a>
          <h1 id="ask-title" ref={heading} tabIndex={-1}>Ask SakhiCare</h1>
          <details className="ask-help">
            <summary aria-label="About Ask SakhiCare"><span aria-hidden="true">i</span></summary>
            <p>Ask about Hb testing, counselling, or follow-up using your team's guidelines.</p>
          </details>
          {hasConversation && <button className="btn subtle" type="button" onClick={newChat} disabled={pending}>New chat</button>}
        </div>
        {!hasConversation && <p className="ask-greeting">
          <span>{greeting.date}</span><span aria-hidden="true">&middot;</span><strong>{greeting.title}</strong>
        </p>}
      </header>
      <div className="ask-thread" ref={thread} role="region" aria-label="Conversation"
        tabIndex={hasConversation ? 0 : undefined}>
        {!isAdmin && !hasConversation && (
          <div className="ask-field-empty">
            <span aria-hidden="true">&#9993;</span>
            <h2>Ask SakhiCare anything</h2>
            <p>Find guidance on anemia screening, counselling, and referrals.</p>
          </div>
        )}
        {conversation.map((exchange, index) => {
          const references = Array.from(new Map(exchange.references.map(reference => [
            `${reference.document_id}:${reference.page}`, reference,
          ])).values());
          return <section className="ask-exchange" key={index} aria-label={exchange.question}>
            <p className="ask-question-bubble" ref={!pending && index === conversation.length - 1 ? latestQuestion : undefined}>
              {exchange.question}
            </p>
            <div className="panel ask-answer" lang={exchange.language} aria-live="polite">
              <p className="ask-answer-text">{exchange.answer}</p>
              {references.length > 0 && <details className="ask-sources" lang="en">
                <summary>Guideline sources ({references.length})</summary>
                <ul>{references.map(reference => <li key={`${reference.document_id}:${reference.page}`}>
                  {reference.title}{reference.version && <> &middot; Version {reference.version}</>} &middot; Page {reference.page}
                </li>)}</ul>
              </details>}
              {references.length > 0 && <div className="ask-email-tools">
                <button className="btn subtle" type="button" aria-expanded={Boolean(emailDraftOpen[index])}
                  onClick={() => toggleEmailDraft(index, exchange)}>
                  {emailDraftOpen[index] ? "Hide email draft" : "Draft email"}
                </button>
                <small>Creates an editable staff email from this guideline answer. Patient records are not included.</small>
              </div>}
              {emailDraftOpen[index] && emailDrafts[index] && <section className="ask-email-draft" aria-label="Editable email draft">
                <div className="ask-email-draft-head"><span className="ask-email-badge">DRAFT</span><strong>Review before sending</strong></div>
                <label>To
                  <input type="text" value={emailDrafts[index].to} maxLength={320}
                    placeholder="Email addresses, separated by commas (optional)"
                    onChange={event => updateEmailDraft(index, "to", event.target.value)} />
                </label>
                <label>Subject
                  <input type="text" value={emailDrafts[index].subject} maxLength={180}
                    onChange={event => updateEmailDraft(index, "subject", event.target.value)} />
                </label>
                <label>Message
                  <textarea rows={10} value={emailDrafts[index].body} maxLength={10000}
                    onChange={event => updateEmailDraft(index, "body", event.target.value)} />
                </label>
                <p className="ask-email-privacy">Staff communication only. Keep patient names, phone numbers, IDs, and other identifying details out of email.</p>
                {emailDrafts[index].message && <p className="ask-email-status" role="status">{emailDrafts[index].message}</p>}
                <div className="ask-email-actions">
                  <button className="btn subtle" type="button" onClick={() => void copyEmailDraft(index)}>Copy draft</button>
                  <button className="btn" type="button" onClick={() => openEmailApp(index)}>Open email app</button>
                </div>
                <small>Your email app opens with this draft. Review it and press Send there when you are ready.</small>
              </section>}
            </div>
          </section>;
        })}
        {(pending || error) && <p ref={latestQuestion} className="ask-question-bubble">{asked}</p>}
        {pending && <p className="ask-chat-status" role="status">Looking up guidelines&hellip;</p>}
        {error && <p className="signup-error" role="alert">{error}</p>}
      </div>
      <div className={hasConversation ? "ask-dock ask-dock-active" : "ask-dock"}>
        {hasConversation && (isAdmin ? suggestionPanel : <details className="ask-field-examples"><summary>Suggested follow-ups</summary>{suggestionPanel}</details>)}
      <form className="panel ask-composer" onSubmit={submit} aria-busy={pending}>
        <label htmlFor="guideline-question">{hasConversation ? "Ask a follow-up" : "Your question"}</label>
        <textarea ref={composer} id="guideline-question" value={question} maxLength={2000} minLength={3} required
          rows={2} aria-describedby="question-guidance" placeholder={hasConversation ? "Ask a follow-up..." : "Ask about anemia protocols..."}
          onChange={event => setQuestion(event.target.value)} />
        <small id="question-guidance">Keep patient details out. Voice input uses your browser's speech service.</small>
        <div className="ask-actions">
          <label>
            <select aria-label="Answer language" value={language} onChange={event => {
              const nextLanguage = event.target.value as Language;
              const selectedExample = suggestions[language].indexOf(question);
              const selectedFollowup = followupQuestions[language].indexOf(question);
              if (selectedExample >= 0) setQuestion(suggestions[nextLanguage][selectedExample]);
              if (selectedFollowup >= 0) setQuestion(followupQuestions[nextLanguage][selectedFollowup]);
              setLanguage(nextLanguage);
            }}>
              <option value="hi" lang="hi">&#2361;&#2367;&#2344;&#2381;&#2342;&#2368;</option>
              <option value="en">English</option>
            </select>
          </label>
          <VoiceQuestion active={active} disabled={pending} language={language}
            onTranscript={text => {
              setQuestion(text.slice(0, 2000));
              composer.current?.focus();
            }} />
          <button className="btn ask-send" type="submit" disabled={pending || question.trim().length < 3}>
            <span className="ask-send-label">{pending ? "Searching..." : hasConversation ? "Send" : "Ask question"}</span>
            <span className="ask-send-icon" aria-hidden="true">&#8593;</span>
          </button>
        </div>
      </form>
        {!hasConversation && (isAdmin ? suggestionPanel : <details className="ask-field-examples"><summary>Example questions</summary>{suggestionPanel}</details>)}
      </div>
    </section>
  );
}
