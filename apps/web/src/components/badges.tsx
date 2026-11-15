// Status, risk, fit and decision indicators shared across pages.
import { Badge, type Tone } from "./ui";

const STATUS: Record<string, [string, Tone]> = {
  running: ["Analysing", "info"],
  awaiting_approval: ["Needs your approval", "accent"],
  submitted: ["Submitted", "good"],
  sent: ["Sent", "good"],
  skipped: ["Skipped", "neutral"],
  watching: ["Watching", "warn"],
  rejected: ["Rejected", "neutral"],
  needs_attention: ["Needs attention", "bad"],
  waiting_marketplace: ["Marketplace down", "warn"],
  dead_letter: ["Failed", "bad"],
  no_action: ["Nothing new", "neutral"],
};

const ACCENT: Record<Tone, string> = {
  accent: "bg-indigo-500", good: "bg-emerald-500", bad: "bg-rose-500", warn: "bg-amber-400", info: "bg-sky-500",
  neutral: "bg-slate-300",
};

/** Colour of the status edge on list cards (same mapping as the status badge). */
export function statusAccent(status?: string | null) {
  return ACCENT[(STATUS[status ?? ""] ?? ["", "neutral"])[1] as Tone];
}

export function StatusBadge({ status }: { status?: string | null }) {
  const [label, tone] = STATUS[status ?? ""] ?? [status ?? "unknown", "neutral" as Tone];
  return <Badge tone={tone}>{label}</Badge>;
}

export function RiskBadge({ score, flags = [] }: { score?: number | null; flags?: string[] }) {
  if (score == null) return <Badge>Risk —</Badge>;
  const tone: Tone = score > 0.7 ? "bad" : score >= 0.3 ? "warn" : "good";
  const label = score > 0.7 ? "High risk" : score >= 0.3 ? "Some risk" : "Low risk";
  return (
    <Badge tone={tone} title={flags.length ? flags.join(", ") : "No risk flags"}>
      {label} · {score.toFixed(2)}
      {flags.length > 0 && <span className="sr-only">Flags: {flags.join(", ")}</span>}
    </Badge>
  );
}

export function FitMeter({ score }: { score?: number | null }) {
  if (score == null) return <span className="text-xs text-slate-400">Fit —</span>;
  const pct = Math.round(score * 100);
  const color = score >= 0.55 ? "bg-emerald-500" : score >= 0.45 ? "bg-amber-500" : "bg-slate-400";
  return (
    <div className="flex items-center gap-2" aria-label={`Fit ${pct}%`}>
      <div className="h-2 w-20 overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium text-slate-700">{pct}%</span>
    </div>
  );
}

export function CoverageBadge({ coverage }: { coverage: string }) {
  const tone: Tone = coverage === "strong" ? "good" : coverage === "partial" ? "warn" : "bad";
  return <Badge tone={tone}>{coverage}</Badge>;
}

export function VerdictBadge({ verdict }: { verdict: string }) {
  const tone: Tone = verdict === "supported" ? "good" : verdict === "partly_supported" ? "warn" : "bad";
  return <Badge tone={tone}>{verdict.replace("_", " ")}</Badge>;
}

export function money(amount?: number | null, unit?: string | null) {
  if (amount == null) return "—";
  const v = `$${amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  return unit === "usd_per_hour" || unit === "hourly" ? `${v}/hr` : v;
}

export function when(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
