import { useEffect, useState } from "react";

const dayFormat = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  month: "long",
  day: "numeric",
});

export function workspaceGreeting(name: string, now: Date) {
  const hour = now.getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const firstName = name.trim().split(/\s+/)[0];
  return {
    date: dayFormat.format(now),
    title: firstName ? `${greeting}, ${firstName}` : greeting,
  };
}

export function useWorkspaceGreeting(name: string) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);
  return workspaceGreeting(name, now);
}
