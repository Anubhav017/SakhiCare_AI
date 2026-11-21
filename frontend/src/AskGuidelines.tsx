import { VoiceQuestion } from "./VoiceQuestion";
import { AskRecords } from "./AskRecords";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useWorkspaceGreeting } from "./workspaceGreeting";

type Language = "hi" | "en";
type Reference = { document_id: number; title: string; version: string | null; page: number };
type Answer = { answer: string; references: Reference[] };
type Exchange = Answer & { question: string; language: Language };

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

  const sourceControl = (
    <select className="ask-source-select" aria-label="Answer source" value={mode}
      onChange={event => setMode(event.target.value === "records" ? "records" : "guidelines")}>
      <option value="guidelines">Guidelines</option>
      <option value="records">Records</option>
    </select>
  );

  return <>
    <div hidden={mode !== "guidelines"}>
      <GuidelineChat {...props} active={mode === "guidelines"} sourceControl={sourceControl} />
    </div>
    {mode === "records" && <AskRecords {...props} sourceControl={sourceControl} />}
  </>;
}

function GuidelineChat({ accountName, backLabel, onSessionExpired, active, sourceControl, isAdmin }:
  AskProps & { active: boolean; sourceControl: ReactNode }) {
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
    setSuggestionIndex(0);
    setAsked("");
    setError("");
    setQuestion(suggestions[language][0]);
    composer.current?.focus();
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
            setError("Guidelines need to be reindexed after an embedding model change. Contact your Super Admin.");
          } else if (code === "model_unavailable") {
            setError("The configured AI model is unavailable. Ask your Super Admin to check the model settings.");
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
          {sourceControl}
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
