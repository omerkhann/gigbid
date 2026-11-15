"use client";

// Job inbox: analysed jobs ranked by fit, with risk, recommended action, price and Connects cost.
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { FitMeter, RiskBadge, StatusBadge, money, when } from "@/components/badges";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { endpoints } from "@/lib/api/endpoints";
import { useRunEvents } from "@/lib/events";

const FILTERS = [
  { id: "", label: "All" },
  { id: "awaiting_approval", label: "Needs approval" },
  { id: "watching", label: "Watching" },
  { id: "skipped", label: "Skipped" },
  { id: "submitted", label: "Submitted" },
  { id: "needs_attention", label: "Needs attention" },
];

export default function InboxPage() {
  const [filter, setFilter] = useState("");
  const [jobId, setJobId] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const { data, error, isLoading, mutate } = useSWR(["inbox", filter], () => endpoints.inbox(filter));
  useRunEvents((e) => {
    if (e.type !== "node") mutate();
  });

  async function scout() {
    await endpoints.scout();
    setNote("Scout is searching your saved searches. New jobs appear here as they're analysed.");
  }
  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    if (!jobId.trim()) return;
    await endpoints.analyze(jobId.trim());
    setNote(`Analysing ${jobId.trim()}…`);
    setJobId("");
    mutate();
  }

  return (
    <>
      <PageHeader
        title="Inbox"
        subtitle="Jobs GigBid has analysed, best fit first. Nothing is sent until you approve it."
        actions={<Button onClick={scout}>Run Scout now</Button>}
      />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div role="tablist" aria-label="Filter" className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              role="tab"
              aria-selected={filter === f.id}
              onClick={() => setFilter(f.id)}
              className={`rounded-full px-3 py-1 text-sm ${filter === f.id ? "bg-slate-900 text-white" : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100"}`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <form onSubmit={analyze} className="flex gap-2">
          <label htmlFor="job-id" className="sr-only">Job id</label>
          <input id="job-id" placeholder="Analyse a job by id" value={jobId} onChange={(e) => setJobId(e.target.value)}
                 className="w-56 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <Button variant="secondary" type="submit">Analyse</Button>
        </form>
      </div>
      {note && <p role="status" className="mb-3 rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-800">{note}</p>}

      {isLoading && <Spinner />}
      {error && <ErrorState error={error} retry={() => mutate()} />}
      {data && data.length === 0 && (
        <EmptyState title="No jobs here yet">Run Scout to search your saved searches, or analyse a job by its id.</EmptyState>
      )}
      <ul className="space-y-3">
        {data?.map((r) => {
          const s = r.summary as { fit?: number; risk?: number; risk_flags?: string[]; decision?: string; price?: number; unit?: string; connects?: number };
          return (
            <li key={r.thread_id}>
              <Link href={`/jobs/${r.job_id}`} className="block rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-400 focus-visible:outline-2">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-slate-900">{r.title ?? r.job_id}</p>
                    <p className="mt-0.5 line-clamp-1 text-xs text-slate-500">{r.status_reason}</p>
                  </div>
                  <span className="shrink-0 self-start"><StatusBadge status={r.status} /></span>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                  <FitMeter score={s.fit} />
                  <RiskBadge score={s.risk} flags={s.risk_flags} />
                  {s.decision && <Badge tone={s.decision === "bid" ? "good" : "neutral"}>Recommend: {s.decision}</Badge>}
                  {s.price != null && <span className="text-slate-700">{money(s.price, s.unit)}</span>}
                  {s.connects != null && <span className="text-slate-500">{s.connects} Connects</span>}
                  <span className="ml-auto text-xs text-slate-400">{when(r.updated_at)}</span>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
      {data && data.length > 0 && <Card className="mt-6" title="Tip"><p className="text-sm text-slate-600">Open a job to see why GigBid recommends it: each requirement is matched to evidence from your portfolio.</p></Card>}
    </>
  );
}
