"use client";

// Analytics: reply and hire rate by category, Connects spent vs outcomes, cost and latency, skip reasons.
import useSWR from "swr";
import { Card, EmptyState, ErrorState, PageHeader, Spinner, Stat } from "@/components/ui";
import { endpoints } from "@/lib/api/endpoints";

function pct(x?: number | null) {
  return x == null ? "—" : `${Math.round(x * 100)}%`;
}

function Bar({ label, value, max, suffix = "" }: { label: string; value: number; max: number; suffix?: string }) {
  return (
    <div className="grid grid-cols-[8rem_1fr_3.5rem] items-center gap-2 text-sm">
      <span className="truncate text-slate-600">{label}</span>
      <div className="h-2.5 rounded-full bg-slate-100"><div className="h-full rounded-full bg-emerald-600" style={{ width: `${max ? (value / max) * 100 : 0}%` }} /></div>
      <span className="text-right font-medium text-slate-800">{value}{suffix}</span>
    </div>
  );
}

export default function AnalyticsPage() {
  const { data, error, isLoading, mutate } = useSWR("analytics", endpoints.analytics, { refreshInterval: 60_000 });
  if (isLoading) return <Spinner />;
  if (error) return <ErrorState error={error} retry={() => mutate()} />;
  if (!data) return null;
  const cats = Object.entries(data.by_category);
  const decisions = Object.entries(data.decisions);
  const maxDecision = Math.max(1, ...decisions.map(([, n]) => n));
  return (
    <>
      <PageHeader title="Analytics" subtitle="What GigBid did and what it got you." />
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Jobs analysed" value={data.jobs_analysed} />
        <Stat label="Proposals sent" value={data.proposals_submitted} hint={`${data.connects_spent} Connects spent`} />
        <Stat label="Reply rate" value={pct(data.reply_rate)} hint={`hire rate ${pct(data.hire_rate)}`} />
        <Stat label="p95 latency / proposal" value={`${((data.per_proposal.latency_ms_p95 ?? 0) / 1000).toFixed(0)} s`}
              hint={`${(data.per_proposal.tokens_avg ?? 0).toLocaleString()} tokens avg`} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Outcomes by category">
          {cats.length === 0 ? <EmptyState title="No outcomes yet">Outcomes appear once clients respond.</EmptyState> : (
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500"><tr><th>Category</th><th>Sent</th><th>Replied</th><th>Hired</th><th>Reply rate</th></tr></thead>
              <tbody>
                {cats.map(([c, v]) => (
                  <tr key={c} className="border-t border-slate-100">
                    <td className="py-1.5">{c.replace("_", " ")}</td><td>{v.submitted}</td><td>{v.replied + v.interview + v.hired}</td><td>{v.hired}</td>
                    <td>{pct(v.submitted ? (v.replied + v.interview + v.hired) / v.submitted : null)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card title="Decisions">
          <div className="space-y-2">{decisions.map(([d, n]) => <Bar key={d} label={d.replace("_", " ")} value={n} max={maxDecision} />)}</div>
        </Card>
        <Card title="Top skip reasons">
          {data.top_skip_reasons.length === 0 ? <p className="text-sm text-slate-500">None yet.</p> : (
            <div className="space-y-2">{data.top_skip_reasons.map(([r, n]) => <Bar key={r} label={r || "other"} value={n} max={data.top_skip_reasons[0][1]} />)}</div>
          )}
        </Card>
        <Card title="Cost and speed">
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-slate-500">p95 per job analysed</dt><dd>{((data.per_job_analysed.latency_ms_p95 ?? 0) / 1000).toFixed(0)} s</dd>
            <dt className="text-slate-500">p95 per proposal</dt><dd>{((data.per_proposal.latency_ms_p95 ?? 0) / 1000).toFixed(0)} s</dd>
            <dt className="text-slate-500">Tokens per proposal</dt><dd>{(data.per_proposal.tokens_avg ?? 0).toLocaleString()}</dd>
            <dt className="text-slate-500">Model cost</dt><dd>$0 (open models, free tiers)</dd>
          </dl>
        </Card>
      </div>
    </>
  );
}
