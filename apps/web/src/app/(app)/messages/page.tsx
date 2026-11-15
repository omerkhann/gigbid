"use client";

// Client conversations, with suggested replies waiting for approval.
import Link from "next/link";
import useSWR from "swr";
import { StatusBadge } from "@/components/badges";
import { Badge, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { endpoints } from "@/lib/api/endpoints";
import { useRunEvents } from "@/lib/events";

export default function MessagesPage() {
  const { data, error, isLoading, mutate } = useSWR("threads", endpoints.threads, { refreshInterval: 30_000 });
  useRunEvents((e) => {
    if (e.type !== "node" && e.thread_id.startsWith("conv:")) mutate();
  });
  return (
    <>
      <PageHeader title="Messages" subtitle="Client replies. GigBid drafts a response; you approve it before it's sent." />
      {isLoading && <Spinner />}
      {error && <ErrorState error={error} retry={() => mutate()} />}
      {data && data.threads.length === 0 && <EmptyState title="No conversations yet">When a client replies to a proposal, the conversation appears here.</EmptyState>}
      <ul className="space-y-2">
        {data?.threads.map((t) => (
          <li key={t.thread_id}>
            <Link href={`/messages/${t.thread_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-400">
              <div>
                <p className="font-medium text-slate-900">Client {t.client_id.slice(-6)} · job {t.job_id.slice(-6)}</p>
                <p className="text-xs text-slate-500">Proposal status: {t.status}{t.accepting_messages ? "" : " (closed)"}</p>
              </div>
              <div className="flex items-center gap-2">
                {t.intent && <Badge tone={t.intent === "scam_signal" ? "bad" : "info"}>{t.intent.replace("_", " ")}</Badge>}
                {t.agent_status && <StatusBadge status={t.agent_status} />}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
