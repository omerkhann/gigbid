"use client";

// Live agent progress over Server-Sent Events, shared by every component that listens.
import { useEffect, useRef, useState } from "react";
import { EVENTS_URL } from "./api/client";
import type { RunEvent } from "./types";

type Listener = (e: RunEvent) => void;
const listeners = new Set<Listener>();
let source: EventSource | null = null;
let connected = false;
const connectionListeners = new Set<(c: boolean) => void>();

function ensureSource() {
  if (source || typeof window === "undefined") return;
  source = new EventSource(EVENTS_URL, { withCredentials: true });
  source.onopen = () => setConnected(true);
  source.onerror = () => setConnected(false); // EventSource reconnects by itself
  source.onmessage = (msg) => {
    try {
      const event = JSON.parse(msg.data) as RunEvent;
      listeners.forEach((l) => l(event));
    } catch {
      /* ignore keep-alives and malformed lines */
    }
  };
}

function setConnected(c: boolean) {
  connected = c;
  connectionListeners.forEach((l) => l(c));
}

/** Call `onEvent` for every live event (optionally only for one thread). */
export function useRunEvents(onEvent: Listener, threadId?: string) {
  const ref = useRef(onEvent);
  useEffect(() => {
    ref.current = onEvent;
  });
  useEffect(() => {
    ensureSource();
    const l: Listener = (e) => {
      if (!threadId || e.thread_id === threadId) ref.current(e);
    };
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  }, [threadId]);
}

export function useLiveConnection(): boolean {
  const [c, setC] = useState(connected);
  useEffect(() => {
    ensureSource();
    connectionListeners.add(setC);
    return () => {
      connectionListeners.delete(setC);
    };
  }, []);
  return c;
}
