"use client";

// Proposal text with its [evidence_id] citations turned into numbered chips. Hovering or focusing a
// chip shows the evidence behind the claim (keyboard accessible: chips are buttons).
import { useId, useState } from "react";
import type { Evidence } from "@/lib/types";
import { Badge } from "./ui";

const CITATION = /\[([A-Za-z0-9_\-]+:[^\]\s]+)\]/g;

export function EvidenceChip({ n, id, evidence }: { n: number; id: string; evidence?: Evidence }) {
  const [open, setOpen] = useState(false);
  const tip = useId();
  return (
    <span className="relative inline-block align-baseline">
      <button
        type="button"
        aria-describedby={open ? tip : undefined}
        aria-label={`Evidence ${n}`}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="mx-0.5 rounded bg-emerald-100 px-1 text-[11px] font-semibold text-emerald-800 hover:bg-emerald-200 focus-visible:outline-2 focus-visible:outline-emerald-600"
      >
        {n}
      </button>
      {open && (
        <span
          id={tip}
          role="tooltip"
          className="absolute left-1/2 top-full z-20 mt-2 block w-72 max-w-[80vw] -translate-x-1/2 rounded-lg border border-slate-200 bg-white p-3 text-left text-xs font-normal text-slate-700 shadow-lg"
        >
          {evidence ? (
            <>
              <span className="mb-1 flex flex-wrap items-center gap-1">
                <Badge tone="info">{evidence.type.replace("_", " ")}</Badge>
                {evidence.date && <Badge>{evidence.date}</Badge>}
                {evidence.outcome && <Badge tone={evidence.outcome === "won" ? "good" : "neutral"}>{evidence.outcome}</Badge>}
              </span>
              <span className="block font-medium text-slate-900">{evidence.title}</span>
              <span className="mt-1 block max-h-40 overflow-y-auto whitespace-pre-wrap">{plain(evidence.text).slice(0, 600)}</span>
            </>
          ) : (
            <span className="text-rose-700">Cited id {id} is not in the retrieved evidence.</span>
          )}
        </span>
      )}
    </span>
  );
}

/** Render text, replacing citations with numbered evidence chips. */
export function CitedText({ text, evidence, order }: { text: string; evidence: Record<string, Evidence>; order?: string[] }) {
  const numbers = new Map<string, number>();
  (order ?? []).forEach((id) => numbers.set(id, numbers.size + 1));
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(CITATION)) {
    parts.push(text.slice(last, m.index));
    const id = m[1];
    if (!numbers.has(id)) numbers.set(id, numbers.size + 1);
    parts.push(<EvidenceChip key={`${m.index}`} n={numbers.get(id)!} id={id} evidence={evidence[id]} />);
    last = (m.index ?? 0) + m[0].length;
  }
  parts.push(text.slice(last));
  return <span className="whitespace-pre-wrap">{parts}</span>;
}

/** Evidence text is Markdown (case studies, READMEs); show it as plain text in tooltips. */
function plain(text: string) {
  return text.replace(/^#+\s*/gm, "").replace(/[*_`]/g, "").replace(/^\s*[-+]\s+/gm, "• ");
}

export function stripCitations(text: string) {
  return text.replace(/\s?\[[A-Za-z0-9_\-]+:[^\]\s]+\]/g, "");
}
