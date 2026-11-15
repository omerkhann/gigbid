"use client";

// Proposal studio: the draft with evidence on hover, claim checks, Critic and Compliance notes, an
// editor with "regenerate this paragraph", the exact dry-run preview with its cost, and approval.
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { ApprovalPanel } from "@/components/approval";
import { RiskBadge, StatusBadge, VerdictBadge, money } from "@/components/badges";
import { CitedText, stripCitations } from "@/components/evidence";
import { Badge, Button, Card, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { endpoints } from "@/lib/api/endpoints";
import type { BidState, Critique, ProposalApproval } from "@/lib/types";

export default function StudioPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, isLoading, mutate } = useSWR(["job", id], () => endpoints.job(id));
  const [editing, setEditing] = useState(false);
  const [paragraphs, setParagraphs] = useState<string[] | null>(null);
  const [answers, setAnswers] = useState<string[] | null>(null);
  const [bid, setBid] = useState<number | null>(null);
  const [regen, setRegen] = useState<number | null>(null);

  const pending = data?.pending_approval as ProposalApproval | undefined;
  const original = useMemo(() => (pending ? pending.draft.cover_letter.split(/\n{2,}/) : []), [pending]);

  if (isLoading) return <Spinner />;
  if (error) return <ErrorState error={error} retry={() => mutate()} />;
  if (!data) return null;
  if (!pending) {
    // After a decision the draft is no longer pending: show the outcome, not an empty studio.
    const outcome: Record<string, string> = {
      submitted: "Submitted. The client can now see your proposal.",
      rejected: "Rejected. Nothing was sent.",
      running: "Your decision is being processed…",
    };
    return (
      <>
        <PageHeader title="Proposal studio" />
        <div role="status" data-testid="approval-result" className="rounded-xl border border-slate-200 bg-white p-6">
          <p className="flex items-center gap-2 font-medium text-slate-900">
            <StatusBadge status={data.status} /> {outcome[data.status ?? ""] ?? "Nothing waiting for approval on this job."}
          </p>
          <p className="mt-3 flex gap-4 text-sm">
            <Link className="font-medium text-emerald-700 hover:underline" href={`/jobs/${id}`}>Back to the job</Link>
            {data.status === "submitted" && <Link className="font-medium text-emerald-700 hover:underline" href="/pipeline">See it in the pipeline</Link>}
          </p>
        </div>
      </>
    );
  }

  const s = data.state as BidState;
  const critiques = (s.critiques ?? []) as Critique[];
  const last = critiques[critiques.length - 1];
  const draftParas = paragraphs ?? original;
  const draftAnswers = answers ?? pending.draft.screening_answers;
  const changed = paragraphs !== null || answers !== null || bid !== null;
  const edited = changed
    ? {
        ...(paragraphs ? { cover_letter: stripCitations(draftParas.join("\n\n")) } : {}),
        ...(answers ? { screening_answers: draftAnswers.map(stripCitations) } : {}),
        ...(bid !== null ? { bid_amount: bid } : {}),
      }
    : null;

  async function regenerate(i: number) {
    setRegen(i);
    try {
      const out = await endpoints.regenerate(data!.thread_id, { paragraph: draftParas[i], instruction: "more specific and concise" });
      const next = [...draftParas];
      next[i] = out.text;
      setParagraphs(next);
      setEditing(true);
    } finally {
      setRegen(null);
    }
  }

  const unsupportedAfter = pending.claims.filter((c) => c.verdict === "unsupported").length;
  return (
    <>
      <PageHeader
        title={<>Proposal for <span className="text-slate-600">{pending.job.title}</span></>}
        subtitle={<span className="flex flex-wrap items-center gap-2"><RiskBadge score={pending.risk.score} flags={pending.risk.flags} /> fit {Math.round(pending.fit.score * 100)}% · v{pending.draft.version}</span>}
        actions={<Link href={`/jobs/${id}`}><Button variant="secondary">Job detail</Button></Link>}
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card
            title="Cover letter"
            actions={<Button variant="secondary" onClick={() => setEditing((e) => !e)} aria-pressed={editing}>{editing ? "Preview" : "Edit"}</Button>}
          >
            {!editing ? (
              <div className="space-y-3 text-sm leading-relaxed text-slate-800" data-testid="cover-letter">
                {draftParas.map((p, i) => (
                  <div key={i} className="group relative">
                    <CitedText text={p} evidence={pending.evidence} order={pending.draft.evidence_ids} />
                    <button onClick={() => regenerate(i)} disabled={regen !== null}
                            className="mt-1 block text-xs font-medium text-emerald-700 opacity-80 hover:underline disabled:text-slate-400">
                      {regen === i ? "Regenerating…" : "Regenerate this paragraph"}
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {draftParas.map((p, i) => (
                  <label key={i} className="block text-xs font-medium text-slate-500">
                    Paragraph {i + 1}
                    <textarea
                      value={p}
                      rows={Math.max(3, Math.ceil(p.length / 90))}
                      onChange={(e) => {
                        const next = [...draftParas];
                        next[i] = e.target.value;
                        setParagraphs(next);
                      }}
                      className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm text-slate-800"
                      data-testid={`paragraph-${i}`}
                    />
                  </label>
                ))}
                <p className="text-xs text-slate-500">Citations like [id] are for you; they are removed before sending.</p>
              </div>
            )}
          </Card>
          {draftAnswers.length > 0 && (
            <Card title="Screening answers">
              <ol className="space-y-3">
                {draftAnswers.map((a, i) => (
                  <li key={i} className="text-sm">
                    <p className="text-xs font-medium text-slate-500">{s.job_spec?.screening_questions?.[i] ?? `Question ${i + 1}`}</p>
                    {editing ? (
                      <textarea value={a} rows={3} onChange={(e) => {
                        const next = [...draftAnswers];
                        next[i] = e.target.value;
                        setAnswers(next);
                      }} className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm" />
                    ) : <p className="mt-1 text-slate-800"><CitedText text={a} evidence={pending.evidence} order={pending.draft.evidence_ids} /></p>}
                  </li>
                ))}
              </ol>
            </Card>
          )}
          <Card title={`Claim check: ${pending.claims.length} claim${pending.claims.length === 1 ? "" : "s"}`} actions={<Badge tone={unsupportedAfter ? "bad" : "good"}>{pending.draft.unsupported_before ?? 0} unsupported removed before review</Badge>}>
            <ul className="space-y-2">
              {pending.claims.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <VerdictBadge verdict={c.verdict} />
                  <span className="text-slate-700">{c.claim}{c.note && <span className="block text-xs text-slate-500">{c.note}</span>}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
        <div className="space-y-4">
          <Card title="What the client will see">
            <p className="text-2xl font-semibold">{money(bid ?? pending.preview.bid_amount, pending.preview.bid_type)}</p>
            <label className="mt-2 block text-xs font-medium text-slate-500">
              Change bid
              <input type="number" min={1} step="any" defaultValue={pending.preview.bid_amount}
                     onChange={(e) => setBid(e.target.value ? Number(e.target.value) : null)}
                     className="mt-1 w-32 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            </label>
            <p className="mt-3 text-sm text-slate-700">
              Costs <strong>{pending.preview.connects_cost} Connects</strong> · balance {pending.preview.balance_before} → {pending.preview.balance_after}
            </p>
            <p className="mt-1 text-xs text-slate-500">Fair band {money(pending.price.band_low, pending.price.unit)} – {money(pending.price.band_high, pending.price.unit)}. {pending.price.rationale}</p>
            {pending.preview.policy_violations.length > 0 && (
              <p role="alert" className="mt-2 text-sm text-rose-700">Marketplace policy: {pending.preview.policy_violations.map((v) => v.rule_id).join(", ")}</p>
            )}
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer text-slate-600">Exact text that will be sent</summary>
              <p className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-50 p-2 text-xs text-slate-700">{pending.preview.cover_letter}</p>
            </details>
          </Card>
          <Card title="Critic" actions={last ? <Badge tone={last.verdict === "pass" ? "good" : last.verdict === "revise" ? "warn" : "neutral"}>{last.verdict}</Badge> : null}>
            {last?.scores && (
              <dl className="mb-2 grid grid-cols-2 gap-1 text-sm">
                {Object.entries(last.scores).map(([k, v]) => (<div key={k} className="flex justify-between"><dt className="text-slate-500">{k}</dt><dd className="font-medium">{v}/5</dd></div>))}
              </dl>
            )}
            {critiques.length > 1 && <p className="mb-1 text-xs text-slate-500">{critiques.length - 1} revision(s) before this draft.</p>}
            <ul className="list-disc pl-5 text-sm text-slate-700">{last?.issues.map((i) => <li key={i}>{i}</li>)}</ul>
          </Card>
          <Card title="Compliance" actions={pending.compliance ? <Badge tone={pending.compliance.status === "pass" ? "good" : "warn"}>{pending.compliance.status}</Badge> : null}>
            <p className="text-sm text-slate-700">{pending.compliance?.reason ?? "Not checked"}</p>
          </Card>
          <ApprovalPanel threadId={data.thread_id} kind="proposal" edited={edited} sendLabel={`Approve & submit (${pending.preview.connects_cost} Connects)`}
                         onDone={() => { setParagraphs(null); setAnswers(null); setBid(null); setEditing(false); mutate(); }} />
        </div>
      </div>
    </>
  );
}
