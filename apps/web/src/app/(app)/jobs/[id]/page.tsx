"use client";

// Job detail: what the agents found and why they recommend bidding or skipping.
import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { CoverageBadge, FitMeter, RiskBadge, StatusBadge, money } from "@/components/badges";
import { EvidenceChip } from "@/components/evidence";
import { RunTimeline } from "@/components/timeline";
import { Badge, Button, Card, ErrorState, PageHeader, Spinner, TextLink } from "@/components/ui";
import { endpoints } from "@/lib/api/endpoints";
import type { BidState } from "@/lib/types";

function List({ items, empty = "None" }: { items?: string[]; empty?: string }) {
  if (!items?.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{items.map((i) => <li key={i}>{i}</li>)}</ul>;
}

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, isLoading, mutate } = useSWR(["job", id], () => endpoints.job(id));
  if (isLoading) return <Spinner />;
  if (error) return <ErrorState error={error} retry={() => mutate()} />;
  if (!data) return null;

  const s = data.state as BidState;
  const spec = s.job_spec;
  const risk = s.risk_report;
  const fit = s.fit_report;
  const price = s.price_quote;
  const evidence = s.evidence ?? {};
  const order = fit?.evidence_ids ?? [];
  const waiting = !!data.pending_approval;

  return (
    <>
      <PageHeader
        title={s.job?.title ?? id}
        subtitle={<span className="flex flex-wrap items-center gap-2"><StatusBadge status={data.status} /> {data.status_reason}</span>}
        actions={
          <>
            {waiting && <Link href={`/studio/${id}`}><Button>Review proposal</Button></Link>}
            <Link href={`/runs/${encodeURIComponent(data.thread_id)}`}><Button variant="secondary">Agent run</Button></Link>
          </>
        }
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card title="Requirement → evidence" actions={<FitMeter score={fit?.score} />}>
            {fit ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase text-slate-500">
                    <tr><th className="py-1 pr-3">Requirement</th><th className="py-1 pr-3">Coverage</th><th className="py-1 pr-3">Evidence</th><th className="py-1">Why</th></tr>
                  </thead>
                  <tbody>
                    {fit.requirements.map((r) => (
                      <tr key={r.requirement} className="border-t border-slate-100 align-top">
                        <td className="py-2 pr-3 font-medium text-slate-800">{r.requirement}</td>
                        <td className="py-2 pr-3"><CoverageBadge coverage={r.coverage} /></td>
                        <td className="py-2 pr-3">
                          {r.evidence_ids.length ? r.evidence_ids.map((e) => (
                            <EvidenceChip key={e} id={e} n={order.indexOf(e) + 1 || 0} evidence={evidence[e]} />
                          )) : <span className="text-slate-400">—</span>}
                        </td>
                        <td className="py-2 text-slate-600">{r.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <p className="text-sm text-slate-500">Fit not computed yet.</p>}
          </Card>
          <Card title="What the job needs (Job Analyst)">
            <div className="grid gap-4 sm:grid-cols-2">
              <div><p className="mb-1 text-xs font-semibold uppercase text-slate-500">Deliverables</p><List items={spec?.deliverables} /></div>
              <div><p className="mb-1 text-xs font-semibold uppercase text-slate-500">Requirements</p><List items={spec?.requirements} /></div>
              <div><p className="mb-1 text-xs font-semibold uppercase text-slate-500">Hidden needs</p><List items={spec?.hidden_needs} /></div>
              <div><p className="mb-1 text-xs font-semibold uppercase text-slate-500">Screening questions</p><List items={spec?.screening_questions} /></div>
            </div>
            {spec?.red_flags?.length ? <div className="mt-3"><p className="mb-1 text-xs font-semibold uppercase text-rose-600">Red flags</p><List items={spec.red_flags} /></div> : null}
          </Card>
          <Card title="Job post">
            <p className="max-h-72 overflow-y-auto whitespace-pre-wrap text-sm text-slate-700">{s.job?.description}</p>
          </Card>
        </div>
        <div className="space-y-4">
          <Card title="Bid or skip">
            {s.decision ? (
              <>
                <Badge tone={s.decision.action === "bid" ? "good" : s.decision.action === "watch" ? "warn" : "neutral"}>{s.decision.action}</Badge>
                <List items={s.decision.reasons} />
              </>
            ) : <p className="text-sm text-slate-500">Not decided yet.</p>}
          </Card>
          <Card title="Risk" actions={<RiskBadge score={risk?.score} flags={risk?.flags} />}>
            {risk ? (
              <>
                <p className="text-sm text-slate-700">{risk.client_summary}</p>
                <div className="my-2 flex flex-wrap gap-1">{risk.flags.map((f) => <Badge key={f} tone="warn">{f.replace(/_/g, " ")}</Badge>)}</div>
                <p className="text-xs text-slate-500">{risk.explanation}</p>
              </>
            ) : <p className="text-sm text-slate-500">Not assessed yet.</p>}
          </Card>
          <Card title="Price">
            {price ? (
              <>
                <p className="text-2xl font-semibold">{money(price.amount, price.unit)}</p>
                <p className="text-xs text-slate-500">Fair band {money(price.band_low, price.unit)} – {money(price.band_high, price.unit)}</p>
                <p className="mt-2 text-sm"><Badge tone={price.worth_connects ? "good" : "bad"}>{price.connects_cost} Connects · {price.worth_connects ? "worth it" : "not worth it"}</Badge></p>
                <p className="mt-2 text-xs text-slate-600">{price.rationale}</p>
              </>
            ) : <p className="text-sm text-slate-500">Priced only when GigBid recommends bidding.</p>}
          </Card>
          <Card title="Agent steps" actions={data.trace_url ? <TextLink href={data.trace_url}>Trace</TextLink> : null}>
            <RunTimeline threadId={data.thread_id} saved={data.events} onFinished={() => mutate()} />
          </Card>
        </div>
      </div>
    </>
  );
}
