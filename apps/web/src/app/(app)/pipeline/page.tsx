"use client";

// Pipeline board: proposals by marketplace status (drafted → hired / lost), refreshed from marketplace events.
import Link from "next/link";
import useSWR from "swr";
import { money, when } from "@/components/badges";
import { Button, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { endpoints } from "@/lib/api/endpoints";
import { useRunEvents } from "@/lib/events";

const LABEL: Record<string, string> = {
  draft: "Drafted", submitted: "Submitted", viewed: "Viewed", replied: "Replied",
  interview: "Interview", hired: "Hired", lost: "Lost",
};

export default function PipelinePage() {
  const { data, error, isLoading, mutate } = useSWR("pipeline", endpoints.pipeline, { refreshInterval: 30_000 });
  useRunEvents((e) => {
    if (e.type === "finished") mutate();
  });
  const total = data ? Object.values(data.board).reduce((n, c) => n + c.length, 0) : 0;
  return (
    <>
      <PageHeader title="Pipeline" subtitle="Every proposal and where it stands on the marketplace."
                  actions={<Button variant="secondary" onClick={() => mutate()}>Refresh</Button>} />
      {isLoading && <Spinner />}
      {error && <ErrorState error={error} retry={() => mutate()} />}
      {data && total === 0 && <EmptyState title="No proposals yet">Approve a proposal from the inbox and it appears here.</EmptyState>}
      {data && total > 0 && (
        <div className="-mx-4 overflow-x-auto px-4 pb-2">
          <div className="grid min-w-[980px] grid-cols-7 gap-3">
            {data.columns.map((col) => (
              <section key={col} aria-label={LABEL[col]} className="rounded-xl bg-slate-100 p-2">
                <h2 className="mb-2 flex items-center justify-between px-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {LABEL[col] ?? col}<span className="rounded-full bg-white px-2 text-slate-700">{data.board[col]?.length ?? 0}</span>
                </h2>
                <ul className="space-y-2">
                  {(data.board[col] ?? []).map((p) => (
                    <li key={p.proposal_id}>
                      <Link href={`/jobs/${p.job_id}`} className="block rounded-lg bg-white p-2 text-sm shadow-sm hover:ring-1 hover:ring-slate-400">
                        <p className="line-clamp-2 font-medium text-slate-800">{p.title ?? p.job_id}</p>
                        <p className="mt-1 text-xs text-slate-500">{money(p.bid_amount, p.bid_type)} · {when(p.updated_at)}</p>
                        {p.thread_id && <p className="mt-1 text-xs text-emerald-700">Conversation open</p>}
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
