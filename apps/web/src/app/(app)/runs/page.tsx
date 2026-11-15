"use client";

import Link from "next/link";
import useSWR from "swr";
import { StatusBadge, when } from "@/components/badges";
import { EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { endpoints } from "@/lib/api/endpoints";
import { useRunEvents } from "@/lib/events";

export default function RunsPage() {
  const { data, error, isLoading, mutate } = useSWR("runs", endpoints.runs);
  useRunEvents(() => mutate());
  return (
    <>
      <PageHeader title="Agent runs" subtitle="Every graph thread: job analyses and conversations, with live progress." />
      {isLoading && <Spinner />}
      {error && <ErrorState error={error} retry={() => mutate()} />}
      {data && data.length === 0 && <EmptyState title="No runs yet" />}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        {data && data.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr><th className="px-3 py-2">Run</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Tokens</th><th className="px-3 py-2">Time</th><th className="px-3 py-2">Updated</th></tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.thread_id} className="border-t border-slate-100">
                  <td className="px-3 py-2"><Link className="font-medium text-emerald-700 hover:underline" href={`/runs/${encodeURIComponent(r.thread_id)}`}>{r.title ?? r.thread_id}</Link><span className="block text-xs text-slate-400">{r.kind}</span></td>
                  <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
                  <td className="px-3 py-2">{r.tokens.toLocaleString()}</td>
                  <td className="px-3 py-2">{(r.latency_ms / 1000).toFixed(1)} s</td>
                  <td className="px-3 py-2 text-xs text-slate-500">{when(r.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
