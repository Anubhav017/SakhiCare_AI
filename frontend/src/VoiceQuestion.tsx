import { useEffect, useRef, useState } from "react";

type Recognition = {
  lang: string;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
};

const speechWindow = window as Window & {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
};

export function VoiceQuestion({ active, disabled, language, onTranscript }: {
  active: boolean;
  disabled: boolean;
  language: "hi" | "en";
  onTranscript: (text: string) => void;
}) {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const session = useRef<Recognition | null>(null);
  const RecognitionAPI = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;

  useEffect(() => () => {
    const recognition = session.current;
    if (recognition) {
      session.current = null;
      recognition.abort();
    }
  }, [active, disabled, language]);

  useEffect(() => {
    setListening(false);
    setError("");
  }, [active, disabled, language]);

  function toggleVoice() {
    if (session.current) {
      session.current.stop();
      return;
    }
    if (!RecognitionAPI) return;
    const recognition = new RecognitionAPI();
    recognition.lang = language === "hi" ? "hi-IN" : "en-IN";
    setError("");
    recognition.onresult = event => {
      if (session.current === recognition) onTranscript(event.results[0]?.[0]?.transcript ?? "");
    };
    recognition.onerror = () => {
      if (session.current === recognition) setError("Voice input unavailable. Check microphone access or type your question.");
    };
    recognition.onend = () => {
      if (session.current !== recognition) return;
      session.current = null;
      setListening(false);
    };
    try {
      session.current = recognition;
      recognition.start();
      setListening(true);
    } catch {
      session.current = null;
      setError("Could not start voice input. You can type your question.");
    }
  }

  if (!active || !RecognitionAPI) return null;
  return <div className="ask-voice">
    <button className="btn subtle" type="button" disabled={disabled} aria-pressed={listening}
      onClick={toggleVoice}>{listening ? "Stop listening" : "Use mic"}</button>
    <small>Browser speech service. Keep patient details out.</small>
    {error && <small role="alert">{error}</small>}
  </div>;
}
