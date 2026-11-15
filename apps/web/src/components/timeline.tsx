"use client";

// Node-by-node progress of one graph thread: saved events from the checkpoint, plus live events
// streamed while the worker runs it.
import { useState } from "react";
import { useRunEvents } from "@/lib/events";
import type { RunEvent } from "@/lib/types";
import { StatusBadge } from "./badges";

type Step = { node?: string; summary?: string; ms?: number; tokens?: number; live?: boolean };

const NODE_LABEL: Record<string, string> = {
  job_analyst: "Job Analyst", risk_assessor: "Risk Assessor", fit_matcher: "Fit Matcher", decide: "Bid / skip",
  pricing: "Pricing", writer: "Proposal Writer", verify_claims: "Claim check", critic: "Critic",
  compliance: "Compliance Guard", prepare_draft: "Draft + preview", approve: "Your approval", submit: "Submit",
  read_thread: "Read messages", classify: "Intent", offer_slots: "Calendar slots", draft_reply: "Draft reply",
  reply_compliance: "Compliance Guard", approve_reply: "Your approval", send_reply: "Send",
};

export function RunTimeline({ threadId, saved, onFinished }: { threadId: string; saved: Step[]; onFinished?: (e: RunEvent) => void }) {
  const [live, setLive] = useState<Step[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  useRunEvents((e) => {
    if (e.type === "node") setLive((l) => [...l, { ...e, live: true }]);
    else {
      setStatus(e.status ?? "awaiting_approval");
      onFinished?.(e);
    }
  }, threadId);

  const steps = [...saved, ...live];
  if (!steps.length) return <p className="text-sm text-slate-500">No steps yet. Live progress appears here while the agents work.</p>;
  return (
    <div>
      {status && <p className="mb-2 text-xs text-slate-500">Latest: <StatusBadge status={status} /></p>}
      <ol className="relative space-y-3 border-l border-slate-200 pl-4" aria-label="Agent steps">
        {steps.map((s, i) => (
          <li key={i} className="relative">
            <span className={`absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full ${s.summary === "failed" ? "bg-rose-500" : s.live ? "bg-emerald-500" : "bg-slate-400"}`} aria-hidden />
            <p className="text-sm font-medium text-slate-800">
              {NODE_LABEL[s.node ?? ""] ?? s.node}
              {s.live && <span className="ml-2 text-xs font-normal text-emerald-700">live</span>}
            </p>
            <p className="text-xs text-slate-600">{s.summary}</p>
            {(s.ms != null || s.tokens) && (
              <p className="text-[11px] text-slate-400">
                {s.ms != null && `${(s.ms / 1000).toFixed(1)} s`}{s.tokens ? ` · ${s.tokens.toLocaleString()} tokens` : ""}
              </p>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
